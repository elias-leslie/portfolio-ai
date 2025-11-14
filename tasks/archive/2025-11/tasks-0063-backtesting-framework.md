# Task List: Backtesting Framework

**Source**: User request via /task_it
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev
**Created**: 2025-11-14 00:30

---

## Summary

**Goal**: Build backtesting framework that validates trading strategies using historical data. Primary purpose: Validate gap fills (Task 0062), test agent ideas before deployment, and measure strategy edge (Sharpe ratio, win rate, drawdown). Two-phase approach: Quick MVP for vacation testing (3-5 days) + Full production framework after vacation (3-4 weeks).

**Approach**:
- **Phase A (Quick MVP)**: Simple date loop replay engine, reuse existing signal_classifier, track equity curve and performance metrics, single-symbol backtests, store results in new `backtest_runs` table, basic API endpoint
- **Phase B (Full Framework)**: Multi-symbol portfolio backtesting, walk-forward validation, parameter optimization, realistic slippage/commission modeling, benchmark comparison, visualization, strategy library with templates

**Scope Discovery**: Required (understand data sources, performance calculation patterns, storage design)

**Infrastructure Reuse** (70% exists):
- ✅ `day_bars` table: 10,103 rows, 39 symbols, 259 trading days (2024-10-28 to 2025-11-13)
- ✅ Signal classification: `backend/app/watchlist/signal_classifier.py` (BUY/HOLD/AVOID logic)
- ✅ Performance calcs: `backend/app/portfolio/analytics_risk.py` (Sharpe ratio, returns)
- ✅ Indicator engine: `backend/app/analytics/indicators.py` (RSI, MACD, BBands, EMAs, ATR)
- ✅ Paper trading: `backend/app/analytics/paper_trading*.py` (order tracking, portfolio updates)

**Missing** (30% to build):
- ❌ Event-driven replay engine (date loop + state management)
- ❌ Portfolio snapshot tracking (holdings, cash, equity curve)
- ❌ Backtest result storage (`backtest_runs`, `backtest_trades`, `backtest_equity`)
- ❌ Benchmark comparison (SPY buy-and-hold)
- ❌ Walk-forward validation framework
- ❌ Parameter optimization infrastructure

**Dependencies**:
- **Task 0062** (Gap Detection): Backtesting validates gap fill effectiveness (GAP-019 identified backtesting as prerequisite)
- **Task 0060** (CLI Agents): Agents will use backtesting for idea validation before live deployment
- **Task 0064** (Paper Trading): Shares portfolio state tracking logic (can extract common code)

**Autonomous Behavior & Agent Integration**:
- **Agent Usage**: Agents will autonomously run backtests to validate strategies before paper trading
- **API Integration**: Agents call `POST /api/backtest` with strategy parameters, receive results
- **Resource Limits**:
  - Max backtest duration: 5 minutes per run (timeout protection)
  - Max date range: 252 trading days (1 year) for Phase A
  - Max concurrent backtests: 3 (prevent resource exhaustion)
- **Result Storage**: All backtest results stored in `backtest_runs` table with agent_run_id foreign key
- **Failure Handling**: If backtest fails (insufficient data, timeout, error), agent logs failure and continues with next strategy
- **Performance Thresholds**: Agents should only paper trade strategies with:
  - Sharpe ratio > 0.5 (positive risk-adjusted returns)
  - Win rate > 45% (more wins than losses)
  - Max drawdown < 25% (acceptable risk)
- **Validation Workflow**: Backtest → Review metrics → If pass thresholds → Paper trade → Monitor

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [x] 0.1 Run Explore subagent in "medium" mode ✅ COMPLETE
  - **Findings:** No existing backtest infrastructure
  - **Strategy patterns:** signal_classifier.py with BUY/HOLD/AVOID logic exists
  - **Result storage:** idea_outcomes table pattern can be reused
  - **Recommendation:** Build new backend/app/backtest/ module, reuse existing components
- [x] 0.2 Analyze data availability for backtesting ✅ COMPLETE
  - **day_bars coverage:** 259 trading days (2024-10-28 to 2025-11-13), 39 symbols, 10,103 rows
  - **Indicator performance:** 299ms per symbol (fast enough, ~3 symbols/second)
  - **Fundamental data:** News sentiment only 8 days (exclude from MVP), earnings via API (defer to Phase B)
  - **Data coverage matrix:** Can backtest technical indicators reliably (RSI, MACD, EMA, volume)
- [x] 0.3 Review existing performance calculation patterns ✅ COMPLETE
  - **analytics_risk.py:** calculate_sharpe_ratio() - reusable for risk-adjusted returns
  - **paper_trading_portfolio.py:** calculate_trade_return(), update_trade_excursions(), check_exit_conditions() - reusable for trade lifecycle
  - **agent_performance.py:** get_agent_performance(), _calculate_win_loss_metrics() - reusable for backtest results
  - **Code reuse:** 60% of logic exists (trade lifecycle, performance metrics, signals)
