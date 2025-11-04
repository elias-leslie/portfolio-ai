# Task List: Fix Mypy Errors & Rename legacy database Legacy References

**Status**: Ready for Implementation
**Completion**: 0%
**Effort**: MEDIUM (3-4 hours)
**Created**: 2025-11-03
**Type**: Standalone cleanup task

---

## Summary

**✅ COMPLETE:** (None)
**🔄 IN PROGRESS:** (Not started)
**⚠️ NEXT:** Task 1.0 - Fix mypy import errors in news.py

**Scope:**
1. Fix ALL mypy errors (5 errors total):
   - news.py: 2 `import-untyped` errors (feedparser, vaderSentiment)
   - news.py: 2 `unused-ignore` errors (wrong ignore type)
   - scoring_service.py: 1 `no-untyped-call` error (redis.from_url)
2. Rename legacy databaseStorage → PortfolioStorage throughout codebase (20 files)
3. Update all documentation references to PostgreSQL

---

## Relevant Files

### Update (22+ files)

**Python files with legacy databaseStorage (20 files):**
- `backend/app/storage/facade.py` - Class definition
- `backend/app/storage/__init__.py` - Export
- `backend/app/watchlist/watchlist_service.py` - Type hints
- `backend/app/watchlist/scoring_service.py` - Type hints
- `backend/app/watchlist/snapshot_service.py` - Type hints
- `backend/app/tasks/agent_tasks.py` - Type hints
- `backend/app/tasks/watchlist_tasks.py` - Type hints
- `backend/app/tasks/data_ingestion_tasks.py` - Type hints
- `backend/app/tasks/indicator_tasks.py` - Type hints
- `backend/app/storage/yaml_loader.py` - Type hints
- `backend/app/api/*.py` - Multiple files
- `backend/app/agents/*.py` - Multiple files
- `backend/app/portfolio/*.py` - Multiple files
- `backend/tests/**/*.py` - Test files

**Python files with mypy errors (ALL will be fixed):**
- `backend/app/watchlist/news.py` - Fix import type hints (4 errors)
- `backend/app/watchlist/scoring_service.py` - Fix redis.from_url type hint (1 error)

**Documentation (5+ files):**
- `CLAUDE.md` - References to legacy database
- `README.md` - Architecture descriptions
- `docs/core/ARCHITECTURE.md` - System design
- `docs/core/SETUP.md` - Installation instructions
- `docs/core/DEVELOPMENT.md` - Development workflows

### Notes
- Tests: `pytest tests/ -v` (all 490 tests should pass)
- Quality: `mypy backend/app/ --strict` (should pass without import-untyped errors)
- Lint: `bash ~/portfolio-ai/scripts/lint.sh`

---

## Tasks

### Phase 1: Fix ALL Mypy Errors (45 minutes)

- [ ] 1.0 Fix mypy import-untyped errors in news.py (20 min, LOW)
  - [ ] 1.1 Update feedparser import (8 min)
    - [ ] 1.1.1 Read backend/app/watchlist/news.py line 13
    - [ ] 1.1.2 Change `# type: ignore[import-not-found]` to `# type: ignore[import-untyped]`
    - [ ] 1.1.3 Verify mypy accepts the change
    - Run: `mypy backend/app/watchlist/news.py --strict`

  - [ ] 1.2 Update vaderSentiment import (8 min)
    - [ ] 1.2.1 Read backend/app/watchlist/news.py line 15
    - [ ] 1.2.2 Change `# type: ignore[import-not-found]` to `# type: ignore[import-untyped]`
    - [ ] 1.2.3 Verify mypy accepts the change
    - Run: `mypy backend/app/watchlist/news.py --strict`

  - [ ] 1.3 Run tests to ensure no breakage (4 min)
    - Run: `cd backend && pytest tests/watchlist/test_news.py -v`

- [ ] 1.4 Fix mypy no-untyped-call error in scoring_service.py (20 min, LOW)
  - [ ] 1.4.1 Read backend/app/watchlist/scoring_service.py line 62
    - Current: `_redis_client = redis.from_url(REDIS_URL, decode_responses=True)`
    - Error: Call to untyped function "from_url" in typed context
  - [ ] 1.4.2 Add type ignore comment for untyped redis call
    - Change to: `_redis_client = redis.from_url(REDIS_URL, decode_responses=True)  # type: ignore[no-untyped-call]`
  - [ ] 1.4.3 Verify mypy accepts the change
    - Run: `mypy backend/app/watchlist/scoring_service.py --strict`
  - [ ] 1.4.4 Run tests to ensure no breakage
    - Run: `cd backend && pytest tests/watchlist/test_scoring.py -v`

- [ ] 1.5 Final verification - ALL mypy errors resolved (5 min)
  - [ ] 1.5.1 Run mypy on entire codebase
    - Run: `mypy backend/app/ --strict`
    - Expected: SUCCESS - no errors remaining
  - [ ] 1.5.2 Verify error count is zero
    - Run: `mypy backend/app/ --strict 2>&1 | grep "error:" | wc -l`
    - Expected: 0

---

