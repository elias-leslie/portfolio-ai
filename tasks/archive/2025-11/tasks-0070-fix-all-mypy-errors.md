# Task List: Fix All Mypy --Strict Errors (260 errors, 43 files)

**Source**: User request via /task_it - Unblock pre-commit hook
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-17 13:20

---

## Summary

**Goal**: Achieve full mypy --strict compliance across entire backend codebase to unblock pre-commit hook

**Current State**: 260 mypy errors across 43 files blocking all commits (require SKIP=mypy workaround)

**Approach**: Systematic categorization for parallel execution with --max mode
- Group errors by category (union-attr, arg-type, return-value, etc.)
- Fix each category across all affected files simultaneously
- Use proper type narrowing (isinstance checks) for long-term maintainability
- Add missing type hints and reduce Any types where easily parallelizable

**Scope Discovery**: Required - Must categorize all 260 errors systematically

---

## Tasks

**IMPORTANT: This task is designed for `--max` mode parallel execution**

### 0.0 Scope Discovery & Categorization (MANDATORY)

- [ ] 0.1 Run full mypy check and capture all 260 errors
  ```bash
  cd ~/portfolio-ai/backend && source .venv/bin/activate
  mypy app/ --strict --config-file=pyproject.toml 2>&1 | tee /tmp/mypy-full-errors.txt
  ```
  - [ ] Parse output to extract: file, line, error type, message
  - [ ] Create structured error catalog by category

- [ ] 0.2 Categorize errors for parallel execution
  - [ ] Group 1: union-attr errors (Item "X" has no attribute "Y")
  - [ ] Group 2: arg-type errors (Incompatible type in argument)
  - [ ] Group 3: return-value errors (Incompatible return value type)
  - [ ] Group 4: list-item errors (List item has incompatible type)
  - [ ] Group 5: operator errors (Unsupported operand types)
  - [ ] Group 6: assignment errors (Incompatible types in assignment)
  - [ ] Group 7: index errors (Invalid index type)
  - [ ] Group 8: Other errors (misc, no-any-return, etc.)

- [ ] 0.3 Create file-by-file breakdown
  - [ ] List all 43 affected files with error counts
  - [ ] Identify files with >10 errors (high priority)
  - [ ] Identify files with <5 errors (quick wins)

- [ ] 0.4 Checkpoint: Confirm scope and approach
  - Total errors: 260
  - Error categories: [TBD from 0.2]
  - High-priority files: [TBD from 0.3]
  - Parallel execution plan: [TBD - which groups can run simultaneously]

**DO NOT PROCEED TO TASK 1 UNTIL CATEGORIZATION COMPLETE**

### 1.0 Fix union-attr Errors (Parallel Group A)

**Error Pattern**: `Item "str" of "str | int | None" has no attribute "isoformat"`

**Root Cause**: Union types from database queries not narrowed before use

**Solution**: Add type guards using isinstance() checks

- [ ] 1.1 Create reusable type guard utilities
  - [ ] Add to `app/utils/type_guards.py`:
    - `is_datetime(val: Any) -> TypeGuard[datetime]`
    - `is_str(val: Any) -> TypeGuard[str]`
    - `is_int(val: Any) -> TypeGuard[int]`
    - `is_float(val: Any) -> TypeGuard[float]`

- [ ] 1.2 Fix union-attr in api/ module (parallel task)
  - [ ] api/news_profiling.py - datetime.isoformat() calls
  - [ ] api/capabilities/capabilities_router.py - attribute access
  - [ ] Add isinstance checks before attribute access

- [ ] 1.3 Fix union-attr in watchlist/ module (parallel task)
  - [ ] watchlist/earnings.py - .get() on union types
  - [ ] Add type narrowing with guard clauses

- [ ] 1.4 Fix union-attr in tasks/ module (parallel task)
  - [ ] tasks/indicator_tasks.py - union type operations
  - [ ] Add runtime type checks

- [ ] 1.5 Verify all union-attr errors resolved
  ```bash
  mypy app/ --strict 2>&1 | grep "union-attr" | wc -l
  # Expected: 0
  ```

### 2.0 Fix arg-type Errors (Parallel Group B)

**Error Pattern**: `Argument 1 to "float" has incompatible type "str | int | float | bool | None"`

**Root Cause**: Database row values have union types, passed to functions expecting specific types

**Solution**: Type narrowing + validation before function calls

- [ ] 2.1 Fix arg-type in storage/ module (parallel task)
  - [ ] storage/connection.py - execute() parameter types
  - [ ] Convert list[str] to Sequence[str | int | float | ...] where needed
  - [ ] Or add explicit type casts with validation

- [ ] 2.2 Fix arg-type in watchlist/ module (parallel task)
  - [ ] watchlist/fundamentals.py - date parameter issues
  - [ ] watchlist/earnings.py - date parameter issues
  - [ ] Add date type validation before SQL execution

