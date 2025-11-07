# Task List: Type System & Infrastructure Improvements

**PRD**: `tasks/0026-prd-type-system-infrastructure.md`
**Status**: Ready for Implementation
**Completion**: 0%
**Effort**: MEDIUM (6-8 hours over 2 sessions)
**Updated**: 2025-11-03

---

## Summary

**✅ COMPLETE:** (None)
**🔄 IN PROGRESS:** (Not started)
**⚠️ NEXT:** Task 1.0 - Type System: Define DatabaseConnection Protocol

---

## Relevant Files

### Create (3 files)
- `backend/app/storage/types.py` (~50 lines) - DatabaseConnection Protocol definition
- `scripts/validate-browser-automation.sh` (~80 lines) - Browser automation validation script
- `backend/tests/storage/test_database_protocol.py` (~100 lines) - Protocol tests

### Update (17 files)
**Type system updates (14 files):**
- `backend/app/storage/schema.py` - 2 `conn: Any` → DatabaseConnection
- `backend/app/storage/connection.py` - 1 `conn: Any` → DatabaseConnection
- `backend/app/watchlist/calculator.py` - 4 `conn: Any` → DatabaseConnection
- `backend/app/watchlist/news.py` - 1 `conn: Any` → DatabaseConnection
- `backend/app/watchlist/fundamentals.py` - 1 `conn: Any` → DatabaseConnection
- `backend/app/watchlist/earnings.py` - 1 `conn: Any` → DatabaseConnection
- `backend/app/storage/yaml_loader.py` - 2 `storage: Any` → PortfolioStorage
- `backend/app/tasks/agent_tasks.py` - 2 `storage: Any` → PortfolioStorage
- `backend/app/storage/__init__.py` - Export types

**Infrastructure updates (2 files):**
- `backend/app/celery_app.py` - Update result_expires to 30 days
- `docs/core/OPERATIONS.md` - Document Celery retention + cleanup query

**Documentation updates (1 file):**
- `CLAUDE.md` - Replace pre-commit section with link to DEVELOPMENT.md

### Notes
- Tests: `mypy backend/app/ --strict` should pass after type updates
- Quality: `pytest tests/` should maintain 100% pass rate
- No runtime behavior changes (pure type annotations)

---

## Tasks

### Phase 1: Type System (4-6 hours)

- [ ] 1.0 Type System: Define DatabaseConnection Protocol (1 hour, LOW)
  - [ ] 1.1 Create storage/types.py module (20 min)
    - [ ] 1.1.1 Create backend/app/storage/types.py file (5 min)
      - Add module docstring
      - Add imports: `from typing import Protocol, Any`
      - Add stub: `# DatabaseConnection Protocol will go here`
    - [ ] 1.1.2 Define DatabaseConnection Protocol (10 min)
      - Create Protocol class with methods:
        - `execute(query: str, params: list | None = None) -> Any`
        - `fetchdf() -> Any`
        - `pl() -> Any`
      - Add docstrings for each method
    - [ ] 1.1.3 Export from storage/__init__.py (5 min)
      - Add: `from app.storage.types import DatabaseConnection`
      - Add to `__all__` list

  - [ ] 1.2 Test Protocol definition (20 min)
    - [ ] 1.2.1 Create test file (10 min)
      - Create `backend/tests/storage/test_database_protocol.py`
      - Import DatabaseConnection Protocol
      - Create test: verify Protocol can be imported
    - [ ] 1.2.2 Test Protocol with mock object (10 min)
      - Create mock class implementing Protocol
      - Verify mypy accepts it
      - Test: `pytest tests/storage/test_database_protocol.py`

  - [ ] 1.3 Replace conn: Any in storage/ modules (20 min)
    - [ ] 1.3.1 Update storage/schema.py (10 min)
      - Line 92: `_apply_migrations(self, conn: DatabaseConnection) -> None`
      - Line 104: `_populate_registry_metadata(self, conn: DatabaseConnection) -> None`
      - Add import: `from app.storage.types import DatabaseConnection`
      - Run: `mypy backend/app/storage/schema.py --strict`
    - [ ] 1.3.2 Update storage/connection.py (10 min)
      - Line 38: `__init__(self, pg_conn: DatabaseConnection, engine: Any = None) -> None`
      - Add import: `from app.storage.types import DatabaseConnection`
      - Run: `mypy backend/app/storage/connection.py --strict`

