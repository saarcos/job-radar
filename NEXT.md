# NEXT

## Status

**B1 · Skeleton — done.** uv project, multi-stage Docker image, compose with
`db` + `api`, migrations on container start, settings via pydantic-settings,
`GET /api/health` (it checks the database) with unit tests, ruff/mypy/pytest
configured.

**B2 · CI and branch protection — done.** `.github/workflows/ci.yml` runs on
every PR and on push to `main`: job `backend`, with Postgres 16 as a service,
runs `uv sync --locked`, ruff check, ruff format --check, mypy,
`alembic upgrade head` and pytest. A ruleset on `main`, with an empty bypass
list (it applies to admins too), requires a PR and the `backend` check with
the branch up to date, and blocks force pushes and deletion. Dependabot
alerts are on, and the dependency graph reads `uv.lock`.

**B3 · Pure domain — done.** `domain/normalize.py` (`company()`, `title()`,
`canonical_key()`), `domain/html_text.py` (`to_markdown()`) and
`domain/language.py` (`detect()`), unit-tested against real responses trimmed
to a few postings (`tests/fixtures/wwr_sample.xml`, five since B6, and
`tests/fixtures/getonboard_sample.json`). `html2text` is a runtime
dependency. The rules that changed from v1 are listed under B3 in
`IMPLEMENTATION.md`. A known failure is marked `xfail(strict=True)` (B6 turned
the other one into a passing test): if it starts passing, the run turns red,
so remove its marker in the same change.

**B4 · Postings schema — done.** The six tables of §2.1 are created by
`migrations/versions/001_job_offers_schema.py`, generated from the models in
`adapters/persistence/models/` (one module per table; classes end in `Row` so
they do not clash with the future `domain/entities.py`) and reviewed by hand.
The same migration seeds the three sources and the default search profile.
The conventions (CHECK instead of enums, server defaults, identity keys,
constraint names) are listed under §2.1 in `IMPLEMENTATION.md`. CI runs
`alembic check` after the upgrade. `tests/integration/test_migrations.py` runs
the upgrade/downgrade round trip and checks the seed on a throwaway database
(`TEST_DATABASE_URL`), and compares the constraint and index definitions of
the migrated database with those of one built by `create_all()`.

**B5 · Get on Board — done.** The `JobSource` protocol
(`ports/job_source.py`), `RawJob` and `JobData` (`domain/entities.py`), and
`adapters/sources/getonboard.py`, which fetches three categories and maps each
posting. Migration 002 adds `remote_modality`, `seniority_hint` and
`applications_count` to `job_postings`. The rules that came from real responses
are listed under B5 in `IMPLEMENTATION.md`. Tests now mirror `src/`, with the
shared fixtures in `tests/conftest.py`, and `tests/unit/conftest.py` fails any
unit test that opens a connection outside loopback.

**B6 · We Work Remotely — done.** `adapters/sources/weworkremotely.py` reads
the four category feeds with `ElementTree` and maps each posting, and
`adapters/sources/__init__.py` lists both adapters in `SOURCES`, typed with the
port so mypy checks each one. Remotive was evaluated and left out of v1
(`IMPLEMENTATION.md` §1). Migration 003 adds `expires_at` to `job_postings`
and `job_posting_sources` and turns Remotive off. `detect()` returns None when
no stopword list clearly dominates. The rules that came from the real feeds are
listed under B6 in `IMPLEMENTATION.md`. A real `fetch()` on 2026-11-14 brought
184 postings (133, 12, 10 and 29 per feed) and mapped all of them.

## Next

**B7 · Sync pipeline.** `application/sync_jobs.py`: sync runs, sightings,
dedupe and merge by priority, and `close_missing` with the 50% cut and the
`expires_at` veto (`IMPLEMENTATION.md` §5).

## Pending

Decisions deferred to later blocks, and things worth knowing before them:

- **Pinned CI versions are bumped by hand.** Actions are pinned to commit
  SHAs (`checkout` v7.0.1, `setup-uv` v10.3.3). Get a new tag's SHA with
  `git ls-remote --tags <repo-url> refs/tags/<tag>` and change the SHA and its
  `# vX.Y.Z` comment together. uv 0.11.13 is pinned in the Dockerfile and in
  `ci.yml`: bump both together. The runner is `ubuntu-24.04`, moved only on
  purpose. A `.github/dependabot.yml` for `github-actions` could automate the
  SHA bumps; not decided.
