#!/bin/sh
# Migrations run on every start; uvicorn only starts if they succeed.
# exec replaces this shell with uvicorn, so uvicorn runs as PID 1 and receives
# SIGTERM directly from `docker compose stop/down` and shuts down gracefully.
alembic upgrade head && exec uvicorn jobradar.api.main:app --host 0.0.0.0 --port 8000
