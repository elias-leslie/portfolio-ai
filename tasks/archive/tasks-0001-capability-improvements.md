# Task List: Capability Improvements (from /capability_it)

**Source**: Automated analysis via /capability_it
**Complexity**: Complex (multi-area improvements)
**Effort**: MEDIUM-HIGH
**Environment**: Local Dev
**Created**: 2025-12-03 17:40
**Generated From**:
  - Capabilities scan: 2025-12-03 17:38
  - Insights pending: 11 critical, 23 high
  - Gaps: 11 P0, 22 P1 (26.8% avg coverage)

---

## Summary

**Goal**: Address 11 critical insights and top P0 gaps to improve system reliability
**Approach**: Fix broken Celery tasks first, then populate empty tables
**Quick Wins**: 8 items (LOW effort, HIGH impact) - covariance, drawdown, position sizing

---

## Key Issues Identified

### Critical Insights (11)
1. `gap_analysis_history` - stale 16 days (task never ran)
2. `portfolio_accounts` - stale 19 days (paper trades not updating cash)

### High Priority Insights (Selected - 10)
3. `maintain-historical-market-data` - 67% success rate
4. `earnings_surprises` - empty table, task never ran
5. `update-technical-indicators-daily` - 50% failure rate
6. `update-portfolio-covariance-daily` - 0% success rate
7. `save-portfolio-snapshots-daily` - 50% failure rate
8. `refresh-watchlist-ohlcv` - 57% success rate
9. `news_cache` - stale despite task running (logic error)
10. Multiple tasks never executed (systemic scheduler issue)

### P0 Gaps (5 Critical)
- GAP-020: Covariance matrix (EFFORT: LOW)
- GAP-043: Equity-based position sizing (EFFORT: LOW)
- GAP-003: Earnings surprises (EFFORT: MEDIUM)
- GAP-023: Drawdown tracking (EFFORT: LOW)
- GAP-045: Kelly position sizing (EFFORT: LOW)

---

## Tasks

### 0.0 Pre-Fix Verification

- [ ] 0.1 Verify services running: `bash ~/portfolio-ai/scripts/status.sh`
- [ ] 0.2 Check Celery Beat logs for scheduler issues: `tail -50 /var/log/portfolio-ai/celery-beat.log`
- [ ] 0.3 Note current capability health baseline (112 active, 4 suspect)

### 1.0 Fix Systemic Scheduler Issues (Critical - Fixes Multiple Tasks)

**Root Cause**: Multiple tasks (analyze-trading-gaps-daily, update-earnings-surprises-weekly, etc.) never ran

- [ ] 1.1 Check Celery Beat service status
- [ ] 1.2 Verify all scheduled tasks are registered in celery_schedules.py
- [ ] 1.3 Check if tasks are importing correctly (no silent import errors)
- [ ] 1.4 Restart Celery Beat after fixes: `bash ~/portfolio-ai/scripts/restart.sh`

### 2.0 Fix High-Failure-Rate Tasks

**Insight IDs: 8, 122, 108, 41, 15**

- [ ] 2.1 Fix `maintain-historical-market-data` (67% success)
  - Check logs for root cause
  - Add symbol-level error handling
  - Prevent one bad ticker from failing batch
  - Files: `app/tasks/market_data_tasks.py`

- [ ] 2.2 Fix `update-technical-indicators-daily` (50% success)
  - Investigate `backfill_technical_indicators` task logs
  - Likely data quality issues in day_bars for specific symbols
  - Files: `app/tasks/technical_tasks.py`

- [ ] 2.3 Fix `update-portfolio-covariance-daily` (0% success)
  - Check worker logs for tracebacks
  - Files: `app/tasks/portfolio_tasks.py`

- [ ] 2.4 Fix `save-portfolio-snapshots-daily` (50% success)
  - Review save_portfolio_snapshots task
  - Ensure idempotent and retries on transient errors
  - Files: `app/tasks/portfolio_tasks.py`

- [ ] 2.5 Fix `refresh-watchlist-ohlcv` (57% success)
  - Add symbol-level error handling
  - Files: `app/tasks/market_data_tasks.py`

### 3.0 Fix Stale Data Issues

**Insight IDs: 43, 64, 1**

- [ ] 3.1 Fix `gap_analysis_history` staleness (16 days)
  - Enable `analyze-trading-gaps-daily` task
  - Verify in celery_schedules.py