- [ ] 2.0 Type System: Replace conn: Any in watchlist/ modules (2 hours, MEDIUM)
  - [ ] 2.1 Update watchlist/calculator.py (45 min)
    - [ ] 2.1.1 Add import (5 min)
      - Add: `from app.storage.types import DatabaseConnection`
    - [ ] 2.1.2 Update get_swing_low function (10 min)
      - Line 19: `def get_swing_low(conn: DatabaseConnection, symbol: str, days: int = 10) -> float | None:`
      - Run: `mypy backend/app/watchlist/calculator.py --strict`
      - Test: `pytest -k test_get_swing_low`
    - [ ] 2.1.3 Update get_swing_high function (10 min)
      - Line 57: `def get_swing_high(conn: DatabaseConnection, symbol: str, days: int = 30) -> float | None:`
      - Run mypy, test
    - [ ] 2.1.4 Update calculate_stop_loss function (10 min)
      - Line 119: `def calculate_stop_loss(conn: DatabaseConnection, symbol: str, entry_price: float) -> float | None:`
      - Run mypy, test
    - [ ] 2.1.5 Update calculate_profit_target function (10 min)
      - Line 170: `def calculate_profit_target(conn: DatabaseConnection, symbol: str, entry_price: float) -> float | None:`
      - Run mypy, test

  - [ ] 2.2 Update watchlist/news.py (20 min)
    - [ ] 2.2.1 Add import and update function (15 min)
      - Line 102: Update function signature with `conn: DatabaseConnection`
      - Add import: `from app.storage.types import DatabaseConnection`
      - Run: `mypy backend/app/watchlist/news.py --strict`
    - [ ] 2.2.2 Test news functions (5 min)
      - Run: `pytest backend/tests/watchlist/test_news.py -v`

  - [ ] 2.3 Update watchlist/fundamentals.py (20 min)
    - [ ] 2.3.1 Add import and update function (15 min)
      - Line 298: `def fetch_fundamentals_cached(conn: DatabaseConnection, symbol: str, ttl_days: int = 1) -> FundamentalData | None:`
      - Add import: `from app.storage.types import DatabaseConnection`
      - Run: `mypy backend/app/watchlist/fundamentals.py --strict`
    - [ ] 2.3.2 Test fundamentals functions (5 min)
      - Run: `pytest backend/tests/watchlist/test_fundamentals.py -v`

  - [ ] 2.4 Update watchlist/earnings.py (20 min)
    - [ ] 2.4.1 Add import and update function (15 min)
      - Line 128: `def fetch_earnings_date_cached(conn: DatabaseConnection, symbol: str, ttl_days: int = 30) -> datetime | None:`
      - Add import: `from app.storage.types import DatabaseConnection`
      - Run: `mypy backend/app/watchlist/earnings.py --strict`
    - [ ] 2.4.2 Test earnings functions (5 min)
      - Run: `pytest backend/tests/watchlist/test_earnings.py -v`

  - [ ] 2.5 Verify all conn: Any replaced (15 min)
    - [ ] 2.5.1 Search for remaining conn: Any (5 min)
      - Run: `grep -rn "conn: Any" backend/app/`
      - Should return: no matches
    - [ ] 2.5.2 Run mypy on all updated files (5 min)
      - `mypy backend/app/storage/ backend/app/watchlist/ --strict`
      - Should pass with no errors
    - [ ] 2.5.3 Run tests on all updated modules (5 min)
      - `pytest backend/tests/storage/ backend/tests/watchlist/ -v`
      - All should pass

