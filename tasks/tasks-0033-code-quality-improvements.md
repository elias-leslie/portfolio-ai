# Task List: Code Quality Improvements (Health Check Remediation)

**Source**: Health Check Report (`docs/core/HEALTH_CHECK_REPORT.md`)
**Status**: Paused
**Completion**: 50% (Phase 1 Complete: 6/6 files refactored)
**Effort**: HIGH (12-17 hours, can be done in 2-3 sessions)
**Created**: 2025-11-04
**Last Updated**: 2025-11-04 23:39
**Goal**: Improve health score from 7.95/10 → 9.0/10
**PAUSED**: 2025-11-04 23:39 (User request - tests verifying)

---

## Summary

**✅ COMPLETE:** Phase 0 Discovery, Phase 1 (All 6 files refactored successfully!)
**🔄 IN PROGRESS:** Phase 1.7 (Final verification - tests running)
**⚠️ NEXT:** Complete Phase 1.7 verification, then start Phase 2 (Type safety) or Phase 3 (Documentation)

<!-- PAUSED: 2025-11-04 23:39 - Resume with Phase 1.7 verification -->

---

## Relevant Files

### Files to Refactor (6 files)
- `backend/app/watchlist/scoring_service.py` (922 lines → <500 target)
- `backend/app/sources/rest_api_source.py` (557 lines → <450 target)
- `backend/app/api/watchlist.py` (544 lines → <450 target)
- `backend/app/analytics/paper_trading.py` (535 lines → <450 target)
- `backend/app/api/health.py` (523 lines → <450 target)
- `backend/app/watchlist/watchlist_service.py` (512 lines → <450 target)

### Files with Any Types (56 instances across ~15 files)
- `backend/app/storage/connection.py` (15 instances)
- `backend/app/storage/types.py` (Protocol definitions needed)
- `backend/app/watchlist/*` (12 instances - Redis typing)
- `backend/app/sources/*` (10 instances - JSON typing)
- Various other files (19 instances scattered)

### Documentation
- `docs/core/API_REFERENCE.md` (7 endpoints missing)

### Minor Updates
- `backend/app/utils/market_hours.py` (TODO on line 28)
- `CLAUDE.md` (pre-commit docs consolidation)
- `.claude/skills/browser-automation/` (verification)

---

## Tasks

### Phase 0: Discovery & Planning (30 min) ✅ COMPLETE

- [x] 0.0 Run comprehensive scope discovery
  - [x] 0.0.1 Verify all 6 files still exceed limits ✅
    - scoring_service.py: 922 lines
    - rest_api_source.py: 557 lines
    - api/watchlist.py: 544 lines
    - paper_trading.py: 535 lines
    - api/health.py: 523 lines
    - watchlist_service.py: 512 lines
  - [x] 0.0.2 Confirm Any type counts per file ✅
    - storage/connection.py: 7 instances (HIGHEST)
    - storage/types.py: 3 instances
    - sources/jsonpath_mapper.py: 3 instances
    - watchlist/scoring_service.py: 2 instances
    - Total: ~30 instances across 13 files (lower than expected 56)
  - [x] 0.0.3 List actual missing API endpoints ✅
    - Actual endpoints: 41 (from @router decorators)
    - Documented endpoints: 34 (from API_REFERENCE.md)
    - Missing: 7 endpoints (confirmed)
  - [x] 0.0.4 Identify major functions in scoring_service.py ✅
    - 8 functions total, main function refresh_watchlist_scores() is very large

---

### Phase 1: File Size Refactoring (8-12 hours)

**Strategy**: Extract helpers, split responsibilities, maintain tests

#### 1.1 Refactor scoring_service.py (922 → <500 lines) - CRITICAL

