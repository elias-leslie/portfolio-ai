# Task List: Comprehensive Code Quality Cleanup

<!-- PAUSED: 2025-11-16 | Context: 73% | Reason: User request | Next: Phase 2 - Task 2.1 (Refactor CRITICAL long functions) -->

**Source**: User request via /task_it
**Complexity**: Complex
**Effort**: HIGH (20-30 hours total, ~12 hours remaining)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-16 17:30
**Status**: PAUSED (Option B - Pragmatic approach)
**Last Updated**: 2025-11-16
**Pause Reason**: User request (73% context used, good stopping point)
**Context Used**: 150K/200K (73%)
**Completed This Session**: Phase 0 (Scope Discovery) + Phase 1 (SQL Injection Fixes - 12/12)
**Next Action**: Phase 2 Task 2.1 - Refactor ml_training_tasks.py (286 lines)
**Resume Command**: `/do_it tasks-0069-comprehensive-code-quality-cleanup.md` or `/do_it`

---

## Summary

**Goal**: Fix ALL code quality issues from baseline report - 46 critical, 121 warning, 158 medium issues. Zero tolerance for skipping pre-existing issues. Systematic cleanup with quality gates at each phase.

**Approach**: Phased approach prioritizing security > complexity > type safety > file size. Each phase has verification gates before proceeding to next. Use parallel subagent dispatch where safe.

**Scope Discovery**: Required for SQL injection and Any type patterns

---

## Tasks

### 0.0 ✅ COMPLETE Scope Discovery (MANDATORY)

- [x] 0.1 Run Explore subagent for SQL injection patterns (very thorough)
  - Found: 10 instances (6 CRITICAL, 4 WARNING)
  - Patterns: Dynamic table/column names, f-string SQL
  - Complete list with file:line:code provided
- [x] 0.2 Run Explore subagent for Any type usages (very thorough)
  - Found: 614 total usages
  - Categorized: 19 trivial, 187 moderate, 38 complex (skip), rest contextual
  - Grouped list by fixability provided
- [x] 0.3 Update task list with discovered scope
  - SQL injection: 12 instances total (found 2 bonus during verification)
  - Any types: Focus on 19 trivial + core TypedDict models
  - Effort estimates updated based on findings
- [x] 0.4 Checkpoint: Confirm scope before proceeding
  - SQL injection risks: 12 files (10 original + 2 found during verification)
  - Any types: 206 fixable (19 trivial, 187 moderate), 38 skip (framework limitations)
  - Estimated effort: 32-40 hours → User selected Option B (20-25 hours)
  - Architectural concerns: None major

**User Decision**: Option B (Pragmatic) - Focus on security + critical complexity + quick type wins

### 1.0 ✅ COMPLETE PHASE 1: CRITICAL Security - SQL Injection Fixes (P0)

**Baseline**: 2 SQL injection risks detected → **Final: 12 instances fixed**

- [x] 1.1 ✅ Fixed backend/app/agents/workflow_orchestrator.py:158 + storage files (6 CRITICAL)
  - metadata.py: Information schema validation
  - ingestion.py: Validate table/column before DELETE
  - status_data.py: Pre-validate all table/column configs
  - workflow_orchestrator.py: Whitelist column validation
  - peer_algorithms.py: Document group_by whitelist
  - capability_db_scanner.py: Document SQLAlchemy validation
- [x] 1.2 ✅ All 12 instances addressed (10 original + 2 found during verification)
  - 6 CRITICAL: Added validation logic (information_schema, whitelists)
  - 4 WARNING: Documented existing safe patterns
  - 2 BONUS: Found and fixed during ruff S608 check
- [x] 1.3 ✅ Validation strategies implemented
  - Information schema validation for dynamic names
  - Whitelist validation for controlled column sets
  - Documented SQLAlchemy inspector sources (already safe)
  - Added "# validated:" comments for audit trail
- [x] 1.4 ✅ Verification gate PASSED
  - Ruff S608: All flagged items validated or fixed
  - Grep check: All f-string SQL has validation markers
  - Mypy: Clean (fixed tuple->list for PostgreSQL)
  - Committed: d66a7f3

### 2.0 PHASE 2: CRITICAL Complexity - Long Functions (P0)

**Baseline**: 8 CRITICAL functions >100 lines (up to 286 lines)

- [ ] 2.1 Refactor backend/app/tasks/ml_training_tasks.py:63 - _retrain_article_quality_model_impl (286 lines)
  - Extract: Data preparation (loading, cleaning)
  - Extract: Model training logic
  - Extract: Evaluation and metrics
  - Extract: Model persistence
  - Target: <75 lines per function
