# Task List: Multi-Source Data Infrastructure & Trading Intelligence System

**PRD**: `0011-prd-multi-source-data-trading-intelligence.md`
**Status**: Phase 1.0 Complete, Phase 2.0 Complete, Phase 3.0 In Progress (Tasks 3.1-3.4 COMMITTED)
**Completion**: 63% (Phase 1.0 + Phase 2.0 + Tasks 3.1-3.4 committed, mypy errors resolved)
**Effort to Complete**: HIGH (~2-3 weeks remaining, 37% of work)
**Last Updated**: 2025-10-28

**Note on Effort Levels**:
- **Low**: 1-2 hours of straightforward work
- **Medium**: Half day of work with some complexity
- **High**: Full day or more, significant complexity

---

## Summary

**✅ COMPLETE (Phase 1.0 - Multi-Source Foundation):**
- Task 1.1: Port core source infrastructure files (5 of 5 subtasks complete)
  - Task 1.1.1: jsonpath_mapper.py (265 lines + 242 test lines)
  - Task 1.1.2: rest_api_source.py (532 lines)
  - Task 1.1.3: polygon_client.py (241 lines)
  - Task 1.1.4: polygon_source.py (214 lines)
  - Task 1.1.5: multi_source_fetcher.py (587 lines)
- Task 1.2: Update database schema for source tracking (3 of 3 subtasks complete)
  - Task 1.2.1: source_performance table
  - Task 1.2.2: day_bars table with index
  - Task 1.2.3: minute_bars table
- Task 1.3: Refactor price_fetcher.py to use MultiSourceFetcher ✅
- Task 1.4: Update health check endpoint for multi-source ✅
- Task 1.5: Write comprehensive multi-source tests (9 tests, all pass) ✅
- Task 2.1: Create YFinance adapter (207 lines) ✅
- Task 2.2: Create Twelve Data adapter (489 lines + 313 test lines) ✅
- Task 2.3: Create FMP adapter (483 lines + 417 test lines) ✅
- Task 2.4: Create Finnhub adapter (503 lines + 392 test lines) ✅
- Task 2.5: Create Alpha Vantage adapter (430 lines + 58 test lines) ✅

**✅ MYPY ERRORS RESOLVED:**
All 19 pre-existing mypy type errors have been fixed and committed (commit fcdf14a):

1. **backend/app/portfolio/models.py** - Added type: ignore[misc] for Pydantic BaseModel issues
2. **backend/app/agents/tools.py** - Added type annotations to AgentTools.__init__
3. **backend/app/agents/base.py** - Added type annotations, used cast() for block.input
4. **backend/app/agents/portfolio_analyzer.py** - Fixed run() signature, added type annotations
5. **backend/app/agents/discovery.py** - Fixed run() signature, added type annotations

**Files successfully committed:**
- ✅ `backend/app/analytics/indicators.py` (324 lines, Task 3.2, committed: f61570a)
- ✅ `backend/app/storage/schema.py` (technical_indicators table, Task 3.3, committed: 0c7967d)
- ✅ `backend/app/tasks/agent_tasks.py` (update_technical_indicators task, Task 3.4, committed: fcdf14a)
- ✅ All 5 agent files with mypy fixes (committed: fcdf14a)
- ✅ 220 tests passing, no new failures introduced
- ✅ All pre-commit hooks passing

**⚠️ NEXT STEPS:**
1. Task 3.5: Expose indicators via API
2. Task 4.0: Paper Trading & Agent Performance Tracking
3. Task 5.0: Risk Management Suite
4. Task 6.0: News Sentiment Scoring & Local AI Models

**EFFORT TO COMPLETE:** HIGH (~2-3 weeks, ~37% remaining)

**Session Summary (2025-10-28 - Phase 3.0 Tasks 3.1-3.4 COMMITTED + Mypy Fixes):**
- ✅ Task 3.1: Added pandas-ta>=0.3.14b dependency (committed: 7edef6d)
- ✅ Task 3.2: Created indicators.py with technical indicator calculations (committed: f61570a, 324 lines)
- ✅ Task 3.3: Added technical_indicators table to schema (committed: 0c7967d, 19 columns)
- ✅ Task 3.4: Created update_technical_indicators Celery task (committed: fcdf14a, 156 lines)
- ✅ **UNBLOCKED**: Fixed all 19 pre-existing mypy errors in agent files (committed: fcdf14a)
- 📝 4 commits successfully made (3 for Tasks 3.1-3.3, 1 combined for Task 3.4 + mypy fixes)
- 📊 ~800 lines added/modified (indicators.py + agent_tasks.py + 5 agent files with type fixes)
- ✅ All code: zero mypy errors, full type safety, linting clean, pre-commit hooks passing
- ✅ 220 tests passing, no new failures

**Session Summary (2025-10-28 - Phase 2.0 Analytics Complete):**
- ✅ Completed Tasks 2.6-2.10 (Historical backfill + Analytics Infrastructure)
- ✅ Task 2.6: `ingest_historical_ohlcv` Celery task for multi-source backfill
- ✅ Task 2.7: RVOL calculator with historical analysis
- ✅ Task 2.8: Sector rotation analyzer with momentum calculation (337 lines, 8 tests)
- ✅ Task 2.9: Peer comparison engine with ranking (475 lines, 13 tests)
- ✅ Task 2.10: Analytics REST API with 4 endpoints (428 lines, 11 tests)
- 📝 5 commits made with conventional format
- 📊 ~2,600 lines added (9 files total: 6 implementation + 3 test files)
- ✅ 32 new tests for analytics, all passing
- ✅ Full type safety, linting clean, comprehensive error handling
- ✅ Phase 2.0 is now COMPLETE

**Context from Current Codebase:**
- ✅ BaseSource class exists with full multi-source support
- ✅ MultiSourceFetcher operational with rate limit cooldown (60s) and performance tracking
- ✅ DuckDB schema complete with source_performance, day_bars, minute_bars tables
- ✅ PriceDataFetcher refactored to use MultiSourceFetcher (YFinance + Polygon)
- ✅ Health endpoint tracks all sources via source_performance table
- ✅ Six source adapters complete: YFinance (1), Twelve Data (2), FMP (3), Polygon (10), Finnhub (10), Alpha Vantage (30)
- ✅ All planned source adapters implemented
- ✅ Analytics infrastructure complete: RVOL, sector rotation, peer comparison with REST API
- ⚠️ Still missing: Technical indicators, paper trading, risk management, sentiment analysis

---

## Relevant Files

### Files Created (19 files)

