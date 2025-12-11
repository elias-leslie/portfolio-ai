# Gemini Code Assistant Context

This document provides context for the Gemini Code Assistant to understand the "Portfolio AI Platform" project.

## Project Overview

The "Portfolio AI Platform" is a full-stack application designed for investment intelligence. It combines portfolio analytics with autonomous agent-driven market insights.

**Key Technologies:**

*   **Backend:**
    *   Python 3.13+
    *   FastAPI
    *   PostgreSQL 16
    *   SQLAlchemy
    *   Pydantic
    *   Celery (Worker & Beat) for asynchronous tasks and scheduling
    *   Modular LLM Clients (`backend/app/agents/clients/`) supporting Anthropic (Claude) and Google (Gemini)
*   **Frontend:**
    *   Next.js 16
    *   React 19
    *   TypeScript
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

*   Python 3.13+
*   Node.js 18+
*   PostgreSQL 16
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