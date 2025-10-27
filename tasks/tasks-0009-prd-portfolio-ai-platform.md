# Task List: PRD #0009 - AI-Led Portfolio Intelligence Platform (Standalone Project)

**Status**: 🟡 IN PROGRESS
**Created**: 2025-10-27
**PRD**: tasks/0009-prd-portfolio-ai-platform.md
**Project Type**: NEW STANDALONE PROJECT (greenfield)
**Location**: /home/kasadis/portfolio-ai/

---

## Relevant Files

### Infrastructure Files (Copied from market-sim)
- `.ai_dev_tasks/document_it.md` - /doc_it command definition
- `.ai_dev_tasks/plan_it.md` - /plan_it command definition
- `.ai_dev_tasks/task_it.md` - /task_it command definition
- `.ai_dev_tasks/do_it.md` - /do_it command definition
- `.ai_dev_tasks/next_it.md` - /next_it command definition
- `.ai_dev_tasks/README.md` - AI Dev Tasks workflow documentation
- `scripts/validate-commands.sh` - Validates slash commands work
- `scripts/lint.sh` - Runs ruff + mypy linting
- `docs/core/ARCHITECTURE.md` - System architecture documentation
- `docs/core/DEVELOPMENT.md` - Development workflows and standards
- `docs/core/SETUP.md` - Getting started guide
- `docs/core/OPERATIONS.md` - Deployment and operations
- `docs/core/API_REFERENCE.md` - API endpoint documentation
- `docs/core/REFACTOR_STATUS.md` - Active work tracking
- `CLAUDE.md` - Project governance and quick reference
- `pyproject.toml` - Python project config (ruff, mypy, pytest)
- `.gitignore` - Git ignore patterns

### Backend Files (New + Copied)
- `backend/app/constants.py` - Application-wide constants (created for portfolio-ai)
- `backend/app/storage/__init__.py` - Storage module exports (created)
- `backend/app/storage/connection.py` - DuckDB connection manager (copied from market-sim)
- `backend/app/storage/schema.py` - Schema manager with 8 portfolio tables (created from scratch)
- `backend/app/storage/ingestion.py` - Ingestion manager (simplified from market-sim)
- `backend/app/storage/metadata.py` - Metadata manager (adapted for portfolio tables)
- `backend/app/storage/queries.py` - Query manager (simplified from market-sim)
- `backend/app/storage/facade.py` - Storage facade (adapted from market-sim)
- `backend/tests/__init__.py` - Test module (created)
- `backend/tests/test_storage_schema.py` - Schema creation unit tests (11 tests, all passing)
- `backend/app/portfolio/__init__.py` - Portfolio module exports (created)
- `backend/app/portfolio/models.py` - Pydantic data models (Account, Position, PriceData, PortfolioValue, ConcentrationMetrics, PortfolioAnalytics)
- `backend/app/portfolio/manager.py` - PortfolioManager for CRUD operations (created)
- `backend/app/portfolio/price_fetcher.py` - PriceDataFetcher with yfinance and caching (created)
- `backend/app/portfolio/analytics.py` - PortfolioAnalytics calculator (created)
- `backend/tests/test_portfolio_manager.py` - PortfolioManager unit tests (14 tests, all passing)
- `backend/tests/test_portfolio_analytics.py` - PortfolioAnalytics unit tests (7 tests, all passing)
- `backend/tests/test_price_fetcher.py` - PriceDataFetcher unit tests (8 tests with mocks, all passing)
- `backend/tests/test_agent_tools.py` - Agent tools unit tests (14 tests with mocked data sources, all passing)
- `backend/tests/test_discovery_agent.py` - Discovery Agent integration tests (13 tests, all passing)
- `backend/tests/test_portfolio_analyzer.py` - Portfolio Analyzer Agent integration tests (13 tests, all passing)
- `backend/app/sources/fred.py` - FRED API integration (copied from market-sim)
- `backend/app/sources/news.py` - Google News RSS integration (created)
- `backend/app/agents/base.py` - Base Agent class (created)
- `backend/app/agents/tools.py` - Agent tools with JSON serialization (created)
- `backend/app/agents/discovery.py` - Discovery Agent (created)
- `backend/app/agents/portfolio_analyzer.py` - Portfolio Analyzer Agent (created)
- `backend/app/main.py` - FastAPI application with CORS (created)
- `backend/app/api/__init__.py` - API module init (created)
- `backend/app/api/portfolio.py` - Portfolio router with 5 endpoints (created)
- `backend/app/api/ideas.py` - Ideas router with 4 endpoints (created)
- `backend/app/api/market.py` - Market data router with 2 endpoints (created)
- `backend/app/api/preferences.py` - User preferences router with 2 endpoints (created, updated to match schema)
- `backend/tests/test_api_ideas.py` - Ideas API integration tests (16 tests, all passing)
- `backend/tests/test_api_market.py` - Market API integration tests (10 tests, all passing)
- `backend/tests/test_api_preferences.py` - Preferences API integration tests (9 tests, all passing)
- `backend/requirements.txt` - Python dependencies