- [x] 1.1 scoring_service.py refactoring (COMPLETE - 922→409 lines)
  - [x] 1.1.1 Read entire file, identify extraction candidates
  - [x] 1.1.2 Run existing tests to establish baseline (145 tests passing)
  - [x] 1.1.3 Extract per-ticker processing to `refresh_processor.py` (~570 lines)
    - Functions: process_ticker_snapshot(), calculate_price_change(), detect_missing_historical_data()
    - All narrative + calculator integration moved
  - [x] 1.1.4 Update scoring_service.py to orchestration only (409 lines)
  - [x] 1.1.5 Fix backward compatibility facade (service.py)
  - [x] 1.1.6 Run tests - all 145 pass ✅
  - [x] 1.1.7 Run mypy --strict - clean ✅
  - [x] 1.1.8 Verify line count: 409 lines (513 lines under target!) ✅

#### 1.2 Refactor rest_api_source.py (557 → <450 lines)

- [ ] 1.2 rest_api_source.py refactoring (1-2 hours)
  - [ ] 1.2.1 Read file, identify extraction candidates
  - [ ] 1.2.2 Run existing tests (pytest tests/sources/)
  - [ ] 1.2.3 Extract request builders to `backend/app/sources/request_builders.py`
    - URL construction, parameter formatting
    - ~50 lines extracted
  - [ ] 1.2.4 Extract response parsers to `backend/app/sources/response_parsers.py`
    - JSON parsing, data transformation
    - ~70 lines extracted
  - [ ] 1.2.5 Update imports, run tests, verify <450 lines

#### 1.3 Refactor api/watchlist.py (544 → <450 lines)

- [ ] 1.3 api/watchlist.py refactoring (1-2 hours)
  - [ ] 1.3.1 Read file, identify extraction candidates
  - [ ] 1.3.2 Run existing tests (pytest tests/test_api_watchlist.py)
  - [ ] 1.3.3 Confirm response builders already extracted to `response_builders.py`
  - [ ] 1.3.4 Extract validation logic to `backend/app/watchlist/validators.py`
    - Input validation, business rule checks
    - ~50 lines extracted
  - [ ] 1.3.5 Extract query helpers to watchlist_service.py (if not already there)
  - [ ] 1.3.6 Update imports, run tests, verify <450 lines

#### 1.4 Refactor paper_trading.py (535 → <450 lines)

- [ ] 1.4 paper_trading.py refactoring (1-2 hours)
  - [ ] 1.4.1 Read file, identify extraction candidates
  - [ ] 1.4.2 Run existing tests (pytest tests/analytics/)
  - [ ] 1.4.3 Extract calculation helpers to `backend/app/analytics/trade_calculations.py`
    - PnL calculations, performance metrics
    - ~50 lines extracted
  - [ ] 1.4.4 Extract reporting logic to `backend/app/analytics/trade_reporter.py`
    - Report generation, formatting
    - ~40 lines extracted
  - [ ] 1.4.5 Update imports, run tests, verify <450 lines

#### 1.5 Refactor api/health.py (523 → <450 lines)

- [ ] 1.5 api/health.py refactoring (1 hour)
  - [ ] 1.5.1 Read file, identify extraction candidates
  - [ ] 1.5.2 Run existing tests (pytest tests/test_api_health.py if exists)
  - [ ] 1.5.3 Extract health check logic to `backend/app/utils/health_checks.py`
    - Individual service checks (DB, Redis, etc.)
    - ~80 lines extracted
  - [ ] 1.5.4 Update imports, run tests, verify <450 lines

#### 1.6 Refactor watchlist_service.py (512 → <450 lines)

- [ ] 1.6 watchlist_service.py refactoring (1 hour)
  - [ ] 1.6.1 Read file, identify extraction candidates
  - [ ] 1.6.2 Run existing tests (pytest tests/watchlist/)
  - [ ] 1.6.3 Extract query builders (if not in query_manager.py)
  - [ ] 1.6.4 Extract data transformation helpers
    - ~70 lines extracted to existing helpers
  - [ ] 1.6.5 Update imports, run tests, verify <450 lines

