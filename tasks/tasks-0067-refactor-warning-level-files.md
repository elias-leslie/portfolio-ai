# Task List: Refactor WARNING-Level Files

**Source**: Code review - Cloud agent analysis (2025-11-15)
**Complexity**: Medium-Complex
**Effort**: MEDIUM-HIGH (8-12 hours total, 1-3 hours per file)
**Environment**: Local Dev
**Created**: 2025-11-15
**Status**: NOT STARTED
**Priority**: Medium (defer until after Task 0065, 0066 complete)

---

## Summary

**Goal**: Refactor 11 files exceeding 500-line soft limit (but under 800-line hard limit) to improve maintainability and approach target file size.

**Approach**: Review each file, identify natural module boundaries, extract focused modules where clear split exists, document justification for files that should remain as-is.

**Scope Discovery**: Completed (cloud agent code review identified all violations)

**Priority Note**: This task is OPTIONAL and MEDIUM priority. Focus on Task 0065 (ai_analyzer blocker) and Task 0066 (CRITICAL file splits) first. This task can be deferred or done incrementally.

**Impact**:
- ✅ Reduces WARNING-level file count (11 → target 5-7)
- ✅ Improves code maintainability for complex modules
- ✅ Better compliance with 500-line soft limit guideline
- ⚠️ Not urgent (all files under 800-line hard limit)

---

## Problem Statement

**Current State** (2025-11-15):

**File Size Warnings** (per `quality-report.sh backend/app --quick`):
1. **services/gap_detector.py**: 804 lines ⚠️ (just over hard limit)
2. **api/capabilities.py**: 798 lines ⚠️ (just under hard limit)
3. **tasks/market_data_tasks.py**: 753 lines ⚠️
4. **watchlist/watchlist_service.py**: 733 lines ⚠️
5. **watchlist/scoring_service.py**: 644 lines ⚠️
6. **agents/workflow_orchestrator.py**: 631 lines ⚠️
7. **services/news_vendor_manager.py**: 565 lines ⚠️
8. **services/news_quality_metrics.py**: 532 lines ⚠️
9. **watchlist/fundamentals.py**: 531 lines ⚠️
10. **sources/finnhub_source.py**: 463 lines (approaching soft limit)
11. **sources/fmp_source.py**: 455 lines (approaching soft limit)

**Code Quality Standards** (from DEVELOPMENT.md:518-533):
- **Soft Limit**: 500 lines (review file, consider splitting if multiple responsibilities)
- **Hard Limit**: 800 lines (requires architectural justification)
- **Rationale**: Balance readability with practical complexity, avoid artificial splits

**Why Review These Files**:
- All exceed soft limit (500L) by 10-60%
- Some approach or exceed hard limit (gap_detector, capabilities)
- Opportunity to improve maintainability if clear boundaries exist
- Not urgent (all under or just at hard limit)

---

## Tasks

### Phase 1: Assess & Prioritize (1-2 hours)

- [ ] 1.1 Review gap_detector.py (804 lines) **[HIGHEST PRIORITY - over hard limit]**
  - **Current structure**: TypedDict definitions + GapDetector service class
  - **Split candidate**: Extract TypedDict definitions to `gap_types.py`
  - **Estimated extraction**: ~100 lines (TypedDict definitions) → gap_types.py
  - **Remaining**: ~700 lines (still large, but under hard limit)
  - **Decision**: SPLIT (TypedDict extraction is clean boundary)
  - **Effort**: LOW (1-2 hours)

- [ ] 1.2 Review api/capabilities.py (798 lines) **[HIGH PRIORITY - just under hard limit]**
  - **Current structure**: Multiple FastAPI router endpoints
  - **Split candidate**: Group endpoints by function
    - Scanning endpoints (trigger scans, refresh) → `api/capabilities_scanning.py`
    - AI insights endpoints (get insights, review, dismiss) → `api/capabilities_insights.py`
    - Query endpoints (list, filter, stats) → `api/capabilities_query.py`
  - **Estimated extraction**: 3 files × ~250 lines each
  - **Main file**: ~50 lines (imports + router registration)
  - **Decision**: EVALUATE (check if endpoint grouping makes sense)
  - **Effort**: MEDIUM (3-4 hours if split)

