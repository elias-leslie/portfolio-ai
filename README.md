# Portfolio AI

AI-led investment intelligence platform combining portfolio analytics with autonomous agent-driven market insights.

## Overview

Portfolio AI is a full-stack application for managing investment portfolios, tracking watchlists, and generating AI-powered market intelligence. It integrates data from multiple financial APIs with failover routing, runs autonomous agents for opportunity discovery, and provides a narrative intelligence system that translates complex market data into actionable plain-language insights.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.13.x, SQLAlchemy 2.0, Pydantic 2 |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui |
| Database | PostgreSQL 15+ (psycopg 3, connection pooling) |
| Caching | Redis |
| Workflows | Hatchet (background tasks, scheduling) |
| AI | Optional Agent Hub companion for Jenny, thesis validation, and document review |
| Data | yfinance, Finnhub, Polygon.io, FMP, TwelveData, AlphaVantage, FRED, RSS feeds |
| Quality | Ruff, ty, pytest, Vitest, sf-browser verification, Biome |

## Architecture

```
portfolio-ai/
├── backend/
│   ├── app/
│   │   ├── agents/        # AI agents (Discovery, Portfolio Analyzer)
│   │   ├── api/           # REST endpoint routers
│   │   ├── analytics/     # Analytics calculations
│   │   ├── backtest/      # Backtesting engine
│   │   ├── config/        # YAML/JSON configuration
│   │   ├── market/        # Market data handling
│   │   ├── ml/            # Machine learning models
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── portfolio/     # Portfolio management logic
│   │   ├── services/      # Business logic services
│   │   ├── sources/       # Data source adapters (multi-source failover)
│   │   ├── strategies/    # Strategy definitions and management
│   │   ├── tasks/         # Background tasks (Hatchet workflows)
│   │   ├── watchlist/     # Watchlist intelligence + narrative system
│   │   └── workflows/     # Hatchet workflow definitions
│   └── tests/
├── frontend/
│   ├── app/               # Pages (App Router)
│   ├── components/        # React components
│   └── lib/               # API clients, hooks, utilities
└── scripts/               # Local helpers and runtime utilities
```

## Key Features

### Portfolio Management
- Multi-account support (IRA, Taxable, 401k, Roth, HSA)
- Real-time position tracking with automatic price updates (15-minute refresh)
- Analytics: beta, volatility, concentration, sector exposure
- Snapshot system for historical tracking

### AI-Powered Intelligence
- **Discovery Agent** - Scans news and economic data for market opportunities
- **Portfolio Analyzer** - Generates personalized ideas based on current holdings
- **Narrative Intelligence System** - Signal classification (BUY/HOLD/AVOID), trading style recommendations, entry/stop/target calculations with position sizing

### Data Integration
- Multi-source failover across 6+ financial data providers
- Economic indicators via FRED (VIX, Treasury yields, HY spreads)
- News aggregation from 10+ RSS feeds and API sources
- Rate-limited request routing with quota management

### Backtesting
- Historical strategy testing with trade simulation
- Performance metrics (Sharpe ratio, win rate, drawdown)
- Paper trading with live updates

### Scheduled Automation
- 60+ Hatchet-scheduled background tasks
- Daily OHLCV refresh, fear/greed index calculation
- Automated data freshness monitoring and stale data alerts
- Strategy signal generation and watchlist candidate discovery

## Install Modes

### Standalone

Runs the full portfolio/watchlist/market/household product without SummitFlow.
Agent Hub is not required. Core analytics, watchlist management, market data,
and scheduled refreshes still work.

### Companion

Adds Agent Hub as an optional companion service. This enables Jenny chat and
review flows, household document review, thesis validation, and other
agent-driven features. SummitFlow is not required for this repo.

## Prerequisites

- Python 3.13.x
- Node.js 20+
- Docker Engine with Compose plugin for Docker installs and for native infra
- `pnpm` for native frontend installs
- `uv` for native backend installs

Portfolio AI currently depends on `pandas-ta -> numba -> llvmlite`, so Python
3.14 is not a supported native install target yet.

## Quickstart

### Fastest: Docker standalone

```bash
cp .env.example .env
./scripts/generate-hatchet-dev-token.sh .env
docker compose up -d --build
```

For the bundled Docker stack, keep `PORTFOLIO_DB_URL` and `REDIS_URL` blank in
`.env`. Docker Compose injects the internal service URLs automatically.

Then open `http://localhost:3000`.

### Docker companion

Populate the Agent Hub companion variables in `.env`, and make sure the
standalone Agent Hub install was started with the same `PORTFOLIO_CLIENT_ID`
so it auto-registers that first-party client. Then start with the
companion override:

