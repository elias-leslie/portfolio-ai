# Task List: Code Quality Cleanup - Cloud Agent Version

**Source**: Comprehensive quality improvement (cloud agent autonomous execution)
**Complexity**: Complex
**Effort**: HIGH (15-20 hours autonomous work)
**Environment**: Cloud/Sandbox (adapt to available tools)
**Created**: 2025-11-10
**Status**: Planned
**Strategy**: Autonomous execution with periodic checkpoints - work until complete or genuinely blocked

---

## Summary

**Goal**: Reach EXCELLENT quality standard (0 critical/0 warning/<10 medium issues) through systematic refactoring.

**Current State**:
```
🔴 Critical:  30 issues (3 functions >100 lines, file sizes)
⚠️  Warning:   65 issues (20+ functions 75-100 lines, 9 files >500 lines)
📋 Medium:    68 issues (100+ functions 50-75 lines)

Details:
  Files > threshold:     9 files
  Long functions (>50):  137 functions
  Any types:             97 instances
```

**Target State**:
```
✅ Excellent: 0 critical, 0 warning, <10 medium
  Files: All <500 lines
  Functions: All <50 lines (or <75 for complex business logic)
  Any types: <10 (only where truly necessary)
```

**Cloud Agent Instructions**:
- Work autonomously through all tasks
- Run tests after each major change (adapt if test environment unavailable)
- Report findings at checkpoints but continue unless genuinely blocked
- Use static analysis if runtime tools unavailable
- Prioritize data safety (Task 7) - critical incident response

---

## Critical Files & Functions (From 0039)

### Critical Functions (3 - HIGHEST PRIORITY)
- `backend/app/watchlist/refresh_processor.py:443` - _generate_narrative_and_trade_levels() (202 lines)
- `backend/app/watchlist/refresh_processor.py:648` - process_ticker_snapshot() (189 lines)
- `backend/app/watchlist/scoring_service.py:263` - refresh_watchlist_scores() (165 lines)

### Warning Files (9)
- `backend/app/watchlist/refresh_processor.py` (837 lines)
- `backend/app/watchlist/watchlist_service.py` (783 lines)
- `backend/app/services/news_service.py` (700 lines)
- `backend/app/services/news_vendor_manager.py` (568 lines)
- `backend/app/watchlist/fundamentals.py` (531 lines)
- `backend/app/sources/multi_source_fetcher.py` (524 lines)
- `backend/app/sources/finnhub_source.py` (463 lines)
- `backend/app/sources/fmp_source.py` (455 lines)
- `backend/app/utils/health_checks.py` (452 lines)

---

## Tasks

### 0.0 Scope Discovery & Cataloging (MANDATORY)

**Goal**: Complete inventory of all quality issues for systematic cleanup

- [ ] 0.1 Run comprehensive quality audit
  - [ ] 0.1.1 Generate full quality report (use available tools in cloud environment)
  - [ ] 0.1.2 Catalog all 3 CRITICAL functions
    - Name, file, line number, actual length
    - Brief description, refactoring approach
  - [ ] 0.1.3 Catalog all WARNING functions (75-100 lines)
    - Group by file for batch processing
    - Identify patterns (API handlers, processors, etc.)
  - [ ] 0.1.4 Catalog MEDIUM functions (50-75 lines)
    - Top 20 worst offenders (closest to 75 lines)
    - Group by module

- [ ] 0.2 Prioritize and create execution plan
  - [ ] 0.2.1 Rank by impact/effort ratio
    - High impact: Critical functions, largest files
    - Quick wins: Functions just over threshold
  - [ ] 0.2.2 Group for efficient execution
    - Track 1: Critical functions (3)
    - Track 2: File size reduction (top 4)
    - Track 3: Warning functions (batch of 10-15)
    - Track 4: Type safety (targeted fixes)
  - [ ] 0.2.3 Document inventory and estimates

- [ ] 0.3 Checkpoint: Scope confirmed
  - Document total issues: 163 (30+65+68)
  - Estimated effort per track
  - **PROCEED AUTOMATICALLY** unless scope >2x expected