- [ ] 1.3 Review market_data_tasks.py (753 lines)
  - **Current structure**: Multiple Celery tasks for market data
  - **Split candidate**: Group by data type
    - Price/OHLCV tasks → `market_data_price_tasks.py`
    - Fear & Greed tasks → `market_data_fear_greed_tasks.py`
    - Maintenance tasks → `market_data_maintenance_tasks.py`
  - **Estimated extraction**: 3 files × ~250 lines each
  - **Decision**: EVALUATE (check if task grouping makes sense)
  - **Effort**: MEDIUM (2-3 hours if split)

- [ ] 1.4 Review watchlist_service.py (733 lines)
  - **Current structure**: WatchlistService class with many methods
  - **Split candidate**: Extract repository layer or complex operations
  - **Note**: Already has watchlist_repository.py (145 lines), may be well-organized
  - **Decision**: REVIEW (may be appropriate size for service class)
  - **Effort**: TBD (check if natural boundaries exist)

- [ ] 1.5 Review scoring_service.py (644 lines)
  - **Current structure**: WatchlistScoringService class
  - **Split candidate**: Extract scoring algorithms or calculation logic
  - **Decision**: REVIEW (service class may be appropriate size)
  - **Effort**: TBD

- [ ] 1.6 Review workflow_orchestrator.py (631 lines)
  - **Current structure**: WorkflowOrchestrator class (10 methods)
  - **Note**: Recently created for Task 0060 Task 3.7 (multi-agent collaboration)
  - **Decision**: KEEP AS-IS (new code, well-organized, under 800L)
  - **Justification**: Single-responsibility orchestrator, 10 methods is reasonable
  - **Effort**: ZERO (no changes)

- [ ] 1.7 Review news_vendor_manager.py (565 lines)
  - **Current structure**: NewsVendorManager class
  - **Split candidate**: Extract vendor registry or health monitoring
  - **Decision**: EVALUATE (check for clear boundaries)
  - **Effort**: TBD

- [ ] 1.8 Review news_quality_metrics.py (532 lines)
  - **Current structure**: Quality metrics calculation logic
  - **Split candidate**: Extract metric calculations by type
  - **Decision**: EVALUATE (check for natural groupings)
  - **Effort**: TBD

- [ ] 1.9 Review fundamentals.py (531 lines)
  - **Current structure**: Fundamental data fetching logic
  - **Decision**: REVIEW (may be appropriate for data fetching module)
  - **Effort**: TBD

- [ ] 1.10 Review source files (finnhub_source.py: 463L, fmp_source.py: 455L)
  - **Note**: Source adapters typically have similar structure (fetch methods)
  - **Decision**: KEEP AS-IS (source adapters are inherently verbose, under 500L)
  - **Justification**: Fetch methods for different data types, natural module size
  - **Effort**: ZERO (no changes)

- [ ] 1.11 Create split plan document
  - Document: Which files to split, which to keep
  - Estimate: Effort per file (LOW/MEDIUM/HIGH)
  - Prioritize: By impact × (1/effort)
  - Output: Markdown file with decisions and justifications

---

### Phase 2: Execute High-Priority Splits (4-6 hours)

#### 2.1 Split gap_detector.py (MANDATORY - over hard limit)

- [ ] 2.1.1 Extract TypedDict definitions to `services/gap_types.py`
  - Copy: Lines with TypedDict definitions (CapabilityRequirement, GapInfo, CoverageResult, GapAnalysisResult)
  - Estimated: ~100 lines
  - Module docstring: "Type definitions for gap detection system."
  - Format: `ruff format services/gap_types.py`

- [ ] 2.1.2 Update gap_detector.py imports
  - Add: `from .gap_types import CapabilityRequirement, GapInfo, CoverageResult, GapAnalysisResult`
  - Remove: TypedDict definitions from gap_detector.py
  - Verify: `mypy services/gap_detector.py --strict` passes

- [ ] 2.1.3 Update dependent imports
  - Search: `grep -r "from.*gap_detector import.*Gap" backend/app --include="*.py"`
  - Update: Any imports of type definitions to use gap_types
  - Verify: All imports resolve

- [ ] 2.1.4 Test and verify
  - Test: `pytest tests/ -k gap -v`
  - Verify: Gap detection still works
  - Check: File sizes (gap_detector.py should be ~700L, gap_types.py ~100L)
  - Lint: `ruff check services/gap_detector.py services/gap_types.py`

#### 2.2 Evaluate and Split api/capabilities.py (if warranted)

- [ ] 2.2.1 Analyze endpoint groupings
  - List: All endpoints in capabilities.py
  - Group: By logical function (scanning, insights, query)
  - Count: Endpoints per group
  - Decide: Is split worthwhile? (if groups are unbalanced, may not be worth it)

