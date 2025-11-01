# PRD: Foundational Code Quality & Architecture Fixes

**PRD ID**: 0020
**Status**: Approved
**Priority**: Critical (Blocking for feature development)
**Created**: 2025-11-01
**Target Completion**: Before PRD 0021 (Narrative Intelligence)

---

## Introduction

The solution_review.md identified 24 critical issues across the codebase that must be addressed before adding new features. These issues fall into three categories:

1. **Data Integrity Issues** (🔴 Critical): Timezone bugs, collision-prone IDs
2. **Architecture Issues** (🟡 High): Async/sync mismatches, DRY violations, logging standard violations
3. **Documentation Issues** (🟢 Medium): Outdated docstrings, legacy terminology

**Problem**: These foundational issues create technical debt that compounds with each new feature:
- Timezone bugs cause incorrect staleness calculations and cache misses
- Non-structured logs make production debugging difficult
- Duplicated code leads to inconsistent behavior
- Async/sync mismatches reduce throughput under load

**Goal**: Complete foundational cleanup to establish clean, maintainable codebase for future development.

---

## Goals

1. **Data Integrity**: Eliminate timezone bugs and ID collision risks (0% tolerance)
2. **Production Readiness**: Migrate to structured logging (15 files) for JSON log aggregation
3. **Maintainability**: Remove code duplication (DRY violations) and consolidate API clients
4. **Performance**: Fix async/sync mismatches to improve throughput
5. **Documentation Accuracy**: Update all outdated docstrings to reflect PostgreSQL reality
6. **Test Coverage**: TDD approach with failing tests first, then fixes
7. **Zero Regressions**: End-to-end UI testing with browser-automation skill

---

## User Stories

### US-1: Developer Debugging Production Issues
**As a** developer debugging production issues
**I want** structured JSON logs with key/value pairs
**So that** I can query logs in aggregation tools and trace errors quickly

**Acceptance Criteria**:
- All 15 backend files use `get_logger(__name__)` instead of `logging.getLogger()`
- Logs output JSON format with structured fields
- Log aggregation tools (e.g., Loki, Elasticsearch) can parse logs

### US-2: Operator Monitoring System Health
**As an** operator monitoring system health
**I want** timezone-aware timestamps across all database records
**So that** staleness detection and cache expiration work correctly across timezones

**Acceptance Criteria**:
- All `datetime.now()` calls replaced with `datetime.now(UTC)`
- Database migration converts existing naive timestamps to UTC
- Staleness calculation tests pass with UTC timestamps

### US-3: Frontend Developer Making API Calls
**As a** frontend developer adding API features
**I want** unified API client with error handling and auth interceptors
**So that** I don't duplicate fetch logic across 5+ files

**Acceptance Criteria**:
- Single `lib/api/client.ts` with `apiRequest()` function
- All 5 API modules (watchlist, portfolio, preferences, ideas, market) use shared client
- Error handling and retry logic centralized

### US-4: Database Administrator Preventing Data Corruption
**As a** database administrator preventing data corruption
**I want** UUID-based IDs instead of timestamp-based IDs
**So that** parallel requests don't cause UNIQUE constraint violations

**Acceptance Criteria**:
- Watchlist ID generation uses `uuid.uuid4()` instead of `timestamp()`
- No ID collisions under parallel load (tested with 100 concurrent requests)

### US-5: New Contributor Understanding Codebase
**As a** new contributor reading the codebase
**I want** accurate docstrings that reflect PostgreSQL architecture
**So that** I'm not confused by outdated DuckDB references

**Acceptance Criteria**:
- All storage module docstrings updated to "PostgreSQL storage layer"
- No references to DuckDB in module/class/function docstrings

---

## Functional Requirements

### FR-1: Timezone Standardization (🔴 Critical)

**FR-1.1**: Replace all `datetime.now()` with `datetime.now(UTC)` in 9 files:
- `backend/app/api/preferences.py` (lines 177-178, 324)
- `backend/app/api/ideas.py` (line 308)
- `backend/app/portfolio/manager.py` (lines 50, 107, 166)
- `backend/app/portfolio/price_fetcher.py` (line 161)
- `backend/app/agents/tools.py` (line 10)

**FR-1.2**: Create database migration to convert naive timestamps to UTC:
- Identify all timestamp columns in all tables
- Convert naive timestamps to UTC (assume server timezone if ambiguous)
- Add `TIMEZONE 'UTC'` to all timestamp columns in schema
- Migration must be idempotent (safe to run multiple times)

**FR-1.3**: Add integration tests for timezone handling:
- Test staleness detection with UTC timestamps
- Test cache expiration across timezones
- Test datetime arithmetic (e.g., "updated 5 minutes ago")

### FR-2: Structured Logging Migration (🟡 High)

