# Portfolio AI API — multi-stage Docker build
# Image: ghcr.io/summitflow-solutions/portfolio-api
# Port: 8000
# Worker: same image with CMD ["python", "-m", "app.worker"]
# Note: ML extras (torch, transformers) available via --build-arg INSTALL_ML=true

# ── Stage 1: Builder ─────────────────────────────────────────────
FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first (cache-friendly layer)
COPY backend/pyproject.toml backend/uv.lock ./
COPY docker/workspace-packages/*.whl /tmp/wheels/

# Optional ML extras (torch, transformers) — adds ~1GB
ARG INSTALL_ML=false

# Install deps and clean caches in same layer
RUN uv export --frozen --no-dev --no-editable --format requirements-txt \
      --no-header > requirements.txt && \
    sed -i '/^\.$/d; /agent-hub-client$/d; /^\.\.\//d' requirements.txt && \
    uv venv .venv && \
    uv pip install --python .venv/bin/python \
      -r requirements.txt /tmp/wheels/agent_hub_client-*.whl && \
    if [ "$INSTALL_ML" = "true" ]; then \
      uv export --frozen --no-dev --no-editable --format requirements-txt \
        --no-header --extra ml > ml-requirements.txt && \
      uv pip install --python .venv/bin/python -r ml-requirements.txt && \
      rm -f ml-requirements.txt; \
    fi && \
    rm -rf /tmp/wheels /root/.cache/uv /root/.cache/pip requirements.txt

# Copy application source
COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic

# ── Stage 2: Runtime ─────────────────────────────────────────────
FROM python:3.13-slim-bookworm

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

RUN mkdir -p /app/.cache && chown appuser:appuser /app/.cache

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000
ENV PORT=8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