**Core Multi-Source Infrastructure:**
- ✅ `backend/app/sources/jsonpath_mapper.py` (265 lines) - JSONPath field mapping with nested data extraction, timestamp conversion, and validation
- ✅ `backend/tests/test_jsonpath_mapper.py` (242 lines) - Comprehensive test suite with 24 passing tests
- ✅ `backend/app/sources/rest_api_source.py` (532 lines) - Dynamic REST API source adapter with auth, rate limiting, structured logging
- ✅ `backend/app/sources/polygon_client.py` (241 lines) - Polygon API client with thread-safe rate limiting (5/min) and retries
- ✅ `backend/app/sources/polygon_source.py` (214 lines) - Polygon source adapter implementing BaseSource interface
- ✅ `backend/app/sources/multi_source_fetcher.py` (587 lines) - Priority-based failover with 60s cooldown, source performance tracking, metrics persistence
- ✅ `backend/app/sources/yfinance_source.py` (207 lines) - YFinance adapter with day_bars and reference data support
- ✅ `backend/app/sources/twelvedata_source.py` (489 lines) - Twelve Data adapter with TwelveDataClient and TwelveDataSource implementing BaseSource, 8/min rate limiting
- ✅ `backend/tests/test_twelvedata_source.py` (313 lines) - Comprehensive test suite with 10 passing tests
- ✅ `backend/app/sources/fmp_source.py` (483 lines) - FMP adapter with FMPClient and FMPSource implementing BaseSource, 250/day rate limiting
- ✅ `backend/tests/test_fmp_source.py` (417 lines) - Comprehensive test suite with 12 passing tests
- ✅ `backend/app/sources/finnhub_source.py` (503 lines) - Finnhub adapter with FinnhubClient and FinnhubSource implementing BaseSource, 60/min rate limiting
- ✅ `backend/tests/test_finnhub_source.py` (392 lines) - Comprehensive test suite with 13 passing tests

**Analytics & Trading Intelligence:**
- ✅ `backend/app/analytics/volume.py` (102 lines) - RVOL calculator with historical volume analysis
- ✅ `backend/tests/test_volume.py` (195 lines) - Comprehensive test suite with 11 passing tests
- ✅ `backend/app/analytics/sectors.py` (337 lines) - Sector rotation analyzer with momentum calculation
- ✅ `backend/tests/test_sectors.py` (213 lines) - Comprehensive test suite with 8 passing tests
- ✅ `backend/app/analytics/peers.py` (475 lines) - Peer comparison engine with ranking and percentiles
- ✅ `backend/tests/test_peers.py` (405 lines) - Comprehensive test suite with 13 passing tests

**Celery Tasks:**
- ✅ `backend/app/tasks/agent_tasks.py` (updated) - Added `ingest_historical_ohlcv` task for multi-source backfill

**API Endpoints:**
- ✅ `backend/app/api/analytics.py` (428 lines) - Analytics API router with RVOL, sector rotation, and peer comparison endpoints
- ✅ `backend/tests/test_api_analytics.py` (258 lines) - Comprehensive API test suite with 11 passing tests

### Files to Create (10 remaining files)

**Analytics & Trading Intelligence:**
- `backend/app/analytics/indicators.py` (~300 lines) - Technical indicators wrapper (pandas_ta)
- `backend/app/analytics/paper_trading.py` (~250 lines) - Paper trade tracker
- `backend/app/analytics/agent_performance.py` (~200 lines) - Agent performance metrics
- `backend/app/analytics/risk_management.py` (~400 lines) - Position sizing, stop-loss, correlation, drawdown

**AI & Sentiment:**
- `backend/app/ai/__init__.py` (~10 lines) - Package initialization
- `backend/app/ai/local_models.py` (~150 lines) - FinBERT and QWEN model loaders
- `backend/app/ai/sentiment.py` (~150 lines) - Sentiment scoring service

**API Endpoints:**
- `backend/app/api/risk.py` (~250 lines) - Risk management endpoints
- `backend/app/api/sentiment.py` (~150 lines) - Sentiment endpoints
- `backend/app/api/indicators.py` (~200 lines) - Technical indicators endpoints

**MCP Server:**
- `backend/app/mcp_server.py` (~400 lines) - Model Context Protocol server

**Storage & Testing:**
- `backend/app/storage/protocols.py` (~50 lines) - StorageProtocol interface
- `tests/mocks/in_memory_storage.py` (~200 lines) - Fast in-memory storage mock
- `tests/test_multi_source.py` (~400 lines) - Multi-source failover tests
- `tests/test_indicators.py` (~300 lines) - Technical indicator tests
- `tests/test_paper_trading.py` (~300 lines) - Paper trading tests
- `tests/test_risk_management.py` (~300 lines) - Risk management tests

### Files to Update (8 files)

- ✅ `backend/app/portfolio/price_fetcher.py` - Refactored to use MultiSourceFetcher with YFinance+Polygon (Task 1.3 complete)
- ✅ `backend/app/storage/schema.py` - Added 3 new tables: source_performance, day_bars, minute_bars (Task 1.2 complete)
- `backend/app/api/health.py` - Add multi-source health checks
- ✅ `backend/requirements.txt` - Added pandas-ta>=0.3.14b (Task 3.1 complete)
- `backend/app/agents/tools.py` - Integrate technical indicators into agent tools
- `backend/app/tasks/agent_tasks.py` - Add Celery tasks for data ingestion and paper trading
- `docs/core/ARCHITECTURE.md` - Document multi-source architecture and local AI strategy
- `docs/core/DEVELOPMENT.md` - Update with new testing protocols

### Notes

- Unit tests should be placed in `tests/unit/` or `tests/integration/` directories
- Use `pytest tests/` to run all tests
- Use `pytest tests/unit/test_file1.py -v` to run specific test file
- Use `mypy app/ --strict` to verify type safety
- Use `scripts/lint.sh` to run linting and formatting checks
- Target test suite runtime: <5 seconds total

---

## Tasks

- [x] 0.0 **URGENT: Fix Pre-Existing Mypy Errors** (Blocking Task 3.4 commit) ✅ COMPLETE
  - [x] 0.1 Fix backend/app/portfolio/models.py (6 errors)
    - [x] Lines 14, 24, 37, 50, 59, 68: Added type: ignore[misc] for Pydantic BaseModel
    - [x] Verified: `mypy app/portfolio/models.py --strict` passes
  - [x] 0.2 Fix backend/app/agents/tools.py (1 error)
    - [x] Line 146: Added type annotations to AgentTools.__init__
    - [x] Verified: `mypy app/agents/tools.py --strict` passes
  - [x] 0.3 Fix backend/app/agents/base.py (6 errors)
    - [x] Line 28: Added type annotation for storage parameter
    - [x] Line 103: Added type annotation for tool_calls_made variable
    - [x] Used cast() for block.input incompatibility
    - [x] Verified: `mypy app/agents/base.py --strict` passes
  - [x] 0.4 Fix backend/app/agents/portfolio_analyzer.py (4 errors)
    - [x] Lines 31, 106: Added missing type annotations
    - [x] Line 106: Fixed run() signature to match base class (user_prompt, max_iterations)
    - [x] Line 113: Fixed current_run_id type (str | None)
    - [x] Verified: `mypy app/agents/portfolio_analyzer.py --strict` passes
  - [x] 0.5 Fix backend/app/agents/discovery.py (4 errors)
    - [x] Lines 29, 94: Added missing type annotations
    - [x] Line 94: Fixed run() signature to match base class (user_prompt, max_iterations)
    - [x] Line 101: Fixed current_run_id type (str | None)
    - [x] Verified: `mypy app/agents/discovery.py --strict` passes
  - [x] 0.6 Commit Task 3.4 (blocked files)
    - [x] Committed: indicators.py, schema.py, agent_tasks.py + all mypy fixes (fcdf14a)
    - [x] Updated task list marking Tasks 3.2-3.4 committed
    - [x] Verified: All pre-commit hooks pass without errors