- [x] 0.4 Update this task list with findings ✅ COMPLETE
  - **Implementation notes:** Create backend/app/backtest/ with engine.py, strategy.py, results.py, models.py, storage.py
  - **Effort estimate:** MEDIUM complexity unchanged (40% new code, 60% reuse)
  - **No blockers:** Data sufficient, indicators fast, clear architecture path
- [x] 0.5 Checkpoint: Confirm scope before proceeding ✅ COMPLETE
  - **Data coverage:** 259 trading days sufficient, technical indicators only for MVP
  - **Reusable components:** 60% (trade lifecycle, performance metrics, signal classifier)
  - **Estimated MVP complexity:** MEDIUM (3-5 days Phase A)
  - **Estimated full framework complexity:** HIGH (3-4 weeks Phase B)

---

### PHASE A: QUICK MVP (3-5 Days) - Functional Before Vacation

**Goal**: Working backtest system that validates basic strategies and runs during vacation. Focus: Simple, correct, complete.

---

### 1.0 Design Phase A Backtesting Architecture

- [ ] 1.1 Define MVP backtest data model
  - `backtest_runs` table: id, strategy_name, symbol, start_date, end_date, initial_capital, final_equity, sharpe_ratio, max_drawdown, win_rate, num_trades, status, created_at
  - `backtest_trades` table: id, run_id, symbol, entry_date, entry_price, exit_date, exit_price, shares, pnl, pnl_pct, exit_reason (target/stop/signal/time), created_at
  - `backtest_equity` table: id, run_id, date, equity, cash, position_value, drawdown_pct
  - Design principle: Simple tables, denormalized for query speed
- [ ] 1.2 Design simple strategy interface
  - Strategy protocol: `should_enter(symbol, date, indicators) -> bool`, `should_exit(position, date, indicators) -> bool`
  - Signal-based strategy: Reuse `classify_signal()` from `signal_classifier.py`
  - Position sizing: Fixed dollar amount or fixed shares (no Kelly criterion yet)
  - Exit rules: Target price (from signal), stop loss (2xATR), max holding period (60 days)
- [ ] 1.3 Design replay engine flow
  - Date loop: Iterate through trading days in `day_bars` (chronological order)
  - For each date: Fetch OHLCV + calculate indicators → Check entry signals → Check exit signals → Update portfolio state → Record equity
  - Portfolio state: `{cash: float, positions: dict[symbol, {shares, entry_price, entry_date}]}`
  - Simplifications for MVP: Single symbol per backtest, no slippage, use closing prices only
- [ ] 1.4 Define MVP performance metrics
  - Total return: `(final_equity - initial_capital) / initial_capital * 100`
  - Sharpe ratio: Use existing `analytics_risk.py:calculate_sharpe_ratio()` (annualized)
  - Max drawdown: `max((peak_equity - current_equity) / peak_equity)` during run
  - Win rate: `winning_trades / total_trades * 100`
  - Average win/loss: Mean PnL of winning vs losing trades
- [ ] 1.5 Document Phase A limitations
  - Single symbol per backtest (no portfolio/correlation effects)
  - No slippage or commission modeling
  - No benchmark comparison (SPY)
  - Limited to signal-based strategy (no custom strategies yet)
  - No walk-forward validation or parameter optimization
  - Frontend: API only, no UI visualization

---

### 2.0 Phase A Database Schema

- [ ] 2.1 Create migration `backend/migrations/XXX_backtest_tables.sql`
  - Create `backtest_runs` table with proper indexes (status, created_at)
  - Create `backtest_trades` table with foreign key to `backtest_runs`, indexes on (run_id, entry_date)
  - Create `backtest_equity` table with foreign key to `backtest_runs`, indexes on (run_id, date)
  - Add constraints: CHECK status IN ('pending', 'running', 'completed', 'failed')
- [ ] 2.2 Add table registry entries
  - Update `migrations/007_populate_table_registry.sql` for new tables
  - Document table purposes in registry
- [ ] 2.3 Create Pydantic models in `backend/app/backtest/models.py`
  - `BacktestRun`: All fields from `backtest_runs` table
  - `BacktestTrade`: All fields from `backtest_trades` table
  - `BacktestEquity`: All fields from `backtest_equity` table
  - `BacktestResult`: Summary model for API responses (run + metrics + trades)
  - `StrategyConfig`: Configuration for signal-based strategy (entry/exit thresholds)
- [ ] 2.4 Run migration and verify schema
  - Apply migration to `portfolio_ai` database
  - Apply migration to `portfolio_ai_test` database
  - Verify foreign key constraints work (insert test data)

---

### 3.0 Phase A Core Backtesting Engine

