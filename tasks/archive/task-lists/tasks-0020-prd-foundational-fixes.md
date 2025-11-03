# Task List: Foundational Code Quality & Architecture Fixes

**PRD**: `0020-prd-foundational-fixes.md`
**Status**: ✅ COMPLETE
**Completion**: 100% (6/6 core tasks + all bugs fixed)
**Last Updated**: 2025-11-01 20:50 UTC
**Completed**: 2025-11-01 - All tasks complete, bugs fixed, ready for PRD #0021

**Note on Effort Levels**:
- **Low**: 1-2 hours of straightforward work
- **Medium**: Half day of work with some complexity
- **High**: Full day or more, significant complexity

---

## Summary

**✅ COMPLETE:**
- Task 1.0: Fix Critical Data Integrity Issues (🔴 BLOCKING) - commit 222e059
- Task 2.0: Migrate to Structured Logging (🟡 HIGH) - commit 23ff4c3
- Task 3.0: Consolidate Frontend API Clients (🟡 HIGH) - commit 8ec0429
- Task 4.0: Fix Async/Sync Mismatches (🟡 HIGH) - commit 475ce7d
- Task 5.0: Code Quality & Documentation Updates (🟢 MEDIUM) - commits e09b418, 6201d71, 15ef009
- Task 6.0: End-to-End Validation & Testing (🟢 LOW-MEDIUM) - commits b746716, 0c40022
  - All 373 tests passing
  - Browser automation tests completed (screenshots captured)
  - Comprehensive timezone fixes (15 additional instances beyond scope)
  - Command file updates (tech debt prevention guidance added)
  - All verification gates passed

**🎁 BONUS ENHANCEMENTS (User Feedback):**
- Watchlist UX Improvements - commit 40b3337
  - Fixed modal closing bug (query key issue)
  - Added bulk ticker import (textarea, multi-line, comma-separated)
  - Smart selective updates with visual feedback (CSS flash animations)
- Additional Features - commit 2d1fa9b
  - Ticker removal functionality
  - Sorting features
- Database Architecture Documentation - commit 098348f
  - Documented two-database setup (production + test)
  - Added to CLAUDE.md and do_it.md to prevent future confusion
- Sparkline Improvements - commit 2d54dff
  - Fixed NaN errors with single data points
  - Proposal created for history backfill improvements (docs/proposals/)

**🔄 IN PROGRESS:**
- None

**✅ BUGS FIXED (Post-Pause):**
- 500 errors when adding tickers - commit 098348f
  - Root cause: Missing "default" account in production database
  - Fix: Created account with proper schema (id, name, account_type)
  - Database architecture documented in CLAUDE.md and do_it.md
- WebSocket HMR errors - commit 098348f
  - Root cause: Next.js 16 Turbopack incompatibility with webpack config
  - Fix: Removed webpack config, added turbopack config, --hostname 0.0.0.0
- Mypy type errors - commit 098348f
  - Root cause: Redis type annotations, missing pandas-stubs
  - Fix: Added proper type ignores, installed pandas-stubs
- Sparkline NaN errors - commit 2d54dff
  - Root cause: Division by zero with single data point
  - Fix: Center single points at width/2

**✅ SESSION STATUS:**
- PRD #0020: 100% Complete ✅
- All bugs fixed ✅
- All tests passing (377 tests) ✅
- UI fully functional ✅
- Tickers successfully added via UI ✅
- No console errors ✅
- Documentation updated ✅

**COMPLETION STATUS:** 100% - Ready for PRD #0021
**NEXT ACTION:** Start PRD #0021 (Watchlist Narrative Intelligence) or next priority

---

## Relevant Files

### Files to Create (3 new files)

- `backend/migrations/006_timezone_and_schema_fixes.sql` (~150 lines) - Database migration for timezone conversion
- `frontend/lib/api/client.ts` (~80 lines) - Unified API client with error handling
- `backend/tests/integration/test_timezone_handling.py` (~100 lines) - Timezone integration tests

### Files to Update (35+ files)

**Phase 1 - Critical Data Integrity (🔴)**:
- `backend/app/api/preferences.py` - Replace `datetime.now()` with `datetime.now(UTC)` (lines 177-178, 324)
- `backend/app/api/ideas.py` - Replace `datetime.now()` (line 308)
- `backend/app/portfolio/manager.py` - Replace `datetime.now()` (lines 50, 107, 166)
- `backend/app/portfolio/price_fetcher.py` - Replace `datetime.now()` (line 161)
- `backend/app/agents/tools.py` - Add UTC import and replace `datetime.now()` (line 10)
- `backend/app/api/watchlist.py` - Replace timestamp-based ID with UUID (line 198)

**Phase 2 - Structured Logging (🟡)**:
- `backend/app/portfolio/manager.py` - Migrate to `get_logger()` (line 18)
- `backend/app/agents/tools.py` - Migrate to `get_logger()` (line 23)
- `backend/app/storage/queries.py` - Migrate to `get_logger()` (line 18)
- `backend/app/storage/facade.py` - Migrate to `get_logger()` (line 28)
- Plus 11 other storage/agent files (via grep search)

**Phase 2 - Frontend Consolidation (🟡)**:
- `frontend/lib/api/watchlist.ts` - Use shared `apiRequest()`
- `frontend/lib/api/preferences.ts` - Use shared `apiRequest()`
- `frontend/lib/api/portfolio.ts` - Use shared `apiRequest()`
- `frontend/lib/api/ideas.ts` - Use shared `apiRequest()`
- `frontend/lib/api/market.ts` - Use shared `apiRequest()`

