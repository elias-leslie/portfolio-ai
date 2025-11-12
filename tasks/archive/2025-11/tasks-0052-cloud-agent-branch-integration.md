# Task List: Cloud Agent Branch Integration

**Source**: 6 cloud agent branches ready for local testing and merge
**Complexity**: Complex (multi-branch integration with dependencies)
**Effort**: HIGH (6 branches × full testing cycle each)
**Environment**: Local Dev (full capabilities required)
**Created**: 2025-11-11

---

## Summary

**Goal**: Finalize and merge 6 cloud agent feature branches to main, ensuring quality and proper integration

**Branches (in merge order)**:
1. `claude/setup-task-methodology-011CV2FAdKrkUXCGLAd9MgHf` - API documentation
2. `claude/setup-task-methodology-011CV2GqBz4TZnsHTU3B6Fq2` - Celery logging enhancement
3. `claude/setup-task-methodology-011CV2GyoVTgkzZEveAK5kGc` - Response caching middleware
4. `claude/setup-task-methodology-011CV2FDTdmqkCz1ktpAfeMk` - Health endpoint enhancements
5. `claude/setup-task-methodology-011CV2GuHofCtCQoxBJeZXbN` - Toast notification system
6. `claude/setup-task-methodology-011CV2G2zWht3hZwUkDZEkiQ` - Maintenance CLI scripts

**Approach**: Test and merge each branch sequentially with full quality checks

**Strategy** (based on user choices):
- ✅ Merge immediately after testing passes
- ✅ Restart services after each merge
- ✅ Archive task files after successful merge
- ✅ Full pytest (508 tests) after each merge

---

## Tasks

### 1.0 Branch 1: API Documentation Enhancement

**Branch**: `claude/setup-task-methodology-011CV2FAdKrkUXCGLAd9MgHf`
**Scope**: Documentation only (no code logic changes)
**Files**: API endpoint docstrings, Pydantic model examples

- [ ] 1.1 Checkout and verify branch
  - [ ] Fetch latest: `git fetch origin`
  - [ ] Checkout: `git checkout claude/setup-task-methodology-011CV2FAdKrkUXCGLAd9MgHf`
  - [ ] Verify commits: `git log --oneline -5`
  - [ ] Check file changes: `git diff --stat origin/main`

- [ ] 1.2 Run code quality checks
  - [ ] Run linting: `bash ~/portfolio-ai/scripts/lint.sh`
  - [ ] Verify no new ruff errors
  - [ ] Verify no new mypy errors
  - [ ] Check file sizes: All files under 800 lines

- [ ] 1.3 Run backend tests
  - [ ] Activate venv: `cd ~/portfolio-ai/backend && source .venv/bin/activate`
  - [ ] Run full pytest: `pytest tests/ -v`
  - [ ] Verify all 508 tests pass
  - [ ] No new test failures

- [ ] 1.4 Manual verification via Swagger UI
  - [ ] Start services: `bash ~/portfolio-ai/scripts/start.sh`
  - [ ] Open: http://localhost:8000/docs
  - [ ] Verify Ideas API documentation enhanced
  - [ ] Verify Watchlist API documentation enhanced
  - [ ] Verify Portfolio API documentation enhanced
  - [ ] Check example schemas visible in Swagger UI

- [ ] 1.5 Merge to main
  - [ ] Switch to main: `git checkout main`
  - [ ] Pull latest: `git pull origin main`
  - [ ] Merge branch: `git merge --no-ff claude/setup-task-methodology-011CV2FAdKrkUXCGLAd9MgHf`
  - [ ] Resolve conflicts if any
  - [ ] Verify merge successful: `git log --oneline -3`

- [ ] 1.6 Post-merge verification
  - [ ] No service restart needed (docs only)
  - [ ] Verify Swagger UI still shows enhanced docs
  - [ ] Run quick smoke test: `curl http://localhost:8000/docs`