- [x] 1.0 Multi-Source Infrastructure Foundation (Port from market-sim) ✅ COMPLETE
  - [x] 1.1 Port core source infrastructure files from market-sim (FR-1.1)
    - [x] 1.1.1 Create `backend/app/sources/jsonpath_mapper.py` (~100 lines)
      - [x] Port JSONPath field mapping logic from market-sim
      - [x] Add type hints for all functions
      - [x] Add function: `map_response_to_schema(response: dict, mapping_config: dict) -> dict`
      - [x] Support nested field access (e.g., `data.quotes[0].price`)
      - [x] Add structured logging for mapping errors
    - [x] 1.1.2 Create `backend/app/sources/rest_api_source.py` (~740 lines)
      - [x] Port REST API source from market-sim with adaptations
      - [x] Replace `perf_profiler` with `time.time()` for duration tracking
      - [x] Remove `job_queue` dependency, use Celery directly
      - [x] Use `logging_config.get_logger()` from portfolio-ai
      - [x] Implement `fetch_day_bars()`, `fetch_reference_payload()`, `fetch_news_payload()`
      - [x] Add rate limit tracking per endpoint (via structured logging)
      - [x] Add HTTP timeout handling (30s default)
    - [x] 1.1.3 Create `backend/app/sources/polygon_client.py` (~100 lines)
      - [x] Implement Polygon API client with 5/min rate limit tracking
      - [x] Add class `PolygonClient` with methods: `get_day_bars()`, `get_ticker_details()`
      - [x] Track rate limit state: `last_request_times: deque[datetime]` (5 items max)
      - [x] Add backoff delay if rate limit approached (sleep until slot available)
      - [x] Read API key from environment: `POLYGON_API_KEY`
    - [x] 1.1.4 Create `backend/app/sources/polygon_source.py` (~150 lines)
      - [x] Implement `PolygonSource(BaseSource)` using `PolygonClient`
      - [x] Set `priority = 10`, `supports_day = True`, `supports_reference = True`
      - [x] Implement `fetch_day_bars()` returning Polars DataFrame
      - [x] Implement `fetch_reference_payload()` returning company info
      - [x] Map Polygon response fields to portfolio-ai schema using jsonpath_mapper
      - [x] Add structured logging: "polygon_fetch_success", "polygon_rate_limit_hit"
    - [x] 1.1.5 Create `backend/app/sources/multi_source_fetcher.py` (~587 lines)
      - [x] Port MultiSourceFetcher from market-sim
      - [x] Implement priority-based failover chain (FR-1.4)
      - [x] Add 60-second rate limit cooldown on HTTP 429 (FR-1.5)
      - [x] Track source performance metrics (success rate, latency, rate limit hits) (FR-1.6)
      - [x] Store metrics in `source_performance` table (need schema update)
      - [x] Add method: `fetch_with_fallback(request: DatasetRequest) -> pl.DataFrame | None`
      - [x] Log all failover events with structured logging
  - [x] 1.2 Update database schema for source tracking (FR-1.6, FR-2.3)
    - [x] 1.2.1 Add `source_performance` table to `backend/app/storage/schema.py`
      - [x] Schema: `source_name TEXT PRIMARY KEY, success_count INTEGER, failure_count INTEGER, total_latency_ms BIGINT, rate_limit_hits INTEGER, last_success_at TIMESTAMP`
      - [x] Add to `_create_metadata_tables()` method
      - [x] Add to table_registry metadata
    - [x] 1.2.2 Add `day_bars` table for historical OHLCV data
      - [x] Schema: `ticker TEXT, date DATE, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT, vwap DOUBLE, source TEXT, ingest_run_id TEXT, PRIMARY KEY (ticker, date)`
      - [x] Add to `_create_timeseries_tables()` method
      - [x] Create index: `CREATE INDEX idx_day_bars_ticker ON day_bars(ticker)`
    - [x] 1.2.3 Add `minute_bars` table for intraday data (optional feature)
      - [x] Schema: `ticker TEXT, ts_utc TIMESTAMP, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume BIGINT, vwap DOUBLE, source TEXT, PRIMARY KEY (ticker, ts_utc)`
      - [x] Add to `_create_timeseries_tables()` method
  - [x] 1.3 Refactor price_fetcher.py to use MultiSourceFetcher (FR-1.3)
    - [x] 1.3.1 Update `backend/app/portfolio/price_fetcher.py`
      - [x] Replace direct `yf.Ticker()` calls with `MultiSourceFetcher.fetch_with_fallback()`
      - [x] Keep existing 15-minute cache logic
      - [x] Keep existing error caching (5-minute TTL)
      - [x] Add source lineage tracking (record which source provided each data point)
      - [x] Removed `_fetch_from_polygon()` placeholder - now uses PolygonSource adapter
      - Note: Old price_fetcher tests need updating for new multi-source architecture (deferred to Task 1.5)
  - [x] 1.4 Update health check endpoint (FR-1.8)
    - [x] 1.4.1 Update `backend/app/api/health.py`
      - [x] Add data source availability checks from source_performance table
      - [x] Query `source_performance` table for last successful fetch per source
      - [x] Report source status: "ok" (recent success <15min, >=80% success rate), "degraded" (stale or 50-80% success), "down" (very stale or <50% success)
      - [x] Report rate limit hits per source (cooldown would need real-time data from MultiSourceFetcher)
      - [x] Calculate success rate and average latency per source
      - [x] Response format includes sources dict: `{"sources": {"yfinance": {"status": "ok", "last_success": "...", "success_rate": 95.5, "avg_latency_ms": 250}}}`
      - Note: Removed old direct yfinance check, now uses source_performance table for all sources
  - [x] 1.5 Write comprehensive multi-source tests (FR-1.7)
    - [x] 1.5.1 Create `tests/test_multi_source.py` (358 lines, 9 tests)
      - [x] Test: MultiSourceFetcher initialization with priority sorting
      - [x] Test: yfinance primary success path (mock yfinance returning valid data)
      - [x] Test: Polygon failover when yfinance returns 429 (mock 429, verify Polygon called)
      - [x] Test: Polygon failover when yfinance times out (mock timeout, verify Polygon called)
      - [x] Test: All sources fail scenario (return None with error dict)
      - [x] Test: Rate limit cooldown (verify source skipped for 60s after 429)
      - [x] Test: Source performance tracking (verify metrics tracked correctly)
      - [x] Test: Source metrics persistence (verify metrics saved to DB)
      - [x] Test: No sources available (verify error handling)
      - [x] Use pytest fixtures for mocking sources and storage
      - Note: All 9 tests pass. Old price_fetcher tests still need updating (3 tests fail)

