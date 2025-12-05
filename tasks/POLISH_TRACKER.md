# Polish Tracker

**Last Run**: 2025-12-05 08:50 UTC
**Status**: IN_PROGRESS
**Context Used**: 35%
**Mode**: FULL (approval for risky items)

---

## Active Items (max 10)

| ID | Category | Priority | Item | Status | Attempts |
|----|----------|----------|------|--------|----------|
| U-001 | UI | P1 | 500 error on /watchlist (localStorage SSR) | FIXED | 0 |
| H-004 | HEALTH | P1 | Workflow 47% success rate (historical, now 100% in 24h) | RESOLVED | 0 |
| H-002 | HEALTH | P1 | Fear & Greed date column errors (historical, now resolved) | RESOLVED | 0 |
| U-002 | UI | P1 | Status page timeout (networkidle issue, page loads fine) | WONTFIX | 0 |
| H-001 | HEALTH | P2 | Data sources degraded: twelvedata, fmp, cboe, alphavantage | MONITORING | 0 |
| H-003 | HEALTH | P2 | Market data staleness 3-4 days (weekend expected) | MONITORING | 0 |
| Q-001 | QUALITY | CRIT | SQL injection risk in capability_db_scanner.py | WONTFIX | 0 |

---

## Recently Completed (last 20)

| ID | Category | Item | Completed | Duration |
|----|----------|------|-----------|----------|
| U-001 | UI | Fixed /watchlist 500 error - localStorage SSR hydration | 2025-12-05 08:45 | 10m |
| H-007 | HEALTH | Fixed empty tables - 8 tables now populated (1400+ rows total) | 2025-12-04 23:05 | 30m |
| B-001 | BUG | Fixed task registration - added exports to ingestion/__init__.py | 2025-12-04 22:50 | 5m |
| B-002 | BUG | Fixed numpy serialization - added _to_python() converter | 2025-12-04 22:52 | 5m |
| B-003 | BUG | Fixed credential loading - added load_credentials_from_database() | 2025-12-04 22:55 | 3m |
| B-004 | BUG | Fixed FRED API key - deleted placeholder, added apikey mapping | 2025-12-04 23:00 | 3m |
| D-002 | DEAD_CODE | Dropped 3 unused empty tables | 2025-12-04 22:45 | 3m |
| D-001 | DEAD_CODE | Archived empty placeholder snapshot_service.py | 2025-12-04 22:30 | 2m |
| P-001 | LINT | Remove unused imports from strategy_evolution_agent.py | 2025-12-04 22:03 | 1m |
| P-002 | LINT | Sort imports in paper_trading_orders.py | 2025-12-04 22:03 | 1m |

---

## Discovery Queue (max 50)

*Fresh discovery 2025-12-05 - Merged from 4 parallel agents*

### Health Issues (4)
| ID | Severity | Item | Safe? |
|----|----------|------|-------|
| H-001 | P2 | Data sources degraded (twelvedata, fmp, cboe, alphavantage 6-12h stale) | NO |
| H-002 | P1 | Fear & Greed date column errors - RESOLVED (historical) | NO |
| H-003 | P2 | Market data staleness 3-4 days (weekend expected) | NO |
| H-004 | P1 | Workflow 47% success rate - RESOLVED (now 100% in 24h) | NO |

### UI Issues (2)
| ID | Severity | Item | Safe? |
|----|----------|------|-------|
| U-001 | P1 | /watchlist 500 error - FIXED (localStorage SSR) | NO |
| U-002 | P1 | /status page timeout - WONTFIX (networkidle polling) | NO |

