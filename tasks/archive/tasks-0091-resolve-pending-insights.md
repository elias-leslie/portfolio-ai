# Task List: Resolve Pending Capability Insights

**Source**: User request via /task_it - Address 17 pending insights
**Complexity**: Medium
**Effort**: MEDIUM
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-04 00:15

---

## Summary

**Goal**: Resolve or dismiss the 17 pending capability insights to bring the Insights count to 0
**Approach**: Group by root cause, fix actual issues, dismiss test/duplicate insights
**Scope Discovery**: Not needed - insights already identified specific issues

---

## Insight Analysis

| ID | Type | Table/Task | Issue | Action |
|----|------|------------|-------|--------|
| 177, 148 | missing_data | strategy_metrics | Empty table, no populating task | Create task or dismiss if not needed |
| 14, 156, 22 | missing_data | agent_messages | Empty (multi-agent not implemented) | Dismiss - future feature |
| 185, 86, 63, 126 | missing_data | api_capabilities | No performance metrics | Fix capability scanner |
| 200 | missing_capability | refresh-analyst-revisions | Task not running | Check Celery schedule |
| 176 | missing_capability | symbols | Missing company info | Run yfinance refresh |
| 141 | missing_capability | update_earnings_surprises | Task never run | Check Celery schedule |
| 6 | missing_capability | cleanup-old-news-weekly | Cleanup tasks not running | Check Celery schedule |
| 38 | broken_dependency | fetch-putcall-ratio | Task needs fixing | Check task implementation |
| 5 | data_quality | agent_runs | Incomplete data | Expected - agents run rarely |
| 54 | broken_dependency | test_table | Test insight | Dismiss |
| 9 | freshness | day_bars | 3 days old | Auto-fixed by daily task |

---

## Tasks

### 0.0 Pre-Work Verification

- [ ] 0.1 Verify services running: `bash ~/portfolio-ai/scripts/status.sh`
- [ ] 0.2 Note current pending insight count (expect 17)

### 1.0 Dismiss Test/Non-Actionable Insights

- [ ] 1.1 Dismiss test insight (ID 54):
  ```bash
  curl -sL -X POST "http://localhost:8000/api/capabilities/insights/54/review" \
    -H "Content-Type: application/json" \
    -d '{"status": "dismissed", "status_reason": "Test insight from scrub_it implementation"}'
  ```

- [ ] 1.2 Dismiss agent_messages insights (IDs 14, 156, 22) - future feature:
  ```bash
  for id in 14 156 22; do
    curl -sL -X POST "http://localhost:8000/api/capabilities/insights/$id/review" \
      -H "Content-Type: application/json" \
      -d '{"status": "dismissed", "status_reason": "Multi-agent collaboration not yet implemented - future feature"}'
  done
  ```

- [ ] 1.3 Dismiss agent_runs insight (ID 5) - expected behavior:
  ```bash
  curl -sL -X POST "http://localhost:8000/api/capabilities/insights/5/review" \
    -H "Content-Type: application/json" \
    -d '{"status": "dismissed", "status_reason": "Agent runs are sparse by design - agents only run for specific tasks"}'
  ```

### 2.0 Fix API Capabilities Performance Metrics (IDs 185, 86, 63, 126)

- [ ] 2.1 Investigate why api_capabilities lacks performance metrics
  - Check capability scanner code for API metrics collection
  - File: `backend/app/services/capability_scanner/`

- [ ] 2.2 Add API performance metric collection if missing
  - Track response times, error rates, call counts

- [ ] 2.3 Re-run capability scan and verify metrics populated:
  ```bash
  curl -sL -X POST http://localhost:8000/api/capabilities/scan
  sleep 10
  curl -sL "http://localhost:8000/api/capabilities/?type=api&limit=5" | jq '.capabilities[0]'
  ```

