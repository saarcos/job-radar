# Job Radar — documento de implementación

Agregador de ofertas remotas con adaptación de CV por oferta. Corre **local**, con `docker compose up`, con la API key del usuario.

Este documento es la fuente de verdad. Cada bloque se le entrega a Claude Code tal cual, sin decidir nada sobre la marcha.

---

## 0. Decisiones cerradas

No se rediscuten durante la implementación. Si algo no funciona, se anota y se cambia **aquí** primero.

| # | Decisión | Elegido | Por qué |
|---|---|---|---|
| 1 | Usuarios | Uno solo, sin auth | Corre local; otro usuario clona el repo y levanta su instancia |
| 2 | Despliegue | Ninguno. `docker compose up` | Un Neon dormido es fricción; el objetivo es usarlo, no alojarlo |
| 3 | Base de datos | Postgres en compose | Un solo `up` levanta todo sin instalar nada en la máquina |
| 4 | ORM | SQLAlchemy 2.0 desde el primer commit | Sin etapa de SQL crudo "para aprender" |
| 5 | Migraciones | Alembic, corriendo al arranque del contenedor | |
| 6 | Idioma de los facts | Uno solo (el que elija el usuario en `profile.facts_language`) | Evita mantener dos versiones, que era el dolor original |
| 7 | Idioma del CV | Se elige al generar/descargar; por defecto el de la oferta | Una versión por `(oferta, idioma)`. Las ediciones manuales **no** se arrastran entre idiomas |
| 8 | Ofertas cerradas | Nunca se borran; `is_open = false` + `closed_at` | Si aplicaste, querés el registro |
| 9 | Detección de cierre | Vía `sync_runs`, por fuente, solo tras un sync exitoso | Un sync fallido no puede cerrar nada |
| 10 | Filtros | Guardados en `search_profiles` | Se usan siempre los mismos |
| 11 | API key | Variable de entorno en `.env` | Local y de un usuario; guardarla en la base no aporta |
| 12 | PDF | HTML + CSS → WeasyPrint, en el backend | CSS normal en vez de la API de react-pdf |
| 13 | Plantilla de CV | Una sola, fija, de una columna | Dos columnas rompen la extracción de varios ATS |
| 14 | Import de PDF | Atajo opcional; **revisión obligatoria** antes de guardar | El parseo va a salir a medias siempre |
| 15 | Validador rechaza | Se muestra al usuario; reintento **manual** | El usuario firma el CV, no el sistema |
| 16 | Dedupe entre idiomas | No se resuelve | Una oferta en ES y EN se ve dos veces. Aceptado |
| 17 | Frontend | React + Vite + TypeScript | |
| 18 | Scraping | No | Las tres fuentes elegidas tienen API o RSS |

### No-goals

Cron / scheduler · deploy en la nube · multiusuario · auth · scoring de ofertas con LLM · evals · auto-apply · LinkedIn / Indeed · notificaciones.

---

## 1. Fuentes

| Fuente | Endpoint | Formato | Notas |
|---|---|---|---|
| **Get on Board** | `https://www.getonbrd.com/api/v0/search/jobs?query=...` y `/api/v0/categories/{id}/jobs` | JSON | La mejor del conjunto. Pública, sin auth. Trae descripción completa, modalidad, países, rango salarial y **número de postulaciones**. LATAM + España, ofertas mayormente en español pero también en inglés; su campo `lang` suele venir `lang_not_specified`, por eso el idioma se detecta (B3). El nombre de la empresa solo viene pidiendo `expand=["company"]`. Doc: `api-doc.getonbrd.com` |
| **We Work Remotely** | `https://weworkremotely.com/categories/remote-programming-jobs.rss` | RSS | Descripción en HTML. Título viene como `"Empresa: Puesto"`. Trae campo `region` |
| **Remotive** | `https://remotive.com/api/remote-jobs?category=software-dev` | JSON | Su categoría es ruidosa (devuelve copywriters y ventas). **Ignorar su filtro** y filtrar nosotros |

**Regla de implementación:** verificar la forma real de la respuesta antes de escribir el adaptador. Guardar una respuesta recortada a 2–3 ofertas en `tests/fixtures/<fuente>_sample.<json|xml>`, según el formato de la fuente (`getonboard_sample.json`, `wwr_sample.xml`), y testear el mapeo contra ese archivo. Ningún test sale a la red.

---

## 2. Esquema

### 2.1 Lado ofertas

