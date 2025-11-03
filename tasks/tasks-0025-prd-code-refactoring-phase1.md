# Task List: Code Refactoring Phase 1 - Large File Splitting

**PRD**: `tasks/0025-prd-code-refactoring-phase1.md`
**Status**: Ready for Implementation
**Completion**: 0%
**Effort**: HIGH (20-28 hours over 3-4 sessions)
**Updated**: 2025-11-03

---

## Summary

**✅ COMPLETE:** (None)
**🔄 IN PROGRESS:** (Not started)
**⚠️ NEXT:** Task 1.0 - CRITICAL: Refactor watchlist/service.py

---

## Relevant Files

### Create (13 files)
- `backend/app/watchlist/watchlist_service.py` (~400 lines) - Core CRUD operations
- `backend/app/watchlist/scoring_service.py` (~400 lines) - Scoring logic
- `backend/app/watchlist/snapshot_service.py` (~400 lines) - Snapshot management
- `backend/app/tasks/watchlist_tasks.py` (~250 lines) - Watchlist refresh tasks
- `backend/app/tasks/data_ingestion_tasks.py` (~250 lines) - OHLCV ingestion
- `backend/app/tasks/indicator_tasks.py` (~250 lines) - Technical indicator updates
- `backend/app/watchlist/response_builders.py` (~300 lines) - Response construction
- `backend/app/watchlist/signal_classifier.py` (~300 lines) - Signal classification
- `backend/app/watchlist/narrative_generator.py` (~300 lines) - Narrative text generation
- `backend/app/config/quota_config.json` (~50 lines) - Quota configuration data
- `backend/app/utils/quota_helpers.py` (~150 lines) - Quota calculation helpers
- `backend/tests/watchlist/test_response_builders.py` (~200 lines) - Response builder tests
- `backend/tests/tasks/test_task_splitting.py` (~150 lines) - Task splitting tests

### Update (21+ files)
**Source files being split:**
- `backend/app/watchlist/service.py` - Split into 3 files
- `backend/app/tasks/agent_tasks.py` - Split into 3 files
- `backend/app/api/watchlist.py` - Extract response builders
- `backend/app/watchlist/narrative.py` - Split into 2 files
- `backend/app/api/health.py` - Extract quota config + helpers
- `backend/app/sources/rest_api_source.py` - Extract generic pattern
- `backend/app/analytics/paper_trading.py` - Extract helpers

**Files importing from refactored modules (8+ files):**
- `backend/app/api/watchlist.py` - Imports watchlist/service
- `backend/app/tasks/agent_tasks.py` - Imports watchlist/service
- `backend/app/api/ideas.py` - Imports tasks/agent_tasks
- `backend/app/celery_app.py` - Imports tasks/agent_tasks
- `backend/scripts/populate_watchlist_data.py` - Imports tasks/agent_tasks
- `backend/tests/unit/test_watchlist_refresh_errors.py` - Imports watchlist/service
- `backend/tests/watchlist/test_service_narrative_integration.py` - Imports watchlist/service
- `backend/tests/watchlist/test_staleness_ttl.py` - Imports watchlist/service
- `backend/tests/watchlist/test_api_timestamp_fix.py` - Imports watchlist/service
- `backend/tests/watchlist/test_service.py` - Imports watchlist/service
- `backend/tests/unit/test_watchlist_price_change.py` - Imports watchlist/service

### Notes
- Tests: Run `pytest tests/` after each phase
- Quality: Run `mypy backend/app/ --strict` and `ruff check backend/app/` after each file split
- Git: Use `git mv` where possible to preserve history
- Commit: After each file split successfully passes tests

---

## Tasks

### Phase 1: CRITICAL - watchlist/service.py (6-8 hours)

