# Job Radar

Local aggregator for remote job postings, with per-posting resume tailoring.
It runs entirely on your machine with Docker Compose: no deployment, no auth.

> Work in progress. The design and the block-by-block plan live in
> [IMPLEMENTATION.md](IMPLEMENTATION.md) (in Spanish).

## Requirements

- Docker with Compose v2 (Docker Desktop on Windows and macOS).
- [uv](https://docs.astral.sh/uv/), only to run the app or the checks outside
  Docker. It installs Python 3.12 by itself if needed.

## Run it

```bash
cp .env.example .env
docker compose up -d
curl localhost:8000/api/health    # {"status":"ok"}
```

`docker compose up -d` returns as soon as the containers start. The API needs a
couple of seconds more, because migrations run first, so a `curl` right after it
may fail. Interactive API docs: http://localhost:8000/docs.

On every start the `api` container runs `alembic upgrade head` and only then
starts uvicorn. Postgres data lives in the named volume `jobradar_pgdata`:
`docker compose down` keeps it, `docker compose down -v` deletes it.

Both services listen on localhost only: the API on port 8000, Postgres on port 5433.

## Develop on the host

Run only Postgres in Docker and the API on your machine, with auto-reload:

```bash
docker compose up -d db
uv sync
uv run alembic upgrade head
uv run uvicorn jobradar.api.main:app --reload
```

On the host the app uses the `DATABASE_URL` from `.env` (`localhost:5433`);
inside Docker, `docker-compose.yml` overrides it with `db:5432`. If the `api`
container is running it already holds port 8000, so stop it first with
`docker compose stop api`.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Unit tests (`tests/unit/`) need neither the network nor a database.