### Phase 2: Rename legacy databaseStorage → PortfolioStorage (2-3 hours)

- [ ] 2.0 Update core storage module (30 min, MEDIUM)
  - [ ] 2.1 Rename class in facade.py (15 min)
    - [ ] 2.1.1 Read backend/app/storage/facade.py
    - [ ] 2.1.2 Rename `class legacy databaseStorage:` → `class PortfolioStorage:`
    - [ ] 2.1.3 Update docstring: "legacy database storage facade" → "Portfolio storage facade"
    - [ ] 2.1.4 Keep backward compat alias: `legacy databaseStorage = PortfolioStorage  # Deprecated`

  - [ ] 2.2 Update storage/__init__.py exports (10 min)
    - [ ] 2.2.1 Export PortfolioStorage as primary
    - [ ] 2.2.2 Keep legacy databaseStorage alias for backward compat
    - [ ] 2.2.3 Update __all__ list

  - [ ] 2.3 Verify storage module works (5 min)
    - Run: `python -c "from app.storage import PortfolioStorage, legacy databaseStorage; print('OK')"`
    - Both imports should work (alias)

- [ ] 3.0 Update watchlist modules (45 min, MEDIUM)
  - [ ] 3.1 Update watchlist_service.py (15 min)
    - [ ] 3.1.1 Replace all `legacy databaseStorage` → `PortfolioStorage` (8 instances)
    - [ ] 3.1.2 Update import: `from ..storage import PortfolioStorage`
    - Run: `mypy backend/app/watchlist/watchlist_service.py --strict`

  - [ ] 3.2 Update scoring_service.py (15 min)
    - [ ] 3.2.1 Replace all `legacy databaseStorage` → `PortfolioStorage` (10 instances)
    - [ ] 3.2.2 Update import: `from ..storage import PortfolioStorage`
    - Run: `mypy backend/app/watchlist/scoring_service.py --strict`

  - [ ] 3.3 Update snapshot_service.py (15 min)
    - [ ] 3.3.1 Replace all `legacy databaseStorage` → `PortfolioStorage`
    - [ ] 3.3.2 Update import
    - Run: `mypy backend/app/watchlist/snapshot_service.py --strict`

- [ ] 4.0 Update task modules (30 min, MEDIUM)
  - [ ] 4.1 Update tasks/agent_tasks.py (10 min)
    - [ ] 4.1.1 Replace `legacy databaseStorage` → `PortfolioStorage` in TYPE_CHECKING import
    - [ ] 4.1.2 Update function type hints (2 functions)
    - Run: `mypy backend/app/tasks/agent_tasks.py --strict`

  - [ ] 4.2 Update tasks/watchlist_tasks.py (10 min)
    - [ ] 4.2.1 Replace all `legacy databaseStorage` → `PortfolioStorage`
    - Run: `mypy backend/app/tasks/watchlist_tasks.py --strict`

  - [ ] 4.3 Update remaining task files (10 min)
    - [ ] 4.3.1 Update tasks/data_ingestion_tasks.py
    - [ ] 4.3.2 Update tasks/indicator_tasks.py
    - Run: `mypy backend/app/tasks/ --strict`

- [ ] 5.0 Update yaml_loader and remaining modules (30 min, MEDIUM)
  - [ ] 5.1 Update storage/yaml_loader.py (10 min)
    - [ ] 5.1.1 Update TYPE_CHECKING import: `from .facade import PortfolioStorage`
    - [ ] 5.1.2 Update function type hints (2 functions)
    - Run: `mypy backend/app/storage/yaml_loader.py --strict`

  - [ ] 5.2 Find and update remaining app files (20 min)
    - [ ] 5.2.1 Search for remaining legacy databaseStorage in app/
    - Run: `grep -rn "legacy databaseStorage" backend/app --include="*.py"`
    - [ ] 5.2.2 Update each file found (api, agents, portfolio modules)
    - [ ] 5.2.3 Verify mypy on each file
    - Run: `mypy backend/app/ --strict`

---

### Phase 3: Update Documentation (30 minutes)

- [ ] 6.0 Update documentation references (30 min, LOW)
  - [ ] 6.1 Update CLAUDE.md (10 min)
    - [ ] 6.1.1 Search for "legacy database" references
    - [ ] 6.1.2 Replace with "PostgreSQL" or "PortfolioStorage"
    - [ ] 6.1.3 Update database description (line ~90+)

  - [ ] 6.2 Update core documentation (15 min)
    - [ ] 6.2.1 Update docs/core/ARCHITECTURE.md
      - Replace "legacy database" → "PostgreSQL"
      - Update storage layer description
    - [ ] 6.2.2 Update docs/core/SETUP.md
      - Fix any legacy database installation references
      - Ensure PostgreSQL is primary
    - [ ] 6.2.3 Update docs/core/DEVELOPMENT.md
      - Update storage class name references

  - [ ] 6.3 Update README.md (5 min)
    - [ ] 6.3.1 Replace "legacy database" → "PostgreSQL" in tech stack
    - [ ] 6.3.2 Update architecture overview

---

### Phase 4: Final Verification (30 minutes)

