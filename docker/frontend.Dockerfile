# Portfolio AI Web — multi-stage Docker build with standalone output
# Image: ghcr.io/summitflow-solutions/portfolio-web
# Port: 3000
# No workspace package dependencies

# ── Stage 1: Build ───────────────────────────────────────────────
FROM node:20-slim AS builder

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# Copy all frontend source first
COPY frontend/ ./

# Install dependencies (after source so pnpm sees package.json in place)
RUN pnpm install --no-frozen-lockfile

# Build with standalone output
ENV NEXT_TELEMETRY_DISABLED=1
# API URL for Next.js rewrites (baked at build time)
ARG API_URL=http://portfolio-api:8000
ENV API_URL=${API_URL}
RUN pnpm build

# ── Stage 2: Runner ──────────────────────────────────────────────
FROM node:20-slim

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Copy standalone output
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
