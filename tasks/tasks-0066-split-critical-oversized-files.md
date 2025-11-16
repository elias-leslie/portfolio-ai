<!-- PAUSED: 2025-11-16 12:00 | Context: 70% | Reason: User request | Next: Task 0.1 - Scope Discovery -->

# Task List: Split Critical Oversized Files

**Source**: Code review - Cloud agent analysis (2025-11-15)
**Complexity**: Complex
**Effort**: HIGH (10-14 hours total, 5-7 hours per file)
**Environment**: Local Dev
**Created**: 2025-11-15
**Last Updated**: 2025-11-16 12:00
**Status**: PAUSED
**Pause Reason**: User request (end of session)
**Context Used**: 140K/200K (70%)
**Completed This Session**: Task 0065 (AI Analyzer CLI migration - commit 29191cb)
**Next Action**: Task 0.1 - Scope Discovery for agents/tools.py and services/capability_scanner.py
**Resume Command**: `/do_it tasks-0066-split-critical-oversized-files.md`

---

## Summary

**Goal**: Split 2 CRITICAL files exceeding 800-line hard limit into focused, maintainable modules following single-responsibility principle.

**Approach**: Extract logical groupings into separate modules, maintain backward compatibility via re-exports, update all imports, verify tests pass.

**Scope Discovery**: Completed (cloud agent code review identified all violations)

**Impact**:
- ✅ Eliminates ALL files over 800L hard limit
- ✅ Improves code maintainability (easier debugging, testing, navigation)
- ✅ Reduces cognitive load (focused modules vs monolithic files)
- ✅ Enables independent testing of tool executors and scanner types
- ✅ Compliance with DEVELOPMENT.md file size guidelines (500 soft, 800 hard)

---

## Problem Statement

**Current State** (2025-11-15):

**File Size Violations** (per `quality-report.sh backend/app --quick`):
1. **agents/tools.py**: 1,214 lines (51% over 800L hard limit) 🔴 CRITICAL
2. **services/capability_scanner.py**: 1,192 lines (49% over hard limit) 🔴 CRITICAL

**Code Quality Standards** (from DEVELOPMENT.md:518-547):
- **Soft Limit**: 500 lines (review and consider splitting)
- **Hard Limit**: 800 lines (requires architectural justification, should be rare)
- **Exceptions**: Schema files, generated code, test files (600L), CLI files (600L)

**Why These Files Violate Standards**:
- Neither is schema/generated/test/CLI code
- Both have clear module boundaries (can be split logically)
- Both have multiple responsibilities (tools.py: 12 tool defs + 16 executors, scanner.py: 3 scanner types)
- Both hinder maintainability (hard to navigate, test, debug)

**Files Affected**:
1. `backend/app/agents/tools.py` (1,214 lines) - Main target
2. `backend/app/services/capability_scanner.py` (1,192 lines) - Main target
3. `backend/app/agents/base.py` (imports tools.py)
4. `backend/app/agents/discovery.py` (imports tools.py)
5. `backend/app/agents/portfolio_analyzer.py` (imports tools.py)
6. `backend/app/tasks/capability_tasks.py` (imports capability_scanner.py)
7. Tests referencing above modules

---

## Tasks

### Phase 1: Split agents/tools.py (1,214 lines → ~50 + 4×~280 lines)

**Current Structure**:
- Lines 1-27: Imports and module docstring
- Lines 27-358: Tool definitions (12 functions returning dict schemas)
- Lines 359-1214: AgentTools class (16 tool executor methods)

**Target Structure**:
- `agents/tool_definitions.py` (~360 lines): All 12 `get_*_tool_definition()` functions
- `agents/tool_executors_data.py` (~300 lines): DataTools class (news, economic, portfolio, price)
- `agents/tool_executors_trading.py` (~400 lines): TradingTools class (store_idea, add_ticker, remove_ticker, create_paper_trade)
- `agents/tool_executors_collaboration.py` (~150 lines): CollaborationTools class (send_message, query_memory, vote, wait)
- `agents/tools.py` (~50 lines): Unified AgentTools orchestrator + re-exports

#### 1.1 Extract Tool Definitions Module