- [ ] 1.0 CRITICAL: Refactor watchlist/service.py (1306 → <500 lines) (6-8 hours, HIGH)
  - [ ] 1.1 Pre-refactor analysis (30 min)
    - [ ] 1.1.1 Read entire watchlist/service.py (10 min)
      - Understand module structure
      - Identify all functions and their dependencies
      - Map which functions belong in which service
    - [ ] 1.1.2 Run existing tests to establish baseline (5 min)
      - `pytest backend/tests/watchlist/test_service.py -v`
      - `pytest backend/tests/watchlist/ -v`
      - Document current pass/fail state
    - [ ] 1.1.3 Find ALL files importing watchlist/service (5 min)
      - Already found: 8 files (api/watchlist.py, tasks/agent_tasks.py, 6 test files)
      - Create checklist of files to update
    - [ ] 1.1.4 Analyze function dependencies (10 min)
      - Map: CRUD functions → watchlist_service.py
      - Map: Scoring functions (refresh_watchlist_scores, etc.) → scoring_service.py
      - Map: Snapshot functions → snapshot_service.py
      - Identify helper functions used across modules

  - [ ] 1.2 Create new module files (30 min)
    - [ ] 1.2.1 Create backend/app/watchlist/watchlist_service.py (5 min)
      - Add module docstring
      - Add imports (copy from service.py)
      - Add placeholder: `# CRUD operations will go here`
    - [ ] 1.2.2 Create backend/app/watchlist/scoring_service.py (5 min)
      - Add module docstring
      - Add imports (copy from service.py)
      - Add placeholder: `# Scoring logic will go here`
    - [ ] 1.2.3 Create backend/app/watchlist/snapshot_service.py (5 min)
      - Add module docstring
      - Add imports (copy from service.py)
      - Add placeholder: `# Snapshot management will go here`
    - [ ] 1.2.4 Update backend/app/watchlist/__init__.py (10 min)
      - Add re-exports from new modules
      - Ensure backward compatibility (old imports still work)
      - Add deprecation warnings if needed
    - [ ] 1.2.5 Verify imports work (5 min)
      - Run: `python -c "from app.watchlist.watchlist_service import *"`
      - Should succeed (no errors)

  - [ ] 1.3 Extract helper functions (from CODE_AUDIT recommendations) (1 hour)
    - [ ] 1.3.1 Extract _gather_inputs_for_symbol helper (20 min)
      - Identify code block in refresh_watchlist_scores (lines ~XX-YY)
      - Create function in scoring_service.py
      - Add type hints, docstring
      - Replace inline code with function call
    - [ ] 1.3.2 Extract _process_single_item helper (20 min)
      - Identify code block in refresh_watchlist_scores
      - Create function in scoring_service.py
      - Add type hints, docstring
      - Replace inline code with function call
    - [ ] 1.3.3 Extract _build_item_response helper (20 min)
      - Used by get_items_with_scores AND get_item_with_score_by_id
      - Create function in watchlist_service.py (shared)
      - Add type hints, docstring
      - Replace duplicate code in both functions

  - [ ] 1.4 Move CRUD functions to watchlist_service.py (2 hours)
    - [ ] 1.4.1 Move add_watchlist_item function (15 min)
      - Copy function to watchlist_service.py
      - Update imports in watchlist_service.py if needed
      - Test: `pytest -k test_add_watchlist_item`
    - [ ] 1.4.2 Move remove_watchlist_item function (15 min)
      - Copy function to watchlist_service.py
      - Test: `pytest -k test_remove_watchlist_item`
    - [ ] 1.4.3 Move get_watchlist_items function (15 min)
      - Copy function to watchlist_service.py
      - Test: `pytest -k test_get_watchlist_items`
    - [ ] 1.4.4 Move get_items_with_scores function (20 min)
      - Copy function to watchlist_service.py
      - Uses _build_item_response helper
      - Test: `pytest -k test_get_items_with_scores`
    - [ ] 1.4.5 Move get_item_with_score_by_id function (20 min)
      - Copy function to watchlist_service.py
      - Uses _build_item_response helper
      - Test: `pytest -k test_get_item_by_id`
    - [ ] 1.4.6 Move update_watchlist_item function (15 min)
      - Copy function to watchlist_service.py
      - Test: `pytest -k test_update_watchlist_item`
    - [ ] 1.4.7 Move other CRUD functions (20 min)
      - Identify remaining CRUD functions (list, filter, etc.)
      - Move to watchlist_service.py
      - Test each function

  - [ ] 1.5 Move scoring functions to scoring_service.py (2 hours)
    - [ ] 1.5.1 Move refresh_watchlist_scores function (30 min)
      - Copy function to scoring_service.py
      - Update to use extracted helpers (_gather_inputs, _process_single_item)
      - Update imports
      - Test: `pytest -k test_refresh_watchlist_scores`
    - [ ] 1.5.2 Move calculate_watchlist_score function (20 min)
      - Copy function to scoring_service.py
      - Test: `pytest -k test_calculate_score`
    - [ ] 1.5.3 Move score aggregation functions (20 min)
      - Identify functions that aggregate scores
      - Move to scoring_service.py
      - Test related functions
    - [ ] 1.5.4 Move scoring helper functions (20 min)
      - Identify private scoring helpers (e.g., _calculate_momentum)
      - Move to scoring_service.py
      - Test edge cases
    - [ ] 1.5.5 Verify scoring logic unchanged (30 min)
      - Run full scoring test suite: `pytest backend/tests/watchlist/ -k score`
      - Manually test scoring for one symbol
      - Compare before/after results

  - [ ] 1.6 Move snapshot functions to snapshot_service.py (1.5 hours)
    - [ ] 1.6.1 Move create_watchlist_snapshot function (20 min)
      - Copy function to snapshot_service.py
      - Test: `pytest -k test_create_snapshot`
    - [ ] 1.6.2 Move get_latest_snapshot function (15 min)
      - Copy function to snapshot_service.py
      - Test: `pytest -k test_get_latest_snapshot`
    - [ ] 1.6.3 Move get_snapshot_history function (15 min)
      - Copy function to snapshot_service.py
      - Test: `pytest -k test_snapshot_history`
    - [ ] 1.6.4 Move snapshot cleanup functions (15 min)
      - Functions for deleting old snapshots
      - Move to snapshot_service.py
      - Test cleanup logic
    - [ ] 1.6.5 Move snapshot comparison functions (15 min)
      - Functions for comparing snapshots over time
      - Move to snapshot_service.py
      - Test comparisons
    - [ ] 1.6.6 Verify snapshot logic unchanged (10 min)
      - Run: `pytest backend/tests/watchlist/ -k snapshot`
      - Verify all tests pass

  - [ ] 1.7 Update imports in dependent files (1 hour)
    - [ ] 1.7.1 Update backend/app/api/watchlist.py imports (10 min)
      - Replace `from app.watchlist.service import X` with specific imports
      - CRUD functions: `from app.watchlist.watchlist_service import X`
      - Scoring functions: `from app.watchlist.scoring_service import X`
      - Run: `ruff check backend/app/api/watchlist.py`
    - [ ] 1.7.2 Update backend/app/tasks/agent_tasks.py imports (10 min)
      - Replace imports with specific service imports
      - Primarily scoring_service functions
      - Run: `ruff check backend/app/tasks/agent_tasks.py`
    - [ ] 1.7.3 Update test file imports (40 min)
      - Update 6 test files:
        - tests/unit/test_watchlist_refresh_errors.py
        - tests/watchlist/test_service_narrative_integration.py
        - tests/watchlist/test_staleness_ttl.py
        - tests/watchlist/test_api_timestamp_fix.py
        - tests/watchlist/test_service.py
        - tests/unit/test_watchlist_price_change.py
      - Each file: update imports, run tests (5-7 min per file)

  - [ ] 1.8 Remove original service.py and final verification (30 min)
    - [ ] 1.8.1 Verify all functions moved (5 min)
      - Check service.py for remaining functions
      - Should only have imports/re-exports or be empty
    - [ ] 1.8.2 Delete or archive service.py (5 min)
      - Option 1: Delete service.py entirely
      - Option 2: Keep as re-export facade for backward compat
      - Recommended: Keep as facade initially, delete in follow-up
    - [ ] 1.8.3 Run full test suite (10 min)
      - `pytest backend/tests/watchlist/ -v`
      - All tests should pass
    - [ ] 1.8.4 Run quality checks (5 min)
      - `mypy backend/app/watchlist/ --strict`
      - `ruff check backend/app/watchlist/`
      - Fix any issues
    - [ ] 1.8.5 Verify file sizes (3 min)
      - `wc -l backend/app/watchlist/*.py`
      - watchlist_service.py: <500 lines
      - scoring_service.py: <500 lines
      - snapshot_service.py: <500 lines
    - [ ] 1.8.6 Commit (2 min)
      - `git add backend/app/watchlist/ backend/app/api/ backend/app/tasks/ backend/tests/`
      - `git commit -m "refactor: split watchlist/service.py into 3 focused modules (1306 → <500 lines each)"`

