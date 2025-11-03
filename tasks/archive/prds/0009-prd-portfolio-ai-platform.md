# PRD #0009: AI-Led Portfolio Intelligence Platform (MVP) - Standalone Project

**Status**: 🟡 IN PROGRESS
**Created**: 2025-10-27
**Priority**: P0 (Strategic Foundation)
**Effort**: 3-4 weeks with AI assistance
**Owner**: TBD
**Project Type**: NEW STANDALONE PROJECT (greenfield)

---

## Executive Summary

**Strategic Vision**: Build a **personalized AI-powered portfolio management platform** that analyzes YOUR specific holdings, market conditions, and trading preferences to generate actionable, ranked trading ideas.

**MVP Goal**: Working system you can use TODAY with your real portfolio to get personalized AI-generated trading ideas.

**Key Insight**: Generic market ideas are noise. **Personalized ideas analyzing your specific portfolio** (e.g., "Trim AAPL from 18% to 12%", "Add XLE for energy exposure") deliver real value.

**Project Approach**: Build as a **new standalone project** at `/home/kasadis/portfolio-ai/` that:
- Copies proven patterns and infrastructure from market-sim
- Inherits the entire dev workflow (AI dev tasks, documentation structure, testing/linting)
- Runs natively without Docker (Python .venv + npm)
- Uses separate DuckDB database

---

## Problem Statement

### User Success Criteria

> "Truly understanding global/USA markets and consistently finding real ideas/strategies/trades that allow me to manage my portfolio and make real money with defined (minimal) risk"

**Analysis**:
- ❌ **Generic ideas don't help** - "Buy tech stocks" is useless if you're already 50% tech
- ✅ **Personalized analysis needed** - "Trim AAPL, add defensive" is actionable
- ✅ **Portfolio context matters** - Agent must know your holdings, risk tolerance, constraints
- ✅ **Visual dashboard required** - User is visual, needs to SEE ideas ranked and explained

**Conclusion**: System must combine portfolio management + AI analysis + data visualization.

---

## Project Structure (New Standalone Project)

```
/home/kasadis/portfolio-ai/
├── .ai_dev_tasks/              # ← COPIED from market-sim
│   ├── document_it.md          # /doc_it command
│   ├── plan_it.md              # /plan_it command
│   ├── task_it.md              # /task_it command
│   ├── do_it.md                # /do_it command
│   ├── next_it.md              # /next_it command
│   └── README.md               # Workflow docs
├── docs/                       # ← COPIED structure from market-sim
│   └── core/
│       ├── ARCHITECTURE.md
│       ├── DEVELOPMENT.md
│       ├── SETUP.md
│       ├── OPERATIONS.md
│       ├── API_REFERENCE.md
│       └── REFACTOR_STATUS.md
├── scripts/                    # ← COPIED from market-sim
│   ├── validate-commands.sh
│   └── lint.sh
├── backend/                    # Python FastAPI + agents
│   ├── app/
│   │   ├── storage/           # ← COPIED/ADAPTED from market-sim
│   │   ├── sources/           # ← COPIED FRED/News integrations
│   │   ├── portfolio/         # NEW: CRUD + analytics
│   │   ├── agents/            # NEW: AI agents + tools
│   │   └── api/               # NEW: FastAPI routers
│   ├── tests/
│   ├── .venv/                 # Python virtual environment
│   ├── pyproject.toml         # ← COPIED/ADAPTED (ruff, mypy, pytest)
│   └── requirements.txt
├── frontend/                   # Next.js UI
│   ├── app/                   # App router pages
│   ├── components/            # React components
│   ├── lib/                   # API client
│   └── package.json
├── data/                       # Separate database
│   └── portfolio-ai.db        # NEW: Separate DuckDB file
├── config/                     # YAML configs
│   └── portfolio/
│       └── default_preferences.yaml
├── tasks/                      # PRDs and task lists
├── CLAUDE.md                   # ← ADAPTED from market-sim
├── README.md
├── .gitignore                  # ← COPIED from market-sim
└── .git/                       # NEW git repository
```

---

## MVP Scope (Day 1/2)

### ✅ INCLUDED

