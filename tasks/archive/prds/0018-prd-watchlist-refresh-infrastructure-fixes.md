# PRD #0018: Watchlist Refresh Infrastructure & Market Hours Handling Fixes

**Status**: Ready for Implementation
**Owner**: Portfolio AI Platform
**Created**: 2025-10-30
**Audience**: Junior developers
**Priority**: CRITICAL
**Complexity**: MEDIUM
**Dependencies**: PRD #0014 Phase 1 (complete), PRD #0016 (complete)
**Blocks**: PRD #0019 (watchlist intelligence layer)

---

## 1. Introduction / Overview

The Watchlist Intelligence Hub UI is functional but the underlying refresh infrastructure is **completely broken**. Users see stale data from hours ago with no updates, creating a dangerous situation where investment decisions could be made on outdated information.

**Critical Issues Discovered**:
1. **Manual refresh button non-functional** - Clicking "Refresh" doesn't update any data or timestamps
2. **Auto-refresh completely broken** - Data stays frozen for 5+ hours despite 15-minute configured interval
3. **Market hours awareness missing** - Tickers marked "stale" immediately at 4:30 PM market close
4. **Batch updates non-atomic** - Timestamps spread over 2.5 hours (1:55 PM - 4:30 PM)
5. **Price fetching sporadic** - Only AAPL has recent data, others stuck hours old
6. **Timezone handling inconsistent** - Table shows "4:30 PM EDT", expanded shows "10:38 PM" (6 hour diff)

**This PRD fixes the refresh infrastructure** before PRD #0019 adds scoring features. Without working refresh, adding more features just adds more broken functionality.

---

## 2. Goals

1. **Fix manual refresh** - Button triggers immediate update for ALL tickers with unified timestamp
2. **Fix auto-refresh** - React Query + Celery both work, respecting user-configured intervals
3. **Implement market hours awareness** - Don't mark data stale during after-hours/weekends
4. **Fix batch processing** - All tickers update atomically, single completion timestamp
5. **Fix timezone handling** - Consistent UTC storage, correct user timezone display
6. **Add visual staleness indicators** - Red badge only for truly stale data (>24 hours old)
7. **Ensure Celery reliability** - Worker runs continuously, tasks execute on schedule

---

## 3. User Stories

- **As a user**, when I click "Refresh", I want all tickers to update immediately and show the same completion timestamp
- **As a user**, I want auto-refresh to work at my configured interval (1m, 5m, 15m) without manual intervention
- **As a user**, I want after-hours data to stay fresh (not marked stale) since markets are closed and prices can't change
- **As a user**, I want consistent timestamps across table and expanded views so I can trust the data age
- **As a developer**, I want Celery tasks to run reliably so I can debug refresh issues when they occur
- **As a user**, I want clear visual indicators when data is truly stale (>24 hours) so I know not to trade on it

---

## 4. Functional Requirements

### 4.1 Manual Refresh Button Fix

**4.1.1** Debug current refresh endpoint `/api/watchlist/refresh`:
- Check if API call is reaching backend (add logging)
- Verify WatchlistService.refresh_scores() is being called
- Confirm database transaction commits (PostgreSQL COMMIT logged)
- Test with single ticker first, then batch

**4.1.2** Fix frontend React Query cache invalidation:
- After successful refresh API call, invalidate `['watchlist']` query key
- Force immediate refetch with `{ refetchType: 'active' }`
- Show loading state during refresh (disable button, show spinner)
- Display success toast with count: "Refreshed 12 tickers"

