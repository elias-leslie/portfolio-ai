# Task List: Comprehensive Market Hours Awareness

**Source**: User request via /task_it
**Complexity**: Complex
**Effort**: MEDIUM-HIGH
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-01 09:20

---

## Summary

**Goal**: Add comprehensive market hours awareness throughout the solution to prevent thrashing, show accurate status, and make self-healing intelligent about when remediation makes sense.

**Approach**: Create centralized market hours service with historical tracking, integrate into freshness monitoring/self-healing, and add visual status indicator to UI.

**Scope Discovery**: Required - need to find all places where market hours awareness is needed

---

## Context

Current issues:
- Fear & Greed data shows "critical" (86h) after weekends when data IS current for last trading day
- Self-healing triggers remediation attempts when market is closed (wastes resources)
- No visual indicator showing market status to users
- Freshness thresholds don't account for non-trading days

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Explore existing market hours code
  - Find: `market_hours.py` and any existing market hours utilities
  - Find: All places that check market status or use `is_stale()`
  - Find: All scheduled tasks that depend on market hours
  - Find: All freshness checks that should be market-aware
- [ ] 0.2 Identify integration points
  - List: Backend services needing market awareness
  - List: Frontend components needing market status
  - List: Celery tasks that should skip on market closed
- [ ] 0.3 Checkpoint: Confirm scope
  - Files to modify: [TBD]
  - New files needed: [TBD]
  - Estimated effort: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Create Market Hours Service

- [ ] 1.1 Extend existing `market_hours.py` with comprehensive functions
  - `is_market_open()` - Real-time check (9:30 AM - 4:00 PM ET, Mon-Fri)
  - `is_pre_market()` - Pre-market hours (4:00 AM - 9:30 AM ET)
  - `is_after_hours()` - After hours (4:00 PM - 8:00 PM ET)
  - `get_market_status()` -> "open" | "pre_market" | "after_hours" | "closed"
  - `get_last_trading_day()` -> date of most recent trading day
  - `get_next_trading_day()` -> date of next trading day
  - `is_trading_day(date)` -> bool (accounts for weekends and US market holidays)
- [ ] 1.2 Add US market holiday calendar
  - Include: NYSE/NASDAQ holidays for current year + next year
  - Source: Static list or pandas_market_calendars if available
  - Handle: Early close days (day before Thanksgiving, Christmas Eve, etc.)
- [ ] 1.3 Create market status tracking table (optional)
  - Track: Last known market state, last trading day, next expected open
  - Use: For quick lookups without recalculating
- [ ] 1.4 Add API endpoint `/api/market/status`
  - Return: status, is_open, last_trading_day, next_trading_day, current_time_et
  - Cache: 1 minute TTL

### 2.0 Update Freshness Monitoring with Market Awareness

- [ ] 2.1 Modify `data_freshness_service.py`
  - Add: `get_expected_age_hours(table_name)` that accounts for non-trading days
  - For market data: Calculate hours since last trading day close, not calendar hours
  - Example: Friday close to Monday 10am = ~18 trading hours, not 62 calendar hours
- [ ] 2.2 Update `check_all_tables_freshness()`
  - Use market-aware age calculation for `market_data: True` tables
  - Only show "critical" if data older than last trading day
- [ ] 2.3 Update `status_data.py` table freshness endpoint
  - Apply same market-aware logic
  - Show actual trading day age vs calendar age

### 3.0 Add Thrashing Protections to Self-Healing

- [ ] 3.1 Create remediation rate limiter
  - Track: Last remediation attempt per table in memory or Redis
  - Rule: Don't retry same table within 30 minutes
  - Rule: Don't attempt market data remediation if market closed
- [ ] 3.2 Update `trigger_remediation()` in data_freshness_service.py
  - Check: Is market open? If not, skip market data remediation
  - Check: Was this table remediated recently? If so, skip
  - Log: Why remediation was skipped (for debugging)
- [ ] 3.3 Add remediation cooldown tracking
  - Store: `{table_name: last_remediation_time}`
  - Clear: On successful data refresh
  - Expose: In /health/detailed for visibility

### 4.0 Add Market Status UI Indicator

- [ ] 4.1 Create `MarketStatusBadge` component
  - Green dot + "Market Open" during trading hours
  - Yellow dot + "Pre-Market" / "After Hours" during extended hours
  - Red dot + "Market Closed" outside trading hours
  - Show: Current time in ET
- [ ] 4.2 Add to main layout header
  - Position: Top right, next to user menu or status area
  - Refresh: Every 30 seconds or on visibility change
- [ ] 4.3 Create `/api/market/status` frontend client
  - Add to `lib/api/market.ts`
  - Return typed MarketStatus interface
- [ ] 4.4 Add tooltip with details
  - Show: Last trading day, next trading day
  - Show: If holiday, which holiday

### 5.0 Update Scheduled Tasks with Market Awareness

- [ ] 5.1 Review all market-data scheduled tasks
  - List tasks that should skip on weekends/holidays
  - List tasks that should run regardless (news, system health)
- [ ] 5.2 Add market check to task preambles
  - Pattern: `if not is_trading_day() and task_requires_market: skip`
  - Log: "Skipping X - market closed"
- [ ] 5.3 Update celery_schedules.py comments
  - Document which tasks are market-aware
  - Document expected behavior on non-trading days

---

## Verification

- [ ] Functional: Market status correctly identifies open/closed/pre/after
- [ ] Functional: Holidays correctly marked as non-trading days
- [ ] Functional: Freshness shows "fresh" for last-trading-day data on weekends
- [ ] Functional: Self-healing skips market data when market closed
- [ ] Functional: UI shows correct market status indicator
- [ ] Tests: Unit tests for market hours calculations
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes
- [ ] Services: Restarted and verified

---

## Relevant Files

- `backend/app/utils/market_hours.py` - Existing market hours utilities
- `backend/app/services/data_freshness_service.py` - Freshness monitoring
- `backend/app/api/status_data.py` - Status page freshness endpoint
- `backend/app/celery_schedules.py` - Scheduled tasks
- `frontend/components/layout/Header.tsx` - Main header (add status badge)
