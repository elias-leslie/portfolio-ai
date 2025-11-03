# Task List: Complete Multi-Source Failover for PriceDataFetcher

**PRD**: `0016-prd-complete-multi-source-failover.md`
**Status**: Ready for Implementation
**Completion**: 0% (Not started)
**Effort to Complete**: Medium (2-3 days)
**Last Updated**: 2025-10-30

**Note on Effort Levels**:
- **Low**: 1-2 hours of straightforward work
- **Medium**: Half day of work with some complexity
- **High**: Full day or more, significant complexity

---

## Summary

**✅ COMPLETE:**
- (None yet)

**🔄 IN PROGRESS:**
- (Not started)

**⚠️ NEXT STEPS:**
1. Begin with Task 1.0: Add All 6 Sources to PriceDataFetcher
2. Follow checklist sequentially through all phases
3. Update this summary as work progresses

**EFFORT TO COMPLETE:** Medium (2-3 days for all 5 phases + documentation)

**Current State Assessment:**
- ✅ All 6 source adapter classes exist and are tested (YFinance, TwelveData, FMP, Polygon, Finnhub, AlphaVantage)
- ✅ MultiSourceFetcher with priority-based failover exists
- ✅ source_performance table exists in database schema
- ⚠️ PriceDataFetcher currently only uses 2 sources (YFinance + Polygon)
- ⚠️ No source performance tracking implemented
- ⚠️ Health endpoint doesn't show all sources
- ⚠️ Frontend doesn't show source indicators

---

## Relevant Files

### Files to Create (2 new files)

- `backend/tests/test_multi_source_price_fetcher.py` (~300 lines) - Comprehensive tests for all 6-source failover scenarios
- `frontend/components/watchlist/SourceBadge.tsx` (~80 lines) - Source indicator UI component

### Files to Update (6 files)

- `backend/app/portfolio/price_fetcher.py` - Add all 6 sources to __init__, add performance tracking
- `backend/app/storage/queries.py` - Add source performance query methods
- `backend/app/api/health.py` - Extend health check to include all 6 sources
- `frontend/components/watchlist/WatchlistTable.tsx` - Add source indicator badges
- `docs/core/ARCHITECTURE.md` - Document 6-source failover architecture
- `docs/core/OPERATIONS.md` - Add source monitoring runbook

### Notes

- Unit tests should be placed in `backend/tests/` directory
- Use `cd ~/portfolio-ai/backend && pytest tests/ -v` to run all tests
- Use `cd ~/portfolio-ai/backend && mypy app/ --strict` to verify type safety
- Use `~/portfolio-ai/scripts/lint.sh` to run linting and formatting checks
- All source adapters already exist in `backend/app/sources/` - just need to wire them up

---

## Tasks

### Phase 1: Add All 6 Sources to PriceDataFetcher (HIGH PRIORITY)

- [ ] 1.0 **Add All 6 Sources to PriceDataFetcher**
  - [ ] 1.1 Add missing source imports to price_fetcher.py (2 min)
    - [ ] 1.1.1 Import TwelveDataSource from sources.twelvedata_source
    - [ ] 1.1.2 Import FMPSource from sources.fmp_source
    - [ ] 1.1.3 Import FinnhubSource from sources.finnhub_source
    - [ ] 1.1.4 Import AlphaVantageSource from sources.alphavantage_source
  - [ ] 1.2 Create helper method to check API key availability (3 min)
    - [ ] 1.2.1 Add _has_api_key(source_name: str) -> bool method
    - [ ] 1.2.2 Check environment variables for each source's API key
    - [ ] 1.2.3 Return True if key exists and is non-empty, False otherwise
  - [ ] 1.3 Update __init__ to initialize all 6 sources in priority order (4 min)
    - [ ] 1.3.1 Keep YFinanceSource() (priority 1, no key needed)
    - [ ] 1.3.2 Add TwelveDataSource() if has_api_key("TWELVEDATA_API_KEY")
    - [ ] 1.3.3 Add FMPSource() if has_api_key("FMP_API_KEY")
    - [ ] 1.3.4 Add PolygonSource() if has_api_key("POLYGON_API_KEY") (already exists, keep)
    - [ ] 1.3.5 Add FinnhubSource() if has_api_key("FINNHUB_API_KEY")
    - [ ] 1.3.6 Add AlphaVantageSource() if has_api_key("ALPHAVANTAGE_API_KEY")
  - [ ] 1.4 Update initialization logging to show all active sources (2 min)
    - [ ] 1.4.1 Build list of active source names
    - [ ] 1.4.2 Log sources_initialized with count and names
    - [ ] 1.4.3 Log skipped sources (those without API keys)
  - [ ] 1.5 Verify imports and run linting (2 min)
    - [ ] 1.5.1 Run: cd ~/portfolio-ai/backend && ~/portfolio-ai/backend/.venv/bin/ruff check app/portfolio/price_fetcher.py
    - [ ] 1.5.2 Run: cd ~/portfolio-ai/backend && ~/portfolio-ai/backend/.venv/bin/mypy app/portfolio/price_fetcher.py
    - [ ] 1.5.3 Fix any import or type errors