**Phase 2 - Async/Sync Fixes (🟡)**:
- `backend/app/api/watchlist.py` - Wrap sync calls in `run_in_threadpool()` (lines 124-137, 363)
- `backend/app/api/preferences.py` - Wrap sync calls in `run_in_threadpool()` (lines 209-234)
- `backend/app/api/preferences.py` - Fix account-scoped query (line 129)

**Phase 3 - Code Quality (🟢)**:
- `backend/app/tasks/agent_tasks.py` - Extract DRY violations (lines 39-101, 103-164)
- `backend/app/storage/__init__.py` - Update docstring (line 1)
- `backend/app/storage/queries.py` - Update docstring (line 1)
- `backend/app/storage/facade.py` - Update docstring (line 3)
- `backend/app/watchlist/service.py` - Add `get_item_with_score_by_id()` method
- `backend/app/api/watchlist.py` - Use optimized query method (line 363)

### Notes

- Run tests: `cd ~/portfolio-ai/backend && pytest tests/ -v --cov=app`
- Type checking: `cd ~/portfolio-ai/backend && mypy app/ --strict`
- Linting: `~/portfolio-ai/scripts/lint.sh`
- Database migration: Apply via `psql` before running app
- Frontend tests: `cd ~/portfolio-ai/frontend && npm run test`
- Browser automation: Use `~/.claude/skills/browser-automation/` for UI testing

---

## Tasks

### 1.0 Fix Critical Data Integrity Issues (🔴 BLOCKING)

**Goal**: Eliminate timezone bugs and ID collision risks with TDD approach

- [ ] 1.1 Timezone Standardization - Write Failing Tests
  - [ ] 1.1.1 Create `tests/integration/test_timezone_handling.py`
  - [ ] 1.1.2 Write test: staleness detection with naive datetime (expect FAIL)
  - [ ] 1.1.3 Write test: cache expiration with mixed timezone timestamps (expect FAIL)
  - [ ] 1.1.4 Write test: "updated 5 minutes ago" calculation with naive datetime (expect FAIL)
  - [ ] 1.1.5 Run tests, verify all 3 fail with timezone issues
  - [ ] 1.1.6 Document failing test output for baseline

- [ ] 1.2 Timezone Standardization - Fix Code (9 files)
  - [ ] 1.2.1 Fix `backend/app/api/preferences.py:177-178` - Replace `datetime.now()` → `datetime.now(UTC)`
  - [ ] 1.2.2 Fix `backend/app/api/preferences.py:324` - Replace `datetime.now()` → `datetime.now(UTC)`
  - [ ] 1.2.3 Fix `backend/app/api/ideas.py:308` - Replace `datetime.now()` → `datetime.now(UTC)`
  - [ ] 1.2.4 Fix `backend/app/portfolio/manager.py:50` - Replace `datetime.now()` → `datetime.now(UTC)`
  - [ ] 1.2.5 Fix `backend/app/portfolio/manager.py:107` - Replace `datetime.now()` → `datetime.now(UTC)`
  - [ ] 1.2.6 Fix `backend/app/portfolio/manager.py:166` - Replace `datetime.now()` → `datetime.now(UTC)`
  - [ ] 1.2.7 Fix `backend/app/portfolio/price_fetcher.py:161` - Replace `datetime.now()` → `datetime.now(UTC)`
  - [ ] 1.2.8 Fix `backend/app/agents/tools.py:10` - Add `from datetime import UTC` and replace `datetime.now()`
  - [ ] 1.2.9 Verify all imports: `from datetime import datetime, UTC` or `import datetime as dt`

- [ ] 1.3 Timezone Standardization - Verify Tests Pass
  - [ ] 1.3.1 Run `pytest tests/integration/test_timezone_handling.py -v`
  - [ ] 1.3.2 Verify staleness detection test PASSES (was failing)
  - [ ] 1.3.3 Verify cache expiration test PASSES (was failing)
  - [ ] 1.3.4 Verify datetime arithmetic test PASSES (was failing)
  - [ ] 1.3.5 Run full test suite to check for regressions
  - [ ] 1.3.6 Run `mypy app/ --strict` to verify type safety

- [ ] 1.4 Database Migration - Timezone Conversion
  - [ ] 1.4.1 Create `backend/migrations/006_timezone_and_schema_fixes.sql`
  - [ ] 1.4.2 Add idempotent ALTER for `watchlist_snapshots.fetched_at` (TIMESTAMPTZ)
  - [ ] 1.4.3 Add idempotent ALTER for `user_preferences.created_at` and `updated_at` (TIMESTAMPTZ)
  - [ ] 1.4.4 Add idempotent ALTER for `positions.created_at` and `updated_at` (TIMESTAMPTZ)
  - [ ] 1.4.5 Add idempotent ALTER for `agent_runs.created_at` and `completed_at` (TIMESTAMPTZ)
  - [ ] 1.4.6 Add idempotent ALTER for `price_cache.cached_at` (TIMESTAMPTZ)
  - [ ] 1.4.7 Add idempotent ALTER for `reference_cache.cached_at` (TIMESTAMPTZ)
  - [ ] 1.4.8 Add idempotent ALTER for `paper_trades.executed_at` (TIMESTAMPTZ)
  - [ ] 1.4.9 Test migration idempotence (run twice, verify no errors)