**AUTONOMOUS MODE**: Continue to Task 1 after documenting findings

---

### 1.0 Critical Function Refactoring

**Goal**: Reduce 3 critical functions from >100 lines to <75 lines

- [ ] 1.1 Refactor _generate_narrative_and_trade_levels() (202 → <75 lines)
  - [ ] 1.1.1 Extract narrative building logic to helpers
  - [ ] 1.1.2 Extract trade level calculations to separate function
  - [ ] 1.1.3 Extract signal determination logic
  - [ ] 1.1.4 Verify: Function <75 lines, all tests passing
  - **Success**: Main function becomes orchestrator, 3-4 extracted helpers

- [ ] 1.2 Refactor process_ticker_snapshot() (189 → <75 lines)
  - [ ] 1.2.1 Extract price change calculation
  - [ ] 1.2.2 Extract news processing logic
  - [ ] 1.2.3 Extract snapshot building
  - [ ] 1.2.4 Verify: Function <75 lines, tests passing
  - **Success**: Clear separation of concerns, 4-5 extracted functions

- [ ] 1.3 Refactor refresh_watchlist_scores() (165 → <75 lines)
  - [ ] 1.3.1 Extract setup/initialization logic
  - [ ] 1.3.2 Extract per-ticker processing
  - [ ] 1.3.3 Extract finalization/aggregation
  - [ ] 1.3.4 Verify: Function <75 lines, tests passing
  - **Success**: Orchestration clear, helpers focused

---

### 2.0 File Size Reduction

**Goal**: Reduce large files to <500 lines through logical module splits

- [ ] 2.1 Reduce refresh_processor.py (837 → <600 lines)
  - [ ] 2.1.1 Extract narrative generation → `watchlist/narrative_builder.py`
  - [ ] 2.1.2 Extract price calculations → `watchlist/price_calculator.py`
  - [ ] 2.1.3 Update imports, verify tests
  - **Success**: Main file coordinator, clear module boundaries

- [ ] 2.2 Reduce watchlist_service.py (783 → <500 lines)
  - [ ] 2.2.1 Extract news intelligence → `watchlist/news_intelligence_builder.py`
  - [ ] 2.2.2 Extract snapshot building → `watchlist/snapshot_builder.py`
  - [ ] 2.2.3 Update imports, verify tests
  - **Success**: Service orchestrates, no circular deps

- [ ] 2.3 Review news_service.py (700 lines - recently refactored)
  - [ ] 2.3.1 Assess current structure (already split into 6 modules)
  - [ ] 2.3.2 Further reduce ONLY if clear benefit
  - **Decision**: Keep as-is OR reduce to <500 lines

- [ ] 2.4 Reduce news_vendor_manager.py (568 → <500 lines)
  - [ ] 2.4.1 Extract vendor routing logic
  - [ ] 2.4.2 Extract aggregation logic
  - **Success**: Clear responsibilities

---

### 3.0 Warning Function Reduction

**Goal**: Systematically reduce WARNING functions (75-100 lines) to <75 lines

- [ ] 3.1 Batch 1: Top 10 warning functions (largest first)
  - [ ] 3.1.1 Identify top 10 from catalog
  - [ ] 3.1.2 Extract helpers, reduce complexity
  - [ ] 3.1.3 Verify: Functions <75 lines, tests passing
  - **Success**: 10 functions reduced

- [ ] 3.2 Batch 2: Next 10 warning functions
  - [ ] 3.2.1 Continue systematic reduction
  - [ ] 3.2.2 Verify quality improving
  - **Success**: 20 total functions reduced

- [ ] 3.3 Remaining warning functions (as time permits)
  - Focus on quick wins
  - Don't over-engineer

---

### 4.0 Type Safety Improvements

**Goal**: Reduce Any type usage from 97 to <10

- [ ] 4.1 Easy wins: JSON response types
  - [ ] 4.1.1 Add TypedDict for API responses
  - [ ] 4.1.2 Replace dict[str, Any] with proper types
  - **Target**: 50+ Any types eliminated