- [ ] 1.1.1 Create `agents/tool_definitions.py`
  - Copy: Lines 1-358 from tools.py (imports + 12 tool definition functions)
  - Update: Module docstring to "Agent tool definitions for Claude API."
  - Include: All `get_*_tool_definition()` functions (12 total)
  - Verify: No runtime dependencies (only return dicts, no storage/service usage)
  - Add: Type hints for return type `-> dict[str, object]`
  - Format: Run `ruff format agents/tool_definitions.py`

- [ ] 1.1.2 Verify tool_definitions.py standalone
  - Import test: `python -c "from app.agents.tool_definitions import *; print('OK')"`
  - Function count: Verify 12 functions present
  - Lint: `ruff check agents/tool_definitions.py` (zero errors)
  - Type check: `mypy agents/tool_definitions.py --strict` (zero errors)

#### 1.2 Extract DataTools Executor

- [ ] 1.2.1 Create `agents/tool_executors_data.py`
  - Copy: Lines ~380-620 from tools.py (data-fetching tool executors)
  - Create: `class DataTools` with methods:
    - `execute_get_news(query, max_results)` (lines ~380-413)
    - `execute_get_economic_data(indicators)` (lines ~415-418)
    - `execute_get_portfolio_data()` (lines ~420-437)
    - `execute_get_price_data(symbols)` (lines ~439-467)
    - `_fetch_indicators(ticker)` (lines ~469-527)
    - `_format_indicator_analysis(ticker, current_price, indicators)` (lines ~529-620)
  - Add: `__init__(self, storage, news_service, fred_source, portfolio_mgr, analytics, price_fetcher)` constructor
  - Add: Type hints for all parameters and return types
  - Import: Required dependencies (NewsService, FREDSource, etc.)

- [ ] 1.2.2 Verify DataTools standalone
  - Import test: `python -c "from app.agents.tool_executors_data import DataTools; print('OK')"`
  - Method count: Verify 6 methods (4 public, 2 private)
  - Dependencies: Verify imports resolve (storage, services)
  - Lint: `ruff check agents/tool_executors_data.py` (zero errors)
  - Type check: `mypy agents/tool_executors_data.py --strict` (zero errors)

#### 1.3 Extract TradingTools Executor

- [ ] 1.3.1 Create `agents/tool_executors_trading.py`
  - Copy: Lines ~650-958 from tools.py (trading tool executors)
  - Create: `class TradingTools` with methods:
    - `execute_store_idea(...)` (~80 lines)
    - `execute_add_ticker(agent_run_id, ticker, reason, expected_return_pct, time_horizon_days)` (~50 lines)
    - `execute_remove_ticker(agent_run_id, ticker, reason)` (~40 lines)
    - `execute_create_paper_trade(agent_run_id, ticker, action, thesis, target_price, stop_loss_pct)` (~140 lines)
  - Add: `__init__(self, storage, order_executor)` constructor
  - Add: Type hints for all parameters (use `Literal["buy", "sell"]` for action)
  - Import: Required dependencies (OrderExecutor, storage types)

- [ ] 1.3.2 Verify TradingTools standalone
  - Import test: `python -c "from app.agents.tool_executors_trading import TradingTools; print('OK')"`
  - Method count: Verify 4 methods
  - Type hints: Verify `Literal` types for action parameter
  - Lint: `ruff check agents/tool_executors_trading.py` (zero errors)
  - Type check: `mypy agents/tool_executors_trading.py --strict` (zero errors)

#### 1.4 Extract CollaborationTools Executor

- [ ] 1.4.1 Create `agents/tool_executors_collaboration.py`
  - Copy: Lines ~960-1214 from tools.py (collaboration tool executors)
  - Create: `class CollaborationTools` with methods:
    - `execute_send_message_to_agent(agent_run_id, agent_type, message_type, message, data, priority)` (~70 lines)
    - `execute_query_agent_memory(workflow_id, key)` (~50 lines)
    - `execute_vote_on_decision(agent_run_id, workflow_id, decision_id, vote, reasoning, confidence)` (~75 lines)
    - `execute_wait_for_agent_response(message_id, timeout_seconds)` (~60 lines)
  - Add: `__init__(self, storage)` constructor
  - Add: Type hints for all parameters (use `Literal` for vote types)
  - Import: Required dependencies (storage, datetime, uuid)

