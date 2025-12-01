# Task List: Dashboard Market News Performance Optimization

**Source**: /test_it Quick Test run on 2025-11-30
**Complexity**: Medium
**Effort**: MEDIUM
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-30 21:15

---

## Summary

**Goal**: Reduce Dashboard Market News loading time from 10+ seconds to <5 seconds
**Approach**: Profile current implementation, identify bottlenecks, implement optimizations (lazy loading, pagination, or caching)
**Scope Discovery**: Required - need to understand current news fetching and rendering pipeline

---

## Problem Statement

- Dashboard Market News section currently takes 10+ seconds to fully load
- API returns 39 articles with full sentiment data (~10KB response)
- Users see "Fetching latest headlines" for extended period
- Target: Full page ready in <5 seconds (per performance thresholds)

---

## Tasks

### 0.0 Scope Discovery & Profiling ✅ COMPLETE

- [x] 0.1 Profile current news loading pipeline
  - API response time: 24-30ms (very fast)
  - Frontend fetch time: 16ms round trip
  - **Bottleneck**: IntersectionObserver waiting for 15% visibility, news below fold
- [x] 0.2 Review current implementation
  - Dashboard: `frontend/app/page.tsx` (MarketNewsSection)
  - News API: `backend/app/api/news.py`
  - Already has lazy loading + limit=6 initial articles
- [x] 0.3 Checkpoint: Confirm optimization strategy
  - **Bottleneck identified**: News section below fold, IntersectionObserver threshold too strict
  - **Fix applied**: Added `rootMargin: '300px'` to prefetch 300px before visible
  - **Result**: News now loads within 1s instead of 10+ seconds

### 1.0 Implement Backend Optimizations (if API is bottleneck) - SKIPPED

**Not needed** - API is already fast (24-30ms) and already supports `limit` parameter.

### 2.0 Implement Frontend Optimizations - SKIPPED

**Not needed** - Frontend already has:
- Lazy loading via IntersectionObserver
- Initial limit of 6 articles
- Progressive expansion to 50 articles
- The rootMargin fix addresses the timing issue

### 3.0 Add Loading State Improvements - SKIPPED

**Not needed** - Current skeleton loader works correctly once fetch triggers.

### 4.0 Testing & Verification ✅ COMPLETE

- [x] 4.1 Measure new load times
  - Before fix: News never loaded without scrolling (10+ seconds perceived)
  - After fix: News fetches at ~544ms, ready within 1 second
  - Target: <5s ✅ ACHIEVED
- [x] 4.2 Test edge cases - Already handled by existing implementation
- [x] 4.3 Verify no regressions
  - News content accurate ✅
  - Sentiment indicators working ✅
  - Links functional ✅

---

## Verification ✅ ALL COMPLETE

- [x] Functional: News loads in <1 second (target was <5s)
- [x] Tests: Frontend page.tsx lints clean
- [x] Quality: No new lint errors introduced
- [x] Services: Frontend serves updated code
- [x] Performance: Measured with Playwright - 544ms to fetch, <1s to render
- [x] UX: Loading states feel responsive

## Commit
- Hash: 1545d1b
- Message: `perf: prefetch Market News before visible with rootMargin`