- [ ] 1.7 Archive task artifacts
  - [ ] Move to archive: `tasks/tasks-0038-api-documentation-enhancement.md`
  - [ ] Remove handoff: `tasks/HANDOFF-api-documentation-local-testing.md`
  - [ ] Archive directory: `tasks/archive/2025-11/`

- [ ] 1.8 Update WORK_TRACKER.md
  - [ ] Mark API documentation task as completed
  - [ ] Add completion notes
  - [ ] Commit changes

### 2.0 Branch 2: Celery Logging Enhancement

**Branch**: `claude/setup-task-methodology-011CV2GqBz4TZnsHTU3B6Fq2`
**Scope**: Structured logging for all Celery tasks (foundation layer)
**Files**: 8 task files + new task_logging.py utility

- [ ] 2.1 Checkout and verify branch
  - [ ] Ensure on main: `git checkout main`
  - [ ] Fetch latest: `git fetch origin`
  - [ ] Checkout: `git checkout claude/setup-task-methodology-011CV2GqBz4TZnsHTU3B6Fq2`
  - [ ] Verify commits and file changes

- [ ] 2.2 Run code quality checks
  - [ ] Run linting: `bash ~/portfolio-ai/scripts/lint.sh`
  - [ ] Verify task_logging.py has proper types
  - [ ] Check all task files pass mypy --strict
  - [ ] File size check: All files under 800 lines

- [ ] 2.3 Run backend tests
  - [ ] Run full pytest: `cd ~/portfolio-ai/backend && pytest tests/ -v`
  - [ ] Verify all 508 tests pass
  - [ ] Check for logging-related test failures

- [ ] 2.4 Manual testing of logging output
  - [ ] Restart services: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] Verify service start times
  - [ ] Trigger test task: `refresh_watchlist_scores_task.delay()`
  - [ ] Check logs: `tail -f /var/log/portfolio-ai/backend-error.log`
  - [ ] Verify structured logging fields: task_name, task_id, duration_ms, status

- [ ] 2.5 Monitor scheduled tasks (2 cycles minimum)
  - [ ] Watch Celery worker logs: `journalctl -u portfolio-celery -f`
  - [ ] Verify structured logs for: news refresh, watchlist refresh, indicators
  - [ ] Check log_task_skip() for conditional tasks
  - [ ] Verify error logging includes full traceback

- [ ] 2.6 Merge to main
  - [ ] Switch to main: `git checkout main`
  - [ ] Pull latest: `git pull origin main`
  - [ ] Merge branch: `git merge --no-ff claude/setup-task-methodology-011CV2GqBz4TZnsHTU3B6Fq2`
  - [ ] Resolve conflicts if any
  - [ ] Test after merge: Services still running correctly

- [ ] 2.7 Post-merge service verification
  - [ ] Restart: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] Verify all services active
  - [ ] Check logs for structured output
  - [ ] Monitor 2 more task cycles

- [ ] 2.8 Archive and update
  - [ ] Archive task file: tasks-0047-celery-task-structured-logging.md
  - [ ] Remove handoff: HANDOFF-celery-logging-local-testing.md
  - [ ] Update WORK_TRACKER.md
  - [ ] Commit changes

### 3.0 Branch 3: Response Caching Middleware

**Branch**: `claude/setup-task-methodology-011CV2GyoVTgkzZEveAK5kGc`
**Scope**: TTL-based response caching for expensive API calls
**Files**: New middleware package, 4 API files modified, .env.example

- [ ] 3.1 Checkout and verify branch
  - [ ] Checkout from main: `git checkout claude/setup-task-methodology-011CV2GyoVTgkzZEveAK5kGc`
  - [ ] Review commits and changes
  - [ ] Check new middleware/ package structure

- [ ] 3.2 Run code quality checks
  - [ ] Linting: `bash ~/portfolio-ai/scripts/lint.sh`
  - [ ] Verify middleware/cache.py passes mypy --strict
  - [ ] Check decorator pattern implementation
  - [ ] File sizes within limits

