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
| 9 | Detección de cierre | Por avistamiento: ausente tras una corrida exitosa **y** sin `expires_at` futuro | Un sync fallido no puede cerrar nada; una fecha de vencimiento futura veta el cierre por ausencia |
| 10 | Filtros | Guardados en `search_profiles` | Se usan siempre los mismos |
| 11 | API key | Variable de entorno en `.env` | Local y de un usuario; guardarla en la base no aporta |
| 12 | PDF | HTML + CSS → WeasyPrint, en el backend | CSS normal en vez de la API de react-pdf |
| 13 | Plantilla de CV | Una sola, fija, de una columna | Dos columnas rompen la extracción de varios ATS |
| 14 | Import de PDF | Atajo opcional; **revisión obligatoria** antes de guardar | El parseo va a salir a medias siempre |
| 15 | Validador rechaza | Se muestra al usuario; reintento **manual** | El usuario firma el CV, no el sistema |
| 16 | Dedupe entre idiomas | No se resuelve | Una oferta en ES y EN se ve dos veces. Aceptado |
| 17 | Frontend | React + Vite + TypeScript | |
| 18 | Scraping | No | Las tres fuentes elegidas tienen API o RSS |
| 19 | Campos que solo publican algunas fuentes | Primer valor **no nulo** en orden de prioridad, no el del ganador del merge | `expires_at` lo da WWR, que pierde el merge contra Get on Board: con "gana todo el ganador" se perdería el dato |
| 20 | Datos derivados | No se persisten como si fueran de la fuente | `posted_at` es el `pubDate` crudo, nunca `expires_at − 30`. Lo derivado se calcula al leer |

### No-goals

Cron / scheduler · deploy en la nube · multiusuario · auth · scoring de ofertas con LLM · evals · auto-apply · LinkedIn / Indeed · notificaciones.

---

## 1. Fuentes

| Fuente | Endpoint | Formato | Notas |
|---|---|---|---|
| **Get on Board** | `https://www.getonbrd.com/api/v0/search/jobs?query=...` y `/api/v0/categories/{id}/jobs` | JSON | La mejor del conjunto. Pública, sin auth. Trae descripción completa, modalidad, países, rango salarial y **número de postulaciones**. LATAM + España, ofertas mayormente en español pero también en inglés; su campo `lang` suele venir `lang_not_specified` y tampoco es confiable cuando viene (27 de las 95 ofertas con `en` estaban en español), por eso el idioma siempre se detecta (B3). El nombre de la empresa y el seniority solo vienen pidiendo `expand=["company","seniority"]`. **No publica fecha de vencimiento**: su único indicador de cierre es la ausencia. Doc: `api-doc.getonbrd.com` |
| **We Work Remotely** | Cuatro feeds por categoría: `remote-full-stack-programming-jobs`, `remote-back-end-programming-jobs`, `remote-front-end-programming-jobs`, `remote-devops-sysadmin-jobs` (`.rss`) | RSS | **No** usar `remote-jobs.rss` (general, 40 ofertas, 10 por categoría) ni el viejo `remote-programming-jobs.rss`: solo los de categoría traen `expires_at`, y entre los cuatro suman ~179 ofertas únicas. Se deduplican por `guid` dentro del adaptador. Sin elemento `<company>`: empresa y puesto vienen juntos en `<title>` como `"Empresa: Puesto"`. Elementos propios fuera del estándar RSS: `<region>`, `<country>`, `<state>`, `<skills>`, `<category>`, `<type>`, `<expires_at>` y `<media:content>`. Descripción en HTML, con un `To apply: <url>` al final que es boilerplate del sitio |
| ~~**Remotive**~~ | `https://remotive.com/api/remote-jobs` | JSON | **Evaluada y descartada en v1** (14-nov). Detalle abajo |

**Regla de implementación:** verificar la forma real de la respuesta antes de escribir el adaptador. Guardar una respuesta recortada a 2–3 ofertas en `tests/fixtures/<fuente>_sample.<json|xml>`, según el formato de la fuente (`getonboard_sample.json`, `wwr_sample.xml`), y testear el mapeo contra ese archivo. Ningún test sale a la red.

**Las tres son ruidosas.** Get on Board devuelve híbridos presenciales en Chile y ofertas de PHP cuando buscás Python; WWR mezcla consultoría SAP en alemán dentro del feed de programación; Remotive trae copywriters. Ninguna categoría de ninguna fuente sustituye al prefiltro de §6.

