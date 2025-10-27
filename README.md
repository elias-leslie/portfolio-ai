# Portfolio AI Platform

AI-led investment intelligence platform combining portfolio analytics with autonomous agent-driven market insights.

## 🎯 Project Status

**Last Updated**: 2025-10-27  
**Development Phase**: MVP Complete - Ready for Manual Testing

### ✅ What's Done (Automated)
- Full-stack application (FastAPI + Next.js)
- Portfolio management with real-time analytics
- AI agent system (Discovery Agent + Portfolio Analyzer)
- 121 tests passing, 86% coverage
- Complete UI with navigation, forms, error handling

### 🧪 What's Next (Manual Testing Required)
See **[HANDOFF_NOTES.md](./HANDOFF_NOTES.md)** for detailed testing checklist.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Anthropic API key (for AI agents)

### Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create .env file with your API key
echo "ANTHROPIC_API_KEY=your-key-here" > .env

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
cd frontend
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
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start frontend  
cd frontend && npm run dev

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
- **Frontend**: Next.js 14, React Query, shadcn/ui, Tailwind CSS
- **Backend**: FastAPI, DuckDB, Pydantic
- **AI**: Anthropic Claude API
- **Data**: yfinance, FRED, Google News RSS

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
# Backend tests (86% coverage)
cd backend
source .venv/bin/activate
pytest tests/ -v --cov=app --cov-report=term-missing

# Frontend build
cd frontend
npm run build
```

## 📁 Project Structure

```
portfolio-ai/
├── backend/              # Python FastAPI application
│   ├── app/
│   │   ├── agents/       # AI agent system
│   │   ├── api/          # API routers
│   │   ├── portfolio/    # Portfolio management
│   │   ├── sources/      # Data sources (yfinance, FRED, News)
│   │   └── storage/      # DuckDB storage layer
│   └── tests/            # 121 tests
├── frontend/             # Next.js 14 application
│   ├── app/              # Pages (dashboard, portfolio, settings, ideas)
│   ├── components/       # React components
│   └── lib/              # API clients & hooks
├── data/                 # DuckDB database (auto-created)
├── docs/core/            # Documentation
└── tasks/                # PRDs and task lists
```

## 📚 Documentation

- **[ARCHITECTURE.md](./docs/core/ARCHITECTURE.md)** - System design and components
- **[HANDOFF_NOTES.md](./HANDOFF_NOTES.md)** - Manual testing checklist
- **[CLAUDE.md](./CLAUDE.md)** - Project governance and commands
- **[tasks/](./tasks/)** - PRD and detailed task breakdowns

## 🔧 Development Workflow

See **[CLAUDE.md](./CLAUDE.md#-command-quick-reference)** for complete commands.

```bash
# Run tests
pytest tests/ -v --cov=app

# Linting
./scripts/lint.sh

# Type checking
mypy app/ --strict

# Validate slash commands
./scripts/validate-commands.sh
```

## 🎯 Next Steps

1. **Manual Testing** - Test app via Tailscale on phone (see HANDOFF_NOTES.md)
2. **Documentation** - Complete remaining docs (SETUP, DEVELOPMENT, OPERATIONS, API_REFERENCE)
3. **Remote Access** - Configure permanent Tailscale serve
4. **Backup** - Add to restic backup configuration

## 💡 Tips

- Agents cost money - each run uses Claude API
- Price data requires internet (yfinance)
- Database auto-created on first backend startup
- Use `/do_it tasks/tasks-0009-prd-portfolio-ai-platform.md` to continue development

## 📝 License

Private project - All rights reserved

---

**Built with Claude Code** 🤖
