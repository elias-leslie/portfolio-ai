# Task List: Fix Capabilities Page - Backend Data Flow

**Source**: User request via /task_it (deep dive exploration findings)
**Complexity**: Medium
**Effort**: MEDIUM
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-30 23:45
**Completed**: 2025-11-30

---

## Summary

**Goal**: Make the Capabilities page functional - currently shows 0 items despite 118 records in database. Fix backend TypedDict definitions, Insights API 500 error, and API scanner garbage data.

**Status**: ✅ COMPLETE - All issues fixed, page displays data correctly.

---

## Completed Tasks

### 1.0 Fix CapabilityDict TypedDict (CRITICAL) ✅

- [x] 1.1 Read current `backend/app/api/types.py` and identify missing fields
- [x] 1.2 Add ALL db_capabilities columns to CapabilityDict (13 fields)
- [x] 1.3 Add ALL celery_capabilities columns to CapabilityDict (14 fields)
- [x] 1.4 Add ALL api_capabilities columns to CapabilityDict (9 fields)
- [x] 1.5 Test API returns full data - verified `table_name`, `row_count` present

### 2.0 Fix InsightDict Validation Error ✅

- [x] 2.1 Change `capability_id: int` to `capability_id: int | None`
- [x] 2.2 Add missing InsightDict fields (finding, expected_behavior, etc.)
- [x] 2.3 Test Insights API - returns 200 with all data

### 3.0 Fix API Scanner Garbage Data ✅

- [x] 3.1 Read `backend/app/services/capability_api_scanner.py`
- [x] 3.2 Identified issue: regex matches Python imports (from X import)
- [x] 3.3 Fixed parsing logic to:
  - Only search inside SQL string literals (quoted strings)
  - Filter out known Python module names
  - Added exclude list for common false positives
- [x] 3.4 New scans will produce clean data (existing data requires rescan)

### 4.0 Fix URL Redirect Issue ✅

- [x] 4.1 Confirmed frontend URLs missing trailing slashes cause 307 redirects
- [x] 4.2 Added trailing slashes to frontend API URLs in `capabilities.ts`:
  - `/api/capabilities/`
  - `/api/capabilities/insights/`
  - `/api/capabilities/notes/`

### 5.0 Verify Frontend Displays Data ✅

- [x] 5.1 Restart backend services
- [x] 5.2 Fixed tab counts using health summary (always fetched)
- [x] 5.3 Dashboard tab shows health summary cards (55 DB, 41 Tasks, 22 API)
- [x] 5.4 Database tab shows tables with full data
- [x] 5.5 Tasks tab shows Celery tasks with schedules, success rates
- [x] 5.6 Endpoints tab shows API endpoints
- [x] 5.7 Insights tab loads without 500 errors
- [x] 5.8 Fixed datetime serialization issue (added isoformat() conversion)

### 6.0 Fix Remaining Frontend Issues ✅

- [x] 6.1 Added `insightsCountData` query for Insights tab badge (always enabled)
- [x] 6.2 Tab badge now shows count without clicking tab first

---

## Files Modified

| File | Change |
|------|--------|
| `backend/app/api/types.py` | Added 30+ fields to CapabilityDict, fixed InsightDict |
| `backend/app/api/capabilities/database.py` | Added datetime→isoformat() conversion |
| `backend/app/services/capability_api_scanner.py` | Fixed depends_on_tables to only search SQL strings |
| `frontend/lib/api/capabilities.ts` | Added trailing slashes to API URLs |
| `frontend/app/capabilities/page.tsx` | Added health summary query, insights count query |

---

## Verification Results

- [x] API: `/api/capabilities/?type=db` returns full data including `table_name`, `row_count`
- [x] API: `/api/capabilities/insights/` returns 200 with all fields
- [x] API: `/api/capabilities/health/summary` returns correct totals
- [x] Frontend: Tab counts show 55, 41, 22 (confirmed by user)
- [x] Frontend: Insights badge shows count without clicking
- [x] Quality: mypy passes on modified files