- [ ] 4.2 Dict parameters with known structure
  - [ ] 4.2.1 Convert to TypedDict or dataclasses
  - [ ] 4.2.2 Update function signatures
  - **Target**: 30+ Any types eliminated

- [ ] 4.3 Protocol/Generic for complex cases
  - [ ] 4.3.1 Add Protocol where duck typing needed
  - [ ] 4.3.2 Use Generic for container types
  - **Target**: 10-15 Any types eliminated

- [ ] 4.4 Verify type safety
  - [ ] 4.4.1 mypy --strict still passing
  - [ ] 4.4.2 Any count <10
  - [ ] 4.4.3 No runtime changes

---

### 5.0 Medium Function Cleanup (Lower Priority)

**Goal**: Reduce top 20 medium functions (closest to 75 lines)

- [ ] 5.1 Target functions 70-75 lines
  - Simple extractions only
  - Quick wins, no over-engineering

- [ ] 5.2 Verify improvements
  - Quality metrics improving
  - Code readability maintained

---

### 6.0 Verification & Quality Check

**Goal**: Confirm EXCELLENT standard reached

- [ ] 6.1 Run comprehensive quality check
  - [ ] 6.1.1 Generate final quality report
  - [ ] 6.1.2 Verify targets:
    - Critical: 0 (was 30)
    - Warning: 0 (was 65)
    - Medium: <10 (was 68)
  - [ ] 6.1.3 Document before/after metrics

- [ ] 6.2 Test suite verification
  - [ ] 6.2.1 All tests passing
  - [ ] 6.2.2 Coverage maintained (85%+)
  - [ ] 6.2.3 No performance regressions

- [ ] 6.3 Production readiness
  - [ ] 6.3.1 Linting passes (if available)
  - [ ] 6.3.2 Type checking passes
  - [ ] 6.3.3 No breaking API changes

- [ ] 6.4 Documentation
  - [ ] 6.4.1 Update WORK_TRACKER.md
  - [ ] 6.4.2 Document major refactorings
  - [ ] 6.4.3 Create summary report

---

### 7.0 Data Safety Improvements (CRITICAL - Nov 9 Incident Response)

**Context**: Migration #18 deleted 612 watchlist items + 246,131 snapshots due to CASCADE. Frontend cache hid the issue for hours. This is CRITICAL infrastructure hardening.

**Goal**: Prevent future data loss incidents through comprehensive safeguards

#### 7.1 PostgreSQL Statement Logging (IMMEDIATE - No Forensics Available)

- [ ] 7.1.1 Create PostgreSQL logging configuration
  - [ ] 7.1.1.1 Create `backend/config/postgresql-logging.conf`:
    ```conf
    log_statement = 'mod'                    # Log all data modifications
    log_min_duration_statement = 1000        # Log slow queries (>1s)
    log_line_prefix = '%t [%p] %u@%d '      # timestamp, PID, user@database
    logging_collector = on
    log_directory = '/var/log/postgresql'
    log_filename = 'postgresql-%Y-%m-%d.log'
    log_rotation_age = 1d
    log_rotation_size = 100MB
    log_truncate_on_rotation = off
    ```
  - [ ] 7.1.1.2 Create installation instructions in `docs/operations/postgresql-logging.md`
  - [ ] 7.1.1.3 Add to OPERATIONS.md deployment checklist

- [ ] 7.1.2 Document log monitoring procedures
  - [ ] 7.1.2.1 How to check deletion history
  - [ ] 7.1.2.2 How to identify mass deletions
  - [ ] 7.1.2.3 Log retention policy (30 days)

#### 7.2 Migration Safety Framework

- [ ] 7.2.1 Create migration dry-run tooling
  - [ ] 7.2.1.1 Add `--dry-run` mode to migration runner
  - [ ] 7.2.1.2 Show impact analysis (rows affected, CASCADE effects)
  - [ ] 7.2.1.3 Require explicit `--execute` confirmation
  - [ ] 7.2.1.4 Example: `python backend/scripts/migrate.py --dry-run 018`

