# Task List: Vision Gap Analysis & Remediation

**Source**: User request via /task_it (Gap Analysis)
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev
**Created**: 2025-11-29 17:20

---

## Summary

**Goal**: Bring the solution into full alignment with `docs/core/VISION.md` by addressing critical gaps in reliability, testing, and code quality.
**Approach**: Systematically fix data source failures, repair the test suite, and enforce code quality limits.
**Scope Discovery**: Completed via initial UI and Codebase review.

---

## Findings (Gap Analysis)

### 1. Reliability (CRITICAL)
- **Gap**: 12 Data Sources are DOWN, 1 Degraded.
- **Impact**: Dashboard data is stale (15 days old).
- **Vision Violation**: "Reliability Through Redundancy" (Objective: Zero downtime).
- **Remediation**: Fix data source configuration and freshness monitoring (Task 0073).

### 2. Test Health (CRITICAL)
- **Gap**: 11 `ModuleNotFoundError` errors during test collection in `tests/unit/sources/`.
- **Impact**: Cannot reliably verify changes.
- **Vision Violation**: "Developer Velocity & Code Quality" (Success Criteria: 100% pass rate).
- **Remediation**: Fix import paths in test modules.

### 3. Code Quality (MEDIUM)
- **Gap**: `backend/app/agents/llm_client.py` is 820 lines.
- **Vision Violation**: "Code Quality" (Success Criteria: 0 files >800 lines).
- **Remediation**: Split `llm_client.py` into smaller modules (e.g., `claude_client.py`, `gemini_client.py`).

### 4. User Experience (MEDIUM)
- **Gap**: "Plain Language" insights in Watchlist are generic ("WHY THIS WORKS").
- **Vision Violation**: "Accessibility Without Compromise" (Plain-language narratives).
- **Remediation**: Enhance insight generation templates.

---

## Tasks

### 1.0 Fix Data Source Reliability (Task 0073)

- [ ] 1.1 Resume and complete Task 0073 (Data Source Reliability & Freshness Guarantee)
  - [ ] Fix DataFrame.empty bug in `data_freshness_tasks.py`
  - [ ] Verify all 6 data sources are operational
  - [ ] Ensure Status page shows all Green

### 2.0 Fix Test Suite Collection Errors

- [ ] 2.1 Investigate `ModuleNotFoundError` in `tests/unit/sources/`
- [ ] 2.2 Fix import paths in affected test files
- [ ] 2.3 Verify `pytest --collect-only` returns 0 errors
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

- [ ] **Reliability**: Status page shows all Data Sources GREEN. Dashboard data is current (<24h).
- [ ] **Tests**: `pytest` runs with 0 collection errors and 100% pass rate.
- [ ] **Code Quality**: No files > 800 lines. `mypy --strict` passes.
- [ ] **UX**: Watchlist insights are specific and helpful.
