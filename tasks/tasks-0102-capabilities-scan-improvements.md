# Task List: Capabilities System - Comprehensive Review & Optimization

**Source**: User request via /task_it + /polish_it findings
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev
**Created**: 2025-12-05 09:10
**Updated**: 2025-12-05 09:30

---

## Summary

**Goal**: Complete end-to-end review, optimization, and verification of the entire Capabilities system - UI, backend, scanners, tasks, and database. Ensure all 9 tabs work correctly with accurate, fresh data. **NEW**: Add Features tab implementing Anthropic's long-running agent patterns.

**Scope**: ALL components of /capabilities page:
1. Dashboard (summary cards, health overview)
2. Database (78 tables)
3. Tasks (60 background tasks)
4. Endpoints (58 API endpoints)
5. Insights (AI-generated findings)
6. Gaps (trading capability gaps)
7. Sources (data providers)
8. Rules (trading rules)
9. **Features (NEW)** - user-facing functionality tracking with corruption protection

**Approach**: Audit each component, verify data accuracy, fix issues, optimize performance, add E2E tests.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         /capabilities UI                              │
├─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┤
│Dashboard│Database │ Tasks   │Endpoints│Insights │ Gaps    │Features │
│         │         │         │         │         │         │  (NEW)  │
│ Sources │ Rules   │         │         │         │         │         │
└────┬────┴────┬────┴────┬────┴────┬────┴────┬────┴────┬────┴────┬────┘
     │         │         │         │         │         │         │
┌────▼────┐┌───▼───┐┌────▼────┐┌───▼────┐┌───▼────┐┌──▼─────┐┌──▼─────┐
│db_caps  ││celery ││api_caps ││insights││gaps    ││sources ││feature │
│scanner  ││scanner││scanner  ││analyzer││analyzer││registry││scanner │
└────┬────┘└───┬───┘└────┬────┘└───┬────┘└───┬────┘└───┬────┘└───┬────┘
     │         │         │         │         │         │         │
