# PostgreSQL Migration - Remaining Work

**PRD**: `0015-prd-postgresql-migration.md`
**Status**: Infrastructure Complete (85%), Test Fixes In Progress
**Test Pass Rate**: 211+/296 (71.3%+)
**Last Updated**: 2025-10-30
**Commit**: 1c8b2aa

---

## Executive Summary

PostgreSQL migration infrastructure is complete and working:
- ✅ Schema migrated (17 tables)
- ✅ Connection pooling working (35 concurrent @ 43.8ms)
- ✅ Celery using PostgreSQL backend
- ✅ DataFrame insertion method implemented
- ✅ Type hints proper and complete
- ✅ Schema validation (single source of truth)

**Remaining**: Fix ~85 test failures (mainly test isolation and schema validation tests)

---

## ✅ Completed Infrastructure (85%)

### Core Migration (100%)
- [x] PostgreSQL 16 installed and configured
- [x] Database and user created
- [x] Schema migrated (17 tables with indexes and foreign keys)
- [x] Data exported from DuckDB
- [x] Configuration data imported to PostgreSQL
- [x] Connection layer migrated to SQLAlchemy
- [x] SQL queries updated for PostgreSQL dialect

### Code Quality Fixes (100%)
- [x] Celery configuration → Redis broker + PostgreSQL backend
- [x] DataFrame insertion method → `insert_dataframe()` using SQLAlchemy
- [x] Type hints → `Iterator[PostgreSQLDuckDBWrapper]` (no more `Any`)
- [x] Schema manager → Validation-only (removed 350 lines of duplicate DDL)
- [x] Test fixtures → Updated for PostgreSQL (9 files)
- [x] DuckDB commands → PostgreSQL equivalents (`SHOW TABLES` → `information_schema.tables`)

### Verification (100%)
- [x] Connection pool test: 35 concurrent connections successful
- [x] Average latency: 43.8ms (well below 50ms target)
- [x] Celery tables created in PostgreSQL
- [x] 211+ tests passing (71.3%+)

---

## 🔧 Remaining Work

### 1. Fix Test Failures (~85 tests) [EFFORT: Medium, 2-3 hours]

**Categories:**

#### Test Isolation Issues (~40 tests estimated)
**Problem**: Tests finding leftover data from previous tests
**Example**: `test_api_ideas.py::test_get_ideas_empty` expects 0 rows but finds 2
**Root Cause**: PostgreSQL persists data between tests (DuckDB was in-memory)

**Solution**:
```python
# Add to conftest.py or test fixtures:
@pytest.fixture(autouse=True)
def clean_database():
    """Clean all tables between tests."""
    yield
    # Cleanup after test
    conn.execute("TRUNCATE TABLE ideas, watchlist_items, ... CASCADE")
```

**Tasks**:
- [ ] 1.1 Create database cleanup fixture in `tests/conftest.py`
- [ ] 1.2 Apply to all test modules with `autouse=True`
- [ ] 1.3 Verify isolation by running tests in random order
- [ ] 1.4 Re-run test suite, should fix ~40 tests

#### Schema Validation Tests (~20 tests estimated)
**Problem**: Tests expect DuckDB-specific column types or table structures
**Example**: Type checks for `JSON` vs `JSONB`, `TIMESTAMP` vs `TIMESTAMPTZ`

**Tasks**:
- [ ] 1.5 Review `tests/test_storage_schema.py` failures
- [ ] 1.6 Update assertions for PostgreSQL types:
  - `JSON` → `JSONB`
  - `TIMESTAMP` → `TIMESTAMPTZ`
  - `INTEGER` (auto-increment) → `SERIAL` or `IDENTITY`
- [ ] 1.7 Update table existence checks to use `information_schema.tables`
- [ ] 1.8 Re-run schema tests, verify all pass

#### Query Compatibility Issues (~10 tests estimated)
**Problem**: SQL dialect differences (rare edge cases)

**Tasks**:
- [ ] 1.9 Run full test suite with verbose output: `pytest tests/ -v --tb=short > test_results.txt`
- [ ] 1.10 Grep for SQL errors: `grep -i "psycopg2\|syntax error" test_results.txt`
- [ ] 1.11 Fix any remaining query syntax issues
- [ ] 1.12 Verify no SQL errors remain

#### Test Fixture Configuration (~15 tests estimated)
**Problem**: Tests may need PostgreSQL-specific transaction handling

**Tasks**:
- [ ] 1.13 Review fixture setup in `tests/conftest.py`
- [ ] 1.14 Ensure connection fixtures use proper transaction scopes
- [ ] 1.15 Test rollback behavior for test isolation
- [ ] 1.16 Update fixtures if needed

**Verification**:
```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
pytest tests/ -v --cov=app --cov-report=term-missing
# Target: 100% pass rate, 80%+ coverage
```

---

### 2. Performance Validation [EFFORT: Low, 30 minutes]

**Tasks**:
- [ ] 2.1 Run concurrent write benchmark:
  ```bash
  python scripts/benchmark-concurrent-writes.py
  # Target: 100 writes, 0 errors, <50ms avg latency
  ```
- [ ] 2.2 Run watchlist refresh benchmark:
  ```bash
  python scripts/benchmark-watchlist-refresh.py
  # Target: <2 seconds for 5 tickers
  ```
- [ ] 2.3 Document results in this file