- [ ] 1.4.2 Verify CollaborationTools standalone
  - Import test: `python -c "from app.agents.tool_executors_collaboration import CollaborationTools; print('OK')"`
  - Method count: Verify 4 methods
  - Type hints: Verify `Literal` types for vote parameter
  - Lint: `ruff check agents/tool_executors_collaboration.py` (zero errors)
  - Type check: `mypy agents/tool_executors_collaboration.py --strict` (zero errors)

#### 1.5 Create Unified Orchestrator

- [ ] 1.5.1 Refactor `agents/tools.py` to orchestrator (~50 lines)
  ```python
  """Agent tools orchestrator - unified interface for all tool execution."""

  from .tool_definitions import (
      get_news_tool_definition,
      get_economic_data_tool_definition,
      # ... all 12 tool definitions
  )
  from .tool_executors_data import DataTools
  from .tool_executors_trading import TradingTools
  from .tool_executors_collaboration import CollaborationTools

  class AgentTools:
      """Unified interface for all agent tools."""

      def __init__(
          self,
          storage,
          news_service,
          fred_source,
          portfolio_mgr,
          analytics,
          price_fetcher,
          order_executor,
      ):
          self.storage = storage
          self.data = DataTools(storage, news_service, fred_source, portfolio_mgr, analytics, price_fetcher)
          self.trading = TradingTools(storage, order_executor)
          self.collaboration = CollaborationTools(storage)

      def execute_tool(self, tool_name: str, tool_input: dict, agent_run_id: str | None = None):
          """Route tool execution to appropriate executor."""
          if tool_name == "get_news":
              return self.data.execute_get_news(...)
          elif tool_name == "execute_add_ticker":
              return self.trading.execute_add_ticker(agent_run_id, ...)
          # ... routing for all 16 tools
  ```

- [ ] 1.5.2 Add re-exports for backward compatibility
  - Add: `__all__ = ['AgentTools', 'get_news_tool_definition', ...]` (export all 13 symbols)
  - Purpose: Existing imports like `from app.agents.tools import AgentTools` still work
  - Test: `python -c "from app.agents.tools import AgentTools, get_news_tool_definition; print('OK')"`

#### 1.6 Update Imports in Dependent Files

- [ ] 1.6.1 Update `agents/base.py`
  - Check: Does it import from tools.py? (likely yes for tool definitions)
  - Update: If needed, change to import from tool_definitions
  - Verify: `mypy agents/base.py --strict` passes

- [ ] 1.6.2 Update `agents/discovery.py`
  - Check: Imports AgentTools or tool definitions
  - Update: Verify imports still resolve after split
  - Test: `python -c "from app.agents.discovery import DiscoveryAgent; print('OK')"`

- [ ] 1.6.3 Update `agents/portfolio_analyzer.py`
  - Check: Imports AgentTools or tool definitions
  - Update: Verify imports still resolve after split
  - Test: `python -c "from app.agents.portfolio_analyzer import PortfolioAnalyzerAgent; print('OK')"`

#### 1.7 Testing & Verification (Phase 1)

- [ ] 1.7.1 Run full test suite
  - Command: `cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/ -v`
  - Verify: ALL 508 tests still pass
  - Check: No import errors in agent tests
  - Monitor: Test duration (should be similar to before)

- [ ] 1.7.2 Test tool execution manually
  - Create: Test script that instantiates AgentTools and executes each tool type
  - Test: Data tools (get_news, get_economic_data, get_portfolio_data, get_price_data)
  - Test: Trading tools (store_idea, add_ticker, remove_ticker, create_paper_trade)
  - Test: Collaboration tools (send_message, query_memory, vote, wait)
  - Verify: All tools execute without import or runtime errors

