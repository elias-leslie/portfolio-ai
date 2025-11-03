# PRD: Code Refactoring Phase 1 - Large File Splitting

**Source**: CODE_AUDIT.md - Findings #1-7 (File Size Violations)
**Severity**: CRITICAL (1 file) + HIGH (3 files) + MEDIUM (3 files)
**Effort**: HIGH (20-24 hours over multiple sessions)
**Created**: 2025-11-03

---

## Introduction

**Current Issue**: 7 Python files exceed the 500-line soft limit (10% of codebase), ranging from 504 to 1306 lines. This violates coding standards and makes files hard to maintain, test, and understand.

**Desired State**: All Python files under 500 lines by splitting large files into focused, single-responsibility modules.

**Impact**:
- **Maintainability**: Easier to understand and modify
- **Testability**: Smaller, focused units are easier to test
- **Code quality**: Enforces single responsibility principle
- **Developer velocity**: Faster to navigate and debug

---

## Goals

1. **Eliminate file size violations**: All 7 files split to <500 lines each
2. **Maintain functionality**: 100% test coverage preserved
3. **Improve structure**: Better separation of concerns
4. **No regressions**: All existing tests pass
5. **Type safety**: mypy --strict passes

---

## Scope: 7 Files to Refactor

### CRITICAL Priority (>800 lines)

#### 1. app/watchlist/service.py - 1306 lines (261% over limit)
**Current state**:
- Monolithic service mixing CRUD, scoring, and snapshots
- Three 100+ line functions
- `refresh_watchlist_scores` (280 lines), `get_items_with_scores` (120 lines), `get_item_with_score_by_id` (110 lines)

**Target split**:
```
app/watchlist/
  ├── watchlist_service.py (~400 lines) - Core CRUD operations
  ├── scoring_service.py (~400 lines) - Scoring logic
  └── snapshot_service.py (~400 lines) - Snapshot management
```

**Refactoring approach** (from CODE_AUDIT.md):
- Extract `_gather_inputs_for_symbol` helper
- Extract `_process_single_item` helper
- Extract `_build_item_response` helper (used by 2 functions)

---

### HIGH Priority (600-800 lines)

#### 2. app/tasks/agent_tasks.py - 786 lines (157% over limit)
**Current state**:
- Mixed concerns: watchlist tasks, data ingestion, indicators
- Three 100+ line functions
- SRP violations

**Target split**:
```
app/tasks/
  ├── watchlist_tasks.py (~250 lines) - Watchlist refresh tasks
  ├── data_ingestion_tasks.py (~250 lines) - OHLCV ingestion
  └── indicator_tasks.py (~250 lines) - Technical indicator updates
```

**Refactoring approach**:
- Split `refresh_watchlist_scores_task` into separate task + auto-backfill task
- Extract `_prepare_dataframe_for_ingestion` helper
- Move SQL to storage layer

#### 3. app/api/watchlist.py - 745 lines (149% over limit)
**Current state**:
- Many endpoint handlers
- Duplicate response construction logic

**Target split**:
```
app/api/
  ├── watchlist.py (~400 lines) - Endpoint handlers only
app/watchlist/
  └── response_builders.py (~300 lines) - Response construction
```

**Refactoring approach**:
- Create `WatchlistItemResponse.from_service_dict()` class method
- Extract response building to separate module

#### 4. app/watchlist/narrative.py - 628 lines (126% over limit)
**Current state**:
- Signal classification + narrative generation mixed
- `classify_signal` (100 lines) - complex rule engine

**Target split**:
```
app/watchlist/
  ├── signal_classifier.py (~300 lines) - Signal classification
  └── narrative_generator.py (~300 lines) - Narrative text generation
```

**Refactoring approach**:
- Refactor `classify_signal` to rule-based pattern
- Extract bullet generation functions

---

### MEDIUM Priority (500-600 lines)

#### 5. app/api/health.py - 572 lines (114% over limit)
**Current state**:
- Health checks + quota management mixed
- Hardcoded quota_map dict (large)

**Target approach**:
```
app/api/
  ├── health.py (~350 lines) - Health endpoints only
app/config/
  └── quota_config.json (~new file) - Quota configuration
app/utils/
  └── quota_helpers.py (~150 lines) - Quota calculation helpers
```