- [ ] 2.2.2 IF SPLIT DECIDED: Extract scanning endpoints
  - Create: `api/capabilities_scanning.py`
  - Extract: Scan trigger, refresh endpoints
  - Router: Create new APIRouter for scanning
  - Estimated: ~250 lines

- [ ] 2.2.3 IF SPLIT DECIDED: Extract insights endpoints
  - Create: `api/capabilities_insights.py`
  - Extract: Get insights, review, dismiss, annotate endpoints
  - Router: Create new APIRouter for insights
  - Estimated: ~250 lines

- [ ] 2.2.4 IF SPLIT DECIDED: Extract query endpoints
  - Create: `api/capabilities_query.py`
  - Extract: List, filter, stats, summary endpoints
  - Router: Create new APIRouter for query
  - Estimated: ~250 lines

- [ ] 2.2.5 IF SPLIT DECIDED: Update main capabilities.py
  - Keep: Main router registration
  - Add: Include sub-routers from new files
  - Size: ~50-100 lines
  - Test: All endpoints still accessible

- [ ] 2.2.6 Test and verify (if split)
  - Test: `pytest tests/api/ -v`
  - Verify: All capability endpoints respond
  - Check: File sizes (3 files ~250L each)
  - Lint: `ruff check api/capabilities*.py`

#### 2.3 Evaluate and Split market_data_tasks.py (if warranted)

- [ ] 2.3.1 Analyze task groupings
  - List: All Celery tasks in market_data_tasks.py
  - Group: By data type (price, fear_greed, maintenance)
  - Count: Tasks per group
  - Decide: Is split worthwhile?

- [ ] 2.3.2 IF SPLIT DECIDED: Extract price tasks
  - Create: `tasks/market_data_price_tasks.py`
  - Extract: OHLCV fetching, price maintenance tasks
  - Estimated: ~250 lines

- [ ] 2.3.3 IF SPLIT DECIDED: Extract fear & greed tasks
  - Create: `tasks/market_data_fear_greed_tasks.py`
  - Extract: Fear & Greed calculation, update tasks
  - Estimated: ~250 lines

- [ ] 2.3.4 IF SPLIT DECIDED: Extract maintenance tasks
  - Create: `tasks/market_data_maintenance_tasks.py`
  - Extract: Data refresh, cleanup, validation tasks
  - Estimated: ~250 lines

- [ ] 2.3.5 IF SPLIT DECIDED: Update Celery beat schedule
  - File: `celery_app.py`
  - Update: Task paths in beat_schedule (if changed)
  - Verify: All scheduled tasks still registered

- [ ] 2.3.6 Test and verify (if split)
  - Test: Trigger each task type manually
  - Verify: All tasks execute successfully
  - Check: File sizes (3 files ~250L each)
  - Lint: `ruff check tasks/market_data*.py`

---

### Phase 3: Review Remaining Files (2-3 hours)

- [ ] 3.1 Review watchlist_service.py (733 lines)
  - Analyze: Class structure, method count, responsibilities
  - Check: Is repository pattern already in use? (watchlist_repository.py exists)
  - Decide: Keep as-is or extract complex operations
  - Document: Decision and justification
  - Action: SPLIT / KEEP / DEFER

- [ ] 3.2 Review scoring_service.py (644 lines)
  - Analyze: Scoring algorithms, calculation logic
  - Check: Can scoring algorithms be extracted?
  - Decide: Keep as-is or extract scoring logic
  - Document: Decision and justification
  - Action: SPLIT / KEEP / DEFER

- [ ] 3.3 Review news_vendor_manager.py (565 lines)
  - Analyze: Vendor registry, health monitoring, manager logic
  - Check: Can vendor registry be separated from health monitoring?
  - Decide: Keep as-is or extract components
  - Document: Decision and justification
  - Action: SPLIT / KEEP / DEFER

- [ ] 3.4 Review news_quality_metrics.py (532 lines)
  - Analyze: Metric calculation types (quality, relevance, freshness, etc.)
  - Check: Can metrics be grouped by type?
  - Decide: Keep as-is or extract metric types
  - Document: Decision and justification
  - Action: SPLIT / KEEP / DEFER

- [ ] 3.5 Review fundamentals.py (531 lines)
  - Analyze: Fundamental data fetching logic
  - Check: Is size appropriate for data fetching module?
  - Decide: Keep as-is or extract by data source
  - Document: Decision and justification
  - Action: SPLIT / KEEP / DEFER

