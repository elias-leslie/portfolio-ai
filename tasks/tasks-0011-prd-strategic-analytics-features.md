# Task List: PRD #0011 - Strategic Analytics Features (Backtesting & Historical Tracking)

**PRD**: `0011-prd-strategic-analytics-features.md`
**Status**: Ready for Implementation (after PRD #0010)
**Completion**: 0% (Not started)
**Effort to Complete**: High
**Last Updated**: 2025-10-27

**Note on Effort Levels**:
- **Low**: 1-2 hours of straightforward work
- **Medium**: Half day of work with some complexity
- **High**: Full day or more, significant complexity

---

## Summary

**✅ COMPLETE:**
- (None yet)

**🔄 IN PROGRESS:**
- (Not started)

**⚠️ NEXT STEPS:**
1. Begin with Task 1.0 (Historical data foundation)
2. Proceed with Task 2.0 (Backtesting engine)
3. Continue in order: 3.0 → 4.0 → 5.0

**EFFORT TO COMPLETE:** High (~20 hours total across 2 major features)

---

## High-Level Tasks (Parent Tasks)

Based on PRD #0011, here are the main implementation phases:

- [ ] **1.0 Implement Historical Price Data Foundation** (~4 hours)
- [ ] **2.0 Build Backtesting Framework for Agent Ideas** (~6 hours)
- [ ] **3.0 Implement Portfolio Snapshot System** (~4 hours)
- [ ] **4.0 Build Historical Analytics Engine** (~4 hours)
- [ ] **5.0 Create Frontend Visualization & Charts** (~4 hours)

---

## Relevant Files

### Files to Create (18 new files)

**Feature 1 - Backtesting:**
- `backend/app/analytics/__init__.py` (5 lines) - Analytics module init
- `backend/app/analytics/backtest.py` (~300 lines) - BacktestEngine implementation
- `backend/app/analytics/models.py` (~100 lines) - Backtest data models (BacktestResult, etc.)
- `backend/tests/test_backtest_engine.py` (~150 lines) - Backtest engine tests

**Feature 2 - Historical Tracking:**
- `backend/app/analytics/historical.py` (~250 lines) - HistoricalAnalytics implementation
- `backend/app/jobs/__init__.py` (5 lines) - Jobs module init
- `backend/app/jobs/snapshot_scheduler.py` (~120 lines) - Celery periodic task for snapshots
- `backend/tests/test_historical_analytics.py` (~120 lines) - Historical analytics tests
- `backend/tests/test_snapshot_scheduler.py` (~80 lines) - Snapshot scheduler tests

**Frontend Visualization:**
- `frontend/app/portfolio/performance/page.tsx` (~200 lines) - Performance tab page
- `frontend/components/analytics/PerformanceChart.tsx` (~150 lines) - Portfolio value line chart (Recharts)
- `frontend/components/analytics/MetricsSummary.tsx` (~100 lines) - Metrics cards (Sharpe, drawdown, etc.)
- `frontend/components/analytics/SectorExposureChart.tsx` (~120 lines) - Sector area chart
- `frontend/components/analytics/DrawdownChart.tsx` (~100 lines) - Drawdown visualization
- `frontend/components/ideas/BacktestResults.tsx` (~150 lines) - Backtest results display
- `frontend/lib/hooks/useHistoricalAnalytics.ts` (~80 lines) - React Query hook for historical data
- `frontend/lib/hooks/useBacktest.ts` (~60 lines) - React Query hook for backtesting

**API Endpoints:**
- `backend/app/api/analytics.py` (~200 lines) - Analytics router (historical, backtest endpoints)

### Files to Update (8 files)

**Database Schema:**
- `backend/app/storage/schema.py` - Add 4 new tables (historical_prices, backtest_results, portfolio_snapshots, position_snapshots)

**Models:**
- `backend/app/portfolio/models.py` - Add BacktestResult, PortfolioSnapshot, PositionSnapshot models

**API:**
- `backend/app/main.py` - Register analytics router
- `backend/app/api/ideas.py` - Add backtest endpoint for ideas

**Frontend:**
- `frontend/app/portfolio/page.tsx` - Add "Performance" tab link
- `frontend/lib/api.ts` - Add historical analytics API functions

**Documentation:**
- `docs/core/API_REFERENCE.md` - Document backtest and historical analytics endpoints
- `docs/guides/backtesting.md` - NEW: User guide for backtesting (create)

### Notes

- Requires PRD #0010 Feature 8 (Celery) for snapshot scheduler
- Requires PRD #0010 Feature 3 (structured logging) for backtest logging
- Requires PRD #0010 Feature 7 (multi-source) for reliable historical data
- Use existing PortfolioAnalytics class methods for snapshot calculations
- All tests should be placed in `backend/tests/` directory
- Use `pytest tests/ -v` to run all tests
- Use `mypy app/ --strict` to verify type safety
- Use `scripts/lint.sh` to run linting and formatting checks

---

## Tasks

- [ ] **1.0 Implement Historical Price Data Foundation** (~4 hours)
  - [ ] 1.1 Create historical_prices table in DuckDB
    - [ ] 1.1.1 Edit `backend/app/storage/schema.py`
    - [ ] 1.1.2 Add `_create_analytics_tables()` method to SchemaManager
    - [ ] 1.1.3 Create historical_prices table: symbol, date, open, high, low, close, volume, source, fetched_at
    - [ ] 1.1.4 Add indexes: idx_historical_prices_symbol, idx_historical_prices_date
    - [ ] 1.1.5 Add compound index: idx_historical_prices_symbol_date
    - [ ] 1.1.6 Call `_create_analytics_tables()` from `ensure_schema()`
  - [ ] 1.2 Implement historical data fetcher
    - [ ] 1.2.1 Create `backend/app/analytics/__init__.py`
    - [ ] 1.2.2 Create `backend/app/analytics/historical_fetcher.py`
    - [ ] 1.2.3 Implement `HistoricalDataFetcher` class with yfinance integration
    - [ ] 1.2.4 Method: `fetch_historical_ohlcv(symbol: str, start_date: date, end_date: date) -> pl.DataFrame`
    - [ ] 1.2.5 Use yfinance `Ticker.history()` with period/start/end parameters
    - [ ] 1.2.6 Add 24-hour cache TTL for historical fetches (cache in historical_prices table)
    - [ ] 1.2.7 Handle yfinance errors gracefully (return None on failure)
  - [ ] 1.3 Add historical data storage methods
    - [ ] 1.3.1 Edit `backend/app/storage/facade.py`
    - [ ] 1.3.2 Method: `insert_historical_prices(df: pl.DataFrame) -> None`
    - [ ] 1.3.3 Method: `get_historical_prices(symbol: str, start: date, end: date) -> pl.DataFrame`
    - [ ] 1.3.4 Use parameterized queries for all DB operations
  - [ ] 1.4 Add background job to update historical prices
    - [ ] 1.4.1 Create `backend/app/jobs/__init__.py`
    - [ ] 1.4.2 Create `backend/app/jobs/historical_update.py`
    - [ ] 1.4.3 Implement Celery periodic task to fetch daily prices for active symbols
    - [ ] 1.4.4 Task: `@celery_app.task def update_historical_prices_daily()`
    - [ ] 1.4.5 Query portfolio_positions for unique symbols
    - [ ] 1.4.6 Fetch yesterday's OHLCV for each symbol
    - [ ] 1.4.7 Insert into historical_prices table
    - [ ] 1.4.8 Schedule to run at 5:00 PM ET (after market close)
  - [ ] 1.5 Write tests for historical data
    - [ ] 1.5.1 Create `backend/tests/test_historical_fetcher.py`
    - [ ] 1.5.2 Test yfinance historical fetch (AAPL, 90 days)
    - [ ] 1.5.3 Test cache hit (fetch same data twice, verify cached)
    - [ ] 1.5.4 Test storage insert and retrieval
    - [ ] 1.5.5 Test date range filtering

- [ ] **2.0 Build Backtesting Framework for Agent Ideas** (~6 hours)
  - [ ] 2.1 Create backtest_results table
    - [ ] 2.1.1 Edit `backend/app/storage/schema.py`
    - [ ] 2.1.2 Create backtest_results table in `_create_analytics_tables()`
    - [ ] 2.1.3 Columns: id, idea_id (FK), symbol, start_date, end_date, entry_price, exit_price
    - [ ] 2.1.4 Columns: total_return_pct, annualized_return_pct, holding_days, win (BOOLEAN)
    - [ ] 2.1.5 Columns: max_drawdown_pct, risk_adjusted_return, trade_log (JSON), executed_at
    - [ ] 2.1.6 Add index: idx_backtest_idea
    - [ ] 2.1.7 Add foreign key constraint to agent_ideas table
  - [ ] 2.2 Create backtest data models
    - [ ] 2.2.1 Create `backend/app/analytics/models.py`
    - [ ] 2.2.2 Create BacktestRequest model (idea_id, start_date, end_date)
    - [ ] 2.2.3 Create BacktestResult model (matches backtest_results table schema)
    - [ ] 2.2.4 Create TradeLog model for JSON trade_log field (entry/exit events)
    - [ ] 2.2.5 Add all models to Pydantic with type hints and validation
  - [ ] 2.3 Implement BacktestEngine core logic
    - [ ] 2.3.1 Create `backend/app/analytics/backtest.py`
    - [ ] 2.3.2 Create `BacktestEngine` class with storage and historical_fetcher dependencies
    - [ ] 2.3.3 Method: `backtest_idea(idea_id: str, start_date: date, end_date: date) -> BacktestResult`
    - [ ] 2.3.4 Query agent_ideas table for idea details (action field)
    - [ ] 2.3.5 Parse idea.action to extract: symbol, target price/pct, time horizon
    - [ ] 2.3.6 Fetch historical OHLCV for symbol between start_date and end_date
    - [ ] 2.3.7 Simulate trade execution (entry at open, exit at target/timeout)
  - [ ] 2.4 Implement trade simulation logic
    - [ ] 2.4.1 Method: `_simulate_long_trade(symbol, entry_date, target_pct, horizon_days, hist_data)`
    - [ ] 2.4.2 Entry: Use next trading day's open price after entry_date
    - [ ] 2.4.3 Target: Calculate target_price = entry_price * (1 + target_pct)
    - [ ] 2.4.4 Exit: Find first day where high >= target_price OR timeout (horizon_days)
    - [ ] 2.4.5 Calculate holding period (days between entry and exit)
    - [ ] 2.4.6 Calculate total return: (exit_price - entry_price) / entry_price * 100
    - [ ] 2.4.7 Calculate max drawdown during holding period
    - [ ] 2.4.8 Calculate risk-adjusted return: total_return / max_drawdown
  - [ ] 2.5 Calculate backtest metrics
    - [ ] 2.5.1 Method: `_calculate_annualized_return(total_return_pct, holding_days) -> float`
    - [ ] 2.5.2 Formula: ((1 + total_return/100) ^ (365/holding_days)) - 1
    - [ ] 2.5.3 Method: `_calculate_max_drawdown(hist_data, entry_idx, exit_idx) -> float`
    - [ ] 2.5.4 Find peak-to-trough decline during holding period
    - [ ] 2.5.5 Method: `_determine_win(exit_price, target_price) -> bool`
    - [ ] 2.5.6 Win if exit_price >= target_price
  - [ ] 2.6 Store backtest results
    - [ ] 2.6.1 Edit `backend/app/storage/facade.py`
    - [ ] 2.6.2 Method: `insert_backtest_result(result: BacktestResult) -> None`
    - [ ] 2.6.3 Method: `get_backtest_results_for_idea(idea_id: str) -> list[BacktestResult]`
    - [ ] 2.6.4 Use parameterized queries
  - [ ] 2.7 Create backtest API endpoints
    - [ ] 2.7.1 Create `backend/app/api/analytics.py`
    - [ ] 2.7.2 Router: `router = APIRouter(prefix="/api/analytics", tags=["analytics"])`
    - [ ] 2.7.3 Endpoint: `POST /api/ideas/{idea_id}/backtest` with BacktestRequest body
    - [ ] 2.7.4 Call BacktestEngine.backtest_idea()
    - [ ] 2.7.5 Return BacktestResult with 200 status
    - [ ] 2.7.6 Endpoint: `GET /api/ideas/{idea_id}/backtest/history`
    - [ ] 2.7.7 Return list of all backtest runs for idea
    - [ ] 2.7.8 Endpoint: `GET /api/analytics/backtest/summary`
    - [ ] 2.7.9 Calculate aggregate stats: win_rate, avg_return, avg_holding_period
    - [ ] 2.7.10 Register router in `backend/app/main.py`
  - [ ] 2.8 Write backtest tests
    - [ ] 2.8.1 Create `backend/tests/test_backtest_engine.py`
    - [ ] 2.8.2 Test parse idea action (extract symbol, target, horizon)
    - [ ] 2.8.3 Test trade simulation (mock historical data)
    - [ ] 2.8.4 Test winning trade (price reaches target within horizon)
    - [ ] 2.8.5 Test losing trade (price doesn't reach target, timeout)
    - [ ] 2.8.6 Test max drawdown calculation
    - [ ] 2.8.7 Test annualized return calculation
    - [ ] 2.8.8 Test API endpoint with real idea_id

- [ ] **3.0 Implement Portfolio Snapshot System** (~4 hours)
  - [ ] 3.1 Create portfolio snapshot tables
    - [ ] 3.1.1 Edit `backend/app/storage/schema.py`
    - [ ] 3.1.2 Create portfolio_snapshots table in `_create_analytics_tables()`
    - [ ] 3.1.3 Columns: id, snapshot_date (UNIQUE), total_value, total_cost_basis, total_gain, total_gain_pct
    - [ ] 3.1.4 Columns: portfolio_beta, portfolio_volatility, num_positions, snapshot_data (JSON), created_at
    - [ ] 3.1.5 Create position_snapshots table
    - [ ] 3.1.6 Columns: id, snapshot_date (FK), symbol, shares, cost_basis, current_price, market_value
    - [ ] 3.1.7 Columns: gain_pct, weight_pct, sector, created_at
    - [ ] 3.1.8 Add indexes: idx_snapshots_date, idx_position_snapshots_date, idx_position_snapshots_symbol
  - [ ] 3.2 Create snapshot data models
    - [ ] 3.2.1 Edit `backend/app/portfolio/models.py`
    - [ ] 3.2.2 Create PortfolioSnapshot model (matches portfolio_snapshots schema)
    - [ ] 3.2.3 Create PositionSnapshot model (matches position_snapshots schema)
    - [ ] 3.2.4 Add type hints and Pydantic validation
  - [ ] 3.3 Implement snapshot creation logic
    - [ ] 3.3.1 Create `backend/app/jobs/snapshot_scheduler.py`
    - [ ] 3.3.2 Implement `create_daily_snapshot(storage: DuckDBStorage) -> str`
    - [ ] 3.3.3 Query portfolio_positions for all positions
    - [ ] 3.3.4 Fetch current prices for all symbols (use PriceDataFetcher)
    - [ ] 3.3.5 Calculate portfolio analytics (reuse PortfolioAnalytics class)
    - [ ] 3.3.6 Create PortfolioSnapshot record
    - [ ] 3.3.7 Create PositionSnapshot records for each position
    - [ ] 3.3.8 Insert both into database (transaction)
    - [ ] 3.3.9 Return snapshot_id
  - [ ] 3.4 Create Celery periodic task
    - [ ] 3.4.1 In `snapshot_scheduler.py`, define `@celery_app.task def daily_portfolio_snapshot()`
    - [ ] 3.4.2 Call create_daily_snapshot()
    - [ ] 3.4.3 Log success/failure with structured logging
    - [ ] 3.4.4 Configure Celery beat schedule: run at 4:30 PM ET (after market close)
    - [ ] 3.4.5 Add to `backend/app/celery_app.py` beat_schedule config
  - [ ] 3.5 Add snapshot storage methods
    - [ ] 3.5.1 Edit `backend/app/storage/facade.py`
    - [ ] 3.5.2 Method: `insert_portfolio_snapshot(snapshot: PortfolioSnapshot) -> None`
    - [ ] 3.5.3 Method: `insert_position_snapshots(snapshots: list[PositionSnapshot]) -> None`
    - [ ] 3.5.4 Method: `get_portfolio_snapshots(start_date: date, end_date: date) -> list[PortfolioSnapshot]`
    - [ ] 3.5.5 Method: `get_position_snapshots(snapshot_date: date) -> list[PositionSnapshot]`
    - [ ] 3.5.6 Use parameterized queries
  - [ ] 3.6 Add snapshot cleanup job
    - [ ] 3.6.1 In `snapshot_scheduler.py`, define `@celery_app.task def cleanup_old_snapshots()`
    - [ ] 3.6.2 Delete snapshots older than 2 years
    - [ ] 3.6.3 Schedule to run weekly (Sunday midnight)
  - [ ] 3.7 Write snapshot tests
    - [ ] 3.7.1 Create `backend/tests/test_snapshot_scheduler.py`
    - [ ] 3.7.2 Test create_daily_snapshot() with mock positions
    - [ ] 3.7.3 Test snapshot includes all analytics (beta, volatility, sector)
    - [ ] 3.7.4 Test position snapshots created for each position
    - [ ] 3.7.5 Test snapshot retrieval by date range
    - [ ] 3.7.6 Test cleanup job (delete old snapshots)

- [ ] **4.0 Build Historical Analytics Engine** (~4 hours)
  - [ ] 4.1 Create HistoricalAnalytics class
    - [ ] 4.1.1 Create `backend/app/analytics/historical.py`
    - [ ] 4.1.2 Create `HistoricalAnalytics` class with storage dependency
    - [ ] 4.1.3 Method: `get_portfolio_value_over_time(start: date, end: date) -> list[tuple[date, float]]`
    - [ ] 4.1.4 Query portfolio_snapshots, return (date, total_value) tuples
    - [ ] 4.1.5 Method: `calculate_cumulative_return(start: date, end: date) -> float`
    - [ ] 4.1.6 Formula: (end_value - start_value) / start_value * 100
  - [ ] 4.2 Implement time-series metrics
    - [ ] 4.2.1 Method: `calculate_annualized_return(start: date, end: date) -> float`
    - [ ] 4.2.2 Get start_value and end_value from snapshots
    - [ ] 4.2.3 Calculate days = (end - start).days
    - [ ] 4.2.4 Formula: ((end_value / start_value) ^ (365 / days)) - 1
    - [ ] 4.2.5 Method: `calculate_volatility(start: date, end: date) -> float`
    - [ ] 4.2.6 Calculate daily returns from snapshots
    - [ ] 4.2.7 Return standard deviation of daily returns (annualized)
  - [ ] 4.3 Implement risk-adjusted metrics
    - [ ] 4.3.1 Method: `calculate_sharpe_ratio(start: date, end: date, risk_free_rate: float) -> float`
    - [ ] 4.3.2 Get annualized return and volatility
    - [ ] 4.3.3 Formula: (annualized_return - risk_free_rate) / volatility
    - [ ] 4.3.4 Method: `calculate_max_drawdown(start: date, end: date) -> tuple[float, date, date]`
    - [ ] 4.3.5 Find largest peak-to-trough decline in portfolio value
    - [ ] 4.3.6 Return (drawdown_pct, peak_date, trough_date)
    - [ ] 4.3.7 Method: `calculate_sortino_ratio(start: date, end: date, risk_free_rate: float) -> float`
    - [ ] 4.3.8 Calculate downside deviation (only negative returns)
    - [ ] 4.3.9 Formula: (annualized_return - risk_free_rate) / downside_deviation
  - [ ] 4.4 Implement benchmark comparison
    - [ ] 4.4.1 Method: `compare_to_benchmark(start: date, end: date, benchmark: str = "SPY") -> dict`
    - [ ] 4.4.2 Fetch SPY historical prices for date range
    - [ ] 4.4.3 Calculate SPY cumulative return
    - [ ] 4.4.4 Calculate alpha: portfolio_return - benchmark_return
    - [ ] 4.4.5 Calculate beta: covariance(portfolio, benchmark) / variance(benchmark)
    - [ ] 4.4.6 Return dict with alpha, beta, portfolio_return, benchmark_return
  - [ ] 4.5 Implement rolling metrics
    - [ ] 4.5.1 Method: `calculate_rolling_returns(start: date, end: date, window_days: int) -> list[tuple[date, float]]`
    - [ ] 4.5.2 Calculate return for each N-day window
    - [ ] 4.5.3 Return list of (date, rolling_return) tuples
    - [ ] 4.5.4 Support windows: 7, 30, 90 days
  - [ ] 4.6 Add historical analytics API endpoints
    - [ ] 4.6.1 Edit `backend/app/api/analytics.py`
    - [ ] 4.6.2 Endpoint: `GET /api/portfolio/history?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
    - [ ] 4.6.3 Return portfolio snapshots for date range
    - [ ] 4.6.4 Endpoint: `GET /api/portfolio/analytics/historical?period={7d|30d|90d|1y|all}`
    - [ ] 4.6.5 Calculate and return: Sharpe ratio, max drawdown, volatility, annualized return
    - [ ] 4.6.6 Endpoint: `GET /api/portfolio/performance?compare_to=SPY`
    - [ ] 4.6.7 Return benchmark comparison (alpha, beta, returns)
    - [ ] 4.6.8 Endpoint: `GET /api/portfolio/export?format={csv|json}&start_date=YYYY-MM-DD`
    - [ ] 4.6.9 Export snapshots as CSV or JSON for external analysis
  - [ ] 4.7 Write historical analytics tests
    - [ ] 4.7.1 Create `backend/tests/test_historical_analytics.py`
    - [ ] 4.7.2 Test cumulative return calculation
    - [ ] 4.7.3 Test annualized return calculation
    - [ ] 4.7.4 Test Sharpe ratio calculation (mock risk-free rate)
    - [ ] 4.7.5 Test max drawdown calculation
    - [ ] 4.7.6 Test benchmark comparison (mock SPY data)
    - [ ] 4.7.7 Test rolling returns (30-day window)
    - [ ] 4.7.8 Test API endpoints with mock snapshot data

- [ ] **5.0 Create Frontend Visualization & Charts** (~4 hours)
  - [ ] 5.1 Create Performance tab page
    - [ ] 5.1.1 Create `frontend/app/portfolio/performance/page.tsx`
    - [ ] 5.1.2 Add tab navigation to portfolio page (Overview, Positions, Performance)
    - [ ] 5.1.3 Edit `frontend/app/portfolio/page.tsx` to add "Performance" tab link
    - [ ] 5.1.4 Create layout with metrics summary + charts
    - [ ] 5.1.5 Add time period selector: 7D, 30D, 90D, 1Y, ALL (buttons)
    - [ ] 5.1.6 Add "Export Data" button (download CSV)
  - [ ] 5.2 Create React Query hooks
    - [ ] 5.2.1 Create `frontend/lib/hooks/useHistoricalAnalytics.ts`
    - [ ] 5.2.2 Hook: `usePortfolioHistory(startDate, endDate)` - fetches snapshots
    - [ ] 5.2.3 Hook: `useHistoricalMetrics(period)` - fetches Sharpe, drawdown, etc.
    - [ ] 5.2.4 Hook: `useBenchmarkComparison(period)` - fetches alpha, beta vs SPY
    - [ ] 5.2.5 Create `frontend/lib/hooks/useBacktest.ts`
    - [ ] 5.2.6 Hook: `useRunBacktest(ideaId)` - mutation to run backtest
    - [ ] 5.2.7 Hook: `useBacktestHistory(ideaId)` - fetches backtest runs
  - [ ] 5.3 Add API functions
    - [ ] 5.3.1 Edit `frontend/lib/api.ts`
    - [ ] 5.3.2 Function: `fetchPortfolioHistory(startDate, endDate)`
    - [ ] 5.3.3 Function: `fetchHistoricalMetrics(period)`
    - [ ] 5.3.4 Function: `fetchBenchmarkComparison(period)`
    - [ ] 5.3.5 Function: `runBacktest(ideaId, startDate, endDate)`
    - [ ] 5.3.6 Function: `fetchBacktestHistory(ideaId)`
    - [ ] 5.3.7 Function: `exportPortfolioData(format, startDate, endDate)`
  - [ ] 5.4 Create metrics summary component
    - [ ] 5.4.1 Create `frontend/components/analytics/MetricsSummary.tsx`
    - [ ] 5.4.2 Display card grid with 6 metrics:
      - [ ] 5.4.2.1 Total Return (%, $ gain) with color coding
      - [ ] 5.4.2.2 Annualized Return (%)
      - [ ] 5.4.2.3 Sharpe Ratio with tooltip explanation
      - [ ] 5.4.2.4 Max Drawdown (%, date range)
      - [ ] 5.4.2.5 Current Beta
      - [ ] 5.4.2.6 Current Volatility (%)
    - [ ] 5.4.3 Use shadcn/ui Card components
    - [ ] 5.4.4 Add loading skeletons
  - [ ] 5.5 Create portfolio value chart
    - [ ] 5.5.1 Create `frontend/components/analytics/PerformanceChart.tsx`
    - [ ] 5.5.2 Use Recharts LineChart component
    - [ ] 5.5.3 X-axis: Date, Y-axis: Portfolio value ($)
    - [ ] 5.5.4 Line: Portfolio value over time (blue)
    - [ ] 5.5.5 Optional line: SPY benchmark overlay (gray, dashed)
    - [ ] 5.5.6 Add tooltip with date, value, gain %
    - [ ] 5.5.7 Add responsive container (height: 400px)
    - [ ] 5.5.8 Format currency values with commas
  - [ ] 5.6 Create sector exposure chart
    - [ ] 5.6.1 Create `frontend/components/analytics/SectorExposureChart.tsx`
    - [ ] 5.6.2 Use Recharts AreaChart component (stacked)
    - [ ] 5.6.3 X-axis: Date, Y-axis: % of portfolio
    - [ ] 5.6.4 Stacked areas for each sector (Technology, Healthcare, Finance, etc.)
    - [ ] 5.6.5 Different color per sector (use consistent palette)
    - [ ] 5.6.6 Add legend
    - [ ] 5.6.7 Add tooltip showing sector % on hover
  - [ ] 5.7 Create drawdown chart
    - [ ] 5.7.1 Create `frontend/components/analytics/DrawdownChart.tsx`
    - [ ] 5.7.2 Use Recharts AreaChart component
    - [ ] 5.7.3 X-axis: Date, Y-axis: Drawdown (%)
    - [ ] 5.7.4 Fill area below zero (red gradient)
    - [ ] 5.7.5 Highlight max drawdown period (darker red)
    - [ ] 5.7.6 Add reference line at 0%
    - [ ] 5.7.7 Add tooltip with date and drawdown %
  - [ ] 5.8 Create backtest results component
    - [ ] 5.8.1 Create `frontend/components/ideas/BacktestResults.tsx`
    - [ ] 5.8.2 Add "Backtest Idea" button on idea details page
    - [ ] 5.8.3 Show backtest form: date range selector (default: last 90 days)
    - [ ] 5.8.4 Display backtest results:
      - [ ] 5.8.4.1 Win/Loss badge (green/red)
      - [ ] 5.8.4.2 Total return % with color coding
      - [ ] 5.8.4.3 Holding period (days vs target)
      - [ ] 5.8.4.4 Max drawdown %
      - [ ] 5.8.4.5 Risk-adjusted return
    - [ ] 5.8.5 Show price chart during backtest period with entry/exit markers
    - [ ] 5.8.6 Display historical backtest runs table
  - [ ] 5.9 Add export functionality
    - [ ] 5.9.1 Edit `frontend/app/portfolio/performance/page.tsx`
    - [ ] 5.9.2 Add "Export Data" button
    - [ ] 5.9.3 On click, call `exportPortfolioData("csv", startDate, endDate)`
    - [ ] 5.9.4 Trigger CSV download in browser
    - [ ] 5.9.5 Include columns: date, value, gain_pct, beta, volatility
  - [ ] 5.10 Update documentation
    - [ ] 5.10.1 Edit `docs/core/API_REFERENCE.md`
    - [ ] 5.10.2 Document all backtest endpoints with examples
    - [ ] 5.10.3 Document all historical analytics endpoints
    - [ ] 5.10.4 Add example request/response for each endpoint
    - [ ] 5.10.5 Create `docs/guides/backtesting.md`
    - [ ] 5.10.6 Explain how to interpret backtest results (win rate, risk-adjusted return)
    - [ ] 5.10.7 Create `docs/guides/performance-tracking.md`
    - [ ] 5.10.8 Explain Sharpe ratio, max drawdown, alpha/beta

---

## Verification & Production Readiness

**MANDATORY before marking task "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All PRD requirements implemented (backtesting + historical tracking)
  - [ ] All user stories satisfied (backtest ideas, view performance, compare to SPY)
  - [ ] Integration points working correctly (Celery snapshots, historical data, charts)
  - [ ] Zero known bugs or regressions

- [ ] **Test Coverage** (target: 80%+)
  - [ ] Unit tests for BacktestEngine (trade simulation, metrics calculation)
  - [ ] Unit tests for HistoricalAnalytics (Sharpe, drawdown, benchmark comparison)
  - [ ] Integration tests for snapshot scheduler
  - [ ] End-to-end test: Create idea → Backtest → View results
  - [ ] End-to-end test: Create positions → Snapshot → View performance chart
  - [ ] All tests passing: `pytest tests/ -v`
  - [ ] Coverage verified: `pytest tests/ --cov=app --cov-report=term-missing`

- [ ] **Type Safety & Code Quality**
  - [ ] 100% type hints on all analytics functions: `mypy app/ --strict` passes
  - [ ] Linting passes: `scripts/lint.sh` returns zero errors
  - [ ] Code formatting applied: `ruff format app/`
  - [ ] Complexity limits met (functions <50 lines, complexity <10)

- [ ] **Documentation**
  - [ ] All analytics functions have docstrings with examples
  - [ ] API_REFERENCE.md updated with backtest and historical endpoints
  - [ ] User guides created (backtesting.md, performance-tracking.md)
  - [ ] Metric explanations (Sharpe ratio, max drawdown) documented

- [ ] **Security & Performance**
  - [ ] SQL queries use parameterized placeholders (no f-strings with user input)
  - [ ] Backtest execution limited to 1-year lookback (prevent long queries)
  - [ ] Snapshot creation < 30 seconds (fast enough for daily job)
  - [ ] Historical data cached (24-hour TTL)
  - [ ] Chart rendering < 2 seconds for 90-day data

- [ ] **Operational Readiness**
  - [ ] Daily snapshot job configured in Celery beat (4:30 PM ET)
  - [ ] Historical price update job configured (5:00 PM ET)
  - [ ] Snapshot cleanup job configured (weekly)
  - [ ] Structured logging for all backtest runs
  - [ ] Error handling for missing historical data
  - [ ] Manual end-to-end test: Backtest idea with real data
  - [ ] Manual end-to-end test: View 90-day performance chart
  - [ ] REFACTOR_STATUS.md updated (mark features complete)

**See**: `docs/core/DEVELOPMENT.md` → "Production Readiness Requirements" for complete checklist

---

## Notes

- **Dependencies**: Requires PRD #0010 features (Celery, structured logging, multi-source) to be complete
- **Implementation order**: Follow task order 1.0 → 2.0 → 3.0 → 4.0 → 5.0
- **Testing**: Run tests after each task: `pytest tests/ -v`
- **Historical data**: yfinance provides 10+ years of free historical data
- **Celery beat**: Configure in `backend/app/celery_app.py` beat_schedule
- **Frontend charts**: Use Recharts library (already in Next.js ecosystem)
- **Performance**: Limit backtest lookback to 1 year to avoid slow queries
- **Data quality**: Cross-validate historical prices with multi-source if available
- **Total effort**: ~20 hours (4+6+4+4+4) across all 5 tasks