- [ ] 3.3 Run backend tests
  - [ ] Full pytest: `cd ~/portfolio-ai/backend && pytest tests/ -v`
  - [ ] All 508 tests pass
  - [ ] Check for caching-related issues

- [ ] 3.4 Configure caching environment
  - [ ] Check .env for CACHE_ENABLED=true
  - [ ] Set CACHE_MAX_SIZE=1000 (if not set)
  - [ ] Set CACHE_DEFAULT_TTL=300 (if not set)
  - [ ] Verify configuration loaded

- [ ] 3.5 Test cache functionality
  - [ ] Restart services: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] Test market endpoint: Cache MISS then HIT
    - [ ] First: `curl -i http://localhost:8000/api/market/conditions | grep X-Cache-Hit`
    - [ ] Second: `curl -i http://localhost:8000/api/market/conditions | grep X-Cache-Hit`
    - [ ] Verify: false → true
  - [ ] Test watchlist endpoint caching (60s TTL)
  - [ ] Test portfolio endpoint caching (30s TTL)

- [ ] 3.6 Test cache invalidation
  - [ ] Prime watchlist cache
  - [ ] Verify cache hit
  - [ ] Add watchlist item (mutation)
  - [ ] Verify cache invalidated (MISS on next GET)
  - [ ] Repeat for portfolio cache

- [ ] 3.7 Test cache management endpoints
  - [ ] GET /health/cache/stats
  - [ ] Verify response: enabled, size, hits, misses, hit_rate
  - [ ] POST /health/cache/clear
  - [ ] Verify cache cleared

- [ ] 3.8 Test TTL expiration
  - [ ] Prime watchlist cache (60s TTL)
  - [ ] Verify HIT immediately
  - [ ] Wait 61 seconds
  - [ ] Verify MISS (TTL expired)

- [ ] 3.9 Merge to main
  - [ ] Switch to main and pull
  - [ ] Merge: `git merge --no-ff claude/setup-task-methodology-011CV2GyoVTgkzZEveAK5kGc`
  - [ ] Resolve conflicts if any

- [ ] 3.10 Post-merge verification
  - [ ] Restart services
  - [ ] Verify caching still working
  - [ ] Check cache stats endpoint
  - [ ] Monitor performance for 5 minutes

- [ ] 3.11 Archive and update
  - [ ] Archive task file
  - [ ] Remove handoff document
  - [ ] Update WORK_TRACKER.md
  - [ ] Commit changes

### 4.0 Branch 4: Health Endpoint Enhancements

**Branch**: `claude/setup-task-methodology-011CV2FDTdmqkCz1ktpAfeMk`
**Scope**: Detailed health endpoint with data freshness, Celery worker, API keys status
**Files**: Backend health API/utils, frontend status page components

- [ ] 4.1 Checkout and verify branch
  - [ ] Checkout from main
  - [ ] Review 9 commits
  - [ ] Check files: 2 backend, 5 frontend

- [ ] 4.2 Run code quality checks
  - [ ] Linting backend and frontend
  - [ ] Check file sizes (health_checks.py: 625 lines, health.py: 525 lines)
  - [ ] Verify under 800 line limit
  - [ ] TypeScript compilation: `cd frontend && npm run build`

- [ ] 4.3 Run backend tests
  - [ ] Full pytest suite
  - [ ] Check health check functions work
  - [ ] Verify no regressions

- [ ] 4.4 Restart services
  - [ ] Restart all: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] Verify start times updated
  - [ ] Check service status

- [ ] 4.5 Test backend /health/detailed endpoint
  - [ ] GET /health/detailed
  - [ ] Verify JSON structure
  - [ ] Check day_bars_freshness array (if data exists)
  - [ ] Check celery_worker object (active, pool_size)
  - [ ] Check api_keys array (configured sources)
  - [ ] Check disk_usage object