```
sources
  id            int pk
  slug          text unique        -- 'getonboard' | 'weworkremotely' | 'remotive'
  name          text
  enabled       bool default true
  priority      int                -- menor gana el merge: getonboard 0, wwr 1, remotive 2

sync_runs
  id            bigint pk
  source_id     int fk -> sources
  started_at    timestamptz
  finished_at   timestamptz null
  status        text               -- 'running' | 'ok' | 'failed'
  postings_seen int default 0
  error         text null

job_postings                       -- una fila por vacante real
  id              bigint pk
  canonical_key   text unique
  company         text             -- valor original, legible
  title           text             -- valor original, legible
  url             text             -- la de la fuente de mejor prioridad
  description_md  text null
  region_hint     text null        -- 'Anywhere in the World', 'US only'... null si la fuente no lo da
  salary_raw      text null        -- texto tal cual; sin parsear
  language        text null        -- 'es' | 'en', detectado del título+descripción
  posted_at       timestamptz null
  status          text default 'new'   -- 'new' | 'seen' | 'dismissed'
  is_open         bool default true
  closed_at       timestamptz null
  first_seen_at   timestamptz
  last_seen_at    timestamptz

job_posting_sources                -- una fila por (oferta, fuente) donde se vio
  id              bigint pk
  job_posting_id  bigint fk -> job_postings on delete cascade
  source_id       int fk -> sources
  external_id     text
  url             text
  payload_json    jsonb            -- crudo, sin interpretar
  content_hash    text
  first_seen_at   timestamptz
  last_seen_at    timestamptz
  unique (source_id, external_id)

search_profiles
  id                int pk
  name              text
  include_keywords  text[]         -- OR entre ellas
  exclude_keywords  text[]
  exclude_seniority text[]         -- ['staff','principal','director','head','vp','manager','lead']
  languages         text[] null
  max_age_days      int default 30
  source_slugs      text[] null    -- null = todas
  is_default        bool default false

applications
  id                 bigint pk
  job_posting_id     bigint fk unique
  resume_version_id  bigint fk null
  status             text          -- 'applied'|'screening'|'interview'|'rejected'|'offer'|'ghosted'
  applied_at         timestamptz
  notes              text null
```

**Por qué `job_posting_sources` y no una tabla `raw_postings` aparte:** cada avistamiento guarda su propio `external_id`, su URL y su payload crudo. Así sabés no solo dónde más se vio la oferta, sino con qué link y qué dijo cada fuente — y podés reconstruir `job_postings` desde cero sin volver a pegarle a ninguna API.

### 2.2 Lado CV (los "facts")

Cada tabla espeja un bloque de la plantilla. Eso hace que la UI de edición salga casi sola.

```
profile                            -- fila única, id siempre 1
  id             int pk default 1 check (id = 1)
  full_name      text
  headline       text              -- default; el LLM lo adapta por oferta
  location       text
  email          text
  phone          text null
  links          jsonb             -- [{label, url}]
  facts_language text default 'es'
  summary        text null         -- resumen por defecto

experiences
  id          int pk
  role        text
  company     text
  location    text null
  start_date  date
  end_date    date null            -- null = actualidad
  sort_order  int

experience_bullets
  id             int pk
  experience_id  int fk -> experiences on delete cascade
  text           text
  tech           text[]            -- tecnologías que ESTE bullet respalda
  sort_order     int

projects
  id          int pk
  name        text
  kind        text                 -- 'personal' | 'university' | 'work'
  repo_url    text null
  live_url    text null
  sort_order  int

project_bullets                    -- misma forma que experience_bullets
  id, project_id fk, text, tech text[], sort_order

education
  id, degree, institution, location, graduation_date, sort_order

skills
  id, category text, name text, sort_order
                                   -- category: 'languages'|'backend'|'frontend'|'tools'|'languages_spoken'

certifications
  id, name, issuer, issued_date, url, sort_order

resume_versions
  id                 bigint pk
  job_posting_id     bigint fk null     -- null = CV base
  language           text
  content_json       jsonb              -- el AdaptedResume completo
  validation_json    jsonb              -- el ValidationReport
  model              text null
  prompt_version     text null
  created_at         timestamptz
  edited_at          timestamptz null   -- no null = el usuario lo tocó a mano
```

**`sort_order` en todas:** el orden de los bullets es información y el usuario lo va a querer cambiar.

**`tech[]` por bullet, no solo global:** es lo que permite al validador distinguir "esta tecnología la usé *en este trabajo*" de "la conozco". Sin eso el validador no sirve.

---

## 3. Estructura del proyecto

