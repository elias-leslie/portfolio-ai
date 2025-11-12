# Task 0047: Response Caching Middleware

**Status**: Planned
**Branch**: `claude/setup-task-methodology-011CV2GyoVTgkzZEveAK5kGc`
**Created**: 2025-11-11
**Environment Split**: Cloud (Code) + Local (Testing)

---

## Summary

### Goal
Add response caching middleware to reduce load on expensive API calls, improving response times and reducing unnecessary computation.

### Approach
- Create lightweight caching middleware using `cachetools` (TTL-based caching)
- Implement `@cache_response` decorator with configurable TTL
- Apply to high-traffic read endpoints (market, watchlist, portfolio, paper trades)
- Add cache invalidation on mutations (POST/PUT/DELETE)
- Add X-Cache-Hit header for observability
- Environment variable configuration
- Cache management endpoint in health check

### Scope
**In Scope**:
- Middleware creation and decorator implementation
- Caching for GET /api/market, /api/watchlist, /api/portfolio, /api/paper-trades/stats
- Cache invalidation hooks
- Health endpoint for cache management
- Environment configuration

**Out of Scope**:
- Redis or external cache systems (keeping simple)
- Per-user cache segregation (future enhancement)
- Cache warming strategies
- Advanced cache eviction policies

---

## Tasks

### Task 1: Create Middleware Infrastructure
- [x] Create `backend/app/middleware/` directory with `__init__.py`
- [x] Create `backend/app/middleware/cache.py` with cachetools dependency
- [x] Implement TTL-based cache storage using `cachetools.TTLCache`
- [x] Create `@cache_response` decorator with TTL parameter
- [x] Add X-Cache-Hit header logic
- [x] Add environment variable configuration (CACHE_ENABLED, CACHE_MAX_SIZE)

### Task 2: Apply Caching to Market Endpoints
- [x] Apply `@cache_response(ttl=300)` to GET /api/market (5 min)
- [x] Verify cache key generation includes relevant params
- [x] Add cache invalidation on market data mutations

### Task 3: Apply Caching to Watchlist Endpoints
- [x] Apply `@cache_response(ttl=60)` to GET /api/watchlist (1 min)
- [x] Verify cache key includes user context
- [x] Add cache invalidation on watchlist mutations (add/remove)

### Task 4: Apply Caching to Portfolio Endpoints
- [x] Apply `@cache_response(ttl=30)` to GET /api/portfolio (30 sec)
- [x] Verify cache key includes user context
- [x] Add cache invalidation on portfolio mutations

### Task 5: Apply Caching to Paper Trades Endpoints
- [x] Apply `@cache_response(ttl=120)` to GET /api/paper-trades/stats (2 min)
- [x] Verify cache key includes user context
- [x] Add cache invalidation on trade execution

### Task 6: Cache Invalidation Strategy
- [x] Create `invalidate_cache_pattern()` helper for pattern-based invalidation
- [x] Hook invalidation into POST/PUT/DELETE endpoints
- [x] Add selective invalidation (e.g., only clear affected user's cache)

### Task 7: Cache Management Endpoints
- [x] Add GET /api/health/cache/stats endpoint (cache size, hit rate)
- [x] Add POST /api/health/cache/clear endpoint (admin only)
- [x] Add cache metrics to health check response

### Task 8: Integration and Configuration
- [x] Wire up middleware in `main.py`
- [x] Add environment variables to `.env.example`
- [x] Update configuration documentation

---

## Verification Checklist

### Functional Testing (Local)
- [ ] Start backend: `bash ~/portfolio-ai/scripts/restart.sh`
- [ ] Verify cache headers on GET /api/market (first: miss, second: hit)
- [ ] Verify cache headers on GET /api/watchlist (first: miss, second: hit)
- [ ] Verify cache headers on GET /api/portfolio (first: miss, second: hit)
- [ ] Verify cache headers on GET /api/paper-trades/stats (first: miss, second: hit)
- [ ] Verify cache invalidation after POST to watchlist (X-Cache-Hit: false after mutation)
- [ ] Verify TTL expiration (wait 1 min, check watchlist cache expires)
- [ ] Test cache clear endpoint: POST /api/health/cache/clear
- [ ] Check cache stats endpoint: GET /api/health/cache/stats
- [ ] Verify CACHE_ENABLED=false disables caching

### Test Coverage (Local)
- [ ] Run unit tests: `cd ~/portfolio-ai/backend && pytest tests/unit/middleware/ -v`
- [ ] Run integration tests: `cd ~/portfolio-ai/backend && pytest tests/integration/ -v`
- [ ] Verify cache decorator tests pass
- [ ] Verify invalidation tests pass
- [ ] Check overall coverage remains >85%

### Code Quality (Cloud)
- [x] Run linting: `~/portfolio-ai/scripts/lint.sh` passes
- [x] Type checking: All mypy checks pass
- [x] File sizes: All files <500 lines
- [x] No duplicate code
- [x] No f-string SQL with user input
- [x] All functions have type hints

### Documentation (Cloud)
- [x] Environment variables documented in `.env.example`
- [x] Cache configuration in DEVELOPMENT.md
- [x] Handoff doc created for local testing

---

## Implementation Notes

### Cache Key Strategy
```python
# Format: "{method}:{path}:{query_params}:{user_id}"
# Example: "GET:/api/watchlist:{}:user_123"
```

### TTL Configuration
- Market data: 5 min (300s) - slower changing
- Watchlist: 1 min (60s) - moderate updates
- Portfolio: 30 sec (30s) - frequent changes
- Paper trades stats: 2 min (120s) - moderate updates

### Cache Invalidation Patterns
```python
# Clear all caches for a user
invalidate_cache_pattern(f"*:user_{user_id}")

# Clear specific endpoint caches
invalidate_cache_pattern(f"GET:/api/watchlist:*")
```

### Environment Variables
```bash
CACHE_ENABLED=true
CACHE_MAX_SIZE=1000
CACHE_DEFAULT_TTL=300
```

---

## Deliverables

1. **Code**: Complete middleware implementation
2. **Task File**: This document (committed)
3. **Handoff Doc**: `tasks/HANDOFF-caching-middleware-local-testing.md`
4. **WORK_TRACKER**: Updated with new task
5. **Branch**: All changes pushed to feature branch

---

## Success Criteria

- ✅ Response times reduced by 50-80% for cached endpoints
- ✅ Cache hit rate >70% after warm-up period
- ✅ X-Cache-Hit header present on all cacheable responses
- ✅ Cache invalidation works correctly on mutations
- ✅ Environment variables control caching behavior
- ✅ Cache management endpoints functional
- ✅ All tests pass
- ✅ Code quality checks pass