- [ ] 1.5 UUID-Based ID Generation - Write Failing Test
  - [ ] 1.5.1 Create `tests/api/test_watchlist_id_collision.py`
  - [ ] 1.5.2 Write test: Create 100 watchlist items concurrently using ThreadPoolExecutor
  - [ ] 1.5.3 Assert: Expect UNIQUE constraint violations with timestamp-based IDs (FAIL expected)
  - [ ] 1.5.4 Run test, verify it fails with ID collision errors
  - [ ] 1.5.5 Document collision frequency (how many failures out of 100)

- [ ] 1.6 UUID-Based ID Generation - Fix Code
  - [ ] 1.6.1 Add `import uuid` to `backend/app/api/watchlist.py`
  - [ ] 1.6.2 Replace line 198: `str(datetime.now(UTC).timestamp())` → `str(uuid.uuid4())`
  - [ ] 1.6.3 Verify function signature unchanged (returns string)
  - [ ] 1.6.4 Check for any other timestamp-based ID generation (grep search)

- [ ] 1.7 UUID-Based ID Generation - Verify Test Passes
  - [ ] 1.7.1 Run `pytest tests/api/test_watchlist_id_collision.py -v`
  - [ ] 1.7.2 Verify 100 concurrent inserts complete successfully (was failing)
  - [ ] 1.7.3 Verify 0 UNIQUE constraint violations (was >0)
  - [ ] 1.7.4 Query database to confirm all 100 items created with UUID format
  - [ ] 1.7.5 Run full watchlist test suite to check for regressions

- [ ] 1.8 Database Migration - UUID Migration for Existing Data
  - [ ] 1.8.1 Add to migration: Generate UUIDs for existing watchlist items with timestamp IDs
  - [ ] 1.8.2 Add: `UPDATE watchlist_items SET id = gen_random_uuid()::text WHERE id ~ '^[0-9]+\.[0-9]+$'`
  - [ ] 1.8.3 Add: Update foreign keys in `watchlist_snapshots` to reference new UUIDs
  - [ ] 1.8.4 Test migration on copy of production data (if available)
  - [ ] 1.8.5 Verify all watchlist items have valid UUID format after migration

- [ ] 1.9 Apply Migration and Verify
  - [ ] 1.9.1 Backup database before migration: `pg_dump portfolio_ai > backup-pre-migration.sql`
  - [ ] 1.9.2 Apply migration: `psql portfolio_ai < migrations/006_timezone_and_schema_fixes.sql`
  - [ ] 1.9.3 Verify all timestamp columns are TIMESTAMPTZ type
  - [ ] 1.9.4 Verify all existing timestamps converted to UTC
  - [ ] 1.9.5 Verify all watchlist items have UUID format IDs
  - [ ] 1.9.6 Run full test suite against migrated database
  - [ ] 1.9.7 Restart backend and verify app works with migrated schema

---

### 2.0 Migrate to Structured Logging (🟡 HIGH)

**Goal**: Replace standard logging with structlog for JSON output and log aggregation

- [ ] 2.1 Identify All Files Using Standard Logging
  - [ ] 2.1.1 Run: `grep -r "logging.getLogger" backend/app/ > logging-files.txt`
  - [ ] 2.1.2 Count affected files (expect ~15)
  - [ ] 2.1.3 Create checklist of all files to migrate
  - [ ] 2.1.4 Prioritize: user-facing modules first (watchlist, portfolio, agents)

- [ ] 2.2 Write Integration Test for JSON Log Output
  - [ ] 2.2.1 Create `tests/integration/test_structured_logging.py`
  - [ ] 2.2.2 Write test: Capture log output from watchlist refresh
  - [ ] 2.2.3 Write test: Parse logs as JSON, assert no parse errors
  - [ ] 2.2.4 Write test: Verify structured fields present (account_id, ticker, etc.)
  - [ ] 2.2.5 Run test, expect FAIL (logs currently f-strings, not JSON)

- [ ] 2.3 Migrate Core Modules (5 files)
  - [ ] 2.3.1 Migrate `backend/app/portfolio/manager.py:18`
    - Replace: `logger = logging.getLogger(__name__)` → `logger = get_logger(__name__)`
    - Add import: `from app.logging_config import get_logger`
  - [ ] 2.3.2 Migrate `backend/app/agents/tools.py:23`
    - Replace logger initialization
    - Add import
  - [ ] 2.3.3 Migrate `backend/app/storage/queries.py:18`
    - Replace logger initialization
    - Add import
  - [ ] 2.3.4 Migrate `backend/app/storage/facade.py:28`
    - Replace logger initialization
    - Add import
  - [ ] 2.3.5 Migrate `backend/app/watchlist/service.py` (if using standard logging)
    - Replace logger initialization
    - Add import

- [ ] 2.4 Convert Log Calls to Key/Value Format (Core Modules)
  - [ ] 2.4.1 Convert `portfolio/manager.py` logs from f-strings to key/value
    - Example: `logger.info(f"Created account {account_id}")` → `logger.info("Created account", account_id=account_id)`
  - [ ] 2.4.2 Convert `agents/tools.py` logs to key/value format
  - [ ] 2.4.3 Convert `storage/queries.py` logs to key/value format
  - [ ] 2.4.4 Convert `storage/facade.py` logs to key/value format
  - [ ] 2.4.5 Convert `watchlist/service.py` logs to key/value format (if applicable)