- [ ] 2.3 Fix arg-type in tasks/ module (parallel task)
  - [ ] tasks/data_ingestion_tasks.py - execute() parameters
  - [ ] tasks/market_data/fear_greed_pipeline.py - execute() parameters
  - [ ] Fix parameter type annotations

- [ ] 2.4 Fix arg-type in services/ module (parallel task)
  - [ ] services/gap_detection/capability_checker.py - execute() parameters
  - [ ] services/capability_db_scanner.py - execute() parameters

- [ ] 2.5 Verify all arg-type errors resolved
  ```bash
  mypy app/ --strict 2>&1 | grep "arg-type" | wc -l
  # Expected: 0
  ```

### 3.0 Fix return-value Errors (Parallel Group C)

**Error Pattern**: `Incompatible return value type (got "X", expected "Y")`

**Root Cause**: Function return type annotations don't match actual return values

**Solution**: Fix type annotations or add proper type conversions

- [ ] 3.1 Fix return-value in storage/ module (parallel task)
  - [ ] storage/connection.py - fetchall() return type
  - [ ] Update return type hints to match actual returns

- [ ] 3.2 Fix return-value in watchlist/ module (parallel task)
  - [ ] watchlist/fundamentals.py - response dict types
  - [ ] watchlist/earnings.py - response dict types

- [ ] 3.3 Fix return-value in tasks/ module (parallel task)
  - [ ] tasks/agent_tasks.py - PaperTradeStatsDict vs dict[str, int]
  - [ ] tasks/market_data/historical_ohlcv_pipeline.py - tuple return types
  - [ ] tasks/market_data/fear_greed_pipeline.py - dict return types

- [ ] 3.4 Fix return-value in services/ module (parallel task)
  - [ ] services/gap_detection/capability_checker.py - dict return types

- [ ] 3.5 Verify all return-value errors resolved
  ```bash
  mypy app/ --strict 2>&1 | grep "return-value" | wc -l
  # Expected: 0
  ```

### 4.0 Fix list-item & operator Errors (Parallel Group D)

**Error Pattern**:
- `List item 2 has incompatible type "date"; expected "str | int | float | datetime | None"`
- `Unsupported operand types for < ("int" and "None")`

**Root Cause**: Type mismatches in list literals and comparison operations

**Solution**: Add proper type casts and null checks

- [ ] 4.1 Fix list-item errors (parallel task)
  - [ ] watchlist/fundamentals.py - date in parameter lists
  - [ ] watchlist/earnings.py - date in parameter lists
  - [ ] Convert date to datetime or add to allowed types

- [ ] 4.2 Fix operator errors (parallel task)
  - [ ] watchlist/calculator.py - comparison with None
  - [ ] services/capability_db_scanner.py - comparison with None
  - [ ] Add null checks before comparisons: `if x is not None and x < threshold`

- [ ] 4.3 Verify list-item and operator errors resolved
  ```bash
  mypy app/ --strict 2>&1 | grep -E "list-item|operator" | wc -l
  # Expected: 0
  ```

### 5.0 Fix index & assignment Errors (Parallel Group E)

**Error Pattern**:
- `Invalid index type "str | int | None" for "dict[str, ...]"`
- `Incompatible types in assignment`

**Root Cause**: Dictionary keys and assignment targets have union types

**Solution**: Type narrowing before indexing and assignment

- [ ] 5.1 Fix index errors (parallel task)
  - [ ] api/capabilities/capabilities_router.py - dict indexing
  - [ ] tasks/market_data/fear_greed_pipeline.py - dict indexing
  - [ ] Add type guards before dictionary access

- [ ] 5.2 Fix assignment errors (parallel task)
  - [ ] services/gap_detection/capability_checker.py - dict assignments
  - [ ] tasks/market_data/fear_greed_pipeline.py - tuple assignments
  - [ ] Fix type annotations to match assigned values

- [ ] 5.3 Verify index and assignment errors resolved
  ```bash
  mypy app/ --strict 2>&1 | grep -E "index|assignment" | wc -l
  # Expected: 0
  ```

### 6.0 Fix TypedDict & Misc Errors (Parallel Group F)

**Error Pattern**:
- `Missing keys (...) for TypedDict "X"`
- `Unused "type: ignore" comment`
- Various other misc errors

**Root Cause**: Incomplete TypedDict construction, stale type: ignore comments

**Solution**: Complete dict construction, remove unused ignores

- [ ] 6.1 Fix TypedDict errors (parallel task)
  - [ ] tasks/indicator_tasks.py - FearGreedCalculationDict
  - [ ] tasks/market_data/fear_greed_pipeline.py - FearGreedPipelineResultDict
  - [ ] Add all required keys or make fields optional

- [ ] 6.2 Fix unused type: ignore comments (parallel task)
  - [ ] api/capabilities/capabilities_router.py - remove unused ignores
  - [ ] api/status_stream.py - remove unused ignores
  - [ ] Clean up after proper type fixes

