# Task List: Fix Multi-Agent Workflow and Trading

**Source**: User request via /task_it (revised by Claude after Gemini handoff)
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-30 08:45
**Revised**: 2025-11-30 (added VISION.md alignment items)

---

## Summary

**Goal**: Fix critical failures in backtesting, paper trading, and multi-agent workflows to ensure end-to-end functionality and VISION.md compliance.
**Approach**: Diagnose root causes, fix data integrity issues, add missing VISION.md features (disagreement detection, backtest gating, cash validation, audit trails).
**Scope Discovery**: Required

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run Explore subagent in "very thorough" mode
  - Pattern 1: `backend/app/backtest/` - Backtest engine, replay logic, strategies
  - Pattern 2: `backend/app/analytics/` - Paper trading, cash management, order execution
  - Pattern 3: `backend/app/tasks/workflow_tasks.py` - Multi-agent orchestration
  - Pattern 4: `backend/app/agents/` - LLM client, tool executors, orchestrator
  - Pattern 5: Celery beat schedule - Which tasks are scheduled, their status
  - Goal: Map complete data flow from agent → backtest → paper trade
  - Output: List of broken components with specific file:line references
- [ ] 0.2 Database state audit
  - Check `backtest_runs` table - How many completed vs failed?
  - Check `paper_trades` table - Any with impossible values (>100% confidence)?
  - Check `agent_workflows` table - Status distribution (pending/running/complete/failed)
  - Check `day_bars` table - Data freshness and symbol coverage
- [ ] 0.3 Update this task list with ALL discovered files
  - Add specific fix tasks for each broken component found
  - Update effort estimate based on actual scope
- [ ] 0.4 Checkpoint: Confirm scope before proceeding
  - Total files affected: [TBD]
  - Estimated effort: [TBD]
  - Architectural concerns: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Fix Backtesting Functionality

- [ ] 1.1 Audit backtest data requirements
  - Verify `day_bars` has 252+ trading days per symbol
  - Add validation: Reject backtests with < 252 days history (B1)
  - Log warning if data gaps detected
- [ ] 1.2 Fix backtest execution in `backend/app/backtest/replay.py`
  - Identify why backtests fail to complete
  - Fix any SQL/data fetching errors
  - Ensure performance metrics calculated correctly (Sharpe, max drawdown, win rate)
- [ ] 1.3 Implement backtest gating for paper trading (B3)
  - Add validation: Block paper trade if Sharpe < 1.0 OR win rate < 50% OR max_drawdown > 20%
  - Location: `backend/app/analytics/order_executor.py` or workflow task
  - Return clear error message explaining why trade was blocked
- [ ] 1.4 Add backtest integration test
  - Create test in `backend/tests/integration/backtest/`
  - Test: Submit backtest → verify completion → verify metrics populated
- [ ] 1.5 Verify backtest results are realistic
  - Manual check: Run AAPL backtest for last 252 days
  - Confirm returns are in reasonable range (-50% to +100%)
  - Confirm Sharpe ratio is in reasonable range (-2 to +3)

### 2.0 Fix Paper Trading Functionality

- [ ] 2.1 Fix cash management validation (P1)
  - Location: `backend/app/analytics/cash_manager.py`
  - Ensure balance check happens BEFORE order execution
  - Add test: Attempt trade exceeding balance → expect rejection
- [ ] 2.2 Add position size limits (P2)
  - Max 5% of portfolio per position
  - Max 20% exposure per sector (if sector data available)
  - Location: `backend/app/analytics/order_executor.py`
- [ ] 2.3 Fix paper trading data integrity
  - Audit `paper_trades` table for impossible values
  - Fix any records with confidence > 10 or negative prices
  - Add database constraint: confidence BETWEEN 0 AND 10
- [ ] 2.4 Implement trade audit trail (P3)
  - Ensure `transactions` table captures: timestamp, action, symbol, qty, price, reason
  - Add agent_run_id foreign key to link trades to workflow that created them
  - Location: `backend/app/analytics/transaction_logger.py`
- [ ] 2.5 Add daily P&L reporting task (P4)
  - Create Celery task: `calculate_daily_paper_trade_pnl`
  - Schedule: Daily at 21:30 UTC (after market close)
  - Store in new table or existing `paper_trades` with daily_pnl column
- [ ] 2.6 Add paper trading integration test
  - Test: Create paper trade → verify cash deducted → verify transaction logged

### 3.0 Fix Multi-Agent Workflow

- [ ] 3.1 Audit workflow health
  - Query `agent_workflows` for failed workflows in last 7 days
  - Extract error messages from `result` JSONB column
  - Categorize failures: LLM error, tool error, timeout, data error