---

### Phase 2: HIGH Priority Files (8-10 hours)

- [ ] 2.0 HIGH: Refactor tasks/agent_tasks.py (786 → <500 lines) (3-4 hours, MEDIUM)
  - [ ] 2.1 Pre-refactor analysis (20 min)
    - [ ] 2.1.1 Read entire agent_tasks.py (10 min)
      - Identify watchlist tasks vs data ingestion vs indicator tasks
      - Map dependencies between tasks
    - [ ] 2.1.2 Find ALL files importing agent_tasks (5 min)
      - Already found: 4 files (api/watchlist.py, api/ideas.py, celery_app.py, scripts/populate_watchlist_data.py)
      - Create checklist
    - [ ] 2.1.3 Run existing task tests (5 min)
      - `pytest backend/tests/tasks/ -v`
      - Document baseline

  - [ ] 2.2 Create new task module files (20 min)
    - [ ] 2.2.1 Create backend/app/tasks/watchlist_tasks.py (5 min)
    - [ ] 2.2.2 Create backend/app/tasks/data_ingestion_tasks.py (5 min)
    - [ ] 2.2.3 Create backend/app/tasks/indicator_tasks.py (5 min)
    - [ ] 2.2.4 Update backend/app/tasks/__init__.py (5 min)
      - Re-export all tasks for backward compat

  - [ ] 2.3 Split refresh_watchlist_scores_task (1 hour, from CODE_AUDIT)
    - [ ] 2.3.1 Extract _prepare_dataframe_for_ingestion helper (20 min)
      - Create in data_ingestion_tasks.py
      - Extract logic from current task
    - [ ] 2.3.2 Move refresh_watchlist_scores_task to watchlist_tasks.py (20 min)
      - Core scoring refresh task
      - Update imports
    - [ ] 2.3.3 Create separate auto_backfill_scores_task (20 min)
      - New task for automatic backfilling
      - Separate concern from refresh task
      - Test both tasks independently

  - [ ] 2.4 Move data ingestion tasks (1 hour)
    - [ ] 2.4.1 Move ingest_ohlcv_data_task to data_ingestion_tasks.py (20 min)
    - [ ] 2.4.2 Move ingest_news_task to data_ingestion_tasks.py (15 min)
    - [ ] 2.4.3 Move ingest_fundamentals_task to data_ingestion_tasks.py (15 min)
    - [ ] 2.4.4 Move SQL queries to storage layer (10 min)
      - From CODE_AUDIT: "Move SQL to storage layer"
      - Identify inline SQL in tasks
      - Create storage functions

  - [ ] 2.5 Move indicator tasks (45 min)
    - [ ] 2.5.1 Move update_technical_indicators_task to indicator_tasks.py (20 min)
    - [ ] 2.5.2 Move calculate_indicator_task to indicator_tasks.py (15 min)
    - [ ] 2.5.3 Move backfill_indicators_task to indicator_tasks.py (10 min)

  - [ ] 2.6 Update imports and verify (45 min)
    - [ ] 2.6.1 Update celery_app.py imports (10 min)
      - Update task registrations
      - Test celery worker starts
    - [ ] 2.6.2 Update api/ideas.py imports (5 min)
    - [ ] 2.6.3 Update api/watchlist.py imports (5 min)
    - [ ] 2.6.4 Update scripts/populate_watchlist_data.py (5 min)
    - [ ] 2.6.5 Run full test suite (15 min)
      - `pytest backend/tests/tasks/ -v`
    - [ ] 2.6.6 Verify file sizes and commit (5 min)
      - Each file <300 lines
      - Commit refactor