- [ ] 3.2 Fix `portfolio_accounts` staleness (19 days)
  - Paper trades not updating cash balance
  - Check `update_paper_trades_task`
  - Files: `app/tasks/paper_trading_tasks.py`

- [ ] 3.3 Fix `news_cache` staleness (1 day)
  - Task runs but doesn't update tables (logic error)
  - Check commit logic in refresh_news_sentiment
  - Files: `app/tasks/news_tasks.py`

### 4.0 Populate Empty Tables

**Insight IDs: 123, 114, 107, 100, 92, 87, 77**

- [ ] 4.1 Enable and run `update-earnings-surprises-weekly`
  - Verify schedule in celery_schedules.py
  - Check API credentials (FMP/Finnhub)
  - Files: `app/celery_schedules.py`, `app/tasks/market_data_tasks.py`

### 5.0 Implement P0 Gap Fixes (LOW Effort)

**Gap IDs: GAP-020, GAP-023, GAP-045**

- [ ] 5.1 Implement covariance matrix calculation (GAP-020)
  - Use 252-day returns from day_bars
  - Store in portfolio_covariance table
  - Replace weighted avg risk with proper σ_portfolio = √(w' Σ w)

- [ ] 5.2 Implement drawdown tracking (GAP-023)
  - Calculate max DD, current DD, days since ATH
  - Store in portfolio_drawdowns table
  - Source from portfolio_snapshots

- [ ] 5.3 Implement Kelly position sizing (GAP-045)
  - Kelly% = (WinRate×AvgWin - LossRate×AvgLoss)/AvgWin
  - Use fractional Kelly (0.25-0.5)
  - Store in strategy_performance table

---

## Verification & Insight Resolution (CRITICAL)

### V.1 Re-scan Capabilities

- [ ] V.1.1 Trigger fresh scan: `curl -s -X POST http://localhost:8000/api/capabilities/scan`
- [ ] V.1.2 Wait 10 seconds for completion
- [ ] V.1.3 Verify health: `curl -s http://localhost:8000/api/capabilities/health/summary | jq .`

### V.2 Mark Resolved Insights as Fixed

Mark each resolved insight via API:

- [ ] V.2.1 Mark insight #43 (gap_analysis_history) as fixed
- [ ] V.2.2 Mark insight #64 (portfolio_accounts) as fixed
- [ ] V.2.3 Mark insight #8 (maintain-historical-market-data) as fixed
- [ ] V.2.4 Mark insight #122 (update-technical-indicators-daily) as fixed
- [ ] V.2.5 Mark insight #108 (update-portfolio-covariance-daily) as fixed
- [ ] V.2.6 Mark insight #41 (save-portfolio-snapshots-daily) as fixed
- [ ] V.2.7 Mark insight #15 (refresh-watchlist-ohlcv) as fixed
- [ ] V.2.8 Mark insight #1 (news_cache) as fixed
- [ ] V.2.9 Mark insights #123, #114, #107, #100, #92, #87, #77 (earnings_surprises) as fixed

### V.3 Verify Resolution

- [ ] V.3.1 Count remaining critical insights (target: 0):
  ```bash
  curl -s "http://localhost:8000/api/capabilities/insights" | jq '[.insights[] | select(.status == "pending" and .severity == "critical")] | length'
  ```

- [ ] V.3.2 Check gap coverage improved:
  ```bash
  curl -s http://localhost:8000/api/gaps/summary | jq '{avg_coverage: .avg_coverage_pct, p0: .p0_gaps}'
  ```

### V.4 Final Quality Check

- [ ] V.4.1 Run lint: `~/portfolio-ai/scripts/lint.sh`
- [ ] V.4.2 Services healthy: `bash ~/portfolio-ai/scripts/status.sh`
- [ ] V.4.3 Take screenshot: `node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js http://192.168.8.233:3000/capabilities /tmp/capabilities-verified.png`

---

## Notes

**Skip items requiring external APIs we don't have:**
- Intraday data (minute_bars) - needs Polygon subscription
- Options flow - needs Tradier account

**Dependencies:**
- Task 1.x (scheduler fixes) may automatically resolve some Task 2.x issues
- Task 3.2 depends on Task 2.x fixes working

**Commits:**
- Commit after each major section (1.x, 2.x, 3.x, etc.)