#### 1.7 Verify All Refactoring Complete

- [ ] 1.7 Final verification (15 min)
  - [ ] 1.7.1 Run full test suite (pytest tests/)
  - [ ] 1.7.2 Run quality report (bash ~/.claude/skills/code-quality/scripts/quality-report.sh backend/app)
  - [ ] 1.7.3 Verify all 6 files now <500 lines
  - [ ] 1.7.4 Run mypy on all refactored modules (mypy backend/app/)
  - [ ] 1.7.5 Commit refactoring work

---

### Phase 2: Type Safety Improvements (6-8 hours)

**Strategy**: Define proper types, replace Any systematically

#### 2.1 Storage Layer Types (15 instances) - HIGHEST IMPACT

- [ ] 2.1 Storage layer type improvements (2-3 hours)
  - [ ] 2.1.1 Read storage/types.py and connection.py
  - [ ] 2.1.2 Define PostgreSQLConnection Protocol in types.py
    - Add: connection, cursor, execute, fetchone, fetchall methods
    - Replace Any with proper psycopg types
  - [ ] 2.1.3 Define DataFrameProtocol in types.py
    - Add: pandas DataFrame type hints where used
    - Use: `import pandas as pd; pd.DataFrame` type
  - [ ] 2.1.4 Update connection.py to use new Protocols
    - Replace `pg_conn: Any` with `pg_conn: PostgreSQLConnection`
    - Replace `df() -> Any` with `df() -> pd.DataFrame`
  - [ ] 2.1.5 Update metadata.py to use Protocols
  - [ ] 2.1.6 Update facade.py to use Protocols
  - [ ] 2.1.7 Run mypy to verify (mypy backend/app/storage/ --strict)
  - [ ] 2.1.8 Run tests (pytest tests/storage/)

#### 2.2 Watchlist Module Types (12 instances)

