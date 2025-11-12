# Task List: Database Query & Data Fetching Deduplication

**Status**: In Progress (Partially Complete)
**Completion**: 35%
**Effort**: MEDIUM-HIGH (8-12 hours, 2-3 sessions)
**Updated**: 2025-11-07

---

## Summary

**Problem**: Analysis identified potential duplicate queries and redundant API calls across Celery tasks and service layers, but hypotheses must be validated with measurements before implementing fixes.

**Approach**: **VALIDATE → FIX → VERIFY** for each issue (facts only, no assumptions)

**Issues to Investigate & Fix**:
1. 🔴 Overlapping news fetches between `refresh_watchlist_scores` and `refresh_news_sentiment` tasks
2. 🔴 Per-symbol news fetching in watchlist refresh loop (N fetches vs 1 batch)
3. 🟡 User preferences queried 5 separate times per task
4. 🟡 Watchlist items queried twice by different tasks
5. 🔴 N+1 query pattern in `get_items_with_scores()` (snapshots queried individually)

**✅ COMPLETE:** Issue #2 (Per-symbol news fetching - 96% API call reduction, commit c5f44de)
**🔄 IN PROGRESS:** Issue #1 (validation test infrastructure exists, needs concurrent testing)
**⚠️ NEXT:** Complete Issue #1 validation, then tackle Issues #3-5

**PROGRESS UPDATE 2025-11-09:**
- ✅ Test infrastructure complete (QueryCounter, APICallTracker)
- ✅ Issue #2 FIXED: Batch news fetching (23 calls → 1 call)
- ⚠️ Issue #1: 25% complete (single-task validation done)
- ❌ Issues #3, #4, #5: Not started (9 duplicate preferences queries identified)

---

## Relevant Files

### Investigation/Analysis
- `backend/app/tasks/watchlist_tasks.py` - Watchlist refresh task
- `backend/app/tasks/news_tasks.py` - News refresh task
- `backend/app/watchlist/scoring_service.py` - Watchlist scoring logic
- `backend/app/watchlist/refresh_processor.py` - Per-ticker processing
- `backend/app/watchlist/watchlist_service.py` - N+1 query location
- `backend/app/services/news_service.py` - News fetching service