- [ ] 3.6 Document all decisions
  - Create: `docs/reference/file-size-review-2025-11.md`
  - Document: All files reviewed, split decisions, justifications
  - Include: Before/after file sizes
  - Note: Files kept as-is with architectural justification

---

### Phase 4: Final Verification (1 hour)

- [ ] 4.1 Run code quality audit
  - Command: `bash ~/portfolio-ai/.claude/skills/code-quality/scripts/quality-report.sh backend/app --quick`
  - Verify: Reduced WARNING count (11 → target 5-7)
  - Document: New file size distribution
  - Note: Files over 500L with justification

- [ ] 4.2 Run full test suite
  - Command: `cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/ -v`
  - Verify: ALL 508 tests pass
  - Check: No regressions from splits
  - Monitor: Test duration unchanged

- [ ] 4.3 Verify services restart
  - Restart: `bash ~/portfolio-ai/scripts/restart.sh`
  - Verify: All services start successfully
  - Check: No import errors in logs
  - Test: API endpoints respond correctly

- [ ] 4.4 Update documentation
  - File: `docs/core/DEVELOPMENT.md` (if module structure changed)
  - Document: New module organization (if splits occurred)
  - Update: File size guidelines with latest audit results
  - Note: Architectural justifications for large files kept as-is

---

## Verification Checklist

- [ ] **File Size Improvements**
  - [ ] gap_detector.py: <800 lines (was 804L)
  - [ ] gap_types.py: Created (~100L)
  - [ ] capabilities.py: Reduced or justified (if kept at 798L)
  - [ ] market_data_tasks.py: Reduced or justified (if kept at 753L)
  - [ ] Other WARNING files: Reviewed and documented

- [ ] **Quality Metrics**
  - [ ] WARNING-level files: Reduced from 11 to 5-7
  - [ ] All files: Under 800-line hard limit
  - [ ] Soft limit (500L): Improved compliance or justified exceptions

- [ ] **Tests**
  - [ ] All 508 tests pass
  - [ ] No import errors
  - [ ] No performance regression

- [ ] **Code Quality**
  - [ ] `~/portfolio-ai/scripts/lint.sh` passes
  - [ ] `mypy backend/app --strict` zero errors
  - [ ] All files formatted with `ruff format`

- [ ] **Runtime Verification**
  - [ ] Services restart successfully
  - [ ] API responds to requests
  - [ ] Scheduled tasks execute without errors

- [ ] **Documentation**
  - [ ] Split decisions documented
  - [ ] Architectural justifications for large files
  - [ ] File size audit results updated

---

## Success Criteria

1. **Gap detector compliant**: gap_detector.py under 800L hard limit (was 804L)
2. **Reduced WARNING count**: 11 WARNING files → 5-7 (50% reduction target)
3. **Justified exceptions**: Large files kept have documented architectural reasons
4. **Zero regressions**: All 508 tests pass, services stable
5. **Documentation complete**: All decisions and justifications documented
6. **Quality improved**: Easier to navigate, test, maintain

---

## Notes

**Priority Guidance**:
- **MUST DO**: gap_detector.py (804L, over hard limit)
- **SHOULD EVALUATE**: capabilities.py (798L), market_data_tasks.py (753L)
- **OPTIONAL**: Other WARNING files (can defer)
- **SKIP**: workflow_orchestrator.py (recent, well-organized), source files (inherently verbose)

**Decision Framework**:
For each file, ask:
1. Does clear module boundary exist? (clean split point)
2. Would split improve maintainability? (easier testing, debugging, navigation)
3. Is effort justified by benefit? (avoid artificial splits)
4. Can we document architectural justification if keeping as-is?

**Effort vs Impact**:
- **HIGH IMPACT, LOW EFFORT**: gap_detector.py (TypedDict extraction)
- **MEDIUM IMPACT, MEDIUM EFFORT**: capabilities.py, market_data_tasks.py (if clear groupings)
- **LOW IMPACT**: Other WARNING files (defer or justify)

**Risk Mitigation**:
- Test after each split
- Keep changes minimal (avoid over-refactoring)
- Document justifications for files kept large
- Can defer optional splits to future work

**Estimated Effort Breakdown**:
- Phase 1 (Assessment): 1-2 hours
- Phase 2 (High-priority splits): 4-6 hours
- Phase 3 (Review remaining): 2-3 hours
- Phase 4 (Verification): 1 hour
- **Total**: 8-12 hours

**Related Work**:
- Task 0066: Split CRITICAL files (completes before this)
- PRD #0024: Code quality refactoring (broader quality effort, 70% complete)