- [ ] 2.2 Refactor backend/app/tasks/market_data_tasks.py:419 - populate_fear_greed_inputs (182 lines)
  - Extract: FRED data fetching
  - Extract: Market breadth calculation
  - Extract: Data aggregation/storage
  - Target: <75 lines per function
- [ ] 2.3 Refactor backend/app/tasks/indicator_tasks.py:224 - calculate_fear_greed (277 lines)
  - Extract: Signal collection by type
  - Extract: Score calculation per signal
  - Extract: Final aggregation
  - Target: <75 lines per function
- [ ] 2.4 Refactor backend/app/tasks/backtest_tasks.py:26 - run_backtest_task (134 lines)
  - Extract: Data loading and validation
  - Extract: Replay execution
  - Extract: Performance calculation
  - Target: <75 lines per function
- [ ] 2.5 Refactor backend/app/tasks/news_profiling_tasks.py:136 - profile_news_sources_task (135 lines)
  - Extract: Source scanning
  - Extract: Metrics calculation
  - Extract: Profile persistence
  - Target: <75 lines per function
- [ ] 2.6 Refactor remaining 3 CRITICAL long functions (>100 lines)
  - backend/app/tasks/reference_tasks.py:192 - parse_valuation_metrics (119 lines)
  - backend/app/tasks/reference_tasks.py:412 - refresh_alphavantage_reference_backup (105 lines)
  - backend/app/tasks/gap_analysis_tasks.py:185 - alert_critical_gaps (104 lines)
  - Apply same extraction pattern
- [ ] 2.7 Verification gate
  - Run: quality-report.sh --quick
  - Confirm: 0 CRITICAL long functions (>100 lines)
  - Confirm: All functions <75 lines (target)
  - Test: Run full test suite (pytest tests/)

### 3.0 PHASE 3: WARNING File Sizes (P1)

**Baseline**: 14 files >500 lines (500-804 lines)

**Strategy**: Group by related functionality, refactor in batches

- [ ] 3.1 Refactor gap_detector.py (804 lines) - Largest file
  - Split: Gap detection engine (core logic)
  - Split: Gap analysis strategies (different gap types)
  - Split: Report generation
  - Split: Database persistence
  - Target: <500 lines per file
- [ ] 3.2 Refactor capabilities.py (798 lines)
  - Split: Scanner implementations (DB, Celery, Endpoints)
  - Split: Analysis engine
  - Split: Insight generators
  - Target: <500 lines per file
- [ ] 3.3 Refactor maintenance.py (764 lines)
  - Split: Maintenance task wrappers
  - Split: Status/history queries
  - Split: Manual trigger handlers
  - Target: <500 lines per file
- [ ] 3.4 Refactor market_data_tasks.py (753 lines)
  - Split: Fear & Greed data pipeline
  - Split: Options data pipeline
  - Split: Market breadth calculations
  - Target: <500 lines per file
- [ ] 3.5 Refactor watchlist_service.py (733 lines)
  - Split: Snapshot building
  - Split: Score management
  - Split: News parsing
  - Target: <500 lines per file
- [ ] 3.6 Refactor scoring_service.py (644 lines)
  - Split: Context initialization
  - Split: Ticker processing
  - Split: Batch operations
  - Target: <500 lines per file
- [ ] 3.7 Refactor remaining 8 WARNING files (500-631 lines)
  - workflow_orchestrator.py (631 lines)
  - news_vendor_manager.py (565 lines)
  - ai_analyzer.py (555 lines)
  - news_quality_metrics.py (532 lines)
  - fundamentals.py (531 lines)
  - celery_app.py (530 lines)
  - finnhub_source.py (463 lines)
  - fmp_source.py (455 lines)
  - Apply focused module extraction
- [ ] 3.8 Verification gate
  - Run: quality-report.sh --quick
  - Confirm: 0 files >500 lines (all under soft limit)
  - Confirm: All new modules <300 lines (target)
  - Test: Run full test suite

### 4.0 PHASE 4: Any Type Cleanup (P2)

**Baseline**: 174 Any type usages

**Strategy**: Categorize by complexity, fix in waves (trivial → moderate → complex)

- [ ] 4.1 Fix trivial Any types (estimated 60-80 instances)
  - Pattern: `from typing import Any` with no actual usage
  - Pattern: Generic containers that can use TypedDict
  - Pattern: JSON responses that have known schemas
  - Use: Grep + batch replacement