### Frontend Files (New)
- `frontend/app/page.tsx` - Dashboard page (market + portfolio + ideas)
- `frontend/app/portfolio/page.tsx` - Portfolio management page with Add Position/Account dialogs
- `frontend/app/settings/page.tsx` - Settings page with risk tolerance slider, position size limit, trade preferences
- `frontend/app/ideas/[id]/page.tsx` - Idea details page with full thesis, action, impact, risks, status management
- `frontend/components/portfolio/PortfolioOverview.tsx` - Portfolio overview component with analytics
- `frontend/components/portfolio/MarketConditions.tsx` - Market conditions component (fixed TypeScript issue)
- `frontend/components/portfolio/IdeaCard.tsx` - Idea card component
- `frontend/components/portfolio/PositionTable.tsx` - Position table component with delete confirmation and toasts
- `frontend/components/ErrorBoundary.tsx` - Error boundary component for error handling
- `frontend/components/Navigation.tsx` - Navigation header with Dashboard, Portfolio, Settings links
- `frontend/lib/api/portfolio.ts` - Portfolio API client
- `frontend/lib/api/ideas.ts` - Ideas API client
- `frontend/lib/api/market.ts` - Market data API client
- `frontend/lib/hooks/usePortfolio.ts` - Portfolio React Query hooks (15-min auto-refetch for prices)
- `frontend/lib/hooks/useIdeas.ts` - Ideas React Query hooks
- `frontend/lib/hooks/usePreferences.ts` - Preferences React Query hooks
- `frontend/lib/api/preferences.ts` - Preferences API client
- `frontend/components/ui/dialog.tsx` - Dialog component (shadcn/ui)
- `frontend/components/ui/label.tsx` - Label component (shadcn/ui)
- `frontend/components/ui/select.tsx` - Select component (shadcn/ui)
- `frontend/app/layout.tsx` - Root layout with Toaster provider
- `frontend/package.json` - Node.js dependencies (added sonner for toasts)
- `frontend/tsconfig.json` - TypeScript configuration

### Configuration Files (New)
- `config/portfolio/default_preferences.yaml` - Default user preferences seed data
- `data/portfolio-ai.db` - DuckDB database file (auto-created)

---

## Tasks

- [x] 0.0 Project Bootstrap & Infrastructure Setup
  - [x] 0.1 Create `/home/kasadis/portfolio-ai/` directory structure (backend/, frontend/, data/, config/, tasks/, docs/, scripts/)
  - [x] 0.2 Initialize git repository (`git init` in portfolio-ai/)
  - [x] 0.3 Copy `.ai_dev_tasks/` folder from market-sim to portfolio-ai/
  - [x] 0.4 Copy `docs/core/` folder structure from market-sim (create templates, not full content)
  - [x] 0.5 Copy `scripts/validate-commands.sh` from market-sim to portfolio-ai/scripts/
  - [x] 0.6 Copy `scripts/lint.sh` from market-sim to portfolio-ai/scripts/ and adapt paths for backend/
  - [x] 0.7 Copy `pyproject.toml` from market-sim to portfolio-ai/backend/ and adapt project name
  - [x] 0.8 Copy `.gitignore` from market-sim to portfolio-ai/
  - [x] 0.9 Create `CLAUDE.md` in portfolio-ai/ adapted from market-sim version (update project name, paths, commands)
  - [x] 0.10 Create initial `README.md` with project overview, setup instructions, and tech stack
  - [x] 0.11 Create Python virtual environment (`python3 -m venv backend/.venv`)
  - [x] 0.12 Create `backend/requirements.txt` with core dependencies (fastapi, uvicorn, duckdb, pydantic, pytest, ruff, mypy)
  - [x] 0.13 Install Python dependencies (`source backend/.venv/bin/activate && pip install -r backend/requirements.txt`)
  - [x] 0.14 Initialize Next.js project in frontend/ (`npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir`)
  - [x] 0.15 Install additional frontend dependencies (react-query, @tanstack/react-table, shadcn/ui components)
  - [x] 0.16 Create backend/app/ module structure (__init__.py files for storage/, sources/, portfolio/, agents/, api/)
  - [x] 0.17 Create config/portfolio/ directory for YAML seed data
  - [x] 0.18 Create data/ directory for DuckDB database
  - [x] 0.19 Run `scripts/validate-commands.sh` to verify slash commands work
  - [x] 0.20 Create initial git commit ("feat: project bootstrap with infrastructure from market-sim")