**4.1.3** Implement atomic batch update:
- Process all tickers in service
- Store results in memory first (don't commit individually)
- Once ALL tickers processed, single database transaction commits all
- Set unified `refreshed_at` timestamp for entire batch
- Return batch metadata: `{ ticker_count: 12, refreshed_at: '2025-10-30T20:35:00Z', failed: [] }`

**4.1.4** Add request timeout handling:
- Refresh endpoint timeout: 60 seconds (allows ~3s per ticker for 20 tickers)
- If timeout occurs, return partial results + warning
- Log which tickers failed, user can retry

### 4.2 Auto-Refresh System Fix

**4.2.1** Fix React Query auto-refresh configuration:
```typescript
// In useWatchlist hook
useQuery({
  queryKey: ['watchlist'],
  refetchInterval: userPreferences.refresh_interval_ms, // From user settings
  refetchIntervalInBackground: true, // Keep refreshing when tab inactive
  staleTime: 60000, // 1 minute (data fresh for 1 min, then refetch)
})
```

**4.2.2** Ensure Celery worker is running:
- Add systemd service file for Celery worker (auto-restart on crash)
- Configure worker: `celery -A app.celery_app worker --loglevel=info --concurrency=4`
- Add health check endpoint: `/api/health/celery` returns worker status
- Log worker startup and task executions

**4.2.3** Fix Celery scheduled task `refresh_watchlist_periodic`:
- Schedule: every 15 minutes during market hours (9:30 AM - 4:30 PM ET)
- Task implementation:
  ```python
  @celery_app.task
  def refresh_watchlist_periodic():
      if not is_market_hours():
          logger.info("Skipping refresh - market closed")
          return
      service = WatchlistService()
      result = service.refresh_scores_all()
      logger.info(f"Periodic refresh complete: {result}")
  ```

**4.2.4** Add task monitoring:
- Log every task execution (start time, duration, result)
- Track task failures in database (`celery_task_log` table)
- Expose metrics via `/api/health/celery`: last_run, next_run, failure_count

### 4.3 Market Hours Awareness

**4.3.1** Create `market_hours.py` utility module:
```python
from datetime import datetime, time
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

def is_market_hours(dt: datetime | None = None) -> bool:
    """Check if given datetime (or now) is during market hours."""
    if dt is None:
        dt = datetime.now(NY_TZ)
    if dt.weekday() >= 5:  # Weekend
        return False
    if dt.time() < MARKET_OPEN or dt.time() >= MARKET_CLOSE:
        return False
    # TODO: Check market holidays from calendar
    return True

def is_stale(fetched_at: datetime, now: datetime | None = None) -> bool:
    """Determine if data is stale based on market hours."""
    if now is None:
        now = datetime.now(ZoneInfo("UTC"))

    age = now - fetched_at

    if is_market_hours(now):
        # During market hours: stale if >15 minutes old
        return age.total_seconds() > 900
    else:
        # After hours/weekends: stale if >24 hours old
        return age.total_seconds() > 86400
```

**4.3.2** Update `WatchlistService.calculate_scores()`:
- Don't mark scores as stale using `is_stale()` logic
- Store `is_stale` flag in watchlist_snapshots
- Frontend reads flag to show red badge

**4.3.3** Update frontend staleness badge:
```typescript
// Only show "stale" badge if truly stale
{item.is_stale && (
  <Badge variant="destructive">Stale (>24h)</Badge>
)}
```

### 4.4 Timezone Handling Consistency

**4.4.1** Database storage - always UTC:
- All TIMESTAMPTZ columns store UTC
- PostgreSQL handles timezone conversion automatically
- Never store local timezones in database

**4.4.2** API responses - always UTC with timezone info:
```python
# In Pydantic models
class WatchlistSnapshot(BaseModel):
    refreshed_at: datetime  # Serializes as ISO 8601 with Z suffix

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + 'Z' if v.tzinfo is None else v.isoformat()
        }
```

**4.4.3** Frontend display - user's local timezone:
```typescript
// Use date-fns with automatic timezone detection
import { formatInTimeZone } from 'date-fns-tz';

const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
const displayTime = formatInTimeZone(
  item.refreshed_at,
  userTimezone,
  'MMM dd, h:mm a zzz'
); // "Oct 30, 4:30 PM EDT"
```

**4.4.4** Consistency check:
- Table "Updated" column: user timezone
- Expanded "Updated" field: same user timezone
- Both should show identical time for same data

### 4.5 Price Fetching Reliability

**4.5.1** Fix multi-source failover for all tickers:
- Current issue: Only AAPL gets fresh data
- Root cause: Batch processing stops on first failure
- Solution: Catch exceptions per ticker, continue batch

```python
def refresh_scores_all(self) -> dict:
    results = {"success": [], "failed": []}

    for item in self.get_all_watchlist_items():
        try:
            snapshot = self.refresh_single_ticker(item.symbol)
            results["success"].append(item.symbol)
        except Exception as e:
            logger.error(f"Failed to refresh {item.symbol}: {e}")
            results["failed"].append({"symbol": item.symbol, "error": str(e)})

    return results
```

**4.5.2** Add retry logic for transient failures:
- Retry 3 times with exponential backoff (2s, 4s, 8s)
- Only for network errors (timeout, connection refused)
- Don't retry for invalid symbols or API quota errors

**4.5.3** Log multi-source fallback:
```python
logger.info(f"Fetched {symbol} from {source_used} after {attempts} attempts")
# Example: "Fetched AMZN from twelvedata after 2 attempts (yfinance failed: timeout)"
```

### 4.6 Error Handling & User Feedback

**4.6.1** Refresh endpoint error responses:
- 200 OK: Full success, all tickers updated
- 207 Multi-Status: Partial success, some tickers failed
  ```json
  {
    "success_count": 10,
    "failed_count": 2,
    "failed": [
      {"symbol": "INVALID", "error": "Symbol not found"},
      {"symbol": "GOOGL", "error": "API quota exceeded"}
    ],
    "refreshed_at": "2025-10-30T20:35:00Z"
  }
  ```
- 500 Internal Server Error: Complete failure, no updates

**4.6.2** Frontend error handling:
```typescript
const handleRefresh = async () => {
  try {
    const result = await refreshWatchlist();

    if (result.failed_count > 0) {
      toast.warning(
        `Refreshed ${result.success_count} tickers. ${result.failed_count} failed.`,
        { description: result.failed.map(f => f.symbol).join(', ') }
      );
    } else {
      toast.success(`Refreshed ${result.success_count} tickers`);
    }
  } catch (error) {
    toast.error('Refresh failed', { description: error.message });
  }
};
```

**4.6.3** Add loading states:
- Manual refresh: Disable button, show spinner, update button text "Refreshing..."
- Auto-refresh: Small indicator in header "Auto-refreshing..." (don't block UI)
- Per-ticker: Show refresh icon spinning for in-progress updates

### 4.7 Testing & Validation

**4.7.1** Unit tests for market hours logic:
```python
def test_is_market_hours_during_trading():
    # Wednesday 10:30 AM ET
    dt = datetime(2025, 10, 29, 14, 30, tzinfo=ZoneInfo("UTC"))
    assert is_market_hours(dt) == True

def test_is_market_hours_after_close():
    # Wednesday 5:00 PM ET
    dt = datetime(2025, 10, 29, 21, 0, tzinfo=ZoneInfo("UTC"))
    assert is_market_hours(dt) == False

def test_is_market_hours_weekend():
    # Saturday 10:30 AM ET
    dt = datetime(2025, 11, 1, 14, 30, tzinfo=ZoneInfo("UTC"))
    assert is_market_hours(dt) == False
```

**4.7.2** Integration test for refresh workflow:
```python
def test_refresh_workflow_end_to_end():
    # Add test tickers
    service.add_ticker("AAPL")
    service.add_ticker("GOOGL")

    # Trigger refresh
    result = service.refresh_scores_all()

    # Verify all updated
    assert result["success_count"] == 2
    assert result["failed_count"] == 0

    # Verify timestamps match
    items = service.get_all_watchlist_items()
    timestamps = [item.refreshed_at for item in items]
    assert len(set(timestamps)) == 1  # All same timestamp
```

**4.7.3** Manual testing checklist:
1. Click "Refresh" → all tickers update to same timestamp
2. Wait for auto-refresh interval → data updates automatically
3. After 4:30 PM → tickers not marked stale
4. Check Celery logs → tasks executing on schedule
5. Expand row → timestamp matches table timestamp
6. Check different timezones → display adjusts correctly

---

## 5. Non-Goals (Out of Scope)

- **Historical data backfill** - Covered in PRD #0019
- **Sentiment scoring** - Covered in PRD #0019
- **Fundamental metrics** - Covered in PRD #0019
- **Market holiday calendar** - Simplified: weekends only (expand later)
- **Real-time streaming** - Keep polling model, fix reliability first
- **Custom refresh intervals per ticker** - Global setting only

---

## 6. Design Considerations

**6.1 UI Visual Changes**

**Staleness Badge**:
- Current: Shows "stale" immediately at market close
- Fixed: Only shows after 24 hours during after-hours
- Color: Red `destructive` variant only for true staleness

**Refresh Button States**:
```typescript
<Button
  variant="outline"
  disabled={isRefreshing}
  onClick={handleRefresh}
>
  {isRefreshing ? (
    <><Loader2 className="animate-spin" /> Refreshing...</>
  ) : (
    <><RefreshCw /> Refresh</>
  )}
</Button>
```

**Auto-Refresh Indicator**:
- Small text in header: "Auto-refresh: ON (every 15m)"
- Next refresh countdown: "Next: in 12:34"
- Disable during manual refresh to avoid conflicts

**6.2 Performance Targets**

- Manual refresh: Complete 50 tickers in <30 seconds
- Auto-refresh: No UI lag (background process)
- Timestamp update: <100ms database query
- Market hours check: <1ms (pure calculation)

**6.3 Database Schema Changes**

Minimal changes to watchlist_snapshots:
```sql
ALTER TABLE watchlist_snapshots ADD COLUMN is_stale BOOLEAN DEFAULT FALSE;
```

Add Celery task logging table:
```sql
CREATE TABLE celery_task_log (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(255) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR(50), -- 'success', 'failure', 'timeout'
    result_json JSONB,
    error_message TEXT
);
```

---

## 7. Technical Considerations

**7.1 Celery Configuration**

**Backend celery_app.py**:
```python
from celery import Celery
from celery.schedules import crontab

celery_app = Celery('portfolio_ai', broker='redis://localhost:6379/0')

celery_app.conf.beat_schedule = {
    'refresh-watchlist-periodic': {
        'task': 'app.tasks.watchlist_tasks.refresh_watchlist_periodic',
        'schedule': crontab(minute='*/15', hour='9-16', day_of_week='1-5'),
        # Every 15 minutes, 9 AM - 4 PM, Monday-Friday
    },
}
```

**Systemd service** (`/etc/systemd/system/celery-worker.service`):
```ini
[Unit]
Description=Celery Worker for Portfolio AI
After=network.target redis.service postgresql.service

[Service]
Type=forking
User=kasadis
Group=kasadis
WorkingDirectory=/home/kasadis/portfolio-ai/backend
Environment="PATH=/home/kasadis/portfolio-ai/backend/.venv/bin"
ExecStart=/home/kasadis/portfolio-ai/backend/.venv/bin/celery -A app.celery_app worker --loglevel=info --concurrency=4 --detach
ExecStop=/bin/kill -TERM $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

**7.2 Error Recovery Strategies**

**Database connection lost**:
- Celery retries task automatically (3 attempts)
- Connection pool handles reconnection
- Log error, continue with next ticker

**Redis unavailable**:
- Celery worker exits (systemd restarts it)
- Frontend shows "Background tasks unavailable" warning
- Manual refresh still works (doesn't use Celery)

**API quota exceeded**:
- Catch `QuotaExceededError`
- Skip remaining tickers for this source
- Use next source in priority chain
- Log warning with quota reset time

**7.3 Timezone Handling Libraries**

**Backend**: Use Python 3.9+ `zoneinfo` (stdlib, no extra dependencies)
**Frontend**: Use `date-fns-tz` (lightweight, tree-shakeable)
- Add to package.json: `"date-fns-tz": "^2.0.0"`

**7.4 Backwards Compatibility**

- Existing watchlist items continue to work
- Old snapshots without `is_stale` column: default to `False`
- Frontend gracefully handles missing `refreshed_at` timestamps

---

## 8. Success Metrics

**8.1 Functional Success**
- Manual refresh: ALL tickers update to same timestamp (verified in UI)
- Auto-refresh: Data updates every 15 minutes without manual intervention
- Market hours: Tickers not marked stale at 4:30 PM, marked stale after 24 hours
- Timezone: Table and expanded view show identical timestamps
- Batch processing: All tickers complete in <30 seconds

**8.2 Reliability**
- Celery worker uptime: 99%+ (systemd keeps it running)
- Refresh success rate: 95%+ (5% tolerance for API failures)
- Zero "stuck" tickers: no ticker >24 hours old during market days
- Zero timezone bugs: no 6-hour discrepancies

**8.3 User Experience**
- Loading states: Visible during refresh (button disabled, spinner)
- Error feedback: Toast shows specific error for failed tickers
- Staleness clarity: Red badge only when truly stale (>24h)
- Auto-refresh transparency: User can see next refresh countdown

---

## 9. Implementation Plan

**Phase 1: Manual Refresh Fix** (Day 1, ~4 hours)
- Task 1.1: Debug current refresh endpoint, add logging
- Task 1.2: Fix React Query cache invalidation
- Task 1.3: Implement atomic batch update
- Task 1.4: Add success/error toasts
- Deliverable: Manual refresh button works reliably

**Phase 2: Market Hours Awareness** (Day 1, ~3 hours)
- Task 2.1: Create market_hours.py utility
- Task 2.2: Update staleness logic in backend
- Task 2.3: Update staleness badge in frontend
- Task 2.4: Unit tests for market hours logic
- Deliverable: Tickers don't go stale at 4:30 PM

**Phase 3: Auto-Refresh & Celery** (Day 2, ~5 hours)
- Task 3.1: Fix React Query auto-refresh config
- Task 3.2: Create Celery systemd service
- Task 3.3: Implement periodic task with market hours check
- Task 3.4: Add Celery health check endpoint
- Task 3.5: Test Celery reliability (restart worker, check logs)
- Deliverable: Auto-refresh works every 15 minutes

**Phase 4: Timezone & Polish** (Day 2, ~3 hours)
- Task 4.1: Fix timezone handling (UTC storage, local display)
- Task 4.2: Add loading states and spinners
- Task 4.3: Improve error messages
- Task 4.4: Manual E2E testing checklist
- Deliverable: Production-ready refresh system

---

## 10. Open Questions

1. **Market holiday calendar**: Should we integrate NYSE holiday calendar API? (Decided: Phase 2, manual list for now)
2. **Refresh during pre-market/after-hours**: Should we support 4 AM - 9:30 AM, 4 PM - 8 PM? (Decided: No, regular hours only)
3. **Celery beat scheduler**: Run on same machine or separate? (Decided: Same machine, beat runs in worker process)
4. **Quota exceeded handling**: Pause refreshes until quota resets? (Decided: Yes, skip that source, retry next interval)
5. **User notification**: Email when refresh fails for >24 hours? (Decided: Phase 2, logs only for now)

---

## 11. Dependencies

**Required PRDs**:
- ✅ PRD #0014 Phase 1 (complete) - Database schema, API endpoints, frontend UI
- ✅ PRD #0016 (complete) - Multi-source price fetcher with 6 sources

**Blocks**:
- ⚠️ **PRD #0019** - Cannot add scoring features until refresh works

**Python Packages** (verify in requirements.txt):
- `celery>=5.3.0` (task queue)
- `redis>=5.0.0` (Celery broker)
- `tzdata>=2023.3` (timezone database for zoneinfo)

**Frontend Packages** (verify in package.json):
- `date-fns-tz>=2.0.0` (timezone-aware date formatting)

---

**Next Steps**: Use `/task_it tasks/0018-prd-watchlist-refresh-infrastructure-fixes.md` to generate detailed task breakdown, then `/do_it` to implement.

**After PRD #0018 complete**: Proceed to PRD #0019 (watchlist intelligence layer with scoring).