- [ ] 6.3 Fix misc errors (parallel task)
  - [ ] api/watchlist.py - WatchlistItemResponse missing args
  - [ ] utils/health_service.py - Literal type mismatch
  - [ ] Any other remaining errors

- [ ] 6.4 Verify all remaining errors resolved
  ```bash
  mypy app/ --strict 2>&1 | wc -l
  # Expected: 0 errors
  ```

### 7.0 Add Missing Type Hints (Bonus - Parallel)

**Only if easily parallelizable with --max mode**

- [ ] 7.1 Scan for functions without return type hints
  ```bash
  grep -r "^def " app/ | grep -v " -> " | wc -l
  ```

- [ ] 7.2 Add return type hints to public APIs (parallel task)
  - [ ] api/ module - all route handlers
  - [ ] Focus on commonly used functions

- [ ] 7.3 Add parameter type hints where missing (parallel task)
  - [ ] storage/ module
  - [ ] services/ module

### 8.0 Reduce Any Types (Bonus - Parallel)

**Only if easily parallelizable with --max mode**

- [ ] 8.1 Find all Any usages
  ```bash
  grep -r "Any" app/ --include="*.py" | grep -v "# type: ignore" | wc -l
  ```

- [ ] 8.2 Convert Any to proper types (parallel task)
  - [ ] Focus on function signatures
  - [ ] Use generic types (TypeVar, Generic) where appropriate
  - [ ] Document where Any is genuinely needed

### 9.0 Final Verification & Cleanup

- [ ] 9.1 Run full mypy check
  ```bash
  cd ~/portfolio-ai/backend && source .venv/bin/activate
  mypy app/ --strict --config-file=pyproject.toml
  ```
  - [ ] Confirm: 0 errors
  - [ ] Capture: Final error count before/after comparison

- [ ] 9.2 Run all backend tests
  ```bash
  cd ~/portfolio-ai/backend && pytest tests/ -v --runslow
  ```
  - [ ] Confirm: All tests still passing
  - [ ] No regressions from type fixes

- [ ] 9.3 Run pre-commit hook (full)
  ```bash
  cd ~/portfolio-ai && pre-commit run --all-files
  ```
  - [ ] Confirm: mypy hook passes WITHOUT skip
  - [ ] Confirm: ruff format and ruff check pass

- [ ] 9.4 Update quality baseline
  ```bash
  bash ~/portfolio-ai/.claude/skills/code-quality/scripts/quality-report.sh backend/app --quick
  ```
  - [ ] Document new baseline (should be improved)
  - [ ] Verify: No new critical issues introduced

- [ ] 9.5 Test commit without SKIP=mypy
  ```bash
  cd ~/portfolio-ai
  git add -A
  git commit -m "test: verify mypy passes without skip"
  # Should complete without SKIP=mypy
  git reset HEAD~1  # Undo test commit
  ```

---

## Verification

- [ ] Functional: All 260 mypy errors resolved (mypy app/ --strict returns 0 errors)
- [ ] Tests: All 508+ tests passing with no regressions
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes (ruff + mypy both clean)
- [ ] Pre-commit: Commits work WITHOUT SKIP=mypy workaround
- [ ] Clean: Any types minimized, type hints comprehensive
- [ ] Docs: tasks/TASK-0060-MYPY-BLOCKER.md can be archived/removed

---

## Parallel Execution Strategy (--max mode)

**Phase 0: Discovery (Sequential)**
- Task 0.1-0.4: Categorize all errors → Creates systematic breakdown

**Phase 1: Core Fixes (6 Parallel Groups)**
- Group A (Task 1.0): union-attr errors → 4 parallel tasks (api/, watchlist/, tasks/, services/)
- Group B (Task 2.0): arg-type errors → 4 parallel tasks (storage/, watchlist/, tasks/, services/)
- Group C (Task 3.0): return-value errors → 4 parallel tasks (storage/, watchlist/, tasks/, services/)
- Group D (Task 4.0): list-item + operator → 2 parallel tasks
- Group E (Task 5.0): index + assignment → 2 parallel tasks
- Group F (Task 6.0): TypedDict + misc → 3 parallel tasks

**Phase 2: Enhancements (2 Parallel Groups - Optional)**
- Group G (Task 7.0): Add type hints → 2 parallel tasks
- Group H (Task 8.0): Reduce Any → 1 task

**Phase 3: Verification (Sequential)**
- Task 9.0: Final checks and quality verification

**Estimated Execution Time:**
- Without --max: 20-40 hours (sequential)
- With --max: 6-10 hours (aggressive parallelization)

**Key for Success:**
- Each module (api/, watchlist/, tasks/, services/, storage/) gets own subagent
- Error categories are independent (can fix simultaneously)
- Main agent orchestrates, verifies, integrates