#### 6. app/sources/rest_api_source.py - 544 lines (109% over limit)
**Current state**:
- Three ~80 line methods with duplicate pattern
- `fetch_day_bars`, `fetch_reference_payload`, `fetch_news_payload`

**Target approach**:
```
app/sources/
  └── rest_api_source.py (~350 lines) - Generic pattern extracted
```

**Refactoring approach**:
- Create `_generic_api_fetch()` method
- Pass callbacks for type-specific processing

#### 7. app/analytics/paper_trading.py - 504 lines (101% over limit)
**Current state**:
- `update_paper_trades` (150 lines) - nested exit conditions
- `create_paper_trade` (80 lines)

**Target approach**:
```
app/analytics/
  └── paper_trading.py (~400 lines) - Extracted helpers
```

**Refactoring approach**:
- Extract `_check_exit_conditions()` helper
- Extract `_update_single_trade()` helper
- Extract data gathering steps

---

## Functional Requirements

### FR-1: Refactor watchlist/service.py (CRITICAL)
- Split into 3 files: watchlist_service, scoring_service, snapshot_service
- Each file <500 lines
- Extract helper functions per CODE_AUDIT recommendations
- Update all imports in dependent files
- All tests pass

### FR-2: Refactor tasks/agent_tasks.py (HIGH)
- Split into 3 files: watchlist_tasks, data_ingestion_tasks, indicator_tasks
- Each file <300 lines
- Separate auto-backfill logic into new task
- Move SQL to storage layer
- All tests pass

### FR-3: Refactor api/watchlist.py (HIGH)
- Extract response builders to watchlist/response_builders.py
- Create factory methods for response construction
- api/watchlist.py <400 lines
- All tests pass

### FR-4: Refactor watchlist/narrative.py (HIGH)
- Split into signal_classifier.py and narrative_generator.py
- Each file <350 lines
- Refactor classify_signal to rule-based pattern
- All tests pass

### FR-5: Refactor api/health.py (MEDIUM)
- Extract quota_map to config/quota_config.json
- Extract helpers to utils/quota_helpers.py
- health.py <400 lines
- All tests pass

### FR-6: Refactor sources/rest_api_source.py (MEDIUM)
- Create generic _generic_api_fetch method
- Refactor 3 fetch methods to use generic pattern
- rest_api_source.py <400 lines
- All tests pass

### FR-7: Refactor analytics/paper_trading.py (MEDIUM)
- Extract helper functions per CODE_AUDIT recommendations
- paper_trading.py <450 lines
- All tests pass

### FR-8: Quality Gates (ALL)
- mypy --strict passes
- ruff check passes
- 100% test coverage maintained
- No duplicate logic introduced
- All imports updated correctly

---

## Non-Goals

