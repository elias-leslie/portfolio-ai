# Task List: Data Freshness Investigation

**Created**: 2025-12-04
**Status**: COMPLETE
**Priority**: HIGH
**Effort**: MEDIUM
**Completed**: 2025-12-04

---

## Summary

Investigated and fixed data freshness display issues. **Key finding**: Backend data was FRESH all along - the issue was in multiple caching layers serving stale cached data despite fresh database.

### Root Causes Fixed

1. **Frontend React Query staleness too long** - F&G was 5hrs stale max, Portfolio 20min stale max
2. **No cache invalidation after Celery tasks** - Response cache persisted stale data
3. **Redis F&G cache TTL too long** - 1hr TTL when data updates daily

### Files Modified

**Backend:**
- `backend/app/middleware/cache.py` - Added `invalidate_market_data_cache()`, `invalidate_fear_greed_cache()`
- `backend/app/market/fear_greed_stub.py` - Added `invalidate_fear_greed_redis_cache()`, reduced TTL to 30min
- `backend/app/tasks/indicators/fear_greed.py` - Added FastAPI cache invalidation after F&G calculation

**Frontend:**
- `frontend/lib/hooks/useFearGreed.ts` - Reduced staleTime to 30min, refetchInterval to 1hr
- `frontend/lib/hooks/useMarket.ts` - Reduced staleTime to 2min, refetchInterval to 5min (conditions) and 2min (prices)
- `frontend/lib/hooks/usePortfolio.ts` - Reduced staleTime to 2min, refetchInterval to 5min

### Verification

All tables confirmed FRESH via `/api/status/table-freshness`:
- day_bars: 24h (yesterday's close - expected)
- fear_greed_daily: 24h (expected)
- technical_indicators: 0.4h (very fresh)
- news_cache: 0.5h (very fresh)
- watchlist_snapshots: 1h (fresh)

---

## 0.0 Scope Discovery (MANDATORY)

- [x] 0.1 Use Explore agent (very thorough) to investigate UI data display
  - Found 20+ components with timestamps
  - All timestamps from API (backend-calculated)
  - Timezone handling for watchlist only

- [x] 0.2 Use Explore agent (very thorough) to check backend data freshness
  - All tables FRESH (day_bars 24h, fear_greed 24h, news 5h, watchlist 6h)
  - Celery beat schedules correctly configured
  - Tasks running without issues

- [x] 0.3 Use Explore agent (very thorough) to trace data flow
  - Fear & Greed: Celery → fear_greed_daily → API → frontend
  - News: Continuous → news_cache → API → frontend
  - Technical: Celery 02:30 UTC → technical_indicators → watchlist API

- [x] 0.4 Use Explore agent (very thorough) to check caching issues
  - **Found 16 caching issues across Redis, Response Cache, React Query**
  - Critical: F&G 5hr max staleness, Portfolio 20min max staleness
  - No cache invalidation when Celery tasks complete

---

## 1.0 Fix Data Freshness Display

- [x] 1.1 Fix any discovered timestamp issues - N/A (timestamps were correct)
- [x] 1.2 Fix any discovered cache issues
  - Added cache invalidation functions to backend
  - Reduced frontend staleness times
  - Reduced Redis F&G TTL
- [x] 1.3 Fix any discovered scheduling issues - N/A (schedules were correct)
- [x] 1.4 Verify all scheduled tasks run correctly - Confirmed via API
- [x] 1.5 Test UI shows current data - Screenshot verified

---

## 2.0 Verification

- [x] 2.1 Check dashboard shows today's date for relevant data
  - Shows "Updated 19h ago" which is correct for Dec 3 close data on Dec 4
- [x] 2.2 Check scheduled tasks complete without errors
  - All tasks properly scheduled and running
- [x] 2.3 Browser screenshot verification of dashboard
  - Dashboard screenshot captured, showing F&G 64 (Greed), market data loading
