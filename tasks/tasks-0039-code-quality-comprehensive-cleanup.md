# Task List: Comprehensive Code Quality Cleanup - Reach EXCELLENT Standard

**Source**: Quality checker fixes revealed accurate state: 30 critical + 65 warning + 68 medium issues
**Complexity**: Complex
**Effort**: HIGH (15-20 hours, 3-4 sessions, comprehensive cleanup)
**Environment**: Local Dev
**Created**: 2025-11-09
**Status**: Planned
**Strategy**: Parallel subagent dispatch - tackle multiple categories simultaneously

---

## Summary

**Goal**: Reach EXCELLENT quality standard (0/0/0 issues) by systematically addressing all quality issues revealed after fixing quality checker bugs.

**Current State** (verified 2025-11-09):
```
🔴 Critical:  30 issues (3 functions >100 lines, file sizes, etc.)
⚠️  Warning:   65 issues (20+ functions 75-100 lines, 9 files 500-800 lines)
📋 Medium:    68 issues (100+ functions 50-75 lines)

Details:
  Files > threshold:     9 files
  Long functions (>50):  137 functions
  Multiple concerns:     17 files
  Any types:             97 instances
  TODOs/FIXMEs:          3 items
```

**Target State**:
```
✅ Excellent: 0 critical, 0 warning, 0 medium issues
  Files: All <500 lines (or appropriate type-aware threshold)
  Functions: All <50 lines (or <75 for complex business logic)
  Any types: <10 (only where truly necessary)
  Code health: 9.5+/10
```

**Approach**:
- Task 0: Comprehensive scope discovery (get exact lists of ALL issues)
- Use parallel subagent dispatch to work on multiple categories simultaneously
- Systematic refactoring: extract helpers, split files, reduce complexity
- No file constraints: comprehensive refactoring allowed
- Continuous testing: maintain 508+ tests passing throughout

**Constraints**: None - comprehensive refactoring authorized

---

## Relevant Files

### Critical Functions (3 functions >100 lines - HIGHEST PRIORITY)
- `backend/app/watchlist/refresh_processor.py:443` - _generate_narrative_and_trade_levels() (202 lines) 🔴
- `backend/app/watchlist/refresh_processor.py:648` - process_ticker_snapshot() (189 lines) 🔴
- `backend/app/watchlist/scoring_service.py:263` - refresh_watchlist_scores() (165 lines) 🔴

### Warning Files (9 files >500 lines)
- `backend/app/watchlist/refresh_processor.py` (837 lines) ⚠️
- `backend/app/watchlist/watchlist_service.py` (783 lines) ⚠️
- `backend/app/services/news_service.py` (700 lines) ⚠️
- `backend/app/services/news_vendor_manager.py` (568 lines) ⚠️
- `backend/app/watchlist/fundamentals.py` (531 lines) ⚠️
- `backend/app/sources/multi_source_fetcher.py` (524 lines) ⚠️
- `backend/app/sources/finnhub_source.py` (463 lines) ⚠️
- `backend/app/sources/fmp_source.py` (455 lines) ⚠️
- `backend/app/utils/health_checks.py` (452 lines) ⚠️

### Warning Functions (20+ functions 75-100 lines)
- To be cataloged in Task 0

### Medium Functions (100+ functions 50-75 lines)
- To be cataloged in Task 0

### Type Safety Issues
- 97 Any type usages across codebase
- To be cataloged in Task 0

---

## Tasks

### 0.0 Scope Discovery & Cataloging (MANDATORY)

**Goal**: Get exact, complete list of ALL quality issues for systematic cleanup

- [ ] 0.1 Run comprehensive quality audit and export detailed results
  - [ ] 0.1.1 Run full quality report: `bash ~/portfolio-ai/.claude/skills/code-quality/scripts/quality-report-full.sh backend/app > /tmp/quality-full-report.txt`
  - [ ] 0.1.2 Extract and catalog all 3 CRITICAL functions (>100 lines)
    - Function name, file, line number, actual length
    - Brief description of what it does
    - Initial assessment of refactoring approach
  - [ ] 0.1.3 Extract and catalog all 20+ WARNING functions (75-100 lines)
    - Group by file for batching
    - Identify common patterns (API handlers, processing logic, etc.)
  - [ ] 0.1.4 Extract and catalog all 100+ MEDIUM functions (50-75 lines)
    - Prioritize top 20 worst offenders (closest to 75 lines)
    - Group by module/domain
  - [ ] 0.1.5 Catalog all 9 WARNING files (>500 lines)
    - Current size, target size, reduction needed
    - Identify natural split points (responsibilities, concerns)
  - [ ] 0.1.6 Catalog all 97 Any type usages
    - Group by file and pattern
    - Identify which can be easily fixed vs require Protocol/Generic