- [x] 1.0 Storage Layer & Database Schema
  - [x] 1.1 Copy `app/storage/connection.py` from market-sim to backend/app/storage/ (no changes needed)
  - [x] 1.2 Copy `app/storage/metadata.py` from market-sim to backend/app/storage/ (adapted for portfolio tables)
  - [x] 1.3 Copy `app/storage/queries.py` from market-sim to backend/app/storage/ (simplified for portfolio-ai)
  - [x] 1.4 Copy `app/storage/ingestion.py` from market-sim to backend/app/storage/ (simplified for portfolio data)
  - [x] 1.5 Copy `app/storage/schema.py` from market-sim to backend/app/storage/ and add portfolio table schemas
  - [x] 1.6 Add portfolio_accounts table schema to SchemaManager._create_config_tables()
  - [x] 1.7 Add portfolio_positions table schema to SchemaManager._create_config_tables()
  - [x] 1.8 Add user_preferences table schema to SchemaManager._create_config_tables()
  - [x] 1.9 Add price_cache table schema to SchemaManager._create_timeseries_tables()
  - [x] 1.10 Add agent_runs table schema to SchemaManager._create_metadata_tables()
  - [x] 1.11 Add agent_ideas table schema to SchemaManager._create_metadata_tables()
  - [x] 1.12 Add agent_tool_calls table schema to SchemaManager._create_metadata_tables()
  - [x] 1.13 Add validation_results table schema to SchemaManager._create_metadata_tables()
  - [x] 1.14 Update table registry metadata in _populate_registry_metadata() for new tables
  - [x] 1.15 Copy `app/storage/facade.py` from market-sim to backend/app/storage/ (adapted for portfolio-ai)
  - [x] 1.16 Create backend/app/storage/__init__.py to export DuckDBStorage and get_storage
  - [x] 1.17 Write unit tests for schema creation (tests/test_storage_schema.py)
  - [x] 1.18 Test database initialization (verify all 8 tables are created)