```
job-radar/
├── docker-compose.yml
├── Dockerfile                    # backend
├── .env.example
├── README.md
├── IMPLEMENTATION.md             # este archivo
├── pyproject.toml
├── alembic.ini
├── migrations/
├── src/jobradar/
│   ├── config.py                 # pydantic-settings
│   ├── domain/                   # NO importa nada de adapters/, api/ ni librerías de IO
│   │   ├── entities.py           # dataclasses puros
│   │   ├── normalize.py          # company(), title(), canonical_key()
│   │   ├── html_text.py          # to_markdown()
│   │   ├── language.py           # detect()
│   │   ├── prefilter.py          # matches(posting, profile) -> bool
│   │   └── validation.py         # validate(adapted, facts) -> ValidationReport
│   ├── ports/
│   │   ├── job_source.py         # Protocol JobSource, RawJob
│   │   ├── llm.py                # Protocol LLMClient
│   │   └── renderer.py           # Protocol ResumeRenderer
│   ├── application/              # casos de uso; orquestan, no deciden reglas
│   │   ├── sync_jobs.py
│   │   ├── list_jobs.py
│   │   ├── import_facts.py
│   │   └── generate_resume.py
│   ├── adapters/
│   │   ├── sources/{getonboard,weworkremotely,remotive}.py
│   │   ├── llm/{anthropic_client,fake_client}.py
│   │   ├── persistence/{db,models,repositories/}.py
│   │   └── render/{weasyprint_renderer.py, templates/resume.html.j2, templates/resume.css}
│   ├── api/
│   │   ├── main.py               # crea la app y monta los routers bajo /api
│   │   ├── dependencies.py       # cablea adapters → routers; los routers no importan adapters/
│   │   ├── schemas.py            # Pydantic de request/response
│   │   └── routers/{health,jobs,facts,resumes,sync,applications}.py
│   └── cli.py                    # typer: sync, generate, export
├── tests/
│   ├── fixtures/
│   ├── fakes.py
│   ├── unit/test_*.py            # sin red ni base de datos
│   └── integration/test_*.py     # contra el Postgres de compose y el de CI
└── web/                          # React + Vite + TS
    ├── package.json
    └── src/
        ├── api/client.ts
        ├── pages/{Jobs,JobDetail,Facts,Resume}.tsx
        └── components/
```

**Regla de puertos.** Solo hay tres, y cada uno existe por un motivo verificable:

| Puerto | Segunda implementación | Falseado en tests |
|---|---|---|
| `JobSource` | Sí — tres fuentes | Sí — `FakeSource` |
| `LLMClient` | Sí — proveedores distintos | Sí — `FakeLLMClient` |
| `ResumeRenderer` | Posible (HTML vs PDF) | Sí |

**No hay `Repository` port.** Postgres no se va a cambiar, y falsear la persistencia con un repo in-memory testearía una mentira: no reproduce `ON CONFLICT` ni los constraints. Los tests de persistencia corren contra el Postgres de compose y el de CI.

---

## 4. Contratos

### 4.1 `ports/job_source.py`

```python
@dataclass(frozen=True)
class RawJob:
    external_id: str
    url: str
    payload: dict  # solo campos serializables a JSON


@dataclass(frozen=True)
class JobData:
    company: str
    title: str
    url: str
    description_md: str | None
    region_hint: str | None
    salary_raw: str | None
    posted_at: datetime | None
    source_slug: str

    @property
    def canonical_key(self) -> str:
        return normalize.canonical_key(self.company, self.title)


class JobSource(Protocol):
    slug: str

    def fetch(self) -> list[RawJob]: ...
    def to_job(self, raw: RawJob) -> JobData: ...
```

Cada adaptador extrae su propio `external_id` y mapea su propio payload. La persistencia nunca conoce la forma de ninguna fuente. Campo que la fuente no da → `None`, **nunca un valor por defecto inventado**: un `None` honesto es información, un `"worldwide"` inventado es una mentira que después el LLM se cree.

### 4.2 `ports/llm.py`

```python
T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def complete_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 4096,
    ) -> LLMResult[T]: ...


@dataclass
class LLMResult(Generic[T]):
    value: T
    model: str
    tokens_in: int
    tokens_out: int
```

Una sola operación. El modelo es configuración (`LLM_MODEL` en `.env`), no código.

### 4.3 `ports/renderer.py`

```python
class ResumeRenderer(Protocol):
    def to_html(self, resume: AdaptedResume, profile: Profile) -> str: ...
    def to_pdf(self, resume: AdaptedResume, profile: Profile) -> bytes: ...
```

---

## 5. El pipeline de sync