- [ ] 2.4 Mark insights as fixed (IDs 185, 86, 63, 126):
  ```bash
  for id in 185 86 63 126; do
    curl -sL -X POST "http://localhost:8000/api/capabilities/insights/$id/review" \
      -H "Content-Type: application/json" \
      -d '{"status": "fixed", "status_reason": "API performance metrics now collected by capability scanner"}'
  done
  ```

### 3.0 Fix Celery Task Scheduling Issues

- [ ] 3.1 Check which scheduled tasks are actually running:
  ```bash
  curl -sL http://localhost:8000/api/status/celery | jq '.scheduled_tasks'
  ```

- [ ] 3.2 Verify task schedules in celery_schedules.py for:
  - `refresh-analyst-revisions-daily` (ID 200)
  - `update-earnings-surprises-weekly` (ID 141)
  - `cleanup-old-news-weekly` (ID 6)
  - `fetch-putcall-ratio-daily` (ID 38)

- [ ] 3.3 Fix any missing/broken task schedules

- [ ] 3.4 Manually trigger tasks to verify they work:
  ```bash
  # Test one task manually
  cd ~/portfolio-ai/backend && source .venv/bin/activate
  celery -A app.celery_app call app.tasks.ingestion.news_ingestion.cleanup_old_news
  ```

- [ ] 3.5 Mark task-related insights as fixed after verification

### 4.0 Fix Strategy Metrics Table (IDs 177, 148)

- [ ] 4.1 Investigate strategy_metrics table purpose:
  - Check if this is used by backtesting or strategy evaluation
  - Determine if a task should populate it

- [ ] 4.2 Either:
  - A) Create a task to populate strategy_metrics if needed, OR
  - B) Dismiss insights if table is for future use

- [ ] 4.3 Mark insights 177 and 148 appropriately

### 5.0 Fix Symbols Table Company Info (ID 176)

- [ ] 5.1 Check symbols table completeness:
  ```bash
  psql -U portfolio_user -d portfolio_ai -c "SELECT COUNT(*), COUNT(company_name) FROM symbols"
  ```

- [ ] 5.2 Run yfinance reference data refresh for missing companies:
  ```bash
  cd ~/portfolio-ai/backend && source .venv/bin/activate
  python3 -c "
  from app.tasks.ingestion.reference_data import refresh_reference_data
  refresh_reference_data.delay()
  "
  ```

- [ ] 5.3 Mark insight 176 as fixed after data populated

### 6.0 Fix Day Bars Freshness (ID 9)

- [ ] 6.1 Check day_bars freshness:
  ```bash
  curl -sL http://localhost:8000/api/status/table-freshness | jq '.tables[] | select(.table_name == "day_bars")'
  ```

- [ ] 6.2 If stale, trigger market data refresh:
  ```bash
  cd ~/portfolio-ai/backend && source .venv/bin/activate
  celery -A app.celery_app call app.tasks.ingestion.market_data.refresh_daily_bars
  ```

- [ ] 6.3 Mark insight 9 as fixed (or auto_resolved if already current)

---

## Verification

- [ ] V.1 Re-scan capabilities:
  ```bash
  curl -sL -X POST http://localhost:8000/api/capabilities/scan
  sleep 15
  ```

- [ ] V.2 Check pending insights count (target: 0):
  ```bash
  curl -sL "http://localhost:8000/api/capabilities/insights" | jq '{pending: .pending_count, fixed: .fixed_count}'
  ```

- [ ] V.3 Take screenshot of capabilities page:
  ```bash
  node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
    http://192.168.8.233:3000/capabilities /tmp/insights-resolved.png
  ```

- [ ] V.4 Verify Insights badge shows 0 (or very low number)

---

## Success Criteria

- [ ] All 17 pending insights addressed (fixed or dismissed with reason)
- [ ] Insights tab badge shows 0-3 pending items
- [ ] No new critical/high insights generated
- [ ] All referenced Celery tasks running on schedule