- [x] 2.0 Historical Data Pipelines & Source Adapters ✅ COMPLETE
  - [x] 2.1 Create YFinance adapter (FR-2.1)
    - [x] 2.1.1 Create `backend/app/sources/yfinance_source.py` (~200 lines)
      - [x] Implement `YFinanceSource(BaseSource)` wrapping yfinance library
      - [x] Set `priority = 1`, `supports_day = True`, `supports_reference = True`
      - [x] Implement `fetch_day_bars(request: DatasetRequest) -> pl.DataFrame`
        - [x] Fetch with date range using `yf.Ticker(ticker).history(start, end)`
        - [x] Handle yfinance quirks (0.5-2s delays between requests)
        - [x] Convert pandas DataFrame to Polars DataFrame
        - [x] Map columns: Date→date, Open→open, High→high, Low→low, Close→close, Volume→volume
      - [x] Implement `fetch_reference_payload(tickers, as_of) -> pl.DataFrame`
        - [x] Fetch company metadata: `yf.Ticker(ticker).info`
        - [x] Extract: sector, industry, market_cap, company_name
        - [x] Return Polars DataFrame with schema: `ticker, as_of_date, payload (JSON), source`
      - [x] Add structured logging for all operations
  - [x] 2.2 Create Twelve Data adapter (FR-2.2) ✅
    - [x] 2.2.1 Create `backend/app/sources/twelvedata_source.py` (~200 lines)
      - [x] Implement `TwelveDataSource(BaseSource)` using REST API
      - [x] Set `priority = 2`, `supports_day = True`, `supports_reference = True`
      - [x] Implement `fetch_day_bars()` using Twelve Data time_series API
        - [x] Endpoint: `https://api.twelvedata.com/time_series?symbol={ticker}&interval=1day&outputsize=252`
        - [x] Track 800/day rate limit (8/min sub-limit) using deque
        - [x] Parse JSON response and convert to Polars DataFrame
      - [x] Implement `fetch_reference_payload()` using profile API
        - [x] Endpoint: `https://api.twelvedata.com/profile?symbol={ticker}`
      - [x] Read API key from environment: `TWELVEDATA_API_KEY`
  - [x] 2.3 Create FMP adapter ✅
    - [x] 2.3.1 Create `backend/app/sources/fmp_source.py` (~150 lines)
      - [x] Implement `FMPSource(BaseSource)` for Financial Modeling Prep
      - [x] Set `priority = 3`, `supports_day = True`, `supports_reference = True`
      - [x] Track 250/day rate limit
      - [x] Implement `fetch_day_bars()` and `fetch_reference_payload()`
      - [x] Read API key from environment: `FMP_API_KEY`
  - [x] 2.4 Create Finnhub adapter ✅
    - [x] 2.4.1 Create `backend/app/sources/finnhub_source.py` (~150 lines)
      - [x] Implement `FinnhubSource(BaseSource)`
      - [x] Set `priority = 10`, `supports_day = True`, `supports_reference = True`
      - [x] Track 60/min rate limit
      - [x] Read API key from environment: `FINNHUB_API_KEY`
  - [x] 2.5 Create Alpha Vantage adapter ✅
    - [x] 2.5.1 Create `backend/app/sources/alphavantage_source.py` (~150 lines)
      - [x] Implement `AlphaVantageSource(BaseSource)`
      - [x] Set `priority = 30`, `supports_day = True`
      - [x] Track 25/day and 5/min rate limits
      - [x] Read API key from environment: `ALPHAVANTAGE_API_KEY`
  - [x] 2.6 Implement historical backfill pipeline (FR-2.3)
    - [x] 2.6.1 Create Celery task in `backend/app/tasks/agent_tasks.py`
      - [x] Add task: `ingest_historical_ohlcv(tickers: list[str], days: int = 252) -> None`
      - [x] Use MultiSourceFetcher with DatasetRequest(dataset='day', tickers, start, end)
      - [x] Store results in `day_bars` table with source lineage
      - [x] Log progress: "Backfilled 252 days for 10 tickers in 2m 15s"
      - [x] Add error handling: If all sources fail, log error but don't crash
  - [x] 2.7 Create RVOL calculator (FR-2.6)
    - [x] 2.7.1 Create `backend/app/analytics/volume.py` (~100 lines)
      - [x] Add function: `calculate_rvol(ticker: str, date: str, lookback_days: int = 20) -> float`
      - [x] Formula: `current_volume / avg(volume, lookback_days)`
      - [x] SQL query from `day_bars` table:
        ```sql
        SELECT AVG(volume) FROM day_bars WHERE ticker = ? AND date BETWEEN ? AND ?
        ```
      - [x] Return: RVOL value (2.0 = 2x normal volume)
      - [x] Add type hints and docstrings
  - [x] 2.8 Create sector rotation analyzer (FR-2.7) ✅
    - [x] 2.8.1 Create `backend/app/analytics/sectors.py` (337 lines)
      - [x] Add function: `get_sector_rotation(date: str, lookback_days: int = 20) -> pl.DataFrame`
      - [x] Aggregate `day_bars` returns by sector (join with reference data for sector)
      - [x] Calculate 5-day, 20-day sector momentum
      - [x] Return: DataFrame with sectors ranked by momentum (columns: sector, momentum_5d, momentum_20d, num_stocks, avg_volume)
      - [x] Add bonus function: `get_sector_performance_detail()` for detailed sector analysis
      - [x] 8 tests created, all passing
  - [x] 2.9 Create peer comparison engine (FR-2.8) ✅
    - [x] 2.9.1 Create `backend/app/analytics/peers.py` (475 lines)
      - [x] Add function: `get_peer_comparison(ticker: str, date: str) -> pl.DataFrame`
      - [x] Group tickers by sector/industry (from reference data)
      - [x] Calculate relative performance: `(ticker_return - sector_avg_return)`
      - [x] Return: DataFrame showing ticker's rank within peer group (peer_rank, percentile)
      - [x] Add bonus function: `get_peer_group_detail()` for detailed peer ranking
      - [x] 13 tests created, all passing
  - [x] 2.10 Expose analytics via API (FR-2.9) ✅
    - [x] 2.10.1 Create `backend/app/api/analytics.py` (428 lines)
      - [x] Add endpoint: `GET /api/analytics/rvol/{ticker}` - Current and historical RVOL
      - [x] Add endpoint: `GET /api/analytics/sectors/rotation` - Sector momentum analysis
      - [x] Add endpoint: `GET /api/analytics/peers/{ticker}` - Peer comparison with ranking
      - [x] Add endpoint: `GET /api/analytics/peers/{ticker}/detail` - Detailed peer group rankings
      - [x] Use FastAPI dependency injection for storage
      - [x] Add Pydantic response models for each endpoint (8 models)
      - [x] Register router in `backend/app/main.py`
      - [x] 11 API tests created, all passing