### Vigencia: cómo sabe cada fuente que una oferta murió

| Fuente | Publica vencimiento | Qué la mata |
|---|---|---|
| Get on Board | no | la ausencia tras una corrida exitosa |
| We Work Remotely | sí, `expires_at` por aviso | el vencimiento (la ausencia coincide con él) |

**Lo verificado sobre WWR** (14-nov, dos fotos del feed con 17 horas de diferencia):

- De 179 ofertas, desaparecieron 6; las 6 habían pasado su `expires_at`.
- **0 desaparecieron antes de vencer**, y **0 siguieron listadas después de vencer.**
- `expires_at` coincide con el "Apply before" que muestra la página de la oferta.
- `pubDate` **no** es la fecha que muestra la página: es la publicación original y no se actualiza al renovar. Hubo casos de 88 y 57 días en el feed contra 28 y 27 en la página, con la oferta abierta. Por eso `posted_at` nunca se filtra por antigüedad sin mirar antes `expires_at`.
- El feed **está ordenado por fecha**, de la más nueva a la más vieja.
- Muchas ofertas comparten el mismo `expires_at` al segundo, porque WWR publica en tandas programadas (se repiten los horarios 17:00:25, 16:00:14, 07:31:0x). No es un artefacto de generación del archivo: a lo largo del feed los valores van del 14-dic al 21-nov, descendiendo con la antigüedad.

**El elemento `<region>` es el filtro más valioso del proyecto.** Tiene un conjunto acotado de valores y restringe de verdad quién puede aplicar:

```
Anywhere in the World · Latin America Only · USA Only · North America Only
Europe Only · Asia Only · Africa Only · California
```

Desde Ecuador solo sirven los dos primeros. En la muestra revisada, **casi la mitad de las ofertas son "USA Only"** y otro tercio "Anywhere in the World": una sola regla determinista descarta la mitad del feed, y es justo la mitad inaplicable.

Ojo con las granularidades mezcladas: `California` es un estado, no una región. WWR mete las restricciones estatales dentro de `<region>`, no en `<state>`, que viene vacío en toda la muestra igual que `<country>`. Hay que tratarlo como una lista de valores conocidos, nunca como una jerarquía.

**`<skills>`** viene como texto separado por comas con un "and" antes del último (`"JSON, PostgreSQL, SQL, … and Intercom"`) y **frecuentemente vacío**: sirve de complemento al prefiltro, no de reemplazo. **`<type>`** trae `Full-Time` o `Contract`; se guarda en el payload y no tiene columna hasta que algún filtro la necesite.

**Lo no verificado:** que los feeds por categoría listen *todo* lo activo y no sean una ventana. Los indicios apuntan a que sí (tamaños dispares de 126/30/13/10, y ofertas con `pubDate` de 2024 todavía listadas), pero no hay prueba. De ahí el veto por `expires_at` en §5: si la hipótesis falla, el veto evita cerrar ofertas vivas.

### Remotive: por qué quedó fuera de la v1

Se exploró el 14-nov y se descartó. El adaptador habría costado poco —con el puerto hecho son unas cuarenta líneas— pero lo que aporta no lo justifica:

- **16 ofertas en total.** `job-count` y `total-job-count` coinciden en 16, en todas las categorías juntas. Contra ~300 de Get on Board y ~179 de WWR, es el 3% del volumen. En agosto servía cientos: la API pública se restringió.
- **Las ofertas vienen con 24 horas de retraso**, a propósito y declarado en su aviso legal, para que Remotive se lleve el tráfico primero. Eso va en contra del objetivo: querés llegar antes de que suban las postulaciones, no un día después y cuando ya salió en otros lados.
- **Tope de ~4 requests por día**, con bloqueo por exceso. Choca con un sync a demanda: media docena de pruebas seguidas y quedás bloqueado.
- **Obliga a enlazar de vuelta y a acreditar a Remotive**, y prohíbe redistribuir sus ofertas. Manejable, pero arrastra condiciones al README y a la UI por 16 ofertas.
- Sin campo de vencimiento (se verificó: no hay `expires_at`, `valid_*` ni `deadline`), así que moriría por ausencia como Get on Board.

Queda sembrada en `sources` con `enabled = false`, sin adaptador. Si algún día recupera volumen, el puerto hace que volver a incluirla sea un archivo y una línea en `SOURCES`.

### La tercera fuente, cuando toque

**No otro agregador: Greenhouse y Lever con una lista curada de empresas** (eran los bloques J y K del spec original). Cada empresa expone su board públicamente y sin auth; verificar las rutas cuando se llegue, que estas cosas cambian.