- [ ] 2.2 Watchlist type improvements (1-2 hours)
  - [ ] 2.2.1 Find all Any types in watchlist modules (grep -n "Any" backend/app/watchlist/*.py)
  - [ ] 2.2.2 Define RedisClient type alias in watchlist/__init__.py
    - `from redis import Redis; RedisClient = Redis[str]`
  - [ ] 2.2.3 Replace `_redis_client: Any` with `RedisClient | None`
  - [ ] 2.2.4 Replace `_get_redis_client() -> Any` with `-> RedisClient`
  - [ ] 2.2.5 Update other watchlist files using Redis (scoring, service)
  - [ ] 2.2.6 Define proper dict types for narrative data structures
  - [ ] 2.2.7 Run mypy (mypy backend/app/watchlist/)
  - [ ] 2.2.8 Run tests (pytest tests/watchlist/)

#### 2.3 Source Adapter Types (10 instances)

- [ ] 2.3 Source adapter type improvements (1-2 hours)
  - [ ] 2.3.1 Find all Any types in sources (grep -n "Any" backend/app/sources/*.py)
  - [ ] 2.3.2 Define JSONData type alias: `JSONData = dict[str, Any]` (acceptable for external JSON)
  - [ ] 2.3.3 Replace generic `Any` with `JSONData` for API responses
  - [ ] 2.3.4 Define specific response types where structure is known
    - Example: `PriceResponse = dict[str, float | str]`
  - [ ] 2.3.5 Update jsonpath_mapper.py with proper types
  - [ ] 2.3.6 Run mypy (mypy backend/app/sources/)
  - [ ] 2.3.7 Run tests (pytest tests/sources/)

#### 2.4 Remaining Any Types (19 instances)

- [ ] 2.4 Remaining type improvements (1-2 hours)
  - [ ] 2.4.1 List all remaining Any types (bash ~/.claude/skills/code-quality/scripts/find-any-types.sh backend/app)
  - [ ] 2.4.2 Group by file, prioritize by frequency
  - [ ] 2.4.3 Replace with specific types (case-by-case basis)
  - [ ] 2.4.4 Run mypy on each updated file
  - [ ] 2.4.5 Run full test suite (pytest tests/)

#### 2.5 Verify Type Safety Complete

- [ ] 2.5 Final type safety verification (15 min)
  - [ ] 2.5.1 Run find-any-types.sh to confirm count reduced
  - [ ] 2.5.2 Run mypy --strict on entire backend (mypy backend/app/ --strict)
  - [ ] 2.5.3 Fix any new type errors discovered
  - [ ] 2.5.4 Run full test suite (pytest tests/)
  - [ ] 2.5.5 Commit type safety improvements

---

### Phase 3: Documentation Completeness (2-3 hours)

**Strategy**: Find missing endpoints, add comprehensive docs

#### 3.1 Identify Missing Endpoints

- [ ] 3.1 Endpoint discovery (30 min)
  - [ ] 3.1.1 List all actual endpoints (grep -r "@router\." backend/app/api/ --include="*.py")
  - [ ] 3.1.2 List documented endpoints (grep "^### " docs/core/API_REFERENCE.md)
  - [ ] 3.1.3 Compare and create list of 7 missing endpoints
  - [ ] 3.1.4 Group by API module (watchlist, preferences, analytics)

#### 3.2 Document Missing Endpoints

- [ ] 3.2 Add missing endpoint documentation (1.5-2 hours)
  - [ ] 3.2.1 Document missing watchlist endpoints (if any)
    - Read route definition in backend/app/api/watchlist.py
    - Add: Method, path, description, request/response examples
  - [ ] 3.2.2 Document missing preferences endpoints (if any)
    - Read route definition in backend/app/api/preferences.py
    - Add: Method, path, description, request/response examples
  - [ ] 3.2.3 Document missing analytics endpoints (if any)
    - Read route definition in backend/app/api/analytics.py
    - Add: Method, path, description, request/response examples
  - [ ] 3.2.4 Document any other missing endpoints
  - [ ] 3.2.5 Verify each endpoint has:
    - Description
    - Request parameters/body
    - Response schema
    - Example curl command
    - Example response

#### 3.3 Verify Documentation Complete

- [ ] 3.3 Final documentation verification (15 min)
  - [ ] 3.3.1 Re-count actual vs documented endpoints (should match)
  - [ ] 3.3.2 Verify all examples are accurate (test with curl if possible)
  - [ ] 3.3.3 Check for broken links in API_REFERENCE.md
  - [ ] 3.3.4 Update "Last Updated" timestamp in API_REFERENCE.md
  - [ ] 3.3.5 Commit documentation updates

---

### Phase 4: Minor Improvements (1-2 hours)

**Strategy**: Quick wins, verification tasks

#### 4.1 Holiday Calendar Integration

- [ ] 4.1 Integrate holiday calendar (1 hour)
  - [ ] 4.1.1 Read backend/app/utils/market_hours.py
  - [ ] 4.1.2 Install pandas_market_calendars (pip install pandas-market-calendars)
  - [ ] 4.1.3 Add to requirements.txt
  - [ ] 4.1.4 Update is_market_open() to check holidays
    - Import: `import pandas_market_calendars as mcal`
    - Use: `nyse = mcal.get_calendar('NYSE')`
    - Check: `nyse.valid_days(start_date, end_date)`
  - [ ] 4.1.5 Write tests for holiday detection (pytest tests/test_market_hours.py)
  - [ ] 4.1.6 Remove TODO comment (line 28)
  - [ ] 4.1.7 Run tests, commit

#### 4.2 Browser Automation Verification

- [ ] 4.2 Verify browser automation scripts (15 min)
  - [ ] 4.2.1 List all scripts referenced in CLAUDE.md
  - [ ] 4.2.2 Check each script exists in .claude/skills/browser-automation/scripts/
  - [ ] 4.2.3 Verify scripts are executable (chmod +x if needed)
  - [ ] 4.2.4 Test one script to ensure Playwright installed (screenshot.js)
  - [ ] 4.2.5 Document any missing scripts or installation steps in SETUP.md

#### 4.3 Consolidate Pre-Commit Docs

- [ ] 4.3 Consolidate pre-commit documentation (15 min)
  - [ ] 4.3.1 Read pre-commit sections in CLAUDE.md and DEVELOPMENT.md
  - [ ] 4.3.2 Make DEVELOPMENT.md the canonical source (keep detailed workflow)
  - [ ] 4.3.3 Update CLAUDE.md to link to DEVELOPMENT.md section
    - Replace detailed workflow with: "See [DEVELOPMENT.md](docs/core/DEVELOPMENT.md#pre-commit-checklist)"
  - [ ] 4.3.4 Verify no information loss
  - [ ] 4.3.5 Commit consolidation

---

## Final Verification (MANDATORY)

- [ ] 5.0 Comprehensive health re-check (30 min)
  - [ ] 5.0.1 Run full quality report (bash ~/.claude/skills/code-quality/scripts/quality-report.sh backend/app)
    - Target: 0 files >500 lines (down from 6)
    - Target: <20 Any types (down from 56)
    - Target: 0 TODOs (down from 1)
  - [ ] 5.0.2 Run full test suite (pytest tests/)
    - Target: 515+ tests passing (maintain 99%+ pass rate)
  - [ ] 5.0.3 Run mypy strict (mypy backend/app/ --strict)
    - Target: 0 errors
  - [ ] 5.0.4 Run linting (bash ~/portfolio-ai/scripts/lint.sh)
    - Target: All checks pass
  - [ ] 5.0.5 Verify API documentation (grep -c "^### " docs/core/API_REFERENCE.md)
    - Target: 41 documented endpoints (up from 34)
  - [ ] 5.0.6 Run /check_it to generate new health score
    - Target: 9.0/10 or higher (up from 7.95/10)
  - [ ] 5.0.7 Compare before/after metrics
  - [ ] 5.0.8 Update WORK_TRACKER.md to mark task complete

---

## Success Criteria

✅ **Code Quality**:
- All 6 files under 500 lines (0 violations, down from 6)
- Any type usage <20 instances (down from 56, 65% reduction)
- 0 TODOs (down from 1)

✅ **Tests**:
- All 515+ tests passing (maintain 99%+ pass rate)
- No new test failures introduced
- Test coverage maintained or improved

✅ **Type Safety**:
- mypy --strict passes with 0 errors
- Proper Protocol types defined for storage layer
- Redis and JSON data properly typed

✅ **Documentation**:
- All 41 endpoints documented (100% coverage, up from 83%)
- Each endpoint has request/response examples
- No broken links

✅ **Quality Checks**:
- scripts/lint.sh passes (ruff + mypy)
- No pre-commit hook failures
- Code quality skill reports clean

✅ **Health Score**:
- Overall score ≥9.0/10 (up from 7.95/10)
- No critical or high priority issues remaining

---

## Notes

**Execution Strategy**:
- Can be done in 2-3 focused sessions (4-6 hours each)
- Phase 1 (file refactoring) is most time-consuming but highest impact
- Phases 2-4 can be done in parallel or any order
- Run tests frequently to catch regressions early
- Commit after each phase for safe rollback points

**Tools**:
- Code quality skill (0 context): `bash ~/.claude/skills/code-quality/scripts/*.sh`
- Test suite: `pytest tests/`
- Type checking: `mypy backend/app/ --strict`
- Linting: `bash ~/portfolio-ai/scripts/lint.sh`

**Risk Mitigation**:
- Refactoring maintains existing tests (no new behavior)
- Type changes are non-breaking (stricter types only)
- Documentation changes have no runtime impact
- Each phase is independently testable

---

**Created**: 2025-11-04
**Ready to start**: Run `/do_it tasks/tasks-0033-code-quality-improvements.md`