- [ ] 3.1 Create `backend/app/backtest/replay.py` - Event replay engine
  - `class BacktestState`: Track cash, positions, equity curve, trade history
  - `def get_trading_days(storage, symbol, start_date, end_date) -> list[date]`: Query `day_bars` for chronological dates
  - `def replay_backtest(storage, run_id, symbol, start_date, end_date, initial_capital, strategy) -> BacktestResult`: Main replay loop
  - Replay loop logic:
    ```python
    state = BacktestState(cash=initial_capital)
    for date in trading_days:
        ohlcv = fetch_day_bars(symbol, date)
        indicators = calculate_indicators(symbol, date)
        
        # Check exits first (for existing positions)
        for position in state.positions:
            if strategy.should_exit(position, date, indicators, ohlcv):
                exit_trade(state, position, date, ohlcv.close)
        
        # Check entries (if no position)
        if not state.has_position(symbol):
            if strategy.should_enter(symbol, date, indicators, ohlcv):
                enter_trade(state, symbol, date, ohlcv.close, position_size)
        
        # Update equity curve
        record_equity(state, date, ohlcv)
    ```
- [ ] 3.2 Create `backend/app/backtest/strategies.py` - Strategy implementations
  - `class Strategy(Protocol)`: Interface with `should_enter()`, `should_exit()`
  - `class SignalStrategy(Strategy)`: Reuse `classify_signal()` from `signal_classifier.py`
    - Entry: `classify_signal()` returns BUY with strength >= 7
    - Exit: Target hit (from signal classification), stop loss (entry - 2xATR), AVOID signal, or max holding days
    - Use `calculate_indicators()` from `analytics/indicators.py`
  - `def calculate_position_size(cash, price, sizing_method) -> int`: Fixed dollar or fixed shares
- [ ] 3.3 Create `backend/app/backtest/metrics.py` - Performance calculations
  - `def calculate_total_return(initial_capital, final_equity) -> float`
  - `def calculate_max_drawdown(equity_curve: list[float]) -> float`: Peak-to-trough
  - `def calculate_sharpe_ratio(equity_curve: list[float], risk_free_rate=0.045) -> float`: Reuse `analytics_risk.py` logic
  - `def calculate_win_rate(trades: list[BacktestTrade]) -> float`
  - `def calculate_average_win_loss(trades: list[BacktestTrade]) -> tuple[float, float]`
  - `def calculate_profit_factor(trades: list[BacktestTrade]) -> float`: Sum(wins) / Sum(losses)
- [ ] 3.4 Create `backend/app/backtest/storage.py` - Database operations
  - `def create_backtest_run(storage, ...) -> str`: Insert into `backtest_runs`, return run_id
  - `def save_backtest_trade(storage, run_id, trade) -> None`: Insert into `backtest_trades`
  - `def save_equity_snapshot(storage, run_id, date, equity, cash, position_value) -> None`: Insert into `backtest_equity`
  - `def update_backtest_result(storage, run_id, metrics) -> None`: Update `backtest_runs` with final metrics
  - `def get_backtest_run(storage, run_id) -> BacktestRun | None`
  - `def get_backtest_trades(storage, run_id) -> list[BacktestTrade]`
  - `def get_backtest_equity_curve(storage, run_id) -> list[BacktestEquity]`
  - `def list_backtest_runs(storage, limit=50) -> list[BacktestRun]`

---

### 4.0 Phase A API Endpoints

