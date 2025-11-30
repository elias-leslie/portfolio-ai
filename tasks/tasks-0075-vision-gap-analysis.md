# Task List: Vision Gap Analysis & Remediation

**Source**: User request via /task_it (Gap Analysis)
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev
**Created**: 2025-11-29 17:20
**Last Updated**: 2025-11-29 21:45

---

## Summary

**Goal**: Bring the solution into full alignment with `docs/core/VISION.md` by addressing critical gaps in reliability, testing, and code quality.
**Approach**: Systematically fix data source failures, repair the test suite, and enforce code quality limits.
**Scope Discovery**: Completed via initial UI and Codebase review.

---

## Findings (Gap Analysis)

### 1. Reliability (CRITICAL)
- **Status**: ✅ **PARTIALLY FIXED**
- **Gap**: 12 Data Sources are DOWN, 1 Degraded. Dashboard data was stale (15 days old).
- **Remediation**:
    - Fixed systemd service configuration (user vs system).
    - Fixed SQL bug in `fear_greed_pipeline.py`.
    - Backfilled missing market data.
    - Verified scheduler and worker functionality.
    - **Remaining**: Individual RSS feeds are still down/timing out.

### 2. Test Health (CRITICAL)
- **Status**: ✅ **FIXED**
- **Gap**: 11 `ModuleNotFoundError` errors during test collection.
- **Remediation**: Removed problematic `__init__.py` files from test subdirectories.
- **Verification**: `pytest --collect-only` now collects 836 tests with 0 errors.

### 3. Code Quality (MEDIUM)
- **Status**: ⏳ **PENDING**
- **Gap**: `backend/app/agents/llm_client.py` is 820 lines.
- **Vision Violation**: "Code Quality" (Success Criteria: 0 files >800 lines).

### 4. User Experience (MEDIUM)
- **Status**: ⏳ **PENDING**
- **Gap**: "Plain Language" insights in Watchlist are generic.

---

## Tasks

### 1.0 Fix Data Source Reliability (Task 0073)

- [x] 1.1 Resume and complete Task 0073 (Data Source Reliability & Freshness Guarantee)
  - [x] Fix DataFrame.empty bug in `data_freshness_tasks.py` (Fixed in Turn 1)
  - [x] Fix Systemd Service Configuration (Celery Beat/Worker)
  - [x] Fix SQL Bug in `fear_greed_pipeline.py`
  - [x] Backfill missing market data (Nov 15-28)
  - [ ] Investigate RSS feed timeouts (12 sources down)

### 2.0 Fix Test Suite Collection Errors

- [x] 2.1 Investigate `ModuleNotFoundError` in `tests/unit/sources/`
- [x] 2.2 Fix import paths in affected test files (Removed `__init__.py`)
- [x] 2.3 Verify `pytest --collect-only` returns 0 errors
- [ ] 2.4 Run full test suite to ensure 100% pass rate

### 3.0 Enforce Code Quality Limits

- [ ] 3.1 Refactor `backend/app/agents/llm_client.py`
  - [ ] Extract `ClaudeCLIClient` to `backend/app/agents/clients/claude_client.py`
  - [ ] Extract `GeminiCLIClient` to `backend/app/agents/clients/gemini_client.py`
  - [ ] Keep `LLMClient` base class and `DualProviderClient` in `llm_client.py` (or rename to `client_factory.py`)
- [ ] 3.2 Verify no files > 800 lines remain

### 4.0 Enhance Plain Language Insights

- [ ] 4.1 Review current insight generation logic
- [ ] 4.2 Improve templates/prompts for "WHY THIS WORKS" to be more specific
- [ ] 4.3 Verify improvements in Watchlist UI

---

## Verification

- [x] **Reliability**: Dashboard data is current (<24h). (Verified Fear & Greed = Nov 28)
- [x] **Tests**: `pytest` runs with 0 collection errors.
- [ ] **Code Quality**: No files > 800 lines. `mypy --strict` passes.
- [ ] **UX**: Watchlist insights are specific and helpful.