- [ ] 3.0 Type System: Replace storage: Any (1 hour, LOW)
  - [ ] 3.1 Update storage/yaml_loader.py (20 min)
    - [ ] 3.1.1 Add import (5 min)
      - Add: `from app.storage.connection import PortfolioStorage`
    - [ ] 3.1.2 Update insert_source_to_db function (7 min)
      - Line 67: `def insert_source_to_db(source_config: dict[str, Any], storage: PortfolioStorage) -> None:`
      - Run: `mypy backend/app/storage/yaml_loader.py --strict`
    - [ ] 3.1.3 Update load_all_sources function (8 min)
      - Line 155: `def load_all_sources(storage: PortfolioStorage, sources_dir: str = "config/sources") -> None:`
      - Run mypy, test

  - [ ] 3.2 Update tasks/agent_tasks.py (20 min)
    - [ ] 3.2.1 Add import (5 min)
      - Add: `from app.storage.connection import PortfolioStorage`
    - [ ] 3.2.2 Update _setup_agent_tools function (7 min)
      - Line 39: `def _setup_agent_tools(storage: PortfolioStorage) -> AgentTools:`
      - Run: `mypy backend/app/tasks/agent_tasks.py --strict`
    - [ ] 3.2.3 Update _update_celery_task_id function (8 min)
      - Line 64: `def _update_celery_task_id(storage: PortfolioStorage, task_id: str, run_id: str) -> None:`
      - Run mypy, test

  - [ ] 3.3 Verify all storage: Any replaced (20 min)
    - [ ] 3.3.1 Search for remaining storage: Any (5 min)
      - Run: `grep -rn "storage: Any" backend/app/`
      - Should return: no matches
    - [ ] 3.3.2 Run mypy on entire codebase (10 min)
      - `mypy backend/app/ --strict`
      - Should pass with no errors
    - [ ] 3.3.3 Run full test suite (5 min)
      - `cd backend && source .venv/bin/activate && pytest tests/ -v`
      - All tests should pass

  - [ ] 3.4 Verify IDE autocomplete works (10 min)
    - [ ] 3.4.1 Test IDE with DatabaseConnection (5 min)
      - Open file using conn parameter
      - Type `conn.` and verify autocomplete shows execute, fetchdf, pl
    - [ ] 3.4.2 Test IDE with PortfolioStorage (5 min)
      - Open file using storage parameter
      - Verify autocomplete shows PortfolioStorage methods

---

### Phase 2: Infrastructure & Documentation (2 hours)

- [ ] 4.0 Infrastructure: Configure Celery Result Retention (30 min, LOW)
  - [ ] 4.1 Update celery_app.py configuration (10 min)
    - [ ] 4.1.1 Update result_expires setting (5 min)
      - Line 42: Change `result_expires=3600` to `result_expires=60*60*24*30`
      - Add comment: `# Results expire after 30 days`
      - Current: 1 hour (3600 seconds)
      - New: 30 days (2,592,000 seconds)
    - [ ] 4.1.2 Verify configuration loads (5 min)
      - Run: `python -c "from app.celery_app import celery_app; print(celery_app.conf.result_expires)"`
      - Should output: 2592000

  - [ ] 4.2 Restart Celery services (10 min)
    - [ ] 4.2.1 Restart backend services (5 min)
      - Run: `bash ~/portfolio-ai/scripts/restart.sh`
      - Wait for services to start
    - [ ] 4.2.2 Verify Celery workers running (5 min)
      - Run: `bash ~/portfolio-ai/scripts/status.sh`
      - Verify celery-worker and celery-beat are running

  - [ ] 4.3 Document retention policy in OPERATIONS.md (10 min)
    - [ ] 4.3.1 Add Celery retention section (8 min)
      - Add section: "### Celery Task Result Retention"
      - Document: "Results auto-expire after 30 days (configured in celery_app.py)"
      - Add manual cleanup query:
        ```sql
        -- Manual cleanup if needed (rarely necessary)
        DELETE FROM celery_taskmeta
        WHERE date_done < NOW() - INTERVAL '30 days';
        ```
    - [ ] 4.3.2 Verify documentation clarity (2 min)
      - Re-read section
      - Ensure operators understand retention policy

- [ ] 5.0 Tooling: Validate Browser Automation Scripts (1 hour, LOW)
  - [ ] 5.1 Create validation script (30 min)
    - [ ] 5.1.1 Create scripts/validate-browser-automation.sh (20 min)
      - Add shebang and header
      - Define SKILL_DIR variable
      - Check directory exists
      - Define array of 10 required scripts:
        - screenshot.js, snapshot.js, console.js, network.js, interact.js
        - execute.js, manage.js, emulate.js, performance.js, expand-and-screenshot.js
      - Loop through scripts, check existence and executable bit
      - Print status for each script (✅ or ❌)
      - Exit with code 1 if any missing
    - [ ] 5.1.2 Make script executable (5 min)
      - Run: `chmod +x ~/portfolio-ai/scripts/validate-browser-automation.sh`
    - [ ] 5.1.3 Test validation script (5 min)
      - Run: `bash ~/portfolio-ai/scripts/validate-browser-automation.sh`
      - Should output: ✅ for all 10 scripts
      - Current status: All 10 scripts exist (verified)

  - [ ] 5.2 Update documentation to reference validation (20 min)
    - [ ] 5.2.1 Update SETUP.md (10 min)
      - Add section: "### Verify Browser Automation"
      - Add command: `bash ~/portfolio-ai/scripts/validate-browser-automation.sh`
      - Add note: "Required for UI testing and automation"
    - [ ] 5.2.2 Update .claude/commands/do_it.md (10 min)
      - Find browser automation section
      - Add: "Before using browser automation: Run `bash ~/portfolio-ai/scripts/validate-browser-automation.sh`"
      - Add: "If fails: Install from project .claude/skills/browser-automation/"

  - [ ] 5.3 Test browser automation end-to-end (10 min)
    - [ ] 5.3.1 Test screenshot script (5 min)
      - Run: `node ~/.claude/skills/browser-automation/scripts/screenshot.js http://192.168.8.233:3000 /tmp/test-screenshot.png`
      - Verify /tmp/test-screenshot.png created
      - Open and verify it's a valid screenshot
    - [ ] 5.3.2 Test snapshot script (5 min)
      - Run: `node ~/.claude/skills/browser-automation/scripts/snapshot.js http://192.168.8.233:3000 /tmp/test-snapshot.json`
      - Verify JSON file created
      - Verify contains page structure