Por qué son mejores que sumar otro agregador:

- Cero ruido: las empresas las elegís vos.
- Es la fuente original, no una copia: sin retraso y sin que la oferta llegue ya saturada.
- Menos competencia: lo que solo está en el board propio no lo ve quien mira agregadores.

El costo no es técnico: hay que **armar la lista** de 20-30 empresas. Ese trabajo es probablemente lo que más sube la calidad de lo que ves, más que cualquier fuente que se agregue.

---

## 2. Esquema

### 2.1 Lado ofertas

```
sources
  id            int pk identity
  slug          text unique        -- 'getonboard' | 'weworkremotely' | 'remotive'
  name          text
  enabled       bool default true
  priority      int unique         -- menor gana el merge: getonboard 0, wwr 1, remotive 2

sync_runs
  id            bigint pk identity
  source_id     int fk -> sources
  started_at    timestamptz default now()
  finished_at   timestamptz null
  status        text check         -- 'running' | 'ok' | 'failed'
  postings_seen int default 0
  error         text null
  index (source_id, status, started_at desc)   -- last_successful_run, en cada sync

job_postings                       -- una fila por vacante real
  id              bigint pk identity
  canonical_key   text unique
  company         text             -- valor original, legible
  title           text             -- valor original, legible
  url             text             -- la de la mejor fuente que la vio en la última corrida
  description_md  text null
  region_hint     text null        -- 'Anywhere in the World', 'US only'... null si la fuente no lo da
  salary_raw      text null        -- texto tal cual; sin parsear
  remote_modality text null        -- valor crudo de la fuente; null si no lo da
  seniority_hint  text null        -- valor crudo de la fuente ('semi_senior', 'senior'...); null si no lo da
  applications_count int null      -- solo Get on Board; null es "no sé", no cero
  expires_at      timestamptz null -- campo disperso (§0.19); null = ninguna fuente declara vencimiento
  language        text null check  -- 'es' | 'en' (domain.language.Language), detectado del título+descripción
  posted_at       timestamptz null -- crudo de la fuente; en WWR no coincide con lo que muestra la página
  status          text default 'new' check   -- 'new' | 'seen' | 'dismissed'
  is_open         bool default true
  closed_at       timestamptz null
  first_seen_at   timestamptz default now()
  last_seen_at    timestamptz default now()
  index (is_open, posted_at desc)  -- el listado de ofertas

job_posting_sources                -- una fila por (oferta, fuente) donde se vio
  id              bigint pk identity
  job_posting_id  bigint fk -> job_postings on delete cascade
  source_id       int fk -> sources
  external_id     text             -- text en todas las fuentes, aunque alguna mande enteros
  url             text
  payload_json    jsonb            -- crudo, sin interpretar
  content_hash    text
  expires_at      timestamptz null -- vencimiento de ESTE aviso, no de la vacante
  first_seen_at   timestamptz default now()
  last_seen_at    timestamptz default now()
  unique (source_id, external_id)
  index (job_posting_id)           -- el NOT EXISTS de close_missing, y el cascade
  index (source_id, last_seen_at)  -- el corte por fuente de close_missing

search_profiles
  id                int pk identity
  name              text
  include_keywords  text[]         -- OR entre ellas
  exclude_keywords  text[]
  exclude_seniority text[]         -- se buscan en el título; las del perfil por defecto están en §6
  languages         text[] null
  max_age_days      int default 30 -- solo aplica a ofertas sin expires_at (§6)
  source_slugs      text[] null    -- null = todas
  is_default        bool default false
  unique index (is_default) where is_default   -- a lo sumo un perfil por defecto

applications
  id                 bigint pk identity
  job_posting_id     bigint fk unique
  resume_version_id  bigint null   -- sin FK hasta B11: resume_versions no existe antes
  status             text check    -- 'applied'|'screening'|'interview'|'rejected'|'offer'|'ghosted'
  applied_at         timestamptz default now()
  notes              text null
```

**Convenciones (B4):**