**Expected Results**:
- Zero errors under load
- Concurrent writes: ~30 writes/sec, <50ms latency
- Watchlist refresh: <2 seconds
- Connection pool: Never exhausted

---

### 3. Operational Scripts [EFFORT: Low, 20 minutes]

**Tasks**:
- [ ] 3.1 Create backup script (`scripts/postgres-backup.sh`):
  ```bash
  pg_dump portfolio_ai | gzip > backup_$(date +%Y%m%d).sql.gz
  ```
- [ ] 3.2 Create monitoring script (`scripts/postgres-status.sh`):
  ```bash
  psql portfolio_ai -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
  ```
- [ ] 3.3 Make scripts executable: `chmod +x scripts/postgres-*.sh`
- [ ] 3.4 Test both scripts

---

### 4. Documentation Updates [EFFORT: Low, 15 minutes]

**Tasks**:
- [ ] 4.1 Update `docs/core/OPERATIONS.md`:
  - Add "PostgreSQL Operations" section
  - Document backup/restore procedures
  - Add troubleshooting guide (connection pool, slow queries, locks)
- [ ] 4.2 Update `CLAUDE.md`:
  - Update "Tech Stack" section (DuckDB → PostgreSQL 16)
  - Update "Quick Start" (remove Redis requirement)
- [ ] 4.3 Update `docs/core/REFACTOR_STATUS.md`:
  - Mark PRD #0015 as COMPLETE
  - Add completion date and metrics

---

### 5. Production Go-Live [EFFORT: Low, 24 hours monitoring]

**Pre-Flight Checklist**:
- [ ] 5.1 All tests passing (100% pass rate)
- [ ] 5.2 Performance benchmarks meet targets
- [ ] 5.3 Backup/restore scripts tested
- [ ] 5.4 Documentation complete
- [ ] 5.5 No errors in logs for 1 hour

**Go-Live Steps**:
```bash
# 1. Stop services
./scripts/shutdown.sh

# 2. Restart with PostgreSQL
./scripts/start.sh

# 3. Verify health
curl http://localhost:8000/api/health

# 4. Monitor for 24 hours
./scripts/postgres-status.sh  # Run every 4 hours
tail -f /tmp/portfolio-backend.log
```

**24-Hour Soak Test Criteria**:
- [ ] 5.6 No connection leaks (count stays <30)
- [ ] 5.7 No lock errors in logs
- [ ] 5.8 All Celery tasks complete successfully
- [ ] 5.9 API responses <100ms p95
- [ ] 5.10 No crashes or restarts needed

---

## Known Issues

### Test Isolation (High Priority)
**Issue**: Tests finding leftover data
**Impact**: ~40 test failures
**Fix**: Database cleanup fixture (Task 1.1-1.4)

### Schema Validation Tests (Medium Priority)
**Issue**: Tests expect DuckDB types
**Impact**: ~20 test failures
**Fix**: Update assertions for PostgreSQL types (Task 1.5-1.8)

---

## Success Metrics

**Current State**:
- Test pass rate: 71.3% (211+/296)
- Celery workers: 4+ capable (Redis broker working)
- Concurrency: 35 simultaneous connections ✅
- Connection latency: 43.8ms avg ✅
- Code quality: Zero band-aids ✅

**Target State**:
- Test pass rate: 100% (296/296)
- Coverage: 80%+
- Celery workers: 4+ concurrent with zero lock errors
- Performance: Maintained or improved vs DuckDB

---

## Quick Commands

```bash
# Activate environment
cd ~/portfolio-ai/backend
source .venv/bin/activate

# Run tests
pytest tests/ -v --tb=short

# Run specific test module
pytest tests/test_storage_schema.py -v

# Check for remaining DuckDB commands
grep -r "SHOW TABLES\|PRAGMA\|DESCRIBE" app/ tests/ --include="*.py"

# Monitor PostgreSQL
./scripts/postgres-status.sh

# Backup database
./scripts/postgres-backup.sh
```

---

## Files Reference

**Archived Analysis Documents** (see `tasks/archive/`):
- `tasks-0015-ANALYSIS-bandaids.md` - Band-aid analysis (historical)
- `tasks-0015-COMPLETED-TASKS-REVIEW.md` - Code review (historical)
- `tasks-0015-CLEAN-MIGRATION-PLAN.md` - Refactored plan (historical)
- `tasks-0015-SUMMARY.md` - Analysis summary (historical)
- `tasks-0015-MIGRATION-STATUS.md` - Status report (historical)

**Current Documents**:
- This file - Current status and remaining work
- `docs/core/ARCHITECTURE.md` - System design
- `docs/core/OPERATIONS.md` - Operational runbooks (to be updated)

---

## Next Steps

1. **Fix test isolation** (highest impact) → Task 1.1-1.4
2. **Fix schema tests** → Task 1.5-1.8
3. **Run full test suite** → Verify 100% pass rate
4. **Create operational scripts** → Tasks 3.1-3.4
5. **Update documentation** → Tasks 4.1-4.3
6. **Production go-live** → Tasks 5.1-5.10

**Estimated Time to Complete**: 3-4 hours active work + 24 hours monitoring

---

**Status**: Ready for test fixes
**Next Action**: Implement database cleanup fixture (Task 1.1)
**Blocker**: None (infrastructure complete)