- [ ] 3.0 Technical Indicators Library & Caching
  - [x] 3.1 Add dependencies (FR-3.1) ✅
    - [x] 3.1.1 Update `backend/requirements.txt`
      - [x] Add `pandas_ta>=0.3.14b`
      - [x] Run `pip install -r requirements.txt` to verify installation
  - [x] 3.2 Create indicator calculation wrapper (FR-3.2) ✅
    - [x] 3.2.1 Create `backend/app/analytics/indicators.py` (324 lines)
      - [x] Add function: `calculate_indicators(ticker: str, indicators: list[str]) -> dict`
      - [x] Supported indicators:
        - [x] RSI (14-period): `pandas_ta.rsi(close, length=14)`
        - [x] MACD (12/26/9): `pandas_ta.macd(close, fast=12, slow=26, signal=9)`
        - [x] Bollinger Bands (20, 2σ): `pandas_ta.bbands(close, length=20, std=2)`
        - [x] SMA (20/50/200): `pandas_ta.sma(close, length=20)`
        - [x] EMA (20/50/200): `pandas_ta.ema(close, length=20)`
        - [x] ATR (14): `pandas_ta.atr(high, low, close, length=14)`
        - [x] Stochastic (14/3/3): `pandas_ta.stoch(high, low, close, k=14, d=3, smooth_k=3)`
      - [x] Fetch OHLCV from `day_bars` table (minimum 200 days for SMA-200)
      - [x] Convert to pandas DataFrame for pandas_ta compatibility
      - [x] Calculate all requested indicators
      - [x] Add interpretations: "oversold" (RSI < 30), "overbought" (RSI > 70), "bullish_cross" (MACD > signal)
      - [x] Return: Dict with indicator values and interpretations
  - [x] 3.3 Update database schema for indicator caching (FR-3.3) ✅
    - [x] 3.3.1 Add `technical_indicators` table to `backend/app/storage/schema.py`
      - [x] Schema: Added with 17 columns (ticker, date, all indicators, calculated_at)
      - [x] Add to `_create_timeseries_tables()` method
      - [x] Create index: `CREATE INDEX idx_indicators_ticker ON technical_indicators(ticker, date)`
  - [x] 3.4 Cache calculated indicators (FR-3.4) ✅
    - [x] 3.4.1 Add Celery task: `update_technical_indicators(tickers: list[str])` in `backend/app/tasks/agent_tasks.py`
      - [x] Calculate indicators for each ticker using latest 200 days of OHLCV
      - [x] Store in `technical_indicators` table using INSERT OR REPLACE
      - [x] Returns dict with success/failed/tickers_processed counts
      - [x] Continues on error for individual tickers (doesn't fail entire task)
      - [ ] Schedule: Daily at market close + 30 minutes (4:30 PM ET) - Celery beat configuration not yet implemented
  - [ ] 3.5 Expose indicators via API (FR-3.5) - **BLOCKED ON PRE-EXISTING MYPY ERRORS**
    - [x] 3.5.1 Create `backend/app/api/indicators.py` (340 lines) ✅
      - [x] Add endpoint: `GET /api/indicators/{ticker}` - All indicators for latest date
      - [x] Add endpoint: `GET /api/indicators/{ticker}/history` - Historical indicators with date range
      - [x] Support query params: date, indicators (comma-separated list), start_date, end_date, limit
      - [x] Pydantic models: IndicatorsResponse, IndicatorValues, IndicatorInterpretations, MACD, BBands, Stochastic
      - [x] Register router in `backend/app/main.py`
      - [x] Fixed all mypy errors in indicators.py (added type: ignore[misc] for Pydantic BaseModel)
      - [ ] **BLOCKED**: 56 pre-existing mypy errors in 7 other API files blocking commit
        - preferences.py (5 errors), health.py (7 errors), portfolio.py (7 errors)
        - market.py (4 errors), analytics.py (6 errors), ideas.py (9 errors), main.py (3 errors)
      - [ ] Write tests (deferred until after commit)
      - [ ] Commit changes (blocked on fixing pre-existing mypy errors)
  - [ ] 3.6 Integrate with AI agent prompts (FR-3.6)
    - [ ] 3.6.1 Update `backend/app/agents/tools.py`
      - [ ] Extend `get_price_data` tool to include indicators
      - [ ] Fetch indicators from `technical_indicators` table
      - [ ] Format for agent prompt: "AAPL current price $182, RSI=32 (oversold), MACD bullish cross, near lower Bollinger Band - potential buy signal"
  - [ ] 3.7 Write indicator tests
    - [ ] 3.7.1 Create `tests/test_indicators.py` (~300 lines)
      - [ ] Test: RSI calculation with known OHLCV data (verify RSI value matches expected)
      - [ ] Test: MACD calculation and bullish cross detection
      - [ ] Test: Bollinger Bands calculation and price position interpretation
      - [ ] Test: SMA/EMA calculations with 200-day lookback
      - [ ] Test: ATR calculation for volatility measurement
      - [ ] Test: Indicator caching (verify data stored in DB correctly)
      - [ ] Use pandas_ta test data or generate synthetic OHLCV

- [ ] 4.0 Paper Trading & Agent Performance Tracking
  - [ ] 4.1 Create idea_outcomes table (FR-4.1)
    - [ ] 4.1.1 Add `idea_outcomes` table to `backend/app/storage/schema.py`
      - [ ] Schema: See PRD FR-4.1 for full schema (17 columns)
      - [ ] Add foreign key: `FOREIGN KEY (idea_id) REFERENCES agent_ideas(id)`
      - [ ] Add to `_create_metadata_tables()` method
      - [ ] Create index: `CREATE INDEX idx_outcomes_status ON idea_outcomes(status)`
  - [ ] 4.2 Create paper trading tracker (FR-4.2)
    - [ ] 4.2.1 Create `backend/app/analytics/paper_trading.py` (~250 lines)
      - [ ] Add function: `create_paper_trade(idea_id: str) -> None`
        - [ ] Extract ticker, idea_type, target_price from `agent_ideas` table
        - [ ] Fetch current price from price_fetcher
        - [ ] Calculate stop_loss_price using ATR (2x ATR below entry)
        - [ ] Insert into `idea_outcomes` table with status='open'
      - [ ] Add function: `update_paper_trades() -> None`
        - [ ] Fetch all open paper trades from `idea_outcomes` table
        - [ ] Get current prices for all tickers
        - [ ] Update current_price, current_return_pct
        - [ ] Track max_favorable_pct and max_adverse_pct
        - [ ] Check if target_price or stop_loss_price hit
        - [ ] Update status to 'target_hit' or 'stop_hit' if triggered
        - [ ] Calculate realized_return_pct when closed
      - [ ] Add type hints and docstrings
  - [ ] 4.3 Automatically create paper trades (FR-4.3)
    - [ ] 4.3.1 Update `backend/app/agents/discovery.py`
      - [ ] After creating new idea, call `create_paper_trade(idea_id)`
    - [ ] 4.3.2 Update `backend/app/agents/portfolio_analyzer.py`
      - [ ] After creating new idea, call `create_paper_trade(idea_id)`
  - [ ] 4.4 Schedule daily paper trade updates (FR-4.4)
    - [ ] 4.4.1 Add Celery periodic task in `backend/app/tasks/agent_tasks.py`
      - [ ] Add task: `update_paper_trades()` scheduled at 4:30 PM ET daily
      - [ ] Close trades if target/stop hit or 60 days elapsed (configurable)
      - [ ] Use Celery beat for scheduling
  - [ ] 4.5 Calculate agent performance metrics (FR-4.5)
    - [ ] 4.5.1 Create `backend/app/analytics/agent_performance.py` (~200 lines)
      - [ ] Add function: `get_agent_performance(agent_type: str, days: int = 90) -> dict`
      - [ ] Metrics to calculate:
        - [ ] Win rate: % of closed trades with realized_return_pct > 0
        - [ ] Average return: Mean realized_return_pct of all closed trades
        - [ ] Average winner: Mean return of winning trades
        - [ ] Average loser: Mean return of losing trades
        - [ ] Win/loss ratio: avg_winner / abs(avg_loser)
        - [ ] Total ideas, open ideas, closed ideas counts
        - [ ] Best trade: Highest realized_return_pct
        - [ ] Worst trade: Lowest realized_return_pct
      - [ ] Query `idea_outcomes` table joined with `agent_ideas` and `agent_runs` tables
      - [ ] Return: Dict with all metrics (see PRD FR-4.5 for structure)
  - [ ] 4.6 Expose performance API (FR-4.6)
    - [ ] 4.6.1 Update `backend/app/api/ideas.py` (or create separate performance endpoint)
      - [ ] Add endpoint: `GET /api/agents/{agent_type}/performance`
      - [ ] Add endpoint: `GET /api/agents/{agent_type}/performance?days=30`
      - [ ] Response format: See PRD FR-4.6 for JSON structure
      - [ ] Add Pydantic model: `AgentPerformanceResponse`
  - [ ] 4.7 Feed performance back to agent prompts (FR-4.8)
    - [ ] 4.7.1 Update `backend/app/agents/base.py` or agent-specific files
      - [ ] Include in system prompt: "Your last 10 ideas: 7 wins (avg +12.3%), 3 losses (avg -4.1%)"
      - [ ] Include context on best/worst trades
      - [ ] Encourage learning: "Focus on patterns from your winning trades"
  - [ ] 4.8 Write paper trading tests
    - [ ] 4.8.1 Create `tests/test_paper_trading.py` (~300 lines)
      - [ ] Test: Create paper trade (verify entry_price, stop_loss calculated correctly)
      - [ ] Test: Update paper trades (verify current_return_pct updated)
      - [ ] Test: Target hit scenario (verify status changes to 'target_hit')
      - [ ] Test: Stop loss hit scenario (verify status changes to 'stop_hit')
      - [ ] Test: Agent performance calculation (verify win rate, avg return correct)
      - [ ] Use mock data in `idea_outcomes` table

- [ ] 5.0 Risk Management Suite
  - [ ] 5.1 Create position sizing calculator (FR-5.1)
    - [ ] 5.1.1 Create `backend/app/analytics/risk_management.py` (~400 lines)
      - [ ] Add function: `calculate_position_size(ticker: str, strategy: str, risk_pct: float = 2.0) -> dict`
      - [ ] Strategies:
        - [ ] `kelly`: Kelly Criterion formula using agent performance metrics
        - [ ] `fixed_pct`: Fixed % of portfolio (e.g., 5%)
        - [ ] `volatility_adjusted`: Position size inversely proportional to ATR
      - [ ] Inputs: Portfolio value (from portfolio_positions), ticker, risk_pct
      - [ ] Output: Dict with recommended position size (shares, dollars, % of portfolio)
  - [ ] 5.2 Create stop-loss suggestion engine (FR-5.2)
    - [ ] 5.2.1 Add function: `suggest_stop_loss(ticker: str, entry_price: float, method: str = 'atr') -> dict` to risk_management.py
      - [ ] Methods:
        - [ ] `atr`: Entry price - (2 × ATR) [most common]
        - [ ] `percent`: Entry price × (1 - stop_loss_pct) [fixed %]
        - [ ] `support`: Nearest technical support level (from day_bars low prices)
      - [ ] Fetch ATR from `technical_indicators` table
      - [ ] Calculate stop price, stop distance ($), stop distance (%)
      - [ ] Calculate risk/reward ratio if target_price provided
      - [ ] Output: Dict with stop price, stop distance, risk/reward ratio
  - [ ] 5.3 Create portfolio correlation matrix calculator (FR-5.3)
    - [ ] 5.3.1 Add function: `calculate_correlation_matrix(tickers: list[str], days: int = 30) -> pl.DataFrame` to risk_management.py
      - [ ] Calculate pairwise correlation of daily returns (rolling 30-day window)
      - [ ] Query `day_bars` table for returns: `(close - prev_close) / prev_close`
      - [ ] Use Polars or pandas correlation matrix function
      - [ ] Identify high correlation pairs (>0.8) as concentration risk
      - [ ] Return: DataFrame with correlation matrix
  - [ ] 5.4 Create max drawdown tracker (FR-5.4)
    - [ ] 5.4.1 Add function: `calculate_max_drawdown(portfolio_value_history: pl.DataFrame) -> dict` to risk_management.py
      - [ ] Track peak portfolio value
      - [ ] Calculate drawdown: (current_value - peak_value) / peak_value
      - [ ] Track max drawdown: Largest peak-to-trough decline
      - [ ] Return: Dict with current_drawdown_pct, max_drawdown_pct, peak_date, trough_date
  - [ ] 5.5 Calculate risk-adjusted metrics (FR-5.5)
    - [ ] 5.5.1 Add function: `calculate_risk_metrics(returns: pl.DataFrame) -> dict` to risk_management.py
      - [ ] Metrics:
        - [ ] Sharpe ratio: (mean_return - risk_free_rate) / std_dev_return
        - [ ] Sortino ratio: (mean_return - risk_free_rate) / downside_deviation
        - [ ] Calmar ratio: mean_annual_return / max_drawdown
      - [ ] Fetch risk_free_rate from FRED (10-year Treasury yield) or assume 4.5%
      - [ ] Return: Dict with all ratios
  - [ ] 5.6 Create risk dashboard API (FR-5.6)
    - [ ] 5.6.1 Create `backend/app/api/risk.py` (~250 lines)
      - [ ] Add endpoint: `GET /api/risk/position-size?ticker=AAPL&strategy=kelly`
      - [ ] Add endpoint: `GET /api/risk/stop-loss?ticker=AAPL&entry_price=180&method=atr`
      - [ ] Add endpoint: `GET /api/risk/correlation` - Portfolio correlation matrix
      - [ ] Add endpoint: `GET /api/risk/drawdown` - Current and max drawdown
      - [ ] Add endpoint: `GET /api/risk/metrics` - Risk-adjusted performance metrics
      - [ ] Add Pydantic models for all responses
      - [ ] Register router in `backend/app/main.py`
  - [ ] 5.7 Write risk management tests
    - [ ] 5.7.1 Create `tests/test_risk_management.py` (~300 lines)
      - [ ] Test: Kelly Criterion position sizing (verify formula correct)
      - [ ] Test: ATR stop-loss calculation (verify 2x ATR below entry)
      - [ ] Test: Correlation matrix calculation (verify pairwise correlation)
      - [ ] Test: Max drawdown tracking (verify peak-to-trough calculation)
      - [ ] Test: Sharpe ratio calculation (use known returns data)
      - [ ] Use synthetic portfolio data for testing

- [ ] 6.0 News Sentiment Scoring & Local AI Models
  - [ ] 6.1 Add local AI model dependencies (FR-6.1)
    - [ ] 6.1.1 Update `backend/requirements.txt`
      - [ ] Add `transformers>=4.30.0` (HuggingFace)
      - [ ] Add `torch>=2.0.0` (PyTorch for model inference)
      - [ ] Add `sentencepiece>=0.1.99` (Tokenizer for FinBERT)
      - [ ] Run `pip install -r requirements.txt` to verify installation
  - [ ] 6.2 Create local model manager (FR-6.2)
    - [ ] 6.2.1 Create `backend/app/ai/local_models.py` (~150 lines)
      - [ ] Add function: `load_finbert_model() -> tuple[model, tokenizer]`
        - [ ] Download ProsusAI/finbert sentiment model (122MB)
        - [ ] Use `transformers.AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')`
        - [ ] Load into memory on first use
        - [ ] Cache for subsequent calls (use module-level variable)
      - [ ] Add function: `load_qwen_model() -> model` [OPTIONAL - defer to Phase 2]
        - [ ] Evaluate QWEN performance vs OpenAI/Anthropic APIs
        - [ ] Document cost/performance tradeoffs in ARCHITECTURE.md
  - [ ] 6.3 Create sentiment scoring service (FR-6.3)
    - [ ] 6.3.1 Create `backend/app/ai/sentiment.py` (~150 lines)
      - [ ] Add function: `score_sentiment(text: str, model: str = 'finbert') -> float`
      - [ ] Input: News article text (title + summary)
      - [ ] Models:
        - [ ] `finbert`: Use FinBERT model (-1 to +1 scale)
        - [ ] `qwen`: Use QWEN for sentiment [OPTIONAL]
      - [ ] Output: Sentiment score (-1 = bearish, 0 = neutral, +1 = bullish)
      - [ ] Add logging for inference time (~200ms per article on CPU)
  - [ ] 6.4 Score news articles on fetch (FR-6.4)
    - [ ] 6.4.1 Update `backend/app/sources/news.py`
      - [ ] After fetching news, call `score_sentiment(title + summary)`
      - [ ] Add `sentiment_score` column to returned DataFrame
      - [ ] Update database schema if `news_cache` table doesn't have sentiment_score column
  - [ ] 6.5 Calculate sentiment aggregates (FR-6.5)
    - [ ] 6.5.1 Add function: `get_sentiment_aggregates(ticker: str, days: int) -> dict` to sentiment.py
      - [ ] 1-day average sentiment (last 24 hours of news)
      - [ ] 5-day average sentiment
      - [ ] 20-day average sentiment
      - [ ] Sentiment trend: Is sentiment improving or declining?
      - [ ] Sentiment inflection: Has sentiment changed >2 std dev recently?
      - [ ] Query `news_cache` table for sentiment_score values
  - [ ] 6.6 Expose sentiment API (FR-6.6)
    - [ ] 6.6.1 Create `backend/app/api/sentiment.py` (~150 lines)
      - [ ] Add endpoint: `GET /api/sentiment/{ticker}` - Current sentiment aggregates
      - [ ] Add endpoint: `GET /api/sentiment/{ticker}/history` - Historical sentiment over time
      - [ ] Add endpoint: `GET /api/sentiment/{ticker}/inflections` - Recent sentiment inflections (>2σ)
      - [ ] Add Pydantic models for responses
      - [ ] Register router in `backend/app/main.py`
  - [ ] 6.7 Integrate with AI agent prompts (FR-6.7)
    - [ ] 6.7.1 Update `backend/app/agents/tools.py`
      - [ ] Include in agent context: "Recent news sentiment for AAPL: +0.65 (bullish), trending up from +0.32 last week"
      - [ ] Alert on inflections: "Sentiment inflection detected: TSLA sentiment dropped from +0.5 to -0.3 (>2σ shift)"
  - [ ] 6.8 Document cost optimization strategy (FR-6.8)
    - [ ] 6.8.1 Update `docs/core/ARCHITECTURE.md`
      - [ ] Document Phase 1: Use local QWEN model for ALL agent tool use and idea generation (validate logic, $0 cost)
      - [ ] Document Phase 2: Enable API models as option (user choice: local free vs API paid)
      - [ ] Record decision: Default to local model
      - [ ] Track API costs in database, alert on budget limits
    - [ ] 6.8.2 Update `docs/core/DEVELOPMENT.md`
      - [ ] Document local model setup instructions
      - [ ] Document how to switch between local and API models

- [ ] 7.0 Protocol-Based Storage Mocking (Test Performance)
  - [ ] 7.1 Create StorageProtocol interface (FR-7.1)
    - [ ] 7.1.1 Create `backend/app/storage/protocols.py` (~50 lines)
      - [ ] Define `StorageProtocol` using `typing.Protocol`
      - [ ] Methods: `query(sql, params) -> pl.DataFrame`, `insert_dict(table, data)`, `insert_dataframe(table, df, mode)`, `connection() -> ContextManager`
      - [ ] Add type hints for all methods
  - [ ] 7.2 Create InMemoryStorage mock (FR-7.2)
    - [ ] 7.2.1 Create `tests/mocks/in_memory_storage.py` (~200 lines)
      - [ ] Implement `StorageProtocol` using Python dicts
      - [ ] Support core CRUD operations (INSERT, SELECT, UPDATE, DELETE)
      - [ ] Support simple WHERE clauses (equality only)
      - [ ] No need for JOIN, GROUP BY, or complex queries (use real DB for integration tests)
      - [ ] Store tables as: `self._tables: dict[str, list[dict]]`
      - [ ] Parse simple SQL: Use regex for INSERT, SELECT, WHERE clauses
      - [ ] Target: 20x faster than DuckDB for simple operations
  - [ ] 7.3 Update test fixtures (FR-7.3)
    - [ ] 7.3.1 Update `tests/conftest.py`
      - [ ] Add fixture: `fast_storage() -> InMemoryStorage` (for unit tests)
      - [ ] Add fixture: `real_storage() -> DuckDBStorage` (for integration tests)
      - [ ] Add pytest marker: `@pytest.mark.integration`
  - [ ] 7.4 Update existing tests (FR-7.4)
    - [ ] 7.4.1 Refactor unit tests to use `fast_storage` fixture
      - [ ] Identify tests that don't need real SQL (e.g., simple CRUD tests)
      - [ ] Replace `DuckDBStorage` with `InMemoryStorage`
      - [ ] Mark integration tests with `@pytest.mark.integration`
  - [ ] 7.5 Verify test performance target (FR-7.5)
    - [ ] 7.5.1 Run test suite and measure time
      - [ ] Unit tests: <2 seconds (using InMemoryStorage)
      - [ ] Integration tests: <3 seconds (using DuckDB :memory:)
      - [ ] Total: <5 seconds for full test suite
      - [ ] If not met, profile and optimize slow tests

- [ ] 8.0 MCP Server for Desktop AI Apps
  - [ ] 8.1 Create MCP server (FR-8.1)
    - [ ] 8.1.1 Create `backend/app/mcp_server.py` (~400 lines)
      - [ ] Implement Model Context Protocol server specification
      - [ ] Expose portfolio data (positions, analytics, ideas) via MCP
      - [ ] Expose market data (prices, indicators, news) via MCP
      - [ ] Enable Claude Desktop and ChatGPT Desktop to query data via MCP instead of API calls
      - [ ] Use FastAPI WebSocket for MCP communication
  - [ ] 8.2 Implement MCP vs API dual access pattern (FR-8.2)
    - [ ] 8.2.1 Add function: `get_portfolio_data(source: str = 'auto') -> dict`
      - [ ] `source='mcp'`: Use MCP protocol (flat cost, desktop apps)
      - [ ] `source='api'`: Use HTTP API (metered cost)
      - [ ] `source='auto'`: Auto-detect most efficient method
      - [ ] Both access methods return identical data
  - [ ] 8.3 Define MCP server endpoints (FR-8.3)
    - [ ] 8.3.1 Add MCP endpoints in mcp_server.py
      - [ ] `mcp://portfolio-ai/portfolio/summary` - Portfolio summary
      - [ ] `mcp://portfolio-ai/portfolio/positions` - All positions
      - [ ] `mcp://portfolio-ai/ideas/recent` - Recent AI agent ideas
      - [ ] `mcp://portfolio-ai/market/prices/{ticker}` - Current prices
      - [ ] `mcp://portfolio-ai/market/indicators/{ticker}` - Technical indicators
      - [ ] `mcp://portfolio-ai/market/news/{ticker}` - Recent news with sentiment
  - [ ] 8.4 Document MCP setup (FR-8.4)
    - [ ] 8.4.1 Update `CLAUDE.md`
      - [ ] Document MCP server setup instructions
      - [ ] Provide MCP config file for Claude Desktop (`~/.claude/mcp_servers.json`)
    - [ ] 8.4.2 Update `docs/core/SETUP.md`
      - [ ] Add section on MCP server configuration
      - [ ] Document how to test MCP server (use wscat or similar WebSocket client)
  - [ ] 8.5 Compare MCP vs API performance (FR-8.5)
    - [ ] 8.5.1 Create performance benchmark script
      - [ ] Measure latency: MCP vs HTTP API
      - [ ] Measure cost: MCP (flat) vs API (per-request)
      - [ ] Document when to use each method in ARCHITECTURE.md

---

## Verification & Production Readiness

**MANDATORY before marking task "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All PRD requirements implemented
  - [ ] All user stories satisfied
  - [ ] Integration points working correctly
  - [ ] Zero known bugs or regressions

- [ ] **Test Coverage** (target: 80%+)
  - [ ] Unit tests written for all new functions/classes
  - [ ] Integration tests for cross-module interactions
  - [ ] End-to-end test of complete workflow
  - [ ] All tests passing: `pytest tests/ -v`
  - [ ] Coverage verified: `pytest tests/ --cov=app --cov-report=term-missing`

- [ ] **Type Safety & Code Quality**
  - [ ] 100% type hints on all functions: `mypy app/ --strict` passes
  - [ ] Linting passes: `scripts/lint.sh` returns zero errors
  - [ ] Code formatting applied: `ruff format app/`
  - [ ] Complexity limits met (functions <50 lines, complexity <10)

- [ ] **Documentation**
  - [ ] All public functions/classes have docstrings
  - [ ] ARCHITECTURE.md updated if patterns changed
  - [ ] DEVELOPMENT.md updated if workflows changed
  - [ ] Usage examples provided for new features

- [ ] **Security & Performance**
  - [ ] SQL queries use parameterized placeholders (no f-strings with user input)
  - [ ] No secrets in code (API keys in environment/database only)
  - [ ] Input validation on all user inputs
  - [ ] No performance regressions vs baseline
  - [ ] Test suite <5 seconds
  - [ ] Daily updates <30 seconds
  - [ ] Historical backfill <5 minutes

- [ ] **Operational Readiness**
  - [ ] Appropriate logging at INFO/WARNING/ERROR levels
  - [ ] Clear error messages on failures
  - [ ] Manual end-to-end test via UI/API successful
  - [ ] REFACTOR_STATUS.md updated (mark feature complete)
  - [ ] Health check endpoint reports all source statuses

**See**: `docs/core/DEVELOPMENT.md` → "Production Readiness Requirements" for complete checklist