- [ ] 1.7.3 Verify code quality
  - File sizes: All new files <500 lines (target: ~150-400 each)
  - Lint: `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy)
  - Type coverage: `mypy agents/ --strict` zero errors
  - Format: All files formatted with `ruff format`

---

### Phase 2: Split services/capability_scanner.py (1,192 lines → ~20 + 3×~390 lines)

**Current Structure**:
- Lines 1-34: Imports and module docstring
- Lines 35-418: DatabaseScanner class (384 lines)
- Lines 419-875: CeleryScanner class (457 lines)
- Lines 876-1180: APIScanner class (305 lines)
- Lines 1181-1192: Utility functions (12 lines)

**Target Structure**:
- `services/capability_db_scanner.py` (~400 lines): DatabaseScanner class
- `services/capability_celery_scanner.py` (~470 lines): CeleryScanner class
- `services/capability_api_scanner.py` (~320 lines): APIScanner class
- `services/capability_utils.py` (~20 lines): Shared utilities (_to_json_string, etc.)
- `services/capability_scanner.py` (~20 lines): Re-exports for backward compatibility

#### 2.1 Extract DatabaseScanner Module

- [ ] 2.1.1 Create `services/capability_db_scanner.py`
  - Copy: Lines 1-34 (imports), Lines 35-418 (DatabaseScanner class)
  - Update: Module docstring to "Database table capability scanner."
  - Include: Entire `DatabaseScanner` class with all methods:
    - `__init__(connection_mgr, config)`
    - `scan() -> list[dict[str, Any]]`
    - `_scan_single_table(...)`
    - `_calculate_freshness_status(...)`
    - `save_capabilities(...)`
    - All private helper methods
  - Import: Dependencies from config_loader (categorize_by_name, get_expected_freshness, etc.)
  - Format: Run `ruff format services/capability_db_scanner.py`

- [ ] 2.1.2 Verify DatabaseScanner standalone
  - Import test: `python -c "from app.services.capability_db_scanner import DatabaseScanner; print('OK')"`
  - Method count: Verify all scanner methods present
  - Dependencies: Verify config_loader imports resolve
  - Lint: `ruff check services/capability_db_scanner.py` (zero errors)
  - Type check: `mypy services/capability_db_scanner.py --strict` (zero errors)

#### 2.2 Extract CeleryScanner Module

- [ ] 2.2.1 Create `services/capability_celery_scanner.py`
  - Copy: Lines 419-875 (CeleryScanner class)
  - Update: Module docstring to "Celery task capability scanner."
  - Include: Entire `CeleryScanner` class with all methods:
    - `__init__(connection_mgr, config)`
    - `scan() -> list[dict[str, Any]]`
    - `_scan_single_task(...)`
    - `_detect_task_schedule(...)`
    - `_get_task_stats(...)`
    - `save_capabilities(...)`
    - All private helper methods
  - Import: Required dependencies (celery_app, pathlib, re, inspect)
  - Format: Run `ruff format services/capability_celery_scanner.py`

- [ ] 2.2.2 Verify CeleryScanner standalone
  - Import test: `python -c "from app.services.capability_celery_scanner import CeleryScanner; print('OK')"`
  - Method count: Verify all scanner methods present
  - Dependencies: Verify celery_app import resolves
  - Lint: `ruff check services/capability_celery_scanner.py` (zero errors)
  - Type check: `mypy services/capability_celery_scanner.py --strict` (zero errors)

#### 2.3 Extract APIScanner Module

- [ ] 2.3.1 Create `services/capability_api_scanner.py`
  - Copy: Lines 876-1180 (APIScanner class)
  - Update: Module docstring to "API endpoint capability scanner."
  - Include: Entire `APIScanner` class with all methods:
    - `__init__(connection_mgr, config)`
    - `scan() -> list[dict[str, Any]]`
    - `_scan_single_endpoint(...)`
    - `_extract_route_info(...)`
    - `save_capabilities(...)`
    - All private helper methods
  - Import: Required dependencies (pathlib, re, ast)
  - Format: Run `ruff format services/capability_api_scanner.py`

- [ ] 2.3.2 Verify APIScanner standalone
  - Import test: `python -c "from app.services.capability_api_scanner import APIScanner; print('OK')"`
  - Method count: Verify all scanner methods present
  - Dependencies: Verify imports resolve
  - Lint: `ruff check services/capability_api_scanner.py` (zero errors)
  - Type check: `mypy services/capability_api_scanner.py --strict` (zero errors)

#### 2.4 Extract Utility Module

- [ ] 2.4.1 Create `services/capability_utils.py`
  - Copy: Lines 1181-1192 (_to_json_string utility)
  - Add: Any other shared utilities used by scanners
  - Update: Module docstring to "Shared utilities for capability scanners."
  - Format: Run `ruff format services/capability_utils.py`

- [ ] 2.4.2 Update scanner imports
  - Update: All 3 scanner modules to import from capability_utils
  - Replace: Local utility usage with `from .capability_utils import _to_json_string`
  - Verify: No duplicate utility code

#### 2.5 Create Re-export Module

- [ ] 2.5.1 Refactor `services/capability_scanner.py` to re-export (~20 lines)
  ```python
  """Capability scanner - imports all scanner types.

  For backward compatibility, imports all scanner classes.
  Existing code can still import from this module.
  """

  from .capability_db_scanner import DatabaseScanner
  from .capability_celery_scanner import CeleryScanner
  from .capability_api_scanner import APIScanner
  from .capability_utils import _to_json_string

  __all__ = ['DatabaseScanner', 'CeleryScanner', 'APIScanner', '_to_json_string']
  ```

- [ ] 2.5.2 Verify backward compatibility
  - Test: `python -c "from app.services.capability_scanner import DatabaseScanner, CeleryScanner, APIScanner; print('OK')"`
  - Verify: Existing imports still work (capability_tasks.py uses these)

#### 2.6 Update Imports in Dependent Files

- [ ] 2.6.1 Update `tasks/capability_tasks.py`
  - Current: Line 15 imports `from ..services.capability_scanner import APIScanner, CeleryScanner, DatabaseScanner`
  - Verify: Still works with re-export module (no changes needed)
  - Test: `python -c "from app.tasks.capability_tasks import scan_system_capabilities; print('OK')"`

- [ ] 2.6.2 Check for other imports
  - Search: `grep -r "from.*capability_scanner import" backend/app --include="*.py"`
  - Update: Any direct imports if found
  - Verify: All imports resolve after split

#### 2.7 Testing & Verification (Phase 2)

- [ ] 2.7.1 Run full test suite
  - Command: `cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/ -v`
  - Verify: ALL 508 tests still pass
  - Check: No import errors in capability tests
  - Monitor: Test duration (should be similar to before)

- [ ] 2.7.2 Test scanners manually
  - Test: DatabaseScanner.scan() executes and returns table metadata
  - Test: CeleryScanner.scan() executes and returns task metadata
  - Test: APIScanner.scan() executes and returns endpoint metadata
  - Verify: All scanners produce same output as before split

- [ ] 2.7.3 Test Celery tasks
  - Trigger: `scan_system_capabilities` task manually
  - Command: `celery -A app.celery_app call app.tasks.capability_tasks.scan_system_capabilities`
  - Verify: Task completes successfully
  - Check: Database tables updated (db_capabilities, celery_capabilities, api_capabilities)
  - Verify: No import errors in task logs

- [ ] 2.7.4 Verify code quality
  - File sizes: All new files <500 lines (target: ~300-470 each)
  - Lint: `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy)
  - Type coverage: `mypy services/capability_*.py --strict` zero errors
  - Format: All files formatted with `ruff format`