**Explicitly OUT OF SCOPE**:
- ❌ Changing business logic (behavior must remain identical)
- ❌ Adding new features
- ❌ Performance optimization (beyond better structure)
- ❌ Replacing Any types (separate PRD #0026)
- ❌ Refactoring files <500 lines

---

## Technical Considerations

### Import Updates
- Many files import from these modules
- Use grep to find ALL import statements
- Update systematically

### Test Updates
- Tests may import from old locations
- Update test imports
- Verify coverage doesn't drop

### Circular Import Risk
- Be careful splitting related modules
- May need to extract interfaces/types to separate file

### Git History
- Use `git mv` where possible to preserve history
- Document splits in commit messages

---

## Success Metrics

### File Size Compliance
- ✅ watchlist/service.py: 1306 → <500 (split to 3 files)
- ✅ tasks/agent_tasks.py: 786 → <500 (split to 3 files)
- ✅ api/watchlist.py: 745 → <400
- ✅ watchlist/narrative.py: 628 → <500 (split to 2 files)
- ✅ api/health.py: 572 → <400
- ✅ sources/rest_api_source.py: 544 → <400
- ✅ analytics/paper_trading.py: 504 → <450

### Quality Gates
- ✅ All tests pass (pytest tests/ -v)
- ✅ mypy --strict passes
- ✅ ruff check passes
- ✅ Coverage ≥85% (same as before)
- ✅ No duplicate code introduced

### Code Quality
- ✅ Single responsibility per module
- ✅ Function cohesion improved
- ✅ Easier to navigate (verified by code review)

---

## Implementation Approach

### Phase 1: Critical - watchlist/service.py (6-8 hours)
1. Create new files: watchlist_service, scoring_service, snapshot_service
2. Extract helpers as recommended
3. Move functions to appropriate modules
4. Update imports
5. Run tests, fix issues
6. Verify mypy/ruff

### Phase 2: High Priority - 3 files (8-10 hours)
1. tasks/agent_tasks.py → 3 task files (3 hours)
2. api/watchlist.py → extract response builders (2-3 hours)
3. watchlist/narrative.py → 2 files (3-4 hours)

### Phase 3: Medium Priority - 3 files (4-6 hours)
1. api/health.py → extract quota config (2 hours)
2. sources/rest_api_source.py → generic pattern (1-2 hours)
3. analytics/paper_trading.py → extract helpers (1-2 hours)

### Phase 4: Final Verification (1-2 hours)
1. Run full test suite
2. Run quality checks
3. Manual code review
4. Update documentation if needed

---

## Risks & Mitigations

### Risk: Breaking existing functionality
**Mitigation**:
- Run tests after each file split
- Maintain 100% test coverage
- Use TDD: ensure tests pass before refactoring

### Risk: Circular imports
**Mitigation**:
- Extract shared types to separate module
- Use dependency injection
- Import at function level if necessary (as last resort)

### Risk: Time overrun (20-24 hours is significant)
**Mitigation**:
- Do in phases (commit after each file)
- Can pause between phases
- Each phase delivers value independently

### Risk: Import update errors
**Mitigation**:
- Use comprehensive grep to find ALL imports
- Update systematically
- mypy will catch missing imports

---

## Testing Plan

### After Each File Split
```bash
# Run full test suite
cd backend && source .venv/bin/activate
pytest tests/ -v

# Run type checking
mypy app/ --strict

# Run linting
ruff check app/
```

### After Each Phase
```bash
# Run coverage check
pytest tests/ --cov=app --cov-report=term-missing

# Verify coverage didn't drop
# Target: ≥85%

# Run quality report
bash ~/.claude/skills/code-quality/scripts/quality-report.sh backend/app
# Verify file count decreased
```

---

## Dependencies

- All existing tests must be passing
- Access to backend/app/ directory
- pytest, mypy, ruff installed
- Understanding of module structure

---

## Estimated Effort Breakdown

| Task | Effort | Complexity |
|------|--------|------------|
| watchlist/service.py | 6-8 hours | HIGH |
| tasks/agent_tasks.py | 3-4 hours | MEDIUM |
| api/watchlist.py | 2-3 hours | MEDIUM |
| watchlist/narrative.py | 3-4 hours | MEDIUM |
| api/health.py | 2 hours | LOW-MEDIUM |
| sources/rest_api_source.py | 1-2 hours | LOW-MEDIUM |
| analytics/paper_trading.py | 1-2 hours | LOW-MEDIUM |
| Testing & verification | 2-3 hours | MEDIUM |
| **TOTAL** | **20-28 hours** | **HIGH** |

**Recommended**: Split into 3-4 work sessions
- Session 1: watchlist/service.py (CRITICAL)
- Session 2: HIGH priority files (3 files)
- Session 3: MEDIUM priority files (3 files)
- Session 4: Final verification

---

## Success Criteria Summary

✅ **COMPLETE when**:
1. All 7 files under size limits
2. No new files exceed 500 lines
3. All tests pass (pytest)
4. mypy --strict passes
5. ruff check passes
6. Coverage ≥85%
7. No duplicate logic
8. Code review confirms improved structure
9. Documentation updated (if module structure changed significantly)

---

## Follow-up PRDs

After this refactoring:
- **Type System Cleanup** - Replace Any types (easier in smaller files)
- **Further Code Quality** - Additional patterns identified during refactoring

**This is Phase 1** - addresses the most critical file size violations.