```
fetch → to_job → upsert raw → proyectar a job_postings → cerrar las ausentes
```

### Orden exacto, en `application/sync_jobs.py`

```python
def sync(session, sources: list[JobSource]) -> SyncSummary:
    collected: list[tuple[int, RawJob, JobData]] = []

    # 1 — traer de cada fuente. Una que falle no corta el resto ni cierra nada.
    for source in sources:
        run = start_run(session, source.slug)  # sync_runs: status='running'
        try:
            raws = source.fetch()
            pairs = [(r, source.to_job(r)) for r in raws]
        except Exception as exc:
            fail_run(session, run, exc)
            continue
        collected.extend((run.source_id, r, j) for r, j in pairs)
        finish_run(session, run, len(raws))  # status='ok'

    # Pasos 2-4 en UNA transacción: si el proceso muere en el medio,
    # no pueden quedar ofertas reabiertas que debían cerrarse.
    with session.begin_nested():
        # 2 — crear/actualizar las ofertas. UNA llamada con todas las fuentes
        #     juntas: es lo que hace posible el merge por prioridad.
        key_to_id = upsert_postings(session, [j for _, _, j in collected])

        # 3 — recién ahora los avistamientos: necesitan el job_posting_id,
        #     que no existe hasta el paso 2 (FK job_posting_sources -> job_postings).
        save_sightings(session, collected, key_to_id)

        # 4 — cerrar lo que ninguna fuente vigente sigue listando.
        close_missing(session)
```

**El paso 3 va después del 2, no antes.** `job_posting_sources.job_posting_id` es una FK: para una oferta nueva, la fila de `job_postings` todavía no existe. Invertir el orden falla por violación de clave foránea en el primer sync.

**Cuidado con las dos columnas homónimas.** Hay dos `last_seen_at`:

| Columna | Qué la refresca | Para qué sirve |
|---|---|---|
| `job_postings.last_seen_at` | Cualquier fuente que vea la oferta | Mostrar "vista hace X" en la UI |
| `job_posting_sources.last_seen_at` | Solo esa fuente | **Decidir el cierre** |

`close_missing` lee **siempre** la de `job_posting_sources`. Si lee la de `job_postings`, el upsert del paso 2 acaba de ponerla en `NOW()` y entonces **no se cierra nada nunca** — un bug silencioso: no falla, solo te llena la lista de vacantes muertas.

**El upsert y el cierre no compiten**, porque operan sobre conjuntos disjuntos: el upsert toca solo lo que vino en este sync (y por eso `is_open = true, closed_at = null` es correcto — una oferta republicada se reabre), y `close_missing` toca solo lo que no vino.

### Dedupe y merge

`upsert_postings` se llama **una vez con todas las fuentes juntas**. Eso es lo que hace posible el merge por prioridad:

```python
ordered = sorted(jobs, key=lambda j: SOURCE_PRIORITY.get(j.source_slug, 99))
seen = {}
for j in ordered:
    seen.setdefault(j.canonical_key, j)  # el primero (mejor prioridad) gana
```

Después un `INSERT ... ON CONFLICT (canonical_key) DO UPDATE SET last_seen_at = NOW(), is_open = true, closed_at = null`.

Dos cosas que importan:

- **Deduplicar en Python antes del insert es obligatorio**, no una optimización: Postgres falla con *"cannot affect row a second time"* si un mismo `INSERT` trae dos filas con la misma `canonical_key`.
- **Limitación conocida:** el merge solo resuelve dentro de una corrida. Si hoy la oferta entra por Remotive y mañana agregás Get on Board, la fila ya existe y conserva la URL fea. Por eso se guardan los payloads crudos: se puede reconstruir. Documentarlo en el commit, no esconderlo.

### Cierre de ofertas

**El principio:** un avistamiento quedó viejo si su `last_seen_at` es anterior al `started_at` de la última corrida **exitosa** de su fuente — significa que esa fuente corrió bien y ya no la listó. Una oferta se cierra solo cuando **todos** sus avistamientos quedaron viejos.

Son dos pasos y el orden importa:

```python
def close_missing(session) -> int:
    # Paso 1 — por fuente: qué avistamientos quedaron viejos
    stale_by_source: dict[int, datetime] = {}
    for source in enabled_sources(session):
        last_ok = last_successful_run(session, source.id)
        if last_ok is None:
            continue  # nunca corrió bien: no envejece nada
        stale = count_sightings_older_than(session, source.id, last_ok.started_at)
        total = count_sightings(session, source.id)
        if total and stale / total > 0.5:
            log.warning("skipping staleness for %s: %d/%d", source.slug, stale, total)
            continue  # cambió el formato, no cerraron todas
        stale_by_source[source.id] = last_ok.started_at

    # Paso 2 — cerrar las ofertas sin NINGÚN avistamiento vigente
    return mark_closed_without_fresh_sightings(session, stale_by_source)
```

