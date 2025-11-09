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
    *   Celery for asynchronous tasks
    *   Anthropic Claude API for AI agents
*   **Frontend:**
    *   Next.js 14
    *   React 19
    *   TypeScript
    *   React Query for data fetching
    *   shadcn/ui and Tailwind CSS for styling
*   **Data Sources:**
    *   Multi-source failover (YFinance, TwelveData, FMP, Polygon, Finnhub, AlphaVantage)
    *   FRED
    *   Google News RSS

**Architecture:**

The application follows a client-server architecture with a Next.js frontend communicating with a FastAPI backend. The backend is responsible for all business logic, data processing, and interaction with the database and external APIs. The frontend is responsible for rendering the user interface and managing user interactions.

## Building and Running

### Prerequisites

*   Python 3.13+
*   Node.js 18+
*   PostgreSQL 16
*   Anthropic API key

### Backend Setup

```bash
cd ~/portfolio-ai/backend
python3 -m venv .venv
source ~/portfolio-ai/backend/.venv/bin/activate
pip install -r ~/portfolio-ai/backend/requirements.txt

# Create .env file with your API key
echo "ANTHROPIC_API_KEY=your-key-here" > ~/portfolio-ai/backend/.env

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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

## Development Conventions

*   **Path Standardization:** All paths should use the `~/portfolio-ai/` prefix to eliminate ambiguity.
*   **Testing:**
    *   Backend tests are located in `~/portfolio-ai/backend/tests/`.
    *   Run backend tests with `cd ~/portfolio-ai/backend && pytest tests/ -v --cov=app --cov-report=term-missing`.
*   **Linting and Type Checking:**
    *   Run linting with `~/portfolio-ai/scripts/lint.sh` (ruff + mypy).
    *   Run type checking with `cd ~/portfolio-ai/backend && mypy app/ --strict`.
*   **Pre-commit Hooks:** The project uses pre-commit hooks to enforce code quality.