- Una columna que no dice `null` es `NOT NULL`.
- Los `status` y `language` son `text` con un `CHECK`, no enums nativos de Postgres: agregarle un valor a un enum pide `ALTER TYPE` y complica las migraciones.
- Los defaults son del servidor (`server_default`), no de Python: el upsert de B7 inserta con `insert(...).values(dicts)`, que no pasa por el ORM, y con defaults de Python `first_seen_at` e `is_open` entrarían en `NULL`.
- Las PKs son `GENERATED BY DEFAULT AS IDENTITY`.
- Una FK sin `on delete` es `NO ACTION`: borrar una oferta con postulación falla. Las ofertas no se borran (decisión 8).
- `priority` es único: con un empate, quién gana el merge dependería del orden de una lista.
- Los nombres de constraints e índices salen de la convención de `models/base.py`: `uq_<tabla>_<columnas>`, `ix_<tabla>_<columnas>`, `ck_<tabla>_<nombre>`, `fk_<tabla>_<columna>_<tabla referida>`.

**Por qué `job_posting_sources` y no una tabla `raw_postings` aparte:** cada avistamiento guarda su propio `external_id`, su URL, su payload crudo y su fecha de vencimiento. Así sabés no solo dónde más se vio la oferta, sino con qué link, qué dijo cada fuente y hasta cuándo corre cada aviso — y podés reconstruir `job_postings` desde cero sin volver a pegarle a ninguna API.

**Las dos columnas `expires_at` no son lo mismo**, y la distinción es la que hace funcionar el cierre:

| Columna | Qué es | Quién la usa |
|---|---|---|
| `job_posting_sources.expires_at` | hasta cuándo corre **ese aviso** | `close_missing`: veta el cierre por ausencia |
| `job_postings.expires_at` | el campo disperso resuelto por prioridad (§0.19) | el prefiltro (§6) y la UI |

Un aviso que caduca y una vacante que se llena son cosas distintas. Que el anuncio de WWR venza no cierra la oferta si Get on Board la sigue listando.

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
│   │   ├── entities.py           # dataclasses puros: RawJob, JobData
│   │   ├── normalize.py          # company(), title(), canonical_key()
│   │   ├── html_text.py          # to_markdown()
│   │   ├── language.py           # detect()
│   │   ├── prefilter.py          # matches(posting, profile) -> bool
│   │   └── validation.py         # validate(adapted, facts) -> ValidationReport
│   ├── ports/
│   │   ├── job_source.py         # Protocol JobSource
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
│   ├── conftest.py               # acceso a los fixtures compartidos
│   ├── unit/<paquete>/test_*.py  # espeja src/; sin red ni base de datos
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

### 4.1 `domain/entities.py` y `ports/job_source.py`

`RawJob` y `JobData` viven en `domain/entities.py`; `JobSource`, en `ports/job_source.py`. El puerto tiene solo lo que llama el pipeline: cómo se parsea cada respuesta es asunto de cada adaptador.

```python
@dataclass(frozen=True)
class RawJob:
    external_id: str
    url: str
    payload: dict[str, Any]  # solo campos serializables a JSON


@dataclass(frozen=True)
class JobData:
    company: str
    title: str
    url: str
    description_md: str | None
    region_hint: str | None
    remote_modality: str | None
    salary_raw: str | None
    posted_at: datetime | None
    expires_at: datetime | None
    language: Language | None
    seniority_hint: str | None
    applications_count: int | None
    source_slug: str

    @property
    def canonical_key(self) -> str:
        return normalize.canonical_key(self.company, self.title)


class JobSource(Protocol):
    slug: str

    def fetch(self) -> list[RawJob]: ...
    def to_job(self, raw: RawJob) -> JobData: ...
```

Cada adaptador extrae su propio `external_id` y mapea su propio payload. La persistencia nunca conoce la forma de ninguna fuente. Campo que la fuente no da → `None`, **nunca un valor por defecto inventado**: un `None` honesto es información, un `"worldwide"` inventado es una mentira que después el LLM se cree. Un valor **derivado** tampoco se persiste como si fuera de la fuente (§0.20).

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
fetch → to_job → upsert postings → guardar avistamientos → cerrar las muertas
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

**Una fuente que falla parcialmente cuenta como fallida.** Si el adaptador de WWR consulta cuatro feeds y uno tira timeout, la corrida entera se marca `failed`: con datos incompletos, la ausencia de una oferta no significa nada. Ese día esa fuente no cierra nada.

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
ordered = sorted(jobs, key=lambda j: SOURCE_PRIORITY[j.source_slug])
seen: dict[str, JobData] = {}
for j in ordered:
    if j.canonical_key not in seen:
        # el primero (mejor prioridad) gana los campos centrales
        seen[j.canonical_key] = j
    else:
        seen[j.canonical_key] = coalesce_sparse(seen[j.canonical_key], j)