---

### Phase 3: Final Verification & Cleanup

- [ ] 3.1 Run complete quality audit
  - Command: `bash ~/portfolio-ai/.claude/skills/code-quality/scripts/quality-report.sh backend/app --quick`
  - Verify: ZERO CRITICAL files (was 2)
  - Check: File size summary shows all files <800 lines
  - Document: New file count and size distribution

- [ ] 3.2 Run full test suite one final time
  - Command: `cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/ -v --tb=short`
  - Verify: ALL 508 tests pass
  - Check: No new warnings or errors
  - Monitor: Test duration unchanged (no performance regression)

- [ ] 3.3 Test service restart
  - Restart: `bash ~/portfolio-ai/scripts/restart.sh`
  - Verify: All services start successfully
  - Check: Backend logs for import errors
  - Test: Make API call to verify backend responds
  - Monitor: First 2 minutes for crashes

- [ ] 3.4 Verify scheduled tasks still work
  - Check: Celery beat schedule intact
  - Wait: For next `scan_system_capabilities` scheduled run
  - Verify: Task executes without errors
  - Monitor: Celery worker logs for import errors

- [ ] 3.5 Update documentation
  - File: `docs/core/DEVELOPMENT.md` (if module structure documented)
  - Update: Agent tools module structure (4 new files)
  - Update: Capability scanner module structure (4 new files)
  - Document: Import patterns and backward compatibility