```sql
-- mark_closed_without_fresh_sightings, con :cutoffs = {source_id: started_at}
UPDATE job_postings p
   SET is_open = false, closed_at = NOW()
 WHERE p.is_open
   -- al menos una fuente evaluable la vio alguna vez
   AND EXISTS (SELECT 1 FROM job_posting_sources s
                WHERE s.job_posting_id = p.id AND s.source_id IN :evaluated)
   -- y ninguna la sigue listando
   AND NOT EXISTS (SELECT 1 FROM job_posting_sources s
                    WHERE s.job_posting_id = p.id
                      AND (s.source_id NOT IN :evaluated          -- fuente sin corrida ok: cuenta como vigente
                           OR s.last_seen_at >= :cutoff_of(s.source_id)))
```

**Por qué no se decide fuente por fuente:** si WWR deja de listar la oferta pero Get on Board todavía la publica, la vacante sigue abierta. Cerrarla ahí sería ocultarte una oferta viva, y en silencio — el peor tipo de bug, porque nada falla.

**Las dos redes de seguridad:** una fuente que falló (o que nunca corrió bien) no envejece nada, y el corte del 50% frena el caso de un cambio de formato que vaciaría la lista de golpe.

**Test obligatorio del bloque:** una oferta vista por dos fuentes, una de las cuales deja de listarla, sigue `is_open = true`.

---

## 6. Prefiltro

`domain/prefilter.py`, funciones puras, **sin LLM**. Decide qué ofertas se le muestran al usuario.

```python
def matches(posting: JobPosting, profile: SearchProfile) -> bool
def reasons(posting: JobPosting, profile: SearchProfile) -> list[str]   # para depurar el filtro
```

Reglas, en orden:

1. `posted_at` más viejo que `max_age_days` → fuera
2. `status == 'dismissed'` o existe `application` → fuera
3. Título contiene algo de `exclude_seniority` → fuera
4. Título o descripción contiene algo de `exclude_keywords` → fuera
5. Ninguna de `include_keywords` aparece en título ni descripción → fuera
6. `language` no está en `profile.languages` (si está definido) → fuera

Todo sobre `description_md`, **nunca sobre el HTML crudo**: en HTML, `python` aparece dentro de URLs y da falsos positivos.

Perfil por defecto que se siembra en la migración:

```yaml
name: Backend / Fullstack
include_keywords: [python, fastapi, django, flask, backend, node, typescript, react, fullstack, full-stack]
exclude_keywords: [sales, marketing, designer, recruiter, copywriter, customer support, data entry]
exclude_seniority: [staff, principal, director, "head of", vp, manager, architect, lead]
max_age_days: 30
```

**Criterio de aceptación:** descarta ≥70% de lo que entra, y ninguna oferta a la que vos aplicarías. Verificarlo a mano una vez sobre ~50 ofertas reales.

### Dónde corre el filtro

**Sync escribe en la base; los filtros leen de la base.** Cambiar un filtro vuelve a consultar la base y **nunca** le pega de nuevo a las fuentes. Sincronizás cuando querés y después cambiás filtros gratis.

El filtrado corre en el **servidor**, no en el navegador: las reglas ya están en `domain/prefilter.py` con tests, y duplicarlas en TypeScript garantiza que diverjan. Además cada oferta arrastra su `description_md`, que son varios KB — mandar 500 al navegador para mostrar 30 es inútil.

Y **el filtro no se traduce a SQL.** El orden dentro de `list_jobs.py` es:

```python
candidates = repo.open_postings(
    session,
    max_age_days=profile.max_age_days,
    exclude_status=["dismissed"],
    exclude_applied=True,
)
matched = [p for p in candidates if prefilter.matches(p, profile)]
return paginate(matched, page, size)
```

SQL hace lo barato y grueso; las reglas corren en Python sobre ese conjunto. A esta escala (cientos, a lo sumo miles de filas) es instantáneo, y mantiene las reglas en un solo lugar probado en vez de repartidas entre Python y SQL. Si algún día no alcanza, se traducen a SQL — pero no antes de medirlo.

**Nada de esto se persiste.** El filtro se calcula al leer, así que editar un `search_profile` tiene efecto en la consulta siguiente sin reprocesar nada.