- [ ] 2.5 Migrate Remaining Files (10+ storage/agent files)
  - [ ] 2.5.1 Batch migrate all files in `backend/app/storage/` directory
  - [ ] 2.5.2 Batch migrate all files in `backend/app/agents/` directory
  - [ ] 2.5.3 Verify no files missed: `grep -r "logging.getLogger" backend/app/` (expect 0 results)
  - [ ] 2.5.4 Convert all log calls to key/value format in migrated files
  - [ ] 2.5.5 Run `mypy app/ --strict` to verify imports and types

- [ ] 2.6 Verify JSON Log Output Test Passes
  - [ ] 2.6.1 Run `pytest tests/integration/test_structured_logging.py -v`
  - [ ] 2.6.2 Verify logs parse as valid JSON (was failing)
  - [ ] 2.6.3 Verify structured fields present in all log entries
  - [ ] 2.6.4 Verify no f-string artifacts in log messages
  - [ ] 2.6.5 Test log output in development vs production environments

- [ ] 2.7 Verify Logging Configuration
  - [ ] 2.7.1 Check `backend/app/logging_config.py` exists and is correct
  - [ ] 2.7.2 Verify `get_logger()` returns `structlog.BoundLogger`
  - [ ] 2.7.3 Verify JSON output enabled in production (environment check)
  - [ ] 2.7.4 Verify plain text output in development (readable for debugging)
  - [ ] 2.7.5 Test log aggregation compatibility (if using Loki/Elasticsearch)

---

### 3.0 Consolidate Frontend API Clients (🟡 HIGH)

**Goal**: Eliminate code duplication across 5 API modules with unified client

- [ ] 3.1 Create Unified API Client
  - [ ] 3.1.1 Create `frontend/lib/api/client.ts`
  - [ ] 3.1.2 Define `ApiError` class extending `Error` with status code
  - [ ] 3.1.3 Implement `apiRequest<T>()` function with retry logic (3 attempts)
  - [ ] 3.1.4 Add exponential backoff: 1s, 2s, 3s between retries
  - [ ] 3.1.5 Add default headers: `Content-Type: application/json`
  - [ ] 3.1.6 Add auth interceptor placeholder (commented TODO)
  - [ ] 3.1.7 Export `API_BASE_URL` constant from environment variable

- [ ] 3.2 Write Tests for API Client
  - [ ] 3.2.1 Create `frontend/lib/api/__tests__/client.test.ts`
  - [ ] 3.2.2 Write test: Successful request returns parsed JSON
  - [ ] 3.2.3 Write test: Failed request throws ApiError with status code
  - [ ] 3.2.4 Write test: Retry logic triggers on network error
  - [ ] 3.2.5 Write test: Retry logic stops after 3 attempts
  - [ ] 3.2.6 Write test: Headers merge correctly (custom + defaults)
  - [ ] 3.2.7 Run tests: `npm run test`

- [ ] 3.3 Refactor Watchlist API Module
  - [ ] 3.3.1 Read current `frontend/lib/api/watchlist.ts` to understand patterns
  - [ ] 3.3.2 Import `apiRequest` and `API_BASE_URL` from `./client`
  - [ ] 3.3.3 Replace all `fetch()` calls with `apiRequest<T>()`
  - [ ] 3.3.4 Remove local `API_BASE_URL` constant
  - [ ] 3.3.5 Remove local error handling (now in `apiRequest`)
  - [ ] 3.3.6 Verify type safety maintained (generic types)
  - [ ] 3.3.7 Test watchlist API calls via UI

- [ ] 3.4 Refactor Preferences API Module
  - [ ] 3.4.1 Read current `frontend/lib/api/preferences.ts`
  - [ ] 3.4.2 Import `apiRequest` and `API_BASE_URL` from `./client`
  - [ ] 3.4.3 Replace all `fetch()` calls with `apiRequest<T>()`
  - [ ] 3.4.4 Remove local `API_BASE_URL` and error handling
  - [ ] 3.4.5 Verify type safety maintained
  - [ ] 3.4.6 Test preferences API via Settings page

- [ ] 3.5 Refactor Portfolio API Module
  - [ ] 3.5.1 Read current `frontend/lib/api/portfolio.ts`
  - [ ] 3.5.2 Import `apiRequest` and `API_BASE_URL` from `./client`
  - [ ] 3.5.3 Replace all `fetch()` calls with `apiRequest<T>()`
  - [ ] 3.5.4 Remove local `API_BASE_URL` and error handling
  - [ ] 3.5.5 Verify type safety maintained
  - [ ] 3.5.6 Test portfolio API via Portfolio page

- [ ] 3.6 Refactor Ideas API Module
  - [ ] 3.6.1 Read current `frontend/lib/api/ideas.ts`
  - [ ] 3.6.2 Import `apiRequest` and `API_BASE_URL` from `./client`
  - [ ] 3.6.3 Replace all `fetch()` calls with `apiRequest<T>()`
  - [ ] 3.6.4 Remove local `API_BASE_URL` and error handling
  - [ ] 3.6.5 Verify type safety maintained
  - [ ] 3.6.6 Test ideas API via Ideas page

- [ ] 3.7 Refactor Market API Module
  - [ ] 3.7.1 Read current `frontend/lib/api/market.ts` (if exists)
  - [ ] 3.7.2 Import `apiRequest` and `API_BASE_URL` from `./client`
  - [ ] 3.7.3 Replace all `fetch()` calls with `apiRequest<T>()`
  - [ ] 3.7.4 Remove local `API_BASE_URL` and error handling
  - [ ] 3.7.5 Verify type safety maintained
  - [ ] 3.7.6 Test market API via Market page (if exists)