- [ ] 3.0 HIGH: Refactor api/watchlist.py (745 → <400 lines) (2-3 hours, MEDIUM)
  - [ ] 3.1 Pre-refactor analysis (15 min)
    - [ ] 3.1.1 Read api/watchlist.py (10 min)
      - Identify duplicate response construction logic
      - Map which endpoints use similar patterns
    - [ ] 3.1.2 Run API tests (5 min)
      - `pytest backend/tests/api/test_watchlist.py -v`

  - [ ] 3.2 Create response_builders.py module (45 min)
    - [ ] 3.2.1 Create backend/app/watchlist/response_builders.py (10 min)
      - Add module docstring
      - Add imports (Pydantic models, etc.)
    - [ ] 3.2.2 Create WatchlistItemResponse class method (from CODE_AUDIT) (20 min)
      - Add `@classmethod from_service_dict(cls, data: dict) -> WatchlistItemResponse`
      - Extract logic from endpoints
      - Add type hints and docstring
    - [ ] 3.2.3 Create additional response builders (15 min)
      - SnapshotResponse.from_service_dict()
      - ScoreResponse.from_service_dict()
      - Any other response patterns

  - [ ] 3.3 Update api/watchlist.py to use response builders (1 hour)
    - [ ] 3.3.1 Update get_watchlist endpoint (15 min)
      - Replace inline response construction
      - Use WatchlistItemResponse.from_service_dict()
      - Test endpoint
    - [ ] 3.3.2 Update get_item endpoint (15 min)
      - Use response builder
      - Test endpoint
    - [ ] 3.3.3 Update remaining endpoints (30 min)
      - Systematic replacement of response construction
      - Test each endpoint after update

  - [ ] 3.4 Final verification and commit (30 min)
    - [ ] 3.4.1 Run API test suite (15 min)
      - `pytest backend/tests/api/test_watchlist.py -v`
    - [ ] 3.4.2 Verify file sizes (5 min)
      - api/watchlist.py: <400 lines
      - response_builders.py: ~300 lines
    - [ ] 3.4.3 Run quality checks and commit (10 min)
      - mypy, ruff
      - Commit refactor

