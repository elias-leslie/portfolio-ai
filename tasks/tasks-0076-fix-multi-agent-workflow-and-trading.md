# Task List: Fix Multi-Agent Workflow and Trading

**Source**: User request via /task_it
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-30 08:45

---

## Summary

**Goal**: Fix critical failures in backtesting, paper trading, and multi-agent workflows to ensure end-to-end functionality and VISION.md compliance.
**Approach**: Diagnose root causes for backtesting failures and paper trading anomalies, fix data freshness issues, and ensure agents can successfully execute workflows.
**Scope Discovery**: Required

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run Explore subagent in "very thorough" mode
  - Pattern: Backtesting execution flow, Paper trading logic, Celery task failures
  - Goal: Identify why backtests fail, why paper trading has bad data, and why workflows are critical.
  - Output: List of broken components and root causes.
- [ ] 0.2 Update this task list with ALL discovered files
  - Add specific tasks for each location found
  - Update effort estimate based on actual scope
- [ ] 0.3 Checkpoint: Confirm scope before proceeding
  - Total files affected: [TBD]
  - Estimated effort: [TBD]
  - Architectural concerns: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Fix Backtesting Functionality

- [ ] 1.1 Investigate and fix backtesting failures (ensure runs complete successfully)
- [ ] 1.2 Verify backtest results are realistic (not 7000% confidence/test data)
- [ ] 1.3 Ensure backtesting integrates with agent workflow

### 2.0 Fix Paper Trading Functionality

- [ ] 2.1 Investigate and fix paper trading anomalies (test data, impossible confidence)
- [ ] 2.2 Ensure paper trading executes correctly based on signals
- [ ] 2.3 Verify transaction history and performance tracking

### 3.0 Fix Multi-Agent Workflow

- [ ] 3.1 Investigate "Critical" health status of multi-agent workflows
- [ ] 3.2 Ensure agents (Discovery, Portfolio Analyzer) run on schedule
- [ ] 3.3 Verify agents can trigger backtests and paper trades

### 4.0 Fix News and Datasource Freshness

- [ ] 4.1 Investigate why news health is bad and datasources are not fresh
- [ ] 4.2 Fix Celery tasks for data fetching (ensure they run and succeed)
- [ ] 4.3 Verify data freshness in database

### 5.0 End-to-End Verification

- [ ] 5.1 Run full multi-agent workflow manually and verify success
- [ ] 5.2 Verify backtest and paper trade creation from agent insights
- [ ] 5.3 Verify system health dashboard shows all green

---

## Verification

- [ ] Functional: All requirements met, zero bugs
- [ ] Tests: 80%+ coverage, all passing (pytest -v)
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes (ruff + mypy)
- [ ] Services: Restarted and verified (bash ~/portfolio-ai/scripts/restart.sh)
- [ ] Clean: No Any types, single source of truth maintained
- [ ] Docs: Updated if public APIs or architecture changed