- [ ] 4.1 Create `backend/app/api/backtest.py` router
  - `POST /api/backtest/run` - Start backtest (returns run_id + task_id)
    - Request: `{symbol, start_date, end_date, initial_capital, strategy_name, strategy_config}`
    - Response: `{run_id, task_id, status: "pending"}`
    - Launch Celery task (don't block HTTP request)
  - `GET /api/backtest/runs` - List backtest runs (with pagination)
    - Response: `[{run_id, symbol, start_date, end_date, sharpe_ratio, status, created_at}, ...]`
  - `GET /api/backtest/runs/{run_id}` - Get backtest details
    - Response: `{run: {...}, metrics: {...}, trades: [...], equity_curve: [...]}`
  - `GET /api/backtest/runs/{run_id}/equity` - Get equity curve (for charting)
    - Response: `[{date, equity, cash, position_value, drawdown_pct}, ...]`
  - `DELETE /api/backtest/runs/{run_id}` - Delete backtest run
- [ ] 4.2 Create Celery task `backend/app/tasks/backtest_tasks.py`
  - `@celery_app.task def run_backtest(run_id: str, symbol: str, ...) -> dict`: Execute replay engine
  - Update `backtest_runs.status`: pending → running → completed/failed
  - Catch exceptions and mark status='failed' with error message
  - Log start/end times and performance metrics
- [ ] 4.3 Register router in `backend/app/main.py`
  - Add `app.include_router(backtest.router)` after other routers
- [ ] 4.4 Write API integration tests `backend/tests/integration/api/test_backtest_api.py`
  - Test POST /backtest/run with valid parameters
  - Test GET /backtest/runs pagination
  - Test GET /backtest/runs/{run_id} with completed run
  - Test 404 handling for non-existent run_id
  - Test DELETE /backtest/runs/{run_id}

---

### 5.0 Phase A Testing & Validation

- [ ] 5.1 Write unit tests `backend/tests/unit/backtest/`
  - `test_replay.py`: Test BacktestState, trading day queries, replay loop logic
  - `test_strategies.py`: Test SignalStrategy entry/exit logic with mock indicators
  - `test_metrics.py`: Test performance calculations with known equity curves
  - `test_storage.py`: Test database operations with test fixtures
- [ ] 5.2 Write integration tests `backend/tests/integration/backtest/`
  - `test_backtest_end_to_end.py`: Run complete backtest on real `day_bars` data (AAPL)
    - Verify backtest_runs record created
    - Verify trades recorded in backtest_trades
    - Verify equity curve in backtest_equity
    - Verify metrics calculated correctly (Sharpe, drawdown, win rate)
  - `test_backtest_edge_cases.py`: Test insufficient data, invalid dates, zero capital
- [ ] 5.3 Manual validation backtest
  - Run backtest on AAPL: 2024-10-28 to 2025-11-13, $10,000 capital, SignalStrategy
  - Manually verify 3 random trades (entry/exit prices, PnL)
  - Verify equity curve matches expected (spot check 5 dates)
  - Verify Sharpe ratio calculation (compare to manual calculation)
  - Document results in `docs/validation/backtest-mvp-validation.md`
- [ ] 5.4 Run smoke test on all watchlist symbols
  - Backtest each symbol in `day_bars` (39 symbols)
  - Collect metrics: Average Sharpe, average win rate, total trades
  - Identify best/worst performing symbols for SignalStrategy
  - Document in `docs/validation/backtest-mvp-smoke-test.md`
- [ ] 5.5 Quality checks
  - Run `~/portfolio-ai/scripts/lint.sh` (ruff + mypy)
  - Run `cd ~/portfolio-ai/backend && pytest tests/unit/backtest/ tests/integration/backtest/ -v`
  - Verify test coverage >80% for backtest module: `pytest --cov=app.backtest tests/`
  - Check file sizes: All modules <500 lines (split if needed)

---

### 6.0 Phase A Documentation

- [ ] 6.1 Create `docs/backtesting/README.md` - User guide
  - What is backtesting and why it matters
  - How to run a backtest (API examples with curl)
  - How to interpret results (Sharpe, drawdown, win rate)
  - Limitations of Phase A MVP
  - Example: Backtest AAPL signal strategy
- [ ] 6.2 Create `docs/backtesting/ARCHITECTURE.md` - Technical design
  - System architecture diagram
  - Replay engine flow (date loop, state management)
  - Strategy interface design
  - Database schema documentation
  - Performance metric formulas
- [ ] 6.3 Update core documentation
  - Add backtesting section to `docs/core/ARCHITECTURE.md`
  - Add backtest API endpoints to `docs/core/API_REFERENCE.md`
  - Add Phase B roadmap to `docs/core/REFACTOR_STATUS.md`
- [ ] 6.4 Add inline code documentation
  - Docstrings for all public functions (Google style)
  - Type hints for all parameters and returns
  - Examples in docstrings for key functions (replay_backtest, calculate_metrics)

---

### 7.0 Phase A Deployment & Monitoring

- [ ] 7.1 Restart services after code changes
  - Run `bash ~/portfolio-ai/scripts/restart.sh`
  - Verify services started: `bash ~/portfolio-ai/scripts/status.sh`
  - Check backend logs: `tail -f /var/log/portfolio-ai/backend-error.log`
  - Check Celery logs: `tail -f /var/log/portfolio-ai/celery-worker.log`
- [ ] 7.2 Run production smoke test
  - POST /api/backtest/run for AAPL (via curl)
  - Wait for completion (poll status)
  - GET /api/backtest/runs/{run_id} and verify metrics
  - Check database: `SELECT * FROM backtest_runs LIMIT 1;`
- [ ] 7.3 Schedule nightly backtests (optional for vacation monitoring)
  - Add Celery beat task: Run backtests on top 10 watchlist symbols nightly
  - Store results in database (track strategy performance over time)
  - Alert if average Sharpe drops below threshold (strategy degradation detection)
- [ ] 7.4 Monitor during vacation
  - Check `/api/backtest/runs` weekly for new results
  - Verify no task failures in Celery logs
  - Collect data for Phase B prioritization

---

### PHASE B: FULL FRAMEWORK (3-4 Weeks) - Production After Vacation

**Goal**: Production-grade backtesting system with multi-symbol portfolios, walk-forward validation, parameter optimization, and UI visualization. Focus: Realistic, robust, professional.

---

### 8.0 Design Phase B Architecture Enhancements

- [ ] 8.1 Design multi-symbol portfolio backtesting
  - Portfolio state: `{cash, positions: {symbol: {shares, entry_price, entry_date}}, margin_used}`
  - Allocation strategy: Equal weight, risk parity, Kelly criterion, or custom
  - Rebalancing: Periodic (monthly) or signal-driven
  - Correlation handling: Use covariance matrix from GAP-020 (Task 0062)
- [ ] 8.2 Design walk-forward validation framework
  - Training window: 6 months (optimize parameters)
  - Testing window: 1 month (out-of-sample validation)
  - Rolling windows: Move forward 1 month, re-optimize, repeat
  - Metrics: Compare in-sample vs out-of-sample Sharpe (detect overfitting)
- [ ] 8.3 Design parameter optimization
  - Parameters: Entry threshold, exit threshold, stop loss multiple, holding period
  - Optimization method: Grid search (simple), Bayesian optimization (advanced)
  - Objective function: Sharpe ratio, Sortino ratio, or Calmar ratio
  - Overfitting prevention: Penalize too many trades, require minimum sample size
- [ ] 8.4 Design slippage and commission modeling
  - Slippage: Model as percentage of trade value (0.05% default) or fixed cents per share
  - Commission: $0 for Robinhood/Webull, $1 per trade for Interactive Brokers
  - Market impact: For large trades, model price impact (not MVP, defer)
- [ ] 8.5 Design benchmark comparison
  - Benchmark: SPY buy-and-hold (same date range, same initial capital)
  - Metrics: Alpha (excess return), beta, information ratio, tracking error
  - Visualization: Overlay strategy equity curve vs SPY

---

### 9.0 Phase B Database Schema Enhancements

- [ ] 9.1 Extend `backtest_runs` table
  - Add columns: `portfolio_symbols TEXT[]`, `allocation_method TEXT`, `rebalance_frequency TEXT`, `slippage_pct FLOAT`, `commission_per_trade FLOAT`, `benchmark_symbol TEXT`, `alpha FLOAT`, `beta FLOAT`, `information_ratio FLOAT`
- [ ] 9.2 Create `backtest_parameters` table
  - Schema: `run_id TEXT, param_name TEXT, param_value TEXT, PRIMARY KEY (run_id, param_name)`
  - Store optimization parameters for reproducibility
- [ ] 9.3 Create `backtest_portfolio_snapshots` table
  - Schema: `run_id TEXT, date DATE, holdings JSONB, cash FLOAT, equity FLOAT`
  - Track portfolio holdings over time (for multi-symbol backtests)
- [ ] 9.4 Create `backtest_optimization_results` table
  - Schema: `id TEXT PRIMARY KEY, base_run_id TEXT, param_grid JSONB, best_params JSONB, best_sharpe FLOAT, all_results JSONB, created_at TIMESTAMP`
  - Store parameter optimization results

---

### 10.0 Phase B Enhanced Backtesting Engine

- [ ] 10.1 Extend `backend/app/backtest/replay.py` for multi-symbol
  - Support multiple symbols in portfolio state
  - Fetch OHLCV for all symbols each day (batch query)
  - Allocate capital across symbols based on allocation strategy
  - Rebalance portfolio on schedule or signal change
- [ ] 10.2 Add slippage and commission to `backend/app/backtest/execution.py`
  - `def apply_slippage(price, direction, slippage_pct) -> float`: Buy pays +slippage, sell receives -slippage
  - `def apply_commission(trade_value, commission_per_trade) -> float`
  - Update `enter_trade()` and `exit_trade()` to include costs
- [ ] 10.3 Create `backend/app/backtest/optimization.py`
  - `def grid_search(storage, symbol, start_date, end_date, param_grid, objective) -> dict`: Try all parameter combinations, return best
  - `def walk_forward_validation(storage, symbol, full_date_range, train_window, test_window) -> list[dict]`: Rolling optimization + testing
  - `def detect_overfitting(in_sample_sharpe, out_of_sample_sharpe) -> bool`: Flag if out-of-sample degrades >30%
- [ ] 10.4 Create `backend/app/backtest/benchmark.py`
  - `def run_buy_and_hold_benchmark(storage, symbol, start_date, end_date, initial_capital) -> BacktestResult`: Simple buy-and-hold
  - `def calculate_alpha_beta(strategy_returns, benchmark_returns) -> tuple[float, float]`: Regression
  - `def calculate_information_ratio(strategy_returns, benchmark_returns) -> float`

---

### 11.0 Phase B Strategy Library

- [ ] 11.1 Create `backend/app/backtest/strategies/` directory
  - Move `SignalStrategy` to `strategies/signal_strategy.py`
- [ ] 11.2 Implement momentum strategy `strategies/momentum_strategy.py`
  - Entry: 60-day momentum > 80th percentile (cross-sectional)
  - Exit: 60-day momentum < 40th percentile or stop loss
  - Reuse multi-horizon momentum from GAP-012 (Task 0062)
- [ ] 11.3 Implement mean reversion strategy `strategies/mean_reversion_strategy.py`
  - Entry: RSI < 30 AND price < BBands lower
  - Exit: RSI > 50 OR price > BBands middle
  - Max holding: 10 days (mean reversion is short-term)
- [ ] 11.4 Implement sector rotation strategy `strategies/sector_rotation_strategy.py`
  - Entry: Sector ETF with highest 20-day momentum
  - Exit: Hold for 1 month, then rotate to new leader
  - Symbols: XLK (tech), XLF (finance), XLE (energy), XLV (healthcare), etc.
- [ ] 11.5 Create strategy registry `strategies/__init__.py`
  - `STRATEGY_REGISTRY = {"signal": SignalStrategy, "momentum": MomentumStrategy, ...}`
  - `def get_strategy(strategy_name: str) -> Strategy`

---

### 12.0 Phase B API Enhancements

- [ ] 12.1 Extend `backend/app/api/backtest.py`
  - `POST /api/backtest/run` - Add support for multi-symbol, slippage, commission, benchmark
  - `POST /api/backtest/optimize` - Run parameter optimization (returns optimization_id)
  - `GET /api/backtest/optimize/{optimization_id}` - Get optimization results
  - `POST /api/backtest/walk-forward` - Run walk-forward validation
  - `GET /api/backtest/strategies` - List available strategies from registry
  - `GET /api/backtest/runs/{run_id}/compare-benchmark` - Compare to SPY
- [ ] 12.2 Create Celery tasks for long-running operations
  - `@celery_app.task def run_optimization(...)`: Grid search or Bayesian optimization
  - `@celery_app.task def run_walk_forward(...)`: Multiple training/testing cycles
- [ ] 12.3 Add pagination to list endpoints
  - Support `?limit=50&offset=0` for `GET /api/backtest/runs`
  - Add total count in response: `{runs: [...], total: 123, limit: 50, offset: 0}`

---

### 13.0 Phase B Frontend Visualization

- [ ] 13.1 Create `frontend/app/backtest/page.tsx` - Backtesting page
  - Form: Select symbol, date range, strategy, initial capital
  - Button: "Run Backtest" (POST /api/backtest/run)
  - Results table: List recent backtests with key metrics (Sharpe, win rate, total return)
  - Click row → Navigate to detail page
- [ ] 13.2 Create `frontend/app/backtest/[runId]/page.tsx` - Backtest detail page
  - Header: Strategy name, symbol, date range, status
  - Metrics cards: Sharpe ratio, max drawdown, win rate, profit factor, total return
  - Equity curve chart: Recharts LineChart with strategy vs benchmark
  - Drawdown chart: Area chart showing drawdown over time
  - Trade table: Entry/exit dates, prices, PnL, exit reason (sortable, filterable)
- [ ] 13.3 Create `frontend/components/backtest/EquityCurveChart.tsx`
  - Recharts LineChart with dual lines: strategy equity, benchmark equity
  - Tooltip: Date, strategy equity, benchmark equity, relative performance
  - X-axis: Date (formatted)
  - Y-axis: Equity ($)
- [ ] 13.4 Create `frontend/components/backtest/DrawdownChart.tsx`
  - Recharts AreaChart showing drawdown percentage over time
  - Color: Red fill for drawdown
  - Highlight max drawdown point
- [ ] 13.5 Add React Query hooks `frontend/hooks/useBacktest.ts`
  - `useBacktestRuns()`: Fetch list of backtests
  - `useBacktestRun(runId)`: Fetch single backtest details
  - `useCreateBacktest(params)`: Mutation for POST /api/backtest/run
  - `useDeleteBacktest(runId)`: Mutation for DELETE /api/backtest/runs/{runId}

---

### 14.0 Phase B Testing & Validation

- [ ] 14.1 Write unit tests for new modules
  - `test_optimization.py`: Test grid search, walk-forward logic
  - `test_benchmark.py`: Test alpha/beta calculations
  - `test_execution.py`: Test slippage and commission application
  - `test_strategies/*.py`: Test each strategy (momentum, mean reversion, sector rotation)
- [ ] 14.2 Write integration tests
  - `test_multi_symbol_backtest.py`: Run backtest with 3 symbols, verify portfolio state
  - `test_optimization_end_to_end.py`: Run grid search, verify best params selected
  - `test_walk_forward_end_to_end.py`: Run walk-forward, verify in-sample vs out-of-sample
  - `test_benchmark_comparison.py`: Run strategy + benchmark, verify alpha/beta
- [ ] 14.3 Manual validation - Multi-symbol backtest
  - Run backtest on 5 symbols: AAPL, MSFT, GOOGL, AMZN, NVDA
  - Verify portfolio snapshots recorded
  - Verify trades for all 5 symbols
  - Verify final equity matches sum of positions + cash
- [ ] 14.4 Manual validation - Walk-forward validation
  - Run walk-forward on AAPL: 12-month period, 6-month train, 1-month test
  - Verify 6 test windows created
  - Compare in-sample vs out-of-sample Sharpe (expect degradation)
  - Document overfitting detection (if out-of-sample Sharpe <70% of in-sample)
- [ ] 14.5 Frontend E2E tests `frontend/tests/e2e/backtest.spec.ts`
  - Test: Create backtest via form
  - Test: View backtest detail page
  - Test: Equity curve chart renders
  - Test: Trade table pagination
  - Test: Delete backtest

---

### 15.0 Phase B Documentation

- [ ] 15.1 Update `docs/backtesting/README.md` with Phase B features
  - Multi-symbol portfolio backtesting examples
  - Walk-forward validation guide
  - Parameter optimization guide
  - Strategy library usage
- [ ] 15.2 Create `docs/backtesting/STRATEGIES.md`
  - Document each strategy: Entry/exit rules, parameters, expected use case
  - SignalStrategy, MomentumStrategy, MeanReversionStrategy, SectorRotationStrategy
  - How to add custom strategies
- [ ] 15.3 Create `docs/backtesting/OPTIMIZATION.md`
  - Parameter optimization best practices
  - Overfitting detection and prevention
  - Walk-forward validation methodology
  - Example: Optimize signal strategy thresholds
- [ ] 15.4 Create `docs/backtesting/BENCHMARK.md`
  - What is alpha and beta
  - How to interpret information ratio
  - Example: Compare momentum strategy vs SPY

---

### 16.0 Phase B Deployment & Monitoring

- [ ] 16.1 Restart services and deploy
  - Run `bash ~/portfolio-ai/scripts/restart.sh`
  - Verify services started: `bash ~/portfolio-ai/scripts/status.sh`
  - Check logs for errors
- [ ] 16.2 Run production smoke tests
  - Create multi-symbol backtest via UI
  - Run parameter optimization (small grid)
  - Run walk-forward validation (short date range)
  - Verify all results display correctly in UI
- [ ] 16.3 Performance optimization
  - Profile replay engine: Measure time per trading day
  - Optimize indicator calculations: Cache results if recalculating same date range
  - Database indexes: Ensure `day_bars(ticker, date)` index used efficiently
  - Target: <10 seconds for 250-day single-symbol backtest, <60 seconds for multi-symbol
- [ ] 16.4 Set up monitoring
  - Add Celery metrics: Track backtest task duration, failure rate
  - Add database metrics: Track `backtest_runs` table growth
  - Alert if backtest task fails >10% of time
  - Alert if backtest task takes >5 minutes (performance degradation)

---

### 17.0 Integration with Task 0062 (Gap Detection)

- [ ] 17.1 Create backtest validation tasks for gap fills
  - For each gap filled in Task 0062: Run "before" backtest (without gap data) + "after" backtest (with gap data)
  - Example: GAP-012 (multi-horizon momentum) → Compare single-day momentum strategy vs 60-day momentum strategy
  - Measure improvement: ΔSharpe ratio, Δwin rate, Δmax drawdown
- [ ] 17.2 Add gap fill validation to API
  - `POST /api/backtest/validate-gap-fill` - Run A/B test backtest
  - Request: `{gap_id, before_strategy, after_strategy, symbols, date_range}`
  - Response: `{before_metrics, after_metrics, improvement_pct, conclusion}`
- [ ] 17.3 Document gap fill validation results
  - Create `docs/gap-validation/` directory
  - For each gap: Document backtest results before/after (e.g., `GAP-012-momentum-validation.md`)
  - Summary table: Gap ID, Before Sharpe, After Sharpe, Improvement %, Validated? (Yes/No)

---

### 18.0 Integration with Task 0060 (CLI Agents)

- [ ] 18.1 Enable agents to run backtests
  - Agent tool: `run_backtest(symbol, strategy_name, date_range) -> BacktestResult`
  - Agent can validate ideas before recommending to user
  - Example: "I recommend buying AAPL based on momentum. I backtested this strategy on AAPL (Sharpe 1.8) and similar stocks (Sharpe 1.6). High confidence."
- [ ] 18.2 Add backtest results to agent context
  - When agent analyzes symbol: Include historical backtest performance if available
  - "AAPL: SignalStrategy Sharpe 1.4 over last 12 months (50 trades, 65% win rate)"
- [ ] 18.3 Create agent validation workflow
  - Agent generates idea → Runs backtest → If Sharpe <1.0, flags as low confidence → Explains why to user
  - Prevents agent from recommending strategies with no historical edge

---

### 19.0 Phase B Quality & Polish

- [ ] 19.1 Code quality checks
  - Run `~/portfolio-ai/scripts/lint.sh` (must pass)
  - Run mypy --strict on backtest module (must pass)
  - Check file sizes: Split any files >500 lines
  - Remove TODOs: Address or convert to issues
- [ ] 19.2 Test coverage verification
  - Run `pytest --cov=app.backtest tests/ --cov-report=term-missing`
  - Target: >85% coverage for backtest module
  - Focus on: Edge cases, error handling, state transitions
- [ ] 19.3 Performance benchmarks
  - Document backtest execution time for standard scenarios
  - Single-symbol, 250 days: <10 seconds
  - Multi-symbol (5 symbols), 250 days: <60 seconds
  - Walk-forward (12 months, 6 train/1 test): <5 minutes
  - Optimization (10x10 grid, 250 days): <10 minutes
- [ ] 19.4 Security review
  - No SQL injection: All queries use parameterized statements
  - No arbitrary code execution: Strategy names validated against registry
  - Rate limiting: Backtest API limited to 10 requests/minute per user
  - Resource limits: Backtest tasks timeout after 30 minutes

---

## Verification

**Phase A (Quick MVP)**:
- [ ] Functional: POST /api/backtest/run works, returns valid results
- [ ] Database: Tables created, data persisted correctly
- [ ] Tests: All unit + integration tests passing (`pytest tests/unit/backtest tests/integration/backtest -v`)
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy)
- [ ] Validation: Manual backtest on AAPL verified correct (equity curve, trades, metrics)
- [ ] Smoke test: All 39 watchlist symbols backtested successfully
- [ ] Services: `bash ~/portfolio-ai/scripts/restart.sh` succeeds, health endpoints green
- [ ] Documentation: README and ARCHITECTURE docs complete
- [ ] Ready for vacation: System runs nightly backtests autonomously