- [ ] 4.6 Test frontend status page UI
  - [ ] Open: http://localhost:3000/status
  - [ ] Verify DataFreshnessCard renders
    - [ ] Shows tickers with age color-coding
    - [ ] Green: ≤1 day, Yellow: 1-7 days, Red: >7 days
    - [ ] Collapsible ticker list works
  - [ ] Verify APIKeysCard renders
    - [ ] Shows configured keys (green checkmark)
    - [ ] Shows unconfigured keys (gray X)
    - [ ] Environment variable names visible
  - [ ] Verify Celery Monitoring badges
    - [ ] "Worker Active" or "Worker Inactive"
    - [ ] "Pool: X" badge
    - [ ] "Active Tasks: X" badge

- [ ] 4.7 Test edge cases
  - [ ] Empty day_bars table handling
  - [ ] Celery worker down scenario
    - [ ] Stop worker: `bash ~/portfolio-ai/scripts/stop-celery.sh`
    - [ ] Refresh status page
    - [ ] Verify "Worker Inactive" badge (red)
    - [ ] Restart: `bash ~/portfolio-ai/scripts/start-celery.sh`
  - [ ] Verify auto-refresh (30s interval)

- [ ] 4.8 Performance check
  - [ ] Measure endpoint response time: `time curl http://localhost:8000/health/detailed`
  - [ ] Should be < 2 seconds
  - [ ] Check backend logs for errors
  - [ ] Monitor celery inspect() calls

- [ ] 4.9 Merge to main
  - [ ] Switch to main and merge
  - [ ] Resolve conflicts if any
  - [ ] Verify merge successful

- [ ] 4.10 Post-merge verification
  - [ ] Restart services
  - [ ] Verify status page works
  - [ ] Check /health/detailed endpoint
  - [ ] Monitor for issues

- [ ] 4.11 Archive and update
  - [ ] Archive tasks-0047-health-endpoint-enhancements.md
  - [ ] Remove HANDOFF-health-endpoint-local-testing.md
  - [ ] Update WORK_TRACKER.md

### 5.0 Branch 5: Toast Notification System

**Branch**: `claude/setup-task-methodology-011CV2GuHofCtCQoxBJeZXbN`
**Scope**: User feedback toasts for async operations (UX enhancement)
**Files**: useToast hook, 3 mutation hooks (watchlist, portfolio, ideas)

- [ ] 5.1 Checkout and verify branch
  - [ ] Checkout from main
  - [ ] Review commits
  - [ ] Check modified hooks

- [ ] 5.2 Run frontend checks
  - [ ] TypeScript build: `cd frontend && npm run build`
  - [ ] ESLint: `npm run lint`
  - [ ] Verify no compilation errors
  - [ ] Check useToast.ts implementation

- [ ] 5.3 Run backend tests (unchanged but verify)
  - [ ] Full pytest suite
  - [ ] Ensure no backend regressions

- [ ] 5.4 Restart services
  - [ ] Restart all: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] Verify frontend rebuild

- [ ] 5.5 Test watchlist toast notifications
  - [ ] Navigate to /watchlist
  - [ ] Add ticker (e.g., "AAPL")
  - [ ] Verify loading toast: "Adding AAPL to watchlist..."
  - [ ] Verify success toast: "AAPL added to watchlist"
  - [ ] Test duplicate ticker (error case)
  - [ ] Verify error toast with helpful message
  - [ ] Delete ticker
  - [ ] Verify removal toast

- [ ] 5.6 Test portfolio toast notifications
  - [ ] Navigate to /portfolio
  - [ ] Add position (paper)
  - [ ] Verify toast: "NVDA paper position added (10 shares @ $500.00)"
  - [ ] Update position
  - [ ] Verify toast: "NVDA position updated"
  - [ ] Delete position
  - [ ] Verify toast: "NVDA position deleted"
  - [ ] Test error case (invalid data)

- [ ] 5.7 Test ideas toast notifications (if applicable)
  - [ ] Navigate to ideas page
  - [ ] Update idea status
  - [ ] Verify toast: "Idea status updated to [status]"

- [ ] 5.8 Verify toast UI behavior
  - [ ] Position: Top-right corner
  - [ ] Styling: Green (success), Red (error), Gray (loading)
  - [ ] Auto-dismiss: ~4 seconds
  - [ ] Multiple toasts: Stack vertically
  - [ ] richColors theme working

