# Portfolio AI Web — multi-stage Docker build with standalone output
# Image: ghcr.io/elias-leslie/portfolio-web
# Port: 3000
# No workspace package dependencies

# ── Stage 0: Dev Runtime ─────────────────────────────────────────
FROM node:20-slim AS dev

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

COPY frontend/ ./

RUN CI=true pnpm install --frozen-lockfile

ENV NODE_ENV=development
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

CMD ["pnpm", "dev", "--hostname", "0.0.0.0", "--port", "3000"]

# ── Stage 1: Build ───────────────────────────────────────────────
FROM node:20-slim AS builder

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# Copy all frontend source first
COPY frontend/ ./

# Install dependencies
RUN CI=true pnpm install --frozen-lockfile

# Build with standalone output, then prune pnpm store
ENV NEXT_TELEMETRY_DISABLED=1
ARG API_URL=http://portfolio-api:8000
ENV API_URL=${API_URL}
RUN pnpm build && pnpm store prune

# ── Stage 2: Runner ──────────────────────────────────────────────
FROM node:20-slim

RUN useradd -m -s /bin/bash appuser

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --chown=appuser:appuser --from=builder /app/.next/standalone ./
COPY --chown=appuser:appuser --from=builder /app/.next/static ./.next/static
COPY --chown=appuser:appuser --from=builder /app/public ./public

USER appuser

EXPOSE 3000

CMD ["node", "server.js"]
