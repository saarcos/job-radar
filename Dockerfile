# ---- builder: resolves and installs everything into /app/.venv ----
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.13 /uv /bin/uv

# Precompile .pyc for faster startup; copy (not hardlink) out of the cache
# mount; always use this image's Python so .venv works in the runtime stage.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies only: this layer is rebuilt only when the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# The project itself, as a regular (non-editable) install, so the runtime
# stage needs .venv but not src/. README.md is required by the build backend.
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# ---- runtime: only what is needed to migrate and serve ----
FROM python:3.12-slim

RUN useradd --system app

WORKDIR /app

# Owned by root: the app user can run the code but not modify it.
COPY --from=builder /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations ./migrations
COPY --chmod=755 entrypoint.sh ./

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