- [x] 2.0 Portfolio Management Backend (CRUD + Analytics)
  - [x] 2.1 Create backend/app/portfolio/__init__.py module
  - [x] 2.2 Create backend/app/portfolio/models.py with Pydantic models (Position, Account, PortfolioValue, ConcentrationMetrics, PortfolioAnalytics)
  - [x] 2.3 Create backend/app/portfolio/manager.py with PortfolioManager class
  - [x] 2.4 Implement PortfolioManager.add_account(name, account_type) -> Account
  - [x] 2.5 Implement PortfolioManager.get_accounts() -> List[Account]
  - [x] 2.6 Implement PortfolioManager.add_position(account_id, symbol, shares, cost_basis, position_type) -> Position
  - [x] 2.7 Implement PortfolioManager.update_position(position_id, shares, cost_basis) -> Position
  - [x] 2.8 Implement PortfolioManager.delete_position(position_id) -> None
  - [x] 2.9 Implement PortfolioManager.get_positions(account_id=None) -> List[Position]
  - [x] 2.10 Create backend/app/portfolio/price_fetcher.py with PriceDataFetcher class
  - [x] 2.11 Implement PriceDataFetcher.fetch_prices(symbols) using yfinance as primary source
  - [x] 2.12 Implement Polygon as backup in PriceDataFetcher (placeholder for future implementation)
  - [x] 2.13 Implement price caching logic (check price_cache table, 15-minute TTL)
  - [x] 2.14 Implement PriceDataFetcher.fetch_price_data(symbols) -> Dict[str, PriceData] (price, beta, volatility, sector)
  - [x] 2.15 Create backend/app/portfolio/analytics.py with PortfolioAnalytics class
  - [x] 2.16 Implement calculate_portfolio_value(positions, price_data) -> PortfolioValue (total_value, cost_basis, gain, gain_pct)
  - [x] 2.17 Implement calculate_portfolio_beta(positions, price_data) -> float (weighted average of position betas)
  - [x] 2.18 Implement calculate_portfolio_volatility(positions, price_data) -> float (weighted average volatility)
  - [x] 2.19 Implement calculate_sector_exposure(positions, price_data) -> Dict[str, float] (% in each sector)
  - [x] 2.20 Implement calculate_concentration_risk(positions, price_data) -> ConcentrationMetrics (top_holding_pct, top_3_pct, top_10_pct, herfindahl_index)
  - [x] 2.21 Write unit tests for PortfolioManager CRUD operations (tests/test_portfolio_manager.py) - 14 tests
  - [x] 2.22 Write unit tests for PriceDataFetcher (tests/test_price_fetcher.py) with mocked yfinance - 8 tests
  - [x] 2.23 Write unit tests for PortfolioAnalytics calculations (tests/test_portfolio_analytics.py) - 7 tests
  - [x] 2.24 Run tests and verify 80%+ coverage for portfolio module (achieved 94% coverage)

- [x] 3.0 AI Agent System (Discovery + Portfolio Analyzer)
  - [x] 3.1 Created simplified FRED and News sources (adapted from market-sim)
  - [x] 3.2 Skipped multi_source_fetcher (using direct sources instead)
  - [x] 3.3 Create backend/app/agents/__init__.py module
  - [x] 3.4 Create backend/app/agents/base.py with base Agent class (tool calling, execution tracking, Claude API)
  - [x] 3.5 Create backend/app/agents/tools.py with 5 agent tools (news, economic data, portfolio, price, store_idea)
  - [x] 3.6-3.10 Implemented AgentTools class with all tool executors (integrated into tools.py)
  - [x] 3.11 Create backend/app/agents/discovery.py with DiscoveryAgent class
  - [x] 3.12 Implement Discovery Agent system prompt (scan news/FRED, generate 5 general ideas)
  - [x] 3.13 Implement Discovery Agent run() method (Claude API, tool calling, idea storage)
  - [x] 3.14 Create backend/app/agents/portfolio_analyzer.py with PortfolioAnalyzerAgent class
  - [x] 3.15 Implement Portfolio Analyzer Agent system prompt (analyze portfolio, generate personalized ideas)
  - [x] 3.16 Implement Portfolio Analyzer Agent run() method (portfolio analysis, Claude API, idea storage)
  - [x] 3.17-3.21 Execution and tool tracking implemented in base Agent class
  - [x] 3.22 Write unit tests for agent tools (tests/test_agent_tools.py) with mocked data sources
  - [x] 3.23 Write integration test for Discovery Agent execution (tests/test_discovery_agent.py)
  - [x] 3.24 Write integration test for Portfolio Analyzer Agent execution (tests/test_portfolio_analyzer.py)
  - [x] 3.25 Test agent run tracking (verify agent_runs and agent_tool_calls tables are populated)