---

## 7. Adaptación del CV

Es el núcleo. Tres piezas separadas: prompt, schema, validador.

### 7.1 Lo que recibe el LLM

- `FactsBundle`: profile + experiences + bullets (con su `tech[]`) + projects + education + skills
- `JobPosting`: título, empresa, `description_md`, idioma
- El idioma destino

### 7.2 Lo que devuelve

```python
class AdaptedBullet(BaseModel):
    source_id: str  # "exp:12" | "proj:3" — DEBE existir en los facts
    text: str  # reescritura; mismo hecho, vocabulario de la oferta


class AdaptedResume(BaseModel):
    headline: str
    summary: str
    experiences: list[AdaptedExperience]  # cada una con su id de origen y sus bullets
    projects: list[AdaptedProject]
    skills_highlighted: list[str]
    language: str
    omitted_source_ids: list[str]  # qué dejó fuera y por qué
```

**El LLM selecciona, ordena, reescribe y traduce. No inventa hechos nuevos.** Lo que sí puede hacer libremente, y es donde está casi toda la ganancia real:

- elegir qué bullets aparecen y cuáles no
- reordenarlos por relevancia
- usar el vocabulario de la oferta ("REST APIs" donde tu bullet dice "endpoints HTTP")
- reescribir el `headline` y el `summary` para esa oferta
- destacar un subconjunto de skills

### 7.3 El validador

`domain/validation.py`, **código determinista, sin LLM**, corre siempre.

```python
@dataclass
class Issue:
    severity: Literal["blocking", "warning"]
    code: str
    field: str
    message: str

@dataclass
class ValidationReport:
    issues: list[Issue]
    @property
    def ok(self) -> bool:
        return not any(i.severity == "blocking" for i in self.issues)

def validate(adapted: AdaptedResume, facts: FactsBundle) -> ValidationReport
```

| Código | Severidad | Regla |
|---|---|---|
| `unknown_source` | blocking | Un `source_id` que no existe en los facts |
| `duplicate_bullet` | blocking | El mismo `source_id` dos veces |
| `invented_number` | blocking | Un número en el texto adaptado que no está en el bullet original |
| `undeclared_tech` | blocking | Una tecnología reconocida que no está en el `tech[]` del bullet, ni en `skills`, ni implicada |
| `skill_not_declared` | blocking | `skills_highlighted` con algo que no está en `skills` |
| `seniority_claim` | warning | El headline afirma un nivel que el perfil no declara |
| `too_long` | warning | Supera el presupuesto de caracteres de una página |

**El mapa de implicaciones** (`domain/tech_aliases.yaml`, editable):

```yaml
fastapi:    [python, rest, api, asgi, pydantic]
sqlalchemy: [python, sql, orm]
react:      [javascript, typescript, frontend, jsx]
postgresql: [sql, postgres, rdbms]
docker:     [containers, containerization]
```

Esto es lo que evita que el validador bloquee una reescritura legítima: si el bullet dice FastAPI y la oferta pide "REST APIs", la reescritura pasa.

**Qué pasa cuando hay un `blocking`:** se guarda la versión igual, con su `validation_json`, y la UI muestra los problemas señalando el bullet. El usuario decide: regenerar, o editar a mano. **Nunca se descarta en silencio ni se degrada a "publicar igual".**

**Nota sobre la traducción:** números y nombres de tecnología sobreviven al cambio de idioma (son dígitos y nombres propios), así que el validador funciona igual con facts en español y CV en inglés. La excepción son los números escritos en palabras — por eso, en los facts, escribí siempre dígitos: "2 años", no "dos años".

### 7.4 Import de PDF

```
POST /api/facts/import      → sube PDF, devuelve un FactsBundle DRAFT. No guarda nada.
POST /api/facts/import/confirm → guarda lo que el usuario revisó y confirmó
```

El draft **nunca** toca la base antes de la confirmación. La pantalla de revisión muestra bullet por bullet con checkbox. Asumí que el parseo va a salir a medias: PDFs con columnas o tablas se extraen mal, y la corrección es parte del flujo, no un extra.

---

## 8. API