- [ ] 0.2 Prioritize and create execution plan
  - [ ] 0.2.1 Rank issues by impact/effort ratio
    - High impact: CRITICAL functions, largest files
    - Low effort: Simple extractions, obvious splits
    - Quick wins: Functions just over threshold (100-110 lines, 50-60 lines)
  - [ ] 0.2.2 Group issues for parallel subagent dispatch
    - Track 1: Critical function refactoring (3 functions)
    - Track 2: File size reduction (top 3-4 files)
    - Track 3: Warning function reduction (20+ functions)
    - Track 4: Type safety improvements (targeted fixes)
  - [ ] 0.2.3 Identify dependencies and order constraints
    - Which files depend on refactored functions?
    - Which refactorings enable others?
    - Test suite implications

- [ ] 0.3 Checkpoint: Confirm scope and approach
  - [ ] 0.3.1 Document full inventory:
    - Total issues: 30 critical + 65 warning + 68 medium = 163 issues
    - Grouped by category and track
    - Estimated effort per track
  - [ ] 0.3.2 Validate parallel dispatch plan
    - Track 1: X hours (critical functions)
    - Track 2: Y hours (file sizes)
    - Track 3: Z hours (warning functions)
    - Track 4: W hours (type safety)
    - Total: 15-20 hours across 3-4 sessions
  - [ ] 0.3.3 **STOP HERE - Report findings and get confirmation**

**DO NOT PROCEED TO TASK 1 UNTIL CHECKPOINT PASSED**

---

### 1.0 Track 1: Critical Function Refactoring (Parallel Dispatch)

**Dispatch 3 general-purpose subagents in PARALLEL, one per critical function**

- [ ] 1.1 Refactor _generate_narrative_and_trade_levels() (202 lines → <50 lines)
  - [ ] 1.1.1 **DISPATCH SUBAGENT** (general-purpose, model: sonnet)
    - Prompt: "Refactor refresh_processor.py:443 _generate_narrative_and_trade_levels() from 202 lines to <50 lines. Extract narrative generation logic to separate focused functions. Maintain all tests passing. Use TDD protocol."
    - Expected: 3-5 extracted helper functions, main function becomes orchestrator
  - [ ] 1.1.2 Verify subagent results
    - Tests passing
    - Function <50 lines
    - Logic preserved
    - No duplication introduced

- [ ] 1.2 Refactor process_ticker_snapshot() (189 lines → <75 lines)
  - [ ] 1.2.1 **DISPATCH SUBAGENT** (general-purpose, model: sonnet)
    - Prompt: "Refactor refresh_processor.py:648 process_ticker_snapshot() from 189 lines to <75 lines. Extract price change, news processing, and snapshot building to focused functions. Maintain all tests passing. Use TDD protocol."
    - Expected: 4-6 extracted functions, main function becomes coordinator
  - [ ] 1.2.2 Verify subagent results
    - Tests passing
    - Function <75 lines
    - Clear separation of concerns

- [ ] 1.3 Refactor refresh_watchlist_scores() (165 lines → <75 lines)
  - [ ] 1.3.1 **DISPATCH SUBAGENT** (general-purpose, model: sonnet)
    - Prompt: "Refactor scoring_service.py:263 refresh_watchlist_scores() from 165 lines to <75 lines. Extract setup, per-ticker processing, and finalization to focused functions. Maintain all tests passing. Use TDD protocol."
    - Expected: 3-4 extracted functions, orchestration logic clear
  - [ ] 1.3.2 Verify subagent results
    - Tests passing
    - Function <75 lines
    - Maintain performance characteristics

---

### 2.0 Track 2: File Size Reduction (Parallel Dispatch)