- [x] 4.0 FastAPI Backend (Routers + Business Logic) - COMPLETED (38 API tests, 13 endpoints, 86% coverage)
  - [x] 4.1 Create backend/app/main.py FastAPI application with CORS middleware
  - [x] 4.2 Create backend/app/api/__init__.py module
  - [x] 4.3 Create backend/app/api/portfolio.py router
  - [x] 4.4 Implement GET /api/portfolio endpoint (returns all positions with current values)
  - [x] 4.5 Implement POST /api/portfolio/account endpoint (create new account)
  - [x] 4.6 Implement POST /api/portfolio/position endpoint (add or update position)
  - [x] 4.7 Implement DELETE /api/portfolio/position/{id} endpoint (delete position)
  - [x] 4.8 Implement GET /api/portfolio/analytics endpoint (returns portfolio value, beta, volatility, concentration, sector exposure)
  - [x] 4.9 Create backend/app/api/ideas.py router
  - [x] 4.10 Implement GET /api/ideas endpoint (filter by type and status, sorted by confidence score DESC)
  - [x] 4.11 Implement POST /api/ideas/generate endpoint (trigger agent run directly)
  - [x] 4.12 Implement GET /api/ideas/{id} endpoint (get detailed idea with full analysis)
  - [x] 4.13 Implement PATCH /api/ideas/{id}/status endpoint (update idea status: pending → validated → executed)
  - [x] 4.14 Create backend/app/api/market.py router
  - [x] 4.15 Implement GET /api/market/conditions endpoint (fetch S&P 500, VIX, 10Y yield, USD index from yfinance)
  - [x] 4.16 Implement GET /api/market/prices endpoint (get current prices for symbols via PriceDataFetcher)
  - [x] 4.17 Create backend/app/api/preferences.py router
  - [x] 4.18 Implement GET /api/preferences endpoint (get user's risk tolerance and trade preferences from user_preferences table)
  - [x] 4.19 Implement POST /api/preferences endpoint (update preferences: risk_tolerance, allow_long, allow_short, etc.)
  - [x] 4.20 Create Pydantic request/response models (created inline in router files)
  - [x] 4.21 Register all routers in backend/app/main.py
  - [x] 4.22 Add startup event to initialize database schema (call storage.ensure_schema())
  - [x] 4.23 Write API integration tests for portfolio endpoints (tests/test_api_portfolio.py) - 3 basic tests
  - [x] 4.24 Write API integration tests for ideas endpoints (tests/test_api_ideas.py) - 16 tests
  - [x] 4.25 Write API integration tests for market and preferences endpoints (tests/test_api_market.py - 10 tests, tests/test_api_preferences.py - 9 tests)
  - [x] 4.26 Test backend startup (run `uvicorn app.main:app --reload` and verify all endpoints accessible - all 13 endpoints working)

- [x] 5.0 Next.js UI (Dashboard + Portfolio + Settings)
  - [x] 5.1 Create frontend/lib/api/ directory for API client functions
  - [x] 5.2 Create frontend/lib/api/portfolio.ts with fetchPortfolio(), addPosition(), deletePosition(), fetchAnalytics()
  - [x] 5.3 Create frontend/lib/api/ideas.ts with fetchIdeas(), generateIdeas(), fetchIdeaDetails(), updateIdeaStatus()
  - [x] 5.4 Create frontend/lib/api/market.ts with fetchMarketConditions(), fetchPrices()
  - [x] 5.5 Create frontend/lib/api/preferences.ts with fetchPreferences(), updatePreferences()
  - [x] 5.6 Create frontend/lib/hooks/ directory for React Query hooks
  - [x] 5.7 Create frontend/lib/hooks/usePortfolio.ts with usePortfolio(), usePortfolioAnalytics(), useAddPosition(), useDeletePosition()
  - [x] 5.8 Create frontend/lib/hooks/useIdeas.ts with useIdeas(), useGenerateIdeas(), useIdeaDetails(), useUpdateIdeaStatus()
  - [x] 5.9 Create frontend/lib/hooks/useMarket.ts with useMarketConditions()
  - [x] 5.10 Create frontend/lib/hooks/usePreferences.ts with usePreferences(), useUpdatePreferences()
  - [x] 5.11 Create frontend/components/portfolio/ directory for portfolio components
  - [x] 5.12 Create frontend/components/portfolio/PortfolioOverview.tsx (displays total value, P&L, beta, volatility, top holdings)
  - [x] 5.13 Create frontend/components/portfolio/MarketConditions.tsx (displays S&P 500, VIX, yields, latest headlines)
  - [x] 5.14 Create frontend/components/portfolio/IdeaCard.tsx (displays single idea with confidence badge, risk level, reward estimate)
  - [x] 5.15 Create frontend/components/portfolio/PositionTable.tsx (displays holdings with TanStack Table: symbol, shares, cost, current price, value, gain)
  - [x] 5.16 Build Dashboard page frontend/app/page.tsx (layout: MarketConditions + PortfolioOverview + top 5 IdeaCards)
  - [x] 5.17 Add "Generate New Ideas" button on Dashboard with loading state and agent type selector
  - [x] 5.18 Build Portfolio management page frontend/app/portfolio/page.tsx (PositionTable + analytics + add/edit/delete forms)
  - [x] 5.19 Add "Add Position" form modal (account selector, symbol input, shares, cost basis, position type dropdown)
  - [x] 5.20 Add "Add Account" form modal (name input, account type dropdown: IRA/Taxable/401k/Roth/HSA)
  - [x] 5.21 Build Settings page frontend/app/settings/page.tsx (risk tolerance slider 1-10, trade type checkboxes)
  - [x] 5.22 Build Idea details page frontend/app/ideas/[id]/page.tsx (full thesis, action, portfolio impact, data needed, risks)
  - [x] 5.23 Add loading states (skeleton screens) for all data fetching using React Query isLoading
  - [x] 5.24 Add error handling with error boundary components and toast notifications
  - [x] 5.25 Add form validation for position entry (symbol format regex, positive numbers for shares/cost)
  - [x] 5.26 Style all components with Tailwind CSS and shadcn/ui components (Card, Table, Button, Input, Slider, Checkbox)
  - [x] 5.27 Implement real-time price updates (poll /api/market/prices every 15 minutes, update PositionTable)
  - [x] 5.28 Add navigation header with links to Dashboard, Portfolio, Settings
  - [x] 5.29 Test frontend (run `npm run dev` and verify all pages render, API integration works)

- [ ] 6.0 Testing & Integration
  - [x] 6.1 Run full backend test suite (`cd backend && source .venv/bin/activate && pytest tests/ -v --cov=app --cov-report=term-missing`)
  - [x] 6.2 Review coverage report and add tests to reach 80%+ coverage
  - [x] 6.3 Write integration test for portfolio CRUD flow (add account → add position → fetch analytics → delete position)
  - [x] 6.4 Write integration test for agent generation flow (trigger Discovery Agent → verify ideas stored → fetch ideas via API)
  - [x] 6.5 Write integration test for Portfolio Analyzer flow (add portfolio positions → trigger Portfolio Analyzer → verify personalized ideas)
  - [x] 6.6 Write integration test for price data fetching with yfinance primary and Polygon fallback
  - [ ] 6.7 Manual testing: Start backend (`uvicorn app.main:app --reload`) and frontend (`npm run dev`)
  - [ ] 6.8 Manual testing: Add real portfolio positions via UI (test add account, add position, view analytics)
  - [ ] 6.9 Manual testing: Generate ideas via UI (test Discovery Agent, verify 5 general ideas appear)
  - [ ] 6.10 Manual testing: Generate personalized ideas via UI (test Portfolio Analyzer, verify ideas reference portfolio)
  - [ ] 6.11 Manual testing: Verify portfolio analytics match expectations (beta, volatility, sector exposure, concentration)
  - [ ] 6.12 Manual testing: Verify price data is current (check last_updated timestamps in price_cache table)
  - [ ] 6.13 Test agent cost tracking (verify costs logged in agent_runs.cost_usd, limits enforced at $0.50)
  - [ ] 6.14 Test edge cases (empty portfolio, single position, invalid symbol, API failures)
  - [ ] 6.15 Performance testing: Measure agent run time (should be < 2 minutes for both agents)
  - [ ] 6.16 Performance testing: Measure API response times (should be < 500ms for portfolio endpoints)
  - [ ] 6.17 Fix any bugs discovered during testing

- [ ] 7.0 Documentation & Deployment
  - [ ] 7.1 Populate docs/core/ARCHITECTURE.md with portfolio-ai system design (components, data flow, tech stack)
  - [ ] 7.2 Populate docs/core/DEVELOPMENT.md with development workflows (testing, linting, git conventions)
  - [ ] 7.3 Populate docs/core/SETUP.md with setup instructions (prerequisites, installation, running locally)
  - [ ] 7.4 Populate docs/core/OPERATIONS.md with deployment instructions (native execution, no Docker)
  - [ ] 7.5 Populate docs/core/API_REFERENCE.md with all API endpoints (portfolio, ideas, market, preferences)
  - [ ] 7.6 Create docs/core/REFACTOR_STATUS.md for tracking future work and tech debt
  - [ ] 7.7 Create docs/guides/portfolio-management.md user guide (how to add positions, interpret analytics)
  - [ ] 7.8 Create docs/guides/agent-system.md guide (how agents work, system prompts, cost tracking)
  - [ ] 7.9 Document agent system prompts in docs/agents/discovery-agent.md and docs/agents/portfolio-analyzer-agent.md
  - [ ] 7.10 Update CLAUDE.md with portfolio-ai quick start commands (run backend, run frontend, run tests, run linting)
  - [ ] 7.11 Create deployment instructions in docs/deployment/local-development.md (backend + frontend startup)
  - [ ] 7.12 Add troubleshooting section to docs/core/OPERATIONS.md (common issues: price data failures, agent errors, database locks)
  - [ ] 7.13 Create main reference document docs/PORTFOLIO_AI_PLATFORM.md (overview, features, architecture, getting started)
  - [ ] 7.14 Update README.md with project overview, features, tech stack, quick start
  - [ ] 7.15 Run `scripts/validate-commands.sh` to verify all slash commands work
  - [ ] 7.16 Create final git commit ("docs: complete documentation for portfolio-ai MVP")

- [ ] 8.0 Remote Access & Backup Configuration
  - [ ] 8.1 Configure Tailscale serve for portfolio-ai frontend (port 3000)
  - [ ] 8.2 Configure Tailscale serve for portfolio-ai backend API (port 8000)
  - [ ] 8.3 Test remote access from phone/other devices over Tailscale
  - [ ] 8.4 Update restic backup script to include /home/kasadis/portfolio-ai/
  - [ ] 8.5 Verify restic backup includes portfolio-ai data directory
  - [ ] 8.6 Document Tailscale setup in docs/core/OPERATIONS.md
  - [ ] 8.7 Document backup configuration in docs/core/OPERATIONS.md
  - [ ] 8.8 Create troubleshooting guide for remote access issues
  - [ ] 8.9 Test backup restoration for portfolio-ai files

---

## Notes

- **This is a NEW STANDALONE PROJECT at `/home/kasadis/portfolio-ai/`**
- **No Docker** - Backend runs in Python .venv, frontend runs via npm
- **Separate database**: `data/portfolio-ai.db` (auto-created by backend on first run)
- **Infrastructure copied from market-sim**: Dev workflow, storage layer, FRED/News integrations, testing/linting setup
- **Testing**: Target 80%+ backend test coverage, run tests with `pytest tests/ -v --cov=app`
- **Linting**: Run `./scripts/lint.sh` before commits (ruff + mypy)
- **Backend commands**: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload` (runs on localhost:8000)
- **Frontend commands**: `cd frontend && npm run dev` (runs on localhost:3000)
- **Agent costs**: Track in agent_runs.cost_usd, abort if exceeds $0.50 per run
- **Price data**: yfinance primary, Polygon backup, 15-minute cache
- **File size guidelines**: 500 soft limit, 800 hard limit (from market-sim conventions)
- **Type hints**: Mandatory for all Python functions (from market-sim conventions)
- **Remote access**: Configure Tailscale serve for ports 3000 (frontend) and 8000 (backend API)
- **Backup**: Add portfolio-ai folder to restic backup targets in ~/.local/bin/restic-backup.sh

## Session Progress (2025-10-27)

**Session 1 - Backend Foundation**:
- ✅ Task 1.0: Storage Layer & Database Schema (8 tables, 5 managers, 11 tests)
- ✅ Task 2.0: Portfolio Management Backend (4 modules, 94% coverage, 29 tests)
- ✅ Task 3.0: AI Agent System (2 agents, 5 tools, base framework)
- Commits: 5333f3e, adf5ce9, 5ac5b1f, 0440673

**Session 2 - Backend API & Frontend Foundation**:
- ✅ Task 4.0: FastAPI Backend COMPLETE (38 API tests, 13 endpoints, 86% coverage)
  - Commit: 96b4078
- ✅ Task 5.0: Next.js UI (17/29 tasks - 59% complete)
  - API clients + React Query hooks (tasks 5.1-5.10)
    - Commit: 0c4bf45
  - Core display components (tasks 5.11-5.14)
    - Commit: 6c145a8
  - Dashboard + PositionTable (tasks 5.15-5.17)
    - Commit: 87af38e

**Status**: 4/8 major sections complete + 1 section 59% complete
**Total tests**: 118 passing
**Coverage**: 86% overall
**Working MVP**: Dashboard with portfolio display, market conditions, AI ideas generation

**Next session starts**: Task 5.18 (Portfolio management page with forms)