- [ ] 7.0 Run comprehensive verification (30 min, MEDIUM)
  - [ ] 7.1 Run all tests (15 min)
    - [ ] 7.1.1 Run full test suite
    - Run: `cd backend && source .venv/bin/activate && pytest tests/ -v`
    - Expected: All 490 tests passing

  - [ ] 7.2 Run type checking (10 min)
    - [ ] 7.2.1 Run mypy on entire codebase
    - Run: `mypy backend/app/ --strict`
    - Expected: Pass (only scoring_service.py from_url remains)
    - [ ] 7.2.2 Verify news.py errors resolved
    - Should see NO import-untyped errors for feedparser/vaderSentiment

  - [ ] 7.3 Run linting and quality checks (5 min)
    - [ ] 7.3.1 Run ruff
    - Run: `cd backend && ruff check app/ tests/`
    - [ ] 7.3.2 Run lint script
    - Run: `bash ~/portfolio-ai/scripts/lint.sh`

  - [ ] 7.4 Search for remaining legacy database references (5 min)
    - [ ] 7.4.1 Search Python files
    - Run: `grep -rn "legacy database" backend/app --include="*.py" | grep -v "Deprecated"`
    - Expected: Only deprecation aliases
    - [ ] 7.4.2 Check if backward compat works
    - Run: `python -c "from app.storage import legacy databaseStorage; print('Alias works')"`

---

## Verification (MANDATORY before "COMPLETE ✅")

- [ ] **Functional**: All code works identically
  - [ ] PortfolioStorage class works as before
  - [ ] legacy databaseStorage alias provides backward compatibility
  - [ ] No runtime behavior changes
- [ ] **Tests**: 100% passing
  - [ ] `pytest backend/tests/ -v` - ALL 490 PASS
  - [ ] No test regressions
- [ ] **Quality**: Type checking 100% clean
  - [ ] `mypy backend/app/ --strict` - PASS (ZERO errors)
  - [ ] news.py ALL 4 errors RESOLVED
  - [ ] scoring_service.py error RESOLVED
  - [ ] NO mypy errors remaining in entire codebase
  - [ ] `bash ~/portfolio-ai/scripts/lint.sh` - PASS
- [ ] **Clean**: No legacy database references except deprecation
  - [ ] No legacy database in active code (only backward compat alias)
  - [ ] Documentation reflects PostgreSQL
  - [ ] Class name reflects purpose (PortfolioStorage)
- [ ] **Docs**: Accurate and up-to-date
  - [ ] ARCHITECTURE.md reflects PostgreSQL
  - [ ] CLAUDE.md has no legacy database references (except history)
  - [ ] README.md tech stack correct

---

## Notes

### Mypy Errors - Complete List (ALL will be fixed)

**Total: 5 errors across 2 files**

**news.py (4 errors):**
```
app/watchlist/news.py:13: error: Unused "type: ignore" comment  [unused-ignore]
app/watchlist/news.py:13: error: Skipping analyzing "feedparser": module is installed, but missing library stubs or py.typed marker  [import-untyped]
app/watchlist/news.py:15: error: Unused "type: ignore" comment  [unused-ignore]
app/watchlist/news.py:15: error: Skipping analyzing "vaderSentiment.vaderSentiment": module is installed, but missing library stubs or py.typed marker  [import-untyped]
```
- **Root cause:** Wrong ignore comment type
- **Fix:** Change `# type: ignore[import-not-found]` → `# type: ignore[import-untyped]`

**scoring_service.py (1 error):**
```
app/watchlist/scoring_service.py:62: error: Call to untyped function "from_url" in typed context  [no-untyped-call]
```
- **Root cause:** redis.from_url() lacks type stubs
- **Fix:** Add `# type: ignore[no-untyped-call]` to line 62

### legacy database → PortfolioStorage Rename Rationale

**Why rename:**
- ✅ Migrated from legacy database to PostgreSQL (completed)
- ✅ "legacy databaseStorage" is misleading (uses PostgreSQL now)
- ✅ "PortfolioStorage" is accurate and clear
- ✅ Reflects actual purpose (portfolio data storage)

**Backward compatibility:**
- Keep `legacy databaseStorage = PortfolioStorage` alias
- Mark as deprecated with comment
- Remove alias in future major version

**Scope: 20 Python files found with legacy databaseStorage references**

### Success Criteria

✅ ALL 5 mypy errors RESOLVED (ZERO errors remaining)
✅ news.py: 4 errors fixed (import-untyped + unused-ignore)
✅ scoring_service.py: 1 error fixed (no-untyped-call)
✅ All 490 tests passing
✅ mypy --strict passes with ZERO errors
✅ legacy databaseStorage → PortfolioStorage renamed throughout (20 files)
✅ Backward compat alias works
✅ Documentation reflects PostgreSQL

---

## Execution Notes for /do_it

- **Low risk** - Type annotations and naming only
- **Backward compatible** - Alias preserves existing code
- **Systematic** - Fix in order: core → modules → docs
- **Test frequently** - Run mypy after each file
- **Commit per phase** - Phase 1, Phase 2, Phase 3 separately