- [ ] 6.0 Documentation: Consolidate Pre-Commit Documentation (30 min, LOW)
  - [ ] 6.1 Verify DEVELOPMENT.md has complete pre-commit docs (10 min)
    - [ ] 6.1.1 Read DEVELOPMENT.md pre-commit section (5 min)
      - Verify comprehensive pre-commit checklist exists
      - Should include: ruff, mypy, pytest, file size checks
    - [ ] 6.1.2 Identify any gaps (5 min)
      - Compare with CLAUDE.md version
      - Ensure DEVELOPMENT.md is complete

  - [ ] 6.2 Update CLAUDE.md to link to DEVELOPMENT.md (15 min)
    - [ ] 6.2.1 Replace pre-commit workflow section (10 min)
      - Find lines 188-195 (pre-commit workflow)
      - Replace with:
        ```markdown
        - **Pre-commit workflow**: See [DEVELOPMENT.md - Pre-Commit Checklist](docs/core/DEVELOPMENT.md#pre-commit-checklist)
          - Quick: `~/portfolio-ai/scripts/lint.sh` (runs all checks)
          - Tests: `cd ~/portfolio-ai/backend && pytest tests/`
          - Hooks run automatically on commit
        ```
      - Remove duplicate steps (lines 189-194)
    - [ ] 6.2.2 Update line 125 reference (5 min)
      - Line 125 already says "see [DEVELOPMENT.md]"
      - Verify link format is correct
      - Ensure consistency

  - [ ] 6.3 Verify no duplication remains (5 min)
    - [ ] 6.3.1 Check for duplicate content (3 min)
      - Read both CLAUDE.md and DEVELOPMENT.md pre-commit sections
      - Confirm CLAUDE.md only has link + quick reference
      - Confirm DEVELOPMENT.md has full details
    - [ ] 6.3.2 Test link (2 min)
      - Verify link format: `[DEVELOPMENT.md - Pre-Commit Checklist](docs/core/DEVELOPMENT.md#pre-commit-checklist)`
      - Should work in GitHub markdown viewer

---

## Verification (MANDATORY before "COMPLETE ✅")

- [ ] **Functional**: All requirements met
  - [ ] DatabaseConnection Protocol defined and exported
  - [ ] All 10 `conn: Any` replaced with DatabaseConnection
  - [ ] All 4 `storage: Any` replaced with PortfolioStorage
  - [ ] Celery result_expires set to 30 days
  - [ ] Browser automation validation script created
  - [ ] All 10 browser scripts validated
  - [ ] Pre-commit docs consolidated
- [ ] **Tests**: All passing
  - [ ] `pytest backend/tests/ -v` - ALL PASS
  - [ ] No test regressions
  - [ ] Coverage maintained (≥85%)
- [ ] **Quality**: Type checking passes
  - [ ] `mypy backend/app/ --strict` - PASS
  - [ ] `ruff check backend/app/` - PASS
  - [ ] `bash ~/portfolio-ai/scripts/lint.sh` - PASS
  - [ ] IDE autocomplete works for DatabaseConnection and PortfolioStorage
- [ ] **Clean**: No regressions
  - [ ] No `conn: Any` instances remain
  - [ ] No `storage: Any` instances remain
  - [ ] No runtime behavior changes
  - [ ] No new `Any` types introduced
- [ ] **Docs**: Updated accurately
  - [ ] OPERATIONS.md has Celery retention documentation
  - [ ] SETUP.md references browser automation validation
  - [ ] do_it.md references validation before use
  - [ ] CLAUDE.md links to DEVELOPMENT.md (no duplication)
