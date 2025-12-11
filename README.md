# Portfolio AI Platform

AI-led investment intelligence platform combining portfolio analytics with autonomous agent-driven market insights.

## 🎯 Project Status

**Last Updated**: 2025-11-02
**Development Phase**: v1.3.0-dev - Post-MVP Enhancements Complete
**Version**: 1.3.0-dev

### ✅ Completed Features
- ✅ Full-stack application (FastAPI + Next.js)
- ✅ Portfolio management with real-time analytics
- ✅ AI agent system (Discovery Agent + Portfolio Analyzer)
- ✅ PostgreSQL 16 migration with connection pooling (4x concurrency)
- ✅ Multi-source data failover (6 operational adapters)
- ✅ Watchlist Intelligence Hub with narrative system
- ✅ **Narrative Intelligence System** (PRD #0021 100% complete):
  - Signal classification (BUY/HOLD/AVOID with 0-10 strength)
  - Trading style recommendations (Index/Trend/Value/Swing/Event)
  - Plain-language insights with zero jargon
  - Multi-source fundamentals and earnings data
  - Entry/stop/target calculations with position sizing
- ✅ 145 tests passing (100% pass rate), 85% coverage
- ✅ Mypy --strict compliance
- ✅ Complete UI with navigation, forms, error handling

### 🎯 Active Development
- Intelligence layer enhancements (sentiment scoring, fundamental data)
- Risk management suite (position sizing, stop-loss, correlation)
- See **[docs/core/REFACTOR_STATUS.md](./docs/core/REFACTOR_STATUS.md)** for current priorities.

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- Node.js 18+
- PostgreSQL 16
- Anthropic API key (for AI agents)

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
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## 📱 Remote Access (Tailscale)

For testing on your phone:

```bash
# Terminal 1: Start backend
cd ~/portfolio-ai/backend && source ~/portfolio-ai/backend/.venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start frontend
cd ~/portfolio-ai/frontend && npm run dev

# Terminal 3: Configure Tailscale
tailscale serve --bg 3000
tailscale serve --bg 8000

# Get your URL
tailscale status
```

Then open `https://<your-machine>.tail-scale.net` on your phone.

## 🏗️ Architecture

See **[docs/core/ARCHITECTURE.md](./docs/core/ARCHITECTURE.md)** for comprehensive system design.

**High-level stack**:
- **Frontend**: Next.js 16, React Query, shadcn/ui, Tailwind CSS
- **Backend**: FastAPI, PostgreSQL 16, SQLAlchemy, Pydantic
- **AI**: Anthropic Claude API
- **Data**: Multi-source failover (YFinance, TwelveData, FMP, Polygon, Finnhub, AlphaVantage), FRED, Google News RSS

## 📊 Key Features

### Portfolio Management
- Multi-account support (IRA, Taxable, 401k, Roth, HSA)
- Real-time position tracking
- Analytics: beta, volatility, concentration, sector exposure
- Automatic price updates (15-min refresh)

### AI-Powered Ideas
- **Discovery Agent**: Scans news/economic data for general market opportunities
- **Portfolio Analyzer**: Generates personalized ideas based on your holdings
- Confidence scoring and risk assessment
- Idea status workflow (pending → validated → executed → rejected)

### User Experience
- Responsive UI with navigation
- Toast notifications for all actions
- Error handling and loading states
- Form validation
- Real-time data updates

## 🧪 Testing

```bash
# Backend tests (145 passing, 85% coverage)
cd ~/portfolio-ai/backend
source ~/portfolio-ai/backend/.venv/bin/activate
pytest tests/ -v --cov=app --cov-report=term-missing

# Linting and type checking
~/portfolio-ai/scripts/lint.sh  # ruff + mypy

# Frontend build
cd ~/portfolio-ai/frontend
npm run build
```

## 📁 Project Structure

```
~/portfolio-ai/
├── backend/              # Python FastAPI application
│   ├── app/
│   │   ├── agents/       # AI agent system
│   │   ├── api/          # API routers
│   │   ├── portfolio/    # Portfolio management
│   │   ├── watchlist/    # Watchlist intelligence + narrative system
│   │   ├── sources/      # Data sources (multi-source failover)
│   │   └── storage/      # PostgreSQL storage layer
│   ├── tests/            # 145 tests (100% passing, 85% coverage)
│   ├── migrations/       # Database schema migrations
│   └── data/             # Database backups only (PostgreSQL managed externally)
├── frontend/             # Next.js 16 application
│   ├── app/              # Pages (dashboard, portfolio, settings, ideas)
│   ├── components/       # React components
│   └── lib/              # API clients & hooks
├── docs/core/            # Documentation
└── tasks/                # PRDs and task lists
```

## 📚 Documentation

- **[/capabilities → Vision tab](http://localhost:3000/capabilities)** - Mission, vision, and strategic goals (DB-backed)
- **[docs/core/ARCHITECTURE.md](docs/core/ARCHITECTURE.md)** - System design and components
- **[docs/core/DEVELOPMENT.md](docs/core/DEVELOPMENT.md)** - Development workflows and standards
- **[docs/core/SETUP.md](docs/core/SETUP.md)** - Installation and setup guide
- **[docs/core/REFACTOR_STATUS.md](docs/core/REFACTOR_STATUS.md)** - Current status and priorities
- **[CLAUDE.md](CLAUDE.md)** - Project governance and AI agent guidelines
- **[tasks/](tasks/)** - PRD and detailed task breakdowns

## 🔧 Development Workflow

See **[CLAUDE.md](./CLAUDE.md#-command-quick-reference)** for complete commands.

```bash
# Run tests
cd ~/portfolio-ai/backend && pytest tests/ -v --cov=app

# Linting
~/portfolio-ai/scripts/lint.sh

# Type checking
cd ~/portfolio-ai/backend && mypy app/ --strict

# Validate slash commands
~/portfolio-ai/scripts/validate-commands.sh
```

## 🎯 Next Steps

See [docs/core/REFACTOR_STATUS.md](docs/core/REFACTOR_STATUS.md) for detailed priorities.

**Immediate**:
1. Complete PRD #0014 Phase 2: Intelligence Layer (sentiment scoring, fundamentals, AI summaries)
2. Complete remaining PRD #0011 features (risk management suite, MCP server)

**Short-term**:
1. Remote access configuration (Tailscale serve)
2. User guides and agent documentation

## 💡 Tips

- Agents cost money - each run uses Claude API
- Price data requires internet (yfinance)
- Database auto-created on first backend startup
- Use `/do_it ~/portfolio-ai/tasks/tasks-0009-prd-portfolio-ai-platform.md` to continue development

## 📝 License

Private project - All rights reserved

---

**Built with Claude Code** 🤖