- [ ] 5.9 Merge to main
  - [ ] Switch to main and merge
  - [ ] Resolve conflicts if any

- [ ] 5.10 Post-merge verification
  - [ ] Restart services
  - [ ] Quick smoke test of all toast scenarios
  - [ ] Verify no console errors

- [ ] 5.11 Archive and update
  - [ ] Archive tasks-0047-toast-notifications.md
  - [ ] Remove HANDOFF-toast-notifications-local-testing.md
  - [ ] Update WORK_TRACKER.md

### 6.0 Branch 6: Maintenance CLI Scripts (Most Complex)

**Branch**: `claude/setup-task-methodology-011CV2G2zWht3hZwUkDZEkiQ`
**Scope**: Database maintenance system with CLI scripts, API, UI, and MIGRATION
**Files**: 13 files (backend: 7, frontend: 5, migration: 1)

- [ ] 6.1 Checkout and verify branch
  - [ ] Checkout from main
  - [ ] Review commits
  - [ ] Check migration file: `backend/migrations/001_maintenance_log.sql`
  - [ ] Check CLI scripts: 3 scripts in backend/app/scripts/
  - [ ] Check API: backend/app/api/maintenance.py

- [ ] 6.2 Run code quality checks
  - [ ] Linting: `bash ~/portfolio-ai/scripts/lint.sh`
  - [ ] Verify all scripts pass mypy
  - [ ] Check file sizes (all under 500 lines)
  - [ ] Verify no SQL injection vulnerabilities
  - [ ] Check parameterized queries used

- [ ] 6.3 Run backend tests
  - [ ] Full pytest suite
  - [ ] Check maintenance-related tests: `pytest tests/ -v -k maintenance`

- [ ] 6.4 Apply database migration
  - [ ] Verify migration file syntax
  - [ ] Check backend migration system
  - [ ] Restart backend: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] Verify migration applied: `psql -U portfolio_ai_user -d portfolio_ai -c "\d maintenance_log"`
  - [ ] Verify table created with correct schema
  - [ ] Verify indexes created

- [ ] 6.5 Test CLI scripts standalone
  - [ ] Test cleanup_old_news.py
    - [ ] Dry-run: `python -m app.scripts.cleanup_old_news --dry-run --days 90`
    - [ ] Verify JSON output
    - [ ] Verify no deletion occurred
  - [ ] Test vacuum_database.py
    - [ ] Dry-run: `python -m app.scripts.vacuum_database --dry-run`
    - [ ] Verify output shows table sizes
  - [ ] Test validate_data_integrity.py
    - [ ] Run: `python -m app.scripts.validate_data_integrity --dry-run`
    - [ ] Verify 5 integrity checks run
    - [ ] Check exit code

- [ ] 6.6 Test backend API endpoints
  - [ ] POST /api/maintenance/cleanup-news (dry-run)
  - [ ] POST /api/maintenance/vacuum-database (dry-run)
  - [ ] POST /api/maintenance/validate-integrity
  - [ ] GET /api/maintenance/last-run
  - [ ] GET /api/maintenance/history?limit=10
  - [ ] Verify maintenance_log table updated

- [ ] 6.7 Test frontend MaintenanceCard
  - [ ] Open: http://localhost:3000/status
  - [ ] Scroll to "Database Maintenance" section
  - [ ] Verify card displays 3 task sections
  - [ ] Verify Dry Run toggle (default: ON)
  - [ ] Test "Cleanup Old News"
    - [ ] Enable dry run
    - [ ] Click play button
    - [ ] Confirm dialog
    - [ ] Verify result alert
  - [ ] Test "Vacuum Database"
    - [ ] Disable dry run
    - [ ] Execute task
    - [ ] Verify summary stats
  - [ ] Test "Validate Data Integrity"
    - [ ] Execute with dry run
    - [ ] Verify check results
  - [ ] Test "Don't ask me again" checkbox
  - [ ] Test refresh button
  - [ ] Test error handling (stop backend, try task)