- **The required check is the job id.** Renaming the `backend` job leaves
  every PR waiting for a check that never reports; change the ruleset with it.
- **B10 · `frontend` job.** Add it to the ruleset's required checks as well. A
  check only shows up in the ruleset picker after it has run once, so open the
  PR first and edit the ruleset after.
- **Testing the ruleset.** GitHub accepts a direct push to `main` of a commit
  that is the head of an open PR meeting every rule, and marks that PR as
  merged: that is how B2 reached `main`. To test that direct pushes are
  rejected, push a commit that no PR covers.

- **New migrations are numbered by hand.** `file_template` names revisions
  `<rev>_<slug>.py` and Alembic has no sequence token, so create each one with
  the next number: `uv run alembic revision --autogenerate --rev-id 002 -m
  "..."`. Without `--rev-id` the file gets a random hash as its name; Alembic
  still works, since it orders revisions by `down_revision`.
- **The post-write hook.** It runs `ruff check --fix` before `ruff format`,
  so it reports E501 on lines that the formatter then wraps; only what
  `ruff check .` still reports afterwards matters (long string literals,
  which have to be split by hand). In a revision created without
  `--autogenerate`, `ruff check --fix` removes the unused
  `from alembic import op` and `import sqlalchemy as sa`; add them back when
  writing the body.
- **What `alembic check` misses.** It compares server defaults only because
  `migrations/env.py` sets `compare_server_default=True`, and it never compares
  a check constraint's condition nor a partial index's `WHERE`.
  `test_migrations.py` covers those two by comparing `pg_get_constraintdef()`
  and `pg_indexes.indexdef` between the migrated database and one built with
  `create_all()`.
- **Check constraints need a name.** The naming convention in
  `models/base.py` builds `ck_<table>_<name>`, so every `CheckConstraint`
  needs `name=` (e.g. the `check (id = 1)` on `profile` in B11).
- **Indexes with `DESC` are declared after the class**, from the mapped
  column (`SyncRunRow.started_at.desc()`): written as `text("... DESC")`, the
  naming convention silently leaves that column out of the index name.
- **Integration tests need `TEST_DATABASE_URL`.** It is in `.env.example`;
  without it in `.env`, the tests in `tests/integration` error. They drop and
  recreate that database (and `<name>_models_test`) on every test, so its name
  must end in `_test`. The fixtures live in `test_migrations.py`; move them to
  `tests/integration/conftest.py` when B7 adds the first repository tests.
- **What a downgrade does is not tested.** The round trip to base passes even
  if a revision's downgrade forgets a `drop_column` or a data change, because
  001 drops the tables anyway; 003's downgrade was checked by hand with
  `psql`. If it gets covered, use one generic test that goes up and down one
  revision at a time and compares the schema, not a test per revision.
- **ruff formats Markdown too.** `ruff format --check .` also checks the Python
  blocks in `.md` files: an inline comment past the line length in a sketch of
  `IMPLEMENTATION.md` turns CI red.
- **`SOURCES` equals the enabled seed.** `test_migrations.py` asserts that the
  slugs in `SOURCES` are exactly the enabled rows of `sources`. Enabling a
  source in a migration before its adapter exists needs that test changed.
- **B7 · Importing `tests/fakes.py`.** pytest runs with
  `--import-mode=importlib`, so test modules cannot import each other by
  default; `from tests.fakes import ...` will need extra configuration, or the
  fake can be a fixture in a `conftest.py`.
- **B7 · What the upsert refreshes.** The sketch in §5 sets only
  `last_seen_at`, `is_open` and `closed_at` on conflict, so
  `applications_count`, which changes every day, would keep its first value.
  Decide which columns are refreshed.
- **B7 · Same company and title.** `canonical_key` merges them: 456 keys for
  466 Get on Board postings on 2026-11-08, four of them BC Tecnología's
  `Desarrollador Full Stack`. Whether those are one opening was not verified.
  On WWR, 3 keys were shared among 184 postings on 2026-11-14; one is Mixpanel
  publishing the same opening twice, 4 seconds apart (its second slug ends in
  `-1`), where merging is right.
