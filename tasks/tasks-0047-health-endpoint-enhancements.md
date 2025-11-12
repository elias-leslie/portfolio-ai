# Task 0047: Health Endpoint and Status Page Enhancements

**Created**: 2025-11-11
**Status**: In Progress
**Priority**: Medium
**Complexity**: MEDIUM (40%)

## Summary

### Goal
Enhance the /health endpoint with more detailed system checks and add corresponding UI components to the status page to provide better visibility into system health metrics.

### Approach
- Add new /health/detailed endpoint with comprehensive system checks
- Create new frontend components following existing card patterns
- Integrate seamlessly with existing status page layout
- Maintain backwards compatibility with existing /health endpoint

### Scope Discovery
✅ Examined existing health check infrastructure (health.py, health_checks.py)
✅ Analyzed current status page components and patterns
✅ Identified database schema (day_bars table structure)
✅ Reviewed resource monitoring utilities (psutil usage)
✅ Checked celery worker inspection patterns

## Tasks

### Backend: Add Detailed Health Checks

- [x] Create helper functions in `backend/app/utils/health_checks.py`:
  - [x] `get_day_bars_freshness()` - Query day_bars table for latest data per ticker
  - [x] `get_celery_worker_status()` - Check celery worker active status
  - [x] `get_api_key_status()` - Validate configured API keys
  - [x] Add internal dataclass models for new check results

- [x] Add `/health/detailed` endpoint in `backend/app/api/health.py`:
  - [x] Create Pydantic response models (DayBarsFreshness, CeleryWorkerStatus, APIKeyStatus)
  - [x] Create DetailedHealthCheckResponse model
  - [x] Implement endpoint handler
  - [x] Include disk space info from existing resource_monitor
  - [x] Maintain backwards compatibility with existing /health endpoint

### Frontend: Create New UI Components

- [x] Create `frontend/components/status/DataFreshnessCard.tsx`:
  - [x] Display day_bars freshness per ticker in table format
  - [x] Show last updated timestamp
  - [x] Color code based on data age (green <1d, yellow 1-7d, red >7d)
  - [x] Follow existing card pattern (collapsible sections)
  - [x] Add loading and error states

- [x] Create `frontend/components/status/APIKeysCard.tsx`:
  - [x] Display configured API keys with validation status
  - [x] Show which keys are active vs not configured
  - [x] Include rate limits and validation details
  - [x] Use icons for validation status (check/x)
  - [x] Follow DataSourcesCard pattern

- [x] Update `frontend/components/status/ResourceCard.tsx`:
  - [x] Already supports disk space (currently rendered on status page)
  - [x] Verify disk space info flows from /health/detailed

- [x] Update `frontend/app/status/page.tsx`:
  - [x] Add DataFreshnessCard to appropriate section
  - [x] Add APIKeysCard after API Quotas section
  - [x] Add celery worker active status to Celery Monitoring section
  - [x] Fetch from /health/detailed endpoint
  - [x] Handle loading states

- [x] Update `frontend/lib/api/status.ts`:
  - [x] Add TypeScript interfaces for new data types
  - [x] Add fetchDetailedHealth() function
  - [x] Export new types for component usage

## Verification

### Functional Testing
- [ ] **(LOCAL)** Start backend and verify /health/detailed endpoint returns expected data
- [ ] **(LOCAL)** Verify day_bars freshness shows accurate data for all tickers
- [ ] **(LOCAL)** Verify celery worker status shows correct active/inactive state
- [ ] **(LOCAL)** Verify API key validation shows correct configured/not configured status
- [ ] **(LOCAL)** Verify disk space appears in resource section
- [ ] **(LOCAL)** Test status page loads without errors
- [ ] **(LOCAL)** Test new cards display correctly with real data
- [ ] **(LOCAL)** Test error handling when day_bars table is empty

### Tests
- [ ] **(LOCAL)** Add unit tests for new health check functions
- [ ] **(LOCAL)** Add API tests for /health/detailed endpoint
- [ ] **(LOCAL)** Run full test suite: `cd ~/portfolio-ai/backend && pytest tests/ -v`
- [ ] **(LOCAL)** Verify all 508 tests still pass

### Code Quality
- [ ] **(CLOUD)** Run linting: `~/portfolio-ai/scripts/lint.sh`
- [ ] **(CLOUD)** Verify mypy type checking passes
- [ ] **(CLOUD)** Check file sizes (<500 lines soft, <800 hard limit)
- [ ] **(CLOUD)** Verify no duplicate code introduced
- [ ] **(CLOUD)** All functions have type hints

### Documentation
- [ ] **(CLOUD)** Code comments explain new health checks
- [ ] **(CLOUD)** API endpoint documented with docstrings
- [ ] **(CLOUD)** Component props documented with JSDoc

## Technical Details

### Database Queries

**day_bars freshness**:
```sql
SELECT ticker, MAX(date) as last_updated
FROM day_bars
GROUP BY ticker
ORDER BY ticker;
```

**Expected output**: List of (ticker, last_date) tuples

### API Key Validation

Leverage existing `get_api_quotas()` function which already checks configuration status via environment variables. Extend with validation ping where possible.

### Celery Worker Status

Use existing `check_celery_worker()` from service_monitor with inspect enabled to get detailed worker stats.

### Response Structure

```json
{
  "status": "healthy",
  "timestamp": "2025-11-11T10:00:00Z",
  "uptime_seconds": 3600,
  "checks": {...},
  "sources": {...},
  "services": {...},
  "day_bars_freshness": [
    {"ticker": "AAPL", "last_updated": "2025-11-10", "age_days": 1},
    {"ticker": "MSFT", "last_updated": "2025-11-09", "age_days": 2}
  ],
  "celery_worker": {
    "active": true,
    "pool_size": 4,
    "active_tasks": 2
  },
  "api_keys": [
    {"source": "polygon", "configured": true, "valid": true},
    {"source": "finnhub", "configured": false, "valid": false}
  ],
  "disk_usage": {
    "total_gb": 100,
    "used_gb": 45,
    "free_gb": 55,
    "percent_used": 45,
    "status": "ok"
  }
}
```

## Deliverables

- [x] Task file created and committed
- [x] Backend health check functions implemented
- [x] /health/detailed endpoint implemented
- [x] DataFreshnessCard component created
- [x] APIKeysCard component created
- [x] Status page integrated with new components
- [x] TypeScript types updated
- [x] All changes committed and pushed
- [x] Handoff document created for local testing

## Notes

- Keep existing /health endpoint unchanged for backwards compatibility
- Use existing patterns from DataSourcesCard and APIQuotasCard
- Celery worker check already exists, just need to expose in detailed endpoint
- Disk space already monitored via resource_monitor, just need to include in response
- day_bars table may be empty for new installs - handle gracefully