- [ ] 6.8 Integration testing
  - [ ] End-to-end cleanup workflow
  - [ ] End-to-end vacuum workflow
  - [ ] Multiple rapid executions (check for race conditions)
  - [ ] Verify structured logging in backend logs

- [ ] 6.9 Merge to main
  - [ ] Switch to main and merge
  - [ ] Resolve conflicts if any (likely most complex)
  - [ ] Verify migration in main

- [ ] 6.10 Post-merge comprehensive testing
  - [ ] Restart all services
  - [ ] Verify migration still applied
  - [ ] Test all 3 CLI scripts
  - [ ] Test all API endpoints
  - [ ] Test frontend UI fully
  - [ ] Monitor for issues

- [ ] 6.11 Archive and update
  - [ ] Archive tasks-0001-maintenance-system.md
  - [ ] Remove HANDOFF-maintenance-system-local-testing.md
  - [ ] Update WORK_TRACKER.md

### 7.0 Final Integration Verification

**Scope**: Ensure all 6 features work together properly

- [ ] 7.1 Run full test suite
  - [ ] Full pytest: `cd ~/portfolio-ai/backend && pytest tests/ -v`
  - [ ] Verify all 508 tests still pass
  - [ ] No new failures introduced

- [ ] 7.2 Run comprehensive linting
  - [ ] Backend + frontend: `bash ~/portfolio-ai/scripts/lint.sh`
  - [ ] Zero ruff errors
  - [ ] Zero mypy errors
  - [ ] Frontend build successful

- [ ] 7.3 Code quality validation
  - [ ] Run quality report: `bash ~/.claude/skills/code-quality/scripts/quality-report.sh backend/app --quick`
  - [ ] Compare to baseline
  - [ ] Check for new critical issues
  - [ ] Document any new warnings

- [ ] 7.4 Service health check
  - [ ] All services active: `bash ~/portfolio-ai/scripts/status.sh`
  - [ ] Backend responding: `curl http://localhost:8000/health`
  - [ ] Frontend accessible: `curl http://localhost:3000`
  - [ ] Celery worker active
  - [ ] Celery beat scheduling

- [ ] 7.5 Functional smoke tests
  - [ ] Swagger UI documentation enhanced ✓
  - [ ] Celery tasks logging structured output ✓
  - [ ] Response caching working (check X-Cache-Hit headers) ✓
  - [ ] Health endpoint showing detailed info ✓
  - [ ] Toast notifications on mutations ✓
  - [ ] Maintenance system functional ✓

- [ ] 7.6 Monitor stability
  - [ ] Watch logs for 10 minutes: `tail -f /var/log/portfolio-ai/backend-error.log`
  - [ ] Check Celery logs: `journalctl -u portfolio-celery -f`
  - [ ] Observe at least 2 scheduled task cycles
  - [ ] Verify no errors or warnings

- [ ] 7.7 Browser testing
  - [ ] Open all pages: /watchlist, /portfolio, /ideas, /status
  - [ ] Test major workflows
  - [ ] Check browser console (no errors)
  - [ ] Verify UI responsive and functional

- [ ] 7.8 Performance validation
  - [ ] Test cached endpoints (should be faster on hits)
  - [ ] Health endpoint < 2s response time
  - [ ] Status page loads < 3s
  - [ ] No memory leaks (check htop)

### 8.0 Documentation and Cleanup

**Scope**: Update core documentation and clean up artifacts

- [ ] 8.1 Update WORK_TRACKER.md
  - [ ] Move all 6 tasks to "Recently Completed"
  - [ ] Add completion date
  - [ ] Add summary notes
  - [ ] Commit changes

- [ ] 8.2 Run /doc_it command
  - [ ] Execute: `/doc_it`
  - [ ] Review documentation updates
  - [ ] Ensure core docs reflect new features
  - [ ] Commit documentation changes