```
GET    /api/health

POST   /api/sync                         → corre el pipeline, devuelve SyncSummary
GET    /api/sync/runs                    → últimas corridas por fuente

GET    /api/jobs?profile_id=&status=&page=
GET    /api/jobs/{id}
PATCH  /api/jobs/{id}                    → { status: 'seen' | 'dismissed' }

GET    /api/search-profiles
POST   /api/search-profiles
PUT    /api/search-profiles/{id}
DELETE /api/search-profiles/{id}

GET    /api/facts                        → el FactsBundle completo
PUT    /api/profile
POST   /api/experiences                  → CRUD estándar; igual para bullets,
PUT    /api/experiences/{id}                projects, education, skills, certifications
DELETE /api/experiences/{id}
POST   /api/facts/import                 → multipart PDF → draft
POST   /api/facts/import/confirm

POST   /api/jobs/{id}/resume             → { language } → devuelve la versión de ese
                                            idioma si existe; si no, genera, valida y guarda
GET    /api/resume-versions/{id}
PUT    /api/resume-versions/{id}         → edición manual; marca edited_at
GET    /api/resume-versions/{id}.pdf     → el PDF
GET    /api/resume-versions/base.pdf?language=es

POST   /api/jobs/{id}/application        → { status, notes }
PATCH  /api/applications/{id}
```

---

## 9. Bloques de trabajo

Cada bloque: 30–60 min, autocontenido, con criterio de terminado verificable. Una rama por bloque, un PR, CI en verde antes de mergear.

### Fase 1 — Ofertas (sin LLM)

**B1 · Esqueleto**
Repo, `pyproject.toml` con el paquete declarado, Docker multi-stage sobre `python:3.12-slim` con usuario no-root y `.dockerignore`, compose con `db` + `api`, Alembic corriendo al arranque del contenedor, `config.py` con pydantic-settings y `.env.example`, ruff + mypy + pytest instalados.
*Listo:* `docker compose up` levanta y `/api/health` responde; `pytest` corre (aunque sea un test trivial); no hay ninguna credencial hardcodeada.

**B2 · CI y protección de rama**
`.github/workflows/ci.yml` que corre en todo PR y en push a `main`:
- job `backend`: Postgres 16 como `services:` con `--health-cmd pg_isready`, caché de dependencias, `ruff check`, `ruff format --check`, `mypy`, `pytest`
- job `frontend` (se agrega en B10, cuando exista `web/`): `tsc --noEmit`, lint, `vite build`

Branch protection en `main` exigiendo el check `backend`.
*Listo:* rompés un test a propósito, abrís un PR, lo ves en rojo, lo arreglás, lo ves en verde y recién ahí podés mergear. **Este bloque es el que convierte el YAML en una práctica**: a partir de acá ningún bloque se mergea con el CI en rojo.

**B3 · Dominio puro**
`normalize.py` (portado de v1, con sus tests), `html_text.py` con html2text (`ignore_links=True`, `ignore_images=True`, `body_width=0`, listas con `-`), `language.py` (conteo de stopwords, sin `langdetect`).

Reglas que cambiaron respecto de v1:
- **Paréntesis en el título:** su contenido se borra solo si todas sus palabras son decoración conocida (`remote`, `latam`, `f/m/d`…: `TITLE_DECORATION` en `normalize.py`). Si no, se borran los paréntesis y se conserva el contenido. Borrarlo siempre fusionaba vacantes distintas: Jumio publicó a la vez en WWR `Machine Learning Engineer - IV (Computer Vision)` y `(Biometrics)`.
- La decoración fuera de paréntesis (`Senior Backend Engineer - Remote`) no se reconoce y da otra key: queda como `xfail` estricto.
- `to_markdown` conserva las URLs escritas como texto de un link: `ignore_links` borra el destino, no el texto, y WWR termina cada oferta con `To apply: https://...`.
- Las stopwords inglesas de `language.py` usan `you` en lugar de `a`, que también es preposición en español.

*Listo:* `pytest` verde; `to_markdown` sobre el fixture de WWR no contiene `<`, `>` ni `&nbsp;` y conserva las listas con `-`.

**B4 · Esquema de ofertas**
Todas las tablas de §2.1 + migración + seed de `sources` y del `search_profile` por defecto.
*Listo:* `alembic upgrade head` desde base vacía crea todo y siembra las tres fuentes.

**B5 · Get on Board**
Puerto `JobSource` + adaptador + fixture + tests de mapeo.
*Listo:* `fetch()` trae ofertas reales; los tests de mapeo corren sin red.

**B6 · WWR y Remotive**
Dos adaptadores más. **Examen del puerto:** si hace falta tocar algo fuera de `adapters/sources/`, el contrato está mal y se corrige.
*Listo:* las tres fuentes en la lista `SOURCES`, sin cambios en el resto.