**FR-2.1**: Replace `logging.getLogger(__name__)` with `get_logger(__name__)` in 15 files:
- `backend/app/portfolio/manager.py` (line 18)
- `backend/app/agents/tools.py` (line 23)
- `backend/app/storage/queries.py` (line 18)
- `backend/app/storage/facade.py` (line 28)
- Plus 11 other storage/agent files (use `grep -r "logging.getLogger" backend/app/`)

**FR-2.2**: Update all log calls from f-strings to key/value format:
```python
# BEFORE
logger.info(f"Refreshing watchlist for account {account_id}")

# AFTER
logger.info("Refreshing watchlist", account_id=account_id)
```

**FR-2.3**: Add integration test to verify JSON log output:
- Capture log output from test run
- Parse as JSON and verify structured fields present
- Verify all required context (account_id, ticker, etc.) included

### FR-3: Frontend API Client Consolidation (🟡 High)

**FR-3.1**: Create `frontend/lib/api/client.ts` with unified client:
```typescript
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public response?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  url: string,
  options?: RequestInit & { retries?: number }
): Promise<T> {
  const { retries = 3, ...fetchOptions } = options || {};

  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await fetch(`${API_BASE_URL}${url}`, {
        ...fetchOptions,
        headers: {
          "Content-Type": "application/json",
          ...fetchOptions?.headers,
        },
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new ApiError(
          `Request failed: ${response.statusText}`,
          response.status,
          error
        );
      }

      return response.json();
    } catch (error) {
      if (attempt === retries - 1) throw error;
      await new Promise((resolve) => setTimeout(resolve, 1000 * (attempt + 1)));
    }
  }

  throw new Error("Unreachable");
}
```

**FR-3.2**: Refactor 5 API modules to use `apiRequest()`:
- `frontend/lib/api/watchlist.ts`
- `frontend/lib/api/preferences.ts`
- `frontend/lib/api/portfolio.ts`
- `frontend/lib/api/ideas.ts`
- `frontend/lib/api/market.ts`

**FR-3.3**: Add future auth interceptor placeholder:
```typescript
// TODO: Add auth token when auth lands
// headers: { Authorization: `Bearer ${token}`, ...fetchOptions?.headers }
```

### FR-4: Async/Sync Mismatch Fixes (🟡 High)

**FR-4.1**: Wrap sync DB calls in async endpoints with `run_in_threadpool()`:
- `backend/app/api/watchlist.py:124-137` - `list_watchlist_items()`
- `backend/app/api/watchlist.py:363` - `get_watchlist_item()`
- `backend/app/api/preferences.py:209-234` - `get_preferences()`

**FR-4.2**: Add performance test to verify throughput improvement:
- Measure requests/second before fix (baseline)
- Measure requests/second after fix (target: 20% improvement)
- Test with 100 concurrent requests

### FR-5: UUID-Based ID Generation (🔴 Critical)

**FR-5.1**: Replace timestamp-based IDs in watchlist:
```python
# BEFORE
item_id = str(datetime.now(UTC).timestamp())

# AFTER
import uuid
item_id = str(uuid.uuid4())
```

**FR-5.2**: Add load test for ID collision detection:
- Create 100 watchlist items concurrently
- Verify no UNIQUE constraint violations
- Verify all 100 items created successfully

### FR-6: Agent Task DRY Violations (🟢 Medium)

**FR-6.1**: Extract shared agent initialization logic:
```python
def _setup_agent_tools(storage: StorageFacade) -> dict:
    """Initialize agent tools with storage context."""
    return {
        "storage": storage,
        "get_price_history": get_price_history,
        "calculate_technical_indicators": calculate_technical_indicators,
        # ... other tools
    }

def _finalize_agent_run(
    storage: StorageFacade,
    agent_run_id: str,
    status: str,
    result: dict
) -> None:
    """Update agent_runs table with completion status."""
    storage.execute(
        "UPDATE agent_runs SET status = %s, result = %s, completed_at = %s WHERE id = %s",
        (status, json.dumps(result), datetime.now(UTC), agent_run_id),
    )
```

**FR-6.2**: Refactor `run_discovery_agent()` and `run_portfolio_analyzer()` to use helpers:
- Remove ~40 lines of duplicated code
- Ensure identical behavior (no regressions)

### FR-7: Storage Docstring Updates (🟢 Medium)

**FR-7.1**: Update module docstrings in 3 files:
- `backend/app/storage/__init__.py:1` - "PostgreSQL storage layer"
- `backend/app/storage/queries.py:1` - "PostgreSQL query operations"
- `backend/app/storage/facade.py:3` - "PostgreSQL database facade"

**FR-7.2**: Remove all DuckDB references from comments and docstrings

### FR-8: Account-Scoped Preference Fix (🟡 High)

