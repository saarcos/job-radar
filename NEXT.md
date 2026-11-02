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

## Next

**B3 · Pure domain** (`normalize.py`, `html_text.py`, `language.py`).
`html2text` is a new dependency: commit the updated `uv.lock` with it, or CI
fails on `uv sync --locked`. The done criterion runs `to_markdown` on the WWR
fixture, which does not exist yet (§1: capture it from the real feed, trimmed
to 2–3 postings).

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
