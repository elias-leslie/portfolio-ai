# Task List: Code Quality & Test Execution

**Source**: VISION.md Gap Analysis via /align_it (2025-12-02)
**Complexity**: Complex
**Effort**: HIGH (3-5 days)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-02 12:00

---

## Summary

**Goal**: Restore code quality compliance by fixing test execution blockers, resolving mypy errors, and decomposing oversized files to meet VISION.md standards (0 mypy errors, all files <800 lines, 100% test pass rate).

**Approach**:
1. Fix migration 052 to unblock test execution
2. Systematically resolve mypy --strict errors (159 total)
3. Decompose 3 hard-limit violation files into smaller modules

**Scope Discovery**: Required for mypy errors and file decomposition strategy

---

## Tasks

**IMPORTANT: Use section headers (###) for high-level tasks**

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run mypy --strict to get current error list
  - Command: `cd ~/portfolio-ai/backend && .venv/bin/mypy --strict app/ 2>&1 | head -200`
  - Goal: Verify 159 errors, identify top offending files
  - Output: Prioritized list of files by error count
- [ ] 0.2 Analyze migration 052 failure
  - Check: `backend/migrations/052_strategy_trade_linking.sql`
  - Identify: Missing table references, dependency issues
- [ ] 0.3 Review 3 hard-limit files for decomposition strategy
  - `app/api/market.py` (935L) - Identify logical splits
  - `app/tasks/indicator_tasks.py` (838L) - Group by indicator type
  - `app/tasks/data_ingestion_tasks.py` (810L) - Group by data source
- [ ] 0.4 Checkpoint: Confirm scope before proceeding
  - Total mypy errors: [TBD - verify 159]
  - Migration issue: [TBD]
  - Decomposition approach: [TBD]
  - Estimated effort: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Fix Migration 052 to Unblock Tests

- [ ] 1.1 Identify missing table/column dependencies
  - Review migration SQL for references to non-existent tables
  - Check `strategy_definitions` table existence
- [ ] 1.2 Fix or rollback migration 052
  - Option A: Add missing table creation
  - Option B: Reorder migration dependencies
  - Option C: Rollback and recreate properly
- [ ] 1.3 Run test collection to verify fix
  - Command: `cd ~/portfolio-ai/backend && pytest --collect-only 2>&1 | tail -20`
  - Success: 0 collection errors
- [ ] 1.4 Run full test suite smoke test
  - Command: `cd ~/portfolio-ai/backend && pytest tests/ -v --tb=short -x 2>&1 | tail -50`

### 2.0 Resolve Mypy Errors in paper_trades.py

- [ ] 2.1 Run mypy on single file to get specific errors
  - Command: `.venv/bin/mypy --strict app/api/paper_trades.py`
- [ ] 2.2 Fix numeric type mismatches (float vs Decimal)
  - Add explicit Decimal() conversions where needed
  - Use float() for display values
- [ ] 2.3 Fix Union type handling
  - Add proper None checks before accessing Optional fields
  - Use `assert` or `if` guards
- [ ] 2.4 Remove unused type: ignore comments
- [ ] 2.5 Verify file passes mypy --strict

### 3.0 Resolve Mypy Errors in recommendations.py

- [ ] 3.1 Run mypy on single file
- [ ] 3.2 Fix type annotation issues
- [ ] 3.3 Fix return type mismatches
- [ ] 3.4 Verify file passes mypy --strict

### 4.0 Resolve Mypy Errors in Remaining Files

- [ ] 4.1 Fix `app/services/agent_telemetry.py` (~12 errors)
- [ ] 4.2 Fix `app/api/capabilities/` modules (~10 errors)
- [ ] 4.3 Fix `app/strategies/storage.py` (Decimal/float)
- [ ] 4.4 Fix `app/backtest/portfolio_backtest.py` (~8 errors)
- [ ] 4.5 Run full mypy --strict and verify 0 errors
  - Command: `cd ~/portfolio-ai/backend && .venv/bin/mypy --strict app/`

### 5.0 Decompose market.py (935L → <500L modules)

- [ ] 5.1 Analyze market.py structure
  - Identify logical groupings (source drivers, transformers, routes)
- [ ] 5.2 Create `app/api/market_sources.py`
  - Extract data source fetching logic
- [ ] 5.3 Create `app/api/market_transformers.py`
  - Extract data transformation/aggregation logic
- [ ] 5.4 Update imports in market.py
  - Keep only route handlers in main file
- [ ] 5.5 Verify market.py <500 lines
- [ ] 5.6 Run tests for market module
  - `pytest tests/api/test_market.py -v`

### 6.0 Decompose indicator_tasks.py (838L → <500L modules)

- [ ] 6.1 Analyze indicator_tasks.py structure
  - Group by indicator type (RSI, MACD, EMA, etc.)
- [ ] 6.2 Create `app/tasks/indicators/` package
  - `__init__.py` - Re-exports
  - `rsi_tasks.py` - RSI calculations
  - `macd_tasks.py` - MACD calculations
  - `trend_tasks.py` - EMA/SMA/trend indicators
- [ ] 6.3 Update Celery task registrations
- [ ] 6.4 Verify indicator_tasks.py <500 lines
- [ ] 6.5 Run tests for indicator tasks
  - `pytest tests/tasks/test_indicator_tasks.py -v`

### 7.0 Decompose data_ingestion_tasks.py (810L → <500L modules)

- [ ] 7.1 Analyze data_ingestion_tasks.py structure
  - Group by data source/type
- [ ] 7.2 Create `app/tasks/ingestion/` package
  - `__init__.py` - Re-exports
  - `price_ingestion.py` - OHLCV data
  - `news_ingestion.py` - News feeds
  - `reference_ingestion.py` - Reference data
- [ ] 7.3 Update Celery task registrations
- [ ] 7.4 Verify data_ingestion_tasks.py <500 lines
- [ ] 7.5 Run tests for ingestion tasks

### 8.0 Final Verification

- [ ] 8.1 Run full mypy --strict
  - Target: 0 errors
- [ ] 8.2 Run full test suite
  - Target: 100% pass rate
- [ ] 8.3 Verify file sizes
  - Command: `wc -l app/api/market.py app/tasks/indicator_tasks.py app/tasks/data_ingestion_tasks.py`
  - Target: All <500 lines
- [ ] 8.4 Run pre-commit hooks
  - Command: `cd ~/portfolio-ai && pre-commit run --all-files`
- [ ] 8.5 Restart services and verify
  - Command: `bash ~/portfolio-ai/scripts/restart.sh`

---

## Verification

- [ ] Functional: All migration issues resolved, tests executable
- [ ] Tests: 100% pass rate (1,056+ tests), all collection errors fixed
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy --strict = 0 errors)
- [ ] Architecture: All files <800 lines (hard limit), target <500 lines (soft limit)
- [ ] Services: Restarted and verified (`bash ~/portfolio-ai/scripts/restart.sh`)
- [ ] Clean: No Any types, proper type annotations throughout
- [ ] Docs: REFACTOR_STATUS.md updated if architectural changes made