**FR-8.1**: Fix `_get_or_create_preferences()` to filter by account_id:
```python
# BEFORE
result = storage.query("SELECT * FROM user_preferences ORDER BY updated_at DESC LIMIT 1")

# AFTER
result = storage.query(
    "SELECT * FROM user_preferences WHERE id = %s LIMIT 1",
    (account_id,)
)
```

**FR-8.2**: Add integration test for multi-account preferences:
- Create preferences for 2 different accounts
- Verify each account gets correct preferences
- Verify no cross-contamination

### FR-9: Inefficient Query Optimization (🟢 Medium)

**FR-9.1**: Add targeted service method for single-item lookup:
```python
def get_item_with_score_by_id(self, item_id: str) -> Optional[dict]:
    """Get single watchlist item with score by ID (efficient query)."""
    # Direct SQL query instead of fetch-all-then-filter
```

**FR-9.2**: Update `get_watchlist_item()` endpoint to use new method

---

## Non-Goals

- **Multi-account auth implementation** - Just fix preference query, defer auth to separate PRD
- **Market holiday calendar** - TODOs documented, but implementation deferred
- **Frontend hard-coded account ID** - Will be fixed with auth PRD
- **Performance optimization beyond async/sync fix** - No query optimization beyond FR-9

---

## Technical Considerations

### Database Migration Strategy

**Migration File**: `backend/migrations/006_timezone_and_schema_fixes.sql`

```sql
-- Convert naive timestamps to UTC (assume server timezone)
ALTER TABLE watchlist_snapshots
  ALTER COLUMN fetched_at TYPE TIMESTAMPTZ USING fetched_at AT TIME ZONE 'UTC';

ALTER TABLE user_preferences
  ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC',
  ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';

-- Repeat for all tables with timestamp columns
-- (positions, agent_runs, price_cache, reference_cache, paper_trades, etc.)
```

### Testing Strategy

**TDD Approach** (Write failing tests FIRST):

1. **Timezone tests** - Test staleness detection with naive timestamps (FAIL), then fix
2. **Logging tests** - Test JSON output with old logging (FAIL), then migrate
3. **API client tests** - Test error handling with duplicated code (FAIL), then consolidate
4. **UUID tests** - Test parallel inserts with timestamp IDs (FAIL - collisions), then fix
5. **Integration tests** - Test complete flows work after all fixes

**End-to-End UI Testing** (browser-automation skill):

```bash
# Test watchlist page after all fixes
node ~/.claude/skills/browser-automation/scripts/screenshot.js \
  http://localhost:3000/watchlist \
  test-post-fixes.png

# Test settings page
node ~/.claude/skills/browser-automation/scripts/screenshot.js \
  http://localhost:3000/settings \
  test-settings-post-fixes.png

# Check for console errors
node ~/.claude/skills/browser-automation/scripts/console.js \
  http://localhost:3000/watchlist 5000
```

### Logging Configuration

**Ensure structlog configured** in `backend/app/logging_config.py`:

```python
import structlog

def get_logger(name: str) -> structlog.BoundLogger:
    """Get structured logger instance."""
    return structlog.get_logger(name)
```

### Pre-Commit Hook Integration

All fixes must pass:
- `ruff check app/ tests/` - Linting
- `ruff format app/ tests/` - Formatting
- `mypy app/ --strict` - Type checking
- `pytest tests/ -v` - All tests pass

---

## Success Metrics

### Code Quality Metrics

- **DRY Compliance**: 0 duplicated blocks >10 lines (via `ruff`)
- **Type Coverage**: 100% type hints on all functions (via `mypy --strict`)
- **Test Coverage**: Maintain 86% overall coverage (via `pytest --cov`)
- **Docstring Accuracy**: 0 references to DuckDB (via `grep -r "DuckDB" app/`)

### Data Integrity Metrics

- **Timezone Bugs**: 0 naive datetimes in database (via migration verification)
- **ID Collisions**: 0 collisions in 1000 parallel inserts (load test)
- **Staleness Accuracy**: 100% correct staleness detection (integration test)

### Performance Metrics

- **Async Throughput**: 20% improvement in requests/second (load test)
- **Query Efficiency**: Single-item lookup 10x faster than fetch-all (benchmark)

### Documentation Metrics

- **Docstring Accuracy**: 100% storage modules reference PostgreSQL (manual review)
- **Logging Standard**: 100% backend files use `get_logger()` (via `grep`)

---

## Implementation Plan

### Phase 1: Critical Data Integrity (🔴)

**Priority**: MUST complete before any feature work

1. **Timezone Standardization** (FR-1)
   - Write failing tests for staleness detection
   - Replace all `datetime.now()` → `datetime.now(UTC)` (9 files)
   - Create database migration for existing timestamps
   - Verify tests pass

