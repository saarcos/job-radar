FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv export --no-dev --no-emit-project --format requirements-txt > req.txt
RUN pip install --no-cache-dir --prefix=/install -r req.txt

FROM python:3.12-slim
RUN useradd -m -u 1000 app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=app:app . .
RUN pip install --no-cache-dir -e . --no-deps
USER app
CMD ["sh", "-c", "alembic upgrade head && python -m jobradar"]