- [ ] 4.0 HIGH: Refactor watchlist/narrative.py (628 → <500 lines) (3-4 hours, MEDIUM)
  - [ ] 4.1 Pre-refactor analysis (15 min)
    - [ ] 4.1.1 Read narrative.py (10 min)
      - Understand classify_signal function (100 lines)
      - Identify signal classification vs narrative generation
    - [ ] 4.1.2 Run narrative tests (5 min)
      - `pytest backend/tests/watchlist/test_narrative.py -v`

  - [ ] 4.2 Create signal_classifier.py module (1.5 hours)
    - [ ] 4.2.1 Create backend/app/watchlist/signal_classifier.py (10 min)
    - [ ] 4.2.2 Refactor classify_signal to rule-based pattern (from CODE_AUDIT) (1 hour)
      - Extract rule definitions
      - Create Rule class or dataclass
      - Refactor 100-line function to rule engine pattern
      - Reduces complexity, improves testability
    - [ ] 4.2.3 Move classification logic to signal_classifier.py (20 min)
      - Move classify_signal
      - Move related helper functions
      - Test classification

  - [ ] 4.3 Create narrative_generator.py module (1.5 hours)
    - [ ] 4.3.1 Create backend/app/watchlist/narrative_generator.py (10 min)
    - [ ] 4.3.2 Extract bullet generation functions (from CODE_AUDIT) (30 min)
      - Identify bullet generation patterns
      - Create helper functions
      - Reduce duplication
    - [ ] 4.3.3 Move narrative generation functions (30 min)
      - Move text generation functions
      - Move template logic
    - [ ] 4.3.4 Move markdown formatting functions (20 min)
      - Move formatting helpers
      - Test output format

  - [ ] 4.4 Update imports and verify (30 min)
    - [ ] 4.4.1 Update imports in files using narrative module (15 min)
      - Find and update imports
    - [ ] 4.4.2 Run narrative tests (10 min)
      - `pytest backend/tests/watchlist/test_narrative.py -v`
    - [ ] 4.4.3 Verify file sizes and commit (5 min)
      - signal_classifier.py: <350 lines
      - narrative_generator.py: <350 lines

