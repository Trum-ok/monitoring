# Build context: repository root (see deploy/docker-compose.yaml)
FROM python:3.13.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /src

COPY pyproject.toml uv.lock ./
COPY monitor-service/pyproject.toml monitor-service/pyproject.toml
COPY sdk/pyproject.toml sdk/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project --package monitor-service


FROM python:3.13.14-slim

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY monitor-service/ /app/

COPY monitor-service/deploy/entrypoint.sh /entrypoint.sh
RUN useradd -m appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app /entrypoint.sh
USER appuser
CMD ["/entrypoint.sh"]