**Dispatch 2-3 general-purpose subagents in PARALLEL for largest files**

- [ ] 2.1 Reduce refresh_processor.py (837 lines → <600 lines)
  - [ ] 2.1.1 **DISPATCH SUBAGENT** (general-purpose, model: sonnet)
    - Prompt: "Reduce refresh_processor.py from 837 to <600 lines. Extract narrative generation to watchlist/narrative_builder.py, extract price calculations to watchlist/price_calculator.py. Maintain all tests. Use TDD protocol."
    - Expected: 2-3 new focused modules, main file becomes coordinator
  - [ ] 2.1.2 Verify subagent results
    - Tests passing
    - File <600 lines
    - Clear module boundaries

- [ ] 2.2 Reduce watchlist_service.py (783 lines → <500 lines)
  - [ ] 2.2.1 **DISPATCH SUBAGENT** (general-purpose, model: sonnet)
    - Prompt: "Reduce watchlist_service.py from 783 to <500 lines. Extract news intelligence building to watchlist/news_intelligence_builder.py, extract snapshot building to watchlist/snapshot_builder.py. Maintain all tests. Use TDD protocol."
    - Expected: 2-3 new focused modules, service becomes orchestrator
  - [ ] 2.2.2 Verify subagent results
    - Tests passing
    - File <500 lines
    - No circular dependencies

- [ ] 2.3 Review news_service.py (700 lines - recently reduced from 2057)
  - [ ] 2.3.1 Determine if further reduction needed
    - Already split into 6 modules in recent refactor
    - Current structure: news_service.py (orchestrator) + 5 specialized modules
    - Decision: Keep as-is OR reduce further to <500 lines
  - [ ] 2.3.2 If reducing: Extract vendor management to separate orchestrator
  - [ ] 2.3.3 Verify: Tests passing, clear boundaries

---

### 3.0 Track 3: Warning Function Reduction (Batch Processing)

**Dispatch 1 general-purpose subagent to systematically reduce WARNING functions**

- [ ] 3.1 **DISPATCH SUBAGENT** (general-purpose, model: sonnet)
  - Prompt: "Reduce all WARNING-level functions (75-100 lines) to <75 lines. Work systematically through list from Task 0. Extract helpers, reduce complexity. Maintain all 508+ tests passing. Use TDD protocol. Process in batches of 5-10 functions."
  - Expected: 20+ functions reduced, helpers extracted, tests passing

- [ ] 3.2 Verify batch results
  - [ ] 3.2.1 Run quality check after each batch
  - [ ] 3.2.2 Ensure warning count decreasing
  - [ ] 3.2.3 All tests still passing
  - [ ] 3.2.4 No new complexity introduced

---

### 4.0 Track 4: Type Safety Improvements (Targeted Fixes)

**Dispatch 1 general-purpose subagent for systematic type safety improvements**

- [ ] 4.1 **DISPATCH SUBAGENT** (general-purpose, model: haiku)
  - Prompt: "Reduce Any type usage from 97 to <10. Focus on easy wins: JSON response types, dict parameters with known structure. Add TypedDict, Protocol where appropriate. Maintain mypy --strict compliance. Use TDD protocol."
  - Expected: 87+ Any types eliminated, proper types added

- [ ] 4.2 Verify type safety improvements
  - [ ] 4.2.1 mypy --strict still passing
  - [ ] 4.2.2 Any count reduced to <10
  - [ ] 4.2.3 No runtime behavior changes
  - [ ] 4.2.4 All tests passing

---

### 5.0 Medium Function Cleanup (As Time Permits)

**Lower priority - focus on quick wins**

- [ ] 5.1 Target top 20 MEDIUM functions (closest to 75 lines)
  - [ ] 5.1.1 Extract common patterns (validation, parsing, formatting)
  - [ ] 5.1.2 Reduce to <50 lines where possible
  - [ ] 5.1.3 Don't over-engineer - simple extractions only

- [ ] 5.2 Verify medium function reductions
  - [ ] 5.2.1 Quality metrics improving
  - [ ] 5.2.2 No new issues introduced
  - [ ] 5.2.3 Code remains readable

---

### 6.0 Final Verification & Documentation