- [ ] 3.2 Implement LLM disagreement detection (A1)
  - Location: `backend/app/agents/orchestrator.py` or `workflow_tasks.py`
  - When Claude and Gemini produce different recommendations, log disagreement
  - Store in `agent_messages` table with `message_type = 'disagreement'`
  - Add field: `disagreement_severity` (low/medium/high based on confidence gap)
- [ ] 3.3 Implement confidence-weighted consensus (A2)
  - When agents disagree, weight by confidence score
  - Example: Claude 0.9 confidence + Gemini 0.6 confidence → Claude wins
  - Location: `backend/app/agents/orchestrator.py` resolve_conflicts method
- [ ] 3.4 Add workflow health monitoring endpoint (A4)
  - Endpoint: GET `/api/status/workflow-health`
  - Returns: success_rate_24h, failed_count, avg_duration, last_success_time
  - Add to health dashboard frontend
- [ ] 3.5 Fix scheduled agent execution
  - Verify Celery beat schedule includes agent tasks at 03:30 UTC
  - Check `backend/app/celery_app.py` beat_schedule
  - Test: Manually trigger `daily_gap_analysis_workflow` and verify completion
- [ ] 3.6 Ensure agents can trigger backtests
  - Verify `run_backtest` tool is registered in `backend/app/agents/tools.py`
  - Test: Agent prompt that requests backtest → verify backtest created
- [ ] 3.7 Add workflow integration test
  - Test: Trigger workflow → verify agent messages created → verify consensus reached

### 4.0 Fix News and Data Source Freshness

- [ ] 4.1 Add data freshness alerts (D1)
  - Create function: `check_data_freshness_alerts()`
  - Check: day_bars, news_cache, fear_greed_daily
  - Alert if any table has max(timestamp) > 24 hours old
  - Integrate with health endpoint
- [ ] 4.2 Implement source failover logging (D2)
  - Location: `backend/app/sources/multi_source_fetcher.py`
  - Log when primary source fails and fallback is used
  - Store in `source_performance` table: timestamp, symbol, primary_source, fallback_source, error
- [ ] 4.3 Audit Celery data fetching tasks
  - List all scheduled tasks in beat_schedule
  - Check last run time for each task
  - Identify tasks that haven't run in > 24 hours
- [ ] 4.4 Fix failing data tasks
  - For each identified failing task:
    - Check error logs
    - Fix root cause (API key, rate limit, code bug)
    - Manually trigger and verify success
- [ ] 4.5 Verify data freshness
  - Query each critical table for max timestamp
  - Confirm all within 24 hours after fixes applied

### 5.0 End-to-End Verification

- [ ] 5.1 Run full multi-agent workflow manually
  - Trigger: `celery -A app.celery_app call app.tasks.workflow_tasks.daily_gap_analysis_workflow`
  - Verify: Workflow completes with status="complete"
  - Verify: Agent messages created in database
  - Verify: Consensus reached and logged
- [ ] 5.2 Verify backtest creation from agent
  - Check if agent workflow created any backtest runs
  - Verify backtest completed successfully
  - Verify performance metrics populated
- [ ] 5.3 Verify paper trade creation (if backtest passed gating)
  - Check if paper trade was created
  - Verify cash management worked (balance reduced)
  - Verify transaction logged
- [ ] 5.4 Verify system health dashboard
  - Navigate to /status page
  - Confirm: All data sources showing fresh data
  - Confirm: Workflow health showing green
  - Confirm: No critical alerts
- [ ] 5.5 Run full test suite
  - `cd ~/portfolio-ai/backend && pytest tests/ -v`
  - Confirm: 100% pass rate
  - Confirm: No new failures introduced

---

## Verification

- [ ] Functional: All requirements met, zero bugs
- [ ] Tests: 80%+ coverage, all passing (pytest -v)
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes (ruff + mypy)
- [ ] Services: Restarted and verified (bash ~/portfolio-ai/scripts/restart.sh)
- [ ] Clean: No Any types, single source of truth maintained
- [ ] Docs: Updated OPERATIONS.md if new scheduled tasks added
- [ ] VISION: Disagreement detection (A1), backtest gating (B3), cash validation (P1), audit trail (P3) implemented

---

## VISION.md Alignment Checklist

- [ ] A1: LLM disagreement detection implemented
- [ ] A2: Confidence-weighted consensus implemented
- [ ] A4: Workflow health monitoring endpoint added
- [ ] B1: 252-day minimum data validation added
- [ ] B3: Backtest gating (Sharpe, win rate, drawdown) implemented
- [ ] P1: Cash management validation fixed
- [ ] P2: Position size limits added
- [ ] P3: Trade audit trail implemented
- [ ] P4: Daily P&L reporting task added
- [ ] D1: Data freshness alerts added
- [ ] D2: Source failover logging implemented
