# Task List: Strategy Validation Pipeline

**Source**: VISION.md Gap Analysis via /align_it (2025-12-02)
**Complexity**: Complex
**Effort**: MEDIUM (2-3 days)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-02 12:10

---

## Summary

**Goal**: Enforce VISION.md "Validate Before Execute" principle by requiring backtest validation before paper trade execution, and tracking live performance metrics daily.

**Approach**:
1. Add backtest_run_id linking to idea_outcomes table
2. Enforce backtest validation in create_paper_trade() flow
3. Create daily Celery task for live performance metric updates
4. Add strategy performance API endpoint

**Scope Discovery**: Required to understand current paper trading flow and integration points

---

## Tasks

**IMPORTANT: Use section headers (###) for high-level tasks**

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Analyze current paper trading flow
  - File: `backend/app/analytics/paper_trading.py`
  - Goal: Understand create_paper_trade() entry points and parameters
  - Find: What validation exists today (if any)
- [ ] 0.2 Analyze strategy signal tasks
  - File: `backend/app/tasks/strategy_signal_tasks.py`
  - Goal: Understand auto_paper_trade_from_signals() flow
  - Find: Where to inject backtest validation
- [ ] 0.3 Review idea_outcomes table schema
  - Check: Current columns and foreign keys
  - Plan: How to add backtest_run_id linkage
- [ ] 0.4 Checkpoint: Confirm scope before proceeding
  - Integration points identified: [TBD]
  - Migration needed: [TBD]
  - Estimated effort: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Add Backtest Linking to Idea Outcomes

- [ ] 1.1 Create migration for backtest_run_id column
  - Add `backtest_run_id` INT nullable FK to `backtest_runs(id)`
  - Add index on `(strategy_id, backtest_run_id)`
- [ ] 1.2 Update idea_outcomes model/TypedDict
  - Add `backtest_run_id` field
  - Update response builders
- [ ] 1.3 Update create_paper_trade() to accept backtest_run_id
  - Store linkage when paper trade created from validated strategy

### 2.0 Enforce Backtest Validation Before Paper Trading

- [ ] 2.1 Create backtest validation function
  - Check: backtest exists for strategy
  - Check: backtest status = "completed"
  - Check: Sharpe ratio > configurable threshold (default 0.5)
  - Check: win_rate > configurable threshold (default 30%)
- [ ] 2.2 Integrate validation into create_paper_trade()
  - Call validation function before creating trade
  - Reject if validation fails with clear error message
- [ ] 2.3 Integrate validation into auto_paper_trade_from_signals()
  - Only auto-execute if strategy has passing backtest
  - Log skipped trades with reason
- [ ] 2.4 Add validation threshold configuration
  - Config file or environment variables
  - Default: Sharpe > 0.5, win_rate > 30%

### 3.0 Create Daily Live Performance Metric Updates

- [ ] 3.1 Create live performance calculation function
  - Calculate Sharpe ratio from paper trade daily returns
  - Calculate win rate (% profitable closed trades)
  - Calculate max drawdown from equity curve
- [ ] 3.2 Create Celery task for daily metric updates
  - Run at 22:00 UTC (after update_paper_trades at 21:30)
  - Query all open paper trades per strategy
  - Calculate and store live metrics
- [ ] 3.3 Update strategy_definitions table with live metrics
  - Populate: `live_sharpe_ratio`, `live_win_rate`, `live_max_drawdown`
  - Add timestamp: `live_metrics_updated_at`
- [ ] 3.4 Add task to celery_schedules.py
  - Schedule: `crontab(hour=22, minute=0)`

### 4.0 Add Strategy Performance API Endpoint

- [ ] 4.1 Create GET /api/strategies/{id}/performance endpoint
  - Return: backtest metrics vs live metrics comparison
  - Include: expected_sharpe, live_sharpe, variance
  - Include: expected_win_rate, live_win_rate, variance
- [ ] 4.2 Add performance summary to strategy list endpoint
  - Include live_vs_expected variance indicator
  - Flag strategies where live performance deviates >20% from backtest
- [ ] 4.3 Update frontend to display performance comparison
  - Strategy detail modal: Add "Backtest vs Live" section
  - Color-code: Green (outperforming), Red (underperforming)

### 5.0 Testing and Verification

- [ ] 5.1 Write unit tests for validation function
  - Test: Passing backtest allows paper trade
  - Test: Missing backtest rejects paper trade
  - Test: Low Sharpe rejects paper trade
  - Test: Low win rate rejects paper trade
- [ ] 5.2 Write unit tests for live metric calculation
  - Test: Sharpe calculation from daily returns
  - Test: Win rate from closed trades
  - Test: Max drawdown calculation
- [ ] 5.3 Write integration test for full pipeline
  - Create strategy → Run backtest → Validate → Paper trade → Update metrics
- [ ] 5.4 Run full test suite
  - `cd ~/portfolio-ai/backend && pytest tests/ -v`
- [ ] 5.5 Restart services and verify
  - `bash ~/portfolio-ai/scripts/restart.sh`

---

## Verification

- [ ] Functional: Backtest validation enforced before paper trading
- [ ] Tests: 80%+ coverage on new code, all passing
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes
- [ ] Data: Live metrics populated for active strategies
- [ ] API: GET /api/strategies/{id}/performance returns expected data
- [ ] Services: Restarted and verified
- [ ] Docs: AUTONOMOUS_TRADING.md updated with validation requirements