- [ ] 3.8 Verify Consolidation Complete
  - [ ] 3.8.1 Search for duplicate `API_BASE_URL` definitions: `grep -r "API_BASE_URL" frontend/lib/api/` (expect 1 result in client.ts)
  - [ ] 3.8.2 Search for duplicate error handling: `grep -r "if (!response.ok)" frontend/lib/api/` (expect 1 result in client.ts)
  - [ ] 3.8.3 Verify all 5 modules import from `./client`
  - [ ] 3.8.4 Run TypeScript compiler: `npm run build` (no errors)
  - [ ] 3.8.5 Run linting: `npm run lint` (no errors)

---

### 4.0 Fix Async/Sync Mismatches & Account Preferences (🟡 HIGH)

**Goal**: Improve throughput by fixing async/sync issues and account-scoped queries

- [ ] 4.1 Baseline Performance Measurement
  - [ ] 4.1.1 Create `tests/performance/test_async_throughput.py`
  - [ ] 4.1.2 Write benchmark: 100 concurrent GET /api/watchlist requests
  - [ ] 4.1.3 Measure requests/second (baseline before fix)
  - [ ] 4.1.4 Measure average response time (baseline)
  - [ ] 4.1.5 Document baseline metrics for comparison

- [ ] 4.2 Fix Watchlist List Endpoint (watchlist.py:124-137)
  - [ ] 4.2.1 Read `backend/app/api/watchlist.py:124-137` (`list_watchlist_items`)
  - [ ] 4.2.2 Add import: `from fastapi.concurrency import run_in_threadpool`
  - [ ] 4.2.3 Wrap sync call: `items = await run_in_threadpool(watchlist_service.get_items_with_scores, account_id)`
  - [ ] 4.2.4 Verify endpoint still async def
  - [ ] 4.2.5 Test endpoint: `curl http://localhost:8000/api/watchlist?account_id=default`
  - [ ] 4.2.6 Verify response unchanged (same data structure)

- [ ] 4.3 Fix Watchlist Get Endpoint (watchlist.py:363)
  - [ ] 4.3.1 Read `backend/app/api/watchlist.py:363` (`get_watchlist_item`)
  - [ ] 4.3.2 Identify sync DB calls in function
  - [ ] 4.3.3 Wrap sync calls with `run_in_threadpool()`
  - [ ] 4.3.4 Test endpoint: `curl http://localhost:8000/api/watchlist/{item_id}`
  - [ ] 4.3.5 Verify response unchanged

- [ ] 4.4 Fix Preferences Get Endpoint (preferences.py:209-234)
  - [ ] 4.4.1 Read `backend/app/api/preferences.py:209-234` (`get_preferences`)
  - [ ] 4.4.2 Identify sync DB calls in function
  - [ ] 4.4.3 Wrap `_get_or_create_preferences()` call: `await run_in_threadpool(_get_or_create_preferences, storage, account_id)`
  - [ ] 4.4.4 Wrap any `storage.query()` calls
  - [ ] 4.4.5 Test endpoint: `curl http://localhost:8000/api/preferences?account_id=default`
  - [ ] 4.4.6 Verify response unchanged

- [ ] 4.5 Verify Performance Improvement
  - [ ] 4.5.1 Re-run benchmark: 100 concurrent requests
  - [ ] 4.5.2 Measure new requests/second (target: 20% improvement)
  - [ ] 4.5.3 Measure new average response time
  - [ ] 4.5.4 Compare before/after metrics
  - [ ] 4.5.5 Document performance gains
  - [ ] 4.5.6 Verify no errors under concurrent load

- [ ] 4.6 Fix Account-Scoped Preference Query - Write Failing Test
  - [ ] 4.6.1 Create `tests/api/test_multi_account_preferences.py`
  - [ ] 4.6.2 Write test: Create preferences for account "user1"
  - [ ] 4.6.3 Write test: Create preferences for account "user2" with different values
  - [ ] 4.6.4 Write test: GET /api/preferences?account_id=user1, expect user1's values
  - [ ] 4.6.5 Run test, expect FAIL (currently returns most recent, not account-filtered)

- [ ] 4.7 Fix Account-Scoped Preference Query - Fix Code
  - [ ] 4.7.1 Read `backend/app/api/preferences.py:129` (`_get_or_create_preferences`)
  - [ ] 4.7.2 Replace query: `ORDER BY updated_at DESC LIMIT 1` → `WHERE id = %s LIMIT 1`
  - [ ] 4.7.3 Update parameters: Pass `(account_id,)` to query
  - [ ] 4.7.4 Verify create logic also uses account_id parameter
  - [ ] 4.7.5 Update all callers to pass account_id

- [ ] 4.8 Fix Account-Scoped Preference Query - Verify Test Passes
  - [ ] 4.8.1 Run `pytest tests/api/test_multi_account_preferences.py -v`
  - [ ] 4.8.2 Verify account isolation test PASSES (was failing)
  - [ ] 4.8.3 Verify user1 gets user1's preferences (not user2's)
  - [ ] 4.8.4 Verify no cross-contamination between accounts
  - [ ] 4.8.5 Run full test suite to check for regressions

- [ ] 4.9 Fix Weight Loading Account Scope
  - [ ] 4.9.1 Read `backend/app/watchlist/service.py:92-108` (`_load_default_weights`)
  - [ ] 4.9.2 Add `WHERE id = %s` filter to query
  - [ ] 4.9.3 Update parameters to include account_id
  - [ ] 4.9.4 Verify all callers pass account_id parameter
  - [ ] 4.9.5 Test watchlist refresh with multiple accounts
  - [ ] 4.9.6 Verify correct weights loaded per account