---

### Phase 3: MEDIUM Priority Files (4-6 hours)

- [ ] 5.0 MEDIUM: Refactor api/health.py (572 → <400 lines) (2 hours, LOW-MEDIUM)
  - [ ] 5.1 Extract quota_map to config file (45 min)
    - [ ] 5.1.1 Create backend/app/config/quota_config.json (15 min)
      - Extract hardcoded quota_map dict
      - Convert to JSON format
      - Add comments/schema
    - [ ] 5.1.2 Create quota loader in health.py (15 min)
      - Load JSON file at module init
      - Parse into quota_map dict
    - [ ] 5.1.3 Test quota loading (15 min)
      - Verify quotas load correctly
      - Test endpoints using quotas

  - [ ] 5.2 Extract quota helpers (45 min)
    - [ ] 5.2.1 Create backend/app/utils/quota_helpers.py (10 min)
    - [ ] 5.2.2 Move quota calculation functions (20 min)
      - Identify quota calculation logic
      - Move to quota_helpers.py
    - [ ] 5.2.3 Update health.py to use helpers (15 min)
      - Import and use helpers
      - Test health endpoints

  - [ ] 5.3 Verify and commit (30 min)
    - [ ] 5.3.1 Run health tests (15 min)
      - `pytest backend/tests/api/test_health.py -v`
    - [ ] 5.3.2 Verify file sizes and commit (15 min)
      - health.py: <400 lines
      - quota_helpers.py: ~150 lines
      - quota_config.json: ~50 lines

- [ ] 6.0 MEDIUM: Refactor sources/rest_api_source.py (544 → <400 lines) (1-2 hours, LOW-MEDIUM)
  - [ ] 6.1 Analyze duplicate pattern (20 min)
    - [ ] 6.1.1 Read rest_api_source.py (15 min)
      - Identify fetch_day_bars, fetch_reference_payload, fetch_news_payload
      - Find common pattern (CODE_AUDIT: "Three ~80 line methods with duplicate pattern")
    - [ ] 6.1.2 Design generic pattern (5 min)
      - Plan _generic_api_fetch() method signature
      - Identify callbacks needed for type-specific processing

  - [ ] 6.2 Create generic fetch method (1 hour)
    - [ ] 6.2.1 Create _generic_api_fetch() method (30 min)
      - Generic fetch logic
      - Callback parameters for customization
      - Error handling
    - [ ] 6.2.2 Refactor fetch_day_bars to use generic pattern (10 min)
      - Replace implementation with call to _generic_api_fetch
      - Pass type-specific callback
    - [ ] 6.2.3 Refactor fetch_reference_payload (10 min)
      - Use _generic_api_fetch
    - [ ] 6.2.4 Refactor fetch_news_payload (10 min)
      - Use _generic_api_fetch

  - [ ] 6.3 Verify and commit (20 min)
    - [ ] 6.3.1 Test all fetch methods (15 min)
      - `pytest backend/tests/sources/test_rest_api_source.py -v`
    - [ ] 6.3.2 Verify file size and commit (5 min)
      - rest_api_source.py: <400 lines