- [ ] 6.1 Run comprehensive quality check
  - [ ] 6.1.1 Run: `bash ~/portfolio-ai/.claude/skills/code-quality/scripts/quality-report-full.sh backend/app`
  - [ ] 6.1.2 Verify target reached:
    - Critical: 0 (was 30)
    - Warning: 0 (was 65)
    - Medium: <10 (was 68)
    - Status: EXCELLENT
  - [ ] 6.1.3 Compare before/after metrics:
    - Files reduced: 9 → 0 over threshold
    - Functions reduced: 137 → <10 over 50 lines
    - Any types: 97 → <10
    - Code health: 7.95/10 → 9.5+/10

- [ ] 6.2 Verify test suite
  - [ ] 6.2.1 All 508+ tests passing
  - [ ] 6.2.2 Coverage maintained or improved (85%+)
  - [ ] 6.2.3 No flaky tests introduced
  - [ ] 6.2.4 Performance regression check (watchlist refresh time)

- [ ] 6.3 Verify production readiness
  - [ ] 6.3.1 Linting: `~/portfolio-ai/scripts/lint.sh` passes
  - [ ] 6.3.2 Type checking: mypy --strict passes
  - [ ] 6.3.3 No security regressions
  - [ ] 6.3.4 No breaking changes to APIs

- [ ] 6.4 Update documentation
  - [ ] 6.4.1 Update WORK_TRACKER.md with new quality state
  - [ ] 6.4.2 Document major refactorings in ARCHITECTURE.md
  - [ ] 6.4.3 Update REFACTOR_STATUS.md
  - [ ] 6.4.4 Add notes about new module structure

- [ ] 6.5 Create summary report
  - [ ] 6.5.1 Before/after quality metrics
  - [ ] 6.5.2 List of all files refactored
  - [ ] 6.5.3 List of all new modules created
  - [ ] 6.5.4 Lessons learned for future refactorings

---

### 7.0 Data Safety Improvements (CRITICAL - Nov 9 Incident Response)

**Context**: Migration #18 deleted 612 watchlist items + 246,131 snapshots due to CASCADE constraints. Frontend showed stale cached data, hiding the issue for hours. Need safeguards to prevent this.

**Root Causes Identified**:
1. Migration #18 had aggressive DELETE without dry-run or backup
2. CASCADE constraint on snapshots → historical data deleted with items
3. Frontend cache (`refetchOnMount: false`) showed stale data after deletions
4. No migration validation or rollback mechanism

- [ ] 7.0 🚨 IMMEDIATE: Enable PostgreSQL Logging (CRITICAL - No Forensics Available)
  - [ ] 7.0.1 Enable statement logging in PostgreSQL
    - Edit `/etc/postgresql/16/main/postgresql.conf`:
      ```
      log_statement = 'mod'                    # Log INSERT/UPDATE/DELETE/TRUNCATE
      log_min_duration_statement = 1000        # Log queries taking >1s
      log_line_prefix = '%t [%p] %u@%d '      # timestamp, PID, user@database
      logging_collector = on
      log_directory = '/var/log/postgresql'
      log_filename = 'postgresql-%Y-%m-%d.log'
      log_rotation_age = 1d
      log_rotation_size = 100MB
      log_truncate_on_rotation = off
      ```
    - Restart PostgreSQL: `sudo systemctl reload postgresql`
    - Verify: `SHOW log_statement;` should return 'mod'
  - [ ] 7.0.2 Set up log rotation and retention
    - Configure logrotate for PostgreSQL logs
    - Retention: 30 days
    - Compression: gzip old logs
  - [ ] 7.0.3 Test logging is working
    - Run test DELETE/UPDATE
    - Verify appears in `/var/log/postgresql/postgresql-*.log`
    - Ensure user@database is logged for attribution

