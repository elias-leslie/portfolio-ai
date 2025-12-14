# Gemini Code Assistant Context

This document provides context for the Gemini Code Assistant to understand the "Portfolio AI Platform" project.

## IMPORTANT: Stock/Trading Questions

**When users ask about stocks, portfolio, or trading from the Agent Hub:**

```bash
# ALWAYS call this FIRST - do NOT web search before checking our data
curl http://localhost:8000/api/symbols/{SYMBOL}/intelligence
```

This returns OUR analysis: scores, signals, technicals, fundamentals, news, portfolio position, and personalized recommendations. **Use this data to answer, not generic web results.**

---

## Project Overview

The "Portfolio AI Platform" is a full-stack application designed for investment intelligence. It combines portfolio analytics with autonomous agent-driven market insights.

**Key Technologies:**

*   **Backend:** (see [STACK.md](docs/core/STACK.md) for versions)
    *   Python, FastAPI, PostgreSQL
    *   SQLAlchemy, Pydantic
    *   Celery (Worker & Beat) for asynchronous tasks and scheduling
    *   Modular LLM Clients (`backend/app/agents/clients/`) supporting Anthropic (Claude) and Google (Gemini)
*   **Frontend:** (see [STACK.md](docs/core/STACK.md) for versions)
    *   Next.js, React, TypeScript
    *   React Query for data fetching
    *   shadcn/ui and Tailwind CSS for styling
*   **Data Sources:**
    *   Multi-source failover (YFinance, TwelveData, FMP, Polygon, Finnhub, AlphaVantage)
    *   FRED (Economic Data)
    *   RSS Feeds (Google News, Nasdaq, CNBC, etc.) - requiring browser-mimicking User-Agents

**Architecture:**

The application follows a client-server architecture with a Next.js frontend communicating with a FastAPI backend.
*   **API Layer**: FastAPI handles synchronous requests (portfolio management, data retrieval).
*   **Autonomous Layer**: Celery Beat schedules periodic tasks (market data refresh, agent workflows) which are executed by Celery Workers.
*   **Intelligence Layer**: AI agents analyze data and generate insights using plain-language narratives.

## Building and Running

### Prerequisites

See [docs/core/STACK.md](docs/core/STACK.md) for current version requirements.

*   Python, Node.js, PostgreSQL (versions in STACK.md)
*   Anthropic API key (optional if using Gemini CLI)

### Backend Setup

```bash
cd ~/portfolio-ai/backend
python3 -m venv .venv
source ~/portfolio-ai/backend/.venv/bin/activate
pip install -r ~/portfolio-ai/backend/requirements.txt

# Create .env file with your API key
echo "ANTHROPIC_API_KEY=your-key-here" > ~/portfolio-ai/backend/.env

# Start API Server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Background Services (Manual)
# Terminal 2: Celery Worker
celery -A app.celery_app worker --loglevel=info --concurrency=2

# Terminal 3: Celery Beat (Scheduler)
celery -A app.celery_app beat --loglevel=info
```

### Systemd Service Setup (Recommended for Autonomy)

The system uses `systemd` user services to ensure continuous operation of the scheduler and workers.

```bash
# Link service files
mkdir -p ~/.config/systemd/user/
ln -sf ~/portfolio-ai/scripts/systemd/portfolio-celery.service ~/.config/systemd/user/
ln -sf ~/portfolio-ai/scripts/systemd/portfolio-celery-beat.service ~/.config/systemd/user/

# Reload and Start
systemctl --user daemon-reload
systemctl --user enable --now portfolio-celery
systemctl --user enable --now portfolio-celery-beat
```

### Frontend Setup

```bash
cd ~/portfolio-ai/frontend
npm install
npm run dev
```

### Access

*   **Frontend:** http://localhost:3000
*   **Backend API:** http://localhost:8000
*   **API Docs:** http://localhost:8000/docs
*   **Health Check:** http://localhost:8000/health (monitors DB, Celery, and Data Sources)

## Development Conventions