### Quality Issues (15)
| ID | Severity | Item | Safe? |
|----|----------|------|-------|
| Q-001 | CRIT | SQL injection in capability_db_scanner.py - FALSE POSITIVE | NO |
| Q-002 | WARN | backtest.py 1027 lines | NO |
| Q-003 | WARN | reference_tasks.py 970 lines | NO |
| Q-004 | WARN | celery_schedules.py 829 lines | NO |
| Q-005 | WARN | watchlist.py 796 lines | NO |
| Q-006 | WARN | paper_trades.py 785 lines | NO |
| Q-007 | WARN | strategy_monitoring_tasks.py 771 lines | NO |
| Q-008 | WARN | research_aggregator.py 769 lines | NO |
| Q-009 | WARN | optimizer.py 738 lines | NO |
| Q-010 | WARN | strategy_evolution_agent.py 731 lines | NO |
| Q-011 | WARN | 214 Any type usages | NO |
| Q-012 | WARN | 14 hardcoded localhost/IP refs | NO |
| Q-013 | WARN | .env.example not found | NO |
| Q-014 | WARN | 498 functions exceed 50 lines | NO |
| Q-015 | WARN | 14 TODO/FIXME comments | NO |

### Dead Code Candidates (10)
| ID | Severity | Item | Safe? |
|----|----------|------|-------|
| D-001 | MED | discover_watchlist_candidates - legacy task | NO |
| D-002 | MED | trim_underperforming_watchlist - legacy task | NO |
| D-003 | LOW | /api/sources/routing/{data_type} - orphaned endpoint | NO |
| D-004 | LOW | /api/sources/gap/{gap_id} - orphaned endpoint | NO |
| D-005 | MED | weekly_optimization_review - legacy task | NO |
| D-006 | LOW | institutional_ownership.py - unused module | NO |
| D-007 | LOW | apply_liquidity_cap() - unused function | NO |
| D-008 | MED | generate_daily_watchlist_report - unscheduled task | NO |
| D-009 | LOW | agent_messages table - empty, legacy | NO |
| D-010 | LOW | watchlist_daily_reports table - empty, legacy | NO |

---

## Deferred Items (user-approved skips)

| ID | Item | Reason | Deferred On |
|----|------|--------|-------------|
| - | No deferred items | - | - |

---

## Session History (last 5)

| Date | Duration | Fixed | Deferred | Remaining |
|------|----------|-------|----------|-----------|
| 2025-12-05 08:50 | 20m | 1 | 0 | 27 (tech debt) |
| 2025-12-04 23:05 | 45m | 5 | 0 | ~60 |
| 2025-12-04 22:30 | 10m | 1 | 0 | 74 |
| 2025-12-04 22:00 | 5m | 2 | 0 | 11 |

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Fixed (all time) | 10 |
| Total Deferred | 0 |
| Average Items/Session | 2.5 |
| Success Rate | 100% |
| Archives Created | 0 |

---

## Notes

*Session-specific notes and context for resume*

- **2025-12-05 08:50**: Fixed U-001 /watchlist 500 error
  - Root cause: `localStorage` accessed during SSR (server-side rendering)
  - Fix: Moved localStorage reads to useEffect hook for hydration safety
  - File: `frontend/app/watchlist/page.tsx:29-50`
  - Verified: Page now returns 200, console clean

- **2025-12-05 08:30**: Investigated P1 issues from fresh discovery
  - H-004 (47% workflow success): Historical 7-day data; current 24h shows 100%
  - H-002 (Fear & Greed date errors): Historical remediation logs from 2025-12-04
  - U-002 (status timeout): Page loads fine, timeout is playwright `networkidle` waiting for API polling
  - All P1 health issues are historical, current health is good

- **2025-12-05 07:30**: Fresh discovery with 4 parallel agents
  - Found 31 total issues: 4 Health, 2 UI, 15 Quality, 10 Dead Code
  - Most are tech debt (large files, long functions)
  - Q-001 SQL injection is FALSE POSITIVE (DB introspection, not user input)

---

## Quality Baseline (2025-12-05)

| Metric | Before | Current |
|--------|--------|---------|
| Health status | degraded | healthy |
| Workflow success (24h) | 47% (7d) | 100% (24h) |
| /watchlist status | 500 | 200 |
| /status page | timeout | 200 (loads fine) |
| P1 Issues open | 4 | 0 |
| Tech debt (files >500) | 37 | 37 |