### Phase 2: Implement Source Performance Tracking (HIGH PRIORITY)

- [ ] 2.0 **Implement Source Performance Tracking**
  - [ ] 2.1 Add source performance query methods to queries.py (5 min)
    - [ ] 2.1.1 Add record_source_attempt(source_name, success, latency_ms, error_type) method
    - [ ] 2.1.2 Add get_source_performance(source_name, limit=100) method
    - [ ] 2.1.3 Add get_all_sources_summary() method (aggregated stats)
  - [ ] 2.2 Update MultiSourceFetcher to track attempts (already done, verify) (2 min)
    - [ ] 2.2.1 Check if fetch_with_fallback already logs source attempts
    - [ ] 2.2.2 Verify SourceMetrics class captures success/failure/latency
  - [ ] 2.3 Add performance tracking to PriceDataFetcher._fetch_fresh_prices (4 min)
    - [ ] 2.3.1 Record start time before multi_source_fetcher.fetch_with_fallback
    - [ ] 2.3.2 Record end time after fetch completes
    - [ ] 2.3.3 Calculate total latency
    - [ ] 2.3.4 Log comprehensive failover event with all source attempts
  - [ ] 2.4 Persist metrics to source_performance table (3 min)
    - [ ] 2.4.1 After successful fetch, call storage.query_mgr.record_source_attempt(...)
    - [ ] 2.4.2 Record success=True, latency, error_type=None
    - [ ] 2.4.3 On failure, record success=False with error details
  - [ ] 2.5 Add logging for failover chain analysis (3 min)
    - [ ] 2.5.1 Log "source_failover_chain" with attempted sources in order
    - [ ] 2.5.2 Log failure reason for each failed source
    - [ ] 2.5.3 Log final successful source and total chain latency

### Phase 3: Extend Health Check Endpoint (MEDIUM PRIORITY)

- [ ] 3.0 **Extend Health Check Endpoint**
  - [ ] 3.1 Read current health.py structure (1 min)
    - [ ] 3.1.1 Check existing health check endpoints
    - [ ] 3.1.2 Identify where to add source status checks
  - [ ] 3.2 Add source status check helper function (4 min)
    - [ ] 3.2.1 Create get_source_health(storage) -> dict function
    - [ ] 3.2.2 Query source_performance table for each of 6 sources
    - [ ] 3.2.3 Calculate success rate (last 100 requests)
    - [ ] 3.2.4 Get average latency and last success timestamp
  - [ ] 3.3 Add API key configuration check (2 min)
    - [ ] 3.3.1 Check environment for each source's API key
    - [ ] 3.3.2 Return {"has_key": bool} for each source
  - [ ] 3.4 Update /health endpoint response schema (3 min)
    - [ ] 3.4.1 Add "data_sources" key to response
    - [ ] 3.4.2 Include array of 6 sources with: name, priority, has_api_key, success_rate, avg_latency, last_success
    - [ ] 3.4.3 Add "source_distribution" showing request counts per source
  - [ ] 3.5 Test health endpoint manually (2 min)
    - [ ] 3.5.1 Run: curl http://localhost:8000/health | jq
    - [ ] 3.5.2 Verify all 6 sources appear in response
    - [ ] 3.5.3 Verify metrics are populated correctly

### Phase 4: Add Frontend Source Indicators (LOW PRIORITY)

