# Task List: Codebase Health Remediation

**Source**: Discovery via /do_it session 2025-11-30
**Complexity**: Medium
**Effort**: MEDIUM (4-6 hours)
**Environment**: Local Dev
**Created**: 2025-11-30 12:30
**Priority**: HIGH - Technical debt blocking CI/CD

---

## Summary

**Goal**: Fix all pytest failures, mypy errors, and ruff lint issues to achieve clean CI/CD pipeline
**Approach**: Systematic fix by category - tests first, then type errors, then lint
**Scope Discovery**: Complete - all issues catalogued below

---

## Current State (2025-11-30)

| Category | Count | Status |
|----------|-------|--------|
| Pytest failures | 17 | Blocking |
| Mypy errors | 29 | Blocking |
| Ruff lint issues | 41 | Warning |
| **Total** | **87** | |

---

## Tasks

### 1.0 Fix Pytest Failures (17 tests)

**1.1 CapabilityAnalyzer Tests (11 failures) - HIGHEST PRIORITY**

Tests expect attributes that no longer exist after refactoring:
- `cli_path` attribute missing
- `call_ai_api()` method missing
- `_find_claude_cli()` method missing

Files:
- [ ] `tests/unit/services/test_ai_analyzer.py` (4 failures)
- [ ] `tests/unit/services/test_ai_analyzer_cli.py` (7 failures)

Fix: Either restore missing attributes or update tests to match current implementation.

**1.2 Config Loader Tests (5 failures)**

Cache and validation logic broken:
- [ ] `test_load_config_success` - dict mismatch
- [ ] `test_load_config_missing_required_keys` - not raising ValueError
- [ ] `test_load_config_uses_cache` - cache not working
- [ ] `test_load_config_reloads_on_file_change` - file change detection broken
- [ ] `test_reload_clears_cache` - dict mismatch

File: `tests/unit/services/test_config_loader.py`

**1.3 Agent Tools Test (1 failure)**

- [ ] `test_execute_store_idea` - `assert 0.75 == 75.0`

Fix: Percentage stored as decimal (0.75) vs percentage (75.0)
File: `tests/unit/agents/test_agent_tools.py`

---

### 2.0 Fix Mypy Errors (29 errors)

**2.1 LLM Client Export Issues (5 errors)**

Module not explicitly exporting attributes:
- [ ] `app/agents/llm_client.py` - Add `__all__` with exports:
  - `ClaudeCLIClient`, `GeminiCLIClient`, `LLMClient`, `LLMResponse`

Files importing: `strategy_reviewer.py`, `base.py`, `strategy_generator.py`

**2.2 Strategy Reviewer Type Issues (4 errors)**

- [ ] `app/agents/strategy_reviewer.py:124-125` - `max_tokens`/`temperature` typed as `object`
- [ ] `app/agents/strategy_reviewer_prompts.py:62` - Missing dict type params
- [ ] `app/agents/strategy_reviewer_prompts.py:101,108` - Object not iterable

**2.3 Task Files Type Issues (9 errors)**

- [ ] `app/tasks/data_freshness_tasks.py:33` - `.df` attribute doesn't exist
- [ ] `app/tasks/workflow_tasks.py:323,325,327` - float vs object comparison
- [ ] `app/tasks/strategy_metrics_tasks.py:18,19,52,82,112,137,161` - decorator/type issues

**2.4 API Files Type Issues (4 errors)**

- [ ] `app/api/layouts.py:23,60,90` - Missing dict type params
- [ ] `app/api/watchlist.py:526` - Missing dict type params

**2.5 Other Type Issues (7 errors)**

- [ ] `app/strategies/optimizer.py:343` - ConnectionManager vs PortfolioStorage
- [ ] `app/services/news_cache.py:365` - execute() argument type
- [ ] `app/api/capabilities/capabilities_router.py:14` - celery import-untyped

---

### 3.0 Fix Ruff Lint Issues (41 issues)

**3.1 Whitespace Issues (12 issues) - AUTO-FIXABLE**

```bash
ruff check app/ --fix
```

- W291: Trailing whitespace (3)
- W292: No newline at EOF (1)
- W293: Blank line whitespace (8)

Files: `status_logs.py`, `narrative_generator.py`, `llm_client.py`, `base_client.py`

**3.2 Import Location Issues (5 issues)**

PLC0415 - imports not at top level:
- [ ] `app/agents/strategy_reviewer_prompts.py:98` - `import re`
- [ ] `app/api/layouts.py:63` - `import json`
- [ ] `app/tasks/data_freshness_tasks.py:109` - circular dep (OK to skip)
- [ ] `app/tasks/strategy_monitoring_tasks.py:274` - circular dep (OK to skip)
- [ ] `app/agents/tool_executors_trading.py:480` - lazy import (OK to skip)

**3.3 Code Quality Issues (6 issues)**

- [ ] `app/agents/tool_executors_trading.py:64,324` - F601 duplicate dict keys
- [ ] `app/api/layouts.py:68` - ERA001 commented code
- [ ] `app/agents/tool_executors_trading.py:409` - PLR0911 too many returns
- [ ] `app/tasks/data_freshness_tasks.py:28` - F841 unused variable

**3.4 Pattern Issues (11+ B905)**

- [ ] Multiple `zip()` calls missing `strict=` parameter
- Files: `health_check.py`, `storage.py`, `narrative_storage.py`, `news/storage.py`
- Action: Add `strict=False` or `strict=True` as appropriate

**3.5 Global Statement Issues (2 PLW0603)**

- [ ] `app/strategies/storage.py:463` - global _storage_instance
- [ ] `app/strategies/strategy_generator.py:316` - global _generator_instance
- Action: Consider refactoring to module-level singleton pattern

---

### 4.0 Fix Truncated File

- [x] `app/tasks/strategy_monitoring_tasks.py` - Restored from git (was truncated at line 316)

---

## Verification

- [ ] `pytest tests/ -q` - 0 failures (843 tests)
- [ ] `mypy app/ --strict` - 0 errors
- [ ] `ruff check app/` - 0 errors
- [ ] `~/portfolio-ai/scripts/lint.sh` - All passes

---

## Technical Notes

**Root Causes:**
1. CapabilityAnalyzer refactored but tests not updated
2. Config loader caching mechanism broken
3. LLM client module missing `__all__` exports
4. Type annotations incomplete in task files
5. strategy_monitoring_tasks.py was truncated (fixed)

**Priority Order:**
1. Fix truncated file (DONE)
2. Fix test failures (blocking CI)
3. Fix mypy errors (type safety)
4. Fix ruff issues (code quality)

---

## /check_it Findings (2025-11-30)

- 5 orphaned files (safety check - modified <24h ago)
- 1 HIGH: Task 0075 claims COMPLETE but 83%
- 3 MEDIUM: Stalled tasks (19 days, 0% progress) - consider archiving