```

**Dos reglas de merge distintas**, y la diferencia importa:

- **Campos centrales** — `company`, `title`, `url`, `description_md`, `source_slug` — se toman **en bloque** de la mejor fuente. Mezclarlos daría el título de una fuente con la descripción de otra.
- **Campos dispersos** — `expires_at`, `seniority_hint`, `remote_modality`, `salary_raw`, `applications_count`, `region_hint` — se resuelven con el **primer valor no nulo en orden de prioridad** (§0.19). Si se tomaran del ganador, se perdería el `expires_at` de WWR cada vez que Get on Board liste la misma oferta.

Después:

```sql
INSERT ... ON CONFLICT (canonical_key) DO UPDATE SET
    company        = EXCLUDED.company,
    title          = EXCLUDED.title,
    url            = EXCLUDED.url,
    description_md = EXCLUDED.description_md,
    source_slug    = EXCLUDED.source_slug,
    expires_at     = EXCLUDED.expires_at,
    -- … el resto de los campos dispersos …
    last_seen_at   = NOW(),
    is_open        = true,
    closed_at      = null
```

**El upsert sobrescribe, no conserva.** Como la deduplicación en Python ya eligió la mejor fuente que vio la oferta **en esta corrida**, la fila que llega al `ON CONFLICT` es siempre la correcta. El significado queda enunciable: *la oferta refleja a la mejor fuente que la listó en la última corrida en que alguien la listó.*

Eso se cura solo. Mientras Get on Board la liste, gana Get on Board; en cuanto deja de listarla, la corrida siguiente trae a WWR como mejor fuente disponible y la URL pasa a la de WWR, sin que nadie gestione el cambio y sin dejar un link muerto apuntando a una fuente que ya no la publica.

Lo único que no cubre: una oferta que ninguna fuente lista en esta corrida pero que sigue abierta por un `expires_at` futuro. Esa conserva los datos de la última vez que alguien la publicó, que es lo mejor que hay.

**Deduplicar en Python antes del insert es obligatorio**, no una optimización: Postgres falla con *"cannot affect row a second time"* si un mismo `INSERT` trae dos filas con la misma `canonical_key`.

### Cierre de ofertas

**La regla, en una línea:**

> Un **avistamiento** muere cuando está ausente desde la última corrida exitosa de su fuente **y** no tiene un `expires_at` futuro.
> Una **oferta** se cierra cuando todos sus avistamientos están muertos.

```python
def close_missing(session) -> int:
    # Paso 1 — por fuente: desde qué momento cuenta la ausencia
    cutoffs: dict[int, datetime] = {}
    for source in enabled_sources(session):
        last_ok = last_successful_run(session, source.id)
        if last_ok is None:
            continue  # nunca corrió bien: no envejece nada
        stale = count_sightings_older_than(session, source.id, last_ok.started_at)
        total = count_sightings(session, source.id)
        if total and stale / total > 0.5:
            log.warning("skipping staleness for %s: %d/%d", source.slug, stale, total)
            continue  # cambió el formato, no cerraron todas
        cutoffs[source.id] = last_ok.started_at

    warn_sightings_without_death_condition(session, cutoffs)
    return mark_closed_without_live_sightings(session, cutoffs)
```

```sql
-- mark_closed_without_live_sightings, con :cutoffs = {source_id: started_at}
UPDATE job_postings p
   SET is_open = false, closed_at = NOW()
 WHERE p.is_open
   -- al menos una fuente evaluable la vio alguna vez
   AND EXISTS (SELECT 1 FROM job_posting_sources s
                WHERE s.job_posting_id = p.id AND s.source_id IN :evaluated)
   -- y ningún avistamiento sigue vivo
   AND NOT EXISTS (
         SELECT 1 FROM job_posting_sources s
          WHERE s.job_posting_id = p.id
            AND (   s.source_id NOT IN :evaluated          -- fuente sin corrida ok: no sabemos nada
                 OR s.last_seen_at >= :cutoff_of(s.source_id)   -- la sigue listando
                 OR (s.expires_at IS NOT NULL AND s.expires_at > NOW())  -- el aviso todavía corre
                )
       )
