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
to three postings (`tests/fixtures/wwr_sample.xml`,
`tests/fixtures/getonboard_sample.json`). `html2text` is a runtime
dependency. The rules that changed from v1 are listed under B3 in
`IMPLEMENTATION.md`. Two known failures are marked `xfail(strict=True)`: if
one starts passing, the run turns red, so remove its marker in the same change.

## Next

**B4 · Postings schema.** Every table of §2.1, the migration, and the seed of
`sources` and the default `search_profile`. `job_postings.language` stores the
output of `detect()`, typed `Literal["es", "en"]` in `domain/language.py`; a
check constraint can mirror it (it needs `name=`, see below).

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
  default; `from tests.fakes import ...` will need extra configuration. For
  the same reason `test_html_text.py` and `test_language.py` each carry their
  own copy of the `wwr_sample.xml` loader.
- **B5 · Get on Board.** Request `expand=["company"]`: without it, `company`
  is only an id (the fixture already has it expanded). The posting text is
  split across five HTML fields (`projects`, `functions`, `description`,
  `desirable`, `benefits`); decide which ones make `description_md`. Its
  `lang` attribute is mostly `lang_not_specified`, Spanish postings included,
  and it lists English postings too: the language comes from `detect()`.
- **B6 · WWR titles.** They come as `"Company: Title"`. A title without `": "`
  leaves the company empty, and all such postings with the same title would
  share one key.
- **B7 · Decoration outside brackets.** `title()` only drops decoration inside
  brackets, so `Senior Backend Engineer - Remote` and `... (Remote)` get two
  keys: a visible duplicate, not a lost posting (strict xfail in
  `test_normalize.py`).
- **B8 · What the prefilter reads.** `description_md` keeps URLs written as
  link text: every WWR posting ends with
  `To apply: https://weworkremotely.com/remote-jobs/<slug>`, and the slug
  repeats the title, so a keyword can match inside it. html2text also turns
  `&lt;` into a literal `<`. `detect()` returns `'en'` for a Spanish title
  with no description (strict xfail in `test_language.py`).
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
- **No LICENSE.** Without one, nobody may reuse the code. `html2text` is
  GPL-3.0-or-later; MIT, Apache-2.0 and GPL-3.0 are all GPL-3.0-compatible.
