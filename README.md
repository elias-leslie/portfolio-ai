# Portfolio AI

AI-led investment intelligence platform combining portfolio analytics with autonomous agent-driven market insights.

## Overview

Portfolio AI is a full-stack application for managing investment portfolios, tracking watchlists, and generating AI-powered market intelligence. It integrates data from multiple financial APIs with failover routing, runs autonomous agents for opportunity discovery, and provides a narrative intelligence system that translates complex market data into actionable plain-language insights.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.13+, SQLAlchemy 2.0, Pydantic 2 |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui |
| Database | PostgreSQL 15+ (psycopg 3, connection pooling) |
| Caching | Redis |
| Workflows | Hatchet (background tasks, scheduling) |
| AI | Anthropic Claude (via Agent Hub completion API) |
| Data | yfinance, Finnhub, Polygon.io, FMP, TwelveData, AlphaVantage, FRED, RSS feeds |
| Quality | Ruff, ty, pytest, Vitest, agent-browser verification, Biome |

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
└── scripts/               # Service management (symlinks to SummitFlow)
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

## Ports

| Service | Port |
|---------|------|
| Frontend (Next.js) | 3000 |
| Backend (FastAPI) | 8000 |

## Getting Started

### Prerequisites

- Python 3.13+
- Node.js 20+
- PostgreSQL 15+
- Redis

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install -e ".[dev,ml]"  # Optional: enable FinBERT/news ML features

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Environment

Use [`.env.example`](.env.example) and [`backend/.env.example`](backend/.env.example) as templates. Local secrets live in `~/.env.local`. Optional data source keys:

- `POLYGON_API_KEY` - Polygon.io (5 req/min, 15m delay)
- `TWELVEDATA_API_KEY` - TwelveData (8 req/min)
- `FMP_API_KEY` - Financial Modeling Prep (250 req/day)
- `FINNHUB_API_KEY` - Finnhub (60 req/min)
- `ALPHAVANTAGE_API_KEY` - AlphaVantage (5 req/min, 25 req/day)

yfinance, FRED, and RSS feeds are free and require no keys.

## Testing

```bash
# Quick gate for current edits
dt -q -d

# Full repo gate
dt --check

# Targeted backend tests without tripping the repo-wide coverage threshold
dt pytest backend/tests/unit/services/test_household_finance_service_dashboard.py -- --no-cov

# Frontend behavior tests (dt does not wrap Vitest yet)
cd frontend
npm test -- --run

# Browser verification
AGENT_BROWSER_SESSION=portfolio-ai ~/.local/bin/agent-browser open http://localhost:3000
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

## Services

All services run as Docker containers via the shared SummitFlow Compose file (`~/summitflow/docker/compose/docker-compose.yml`, `--profile portfolio` or `--profile full`).

```bash
scripts/rebuild.sh            # Full rebuild and restart (auto-detects Docker)
scripts/rebuild.sh --restart  # Restart only
scripts/rebuild.sh --status   # Check service health
```

## License

Licensed under the Apache License, Version 2.0. See `LICENSE` for the full text.

## Security

If you discover a security issue, do not open a public issue. Report it privately via [GitHub Discussions](https://github.com/summitflow-solutions/portfolio-ai/discussions) with the affected area, reproduction steps, and any suggested mitigation.

## Commercial

Commercial use is permitted under Apache 2.0.

For commercial support, custom development, partnerships, or private licensing for future versions, reach out via [GitHub Discussions](https://github.com/summitflow-solutions/portfolio-ai/discussions).
