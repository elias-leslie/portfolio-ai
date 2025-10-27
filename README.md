# Portfolio AI Platform

An AI-led investment intelligence system that combines portfolio analytics with autonomous agent-driven market insights.

## Overview

Portfolio AI Platform helps investors make better decisions by:

- **Portfolio Management**: Track positions across multiple accounts with real-time analytics
- **AI-Driven Insights**: Autonomous agents discover market opportunities and generate personalized investment ideas
- **Multi-Source Intelligence**: Integrates market data, economic indicators, news sentiment, and portfolio analysis
- **Cost-Controlled**: Agent runs tracked and limited to $0.50 per execution

## Key Features

### Portfolio Analytics
- Real-time portfolio valuation and P&L tracking
- Risk metrics: beta, volatility, concentration analysis
- Sector exposure breakdown
- Multi-account support (IRA, Taxable, 401k, Roth, HSA)

### AI Agent System
- **Discovery Agent**: Scans news and economic data to generate general investment ideas
- **Portfolio Analyzer Agent**: Analyzes your holdings to generate personalized recommendations
- Full execution tracking with tool call logging
- Cost tracking and safety limits

### Market Intelligence
- Multi-source price data (yfinance primary, Polygon backup)
- FRED economic indicators
- Google News RSS sentiment analysis
- 15-minute price caching for performance

## Tech Stack

**Backend**:
- Python 3.11+
- FastAPI for REST API
- DuckDB for storage
- Anthropic Claude API for AI agents
- yfinance + Polygon for market data

**Frontend**:
- Next.js 14 (App Router)
- TypeScript
- TanStack Query for data fetching
- TanStack Table for data grids
- shadcn/ui components
- Tailwind CSS

## Quick Start

### Prerequisites
- Python 3.11 or higher
- Node.js 18 or higher
- Git

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd portfolio-ai
```

2. **Backend setup**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. **Frontend setup**
```bash
cd frontend
npm install
```

4. **Environment configuration**
```bash
# Create .env file in backend/
cp backend/.env.example backend/.env
# Add your API keys (Anthropic, Polygon, etc.)
```

### Running the Application

**Start the backend** (in `backend/` directory):
```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```
Backend runs on http://localhost:8000

**Start the frontend** (in `frontend/` directory):
```bash
npm run dev
```
Frontend runs on http://localhost:3000

## Development

### Code Quality
```bash
# Run linting (requires activated venv)
./scripts/lint.sh

# Run tests with coverage
cd backend
source .venv/bin/activate
pytest tests/ -v --cov=app --cov-report=term-missing
```

### Project Structure
```
portfolio-ai/
├── backend/           # Python FastAPI application
│   ├── app/
│   │   ├── storage/   # DuckDB storage layer
│   │   ├── portfolio/ # Portfolio CRUD & analytics
│   │   ├── agents/    # AI agent system
│   │   ├── api/       # FastAPI routers
│   │   └── main.py    # Application entry point
│   └── tests/         # Unit & integration tests
├── frontend/          # Next.js dashboard
│   ├── app/           # App router pages
│   ├── components/    # React components
│   └── lib/           # API clients & hooks
├── config/            # YAML seed data
├── data/              # DuckDB database
├── docs/              # Documentation
└── scripts/           # Build & validation scripts
```

## Documentation

- **[ARCHITECTURE.md](docs/core/ARCHITECTURE.md)**: System design and technical decisions
- **[SETUP.md](docs/core/SETUP.md)**: Detailed installation guide
- **[DEVELOPMENT.md](docs/core/DEVELOPMENT.md)**: Development workflows and standards
- **[API_REFERENCE.md](docs/core/API_REFERENCE.md)**: API endpoint documentation
- **[CLAUDE.md](CLAUDE.md)**: Quick reference for Claude Code AI assistant

## API Endpoints

### Portfolio
- `GET /api/portfolio` - Get all positions with current values
- `POST /api/portfolio/account` - Create new account
- `POST /api/portfolio/position` - Add or update position
- `DELETE /api/portfolio/position/{id}` - Delete position
- `GET /api/portfolio/analytics` - Get portfolio analytics

### Ideas
- `GET /api/ideas` - List investment ideas (filterable)
- `POST /api/ideas/generate` - Trigger agent to generate new ideas
- `GET /api/ideas/{id}` - Get idea details
- `PATCH /api/ideas/{id}/status` - Update idea status

### Market Data
- `GET /api/market/conditions` - Current market conditions (S&P 500, VIX, yields)
- `GET /api/market/prices` - Get current prices for symbols

### Preferences
- `GET /api/preferences` - Get user preferences
- `POST /api/preferences` - Update risk tolerance and trade preferences

## Testing

```bash
cd backend
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/test_portfolio_manager.py -v
```

Target: 80%+ test coverage

## Contributing

1. Read [ARCHITECTURE.md](docs/core/ARCHITECTURE.md) and [DEVELOPMENT.md](docs/core/DEVELOPMENT.md)
2. Follow the AI Dev Tasks workflow (see `.ai_dev_tasks/README.md`)
3. Ensure all tests pass and linting succeeds before committing
4. Use conventional commit messages (`feat:`, `fix:`, `refactor:`, etc.)

## License

[License information to be added]

## Contact

[Contact information to be added]