- [ ] **Security**: No issues
  - [ ] No credentials in code
  - [ ] Type safety improved (fewer Any types)
- [ ] **Ops**: Services healthy
  - [ ] Celery workers/beat running
  - [ ] Browser automation scripts work
  - [ ] Services restart successfully

---

## Notes

### Type System Changes Summary

**Before:**
- 10 instances of `conn: Any` (no IDE support, no type safety)
- 4 instances of `storage: Any`
- Total: 14 `Any` types masking duck-typed interfaces

**After:**
- 0 instances of `conn: Any` (replaced with DatabaseConnection Protocol)
- 0 instances of `storage: Any` (replaced with PortfolioStorage)
- IDE autocomplete fully functional
- mypy can verify correct usage

**Files Updated:**
1. storage/schema.py (2 instances)
2. storage/connection.py (1 instance)
3. watchlist/calculator.py (4 instances)
4. watchlist/news.py (1 instance)
5. watchlist/fundamentals.py (1 instance)
6. watchlist/earnings.py (1 instance)
7. storage/yaml_loader.py (2 instances)
8. tasks/agent_tasks.py (2 instances)

### Protocol Pattern Benefits

Using `Protocol` (structural typing) instead of abstract base class:
- ✅ No inheritance required (duck typing preserved)
- ✅ Backward compatible (existing code works)
- ✅ IDE autocomplete enabled
- ✅ mypy type checking enabled
- ✅ No runtime overhead (type checking only)

### Celery Retention Change

**Current:** `result_expires=3600` (1 hour)
**New:** `result_expires=60*60*24*30` (30 days, 2,592,000 seconds)

**Impact:**
- Prevents unbounded growth of celery_taskmeta table
- Current size: 6.5 MB (will stabilize after 30 days)
- Auto-cleanup: Celery handles expiration automatically
- Manual cleanup: Rarely needed (query provided in OPERATIONS.md)

### Browser Automation Validation

**Current state:** All 10 scripts exist and work
**Issue:** No validation prevents runtime failures if scripts missing
**Solution:** Validation script that checks before use

**Scripts validated:**
1. screenshot.js - Take screenshots
2. snapshot.js - Get page structure
3. console.js - Capture console messages
4. network.js - Monitor network requests
5. interact.js - Page interactions
6. execute.js - Run JavaScript
7. manage.js - Multi-page management
8. emulate.js - Device/network emulation
9. performance.js - Performance tracing
10. expand-and-screenshot.js - Composite script

### Documentation Consolidation

**Problem:** Pre-commit workflow duplicated in CLAUDE.md and DEVELOPMENT.md
**Solution:** DEVELOPMENT.md is canonical source, CLAUDE.md links to it

**Rationale:**
- Single source of truth (DEVELOPMENT.md)
- Reduces maintenance burden
- Prevents conflicting instructions
- CLAUDE.md remains useful (quick reference + link)

### Success Criteria

✅ All 14 `Any` types replaced with proper types
✅ mypy --strict passes
✅ IDE autocomplete works
✅ Celery result retention configured (30 days)
✅ Browser automation validated
✅ Pre-commit docs consolidated
✅ All tests pass
✅ No runtime behavior changes

### Estimated Time Breakdown

| Task | Effort | Complexity |
|------|--------|------------|
| Define DatabaseConnection Protocol | 1 hour | LOW |
| Replace 10 conn: Any instances | 2 hours | MEDIUM |
| Replace 4 storage: Any instances | 1 hour | LOW |
| Configure Celery retention | 30 min | LOW |
| Create browser validation script | 30 min | LOW |
| Validate browser scripts | 30 min | LOW |
| Update documentation | 1 hour | LOW |
| Testing & verification | 30 min | LOW |
| **TOTAL** | **6.5-8 hours** | **MEDIUM** |

**Recommended execution:** 2 sessions
- Session 1: Type system (Phase 1) - 4-6 hours
- Session 2: Infrastructure + docs (Phase 2) - 2 hours

---

## Execution Notes for /do_it

- **No behavior changes** - Pure type annotations + config updates
- **Type safety focused** - All changes improve static analysis
- **Autonomous friendly** - All tasks clearly defined
- **Test after each module** - Run mypy + pytest incrementally
- **Commit frequently** - After each major module update
- **Zero risk** - Type annotations don't affect runtime
- **High value** - IDE support + type safety dramatically improved