**Portfolio Management**:
- Manual entry (symbol, shares, cost basis, account name)
- Account grouping (IRA, Taxable, 401k, Roth, etc.)
- Position types (stocks, ETFs, funds, cash, options, crypto)
- Live portfolio value (pull current prices from free APIs)
- Risk metrics (beta, volatility, concentration by holding/sector)
- Simple P&L (current value - cost basis)

**AI Idea Generation**:
- General market ideas (5 ideas from scanning news/economic data)
- **Personalized ideas analyzing YOUR portfolio** (e.g., "Trim AAPL", "Add XLE")
- Risk/reward calculation per idea (portfolio-level impact)
- Confidence scoring (0-1 scale)
- Ranked by quality (best ideas at top)

**Trading Preferences**:
- Set risk tolerance (1-10 scale)
- Enable/disable trade types (long, short, options, day trade, swing trade)
- Preferences stored in database

**Data Presentation**:
- Real verified data (news from Google News, economic data from FRED, prices from yfinance/Polygon)
- No hallucinations (all data traced to source)

**Dashboard**:
- Market conditions summary (S&P 500, VIX, yields, USD)
- Portfolio overview (total value, P&L, risk metrics)
- Top 5 ideas ranked by score
- Desktop-focused UI (mobile Phase 2)

**Development Workflow** (Inherited from market-sim):
- AI Dev Tasks workflow (/plan_it, /task_it, /do_it, /doc_it, /next_it)
- Documentation structure (docs/core/)
- Testing/linting (pytest, ruff, mypy)
- Command validation (scripts/validate-commands.sh)
- Git workflow and conventions

### ❌ DEFERRED (Phase 2+)

- Screenshot/OCR portfolio upload
- Copy-paste text parsing
- Mobile responsive design
- Enable/disable specific accounts for AI consideration
- Detailed performance charts (time series, equity curves)
- Multi-timeframe profit projections (years/months/weeks/days)
- Advanced constraints (max position size, sector limits)
- Expandable article summaries
- Interactive charts
- Authentication/MFA (single user for MVP)
- Cloud deployment (localhost only for MVP)
- Docker support (native execution for MVP)

---

## Technical Architecture (MVP)

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                   Next.js Web UI (Desktop)                      │
│                   Running on localhost:3000                     │
│                                                                 │
│  Pages:                                                         │
│  - / (Dashboard: market + portfolio + top 5 ideas)            │
│  - /portfolio (Manage positions: add/edit/delete)             │
│  - /settings (Risk tolerance, trade preferences)              │
│  - /ideas/[id] (Idea details: full analysis)                  │
│                                                                 │
│  Components:                                                    │
│  - PortfolioOverview (value, P&L, metrics)                    │
│  - MarketConditions (S&P, VIX, yields)                        │
│  - IdeaCard (ranked list of ideas)                            │
│  - PositionTable (holdings with live prices)                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓ HTTP/REST (localhost:8000)
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│                   Running on localhost:8000                     │
│                   (Python .venv, no Docker)                     │
│                                                                 │
│  Routers:                                                       │
│  - /api/portfolio (GET, POST positions)                        │
│  - /api/portfolio/analytics (GET metrics)                      │
│  - /api/ideas (GET ideas, POST generate)                       │
│  - /api/market (GET market conditions)                         │
│  - /api/preferences (GET, POST risk/trade prefs)              │
│                                                                 │
│  Business Logic:                                                │
│  - PortfolioManager (CRUD for positions)                       │
│  - PortfolioAnalytics (calculate beta, volatility, etc.)       │
│  - AgentOrchestrator (trigger agent runs)                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
           ┌─────────────┴──────────────┐
           ↓                            ↓