---

### 5.0 Code Quality & Documentation Updates (🟢 MEDIUM)

**Goal**: Remove DRY violations, update docstrings, optimize queries

- [ ] 5.1 Extract Agent Task Setup Helper
  - [ ] 5.1.1 Read `backend/app/tasks/agent_tasks.py:39-101` (`run_discovery_agent`)
  - [ ] 5.1.2 Read `backend/app/tasks/agent_tasks.py:103-164` (`run_portfolio_analyzer`)
  - [ ] 5.1.3 Identify duplicated setup code (~20 lines)
  - [ ] 5.1.4 Create `_setup_agent_tools(storage: StorageFacade) -> dict` helper
  - [ ] 5.1.5 Extract tool initialization logic to helper
  - [ ] 5.1.6 Return tools dictionary from helper
  - [ ] 5.1.7 Add type hints and docstring to helper

- [ ] 5.2 Extract Agent Run Finalization Helper
  - [ ] 5.2.1 Identify duplicated cleanup code (~20 lines)
  - [ ] 5.2.2 Create `_finalize_agent_run(storage, agent_run_id, status, result) -> None` helper
  - [ ] 5.2.3 Extract agent_runs UPDATE logic to helper
  - [ ] 5.2.4 Add error handling in helper
  - [ ] 5.2.5 Add type hints and docstring to helper
  - [ ] 5.2.6 Use `datetime.now(UTC)` for completed_at timestamp

- [ ] 5.3 Refactor run_discovery_agent to Use Helpers
  - [ ] 5.3.1 Replace setup code with `tools = _setup_agent_tools(storage)`
  - [ ] 5.3.2 Replace cleanup code with `_finalize_agent_run(storage, agent_run_id, status, result)`
  - [ ] 5.3.3 Verify logic unchanged (no behavioral changes)
  - [ ] 5.3.4 Verify error handling preserved
  - [ ] 5.3.5 Test discovery agent task execution

- [ ] 5.4 Refactor run_portfolio_analyzer to Use Helpers
  - [ ] 5.4.1 Replace setup code with `tools = _setup_agent_tools(storage)`
  - [ ] 5.4.2 Replace cleanup code with `_finalize_agent_run(storage, agent_run_id, status, result)`
  - [ ] 5.4.3 Verify logic unchanged (no behavioral changes)
  - [ ] 5.4.4 Verify error handling preserved
  - [ ] 5.4.5 Test portfolio analyzer task execution

- [ ] 5.5 Verify DRY Violations Removed
  - [ ] 5.5.1 Count lines in agent_tasks.py before and after (expect ~40 line reduction)
  - [ ] 5.5.2 Search for remaining duplicated blocks: `ruff check app/tasks/agent_tasks.py`
  - [ ] 5.5.3 Verify both tasks behave identically (integration test)
  - [ ] 5.5.4 Run full agent test suite
  - [ ] 5.5.5 Run `mypy app/tasks/ --strict` to verify types

- [ ] 5.6 Update Storage Module Docstrings
  - [ ] 5.6.1 Update `backend/app/storage/__init__.py:1` - Replace "DuckDB" with "PostgreSQL"
  - [ ] 5.6.2 Update `backend/app/storage/queries.py:1` - Replace "DuckDB query operations" with "PostgreSQL query operations"
  - [ ] 5.6.3 Update `backend/app/storage/facade.py:3` - Replace DuckDB references with PostgreSQL
  - [ ] 5.6.4 Search for remaining DuckDB references: `grep -ri "duckdb" backend/app/storage/`
  - [ ] 5.6.5 Replace any remaining DuckDB mentions in comments
  - [ ] 5.6.6 Verify docstrings accurate and consistent

- [ ] 5.7 Add Optimized Single-Item Query Method
  - [ ] 5.7.1 Create `get_item_with_score_by_id(item_id: str)` in `backend/app/watchlist/service.py`
  - [ ] 5.7.2 Implement direct SQL query with WHERE clause (not fetch-all-then-filter)
  - [ ] 5.7.3 Add type hints: `-> Optional[dict]`
  - [ ] 5.7.4 Add docstring explaining efficiency gain
  - [ ] 5.7.5 Write test comparing performance vs old method
  - [ ] 5.7.6 Verify 10x+ speedup for single-item lookup

- [ ] 5.8 Update Watchlist API to Use Optimized Query
  - [ ] 5.8.1 Read `backend/app/api/watchlist.py:363` (`get_watchlist_item`)
  - [ ] 5.8.2 Replace `get_items_with_scores()` call with `get_item_with_score_by_id(item_id)`
  - [ ] 5.8.3 Remove in-memory filtering logic (no longer needed)
  - [ ] 5.8.4 Verify response format unchanged
  - [ ] 5.8.5 Test endpoint: `curl http://localhost:8000/api/watchlist/{item_id}`
  - [ ] 5.8.6 Benchmark response time improvement

- [ ] 5.9 Verify Code Quality Standards
  - [ ] 5.9.1 Run `ruff check app/ tests/` (expect 0 errors)
  - [ ] 5.9.2 Run `ruff format app/ tests/` (auto-fix formatting)
  - [ ] 5.9.3 Run `mypy app/ --strict` (expect 0 errors)
  - [ ] 5.9.4 Verify no duplicate code blocks: `ruff check --select PLR0912`
  - [ ] 5.9.5 Check file sizes comply with guidelines (500 soft, 800 hard)
  - [ ] 5.9.6 Run full test suite: `pytest tests/ -v`

