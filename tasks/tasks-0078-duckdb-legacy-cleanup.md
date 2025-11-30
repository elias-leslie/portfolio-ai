# Task List: DuckDB Legacy Code Cleanup

**Source**: Discovered during Task 0076 backtest fixes
**Complexity**: Medium
**Effort**: MEDIUM (3-4 hours)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-30
**Priority**: HIGH - Blocking full system functionality

---

## Summary

**Goal**: Complete the DuckDB → PostgreSQL migration by fixing all remaining legacy code patterns
**Approach**: Search for DuckDB patterns (`execute_read_query`, `?` placeholders, `ConnectionManager` misuse) and update to PostgreSQL/PortfolioStorage
**Scope Discovery**: Required

---

## Background

During Task 0076, we discovered multiple files still using DuckDB patterns:
- `execute_read_query()` method calls (doesn't exist on PortfolioStorage)
- `?` SQL placeholders (should be `$1, $2, $3`)
- `ConnectionManager` type hints where `PortfolioStorage` expected
- `.execute()` method calls (should use `connection()` context manager)

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run Explore subagent in "very thorough" mode
  - Pattern 1: `execute_read_query` across entire codebase
  - Pattern 2: SQL queries with `?` placeholders in Python files
  - Pattern 3: `ConnectionManager` used where `PortfolioStorage` expected
  - Pattern 4: `.execute()` on PortfolioStorage objects
  - Goal: Find ALL remaining DuckDB patterns
  - Output: Complete list with file:line references
- [ ] 0.2 Update this task list with ALL discovered files
  - Group by: Backtest module, API endpoints, Tasks, Strategies
- [ ] 0.3 Checkpoint: Confirm scope before proceeding
  - Total files affected: [TBD]
  - Estimated effort: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Known Files from Task 0076

**These were identified but not fixed during backtest repair:**

- [ ] 1.1 Fix `app/strategies/optimizer.py:343`
  - Change `storage: ConnectionManager` to `storage: PortfolioStorage`
  - Update any `execute_read_query()` calls
- [ ] 1.2 Fix `app/api/layouts.py` (lines 69, 91)
  - Replace `.execute()` with `storage.connection()` context manager
  - Update type hints
- [ ] 1.3 Fix `app/tasks/strategy_metrics_tasks.py:146`
  - Replace `.execute()` with proper query method
- [ ] 1.4 Fix `app/api/watchlist.py:589`
  - Replace `.execute()` with proper query method
- [ ] 1.5 Fix `app/tasks/data_freshness_tasks.py:33`
  - Fix `.df` attribute access

### 2.0 Additional Files from Scope Discovery

- [ ] 2.1-2.N [To be added after scope discovery]

### 3.0 Verification

- [ ] 3.1 Run `~/portfolio-ai/scripts/lint.sh`
  - Confirm 0 new mypy errors in fixed files
- [ ] 3.2 Run relevant unit tests
  - `pytest tests/unit/backtest/ -v`
  - `pytest tests/unit/strategies/ -v`
- [ ] 3.3 Test API endpoints that were fixed
- [ ] 3.4 Verify Celery tasks execute without errors

---

## Verification

- [ ] Functional: All DuckDB patterns replaced
- [ ] Tests: Related tests passing
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes (no new errors)
- [ ] Services: Restarted and verified

---

## Migration Patterns Reference

### Query Execution

```python
# ❌ DuckDB pattern
result = storage.execute_read_query(query, (param1, param2))

# ✅ PostgreSQL pattern
result_df = storage.query(query, [param1, param2])
rows = result_df.to_dicts()
```

### SQL Placeholders

```python
# ❌ DuckDB pattern
query = "SELECT * FROM table WHERE col = ? AND date = ?"

# ✅ PostgreSQL pattern
query = "SELECT * FROM table WHERE col = $1 AND date = $2"
```

### Type Hints

```python
# ❌ DuckDB pattern
def my_function(storage: ConnectionManager) -> None:

# ✅ PostgreSQL pattern
def my_function(storage: PortfolioStorage) -> None:
```

### Connection Context

```python
# ❌ DuckDB pattern
storage.execute("INSERT INTO ...")

# ✅ PostgreSQL pattern
with storage.connection() as conn:
    conn.execute("INSERT INTO ...")
    conn.commit()
```