### Create (2-3 files)
- `backend/tests/integration/test_query_duplication.py` (~200 lines) - Validation tests for duplicates
- `backend/app/utils/preferences_loader.py` (~100 lines) - Centralized preferences (if Issue #3 validated)
- `backend/app/storage/queries.py` - Add optimized JOIN query (if Issue #5 validated)

### Update (5-8 files)
- Files above (after validation confirms issues)

### Notes
- **CRITICAL**: Run validation tests BEFORE any fix
- Tests: `cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/`
- Linting: `~/portfolio-ai/scripts/lint.sh`
- Current test count: 508+ tests must all pass

---

## Tasks

### 0.0 Setup: Create Instrumentation for Validation

- [ ] 0.1 Create test infrastructure for measuring queries and API calls
  - [ ] 0.1.1 Create `backend/tests/integration/test_query_duplication.py`
  - [ ] 0.1.2 Add query counter using SQLAlchemy event listeners
    ```python
    from sqlalchemy import event

    class QueryCounter:
        def __init__(self):
            self.queries = []

        def __call__(self, conn, cursor, statement, parameters, context, executemany):
            self.queries.append({
                'sql': statement,
                'params': parameters,
                'timestamp': datetime.now(UTC)
            })
    ```
  - [ ] 0.1.3 Add API call counter (mock NewsService to track calls)
  - [ ] 0.1.4 Write helper function to analyze query patterns (find duplicates)

- [ ] 0.2 Create baseline measurement test
  - [ ] 0.2.1 Write test that runs watchlist refresh for 10 symbols
  - [ ] 0.2.2 Capture all queries executed
  - [ ] 0.2.3 Capture all API calls made
  - [ ] 0.2.4 Document baseline metrics (save to file for comparison)
  - [ ] 0.2.5 Run test and record:
    - Total queries
    - Duplicate queries (same SQL + params)
    - API calls per symbol
    - Total execution time

---

### 1.0 ISSUE #1: Validate Overlapping News Fetches Between Tasks

**Hypothesis**: Both `refresh_watchlist_scores` and `refresh_news_sentiment` tasks fetch news for same symbols when running concurrently.

- [ ] 1.1 Write validation test to prove overlap exists
  - [ ] 1.1.1 Create test that runs both tasks concurrently (with 10 test symbols)
  - [ ] 1.1.2 Mock NewsService to track which symbols are fetched
  - [ ] 1.1.3 Mock time.time() to control task scheduling
  - [ ] 1.1.4 Measure:
    - Symbols fetched by watchlist task (timestamp each)
    - Symbols fetched by news task (timestamp each)
    - Overlap count (same symbol fetched twice within 5 seconds)

- [ ] 1.2 Analyze validation results
  - [ ] 1.2.1 If NO overlap detected → Mark Issue #1 as FALSE POSITIVE, skip to Issue #2
  - [ ] 1.2.2 If overlap detected → Document findings:
    - Percentage of symbols fetched twice
    - Time delta between duplicate fetches
    - Root cause (task scheduling, no coordination, etc.)

- [ ] 1.3 **IF VALIDATED**: Implement fix for overlapping news fetches
  - [ ] 1.3.1 Design decision: Choose fix approach
    - Option A: Remove news fetching from watchlist refresh (read from cache only)
    - Option B: Add Redis lock to prevent duplicate fetches within window
    - Option C: Centralize all news fetching in news_refresh task only
  - [ ] 1.3.2 Implement chosen approach
  - [ ] 1.3.3 Update watchlist refresh to skip news fetch if lock exists (if Option B)
  - [ ] 1.3.4 Update news service to set lock on fetch (if Option B)

- [ ] 1.4 **IF VALIDATED**: Verify fix eliminates overlap
  - [ ] 1.4.1 Re-run validation test from 1.1
  - [ ] 1.4.2 Measure:
    - Overlap count (should be 0)
    - API calls reduced (calculate %)
    - Execution time impact
  - [ ] 1.4.3 Document improvement metrics
  - [ ] 1.4.4 Run full test suite: `pytest tests/ -v`

---

### 2.0 ISSUE #2: Validate Per-Symbol News Fetching in Loop

**Hypothesis**: Watchlist refresh fetches news individually per symbol (N calls) instead of batch (1 call).

- [ ] 2.1 Write validation test to prove per-symbol fetching exists
  - [ ] 2.1.1 Create test that runs `refresh_watchlist_scores` with 10 symbols
  - [ ] 2.1.2 Mock `news_service.get_symbol_news()` to track call count
  - [ ] 2.1.3 Mock `news_service.get_watchlist_news()` to track call count
  - [ ] 2.1.4 Measure:
    - Number of `get_symbol_news()` calls (expect: N)
    - Number of `get_watchlist_news()` calls (expect: 0)
    - Total API calls
    - Execution time

- [ ] 2.2 Analyze validation results
  - [ ] 2.2.1 If `get_watchlist_news()` IS used → Mark Issue #2 as FALSE POSITIVE, skip to Issue #3
  - [ ] 2.2.2 If `get_symbol_news()` called N times → Document findings:
    - Confirm N individual calls
    - Calculate overhead (time per call × N vs 1 batch call)
    - Identify call location in code

- [ ] 2.3 **IF VALIDATED**: Implement batch news fetching
  - [ ] 2.3.1 Update `scoring_service.py` to fetch news BEFORE loop
    ```python
    # BEFORE the loop (around line 274):
    news_bundles = news_service.get_watchlist_news(
        symbols=symbols,
        max_articles=news_max_articles,
        force_refresh=False,  # Respect cache
    )
    ```
  - [ ] 2.3.2 Update `process_ticker_snapshot()` signature to accept `news_bundle: NewsBundle | None`
  - [ ] 2.3.3 Update loop to pass pre-fetched bundle:
    ```python
    for row in items_df.iter_rows(named=True):
        symbol = row["symbol"]
        news_bundle = news_bundles.get(symbol)  # Dict lookup
        snapshot = process_ticker_snapshot(
            # ... other args ...
            news_bundle=news_bundle,  # Pass directly, don't fetch inside
        )
    ```
  - [ ] 2.3.4 Update `refresh_processor.py` to use passed bundle instead of fetching

- [ ] 2.4 **IF VALIDATED**: Verify fix uses batch fetching
  - [ ] 2.4.1 Re-run validation test from 2.1
  - [ ] 2.4.2 Measure:
    - `get_symbol_news()` calls (should be 0)
    - `get_watchlist_news()` calls (should be 1)
    - API calls reduced (calculate %)
    - Execution time improvement
  - [ ] 2.4.3 Document improvement: N calls → 1 call (X% reduction)
  - [ ] 2.4.4 Run full test suite: `pytest tests/ -v`

---

### 3.0 ISSUE #3: Validate User Preferences Queried 5 Times

**Hypothesis**: User preferences table is queried 5 separate times per task execution.

- [ ] 3.1 Write validation test to prove multiple preference queries
  - [ ] 3.1.1 Create test that runs `refresh_watchlist_scores` once
  - [ ] 3.1.2 Use QueryCounter to capture all queries
  - [ ] 3.1.3 Filter queries to `user_preferences` table
  - [ ] 3.1.4 Measure:
    - Count of queries to `user_preferences` (hypothesis: 5)
    - Unique queries vs duplicate queries
    - Fields fetched by each query

- [ ] 3.2 Analyze validation results
  - [ ] 3.2.1 If queries < 3 → Mark Issue #3 as FALSE POSITIVE, skip to Issue #4
  - [ ] 3.2.2 If queries ≥ 3 → Document findings:
    - Exact count of preference queries
    - Location of each query in code
    - Which fields could be fetched in single query

- [ ] 3.3 **IF VALIDATED**: Implement centralized preferences loader
  - [ ] 3.3.1 Create `backend/app/utils/preferences_loader.py`
  - [ ] 3.3.2 Implement `UserPreferences` dataclass with all fields
  - [ ] 3.3.3 Implement `UserPreferences.load_all(storage, account_id)` with single query
  - [ ] 3.3.4 Update `watchlist_tasks.py` to use centralized loader
  - [ ] 3.3.5 Update `scoring_service.py` helper functions to accept preferences object
  - [ ] 3.3.6 Update `news_tasks.py` to use centralized loader

- [ ] 3.4 **IF VALIDATED**: Verify fix reduces preference queries
  - [ ] 3.4.1 Re-run validation test from 3.1
  - [ ] 3.4.2 Measure:
    - Count of queries to `user_preferences` (should be 1)
    - Queries eliminated (calculate reduction %)
  - [ ] 3.4.3 Document improvement: N queries → 1 query
  - [ ] 3.4.4 Run full test suite: `pytest tests/ -v`

---

### 4.0 ISSUE #4: Validate Watchlist Items Queried Twice

**Hypothesis**: Both `watchlist_tasks.py` and `news_tasks.py` query `watchlist_items` table separately.

- [ ] 4.1 Write validation test to prove duplicate watchlist queries
  - [ ] 4.1.1 Create test that runs both tasks with same account_id
  - [ ] 4.1.2 Use QueryCounter to capture all queries
  - [ ] 4.1.3 Filter queries to `watchlist_items` table
  - [ ] 4.1.4 Measure:
    - Count of queries to `watchlist_items`
    - Whether queries are identical or different
    - Time between duplicate queries

- [ ] 4.2 Analyze validation results
  - [ ] 4.2.1 If only 1 query → Mark Issue #4 as FALSE POSITIVE, skip to Issue #5
  - [ ] 4.2.2 If 2+ queries → Document findings:
    - Which tasks query watchlist items
    - Query patterns (same SQL or different)
    - Opportunity for caching

- [ ] 4.3 **IF VALIDATED**: Implement Redis cache for watchlist symbols
  - [ ] 4.3.1 Add helper function to cache watchlist symbols
    ```python
    def get_watchlist_symbols_cached(storage, account_id, ttl_seconds=60):
        redis_key = f"watchlist:symbols:{account_id}"
        cached = redis_client.get(redis_key)
        if cached:
            return json.loads(cached)

        # Query DB
        symbols = _query_watchlist_symbols(storage, account_id)
        redis_client.setex(redis_key, ttl_seconds, json.dumps(symbols))
        return symbols
    ```
  - [ ] 4.3.2 Update `watchlist_tasks.py` to use cache
  - [ ] 4.3.3 Update `news_tasks.py` to use cache
  - [ ] 4.3.4 Add cache invalidation on watchlist add/remove

- [ ] 4.4 **IF VALIDATED**: Verify fix eliminates duplicate queries
  - [ ] 4.4.1 Re-run validation test from 4.1
  - [ ] 4.4.2 Measure:
    - Count of DB queries to `watchlist_items` (should be 1)
    - Redis cache hits (should be 1+)
  - [ ] 4.4.3 Document improvement: 2+ queries → 1 query + cache hits
  - [ ] 4.4.4 Run full test suite: `pytest tests/ -v`

---

### 5.0 ISSUE #5: Validate N+1 Query Pattern in get_items_with_scores()

**Hypothesis**: `get_items_with_scores()` queries snapshots individually per item (N+1 problem).

- [ ] 5.1 Write validation test to prove N+1 pattern exists
  - [ ] 5.1.1 Create test that calls `watchlist_service.get_items_with_scores()` with 10 items
  - [ ] 5.1.2 Use QueryCounter to capture all queries
  - [ ] 5.1.3 Filter queries to `watchlist_snapshots` table
  - [ ] 5.1.4 Measure:
    - Query to `watchlist_items` (expect: 1)
    - Queries to `watchlist_snapshots` (expect: N, one per item)
    - Total queries (expect: 1 + N)

- [ ] 5.2 Analyze validation results
  - [ ] 5.2.1 If only 1-2 queries total → Mark Issue #5 as FALSE POSITIVE, done
  - [ ] 5.2.2 If 1 + N queries → Document findings:
    - Confirm N+1 pattern
    - Calculate overhead for typical watchlist sizes (10, 20, 50 items)
    - Identify loop location in code

- [ ] 5.3 **IF VALIDATED**: Implement optimized JOIN query
  - [ ] 5.3.1 Add optimized query to `storage/queries.py`:
    ```python
    def get_watchlist_items_with_latest_snapshots(self, account_id: str) -> pl.DataFrame:
        """Get watchlist items with latest snapshots in single query (eliminates N+1)."""
        sql = """
            SELECT
                wi.id, wi.account_id, wi.symbol, wi.note, wi.created_at, wi.updated_at,
                ws.overall_score, ws.technical_score, ws.fetched_at, ws.raw_metrics,
                ws.signal_type, ws.signal_strength, ws.narrative_headline,
                ws.recommended_style, ws.style_confidence, ws.optimal_holding_period, ws.risk_level,
                ws.entry_price, ws.stop_loss, ws.profit_target, ws.position_size_shares,
                ws.narrative_action_plan, ws.narrative_position_sizing,
                ws.narrative_company_health, ws.narrative_special_notes,
                ws.company_health, ws.earnings_date, ws.earnings_days_away,
                ws.news_sentiment_score, ws.recent_news_headlines
            FROM watchlist_items wi
            LEFT JOIN LATERAL (
                SELECT * FROM watchlist_snapshots
                WHERE item_id = wi.id
                ORDER BY fetched_at DESC
                LIMIT 1
            ) ws ON TRUE
            WHERE wi.account_id = ?
            ORDER BY wi.created_at DESC
        """
        return self.query(sql, [account_id])
    ```
  - [ ] 5.3.2 Update `watchlist_service.py` `get_items_with_scores()` to use new query
  - [ ] 5.3.3 Remove per-item snapshot query loop (lines 227-243)
  - [ ] 5.3.4 Process joined results in single iteration

- [ ] 5.4 **IF VALIDATED**: Also fix `get_item_with_score_by_id()` (same N+1 pattern)
  - [ ] 5.4.1 Add single-item optimized query to `storage/queries.py`
  - [ ] 5.4.2 Update `get_item_with_score_by_id()` to use new query

- [ ] 5.5 **IF VALIDATED**: Verify fix eliminates N+1 pattern
  - [ ] 5.5.1 Re-run validation test from 5.1
  - [ ] 5.5.2 Measure:
    - Queries to `watchlist_snapshots` (should be 0 - included in JOIN)
    - Total queries (should be 1 for all items)
  - [ ] 5.5.3 Document improvement: (1 + N) queries → 1 query (N queries eliminated)
  - [ ] 5.5.4 Calculate speedup for typical watchlist sizes
  - [ ] 5.5.5 Run full test suite: `pytest tests/ -v`

---

### 6.0 Comprehensive Verification & Documentation

- [ ] 6.1 Run all validation tests together
  - [ ] 6.1.1 Create comprehensive test that measures BEFORE and AFTER metrics
  - [ ] 6.1.2 Run watchlist refresh + news refresh for 20 symbols
  - [ ] 6.1.3 Capture all queries and API calls
  - [ ] 6.1.4 Compare against baseline from Task 0.2

- [ ] 6.2 Calculate and verify overall improvements
  - [ ] 6.2.1 Total queries: Before vs After (target: 60-80% reduction)
  - [ ] 6.2.2 Duplicate queries eliminated: Count
  - [ ] 6.2.3 API calls: Before vs After (target: 60-80% reduction)
  - [ ] 6.2.4 Execution time: Before vs After (measure improvement)
  - [ ] 6.2.5 Verify all 508+ tests still passing

- [ ] 6.3 Update documentation
  - [ ] 6.3.1 Add query optimization notes to `docs/core/DEVELOPMENT.md`
  - [ ] 6.3.2 Document new `UserPreferences` loader (if implemented)
  - [ ] 6.3.3 Document optimized queries in `storage/queries.py` docstrings
  - [ ] 6.3.4 Add performance metrics to `CODE_DUPLICATION_REPORT_2025-11-07.md`

- [ ] 6.4 Manual smoke testing
  - [ ] 6.4.1 Start services: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] 6.4.2 Add 10 symbols to watchlist via UI
  - [ ] 6.4.3 Trigger manual refresh and observe logs
  - [ ] 6.4.4 Verify no errors, watchlist loads correctly
  - [ ] 6.4.5 Check Redis for cached data (if caching implemented)

---

## Verification (MANDATORY before "COMPLETE ✅")

- [ ] **Functional**: All watchlist and news features work identically (zero behavior changes)
- [ ] **Validated**: Each issue proven to exist with measurements before fixing
- [ ] **Tests**: All 508+ tests passing, new validation tests added
- [ ] **Performance**: 60-80% reduction in duplicate queries/API calls (measured)
- [ ] **Quality**: `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy --strict)
- [ ] **Clean**: No breaking changes, backward compatible
- [ ] **Docs**: Performance improvements documented with metrics
- [ ] **Ops**: Logging preserved, no new errors in production

---

## Success Metrics (Measured, Not Assumed)

### Baseline (Before Fixes)
- Total queries for 20-symbol watchlist refresh: **TBD** (measure in Task 0.2)
- Duplicate queries: **TBD**
- News API calls: **TBD**
- Execution time: **TBD**

### Target (After Fixes)
- Total queries: **60-80% reduction**
- Duplicate queries: **0** (eliminated)
- News API calls: **60-80% reduction**
- Execution time: **30-50% faster**

### Validation Approach
- ✅ If hypothesis proven true → Implement fix → Verify improvement
- ❌ If hypothesis proven false → Mark as FALSE POSITIVE → Skip fix
- 📊 All metrics captured with actual measurements, not estimates

---

## Notes

**Key Principle**: **"Trust but verify"** - Validate every hypothesis with tests before implementing fixes.

**Why Validation First?**:
- Avoids wasted effort fixing non-existent problems
- Provides baseline for measuring improvements
- Documents actual behavior vs assumptions
- Ensures fixes are solving real issues

**Testing Strategy**:
- Integration tests with real database
- Query counting via SQLAlchemy event listeners
- API call mocking to track external requests
- Time measurements for performance comparison

**Risk**: LOW - All changes are performance optimizations, no functional changes. Extensive validation ensures fixes are correct.