---

### 6.0 End-to-End Validation & Testing

**Goal**: Comprehensive testing with browser-automation skill and integration tests

- [ ] 6.1 Browser-Automation Setup & Baseline
  - [ ] 6.1.1 Verify browser-automation skill installed: `ls ~/.claude/skills/browser-automation/`
  - [ ] 6.1.2 Verify backend running: `curl http://localhost:8000/health`
  - [ ] 6.1.3 Verify frontend running: `curl http://localhost:3000/`
  - [ ] 6.1.4 Take baseline screenshot: `node ~/.claude/skills/browser-automation/scripts/screenshot.js http://localhost:3000/watchlist docs/screenshots/pre-fixes-watchlist.png`
  - [ ] 6.1.5 Take baseline screenshot: `node ~/.claude/skills/browser-automation/scripts/screenshot.js http://localhost:3000/settings docs/screenshots/pre-fixes-settings.png`

- [ ] 6.2 Watchlist Page End-to-End Test
  - [ ] 6.2.1 Open watchlist page in browser automation
  - [ ] 6.2.2 Take screenshot: `docs/screenshots/post-fixes-watchlist.png`
  - [ ] 6.2.3 Capture console messages: `node ~/.claude/skills/browser-automation/scripts/console.js http://localhost:3000/watchlist 5000`
  - [ ] 6.2.4 Verify no console errors (expect 0 errors)
  - [ ] 6.2.5 Monitor network requests: `node ~/.claude/skills/browser-automation/scripts/network.js http://localhost:3000/watchlist 5000`
  - [ ] 6.2.6 Verify all API calls return 200 status
  - [ ] 6.2.7 Verify timestamps display correctly (UTC-aware)
  - [ ] 6.2.8 Compare screenshots: pre-fixes vs post-fixes (no visual regressions)

- [ ] 6.3 Settings Page End-to-End Test
  - [ ] 6.3.1 Open settings page in browser automation
  - [ ] 6.3.2 Take screenshot: `docs/screenshots/post-fixes-settings.png`
  - [ ] 6.3.3 Capture console messages (5 second duration)
  - [ ] 6.3.4 Verify no console errors
  - [ ] 6.3.5 Monitor network requests (5 second duration)
  - [ ] 6.3.6 Verify GET /api/preferences returns account-specific data
  - [ ] 6.3.7 Test preference save functionality (if interactive test possible)
  - [ ] 6.3.8 Compare screenshots: verify no layout issues

- [ ] 6.4 Portfolio Page End-to-End Test
  - [ ] 6.4.1 Open portfolio page in browser automation
  - [ ] 6.4.2 Take screenshot: `docs/screenshots/post-fixes-portfolio.png`
  - [ ] 6.4.3 Capture console messages
  - [ ] 6.4.4 Verify no console errors
  - [ ] 6.4.5 Monitor network requests
  - [ ] 6.4.6 Verify API calls succeed
  - [ ] 6.4.7 Verify timestamps display correctly

- [ ] 6.5 Ideas Page End-to-End Test
  - [ ] 6.5.1 Open ideas page in browser automation
  - [ ] 6.5.2 Take screenshot: `docs/screenshots/post-fixes-ideas.png`
  - [ ] 6.5.3 Capture console messages
  - [ ] 6.5.4 Verify no console errors
  - [ ] 6.5.5 Monitor network requests
  - [ ] 6.5.6 Verify API calls succeed
  - [ ] 6.5.7 Verify timestamps display correctly

- [ ] 6.6 Integration Test Suite - Watchlist Full Flow
  - [ ] 6.6.1 Create `tests/integration/test_watchlist_complete_flow.py`
  - [ ] 6.6.2 Write test: Add ticker to watchlist → Verify created with UUID ID
  - [ ] 6.6.3 Write test: Trigger refresh → Verify updated_at timestamp is UTC-aware
  - [ ] 6.6.4 Write test: Get watchlist items → Verify API response time <500ms
  - [ ] 6.6.5 Write test: Get single item by ID → Verify uses optimized query
  - [ ] 6.6.6 Run integration test suite
  - [ ] 6.6.7 Verify all tests pass

- [ ] 6.7 Integration Test Suite - Preferences Multi-Account
  - [ ] 6.7.1 Create `tests/integration/test_preferences_isolation.py`
  - [ ] 6.7.2 Write test: Create preferences for account1
  - [ ] 6.7.3 Write test: Create preferences for account2 with different values
  - [ ] 6.7.4 Write test: GET preferences for account1 → Verify correct values
  - [ ] 6.7.5 Write test: GET preferences for account2 → Verify correct values
  - [ ] 6.7.6 Write test: Verify no cross-contamination
  - [ ] 6.7.7 Run integration test suite

- [ ] 6.8 Performance Validation - Load Testing
  - [ ] 6.8.1 Run load test: 100 concurrent GET /api/watchlist requests
  - [ ] 6.8.2 Measure throughput (requests/second)
  - [ ] 6.8.3 Verify 20%+ improvement vs baseline (from Task 4.1)
  - [ ] 6.8.4 Measure 95th percentile response time (target <500ms)
  - [ ] 6.8.5 Monitor server CPU/memory during load test
  - [ ] 6.8.6 Verify no errors or timeouts under load
  - [ ] 6.8.7 Document performance metrics