- [ ] 4.2 Fix moderate Any types (estimated 50-70 instances)
  - Pattern: Function params/returns with inferable types
  - Pattern: Redis/Cache values with known types
  - Pattern: Dict[str, Any] with consistent structure → TypedDict
  - Use: File-by-file review
- [ ] 4.3 Fix complex Any types (estimated 30-50 instances)
  - Pattern: Celery self/request objects
  - Pattern: External library responses (yfinance, etc)
  - Pattern: Dynamic DB query results
  - Strategy: Use generics, protocols, or cast with comments
- [ ] 4.4 Verification gate
  - Run: quality-report.sh --quick
  - Target: <50 Any types (70% reduction)
  - Stretch: <20 Any types (88% reduction)
  - Confirm: mypy --strict passes

### 5.0 PHASE 5: Multiple Concerns Files (P2)

**Baseline**: 28 files with multiple concerns (>5 classes or >10 functions)

- [ ] 5.1 Refactor 2 CRITICAL multiple concern files
  - backend/app/api/capabilities.py (8 classes, 11 functions)
  - backend/app/api/maintenance.py (6 classes, 14 functions)
  - Strategy: Split by API resource (one file per endpoint group)
- [ ] 5.2 Refactor 26 WARNING multiple concern files
  - Group by module (watchlist, api, services, etc)
  - Apply single responsibility principle
  - Create focused submodules
- [ ] 5.3 Verification gate
  - Run: quality-report.sh --quick
  - Confirm: 0 CRITICAL (>10 classes or >15 functions)
  - Target: <5 WARNING files (80% reduction)

### 6.0 PHASE 6: Technical Debt (TODOs) (P3)

**Baseline**: 13 TODOs/FIXMEs

- [ ] 6.1 Categorize TODOs by priority
  - CRITICAL: Blocking functionality or security
  - HIGH: Missing features affecting UX
  - MEDIUM: Nice-to-have improvements
  - LOW: Future enhancements
- [ ] 6.2 Resolve or document all TODOs
  - CRITICAL/HIGH: Implement now
  - MEDIUM: Create follow-up tasks
  - LOW: Move to backlog or remove
- [ ] 6.3 Verification gate
  - Confirm: 0 TODO/FIXME comments in code
  - Confirm: All deferred work in WORK_TRACKER.md

### 7.0 PHASE 7: Final Verification & Documentation

- [ ] 7.1 Run comprehensive quality check
  - Baseline: 46 critical, 121 warning, 158 medium
  - Target: 0 critical, <20 warning, <50 medium
  - Run: quality-report-full.sh backend/app
- [ ] 7.2 Run full test suite
  - Backend: pytest tests/ -v (all 508+ tests)
  - Coverage: pytest --cov=app tests/ (target 85%+)
  - Confirm: No regression in functionality
- [ ] 7.3 Update documentation
  - DEVELOPMENT.md: Add code quality standards section
  - REFACTOR_STATUS.md: Update with completed cleanup
  - Document: New module organization (if applicable)
- [ ] 7.4 Create summary report
  - Before/after metrics
  - Files touched, lines refactored
  - Quality improvement percentages
  - Remaining issues (if any)

---

## Verification

- [ ] Security: 0 SQL injection risks (ruff + manual review)
- [ ] Complexity: 0 CRITICAL long functions (>100 lines)
- [ ] Files: 0 files >500 lines (all under soft limit)
- [ ] Types: <50 Any types (70% reduction minimum)
- [ ] Concerns: 0 CRITICAL multiple concern files
- [ ] Debt: 0 TODO/FIXME comments
- [ ] Tests: All 508+ tests passing, 85%+ coverage
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes (ruff + mypy)
- [ ] Baseline: 0 critical, <20 warning, <50 medium issues
- [ ] Docs: Code quality standards documented

---

## Success Criteria

1. **Security**: Zero SQL injection risks (CRITICAL)
2. **Maintainability**: All functions <75 lines, all files <500 lines
3. **Type Safety**: <50 Any types (70%+ reduction)
4. **Clarity**: Single responsibility per file
5. **Debt-Free**: Zero TODOs in code
6. **Quality Gates**: Each phase verified before proceeding
7. **No Regression**: All tests passing, functionality intact
8. **Documented**: Standards updated, cleanup recorded

---

## Notes

- **Parallel Dispatch**: Use --max mode for independent file refactoring
- **Quality Gates**: MANDATORY verification after each phase
- **No Skipping**: Address ALL issues found, even if "pre-existing"
- **Safety**: Full test suite after each phase to catch regressions
- **Service Restart**: Required after code changes (scripts/restart.sh)
- **Incremental Commits**: Commit after each phase completion
