# Task List: Comprehensive Code Quality Cleanup

**Source**: User request via /task_it
**Complexity**: Complex
**Effort**: HIGH (20-30 hours)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-16 17:30

---

## Summary

**Goal**: Fix ALL code quality issues from baseline report - 46 critical, 121 warning, 158 medium issues. Zero tolerance for skipping pre-existing issues. Systematic cleanup with quality gates at each phase.

**Approach**: Phased approach prioritizing security > complexity > type safety > file size. Each phase has verification gates before proceeding to next. Use parallel subagent dispatch where safe.

**Scope Discovery**: Required for SQL injection and Any type patterns

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run Explore subagent for SQL injection patterns (very thorough)
  - Pattern 1: f-string with SQL WHERE/SET/VALUES clauses
  - Pattern 2: Dynamic table/column names without validation
  - Pattern 3: String concatenation in SQL queries
  - Goal: Find ALL instances across backend/app
  - Output: Complete list with file:line:code
- [ ] 0.2 Run Explore subagent for Any type usages (very thorough)
  - Pattern: `Any` in type annotations across backend/app
  - Goal: Categorize by fixability (trivial, moderate, complex)
  - Output: Grouped list by complexity
- [ ] 0.3 Update task list with discovered scope
  - Add specific SQL injection fixes (file by file)
  - Add Any type cleanup tasks by complexity group
  - Update effort estimates based on findings
- [ ] 0.4 Checkpoint: Confirm scope before proceeding
  - SQL injection risks: [TBD] files
  - Any types: [TBD] instances (trivial/moderate/complex breakdown)
  - Estimated effort: [TBD] hours
  - Any architectural concerns: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 PHASE 1: CRITICAL Security - SQL Injection Fixes (P0)

**Baseline**: 2 SQL injection risks detected

- [ ] 1.1 Fix backend/app/agents/workflow_orchestrator.py:158
  - Current: f"UPDATE agent_workflows SET {set_clause} WHERE..."
  - Fix: Use parameterized queries with psycopg2/sqlalchemy
  - Verify: No user input in f-string SQL
- [ ] 1.2 Fix backend/app/services/capability_db_scanner.py:233
  - Current: f"SELECT MIN({col_name}), MAX({col_name}) FROM {table_name}..."
  - Fix: Validate col_name/table_name against whitelist or use SQL identifiers
  - Verify: Add "# validated: table/column from enum" comments
- [ ] 1.3 Review all 9 dynamic table name patterns
  - Files: Check if table names are from enum/hardcoded
  - Add validation markers where safe
  - Flag any that need user input validation
- [ ] 1.4 Verification gate
  - Run: ruff check --select S608 (SQL injection check)
  - Run: grep -r "f\".*WHERE\|SET\|VALUES" backend/app/
  - Confirm: 0 SQL injection risks
  - Test: Run integration tests for affected endpoints

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