---

## Verification Checklist

- [ ] **File Size Compliance**
  - [ ] agents/tools.py: <100 lines (orchestrator only)
  - [ ] agents/tool_definitions.py: ~360 lines
  - [ ] agents/tool_executors_data.py: ~300 lines
  - [ ] agents/tool_executors_trading.py: ~400 lines
  - [ ] agents/tool_executors_collaboration.py: ~150 lines
  - [ ] services/capability_scanner.py: <50 lines (re-exports only)
  - [ ] services/capability_db_scanner.py: ~400 lines
  - [ ] services/capability_celery_scanner.py: ~470 lines
  - [ ] services/capability_api_scanner.py: ~320 lines
  - [ ] services/capability_utils.py: ~20 lines
  - [ ] ZERO files over 800L hard limit

- [ ] **Backward Compatibility**
  - [ ] Existing imports still work (no breaking changes)
  - [ ] AgentTools instantiation unchanged
  - [ ] Scanner imports resolve from re-export module
  - [ ] No code changes needed in dependent files

- [ ] **Tests**
  - [ ] All 508 tests pass
  - [ ] No new import errors
  - [ ] No performance regression
  - [ ] Agent tests exercise all tool types
  - [ ] Capability tests exercise all scanner types

- [ ] **Code Quality**
  - [ ] `~/portfolio-ai/scripts/lint.sh` passes
  - [ ] `mypy backend/app --strict` zero errors
  - [ ] All files formatted with `ruff format`
  - [ ] No duplicate code across modules

- [ ] **Runtime Verification**
  - [ ] Services restart successfully
  - [ ] API responds to requests
  - [ ] Scheduled tasks execute without errors
  - [ ] No import errors in logs
  - [ ] Agent tool execution works
  - [ ] Capability scanning works

- [ ] **Documentation**
  - [ ] Module structure documented (if applicable)
  - [ ] Import patterns explained
  - [ ] Backward compatibility noted

---

## Success Criteria

1. **Zero CRITICAL files**: No files exceed 800-line hard limit (was 2, now 0)
2. **Focused modules**: Each module has single responsibility (tools defs, data tools, trading tools, collaboration tools, DB scanner, Celery scanner, API scanner)
3. **Backward compatible**: Existing code works without changes
4. **All tests pass**: 508 tests green, zero regressions
5. **Services stable**: Backend, Celery, Beat all restart successfully
6. **Quality improved**: Easier to navigate, test, debug, maintain
7. **Compliance achieved**: DEVELOPMENT.md file size guidelines met

---

## Notes

**Why Split These Files?**
- Both exceed hard limit by 49-51% (egregious violations)
- Both have clear module boundaries (natural split points)
- Both hinder maintainability (too large to navigate effectively)
- Both can be split without breaking changes (re-export pattern)

**Split Strategy**:
- **tools.py**: Split by tool category (definitions, data, trading, collaboration)
- **capability_scanner.py**: Split by scanner type (database, Celery, API)
- Both use re-export pattern for backward compatibility

**Risk Mitigation**:
- Re-export modules preserve existing imports (zero breaking changes)
- Full test suite run after each phase
- Service restart verification
- Rollback plan: Keep original files in git history, can revert easily

**Estimated Effort Breakdown**:
- Phase 1 (tools.py): 5-7 hours (4 extractions + orchestrator + testing)
- Phase 2 (capability_scanner.py): 4-5 hours (3 extractions + utils + testing)
- Phase 3 (verification): 1-2 hours (final checks + docs)
- **Total**: 10-14 hours

**Related Work**:
- Task 0067: Refactor WARNING-level files (500-800L, next priority)
- PRD #0024: Code quality refactoring (broader quality effort)