- [ ] 7.0 MEDIUM: Refactor analytics/paper_trading.py (504 → <450 lines) (1-2 hours, LOW-MEDIUM)
  - [ ] 7.1 Extract helpers (from CODE_AUDIT recommendations) (1 hour)
    - [ ] 7.1.1 Extract _check_exit_conditions() helper (20 min)
      - From update_paper_trades (150 lines with nested exit conditions)
      - Simplifies nested logic
    - [ ] 7.1.2 Extract _update_single_trade() helper (20 min)
      - Isolate single trade update logic
    - [ ] 7.1.3 Extract data gathering helpers (20 min)
      - Extract steps from create_paper_trade (80 lines)

  - [ ] 7.2 Verify and commit (30 min)
    - [ ] 7.2.1 Run paper trading tests (20 min)
      - `pytest backend/tests/analytics/test_paper_trading.py -v`
    - [ ] 7.2.2 Verify file size and commit (10 min)
      - paper_trading.py: <450 lines

---

### Phase 4: Final Verification (1-2 hours)

- [ ] 8.0 Final Verification and Quality Gates (1-2 hours, MEDIUM)
  - [ ] 8.1 Run complete test suite (30 min)
    - [ ] 8.1.1 Run all tests (20 min)
      - `cd backend && source .venv/bin/activate`
      - `pytest tests/ -v`
      - All tests should pass
    - [ ] 8.1.2 Check test coverage (10 min)
      - `pytest tests/ --cov=app --cov-report=term-missing`
      - Coverage should be ≥85% (same as before)

  - [ ] 8.2 Run quality checks (20 min)
    - [ ] 8.2.1 Run mypy on entire codebase (10 min)
      - `mypy backend/app/ --strict`
      - Should pass with no errors
    - [ ] 8.2.2 Run ruff on entire codebase (5 min)
      - `ruff check backend/app/`
      - Should pass with no errors
    - [ ] 8.2.3 Run scripts/lint.sh (5 min)
      - Should pass all checks

  - [ ] 8.3 Verify file size compliance (10 min)
    - [ ] 8.3.1 Check all refactored files (5 min)
      - Run: `wc -l backend/app/**/*.py | awk '$1 > 500 {print}'`
      - Should return: no files (all under 500 lines)
    - [ ] 8.3.2 Generate file size report (5 min)
      - Document before/after line counts
      - Verify 7 violations eliminated

  - [ ] 8.4 Code review (20 min)
    - [ ] 8.4.1 Review for single responsibility (10 min)
      - Each module has clear, focused purpose
      - No mixed concerns
    - [ ] 8.4.2 Review for code duplication (5 min)
      - Verify no duplicate logic introduced
      - DRY principle maintained
    - [ ] 8.4.3 Review imports (5 min)
      - No circular imports
      - All imports necessary and correct

  - [ ] 8.5 Update documentation if needed (10 min)
    - [ ] 8.5.1 Check if ARCHITECTURE.md needs updates (5 min)
      - Module structure changed significantly?
      - Add note about refactored modules if needed
    - [ ] 8.5.2 Update CODE_AUDIT.md (5 min)
      - Mark findings #1-7 as RESOLVED
      - Document new file structure

  - [ ] 8.6 Create summary commit (10 min)
    - [ ] 8.6.1 Review all changes (5 min)
      - `git log --oneline` since refactoring started
      - Verify all phases committed
    - [ ] 8.6.2 Optional: Create summary doc (5 min)
      - Document refactoring results
      - Before/after file sizes
      - Test coverage maintained

---

## Verification (MANDATORY before "COMPLETE ✅")

- [ ] **Functional**: All code works identically
  - [ ] All 7 files under size limits
  - [ ] No behavior changes (business logic identical)
  - [ ] All features work as before
- [ ] **Tests**: 100% passing
  - [ ] `pytest backend/tests/ -v` - ALL PASS
  - [ ] Coverage ≥85% (maintained from before)
  - [ ] No test regressions
  - [ ] New tests added where needed
- [ ] **Quality**: mypy --strict and ruff pass
  - [ ] `mypy backend/app/ --strict` - PASS
  - [ ] `ruff check backend/app/` - PASS
  - [ ] `bash ~/portfolio-ai/scripts/lint.sh` - PASS