2. **UUID-Based ID Generation** (FR-5)
   - Write failing test for parallel inserts (expect collisions)
   - Replace timestamp-based IDs with `uuid.uuid4()`
   - Load test with 100 concurrent requests
   - Verify 0 collisions

### Phase 2: Architecture & Performance (🟡)

**Priority**: High (blocking for production readiness)

3. **Structured Logging Migration** (FR-2)
   - Write test for JSON log output
   - Replace `logging.getLogger()` in 15 files
   - Convert f-strings to key/value logging
   - Verify JSON parsable logs

4. **Frontend API Client Consolidation** (FR-3)
   - Create `lib/api/client.ts` with error handling
   - Refactor 5 API modules to use shared client
   - Test retry logic and error handling
   - Verify UI still works (browser-automation)

5. **Async/Sync Mismatch Fixes** (FR-4)
   - Benchmark current throughput (baseline)
   - Wrap sync calls with `run_in_threadpool()`
   - Benchmark new throughput (target: +20%)
   - Load test with 100 concurrent requests

6. **Account-Scoped Preference Fix** (FR-8)
   - Write failing test for multi-account preferences
   - Fix `_get_or_create_preferences()` query
   - Verify account isolation (integration test)

### Phase 3: Code Quality & Documentation (🟢)

**Priority**: Medium (nice-to-have, improves maintainability)

7. **Agent Task DRY Violations** (FR-6)
   - Extract `_setup_agent_tools()` helper
   - Extract `_finalize_agent_run()` helper
   - Refactor both agent tasks to use helpers
   - Verify identical behavior (no regressions)

8. **Storage Docstring Updates** (FR-7)
   - Update 3 storage module docstrings
   - Remove all DuckDB references (grep search)
   - Verify accuracy (manual review)

9. **Inefficient Query Optimization** (FR-9)
   - Add `get_item_with_score_by_id()` method
   - Update `get_watchlist_item()` endpoint
   - Benchmark performance improvement

### Phase 4: End-to-End Validation

10. **Browser-Automation UI Testing**
    - Screenshot watchlist page (verify no regressions)
    - Screenshot settings page (verify preferences load)
    - Check console logs (verify no errors)
    - Monitor network requests (verify API calls work)
    - Test full user flows (add ticker, refresh, expand, etc.)

11. **Integration Testing**
    - Test complete watchlist refresh flow
    - Test preferences CRUD with multiple accounts
    - Test agent runs with structured logging
    - Verify all timestamps UTC-aware

12. **Performance Validation**
    - Load test watchlist API (100 concurrent)
    - Benchmark async endpoints (measure improvement)
    - Verify no memory leaks (long-running test)

---

## Open Questions

1. **Database Migration Timing**: Should we run migration during deployment or as separate step?
   - **Recommendation**: Run as part of deployment (automated in CI/CD)

2. **Logging Format**: Should we use JSON for all environments or plain text for development?
   - **Recommendation**: JSON for production, plain text for development (environment variable)

3. **API Client Error Handling**: Should we toast errors to user or just log them?
   - **Recommendation**: Log all errors, toast user-facing errors only

4. **Backward Compatibility**: Any concerns about breaking changes?
   - **Impact**: UUID-based IDs are breaking change for existing watchlist items
   - **Mitigation**: Generate UUIDs for existing items in migration

---

## Acceptance Criteria (Definition of Done)

- [ ] All 24 issues from solution_review.md addressed
- [ ] All tests pass (unit + integration + end-to-end)
- [ ] Test coverage maintained at 86%+
- [ ] All pre-commit hooks pass (ruff, mypy, pytest)
- [ ] Database migration tested and idempotent
- [ ] Browser-automation UI tests pass (no console errors, no visual regressions)
- [ ] Performance benchmarks meet targets (async +20%, query 10x)
- [ ] Documentation updated (ARCHITECTURE.md, DEVELOPMENT.md)
- [ ] Zero DuckDB references in codebase (grep verification)
- [ ] All functions have type hints (mypy --strict passes)
- [ ] Structured logs parsable as JSON (integration test)
- [ ] REFACTOR_STATUS.md updated (mark 0020 complete)

---

## Related Documents

- [solution_review.md](../solution_review.md) - Source of all issues addressed
- [docs/core/ARCHITECTURE.md](../docs/core/ARCHITECTURE.md) - System architecture
- [docs/core/DEVELOPMENT.md](../docs/core/DEVELOPMENT.md) - Development workflows
- [CLAUDE.md](../CLAUDE.md) - Project guidelines and standards

---

**Estimated Effort**: High (35 files affected, database migration, comprehensive testing)
**Risk Level**: Medium (breaking changes to IDs, database migration)
**Blocker For**: PRD 0021 (Narrative Intelligence), all future features