┌────────────────────────┐    ┌──────────────────────────┐
│   Agent System         │    │   DuckDB Database        │
│                        │    │   portfolio-ai.db        │
│  Discovery Agent       │◄───│                          │
│  - Scans news/FRED     │    │  - portfolio_accounts    │
│  - Generates 5 general │    │  - portfolio_positions   │
│    market ideas        │    │  - user_preferences      │
│                        │    │  - agent_ideas           │
│  Portfolio Analyzer    │    │  - agent_runs            │
│  - Loads user portfolio│    │  - agent_tool_calls      │
│  - Calculates metrics  │    │  - price_cache           │
│  - Generates personal- │    │  - validation_results    │
│    ized ideas          │    └──────────────────────────┘
│                        │
│  Tools Available:      │
│  - NewsAPITool         │◄─── Google News RSS (copied from market-sim)
│  - FREDTool            │◄─── FRED API (copied from market-sim)
│  - PriceDataTool       │◄─── yfinance / Polygon
│  - PortfolioDatabaseTool│
│  - DatabaseTool        │
└────────────────────────┘
```

### Infrastructure to Copy from market-sim

**1. Development Workflow** (COPY ENTIRE):
- `.ai_dev_tasks/` folder with all markdown files
- `scripts/validate-commands.sh` (validates slash commands)
- `scripts/lint.sh` (ruff + mypy runner)

**2. Documentation Structure** (COPY STRUCTURE):
- `docs/core/` folder structure
- Template files (populate for portfolio-ai)

**3. Storage Layer** (COPY & ADAPT):
- `app/storage/` modular structure
- Connection, schema, ingestion, metadata, queries managers
- Adapt schema for portfolio tables

**4. Data Sources** (COPY & ADAPT):
- Multi-source fetcher pattern for API failover
- FRED API integration
- Google News RSS integration
- Adapt for portfolio-specific needs

**5. Configuration** (COPY PATTERN):
- `pyproject.toml` (ruff, mypy, pytest config)
- `.gitignore`
- Same coding standards and pre-commit checklist

**6. Testing Infrastructure** (COPY):
- pytest setup
- Test structure and patterns
- Same 80% coverage target

---

## Database Schema (MVP)

### Portfolio Tables (NEW)

```sql
-- Portfolio accounts (IRA, Taxable, etc.)
CREATE TABLE IF NOT EXISTS portfolio_accounts (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,              -- "Fidelity IRA", "Schwab Taxable"
    account_type VARCHAR NOT NULL,      -- "IRA", "Taxable", "401k", "Roth", "HSA"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Portfolio positions
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id VARCHAR PRIMARY KEY,
    account_id VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,            -- "AAPL", "SPY", "VTSAX"
    shares DECIMAL NOT NULL,            -- 100.5 shares
    cost_basis DECIMAL NOT NULL,        -- $150.25 per share (price paid)
    position_type VARCHAR NOT NULL,     -- "stock", "etf", "fund", "cash", "option", "crypto"
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES portfolio_accounts(id)
);

-- User trading preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    id VARCHAR PRIMARY KEY,
    risk_tolerance INTEGER NOT NULL DEFAULT 5,  -- 1-10 scale
    allow_long BOOLEAN DEFAULT true,
    allow_short BOOLEAN DEFAULT false,
    allow_options BOOLEAN DEFAULT false,
    allow_day_trading BOOLEAN DEFAULT false,
    allow_swing_trading BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Price cache (avoid redundant API calls)