- [ ] 4.0 **Add Frontend Source Indicators**
  - [ ] 4.1 Create SourceBadge component (5 min)
    - [ ] 4.1.1 Create frontend/components/watchlist/SourceBadge.tsx
    - [ ] 4.1.2 Accept props: source (string), stale (bool), priority (number)
    - [ ] 4.1.3 Return Badge component with source name
  - [ ] 4.2 Add color coding logic to SourceBadge (3 min)
    - [ ] 4.2.1 Green badge for YFinance (priority 1)
    - [ ] 4.2.2 Yellow badge for backup sources (priority 2-10)
    - [ ] 4.2.3 Red badge for stale/cached data
  - [ ] 4.3 Update WatchlistTable to show source badges (4 min)
    - [ ] 4.3.1 Import SourceBadge component
    - [ ] 4.3.2 Extract source from item.current_score?.price.metadata.source
    - [ ] 4.3.3 Extract stale flag from item.current_score?.price.stale
    - [ ] 4.3.4 Render SourceBadge next to symbol in table row
  - [ ] 4.4 Add failover message display (3 min)
    - [ ] 4.4.1 Check if metadata.reason exists (e.g., "yfinance_unavailable")
    - [ ] 4.4.2 Show tooltip/message: "Data from {source} (YFinance unavailable)"
    - [ ] 4.4.3 Only show message when backup source was used
  - [ ] 4.5 Test UI changes manually (2 min)
    - [ ] 4.5.1 View watchlist page in browser
    - [ ] 4.5.2 Verify source badges appear for each ticker
    - [ ] 4.5.3 Verify color coding matches expected behavior

### Phase 5: Comprehensive Testing (CRITICAL)

- [ ] 5.0 **Comprehensive Testing**
  - [ ] 5.1 Write unit tests for source initialization (10 min)
    - [ ] 5.1.1 Create backend/tests/test_multi_source_price_fetcher.py
    - [ ] 5.1.2 Test: PriceDataFetcher initializes with YFinance only (no API keys)
    - [ ] 5.1.3 Test: PriceDataFetcher initializes all 6 sources (with API keys mocked)
    - [ ] 5.1.4 Test: _has_api_key() returns True/False correctly
    - [ ] 5.1.5 Test: Sources are ordered by priority correctly
  - [ ] 5.2 Write integration tests for failover scenarios (15 min)
    - [ ] 5.2.1 Test: YFinance fails → TwelveData succeeds
    - [ ] 5.2.2 Test: First 3 sources fail → Polygon succeeds
    - [ ] 5.2.3 Test: All sources fail → return cached data
    - [ ] 5.2.4 Test: Source returns incomplete data (null price) → try next source
    - [ ] 5.2.5 Test: Source returns stale data → try next source
  - [ ] 5.3 Write tests for performance tracking (8 min)
    - [ ] 5.3.1 Test: Successful fetch records metrics to source_performance table
    - [ ] 5.3.2 Test: Failed fetch records error metrics
    - [ ] 5.3.3 Test: Metrics include correct latency measurements
    - [ ] 5.3.4 Test: Failover chain is logged with all attempts
  - [ ] 5.4 Write end-to-end tests for watchlist operations (10 min)
    - [ ] 5.4.1 Test: Add ticker → fetches from best available source
    - [ ] 5.4.2 Test: Refresh watchlist → all tickers get fresh data
    - [ ] 5.4.3 Test: Source failure doesn't cause degraded scores
    - [ ] 5.4.4 Test: Watchlist shows correct source indicator in response
  - [ ] 5.5 Run full test suite and verify coverage (5 min)
    - [ ] 5.5.1 Run: cd ~/portfolio-ai/backend && pytest tests/test_multi_source_price_fetcher.py -v
    - [ ] 5.5.2 Run: cd ~/portfolio-ai/backend && pytest tests/ --cov=app/portfolio --cov-report=term-missing
    - [ ] 5.5.3 Verify coverage >80% for price_fetcher.py
    - [ ] 5.5.4 Fix any failing tests

### Phase 6: Documentation Updates (FINAL)