- [ ] 7.1 Migration Safety Framework
  - [ ] 7.1.1 Create migration dry-run mode
    - Add `--dry-run` flag to migration runner
    - Show: "WOULD DELETE X items, affecting Y snapshots"
    - Require explicit `--execute` after dry-run review
    - Script: `backend/scripts/migrate.py --dry-run migration_018`
  - [ ] 7.1.2 Add pre-migration backup automation
    - Auto-create pg_dump before any migration with DELETE/DROP
    - Location: `backups/pre-migration-{version}-{timestamp}.sql`
    - Retention: 30 days
    - Script: `backend/scripts/migrate.py` auto-backup
  - [ ] 7.1.3 Migration validation checklist
    - Document in `backend/migrations/MIGRATION_SAFETY.md`:
      - ✅ Dry-run shows expected changes?
      - ✅ Backup created and verified?
      - ✅ Rollback plan documented?
      - ✅ CASCADE impacts analyzed?
      - ✅ Frontend cache invalidation needed?
  - [ ] 7.1.4 Add migration rollback mechanism
    - Store rollback SQL with each migration
    - Test rollback in dev before production
    - Add `--rollback` flag to migration runner

- [ ] 7.2 Database Constraint Improvements
  - [ ] 7.2.1 Review CASCADE constraints
    - Current: `watchlist_snapshots.item_id` → `ON DELETE CASCADE`
    - Issue: Deleting items nukes ALL historical data
    - Solution: Change to `ON DELETE SET NULL` for historical tables
    - Migration: `023_fix_cascade_constraints.sql`
  - [ ] 7.2.2 Add soft-delete for critical tables
    - Add `deleted_at` column to `watchlist_items`
    - Keep historical snapshots even after "deletion"
    - Filter out soft-deleted items in queries
    - Allow recovery within 30 days
  - [ ] 7.2.3 Add deletion audit log
    - Create `deletion_audit` table
    - Track: who, what, when, why (migration/user/cascade)
    - Helps debug "where did my data go" scenarios

- [ ] 7.3 Frontend Cache Invalidation Fixes
  - [ ] 7.3.1 Fix React Query cache on errors
    - Current issue: `refetchOnMount: false` + cached data persists after 404s
    - Solution: Invalidate cache on delete errors (404, 410)
    - File: `frontend/lib/hooks/useWatchlist.ts`
    - Change: `onError` → invalidate cache + force refetch
  - [ ] 7.3.2 Add cache staleness detection
    - Compare `updated_at` from cache vs API
    - Show warning: "Data may be stale, click to refresh"
    - Auto-invalidate cache if API returns newer data
  - [ ] 7.3.3 Add optimistic update rollback
    - Current: Delete shows success, backend 404 hidden
    - Solution: On delete error, revert optimistic update
    - Show error toast + restore item to UI

- [ ] 7.4 Monitoring & Alerting
  - [ ] 7.4.1 Add data deletion monitoring
    - Alert if >10 items deleted in <1 hour
    - Alert if >1000 snapshots deleted in <1 hour
    - Track deletion rate in health dashboard
  - [ ] 7.4.2 Add migration impact tracking
    - Log rows affected by each migration
    - Store in `migration_audit` table
    - Review before applying to production

- [ ] 7.5 Documentation & Prevention
  - [ ] 7.5.1 Create `backend/migrations/MIGRATION_SAFETY.md`
    - Document all safety protocols
    - Add examples of safe vs unsafe migrations
    - Require sign-off checklist for DELETE/DROP migrations
  - [ ] 7.5.2 Update `docs/core/OPERATIONS.md`
    - Add migration runbook
    - Document rollback procedures
    - Add incident response checklist
  - [ ] 7.5.3 Add migration testing guidelines
    - Test migrations on copy of production data first
    - Verify row counts before/after
    - Check CASCADE impacts with `EXPLAIN`