```

**Por qué el veto por `expires_at`.** Si los feeds de WWR resultaran ser una ventana y no un listado completo, cerrar por ausencia ocultaría ofertas vivas **en silencio**. El veto cuesta una condición y hace que esa hipótesis —la única sin verificar de §1— deje de ser peligrosa. El precio es que una oferta que la empresa cierra antes de tiempo sobrevive hasta su fecha de vencimiento: un clic de más, contra una oferta perdida. Errores asimétricos, se elige el barato.

**Por qué no se decide fuente por fuente:** si WWR deja de listar la oferta pero Get on Board todavía la publica, la vacante sigue abierta. Cerrarla ahí sería ocultarte una oferta viva, y en silencio — el peor tipo de bug, porque nada falla.

**Las tres redes de seguridad:** una fuente que falló (o que nunca corrió bien) no envejece nada; el corte del 50% frena el caso de un cambio de formato que vaciaría la lista de golpe; y el veto por vencimiento cubre la hipótesis de la ventana.

**El warning.** `warn_sightings_without_death_condition` registra los avistamientos sin `expires_at` **y** cuya fuente nunca tuvo una corrida exitosa: no tienen ninguna condición de muerte y quedarían abiertos para siempre. Con los feeds actuales no debería pasar; que aparezca en el log es cómo te enterás si WWR deja de publicar el campo, en vez de descubrirlo seis meses después por una lista llena de zombis.

**Tests obligatorios del bloque:**

1. Una oferta vista por dos fuentes, una de las cuales deja de listarla, sigue `is_open = true`.
2. Una oferta que ninguna fuente lista ya **sí** se cierra (atrapa el error de leer el `last_seen_at` equivocado).
3. Una oferta ausente pero con `expires_at` futuro **no** se cierra.
4. Una corrida fallida no cierra nada.

---

## 6. Prefiltro

`domain/prefilter.py`, funciones puras, **sin LLM**. Decide qué ofertas se le muestran al usuario.

```python
def matches(posting: JobPosting, profile: SearchProfile) -> bool
def reasons(posting: JobPosting, profile: SearchProfile) -> list[str]   # para depurar el filtro
```

Reglas, en orden:

1. **Frescura.** Si la oferta tiene `expires_at`, se usa eso: vencida → fuera. Si no lo tiene, se cae a `posted_at` más viejo que `max_age_days` → fuera.
2. **Región incompatible** → fuera. Es la regla que más descarta: la mitad de WWR es "USA Only".
3. `status == 'dismissed'` o existe `application` → fuera
4. `seniority_hint` incompatible (cuando la fuente lo publica) → fuera
5. Título contiene algo de `exclude_seniority` → fuera
6. Título o descripción contiene algo de `exclude_keywords` → fuera
7. Ninguna de `include_keywords` aparece en título ni descripción → fuera
8. `language` no está en `profile.languages` (si está definido) → fuera

Todo sobre `description_md`, **nunca sobre el HTML crudo**: en HTML, `python` aparece dentro de URLs y da falsos positivos.

### La regla de región necesita diseño propio

Las fuentes hablan vocabularios distintos y no se pueden comparar en crudo:

| Fuente | Qué dice |
|---|---|
| WWR | `region`: `"USA Only"`, `"Latin America Only"`, `"Anywhere in the World"`, `"California"`… |
| Get on Board | `countries`: `["Chile"]` o `["Remote"]`, más `remote_modality`: `no_remote` / `hybrid` / `remote_local` |

Hace falta un `domain/region.py` que normalice ambos a un conjunto común y chico —`worldwide`, `latam`, `usa`, `europe`, `asia`, `africa`, `other`— con su mapeo dentro de cada adaptador, y un campo en `search_profiles` con las regiones aceptables (para Ecuador: `worldwide` y `latam`).

Se diseña en B8, no antes: B6 y B5 solo **capturan** el valor crudo en `region_hint`. Pero queda escrito acá para que ese bloque no lo improvise, porque es la regla que más ofertas descarta de todo el prefiltro.

**Por qué `expires_at` manda sobre la edad.** El `pubDate` de WWR es la publicación original y no se actualiza al renovar: hubo ofertas con 88 días en el feed que la página mostraba como de 28 y seguían abiertas. Filtrar por antigüedad sin mirar el vencimiento te oculta ofertas vivas.

**Por qué la regla 3 va antes que la 4.** Cuando la fuente publica el seniority en un campo propio —Get on Board lo da como `locale_key`: `semi_senior`, `senior`— es más confiable que buscar palabras en el título. La regla 4 es el plan B para las fuentes que no lo dan.

Perfil por defecto que se siembra en la migración:

```yaml
name: Backend / Fullstack
include_keywords: [python, fastapi, django, flask, backend, node, typescript, react, fullstack, full-stack]
exclude_keywords: [sales, marketing, designer, recruiter, copywriter, customer support, data entry]
exclude_seniority: [staff, principal, director, "head of", vp, manager, architect, lead,
                    líder, lider, jefe, gerente, arquitecto, encargado, consultor]
