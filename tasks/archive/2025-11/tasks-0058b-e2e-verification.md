<!-- PAUSED: 2025-11-14 09:30 | Context: 63% | Next: Task 0 - Verify Scheduled Tasks Are Running -->

# Phase 1: E2E Verification & Testing

**Created**: 2025-11-14
**Priority**: P0 (CRITICAL - Verify all Phase 1 implementations)
**Parent**: tasks-0058a-fix-existing-features.md
**Phase**: Verification after implementation
**Status**: READY TO START
**PAUSED**: 2025-11-14 09:30 (User request - task list created, ready for /do_it --max)
**Next**: Task 0 - Verify Scheduled Tasks Are Running

**Objective**: Comprehensive E2E testing to verify all Phase 1 implementations are working correctly in production UI and API.

**Current Problem**:
- UI shows "Fear & Greed data is 4 days old" (should be current)
- Market data shows "as of Nov 12" (today is Nov 14)
- Need to verify all our implementations (Fear & Greed 5 components, valuation data) are actually reflected in UI

**Success Criteria**:
- ✅ Dashboard shows CURRENT Fear & Greed data (today's date, not 4 days old)
- ✅ All 5 Fear & Greed components visible and populated
- ✅ Watchlist shows valuation metrics (P/E, P/B, P/S)
- ✅ Market data is current (Nov 14 or later)
- ✅ No stale data warnings in UI
- ✅ All scheduled tasks running on time

---

## Task 0: Verify Scheduled Tasks Are Running (1 hour)

**Priority**: P0 - CRITICAL
**Objective**: Confirm all scheduled Celery tasks are executing on schedule

### 0.1: Check Celery Beat Schedule
- [ ] Verify beat is running: `systemctl status portfolio-beat`
- [ ] Check beat logs for scheduled task execution
- [ ] Confirm all 5 tasks in schedule:
  - `populate_fear_greed_inputs` (02:45 UTC daily)
  - `refresh_yfinance_reference_data` (04:00 UTC daily)
  - `parse_valuation_metrics` (04:30 UTC daily)
  - `refresh_alphavantage_reference_backup` (04:45 UTC daily)
  - `calculate_fear_greed` (03:00 UTC daily)

### 0.2: Check Task Execution History
- [ ] Query Celery results backend for recent task executions
- [ ] Verify tasks completed successfully (not failed/retrying)
- [ ] Check execution timestamps (should be within last 24 hours)
- [ ] Review task logs for errors/warnings

### 0.3: Manual Task Trigger Test
- [ ] Manually trigger `populate_fear_greed_inputs`
- [ ] Manually trigger `refresh_yfinance_reference_data`
- [ ] Manually trigger `calculate_fear_greed`
- [ ] Verify all complete successfully
- [ ] Check database has new data with today's date

**Verification Command**:
```bash
# Check recent task executions
cd ~/portfolio-ai/backend && source .venv/bin/activate
celery -A app.celery_app inspect active
celery -A app.celery_app inspect stats

# Check beat schedule
celery -A app.celery_app inspect scheduled

# Check database for today's data
PGPASSWORD=REDACTED_PASSWORD psql -U portfolio_ai_user -h localhost -d portfolio_ai -c "
SELECT 'fear_greed_inputs' as table_name, MAX(as_of_date) as latest_date FROM fear_greed_inputs
UNION ALL
SELECT 'fear_greed_daily', MAX(as_of_date) FROM fear_greed_daily
UNION ALL
SELECT 'reference_cache (yfinance)', MAX(as_of_date) FROM reference_cache WHERE source='yfinance';
"
```

**Expected Result**: All tables have data from 2025-11-14 or later

---

## Task 1: Verify Fear & Greed Data Freshness (30 min)

**Priority**: P0 - CRITICAL
**Objective**: Ensure Fear & Greed shows CURRENT data, not "4 days old"

### 1.1: Check Database for Latest Fear & Greed
- [ ] Query `fear_greed_daily` for latest entry
- [ ] Query `fear_greed_inputs` for latest entry
- [ ] Query `fear_greed_components` for latest entry
- [ ] Verify all tables have 2025-11-14 data
- [ ] Verify signal_count = 5 (all components)

### 1.2: Check API Response
- [ ] GET `/api/market/intelligence`
- [ ] Verify `fear_greed.score` is present
- [ ] Verify `fear_greed.label` is present
- [ ] Verify `fear_greed.as_of_date` is 2025-11-14 or later
- [ ] Verify `timestamp` is recent (not 4 days old)

### 1.3: Check UI Display
- [ ] Use browser automation to screenshot Market Conditions card
- [ ] Verify no "Fear & Greed data is 4 days old" warning
- [ ] Verify Fear & Greed score displays current value
- [ ] Verify "Updated just now" or recent timestamp
- [ ] Verify no stale data warnings anywhere on page

**Browser Automation Test**:
```bash
node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
  http://192.168.8.233:3000/ /tmp/market-conditions-current.png --full-page

node ~/portfolio-ai/.claude/skills/browser-automation/scripts/console.js \
  http://192.168.8.233:3000/ 5000 > /tmp/console-errors.txt
```

**Expected Result**: No stale data warnings, current date in UI

---

## Task 2: Verify All 5 Fear & Greed Components (45 min)

**Priority**: P0 - CRITICAL
**Objective**: Confirm all 5 components are populated and used in calculation

### 2.1: Database Verification
- [ ] Query `fear_greed_inputs` for latest row
- [ ] Verify all 5 component columns populated:
  - `vix_close` (not NULL)
  - `spy_close` (not NULL)
  - `rsi_14` (not NULL)
  - `hy_spread` (not NULL, NOT constant 3.13)
  - `breadth_pct` (not NULL)
- [ ] Query `fear_greed_components` for latest calculation
- [ ] Verify 5 rows exist for latest date
- [ ] Query `fear_greed_daily` - verify `signal_count = 5`

### 2.2: API Verification
- [ ] GET `/api/market/intelligence`
- [ ] Check if `fear_greed.components` array exists
- [ ] Verify components include all 5:
  - VIX component
  - Momentum component
  - RSI component
  - Credit spread component
  - Breadth component
- [ ] Verify each component has score and percentile

### 2.3: Data Quality Check
- [ ] Verify HY spread varies (not constant 3.13)
- [ ] Verify breadth_pct changes day-to-day (42%-90% range expected)
- [ ] Verify VIX values are realistic (15-25 typical)
- [ ] Verify RSI values are 0-100 range
- [ ] Check for NULL values (should be minimal)

**Verification Query**:
```sql
SELECT
  as_of_date,
  vix_close,
  spy_close,
  rsi_14,
  hy_spread,
  breadth_pct,
  CASE
    WHEN vix_close IS NULL THEN 'MISSING VIX'
    WHEN hy_spread IS NULL THEN 'MISSING HY_SPREAD'
    WHEN breadth_pct IS NULL THEN 'MISSING BREADTH'
    ELSE 'OK'
  END as status
FROM fear_greed_inputs
ORDER BY as_of_date DESC
LIMIT 10;
```

**Expected Result**: All 5 components populated for recent dates, no MISSING status

---

## Task 3: Verify Valuation Data in UI (1 hour)

**Priority**: P0 - CRITICAL
**Objective**: Confirm P/E, P/B, P/S ratios display in watchlist

### 3.1: Database Verification
- [ ] Query `reference_cache` for yfinance source data
- [ ] Verify 8+ symbols have valuation data
- [ ] Verify parsed columns populated:
  - `pe_ratio_trailing` (not NULL)
  - `pb_ratio` (not NULL)
  - `ps_ratio` (not NULL)
  - `dividend_yield` (not NULL for dividend stocks)
- [ ] Verify `as_of_date` is 2025-11-14 or later

### 3.2: API Verification
- [ ] GET `/api/valuation/AAPL`
- [ ] Verify all 7 metrics returned:
  - `pe_ratio_trailing`
  - `pe_ratio_forward`
  - `pb_ratio`
  - `ps_ratio`
  - `peg_ratio`
  - `dividend_yield`
  - `payout_ratio`
- [ ] GET `/api/watchlist`
- [ ] Verify `score_components` includes valuation sub-scores
- [ ] Verify valuation sub-scores are NOT "N/A"

### 3.3: UI Verification
- [ ] Navigate to watchlist page
- [ ] Expand first stock (e.g., AAPL)
- [ ] Screenshot expanded view
- [ ] Verify valuation metrics visible:
  - P/E Ratio displayed
  - P/B Ratio displayed
  - P/S Ratio displayed
  - NOT showing "N/A" or "—"
- [ ] Verify "Valuation" score component shows actual score (not N/A)
- [ ] Test with 3-5 different stocks

**Browser Automation Test**:
```bash
# Screenshot watchlist
node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
  http://192.168.8.233:3000/watchlist /tmp/watchlist-before-expand.png

# Expand AAPL row and screenshot
node ~/portfolio-ai/.claude/skills/browser-automation/scripts/expand-and-screenshot.js \
  http://192.168.8.233:3000/watchlist AAPL /tmp/watchlist-aapl-expanded.png

# Check for "N/A" in page content
node ~/portfolio-ai/.claude/skills/browser-automation/scripts/execute.js \
  http://192.168.8.233:3000/watchlist \
  "document.body.innerText.includes('N/A') ? 'Found N/A' : 'No N/A found'"
```

**Expected Result**: Valuation metrics display with actual numbers, no N/A

---

## Task 4: Verify Market Data Currency (30 min)

**Priority**: P1 - HIGH
**Objective**: Ensure all market data shows current dates (Nov 14+, not Nov 12)

### 4.1: Check Data Timestamps
- [ ] GET `/api/market/intelligence`
- [ ] Verify `timestamp` field is recent (within 1 hour)
- [ ] Check `sp500.as_of_date` is current
- [ ] Check `vix.as_of_date` is current
- [ ] Check sector data has current dates

### 4.2: Check UI Display
- [ ] Screenshot Market Conditions card
- [ ] Verify "Updated just now" or recent timestamp
- [ ] Verify "Market Data as of [DATE]" shows Nov 14 or later
- [ ] Check sector rotation shows current data
- [ ] Check key indicators show current data

### 4.3: Check Backend Cache
- [ ] Review Redis cache TTL for market data
- [ ] Verify cache invalidation working
- [ ] Check if old cache entries exist
- [ ] Clear stale cache if found

**Cache Check**:
```bash
# Check Redis for market intelligence cache
redis-cli KEYS "*market*intelligence*"
redis-cli GET "cache:market_intelligence" | jq '.timestamp'
```

**Expected Result**: All dates are Nov 14 or later, no Nov 12 data

---

## Task 5: E2E User Journey Test (1 hour)

**Priority**: P1 - HIGH
**Objective**: Simulate complete user flow through dashboard → watchlist → data verification

### 5.1: Dashboard Journey
- [ ] Load dashboard at http://192.168.8.233:3000/
- [ ] Verify page loads without errors (check console)
- [ ] Verify Fear & Greed score displays
- [ ] Verify Market Health score displays
- [ ] Verify all key indicators load
- [ ] Verify sector rotation loads
- [ ] Verify no "data is X days old" warnings
- [ ] Screenshot full dashboard

### 5.2: Watchlist Journey
- [ ] Navigate to /watchlist
- [ ] Verify all symbols load
- [ ] Verify scores display for each symbol
- [ ] Expand 3 different stocks
- [ ] Verify valuation metrics for each
- [ ] Verify technical/fundamental scores show sub-scores
- [ ] Screenshot 3 expanded stocks

### 5.3: Data Consistency Check
- [ ] Compare API data to UI display
- [ ] Verify Fear & Greed score matches between API and UI
- [ ] Verify valuation metrics match between API and UI
- [ ] Verify timestamps consistent across all sources
- [ ] Document any discrepancies

**Full Journey Script**:
```bash
#!/bin/bash
BASE_URL="http://192.168.8.233:3000"

# Dashboard
node .claude/skills/browser-automation/scripts/screenshot.js $BASE_URL /tmp/e2e-dashboard.png --full-page
node .claude/skills/browser-automation/scripts/console.js $BASE_URL 5000 > /tmp/e2e-dashboard-console.txt

# Watchlist
node .claude/skills/browser-automation/scripts/screenshot.js $BASE_URL/watchlist /tmp/e2e-watchlist.png --full-page
node .claude/skills/browser-automation/scripts/console.js $BASE_URL/watchlist 5000 > /tmp/e2e-watchlist-console.txt

# Expanded stocks
for symbol in AAPL NVDA MSFT; do
  node .claude/skills/browser-automation/scripts/expand-and-screenshot.js \
    $BASE_URL/watchlist $symbol /tmp/e2e-$symbol.png
done

# Network monitoring for API calls
node .claude/skills/browser-automation/scripts/network.js $BASE_URL 30000 "/api/" > /tmp/e2e-network.txt
```

**Expected Result**: Full journey completes without errors, all data current and accurate

---

## Task 6: Create Verification Report (30 min)

**Priority**: P2 - MEDIUM
**Objective**: Document all findings and create pass/fail report

### 6.1: Compile Results
- [ ] Gather all verification evidence:
  - Database query results
  - API responses
  - UI screenshots
  - Console logs
  - Network traces
- [ ] Create summary table of all tests
- [ ] Document any failures or issues found
- [ ] Calculate pass rate (target: 100%)

### 6.2: Create Evidence Archive
- [ ] Organize all screenshots in `/tmp/e2e-verification/`
- [ ] Save all API responses as JSON
- [ ] Save all database queries and results
- [ ] Create README with test execution details

### 6.3: Generate Report
- [ ] Create `E2E_VERIFICATION_REPORT.md`
- [ ] Include pass/fail for each test
- [ ] Include evidence (screenshots, data samples)
- [ ] Include recommendations if issues found
- [ ] Include "Production Ready" or "Needs Fixes" conclusion

**Report Template**:
```markdown
# E2E Verification Report
**Date**: 2025-11-14
**Tester**: Claude Code (Autonomous)
**Duration**: [X hours]

## Executive Summary
- Total Tests: [X]
- Passed: [X]
- Failed: [X]
- Pass Rate: [X%]
- **Conclusion**: [Production Ready / Needs Fixes]

## Test Results

### Task 0: Scheduled Tasks
- [x] Beat running: PASS
- [x] All 5 tasks scheduled: PASS
- [x] Tasks executing on time: PASS

### Task 1: Fear & Greed Freshness
- [x] Database current: PASS
- [x] API returns current data: PASS
- [x] UI shows current data: PASS
- [x] No stale warnings: PASS

[...continue for all tasks...]

## Evidence
[Screenshots, queries, API responses]

## Issues Found
[None / List of issues]

## Recommendations
[None needed / Action items]
```

---

## Relevant Files

**Testing**:
- `/tmp/e2e-verification/` (all evidence)
- `tasks/E2E_VERIFICATION_REPORT.md` (results)

**Data Sources**:
- Database: `fear_greed_inputs`, `fear_greed_daily`, `fear_greed_components`, `reference_cache`
- API: `/api/market/intelligence`, `/api/valuation/*`, `/api/watchlist`
- UI: http://192.168.8.233:3000/ (dashboard, watchlist)

**Services**:
- Celery Beat (scheduled tasks)
- Celery Worker (task execution)
- Backend API (FastAPI)
- Frontend (Next.js)

---

## Acceptance Criteria

- [ ] All scheduled tasks running on time (0 missed executions)
- [ ] Fear & Greed data is CURRENT (no "X days old" warnings)
- [ ] All 5 Fear & Greed components populated in database
- [ ] Valuation data displays in watchlist (P/E, P/B, P/S visible)
- [ ] No "N/A" for valuation metrics
- [ ] Market data shows Nov 14+ dates (not Nov 12)
- [ ] All API endpoints return current data
- [ ] UI displays match API data (consistency)
- [ ] No console errors in browser
- [ ] No 404/500 errors in network trace
- [ ] E2E verification report shows 100% pass rate

**Definition of Done**:
- All tests executed
- All tests passing (100% pass rate)
- Evidence collected and archived
- Report generated
- "Production Ready" conclusion OR issues documented with fix plan

---

**Estimated Total Effort**: 4.5 hours

**Execution Mode**: Use `/do_it --max` for parallel execution and maximum speed
