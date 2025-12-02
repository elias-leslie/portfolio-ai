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

### 0.0 Scope Discovery (MANDATORY) ✅ COMPLETE

- [x] 0.1 Explore existing market hours code
  - Found: `market_hours.py` with `is_market_hours()` and `is_stale()` (no holidays)
  - Found: `data_freshness_service.py` with `_is_trading_day()` (weekdays only)
  - Found: 16+ scheduled tasks for market data
- [x] 0.2 Identify integration points
  - Backend: market_hours.py, data_freshness_service.py, market.py API
  - Frontend: Navigation.tsx for badge, new MarketStatusBadge component
  - Celery: Documentation updated in celery_schedules.py
- [x] 0.3 Checkpoint: Confirmed scope - 5 backend + 2 frontend files

### 1.0 Create Market Hours Service ✅ COMPLETE

- [x] 1.1 Extend existing `market_hours.py` with comprehensive functions
  - `is_market_open()`, `is_pre_market()`, `is_after_hours()`
  - `get_market_status()` -> "open" | "pre_market" | "after_hours" | "closed"
  - `get_last_trading_day()`, `get_next_trading_day()`
  - `is_trading_day(date)`, `is_market_holiday()`, `is_early_close_day()`
  - `get_hours_since_last_close()` for freshness calculations
- [x] 1.2 Add US market holiday calendar (2024-2026)
  - Static dict with all NYSE/NASDAQ holidays
  - Early close days handled (1 PM close)
- [x] 1.3 Market status tracking - Using functions (no table needed)
- [x] 1.4 Add API endpoint `/api/market/status` (1 min cache)

### 2.0 Update Freshness Monitoring with Market Awareness ✅ COMPLETE

- [x] 2.1 Added `get_market_aware_age_hours()` function
  - For market data: Uses `get_hours_since_last_close()`
  - Friday data still "fresh" on Sunday
- [x] 2.2 Updated `check_table_freshness()` to use market-aware age
- [x] 2.3 Uses `is_trading_day()` from market_hours (with holidays)
- [x] 2.4 Updated `status_data.py` /api/status/table-freshness endpoint
  - Added `is_market_data` flag to table configs
  - Uses `get_market_aware_age_hours()` for market data tables

### 3.0 Add Thrashing Protections to Self-Healing ✅ COMPLETE

- [x] 3.1 Created in-memory cooldown tracking (30 min)
  - `_remediation_cooldowns` dict with timestamps
  - `get_remediation_cooldowns()` for health endpoint visibility
- [x] 3.2 Updated `trigger_remediation()` with:
  - Cooldown check (skip if remediated in last 30 min)
  - Market hours check (skip market data if market closed)
  - Logging for skipped remediations
- [x] 3.3 Added `clear_remediation_cooldown()` for post-success cleanup
- [x] 3.4 Fixed Fear & Greed remediation task mapping
  - Changed fear_greed_daily/components to trigger `populate_fear_greed_inputs`
  - Was triggering `calculate_fear_greed` which only recalculates existing data
  - Now properly fetches new data then calculates

### 4.0 Add Market Status UI Indicator ✅ COMPLETE

- [x] 4.1 Created `MarketStatusBadge` component
  - Green pulsing dot + "Market Open"
  - Yellow dot + "Pre-Market" / "After Hours"
  - Gray dot + "Market Closed"
- [x] 4.2 Added to Navigation.tsx header (between utility links and theme toggle)
- [x] 4.3 Uses `apiRequest()` from existing API client
- [x] 4.4 Tooltip shows: current time ET, last/next trading day, holiday info

### 5.0 Update Scheduled Tasks with Market Awareness ✅ COMPLETE

- [x] 5.1 Market awareness integrated via data_freshness_service.py
  - Market data remediation skipped when market closed
  - Freshness uses market-aware age calculation
- [x] 5.2 Added market hours awareness documentation to celery_schedules.py
- [x] 5.3 Documented market hours integration at top of celery_schedules.py

---

## Verification ✅ ALL PASSED

- [x] Functional: Market status correctly identifies open/closed/pre/after
- [x] Functional: Holidays correctly marked as non-trading days (2024-2026 calendar)
- [x] Functional: Freshness shows "fresh" for last-trading-day data on weekends
- [x] Functional: Self-healing skips market data when market closed
- [x] Functional: UI shows correct market status indicator
- [x] Tests: 19/19 market hours unit tests passing
- [x] Quality: ruff + mypy passing
- [x] Services: Restarted and API verified (`/api/market/status` returns correct data)

---

## Relevant Files

**Modified:**
- `backend/app/utils/market_hours.py` - Extended with holiday calendar, status functions
- `backend/app/services/data_freshness_service.py` - Market-aware age, thrashing protection
- `backend/app/api/market.py` - Added `/api/market/status` endpoint
- `backend/app/celery_schedules.py` - Added market hours documentation
- `frontend/components/Navigation.tsx` - Added MarketStatusBadge

**Created:**
- `frontend/components/market/MarketStatusBadge.tsx` - Market status indicator component