- [ ] 6.0 **Documentation Updates**
  - [ ] 6.1 Update ARCHITECTURE.md (8 min)
    - [ ] 6.1.1 Add section: "Multi-Source Data Fetching Architecture"
    - [ ] 6.1.2 Document 6-source priority order and failover logic
    - [ ] 6.1.3 Add decision tree diagram (text/ASCII) for source selection
    - [ ] 6.1.4 Document performance metrics tracking strategy
  - [ ] 6.2 Update OPERATIONS.md (10 min)
    - [ ] 6.2.1 Add section: "Data Source Health Monitoring"
    - [ ] 6.2.2 Document how to check /health endpoint for source status
    - [ ] 6.2.3 Add runbook: "Troubleshooting Data Source Failures"
    - [ ] 6.2.4 Document API key configuration for each source (env var names)
    - [ ] 6.2.5 Add example queries to check source_performance table
  - [ ] 6.3 Update CLAUDE.md (4 min)
    - [ ] 6.3.1 Update "Current Status" section to mark PRD #0011 as 100% complete
    - [ ] 6.3.2 Add PRD #0016 as completed in version history
    - [ ] 6.3.3 Update multi-source status from "2 sources" to "6 sources"
    - [ ] 6.3.4 Document confirmed source priorities
  - [ ] 6.4 Update REFACTOR_STATUS.md (3 min)
    - [ ] 6.4.1 Add PRD #0016 completion entry
    - [ ] 6.4.2 Update tech stack to confirm "6-source multi-source failover"
    - [ ] 6.4.3 Mark multi-source data infrastructure as 100% complete
  - [ ] 6.5 Create commit with all documentation changes (2 min)
    - [ ] 6.5.1 Stage documentation files: git add docs/ CLAUDE.md
    - [ ] 6.5.2 Commit: "docs: complete multi-source failover documentation (PRD #0016)"
    - [ ] 6.5.3 Verify commit with git log

---

## Verification & Production Readiness

**MANDATORY before marking task "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All 6 sources initialized in PriceDataFetcher (YFinance, TwelveData, FMP, Polygon, Finnhub, AlphaVantage)
  - [ ] Failover works across all sources in priority order
  - [ ] Source performance metrics tracked in database
  - [ ] Health endpoint shows all 6 sources with status
  - [ ] Frontend displays source indicators
  - [ ] Zero "missing_change_pct" errors in watchlist after 24 hours

- [ ] **Test Coverage** (target: 80%+)
  - [ ] Unit tests for source initialization (all scenarios)
  - [ ] Integration tests for failover chains
  - [ ] E2E tests for watchlist with multi-source
  - [ ] All tests passing: cd ~/portfolio-ai/backend && pytest tests/ -v
  - [ ] Coverage verified: cd ~/portfolio-ai/backend && pytest tests/ --cov=app/portfolio --cov-report=term-missing

- [ ] **Type Safety & Code Quality**
  - [ ] 100% type hints on all new functions: cd ~/portfolio-ai/backend && mypy app/ --strict
  - [ ] Linting passes: ~/portfolio-ai/scripts/lint.sh
  - [ ] Code formatting applied: cd ~/portfolio-ai/backend && ~/portfolio-ai/backend/.venv/bin/ruff format app/
  - [ ] No complexity issues (functions <50 lines)

- [ ] **Clean Implementation**
  - [ ] No `Any` type shortcuts
  - [ ] Proper error messages (specific failure reasons)
  - [ ] Single source of truth maintained (no duplicated source lists)
  - [ ] Standard patterns used (leverage existing MultiSourceFetcher)
  - [ ] Clear intent (explicit priority ordering)

- [ ] **Documentation**
  - [ ] All new functions have docstrings
  - [ ] ARCHITECTURE.md documents 6-source architecture
  - [ ] OPERATIONS.md has source monitoring runbook
  - [ ] CLAUDE.md reflects 100% multi-source completion
  - [ ] REFACTOR_STATUS.md updated with PRD #0016 completion

- [ ] **Security & Performance**
  - [ ] API keys checked via environment (not hardcoded)
  - [ ] Source attempts logged (no silent failures)
  - [ ] Performance metrics tracked in database
  - [ ] No regression in price fetch latency (<3s avg for failover chain)

- [ ] **Operational Readiness**
  - [ ] Appropriate logging at INFO level for source selection
  - [ ] WARNING level for failover events
  - [ ] ERROR level for all-sources-failed scenarios
  - [ ] Manual test: Add ticker → verify source failover works
  - [ ] Manual test: Check /health → verify all 6 sources visible

**See**: `docs/core/DEVELOPMENT.md` → "Production Readiness Requirements" for complete checklist

---