┌────▼─────────▼─────────▼─────────▼─────────▼─────────▼─────────▼────┐
│                          PostgreSQL                                  │
│  db_capabilities | celery_capabilities | api_capabilities           │
│  capability_insights | trading_gaps | api_sources_registry          │
│  feature_capabilities (NEW)                                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    tasks/*.md (Feature Details)                      │
│  Linked via task_file + task_section fields                         │
│  Agent permissions: task_it adds, do_it verifies (passes only)      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tasks

### 0.0 Scope Discovery & Baseline (MANDATORY)

- [ ] 0.1 Document current state of each tab
  - Screenshot each tab, note row counts
  - Record last_scanned_at timestamps
  - Note any visible errors/warnings
- [ ] 0.2 Identify all backend components
  - Scanners: capability_db_scanner.py, capability_celery_scanner.py, capability_api_scanner.py
  - Analyzers: ai_analyzer.py, gap_analysis_tasks.py
  - APIs: capabilities_router.py, insights_router.py, gaps_router.py
  - Tasks: capability_tasks.py, maintenance_tasks.py
- [ ] 0.3 Verify scheduled tasks exist
  - Check celery_schedules.py for all capability-related tasks
  - Verify execution frequency
- [ ] 0.4 Baseline performance
  - Time full scan execution
  - Note any slow queries

### 1.0 Dashboard Tab Review

- [ ] 1.1 Verify summary cards are accurate
  - Database Tables count matches actual
  - Background Tasks count matches actual
  - API Endpoints count matches actual
  - Health status breakdown is correct
- [ ] 1.2 Verify "Recent Critical & High Priority Insights"
  - Are insights fresh (not stale)?
  - Do they link to correct items?
  - Is severity classification correct?
- [ ] 1.3 Test "Scan System" button
  - Does it trigger scan?
  - Does UI update after scan?
  - Is there progress indication?

### 2.0 Database Tab Review

- [ ] 2.1 Verify table list is complete
  - Compare against actual `\dt` in psql
  - No missing tables
  - No phantom/dropped tables
- [ ] 2.2 Verify row counts are accurate
  - Spot-check 10 random tables
  - Compare UI count vs `SELECT COUNT(*)`
- [ ] 2.3 Verify freshness data
  - Are date_range_start/end correct?
  - Is days_since_update accurate?
  - Is freshness_status (fresh/stale/critical) correct?
- [ ] 2.4 Verify health status logic
  - Active: Has data, recently updated
  - Suspect: Low completeness or stale
  - Orphaned: No references
  - Legacy: Deprecated
- [ ] 2.5 Test filtering and search
  - Category filter works
  - Health filter works
  - Search finds tables

### 3.0 Tasks Tab Review

- [ ] 3.1 Verify task list is complete
  - Compare against celery_schedules.py beat_schedule
  - No missing scheduled tasks
  - No phantom/removed tasks
- [ ] 3.2 Verify schedule information
  - Crontab/interval correct
  - Next run time calculated correctly
- [ ] 3.3 Verify execution metrics
  - last_run_at matches reality
  - success_count_7d / failure_count_7d accurate
  - success_rate_pct calculated correctly
- [ ] 3.4 Verify health status logic
  - Active: Running on schedule, good success rate
  - Legacy: Old/deprecated tasks
  - Orphaned: Not in beat_schedule but still registered
- [ ] 3.5 Verify populates_tables linkage
  - Are table dependencies correct?
  - Cross-reference with actual INSERT statements

### 4.0 Endpoints Tab Review

- [ ] 4.1 Verify endpoint list is complete
  - Compare against actual FastAPI routes
  - All routers included (api/, capabilities/, etc.)
  - Router prefixes correctly applied
- [ ] 4.2 Verify depends_on_tables
  - Spot-check 10 endpoints
  - Do detected tables match actual SQL queries?
- [ ] 4.3 Verify frontend_callers detection
  - Are template literals detected?
  - Are useSWR calls detected?
  - Are API client calls detected?
- [ ] 4.4 Verify health status logic
  - Active: Has frontend callers OR table deps
  - Orphaned: No callers AND no deps
  - Fix any false positives
- [ ] 4.5 Fix router prefix bug (DONE)
  - ✅ Already fixed in this session

### 5.0 Insights Tab Review

- [ ] 5.1 Verify insights are being generated
  - Check last insight timestamp
  - Verify AI analyzer is running
- [ ] 5.2 Verify insight quality
  - Are insights actionable?
  - Is severity (CRITICAL/HIGH/MEDIUM/LOW) appropriate?
  - Do insights link to correct capabilities?
- [ ] 5.3 Verify insight categories
  - db: Database issues
  - celery: Task issues
  - api: Endpoint issues
  - missing: Missing data
- [ ] 5.4 Test insight status workflow
  - pending → acknowledged → resolved
  - Status changes persist
- [ ] 5.5 Check for stale/duplicate insights
  - Old insights that no longer apply
  - Duplicate entries for same issue

### 6.0 Gaps Tab Review

- [ ] 6.1 Verify gaps are being identified
  - Check gap_analysis_tasks execution
  - Are new gaps being detected?
- [ ] 6.2 Verify gap definitions
  - Are GAP-XXX codes documented?
  - Do gaps link to relevant capabilities?
- [ ] 6.3 Verify gap resolution tracking
  - Can gaps be marked resolved?
  - Resolution status persists
- [ ] 6.4 Check gap criticality
  - CRITICAL/HIGH/MEDIUM/LOW appropriate?
  - Priority ordering correct?

### 7.0 Sources Tab Review

- [ ] 7.1 Verify sources list
  - All data providers shown
  - Configuration accurate
- [ ] 7.2 Verify source health
  - API key status correct
  - Rate limit info accurate
  - Last success timestamp correct
- [ ] 7.3 Test source details expansion
  - Endpoints list complete
  - GAP coverage accurate

### 8.0 Rules Tab Review

- [ ] 8.1 Verify rules list
  - Trading rules from config loaded
  - Rule definitions accurate
- [ ] 8.2 Verify rule validation
  - Rules being validated against trades
  - Violation detection working
- [ ] 8.3 Test rule editing (if applicable)
  - Can rules be modified?
  - Changes persist

### 9.0 Data Pipeline Verification

- [ ] 9.1 Verify scan → insights → gaps pipeline
  - scan_all_capabilities runs first
  - analyze_capabilities_ai runs after scan
  - analyze_trading_gaps runs after insights
- [ ] 9.2 Verify cleanup logic
  - Stale entries removed on scan (API scanner ✅)
  - Stale entries removed (Celery scanner ✅)
  - Stale entries removed (DB scanner ✅)
- [ ] 9.3 Verify scheduled execution
  - All tasks in beat_schedule
  - Appropriate frequency
- [ ] 9.4 Add missing pipeline connections
  - Insights should trigger on scan completion
  - Gaps should trigger on insights completion

### 10.0 Performance Optimization

- [ ] 10.1 Benchmark current performance
  - Full scan time: [TBD] (target <30s)
  - UI load time: [TBD] (target <2s)
  - Individual tab load: [TBD]
- [ ] 10.2 Optimize slow queries
  - Profile DB queries
  - Add indexes if needed
- [ ] 10.3 Batch database operations
  - Avoid N+1 queries
  - Use bulk inserts
- [ ] 10.4 Cache expensive computations
  - Frontend file scanning
  - Regex compilations

### 11.0 End-to-End UI Testing

- [ ] 11.1 Test Dashboard tab
  - Loads without errors
  - Data is current (not stale)
  - Scan button works
- [ ] 11.2 Test Database tab
  - Table list loads
  - Filters work
  - Click-through to details works
- [ ] 11.3 Test Tasks tab
  - Task list loads
  - Schedule info accurate
  - Metrics display correctly
- [ ] 11.4 Test Endpoints tab
  - Endpoint list loads
  - Health status correct (no false orphans)
  - Dependencies shown
- [ ] 11.5 Test Insights tab
  - Insights load
  - Status changes work
  - Filtering works
- [ ] 11.6 Test Gaps tab
  - Gaps load
  - Resolution workflow works
- [ ] 11.7 Test Sources tab
  - Sources load
  - Details expand correctly
- [ ] 11.8 Test Rules tab
  - Rules load
  - Validation info shown
- [ ] 11.9 Console error check
  - No JavaScript errors
  - No failed API calls
  - No hydration errors

### 12.0 Features Tab Implementation (Long-Running Agent Patterns)

*Implements Anthropic's long-running agent patterns via capabilities extension*

- [ ] 12.1 Create feature_capabilities table (migration)
  - Fields: feature_id, name, category, description, passes, task_file, task_section
  - Indexes on feature_id, category, health_status
  - passes: null=not reviewed, false=failing, true=verified
- [ ] 12.2 Create capability_feature_scanner.py
  - Validates task_file exists
  - Checks task_section completion status
  - Updates health_status based on passes + task completion
  - **Key**: Scanner can only modify passes, health_status, last_verified_at
- [ ] 12.3 Register scanner in capability_tasks.py
  - Add to scan_all_capabilities task
  - Add individual scan_feature_capabilities task
- [ ] 12.4 Create features_router.py API endpoints
  - GET /api/capabilities/features - List all features
  - GET /api/capabilities/features/{id} - Get feature detail
  - POST /api/capabilities/features - Add feature (task_it only)
  - PATCH /api/capabilities/features/{id}/passes - Update passes (do_it only)
- [ ] 12.5 Add Features tab to /capabilities UI
  - New tab alongside existing 8 tabs
  - Table with: ID, Name, Category, Passes, Health, Task Link
  - Filters: Category, Health, Passes status
- [ ] 12.6 Create FeaturesTab.tsx component
  - Click to expand: Shows linked task section
  - Color-coded passes status (green/red/gray)
- [ ] 12.7 Add to Dashboard summary cards
  - Features count card
  - Features health breakdown (verified/failing/unreviewed)
- [ ] 12.8 Audit and populate initial features (~80-120 features)
  - Systematically review each page/feature
  - Create comprehensive feature list
- [ ] 12.9 Create category task files for feature details
  - tasks/tasks-features-dashboard.md
  - tasks/tasks-features-watchlist.md
  - tasks/tasks-features-portfolio.md
  - tasks/tasks-features-trading.md
  - tasks/tasks-features-agents.md
  - tasks/tasks-features-status.md
  - tasks/tasks-features-settings.md
  - tasks/tasks-features-capabilities.md
- [ ] 12.10 Update CLAUDE.md with feature registry rules
  - Agent boundaries: task_it adds, do_it verifies
  - Feature discovery protocol
- [ ] 12.11 Test feature verification workflow
  - Add feature via /task_it
  - Verify feature via /do_it (passes: null → true)
  - Scanner detects inconsistencies

---

## Already Fixed (This Session)

1. ✅ Router prefix now included in API endpoint paths
2. ✅ Self-healing cleanup added to API scanner
3. ✅ Manual DB fix for existing orphan entries
4. ✅ Orphaned count reduced from 6 to 0

---

## Files Reference

**Scanners:**
- `backend/app/services/capability_db_scanner.py`
- `backend/app/services/capability_celery_scanner.py`
- `backend/app/services/capability_api_scanner.py`
- `backend/app/services/capability_feature_scanner.py` **(NEW)**

**Analyzers:**
- `backend/app/services/ai_analyzer.py`
- `backend/app/tasks/gap_analysis_tasks.py`

**APIs:**
- `backend/app/api/capabilities/` (router files)
- `backend/app/api/capabilities/features_router.py` **(NEW)**
- `backend/app/api/gaps.py`
- `backend/app/api/sources.py`

**Tasks:**
- `backend/app/tasks/capability_tasks.py`
- `backend/app/celery_schedules.py`

**Frontend:**
- `frontend/app/capabilities/page.tsx`
- `frontend/components/capabilities/`
- `frontend/components/capabilities/FeaturesTab.tsx` **(NEW)**

**Feature Task Files (NEW):**
- `tasks/tasks-features-dashboard.md`
- `tasks/tasks-features-watchlist.md`
- `tasks/tasks-features-portfolio.md`
- `tasks/tasks-features-trading.md`
- `tasks/tasks-features-agents.md`
- `tasks/tasks-features-status.md`
- `tasks/tasks-features-settings.md`
- `tasks/tasks-features-capabilities.md`

---

## Verification Checklist

- [ ] All 9 tabs load without errors (including new Features tab)
- [ ] Data is fresh (updated within 24h)
- [ ] No false positives (orphaned items that aren't)
- [ ] No missing data (items that should appear but don't)
- [ ] Performance: Full scan <30s, UI load <2s
- [ ] Pipeline: Scan → Insights → Gaps runs correctly
- [ ] Self-healing: Stale entries auto-cleaned
- [ ] Features tab: Corruption protection working (passes field only editable by do_it)
- [ ] Features tab: Task file linkage working (task_section maps to markdown sections)
- [ ] Features tab: Initial features populated (~80-120 features catalogued)