**B7 · Pipeline de sync**
`sync_jobs.py` completo: sightings, dedupe, merge por prioridad, `sync_runs`, `close_missing` con el corte del 50%.
*Listo, los cinco:* dos corridas seguidas no duplican; `count(job_postings) <= count(job_posting_sources)`; una oferta vista por dos fuentes y dejada de listar por una sigue abierta; una corrida fallida no cierra nada; y **una oferta que ninguna fuente lista ya sí se cierra** (el test que atrapa el error de leer el `last_seen_at` equivocado).

**B8 · Prefiltro**
`prefilter.py` + tests + `GET /api/jobs?profile_id=`.
*Listo:* descarta ≥70% y, revisado a mano sobre 50 ofertas, no descarta ninguna que aplicarías.

**B9 · API de lectura**
`/api/jobs`, `/api/jobs/{id}`, `PATCH` de status, `/api/sync`, search-profiles CRUD.
*Listo:* el flujo completo funciona desde `curl` o `/docs`.

**B10 · Pantalla de ofertas**
Vite + React + TS + TanStack Query + react-router. Tabla con filtros, botón Sync, detalle, marcar vista/descartada. **Agregar el job `frontend` al `ci.yml`** en este mismo bloque.
*Listo:* **acá el proyecto ya te sirve**, sin una línea de LLM.

### Fase 2 — CV sin LLM

**B11 · Esquema de facts** — tablas de §2.2 + migración.

**B12 · CRUD de facts** — endpoints + tests.

**B13 · Editor de facts** — pantalla con secciones, drag para reordenar, `tech[]` por bullet.

**B14 · Render**
Plantilla Jinja2 + el CSS de la plantilla ya diseñada + WeasyPrint. `GET /api/resume-versions/base.pdf`.
*Listo:* descargás tu CV base en PDF, en una página, sin LLM de por medio.

### Fase 3 — LLM

**B15 · Puerto LLM** — `LLMClient` + `FakeLLMClient` + cliente real + `LLM_API_KEY` en `.env`. Ningún test llama a un modelo real.

**B16 · Import de PDF** — extracción, draft, pantalla de revisión bullet por bullet, confirm.

**B17 · Adaptación** — prompt + `AdaptedResume` + `POST /api/jobs/{id}/resume` con selector de idioma.

**B18 · Validador** — `validation.py` + `tech_aliases.yaml` + tests con casos de alucinación plantados a mano.

**B19 · Pantalla de adaptación** — diff contra el CV base, issues señalados sobre el bullet, edición manual, regenerar, descargar en el idioma elegido.

**B20 · Aplicaciones** — marcar aplicada, estado, historial.

### Fase 4 — Cierre

**B21 · README** — qué hace, capturas, `docker compose up`, `.env.example`, sección de decisiones de diseño con sus trade-offs.

---

## 10. Cómo trabajar cada bloque

El implementador es Claude Code, dentro del repo, con este archivo como contexto.

**Lo que no se delega nunca:**

1. **El diseño ya está acá.** Si Claude Code propone cambiar el modelo de datos o un contrato, se decide en este archivo primero, no en el código.
2. **Revisar el diff con intención de rechazar.** No "compila, va". *Métrica honesta: si en veinte PRs no rechazaste ninguno, no estabas revisando.*
3. **Debuggear.** Antes de pasarle un error al agente, escribí tu hipótesis de qué está pasando. Después contrastá.

**Regla que decide todo lo demás:** no se mergea lo que no podés explicar con tus palabras en la descripción del PR. Si algo no se entiende, se le pide al agente que lo explique o lo simplifique — no se aprueba.

**Al cerrar cada bloque:** actualizar `NEXT.md` (estado / siguiente / pendientes) y commitear con el *porqué* en el cuerpo, no el *qué*.

**Al retomar después de una pausa:**

```bash
cat NEXT.md
git log --oneline -10
pytest              # si pasa, el proyecto está sano
```

Y acá, el primer bloque sin tildar.

---

## 11. Riesgos conocidos

| Riesgo | Mitigación |
|---|---|
| Una fuente cambia de formato y rompe el adaptador | Los tests de mapeo lo detectan; `close_missing` tiene el corte del 50% |
| Get on Board cambia su API pública | Las otras dos siguen; el puerto aísla el daño a un archivo |
| El parseo de PDF sale mal | Revisión obligatoria antes de guardar; es parte del flujo |
| El validador bloquea reescrituras legítimas | `tech_aliases.yaml` editable + severidad `warning` para lo dudoso |
| El frontend se come el tiempo | Es lo primero que se recorta: una pantalla fea pero funcional cumple |
| Pausa larga | `NEXT.md` + bloques autocontenidos + commits que explican el porqué |
