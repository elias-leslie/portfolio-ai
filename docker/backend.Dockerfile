# Portfolio AI API — multi-stage Docker build
# Image: ghcr.io/elias-leslie/portfolio-api
# Port: 8000
# Worker: same image with CMD ["python", "-m", "app.worker"]

# ── Stage 1: Builder ─────────────────────────────────────────────
FROM python:3.13-slim-bookworm@sha256:bb73517d48bd32016e15eade0c009b2724ec3a025a9975b5cd9b251d0dcadb33 AS builder

COPY --from=ghcr.io/astral-sh/uv:latest@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first (cache-friendly layer)
COPY backend/pyproject.toml backend/uv.lock ./
COPY docker/workspace-packages/*.whl /docker/workspace-packages/

# Install deps and clean caches in same layer
RUN uv export --frozen --no-dev --no-editable --format requirements-txt \
      --no-header > requirements.txt && \
    sed -i '/^\.$/d' requirements.txt && \
    uv venv .venv && \
    uv pip install --python .venv/bin/python -r requirements.txt && \
    rm -rf /root/.cache/uv /root/.cache/pip requirements.txt

# Copy application source
COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic

# ── Stage 2: Runtime ─────────────────────────────────────────────
FROM python:3.13-slim-bookworm@sha256:bb73517d48bd32016e15eade0c009b2724ec3a025a9975b5cd9b251d0dcadb33

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user before COPY --chown
# Pre-create .cache so Docker volume mount inherits appuser ownership
RUN useradd -m -s /bin/bash appuser

WORKDIR /app

COPY --chown=appuser:appuser --from=builder /app/.venv /app/.venv
COPY --chown=appuser:appuser --from=builder /app/app ./app
COPY --chown=appuser:appuser --from=builder /app/alembic.ini ./
COPY --chown=appuser:appuser --from=builder /app/alembic ./alembic

RUN mkdir -p /app/.cache /app/logs /app/data/artifacts /app/data/household_uploads \
    && chown -R appuser:appuser /app/.cache /app/logs /app/data \
    && chmod 700 /app/data/household_uploads

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000
ENV PORT=8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