CREATE TABLE IF NOT EXISTS price_cache (
    symbol VARCHAR PRIMARY KEY,
    price DECIMAL NOT NULL,
    beta DECIMAL,                       -- Stock beta (vs S&P 500)
    volatility DECIMAL,                 -- Annualized volatility
    sector VARCHAR,                     -- "Technology", "Healthcare", etc.
    market_cap BIGINT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Agent Tables (NEW)

```sql
-- Agent execution tracking
CREATE TABLE IF NOT EXISTS agent_runs (
    id VARCHAR PRIMARY KEY,
    agent_type VARCHAR NOT NULL,        -- "discovery", "portfolio_analyzer"
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR DEFAULT 'running',   -- 'running', 'completed', 'failed'
    num_ideas INTEGER DEFAULT 0,
    num_tool_calls INTEGER DEFAULT 0,
    cost_usd DECIMAL(10, 4) DEFAULT 0,
    error_message TEXT,
    prompt_hash VARCHAR
);

-- Agent-generated ideas
CREATE TABLE IF NOT EXISTS agent_ideas (
    id VARCHAR PRIMARY KEY,
    agent_run_id VARCHAR NOT NULL,
    idea_type VARCHAR NOT NULL,         -- "general", "personalized"
    thesis TEXT NOT NULL,
    asset_class VARCHAR,                -- "equity", "fixed_income", "commodity"
    symbols TEXT[],                     -- ["AAPL", "MSFT"]
    action TEXT,                        -- "Trim AAPL from 18% to 12%"
    data_needed TEXT[],
    risks TEXT[],
    confidence_score FLOAT,             -- 0.0-1.0
    risk_level VARCHAR,                 -- "Low", "Medium", "High"
    reward_estimate VARCHAR,            -- "+5.2% (portfolio level)"
    status VARCHAR DEFAULT 'pending',   -- 'pending', 'validated', 'rejected', 'executed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id)
);

-- Validation results (Phase 2, but define schema now)
CREATE TABLE IF NOT EXISTS validation_results (
    id VARCHAR PRIMARY KEY,
    idea_id VARCHAR NOT NULL,
    agent_run_id VARCHAR NOT NULL,
    data_source VARCHAR NOT NULL,
    data_query TEXT,
    data_summary TEXT,
    supports_thesis BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (idea_id) REFERENCES agent_ideas(id),
    FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id)
);

-- Tool call audit log
CREATE TABLE IF NOT EXISTS agent_tool_calls (
    id VARCHAR PRIMARY KEY,
    agent_run_id VARCHAR NOT NULL,
    tool_name VARCHAR NOT NULL,
    parameters TEXT,
    response_summary TEXT,
    duration_ms INTEGER,
    success BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id)
);
```

---

## Agent Specifications

### 1. Discovery Agent (General Market Ideas)

**Purpose**: Scan news and economic data to generate 5 general market ideas (not personalized)

**System Prompt**:
```markdown
You are a market intelligence analyst. Analyze current market conditions and generate 5 actionable trading ideas.

Process:
1. Fetch recent news on major themes (Fed policy, earnings, geopolitics)
2. Check key economic indicators (GDP, inflation, unemployment, yields)
3. Synthesize into 5 specific ideas
4. Store each idea with store_idea()

For each idea:
- State clear thesis (what to trade, direction, timeframe)
- Explain fundamental rationale
- List data needed to validate
- Identify concrete risks
- Assign confidence score (0.0-1.0)

Quality criteria:
- Specific (include symbols, direction, timeframe)
- Avoid generic themes
- Data needed must be obtainable
- Risks must be concrete scenarios

Begin by fetching recent market news.
```

**Tools Available**:
- `fetch_news(query, date_range)` - Google News RSS (copied from market-sim)
- `fetch_economic_data(indicator, date_range)` - FRED API (copied from market-sim)
- `store_idea(thesis, symbols, data_needed, risks, confidence)` - Write to DuckDB

---

### 2. Portfolio Analyzer Agent (Personalized Ideas)

**Purpose**: Analyze user's specific portfolio and generate personalized trading ideas

**System Prompt**:
```markdown
You are a portfolio analyst. Analyze the user's portfolio and generate 3-5 personalized trading ideas.

User's Portfolio:
{portfolio_summary}

User's Preferences:
- Risk Tolerance: {risk_tolerance}/10
- Allowed Trade Types: {allowed_trades}

Process:
1. Analyze portfolio composition (holdings, sectors, concentration)
2. Calculate risk metrics (beta, volatility, sector exposure)
3. Identify risks (overweight sectors, concentration, low diversification)
4. Fetch market data relevant to holdings
5. Generate 3-5 personalized ideas
6. Store each idea with store_idea()

For each idea:
- State specific action (e.g., "Trim AAPL from 18% to 12%")
- Explain rationale (why this helps portfolio)
- Calculate portfolio-level impact (e.g., "+5.2% expected, reduces beta from 1.15 to 1.05")
- Identify risks
- Assign confidence score

Quality criteria:
- Personalized to THIS portfolio (not generic)
- Actionable (specific symbols, quantities)
- Portfolio-level impact (not just individual stock return)
- Respects user's risk tolerance and trade preferences

Begin by analyzing the portfolio composition.
```

**Tools Available**:
- `get_portfolio_data()` - Returns positions, analytics
- `fetch_news(query, date_range)` - News about holdings
- `fetch_economic_data(indicator)` - Macro context
- `fetch_price_data(symbols)` - Current prices, betas, volatility (yfinance + Polygon)
- `store_idea(thesis, action, symbols, confidence, reward_estimate)`

---

## API Endpoints

### Portfolio Management

```python
GET /api/portfolio
# Returns all positions with current values

POST /api/portfolio/position
# Add or update a position
# Body: {account_id, symbol, shares, cost_basis, position_type}

DELETE /api/portfolio/position/{id}
# Delete a position

GET /api/portfolio/analytics
# Returns calculated metrics (value, P&L, beta, volatility, concentration)
```

### Idea Generation

```python
GET /api/ideas
# Returns all ideas (sorted by confidence, filtered by status)
# Query params: ?type=general|personalized&status=pending|validated

POST /api/ideas/generate
# Trigger agent run to generate new ideas
# Body: {agent_type: "discovery" | "portfolio_analyzer"}

GET /api/ideas/{id}
# Get detailed idea with full analysis

PATCH /api/ideas/{id}/status
# Update idea status (pending → validated → executed)
```

### Market Data

```python
GET /api/market/conditions
# Returns current market snapshot (S&P 500, VIX, yields, USD)

GET /api/market/prices
# Get current prices for symbols
# Query params: ?symbols=AAPL,MSFT,SPY
```

### Preferences

```python
GET /api/preferences
# Get user's risk tolerance and trade preferences

POST /api/preferences
# Update preferences
# Body: {risk_tolerance, allow_long, allow_short, allow_options, etc.}
```

---

## Implementation Plan

### Phase 0: Project Bootstrap (NEW - Critical Phase)
**Goal**: Setup standalone project with copied infrastructure
**Duration**: 1-2 days

**Tasks**:
1. Create `/home/kasadis/portfolio-ai/` directory structure
2. Initialize git repository
3. Copy `.ai_dev_tasks/` folder from market-sim
4. Copy `docs/core/` structure from market-sim (templates)
5. Copy `scripts/` folder (validate-commands.sh, lint.sh)
6. Copy `pyproject.toml`, `.gitignore` from market-sim
7. Adapt `CLAUDE.md` for portfolio-ai project
8. Copy storage layer from market-sim (`app/storage/`)
9. Copy multi-source fetcher pattern from market-sim
10. Copy FRED/News integrations from market-sim
11. Setup Python virtual environment (.venv)
12. Install dependencies (FastAPI, DuckDB, pytest, ruff, mypy)
13. Setup Next.js project (App Router, TypeScript, Tailwind)
14. Verify slash commands work (run scripts/validate-commands.sh)
15. Write initial README.md

### Phase 1: Backend Foundation
**Goal**: Portfolio management + database + core agents
**Duration**: 1-1.5 weeks

**Tasks**:
1. Database schema (portfolio tables + agent tables)
2. Portfolio management module (CRUD operations)
3. Portfolio analytics calculator (beta, volatility, concentration)
4. Price Data Tool (yfinance integration + Polygon fallback)
5. Portfolio Database Tool
6. Discovery Agent (general ideas)
7. Portfolio Analyzer Agent (personalized ideas)
8. Unit tests (80% coverage target)

### Phase 2: API + Basic UI
**Goal**: FastAPI + Next.js UI + integration
**Duration**: 1-1.5 weeks

**Tasks**:
1. FastAPI setup (routers, schemas)
2. Portfolio API endpoints
3. Ideas API endpoints
4. Market data API endpoints
5. Preferences API endpoints
6. Dashboard page (basic layout)
7. Portfolio management page
8. Settings page
9. API integration (React Query)

### Phase 3: Polish + Testing
**Goal**: UI polish + full integration testing + documentation
**Duration**: 1 week

**Tasks**:
1. Idea details page
2. Real-time price updates
3. Loading states + error handling
4. Integration testing (API + UI)
5. Manual testing with real portfolio
6. Performance optimization
7. Documentation (populate docs/core/, write user guide)

---

## Success Criteria (MVP)

### Functional Requirements

- ✅ **FR1**: User can add portfolio positions (symbol, shares, cost basis, account)
- ✅ **FR2**: System displays live portfolio value (pulls current prices)
- ✅ **FR3**: System calculates risk metrics (beta, volatility, concentration)
- ✅ **FR4**: Discovery Agent generates 5 general market ideas
- ✅ **FR5**: Portfolio Analyzer generates 3-5 personalized ideas
- ✅ **FR6**: Ideas include thesis, symbols, risk/reward, confidence
- ✅ **FR7**: Ideas ranked by quality (best at top)
- ✅ **FR8**: User can set risk tolerance and trade preferences
- ✅ **FR9**: Dashboard shows market conditions + portfolio + top 5 ideas
- ✅ **FR10**: All data traced to verified sources (no hallucinations)

### Quality Requirements

- ✅ **QR1**: At least 1 personalized idea is genuinely useful (user validation)
- ✅ **QR2**: Portfolio analytics are accurate (beta/volatility within 10% of broker)
- ✅ **QR3**: Price data is current (< 15 minutes old during market hours)
- ✅ **QR4**: Ideas respect user's preferences (no shorts if disabled, etc.)
- ✅ **QR5**: UI is usable on desktop (1920x1080 and 1440x900)
- ✅ **QR6**: Agent runs complete without errors
- ✅ **QR7**: Total cost < $2 for 10 agent runs (MVP budget)
- ✅ **QR8**: Code coverage > 70% (backend only)

### Infrastructure Requirements (NEW)

- ✅ **IR1**: All slash commands work (/plan_it, /task_it, /do_it, /doc_it, /next_it)
- ✅ **IR2**: Documentation follows market-sim structure (docs/core/)
- ✅ **IR3**: Testing/linting matches market-sim standards (ruff, mypy, pytest)
- ✅ **IR4**: Git workflow matches market-sim conventions
- ✅ **IR5**: No Docker dependencies (runs natively)

---

## Cost Analysis (MVP)

### Development Time (With AI Assistance)
- Phase 0 (Bootstrap): 10-15 hours
- Phase 1 (Backend): 30-40 hours
- Phase 2 (API + UI): 30-40 hours
- Phase 3 (Polish): 20-30 hours
- **Total**: 90-125 hours (3-4 weeks part-time with AI pair programming)

### API Costs (Monthly)
- **Claude API**: $50-150/month
  - Personalized analysis = more tokens (portfolio data in context)
  - ~$0.15 per run (vs $0.06 for simple POC)
  - 30 runs/month = ~$4.50
  - Development/testing = $10-20
  - Buffer for experimentation = $35-130

- **Price Data APIs**:
  - yfinance: Free (unlimited)
  - Polygon: Free tier (5 calls/min, sufficient as backup)

- **News/Economic Data**:
  - Google News RSS: Free
  - FRED: Free

- **Total Runtime**: $50-150/month (mostly Claude API)

### Hosting
- **Localhost**: $0 (runs on your home server)
- **No Docker**: $0 (native execution)
- **Total**: $0

---

## Deployment & Access (MVP)

### Local Development
- Backend: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload`
- Frontend: `cd frontend && npm run dev`
- Database: `data/portfolio-ai.db` (auto-created by backend)

### Commands (After Phase 0)
```bash
# Run tests
cd backend && source .venv/bin/activate && pytest tests/ -v

# Run linting
cd backend && ./scripts/lint.sh

# Validate slash commands
./scripts/validate-commands.sh

# Generate docs
# (use /doc_it slash command)
```

---

## Next Steps

1. ✅ **Review PRD** - Confirm scope and greenfield approach
2. 🚀 **Generate Task List** - Run `/task_it tasks/0009-prd-portfolio-ai-platform.md`
3. 🚀 **Start Implementation** - Use `/do_it` with generated task list
4. 📝 **Feedback Loop** - User tests after Phase 2, iterate

---

**Version**: 2.0 (Standalone Project)
**Last Updated**: 2025-10-27
**Supersedes**: Version 1.0 (market-sim extension approach)