- [ ] 7.6 Validation & Testing (MANDATORY - Verify All Hardening Works)
  - [ ] 7.6.1 Test PostgreSQL logging
    - Apply logging config: `sudo cp backend/config/postgresql-logging.conf /etc/postgresql/16/main/conf.d/`
    - Reload PostgreSQL: `sudo systemctl reload postgresql`
    - Verify enabled: `psql -c "SHOW log_statement;"` → should return 'mod'
    - Run test DELETE: `DELETE FROM watchlist_items WHERE id = 'test-id';`
    - Verify logged: `grep "DELETE FROM watchlist_items" /var/log/postgresql/*.log`
    - Check attribution: Log should show `portfolio_ai_user@portfolio_ai`
  - [ ] 7.6.2 Test frontend cache invalidation
    - Create test item in watchlist
    - Delete it via API (return 404)
    - Verify: Frontend should show error + refresh data (not show deleted item)
    - No stale cached data should remain visible
  - [ ] 7.6.3 Test CASCADE constraint fix (after 7.2.1 complete)
    - Delete watchlist item
    - Verify: Snapshots remain (item_id set to NULL, not deleted)
    - Historical data preserved
  - [ ] 7.6.4 Test deletion audit log (after 7.2.3 complete)
    - Delete item via API
    - Check deletion_audit table has record
    - Verify: user, timestamp, reason captured
  - [ ] 7.6.5 Test deletion monitoring alerts (after 7.4.1 complete)
    - Simulate mass deletion (>10 items)
    - Verify: Alert triggered
    - Check alert includes deletion count + timeframe
  - [ ] 7.6.6 Integration test: Full deletion scenario
    - Start with 10 items in watchlist
    - Enable all logging/monitoring
    - Delete 5 items (should NOT trigger alert threshold)
    - Delete 6 more items within 1 hour (SHOULD trigger alert)
    - Verify: All deletions logged, audit trail complete
    - Verify: Historical snapshots preserved

**Verification**:
- [ ] PostgreSQL logging enabled and tested
- [ ] Dry-run mode working (test with safe migration)
- [ ] Backup automation tested
- [ ] CASCADE constraints reviewed and fixed
- [ ] Frontend cache properly invalidates on errors
- [ ] Deletion audit log captures all deletes
- [ ] Monitoring alerts trigger correctly
- [ ] Documentation complete and reviewed
- [ ] ✅ ALL 7.6.x validation tests passing

---

## Verification (MANDATORY before "COMPLETE ✅")

- [ ] **Quality Metrics**: EXCELLENT (0/0/0) or near-EXCELLENT (<5 issues total)
- [ ] **Tests**: All 508+ tests passing, 85%+ coverage maintained
- [ ] **Linting**: `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy --strict)
- [ ] **Type Safety**: <10 Any types remaining (only where truly necessary)
- [ ] **No Regressions**: Watchlist refresh performance maintained
- [ ] **Data Safety**: All Task 7 improvements implemented and verified
- [ ] **Clean Architecture**: No circular dependencies introduced
- [ ] **Documentation**: Major refactorings documented
- [ ] **Production Ready**: No breaking changes, backward compatible

---

## Success Metrics

### Baseline (Before - 2025-11-09)
```
🔴 Critical:  30 issues
⚠️  Warning:   65 issues
📋 Medium:    68 issues

Files > threshold:     9
Long functions (>50):  137
Any types:             97
Code health:           7.95/10
```

### Target (After)
```
✅ Excellent:  0 critical, 0 warning, <10 medium

Files > threshold:     0
Long functions (>50):  <10
Any types:             <10
Code health:           9.5+/10
```

### Measurements
- **Actual results to be filled in Task 6.1**
- Track progress after each major track completion
- Use quality checker (now reliable) for validation

---

## Notes

**Parallel Dispatch Strategy**:
- Task 0: Run comprehensive scope discovery FIRST
- Tasks 1-4: Dispatch 6-8 subagents in PARALLEL after checkpoint
  - Track 1: 3 subagents (1 per critical function)
  - Track 2: 2-3 subagents (file size reduction)
  - Track 3: 1 subagent (warning functions batch)
  - Track 4: 1 subagent (type safety)
- Each subagent works independently, reports back
- Main agent coordinates, verifies, integrates results

**Constraints**: None - comprehensive refactoring authorized

**Risk Mitigation**:
- TDD protocol mandatory (tests first, then refactor)
- Run full test suite after each track completion
- Quality check after each major change
- Incremental commits (don't batch everything)

**Estimated Timeline**:
- Session 1 (4-5 hours): Task 0 + Track 1 (critical functions)
- Session 2 (4-5 hours): Track 2 (file sizes)
- Session 3 (4-5 hours): Track 3 + Track 4 (functions + types)
- Session 4 (2-3 hours): Task 5 + Task 6 (cleanup + verification)
- Total: 15-20 hours across 3-4 sessions

**Quality Checker**: Now reliable after fixes (commits 5eb1171, a8f53ce)