- [ ] 8.3 Verify archive structure
  - [ ] Check tasks/archive/2025-11/ has all 6 task files
  - [ ] Verify no handoff documents in tasks/
  - [ ] Clean directory structure

- [ ] 8.4 Create summary commit
  - [ ] Git status clean
  - [ ] Create final commit: "feat: integrate 6 cloud agent features (docs, logging, caching, health, toasts, maintenance)"
  - [ ] Push to origin: `git push origin main`

- [ ] 8.5 Verify remote repository
  - [ ] Check GitHub/GitLab for successful push
  - [ ] Verify all branches merged
  - [ ] Tag release if appropriate

- [ ] 8.6 Delete merged branches (optional)
  - [ ] Local cleanup: `git branch -d <branch-name>`
  - [ ] Remote cleanup: `git push origin --delete <branch-name>`
  - [ ] Or keep for historical reference

---

## Verification Checklist

### Code Quality
- [ ] All linting passes (ruff + mypy)
- [ ] All 508 tests passing
- [ ] No new critical quality issues
- [ ] File sizes within guidelines
- [ ] No SQL injection vulnerabilities
- [ ] Proper type hints maintained

### Functional Requirements
- [ ] API documentation enhanced in Swagger UI
- [ ] Celery tasks logging structured output
- [ ] Response caching functional with invalidation
- [ ] Health endpoint shows detailed system status
- [ ] Toast notifications working for all mutations
- [ ] Maintenance system fully operational (CLI + API + UI)
- [ ] Database migration applied successfully

### Integration
- [ ] No merge conflicts (or all resolved)
- [ ] All features work together
- [ ] No regressions in existing functionality
- [ ] Services stable for 10+ minutes
- [ ] No console errors
- [ ] Performance acceptable

### Documentation
- [ ] WORK_TRACKER.md updated
- [ ] Task files archived properly
- [ ] Handoff documents removed
- [ ] Core docs updated via /doc_it
- [ ] Changes pushed to remote

---

## Risk Mitigation

**High-risk areas**:
1. **Maintenance migration**: First migration in a while - verify carefully
2. **Merge conflicts**: 6 branches may touch same files (health.py, main.py)
3. **Caching**: Could cause stale data if invalidation broken
4. **Service restarts**: 6 restarts - ensure stability each time

**Mitigation strategies**:
- Full pytest after each merge (catches regressions immediately)
- Service restart verification after each merge
- Manual testing of critical paths
- Rollback plan: Git revert if major issues arise

**Rollback procedure** (if needed):
```bash
# Identify bad commit
git log --oneline -10

# Revert specific merge
git revert -m 1 <merge-commit-hash>

# Or reset to before merges (DANGER)
git reset --hard <commit-before-merges>

# Restart services
bash ~/portfolio-ai/scripts/restart.sh
```

---

## Success Criteria

✅ **All 6 branches successfully merged to main**
✅ **All 508 tests passing**
✅ **Zero linting errors**
✅ **All features functional and tested**
✅ **Services stable (10+ minute observation)**
✅ **Documentation updated and committed**
✅ **Task files archived properly**
✅ **Code quality maintained or improved**

---

## Estimated Effort

- Branch 1 (API docs): 30 min
- Branch 2 (Celery logging): 45 min
- Branch 3 (Caching): 60 min
- Branch 4 (Health): 60 min
- Branch 5 (Toasts): 45 min
- Branch 6 (Maintenance): 90 min
- Final verification: 45 min
- Documentation: 30 min

**Total**: ~6.5 hours (HIGH complexity confirmed)

---

## Notes

- **Order is critical**: Dependencies mean later branches may assume earlier features exist
- **Full testing per branch**: Expensive but catches issues early
- **Service restarts**: Ensures each feature works in isolation before adding next
- **Archive task files**: Keeps tasks/ directory clean and focused on active work
- **Migration handling**: Only Branch 6 has migration - extra care needed

**Confidence**: HIGH - All code already written and reviewed by cloud agents. Local testing is validation phase, not development phase.
