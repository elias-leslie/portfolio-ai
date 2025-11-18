# Task 0060 Task 3.7 - Mypy Pre-Commit Blocker

## Status
Task 3.7 implementation is **COMPLETE** but blocked on pre-commit mypy hook.

## Completed Work
- ✅ Updated `agent_tasks.py` to use DualProviderClient
- ✅ Created 7 comprehensive integration tests (all passing)
- ✅ Ruff: All checks passing
- ✅ No code quality regression (41/131/168 baseline maintained)
- ✅ My changes introduce **ZERO new mypy errors**

## Blocker
Pre-commit mypy hook runs on ALL files in `backend/app/` and fails with **260 pre-existing errors across 43 files**:
- 262 mypy errors total
- 43 files affected
- None caused by Task 3.7 changes
- All are pre-existing from previous work

## Files with Changes (Task 3.7)
1. `backend/app/tasks/agent_tasks.py` - ✅ No mypy errors
2. `backend/tests/integration/agents/test_agents_with_cli.py` - ✅ No mypy errors (new file)
3. `tasks/tasks-0060-cli-agent-integration.md` - Documentation only
4. `tasks/WORK_TRACKER.md` - Documentation only

## Evidence - No Regression
```bash
# Check only our changed files
cd backend && source .venv/bin/activate
mypy app/tasks/agent_tasks.py tests/integration/agents/test_agents_with_cli.py
# Result: Only shows pre-existing errors in IMPORTED modules, not our code
```

## Options

### Option A: Fix All 260 Pre-Existing Mypy Errors (NOT RECOMMENDED)
- **Scope**: Massive scope creep - 43 files, 260 errors
- **Effort**: HIGH (20-40 hours estimated)
- **Risk**: High risk of introducing bugs in unrelated code
- **Benefit**: Full mypy compliance
- **Recommendation**: ❌ This should be a separate task/PRD

### Option B: Temporarily Disable Mypy Hook for This Commit (PRAGMATIC)
- **Scope**: Task 3.7 only
- **Effort**: LOW (1 command)
- **Risk**: None - my changes are clean
- **Approach**:
  ```bash
  SKIP=mypy git commit -m "..."
  ```
- **Justification**: My code introduces zero new errors
- **Documentation**: Create Task 0070 for mypy cleanup
- **Recommendation**: ✅ Pragmatic given scope

### Option C: Modify Mypy Hook to Check Only Changed Files (IDEAL)
- **Scope**: Update pre-commit config
- **Effort**: MEDIUM (2-4 hours to test)
- **Risk**: Low - better CI/CD practice
- **Approach**:
  ```yaml
  - id: mypy
    pass_filenames: true  # Only check staged files
  ```
- **Recommendation**: ✅ Best long-term solution

## Recommendation
**Option B** for immediate unblocking, followed by creating **Task 0070: Fix All Pre-Existing Mypy Errors** for systematic cleanup.

## Task 0070 PRD (Proposed)
```markdown
# Task 0070: Fix All Pre-Existing Mypy Errors

**Goal**: Achieve full mypy --strict compliance across entire codebase

**Scope**:
- 260 mypy errors across 43 files
- Categories: union-attr, arg-type, return-value, list-item, operator
- Files: storage, watchlist, tasks, services, api, sources

**Approach**:
1. Group errors by category
2. Fix systematic patterns first (e.g., all union-attr issues)
3. Fix file-by-file for isolated errors
4. Add type hints where missing
5. Use type narrowing (isinstance checks)

**Estimated Effort**: HIGH (20-40 hours)
**Priority**: MEDIUM (code quality improvement)
**Blocking**: None (system functional, tests passing)
```

## Decision Needed
Should I:
1. Use `SKIP=mypy git commit ...` to unblock Task 3.7? (Pragmatic)
2. Start massive scope creep to fix all 260 errors? (Not recommended)
3. Modify mypy hook to only check changed files? (Ideal but requires testing)