- [ ] 7.2.2 Create pre-migration backup automation
  - [ ] 7.2.2.1 Auto-create pg_dump before destructive migrations
  - [ ] 7.2.2.2 Store in `backups/pre-migration-{version}-{timestamp}.sql`
  - [ ] 7.2.2.3 Add backup verification step
  - [ ] 7.2.2.4 Document restoration procedure

- [ ] 7.2.3 Create migration safety checklist
  - [ ] 7.2.3.1 Create `backend/migrations/MIGRATION_SAFETY.md`:
    - ✅ Dry-run shows expected changes?
    - ✅ Backup created and verified?
    - ✅ Rollback plan documented?
    - ✅ CASCADE impacts analyzed?
    - ✅ Frontend cache invalidation needed?
  - [ ] 7.2.3.2 Add template for migration with rollback SQL

- [ ] 7.2.4 Add migration rollback mechanism
  - [ ] 7.2.4.1 Store rollback SQL with each migration
  - [ ] 7.2.4.2 Add `--rollback` flag to runner
  - [ ] 7.2.4.3 Test rollback in dev first

#### 7.3 Database Constraint Review

- [ ] 7.3.1 Analyze CASCADE constraints
  - [ ] 7.3.1.1 Review `watchlist_snapshots.item_id` → CASCADE
  - [ ] 7.3.1.2 Document incident: DELETE item → nuked historical data
  - [ ] 7.3.1.3 **DECISION POINT**: Keep CASCADE (user accepted data loss) OR implement soft delete later

- [ ] 7.3.2 Add deletion audit log (future-proofing)
  - [ ] 7.3.2.1 Create migration `024_deletion_audit.sql`:
    ```sql
    CREATE TABLE deletion_audit (
      id BIGSERIAL PRIMARY KEY,
      table_name TEXT NOT NULL,
      record_id TEXT NOT NULL,
      deleted_by TEXT NOT NULL,  -- user or 'migration:018'
      deleted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      deletion_reason TEXT,       -- 'user_action' | 'migration' | 'cascade'
      row_count INTEGER,          -- for batch deletes
      metadata JSONB
    );
    ```
  - [ ] 7.3.2.2 Add trigger for watchlist_items deletions
  - [ ] 7.3.2.3 Document audit log usage in OPERATIONS.md

#### 7.4 Frontend Cache Invalidation Fixes

- [ ] 7.4.1 Fix React Query cache on errors
  - [ ] 7.4.1.1 Update `frontend/lib/hooks/useWatchlist.ts`
  - [ ] 7.4.1.2 Invalidate cache on delete errors (404, 410)
  - [ ] 7.4.1.3 Force refetch after failed operations
  - [ ] 7.4.1.4 Change: `refetchOnMount: false` → conditional based on error state

- [ ] 7.4.2 Add cache staleness detection
  - [ ] 7.4.2.1 Compare `updated_at` from cache vs API
  - [ ] 7.4.2.2 Show warning: "Data may be stale, click to refresh"
  - [ ] 7.4.2.3 Auto-invalidate if API returns newer `updated_at`

- [ ] 7.4.3 Improve optimistic update rollback
  - [ ] 7.4.3.1 On delete error, revert optimistic update
  - [ ] 7.4.3.2 Show error toast + restore item to UI
  - [ ] 7.4.3.3 Test: Delete non-existent item → UI reverts

#### 7.5 Monitoring & Alerting

- [ ] 7.5.1 Add data deletion monitoring
  - [ ] 7.5.1.1 Create health check endpoint: `/api/health/deletion-rate`
  - [ ] 7.5.1.2 Track deletions per hour in memory
  - [ ] 7.5.1.3 Alert thresholds:
    - Warning: >10 items deleted in <1 hour
    - Critical: >100 items deleted in <1 hour
  - [ ] 7.5.1.4 Add to health dashboard

- [ ] 7.5.2 Add migration impact tracking
  - [ ] 7.5.2.1 Log rows affected by each migration
  - [ ] 7.5.2.2 Store in `migration_audit` table
  - [ ] 7.5.2.3 Review before production migrations

#### 7.6 Documentation & Prevention