**Phase B (Full Framework)**:
- [ ] Functional: All Phase B endpoints work, UI pages render correctly
- [ ] Multi-symbol: Portfolio backtest with 5 symbols verified correct
- [ ] Walk-forward: In-sample vs out-of-sample comparison works
- [ ] Optimization: Grid search completes, best params selected correctly
- [ ] Benchmark: Alpha/beta calculated correctly vs SPY
- [ ] Strategies: All 4 strategies (signal, momentum, mean reversion, sector rotation) tested
- [ ] Tests: All tests passing, >85% coverage
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes, all files <500 lines
- [ ] Performance: 250-day single-symbol backtest <10 seconds
- [ ] Frontend: E2E tests passing (`npm run test:e2e`)
- [ ] Integration: Gap validation (Task 0062) and agent integration (Task 0060) complete
- [ ] Documentation: All Phase B docs complete (README, STRATEGIES, OPTIMIZATION, BENCHMARK)
- [ ] Production ready: System handles concurrent backtests, errors logged, monitoring active

---

## Effort Estimates

**Phase A (Quick MVP)**: 3-5 days (LOW-MEDIUM complexity, 60% implementation / 40% testing+validation)
- Scope discovery: 4-6 hours
- Design + schema: 4-6 hours
- Core engine: 8-12 hours (replay, strategies, metrics, storage)
- API endpoints: 4-6 hours
- Testing: 8-10 hours
- Documentation: 3-4 hours
- Deployment: 2-3 hours