- **B7 · Duplicate sightings.** A real run repeated no `external_id`, but a
  posting published while paging shifts the list and can repeat one. Remove
  duplicates by `(source_id, external_id)` before the insert, or Postgres fails
  with *"cannot affect row a second time"*. The WWR adapter already keeps one
  `RawJob` per `guid`, the first feed's; no posting was in two feeds on
  2026-11-14, and identical fields across feeds were checked only between the
  general feed and the full-stack one (10 postings).
- **B7 · Decoration outside brackets.** `title()` only drops decoration inside
  brackets, so `Senior Backend Engineer - Remote` and `... (Remote)` get two
  keys: a visible duplicate, not a lost posting (strict xfail in
  `test_normalize.py`).
- **B7 · Priority lives in the database.** `sources.priority` is seeded and
  unique, while the sketch in §5 sorts by a `SOURCE_PRIORITY` dict in Python.
  Read it from `sources`, or the two will drift apart.
- **B7 · What mypy does not check.** `JobPostingRow.language` is typed
  `Language`, so mypy checks reads and attribute assignments, but not
  constructor keywords nor the dicts given to `insert(...).values()`, which is
  what the upsert uses. There, only the CHECK constraint stops a value other
  than `'es'` or `'en'`.
- **B8 · Location on Get on Board.** `remote_zone` was null in every posting,
  so `region_hint` is just `countries`, which says `Remote` for 214 of 466.
  Whether a posting is workable comes from `remote_modality`: 252 of the 466
  were `hybrid` or `no_remote`.
- **B8 · What the prefilter reads.** `description_md` keeps URLs written as
  link text. The WWR adapter drops the `To apply: <url>` trailer, but 82 of 133
  full-stack descriptions still carry a URL, 75 of them in the
  `URL: <company site>` header, so a keyword can match inside one. html2text
  also turns `&lt;` into a literal `<`.
- **B8 · `<region>` alone misleads.** 20 of 184 WWR postings on 2026-11-14 said
  `Anywhere in the World` in `region` but restricted `country`, mostly to the
  USA. `country` and `state` are in the payload, and §6 puts the region
  mapping in each adapter, where the payload is. `state` looks like the
  company's headquarters (`Hovedstaden`, `Telangana`); not verified.
  `EMEA Only` is a region value too.
- **B8 · Spanish seniority words.** §6 lists `líder`, `lider`, `jefe`,
  `gerente`, `arquitecto`, `encargado` and `consultor` in the default
  `exclude_seniority`, but migration 001 seeds only the 8 English words, and
  `test_seed_has_the_three_sources_and_the_default_profile` asserts those.
  Update both in a migration.
- **B8 · Postings without a language.** `detect()` returns None when no
  stopword list reaches 5% of the words (1 of 184 WWR postings, in German).
  Decide what rule 8 of the prefilter does with a None language when the
  profile sets `languages`, and what the resume defaults to (§0.7). Portuguese
  still comes out `'es'`: it shares `de`, `que` and `para`.
- **B9 · Session policy.** `get_session()` never commits; uncommitted work is
  rolled back on close. Decide whether to commit once per request or explicitly
  in each use case, and whether `get_sessionmaker()` needs
  `expire_on_commit=False`.
- **B9 · Changing the default profile.** A partial unique index allows a single
  row with `is_default = true`: unset the current default before setting the
  new one, in the same transaction.
- **B10 · `.dockerignore`.** It is a denylist: add `web/node_modules` (and any
  other frontend build output) when `web/` appears.
- **B11 · `applications.resume_version_id`.** It has no foreign key until
  `resume_versions` exists. Add the constraint in the B11 migration and
  `ForeignKey("resume_versions.id")` in `models/application.py` together, or
  `alembic check` reports the difference.
- **psycopg on the Windows host.** psycopg does not notice a refused connection
  and waits for the full `connect_timeout` (3 s) per address. `localhost`
  resolves to `::1` first, where compose publishes nothing, so every
  connection to `localhost` took 3 s, successful ones included (B4 measured
  70 s for the integration tests, 10 s with `127.0.0.1`). `.env.example` uses
  `127.0.0.1`; an older `.env` that says `localhost` should be updated. In the
  Linux container it fails immediately. Root cause not verified.
- **No LICENSE.** Without one, nobody may reuse the code. `html2text` is
  GPL-3.0-or-later; MIT, Apache-2.0 and GPL-3.0 are all GPL-3.0-compatible.