```bash
cp .env.example .env
./scripts/generate-hatchet-dev-token.sh .env
docker compose -f docker-compose.yml -f docker-compose.companion.yml up -d --build
```

Keep `PORTFOLIO_DB_URL` and `REDIS_URL` blank in the Docker `.env` file here as
well so the compose stack uses its bundled database and Redis services.

### Native standalone

Use Docker for PostgreSQL, Redis, and Hatchet, then run the app processes
natively:

```bash
cp .env.example .env.local
./scripts/generate-hatchet-dev-token.sh .env.local
docker compose --env-file .env.local up -d portfolio-db portfolio-redis hatchet-migrate hatchet-setup-config hatchet

cd backend
uv sync --python 3.13 --frozen --extra dev
uv run alembic upgrade head

cd ../frontend
pnpm install --frozen-lockfile
pnpm build
```

Start the processes in separate shells:

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
cd backend
uv run python -m app.worker
```

```bash
cd frontend
API_URL=http://localhost:8000 HOSTNAME=0.0.0.0 PORT=3000 pnpm start
```

`pnpm start` stages `.next/static` and `public/` into the standalone runtime
directory before launching the Next standalone server, so native installs match
the Docker frontend layout.

### Native companion

Use the same steps as native standalone, but also set `AGENT_HUB_URL`,
`PORTFOLIO_CLIENT_ID`, and optionally `PORTFOLIO_REQUEST_SOURCE` in `.env.local`.
Use the same `PORTFOLIO_CLIENT_ID` on the Agent Hub side so the companion
client is auto-registered during Agent Hub startup.
If you are not using the default backend port, keep `API_URL` aligned with the
actual backend URL when starting the frontend so `/ws/*` resolves correctly.

## Environment

Use [`.env.example`](.env.example) as the template. Native installs should use
repo-local `.env.local`. Docker Compose should use repo-local `.env`. The
backend loads both automatically, and `~/.env.local` is only a legacy fallback
for the current internal runtime.

`scripts/generate-hatchet-dev-token.sh` bootstraps a Hatchet client token using
the tenant created by Hatchet quickstart and writes both
`HATCHET_TENANT_ID` and `HATCHET_CLIENT_TOKEN` into the target env file. If
you created a different tenant yourself, set `HATCHET_TENANT_ID` before
running the script.

Portfolio AI ships a bundled `agent-hub-client` wheel under
`docker/workspace-packages/` so clean native installs do not need private Git
access just to resolve the optional companion SDK.

## Testing

```bash
# Quick gate for current edits
dt --quick --changed-only

# Frontend-only verification
dt --frontend-only

# Full repo gate
dt --check

# Browser verification
sf-browser health
sf-browser open http://<host-ip-from-.index.yaml>:3000
sf-browser screenshot /tmp/portfolio-home.png
```

## API

Key endpoint groups:

| Group | Endpoints | Description |
|-------|-----------|-------------|
| Portfolio | `/api/portfolio/*` | Accounts, positions, analytics |
| Watchlist | `/api/watchlist/*` | Items, snapshots, narrative intelligence |
| Agents | `/api/agents/*` | Telemetry, token summary, discussion |
| Sources | `/api/sources/*` | Data source status, routing |
| Strategies | `/api/strategies/*` | Strategy definitions, signals, backtesting |
| Tasks | `/api/tasks/*` | Background task management |
| Status | `/api/status/*` | System health, data freshness |

Full interactive docs at `http://localhost:8000/docs`.

## Database

163+ tables covering portfolio positions, watchlist intelligence, market data caching, agent runs, strategy management, backtesting, and system monitoring. Schema managed via Alembic migrations.

## Internal SummitFlow Runtime

Inside the existing SummitFlow workspace, Portfolio AI still supports the shared
native wrapper flow:

```bash
rebuild.sh portfolio-ai
status.sh portfolio-ai
```

That path is for the current internal multi-repo runtime. The public-ready
standalone instructions are the Docker and native flows above.

## License

Licensed under the Apache License, Version 2.0. See `LICENSE` for the full text.

## Security

If you discover a security issue, do not open a public issue. Report it privately via [GitHub Discussions](https://github.com/summitflow-solutions/portfolio-ai/discussions) with the affected area, reproduction steps, and any suggested mitigation.

## Commercial

Commercial use is permitted under Apache 2.0.

For commercial support, custom development, partnerships, or private licensing for future versions, reach out via [GitHub Discussions](https://github.com/summitflow-solutions/portfolio-ai/discussions).
