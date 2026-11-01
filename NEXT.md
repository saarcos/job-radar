# NEXT

## Status

**B1 · Skeleton — done.** uv project, multi-stage Docker image, compose with
`db` + `api`, migrations on container start, settings via pydantic-settings,
`GET /api/health` (it checks the database) with unit tests, ruff/mypy/pytest
configured.

## Next

**B2 · CI and branch protection** (`.github/workflows/ci.yml`, job `backend`).
Unit tests need no `.env` and no database; `uv run mypy` works without
arguments (`files = ["src"]` in `pyproject.toml`).

## Pending

Decisions deferred to later blocks, and things worth knowing before them:

- **B4 · Hand-written migrations.** The Alembic post-write hook runs
  `ruff check --fix`, which removes the unused `from alembic import op` and
  `import sqlalchemy as sa` from an empty revision created without
  `--autogenerate`. Add them back when writing the migration body.
- **B4 · Check constraints need a name.** The naming convention in `models.py`
  builds `ck_<table>_<name>`, so every `CheckConstraint` needs `name=`
  (e.g. the `check (id = 1)` on `profile`).
- **B5 · Importing `tests/fakes.py`.** pytest runs with
  `--import-mode=importlib`, so test modules cannot import each other by
  default; `from tests.fakes import ...` will need extra configuration.
- **B9 · Session policy.** `get_session()` never commits; uncommitted work is
  rolled back on close. Decide whether to commit once per request or explicitly
  in each use case, and whether `get_sessionmaker()` needs
  `expire_on_commit=False`.
- **B10 · `.dockerignore`.** It is a denylist: add `web/node_modules` (and any
  other frontend build output) when `web/` appears.
- **psycopg on the Windows host.** psycopg does not notice a refused connection
  and waits for the full `connect_timeout` (3 s per address; `localhost`
  resolves to two). In the Linux container it fails immediately. Root cause not
  verified.