**Phase B (Full Framework)**: 3-4 weeks (HIGH complexity, 50% implementation / 30% testing / 20% polish)
- Design enhancements: 1 week
- Multi-symbol + optimization: 1 week
- Strategy library: 4-5 days
- Frontend UI: 1 week
- Integration (0060, 0062): 3-4 days
- Testing + validation: 1 week
- Documentation: 3-4 days
- Performance optimization: 2-3 days

**Total**: 4-5 weeks (Phase A: 3-5 days, Phase B: 3-4 weeks)

---

## Dependencies

- **Task 0062** (Gap Detection): Backtesting validates gap fill effectiveness
  - GAP-019 explicitly identifies backtesting as prerequisite
  - Phase B Task 17.0 requires gap_definition.md and gap fill implementations
- **Task 0060** (CLI Agents): Agents use backtesting for idea validation
  - Phase B Task 18.0 requires agent tool integration
  - Agents should recommend strategies only if backtest Sharpe >1.0
- **Task 0064** (Paper Trading): Shares portfolio state tracking logic
  - Can extract common code after Phase A complete
  - Both systems track positions, cash, equity over time

**NOTES**:
- Phase A is standalone (no blockers, can start immediately)
- Phase B Task 17.0 blocked until Task 0062 gaps filled
- Phase B Task 18.0 blocked until Task 0060 agent integration complete
- Recommend: Phase A now, Phase B after vacation + 0060/0062 progress

---

**Version**: 1.0.0
**Last Updated**: 2025-11-14 00:35