- [ ] 7.6.1 Create comprehensive migration safety guide
  - [ ] 7.6.1.1 `backend/migrations/MIGRATION_SAFETY.md` with:
    - All safety protocols
    - Safe vs unsafe migration examples
    - Required sign-off checklist
  - [ ] 7.6.1.2 Add to developer onboarding

- [ ] 7.6.2 Update operations documentation
  - [ ] 7.6.2.1 `docs/core/OPERATIONS.md` - migration runbook
  - [ ] 7.6.2.2 Document rollback procedures
  - [ ] 7.6.2.3 Incident response checklist

- [ ] 7.6.3 Add migration testing guidelines
  - [ ] 7.6.3.1 Test on production data copy first
  - [ ] 7.6.3.2 Verify row counts before/after
  - [ ] 7.6.3.3 Use EXPLAIN to check CASCADE impacts

#### 7.7 Validation & Testing (MANDATORY)

- [ ] 7.7.1 Test PostgreSQL logging (if environment available)
  - Apply config, reload PostgreSQL
  - Run test DELETE
  - Verify logged with user@database attribution

- [ ] 7.7.2 Test frontend cache invalidation
  - Create item, delete (trigger 404)
  - Verify: UI shows error + refreshes (no stale data)

- [ ] 7.7.3 Test deletion audit log
  - Delete item via API
  - Verify audit record created with user/timestamp

- [ ] 7.7.4 Test deletion monitoring
  - Simulate mass deletion (>10 items)
  - Verify alert triggered with count + timeframe

- [ ] 7.7.5 Integration test: Full deletion scenario
  - Start with 10 items
  - Enable all logging/monitoring
  - Delete 5 items (no alert)
  - Delete 6 more within 1 hour (should alert)
  - Verify: All logged, audit trail complete

**Verification**:
- [ ] PostgreSQL logging enabled and documented
- [ ] Dry-run mode working
- [ ] Backup automation in place
- [ ] Deletion audit log functional
- [ ] Frontend cache properly invalidates
- [ ] Monitoring alerts tested
- [ ] Documentation complete
- [ ] ✅ ALL 7.7.x validation tests passing

---

## Verification (MANDATORY before "COMPLETE ✅")

- [ ] **Quality Metrics**: EXCELLENT (0/0/<10) achieved
- [ ] **Tests**: All tests passing (adapt to environment)
- [ ] **Type Safety**: <10 Any types remaining
- [ ] **No Regressions**: Performance maintained
- [ ] **Data Safety**: Task 7 complete and verified
- [ ] **Documentation**: Refactorings documented
- [ ] **Production Ready**: No breaking changes

---

## Success Metrics

### Baseline (Before)
```
🔴 Critical:  30 issues
⚠️  Warning:   65 issues
📋 Medium:    68 issues

Files > threshold:     9
Long functions (>50):  137
Any types:             97
```

### Target (After)
```
✅ Excellent:  0 critical, 0 warning, <10 medium

Files > threshold:     0
Long functions (>50):  <10
Any types:             <10
```

---

## Cloud Agent Guidelines

**Autonomous Execution**:
- Work through tasks systematically
- Run tests after major changes (or use static analysis if unavailable)
- Document findings at checkpoints but continue unless genuinely blocked
- Adapt to available tools (may not have runtime environment)

**When to Report & Wait**:
- Scope >2x expected (Task 0)
- Critical architectural decision needed
- Cannot verify changes (no test environment)
- Genuinely blocked (not just complex)

**When to Continue Autonomously**:
- Scope matches expectations
- Clear refactoring path
- Tests passing (or can verify via static analysis)
- Making steady progress

**Data Safety Priority**:
- Task 7 is CRITICAL incident response
- Document thoroughly even if can't test in cloud
- Provide clear installation instructions for local execution
- This prevents future data loss - highest priority

**Return Handoff**:
When complete or genuinely blocked, document:
- Tasks completed (with commits if possible)
- Tasks remaining (if blocked)
- Quality metrics before/after
- Any architectural decisions made
- What local agent needs to verify/complete