- [ ] **Clean**: Improved structure
  - [ ] Single responsibility per module
  - [ ] No duplicate logic (DRY)
  - [ ] No circular imports
  - [ ] No `Any` types added
- [ ] **Docs**: Updated if needed
  - [ ] ARCHITECTURE.md updated if module structure changed
  - [ ] CODE_AUDIT.md updated (findings resolved)
  - [ ] Docstrings present and accurate
- [ ] **Security**: No issues
  - [ ] No SQL injection vulnerabilities
  - [ ] Parameterized queries maintained
  - [ ] No secrets in code
- [ ] **Ops**: Services healthy
  - [ ] Services restart successfully
  - [ ] No runtime errors
  - [ ] Manual smoke test successful

---

## Notes

### File Refactoring Priority Order

**Phase 1 (CRITICAL)**: watchlist/service.py - Most dependencies, highest complexity
**Phase 2 (HIGH)**: 3 files - Major refactors but less interdependent
**Phase 3 (MEDIUM)**: 3 files - Smaller scoped, more isolated
**Phase 4**: Final verification and quality gates

### Dependencies Between Files

**Critical path**:
- watchlist/service.py → used by api/watchlist.py AND tasks/agent_tasks.py
- tasks/agent_tasks.py → used by celery_app.py, api/ideas.py

**Isolated**:
- api/health.py → standalone
- sources/rest_api_source.py → standalone
- analytics/paper_trading.py → standalone

**Refactor isolated files first if risk-averse, or critical path first for maximum impact**

### Import Update Strategy

For each refactored file:
1. Keep old module as re-export facade initially (backward compat)
2. Update imports systematically
3. Remove facade in follow-up commit if desired

Example facade (service.py):
```python
"""Backward compatibility facade. Use specific services instead."""
from app.watchlist.watchlist_service import *
from app.watchlist.scoring_service import *
from app.watchlist.snapshot_service import *
```

### Git History Preservation

Use `git mv` where possible:
```bash
# Don't: Create new file, copy content
# Do: Move file, then split
git mv app/watchlist/service.py app/watchlist/watchlist_service.py
# Edit watchlist_service.py to remove non-CRUD functions
# Create other files with removed content
```

### Testing Strategy

- Test after each logical unit (not after every tiny task)
- Run focused tests during refactoring: `pytest -k test_specific_function`
- Run full suite at phase boundaries
- Maintain 85% coverage target

### Risk Mitigation

- **Circular imports**: Extract shared types to separate file if needed
- **Breaking changes**: Keep backward compat facades initially
- **Test failures**: Commit working state before each phase
- **Time overrun**: Can pause between phases, each delivers value

### Success Metrics

| File | Before | After | Reduction |
|------|--------|-------|-----------|
| watchlist/service.py | 1306 | <500 (3 files) | 61% |
| tasks/agent_tasks.py | 786 | <500 (3 files) | 36% |
| api/watchlist.py | 745 | <400 | 46% |
| watchlist/narrative.py | 628 | <500 (2 files) | 20% |
| api/health.py | 572 | <400 | 30% |
| sources/rest_api_source.py | 544 | <400 | 26% |
| analytics/paper_trading.py | 504 | <450 | 11% |
| **Total** | **5085** | **~3500** | **31%** |

---

## Execution Notes for /do_it

- **Autonomous friendly**: All tasks clearly defined
- **Test-driven**: Run tests after each logical unit
- **Commit frequently**: After each file split
- **Quality gates**: mypy/ruff after each phase
- **Can pause**: Between phases (each phase delivers independent value)
- **Estimated sessions**:
  - Session 1: Phase 1 (watchlist/service.py) - 6-8 hours
  - Session 2: Phase 2 (3 HIGH priority files) - 8-10 hours
  - Session 3: Phase 3 (3 MEDIUM priority files) - 4-6 hours
  - Session 4: Phase 4 (final verification) - 1-2 hours