max_age_days: 30
```

**`exclude_seniority` tiene que estar en los dos idiomas.** Get on Board publica en español y una oferta titulada *"Líder Técnico"* que pide 6 años no matchea ninguna palabra en inglés. El mismo problema aparece en WWR, que mezcla ofertas en alemán dentro del feed de programación.

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

> Ojo con `repo.open_postings`: el corte grueso por `max_age_days` en SQL **no puede** descartar ofertas con `expires_at` futuro, o volvés a ocultar las de WWR con `pubDate` viejo. El filtro SQL es `is_open AND (expires_at > now() OR posted_at > now() - max_age_days)`.

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

Reglas que salieron de respuestas reales:
- `language` sale siempre de `detect()`, nunca de `lang`.
- `description_md` une `projects`, `functions`, `description`, `desirable` y `benefits` de la oferta. Si una sección se saltea lo decide su texto, no su título: hay títulos sin texto y textos sin título. `company.attributes.projects` nunca entra: es el texto de la última oferta de la empresa.
- `salary_raw` no declara moneda: la API no la informa y la muestra no permite deducirla.
- `region_hint` sale de los campos de la oferta, nunca de `company.attributes.country`, que dice dónde está la empresa y no dónde contrata.
- `expires_at` queda en `None`: Get on Board no publica fecha de vencimiento.

*Listo:* `fetch()` trae ofertas reales; los tests de mapeo corren sin red.

**B6 · We Work Remotely**
El segundo adaptador. **Examen del puerto:** si hace falta tocar algo fuera de `adapters/sources/`, el contrato está mal y se corrige.

Incluye además una migración que agrega `expires_at` a `job_postings` y a `job_posting_sources`, deja `remotive` en `enabled = false`, y un ajuste a `language.detect()`.

**La v1 va con dos fuentes.** Remotive se evaluó y se descartó (§1). La tercera no se agrega antes de B10: el pipeline es lo que falta, no el volumen — con ~480 ofertas entre las dos no vas a aplicar a todas. Y una fuente nueva rinde más como examen del puerto **después** de B7, cuando además prueba el dedupe, el merge y el cierre, y no solo el mapeo.

Reglas de WWR que salieron de la exploración:
- Cuatro feeds por categoría, **no** el general ni el viejo `remote-programming-jobs.rss` (§1). Se deduplican por `guid` dentro del adaptador.
- Sin elemento `<company>`: el split de `"Empresa: Puesto"` por el **primer** `:` es el camino principal, no un fallback.
- `<region>` → `region_hint`. `<category>` se conserva en el payload.
- `posted_at` = `pubDate` crudo. **No** `expires_at − 30`: sería un valor derivado persistido como si fuera de la fuente (§0.20). Lo que resuelve el problema de la fecha mentirosa es la regla 1 del prefiltro, no falsear el dato.
- El `To apply: <url>` del final se descarta en el adaptador: es boilerplate del sitio, no HTML genérico, así que no es trabajo de `to_markdown`.
- Se descartan `summary_detail` (duplica `summary`) y `published_parsed` (no es serializable).
- **El XML se lee como bytes**, dejando que el parser respete la declaración de encoding. Leerlo con el default del sistema produce mojibake (`DÃ¼sseldorf`) que termina guardado en el fixture.
- Elegir feedparser **o** `ElementTree` y escribirlo en el ticket: los campos se llaman distinto (`summary`/`published` contra `description`/`pubDate`).

Ajuste a B3 que entra acá: `language.detect()` devuelve `None` cuando ninguna lista de stopwords domina con claridad. El feed de WWR trae ofertas en alemán, y hoy el clasificador las etiquetaría `es` o `en`, inventando un dato.

*Listo:* las dos fuentes en la lista `SOURCES`, sin cambios fuera de `adapters/sources/` salvo la migración y el ajuste de `detect()`.

**B7 · Pipeline de sync**
`sync_jobs.py` completo: avistamientos, dedupe, merge por prioridad con las dos reglas (campos centrales en bloque, dispersos por coalesce), `sync_runs`, corrida parcial = corrida fallida, `close_missing` con el corte del 50% y el veto por `expires_at`, y el warning de avistamientos sin condición de muerte.
*Listo, los seis:* dos corridas seguidas no duplican; `count(job_postings) <= count(job_posting_sources)`; una oferta vista por dos fuentes y dejada de listar por una sigue abierta; una oferta ausente con `expires_at` futuro no se cierra; una corrida fallida no cierra nada; y **una oferta que ninguna fuente lista ya sí se cierra**.

**B8 · Prefiltro**
`prefilter.py` + `domain/region.py` + tests + `GET /api/jobs?profile_id=`.
*Listo:* descarta ≥70% y, revisado a mano sobre 50 ofertas, no descarta ninguna que aplicarías. Una oferta de WWR con `pubDate` de 88 días pero `expires_at` futuro **pasa** el filtro. Y una `"USA Only"` **no** pasa, mientras que una `"Latin America Only"` sí.

**B9 · API de lectura**
`/api/jobs`, `/api/jobs/{id}`, `PATCH` de status, `/api/sync`, search-profiles CRUD.
*Listo:* el flujo completo funciona desde `curl` o `/docs`.

**B10 · Pantalla de ofertas**
Vite + React + TS + TanStack Query + react-router. Tabla con filtros, botón Sync, detalle, marcar vista/descartada. **Agregar el job `frontend` al `ci.yml`** en este mismo bloque.
*Listo:* **acá el proyecto ya te sirve**, sin una línea de LLM.

### Fase 2 — CV sin LLM

**B11 · Esquema de facts** — tablas de §2.2 + migración. Incluye la FK de `applications.resume_version_id`, que quedó pendiente desde B4.

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

**Antes de escribir el adaptador de una fuente nueva, explorala a mano.** Un par de requests con `curl` y mirar la respuesta cruda cuesta diez minutos y cambia el diseño: de ahí salieron el `expand` de Get on Board, los cinco campos de descripción, el `expires_at` de WWR y la trampa de los dos `projects`. Ninguna de esas cosas estaba en la documentación.

**Al cerrar cada bloque:** actualizar `NEXT.md` (estado / siguiente / pendientes) y commitear con el *porqué* en el cuerpo, no el *qué*. Si el bloque cambió una decisión de diseño, **actualizar este archivo en el mismo PR**.

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
| **Los feeds de WWR resultan ser una ventana y no un listado completo** | El veto por `expires_at` en `close_missing`: una oferta ausente con vencimiento futuro no se cierra |
| WWR deja de publicar `expires_at` | El warning de avistamientos sin condición de muerte lo hace visible en el log |
| Una oferta se cierra antes de su vencimiento y la seguimos mostrando | Asumido. Cuesta un clic; el error inverso cuesta una oferta |
| Get on Board cambia su API pública | Las otras dos siguen; el puerto aísla el daño a un archivo |
| El parseo de PDF sale mal | Revisión obligatoria antes de guardar; es parte del flujo |
| El validador bloquea reescrituras legítimas | `tech_aliases.yaml` editable + severidad `warning` para lo dudoso |
| El frontend se come el tiempo | Es lo primero que se recorta: una pantalla fea pero funcional cumple |
| Pausa larga | `NEXT.md` + bloques autocontenidos + commits que explican el porqué |

---

## 12. Pendientes de verificación

Cosas asumidas que todavía no se probaron. No bloquean ningún bloque, pero conviene cerrarlas cuando haya datos.

| Qué | Cómo se verifica | Por qué importa |
|---|---|---|
| Que los feeds de WWR listen todo lo activo | Bajar el feed un martes a media mañana: si tampoco entra nada nuevo en las cuatro categorías, está cacheado. Comparar el conteo de la página de categoría contra las 126 de Full-Stack | Si es una ventana, el cierre por ausencia sería peligroso. Hoy lo cubre el veto |
| Si una oferta cerrada por la empresa sale del feed antes de vencer | `job_posting_sources` lo acumula solo: en un mes se puede comparar la desaparición contra `expires_at` | Decide si vale la pena reintroducir un cierre por ausencia con gracia |
| La moneda de `min_salary`/`max_salary` en Get on Board | Buscar una oferta cuya descripción declare el sueldo en dólares y comparar | Hoy `salary_raw` no declara unidad, que es lo honesto |
| Si Remotive recupera volumen | Un `curl` cada tantos meses mirando `total-job-count` | Con 16 ofertas no entra; con cientos y el puerto hecho, el costo sería un archivo |
| Las rutas públicas de Greenhouse y Lever | Un `curl` al board de una empresa conocida antes de escribir el adaptador | Es la tercera fuente candidata (§1), y estas rutas cambian |