*   **Path Standardization:** All paths should use the `~/portfolio-ai/` prefix to eliminate ambiguity.
*   **Testing:**
    *   Backend tests are located in `~/portfolio-ai/backend/tests/`.
    *   **Structure**: Test subdirectories (e.g., `tests/unit/sources/`) should **not** contain `__init__.py` files to avoid collection errors.
    *   Run backend tests: `cd ~/portfolio-ai/backend && pytest tests/ -v --cov=app --cov-report=term-missing`.
*   **Linting and Type Checking:**
    *   Run linting with `~/portfolio-ai/scripts/lint.sh` (ruff + mypy).
    *   Run type checking with `cd ~/portfolio-ai/backend && mypy app/ --strict`.
*   **Code Quality:**
    *   Files should remain under 800 lines. Refactor large modules (like `llm_client.py`) into smaller sub-modules.
*   **Pre-commit Hooks:** The project uses pre-commit hooks to enforce code quality.

## Agent API Reference (For Answering Stock/Portfolio Questions)

**CRITICAL: ALWAYS check internal APIs FIRST before web search.**

When users ask about stocks, portfolio, or trading:
1. **FIRST** - Call `/api/symbols/{symbol}/intelligence` to get OUR data
2. **THEN** - Only use web search if specifically asked for external news/analysis

Our internal data includes scores, signals, technicals, fundamentals, news sentiment, portfolio position, and recommendations. This is more relevant than generic web results.

### Quick Reference

| User's Page | Primary Endpoint | Data Available |
|-------------|------------------|----------------|
| `/` (Dashboard) | `/api/market/intelligence` | Fear/Greed, VIX, sector rotation |
| `/watchlist` | `/api/symbols/{symbol}/intelligence` | **ALL data in one call** |
| `/portfolio` | `/api/portfolio/`, `/api/portfolio/analytics` | Holdings, P&L, diversification |
| `/trading` | `/api/paper-trades`, `/api/paper-trades/summary` | Open/closed trades, win rate |
| `/strategies` | `/api/strategies` | Active strategies, signals |

### Symbol Intelligence (One-Stop Endpoint)

For any symbol-specific question, use this single endpoint:

```bash
curl http://localhost:8000/api/symbols/AMBA/intelligence
```

**Returns ALL data:**
- `scores`: Overall score, 6 pillars (price/technical/fundamental/catalyst/options_flow/performance), data quality
- `signal`: BUY/HOLD/AVOID with strength (1-10), avoid_flags count
- `trading`: Recommended style, entry/stop/target, position sizing, risk level
- `company`: Health (WEAK/FAIR/STRONG), earnings_date, earnings_days_away
- `trends`: short_term_aligned, long_term_aligned, volume_relative (1.0 = average)
- `portfolio`: Whether user holds it, shares, cost basis, gain%, weight%
- `paper_trades`: Open position, closed trades, win rate, avg return
- `strategies`: Active strategies for this symbol
- `news`: Sentiment score/label, article count, headline, recent article headlines
- `market`: Fear/Greed (score + label), VIX, S&P500 change
- `alerts`: Priority indicators (Breaking News, Earnings Soon, etc.)
- `recommendation`: Personalized action (BUY_MORE, HOLD_POSITION, TRIM, etc.)

### Example Response Pattern

When answering "Why is AMBA a BUY?":

1. Call: `curl http://localhost:8000/api/symbols/AMBA/intelligence`
2. Cite specific numbers from response
3. Check if user holds position (`portfolio.held`)
4. Give personalized recommendation

**Example answer:**
> "AMBA is rated **BUY** with strength 5/10.
>
> **Bullish factors:** RSI at 43 (healthy), Revenue +31% YoY, Analysts at 1.93 (bullish)
>
> **Concerns:** -21% profit margins, catalyst score only 25 (SEC investigation)
>
> **Your position:** Not held. Recommendation: Small position due to moderate signal strength."

### Other Useful Endpoints

```bash
# Market context
GET /api/market/intelligence

# Portfolio
GET /api/portfolio/
GET /api/portfolio/analytics

# Paper trades
GET /api/paper-trades?status=open
GET /api/paper-trades/summary

# Strategies
GET /api/strategies?symbol=AMBA

# News
GET /api/news/AMBA
```

**IMPORTANT:** Always cite real numbers from API responses. Never make up data.