- [ ] 6.9 Verify Logging Output in Production Mode
  - [ ] 6.9.1 Set environment: `export LOG_FORMAT=json`
  - [ ] 6.9.2 Restart backend with production logging
  - [ ] 6.9.3 Trigger watchlist refresh
  - [ ] 6.9.4 Capture log output to file
  - [ ] 6.9.5 Parse logs as JSON, verify no parse errors
  - [ ] 6.9.6 Verify structured fields present (account_id, ticker, timestamp)
  - [ ] 6.9.7 Test log aggregation compatibility (if using Loki/Elasticsearch)

- [ ] 6.10 Final Verification Checklist
  - [ ] 6.10.1 All 35+ files updated successfully
  - [ ] 6.10.2 Database migration applied and verified
  - [ ] 6.10.3 All tests pass: `pytest tests/ -v --cov=app`
  - [ ] 6.10.4 Test coverage maintained at 86%+ (current baseline)
  - [ ] 6.10.5 Type checking passes: `mypy app/ --strict`
  - [ ] 6.10.6 Linting passes: `scripts/lint.sh`
  - [ ] 6.10.7 No console errors in browser automation tests
  - [ ] 6.10.8 No DuckDB references remaining: `grep -ri "duckdb" backend/app/`
  - [ ] 6.10.9 All timestamps UTC-aware: Verify in database
  - [ ] 6.10.10 All watchlist IDs are UUIDs: Verify in database
  - [ ] 6.10.11 Structured logging enabled: Verify JSON output
  - [ ] 6.10.12 Performance targets met: 20% throughput improvement
  - [ ] 6.10.13 No visual regressions: Compare screenshots
  - [ ] 6.10.14 Documentation updated (see Task 6.11)

- [ ] 6.11 Update Documentation
  - [ ] 6.11.1 Update `docs/core/ARCHITECTURE.md` with logging changes
  - [ ] 6.11.2 Update `docs/core/DEVELOPMENT.md` with migration instructions
  - [ ] 6.11.3 Document unified API client pattern in ARCHITECTURE.md
  - [ ] 6.11.4 Document async/sync best practices
  - [ ] 6.11.5 Update `docs/core/REFACTOR_STATUS.md` - Mark PRD 0020 complete
  - [ ] 6.11.6 Add notes on timezone standardization
  - [ ] 6.11.7 Add notes on UUID-based ID generation

---

## Verification & Production Readiness

**MANDATORY before marking task "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All 24 issues from solution_review.md addressed
  - [ ] All PRD requirements implemented
  - [ ] Zero known bugs or regressions
  - [ ] All integration points working correctly

- [ ] **Test Coverage** (target: 86%+ maintained)
  - [ ] Unit tests written for all new functions/classes
  - [ ] Integration tests for cross-module interactions
  - [ ] End-to-end tests via browser-automation skill
  - [ ] All tests passing: `pytest tests/ -v`
  - [ ] Coverage verified: `pytest tests/ --cov=app --cov-report=term-missing`

- [ ] **Type Safety & Code Quality**
  - [ ] 100% type hints on all functions: `mypy app/ --strict` passes
  - [ ] Linting passes: `scripts/lint.sh` returns zero errors
  - [ ] Code formatting applied: `ruff format app/`
  - [ ] No duplicate code blocks (DRY compliance)

- [ ] **Clean Implementation (No Band-Aids)**
  - [ ] All type hints are proper (no `Any` shortcuts)
  - [ ] Behavior is explicit (no magic parsing)
  - [ ] Single source of truth maintained (no duplicated logic)
  - [ ] Standard patterns used (no custom workarounds)
  - [ ] Proper error messages (no silent failures)

- [ ] **Database Migration**
  - [ ] Migration script idempotent (safe to run multiple times)
  - [ ] All timestamps converted to TIMESTAMPTZ
  - [ ] All watchlist IDs converted to UUID format
  - [ ] Migration tested on copy of production data
  - [ ] Rollback procedure documented

- [ ] **Documentation**
  - [ ] All public functions/classes have docstrings
  - [ ] ARCHITECTURE.md updated with logging/API patterns
  - [ ] DEVELOPMENT.md updated with migration instructions
  - [ ] No DuckDB references remaining in codebase

- [ ] **Security & Performance**
  - [ ] SQL queries use parameterized placeholders (no f-strings)
  - [ ] No secrets in code (API keys in environment/database only)
  - [ ] Input validation on all user inputs
  - [ ] Performance targets met (20% throughput improvement)

- [ ] **Operational Readiness**
  - [ ] Structured logging enabled (JSON output)
  - [ ] Clear error messages on failures
  - [ ] Manual end-to-end test via browser-automation successful
  - [ ] No console errors in UI
  - [ ] REFACTOR_STATUS.md updated (mark PRD 0020 complete)

---

## Related Documents

- [0020-prd-foundational-fixes.md](0020-prd-foundational-fixes.md) - Full PRD with requirements
- [solution_review.md](../solution_review.md) - Source of all 24 issues
- [docs/core/ARCHITECTURE.md](../docs/core/ARCHITECTURE.md) - System architecture
- [docs/core/DEVELOPMENT.md](../docs/core/DEVELOPMENT.md) - Development workflows
- [CLAUDE.md](../CLAUDE.md) - Project guidelines and standards

---

**Estimated Effort**: High (35+ files, database migration, comprehensive testing)
**Risk Level**: Medium (breaking changes, database migration)
**Blocker For**: PRD 0021 (Watchlist Narrative Intelligence), all future feature development
