# Handoff: Maintenance System Local Testing

**Feature**: Database Maintenance System with CLI Scripts and Status Page UI
**Created**: 2025-11-11
**Task File**: `tasks/tasks-0001-maintenance-system.md`
**Branch**: `claude/setup-task-methodology-011CV2G2zWht3hZwUkDZEkiQ`

---

## Overview

This handoff document provides step-by-step instructions for testing the maintenance system locally. All code has been written in the cloud environment. The following steps require a local environment with:
- PostgreSQL database access
- Backend service running
- Frontend development server
- Ability to run migrations and tests

---

## Files Created/Modified

### Backend
- ✅ `backend/migrations/001_maintenance_log.sql` - Database migration
- ✅ `backend/app/scripts/__init__.py` - Scripts package
- ✅ `backend/app/scripts/cleanup_old_news.py` - Cleanup CLI script
- ✅ `backend/app/scripts/vacuum_database.py` - Vacuum CLI script
- ✅ `backend/app/scripts/validate_data_integrity.py` - Validation CLI script
- ✅ `backend/app/api/maintenance.py` - API endpoints (NEW)
- ✅ `backend/app/main.py` - Router registration (MODIFIED)

### Frontend
- ✅ `frontend/lib/api/maintenance.ts` - API client (NEW)
- ✅ `frontend/components/ui/switch.tsx` - Switch component (NEW)
- ✅ `frontend/components/status/MaintenanceCard.tsx` - Maintenance card (NEW)
- ✅ `frontend/app/status/page.tsx` - Status page integration (MODIFIED)

---

## Step-by-Step Testing Instructions

### Phase 1: Database Migration

**Goal**: Apply the maintenance_log table migration

1. **Navigate to backend directory**:
   ```bash
   cd ~/portfolio-ai/backend
   source .venv/bin/activate
   ```

2. **Verify migration file exists**:
   ```bash
   ls -l ../migrations/001_maintenance_log.sql
   ```
   Expected: File exists with CREATE TABLE statement

3. **Check if backend is running** (migration happens on startup):
   ```bash
   systemctl is-active portfolio-backend
   ```

4. **If backend is running, restart to apply migration**:
   ```bash
   bash ~/portfolio-ai/scripts/restart.sh
   ```

5. **Verify migration was applied**:
   ```bash
   psql -U portfolio_ai_user -d portfolio_ai -c "\d maintenance_log"
   ```
   Expected output: Table definition with columns:
   - id (serial primary key)
   - task_name (text with CHECK constraint)
   - started_at (timestamp)
   - completed_at (timestamp, nullable)
   - status (text with CHECK constraint)
   - dry_run (boolean)
   - summary (jsonb, nullable)
   - error_message (text, nullable)

6. **Verify indexes were created**:
   ```bash
   psql -U portfolio_ai_user -d portfolio_ai -c "\d+ maintenance_log" | grep INDEX
   ```
   Expected: 4 indexes (primary key + 3 custom indexes)

**Verification**:
- ✅ Migration applied without errors
- ✅ Table `maintenance_log` exists
- ✅ All columns have correct types
- ✅ CHECK constraints on task_name and status
- ✅ Indexes created

---

### Phase 2: CLI Scripts Testing

**Goal**: Test each maintenance script standalone with --dry-run

#### Test 1: Cleanup Old News Script

1. **Run in dry-run mode**:
   ```bash
   cd ~/portfolio-ai/backend
   python -m app.scripts.cleanup_old_news --dry-run --days 90
   ```

2. **Expected output** (JSON format):
   ```json
   {
     "deleted": <number>,
     "dry_run": true,
     "cutoff_date": "2025-XX-XX...",
     "oldest_date": "...",
     "newest_date": "..."
   }
   ```

3. **Verify no actual deletion occurred**:
   ```bash
   psql -U portfolio_ai_user -d portfolio_ai -c "SELECT COUNT(*) FROM news_headlines WHERE published_at < NOW() - INTERVAL '90 days';"
   ```
   Expected: Same count as reported by script

4. **Test with different days argument**:
   ```bash
   python -m app.scripts.cleanup_old_news --dry-run --days 30
   ```

5. **(Optional) Test actual deletion**:
   ```bash
   # CAUTION: This will actually delete data!
   python -m app.scripts.cleanup_old_news --days 90
   ```

**Verification**:
- ✅ Script runs without errors
- ✅ JSON output is valid
- ✅ Dry-run mode doesn't delete data
- ✅ Script logs to console with structured logging

#### Test 2: Vacuum Database Script

1. **Run in dry-run mode**:
   ```bash
   python -m app.scripts.vacuum_database --dry-run
   ```

2. **Expected output** (JSON format):
   ```json
   {
     "tables": [
       {
         "table": "news_headlines",
         "before_mb": 12.34,
         "after_mb": 12.34,
         "reclaimed_mb": 0.0
       },
       ...
     ],
     "total_before_mb": 123.45,
     "total_after_mb": 123.45,
     "total_reclaimed_mb": 0.0,
     "dry_run": true,
     "tables_processed": 15
   }
   ```

3. **Test vacuum specific tables**:
   ```bash
   python -m app.scripts.vacuum_database --dry-run --tables news_headlines day_bars
   ```

4. **(Optional) Test actual vacuum**:
   ```bash
   # This is safe - VACUUM ANALYZE doesn't delete data
   python -m app.scripts.vacuum_database
   ```

**Verification**:
- ✅ Script runs without errors
- ✅ JSON output includes all tables
- ✅ Size calculations are reasonable
- ✅ --tables filter works

#### Test 3: Validate Data Integrity Script

1. **Run validation checks**:
   ```bash
   python -m app.scripts.validate_data_integrity --dry-run
   ```

2. **Expected output** (JSON format):
   ```json
   {
     "checks_run": 5,
     "total_errors": 0,
     "total_warnings": 2,
     "total_info": 1,
     "dry_run": true,
     "checks": [
       {
         "table": "watchlist_snapshots",
         "check": "orphaned_records",
         "issue_count": 0,
         "severity": "ok",
         "description": "..."
       },
       ...
     ]
   }
   ```

3. **Check exit code**:
   ```bash
   python -m app.scripts.validate_data_integrity --dry-run
   echo "Exit code: $?"
   ```
   Expected exit codes:
   - 0 = All checks passed
   - 1 = Warnings found
   - 2 = Errors found
   - 3 = Script error

**Verification**:
- ✅ Script runs without errors
- ✅ All 5 integrity checks execute
- ✅ JSON output shows check results
- ✅ Exit code reflects severity

---

### Phase 3: Backend API Testing

**Goal**: Test API endpoints with curl

1. **Ensure backend is running**:
   ```bash
   systemctl is-active portfolio-backend
   curl http://192.168.8.233:8000/api/health
   ```

2. **Test POST /api/maintenance/cleanup-news (dry-run)**:
   ```bash
   curl -X POST http://192.168.8.233:8000/api/maintenance/cleanup-news \
     -H "Content-Type: application/json" \
     -d '{"dry_run": true, "days": 90}' \
     | jq .
   ```
   Expected: MaintenanceResult with task_id, status, summary

3. **Test POST /api/maintenance/vacuum-database (dry-run)**:
   ```bash
   curl -X POST http://192.168.8.233:8000/api/maintenance/vacuum-database \
     -H "Content-Type: application/json" \
     -d '{"dry_run": true}' \
     | jq .
   ```

4. **Test POST /api/maintenance/validate-integrity**:
   ```bash
   curl -X POST http://192.168.8.233:8000/api/maintenance/validate-integrity \
     -H "Content-Type: application/json" \
     -d '{"dry_run": true}' \
     | jq .
   ```

5. **Test GET /api/maintenance/last-run**:
   ```bash
   curl http://192.168.8.233:8000/api/maintenance/last-run | jq .
   ```
   Expected: LastRunSummary with cleanup_news, vacuum_database, validate_integrity

6. **Test GET /api/maintenance/history**:
   ```bash
   curl "http://192.168.8.233:8000/api/maintenance/history?limit=10" | jq .
   ```
   Expected: Array of maintenance runs

7. **Verify maintenance_log table was updated**:
   ```bash
   psql -U portfolio_ai_user -d portfolio_ai -c "SELECT * FROM maintenance_log ORDER BY started_at DESC LIMIT 5;"
   ```
   Expected: Recent entries for each task you triggered

**Verification**:
- ✅ All POST endpoints return MaintenanceResult
- ✅ Scripts execute and results are stored in database
- ✅ GET /last-run returns most recent run for each task
- ✅ GET /history returns chronological list
- ✅ maintenance_log table updates correctly
- ✅ Error handling works (test with invalid params)

---

### Phase 4: Frontend UI Testing

**Goal**: Test MaintenanceCard component in browser

1. **Ensure frontend is running**:
   ```bash
   systemctl is-active portfolio-frontend
   ```
   Or start dev server:
   ```bash
   cd ~/portfolio-ai/frontend
   npm run dev
   ```

2. **Open status page in browser**:
   ```
   http://192.168.8.233:3000/status
   ```

3. **Scroll to "Database Maintenance" section** (below Celery Monitoring)

4. **Verify MaintenanceCard displays**:
   - ✅ Card title: "Database Maintenance"
   - ✅ Three task sections visible:
     - Cleanup Old News (orange trash icon)
     - Vacuum Database (blue database icon)
     - Validate Data Integrity (green checkmark icon)
   - ✅ Dry Run toggle switch at top (default: ON)
   - ✅ Refresh button at top right

5. **Test "Never run" state**:
   - If you haven't run tasks yet, should see "Never run" for each task
   - If you ran tasks in Phase 3, should see last run timestamp and status

6. **Test Cleanup Old News**:
   - Enable Dry Run toggle
   - Click Play button on "Cleanup Old News"
   - Confirm dialog appears with preview message
   - Click "Preview Cleanup"
   - Wait for execution (spinner shows on button)
   - Alert shows result: "X articles would be deleted"
   - Card refreshes to show last run details

7. **Test Vacuum Database**:
   - Disable Dry Run toggle
   - Click Play button on "Vacuum Database"
   - Confirm dialog warns about actual vacuum
   - Click "Vacuum Database"
   - Wait for execution
   - Alert shows result: "X MB reclaimed"
   - Card updates with summary stats

8. **Test Validate Data Integrity**:
   - Enable Dry Run toggle
   - Click Play button on "Validate Data Integrity"
   - Confirm dialog appears
   - Click "Check Integrity"
   - Wait for execution
   - Alert shows: "X issues found (Y errors, Z warnings)"
   - Card displays check results

9. **Test "Don't ask me again" checkbox**:
   - Trigger any task
   - Check "Don't ask me again" in dialog
   - Click confirm
   - Trigger same task again
   - Verify dialog doesn't appear (runs immediately)

10. **Test refresh button**:
    - Click refresh button at top of card
    - Verify spinner shows briefly
    - Card updates with latest data

11. **Test error handling**:
    - Stop backend: `bash ~/portfolio-ai/scripts/shutdown.sh`
    - Try to trigger a task
    - Verify error alert shows with helpful message
    - Start backend: `bash ~/portfolio-ai/scripts/start.sh`

**Verification**:
- ✅ MaintenanceCard renders correctly
- ✅ All three task sections display
- ✅ Dry run toggle works
- ✅ Confirmation dialogs appear (with don't ask again option)
- ✅ Tasks execute and show results
- ✅ Summary displays correctly for each task type
- ✅ Status badges show correct state (success/error/running)
- ✅ Refresh button updates data
- ✅ Error handling shows user-friendly messages

---

### Phase 5: Integration Testing

**Goal**: Test full workflow end-to-end

1. **Scenario: Cleanup old news with dry-run**:
   - Open status page
   - Enable Dry Run
   - Click "Cleanup Old News"
   - Confirm dialog
   - Verify:
     - Backend executes script
     - maintenance_log updated
     - UI shows result
     - No data actually deleted

2. **Scenario: Vacuum database without dry-run**:
   - Disable Dry Run
   - Click "Vacuum Database"
   - Confirm dialog
   - Verify:
     - Backend executes VACUUM ANALYZE
     - Tables optimized
     - Space reclaimed (if any)
     - UI shows before/after sizes

3. **Scenario: Validate integrity and check logs**:
   - Enable Dry Run
   - Click "Validate Data Integrity"
   - Check backend logs:
     ```bash
     tail -f /var/log/portfolio-ai/backend.log | grep validate
     ```
   - Verify structured logging output

4. **Scenario: Multiple rapid executions**:
   - Try clicking multiple task buttons quickly
   - Verify only one executes at a time (button shows spinner)
   - Verify no race conditions

**Verification**:
- ✅ End-to-end workflow works smoothly
- ✅ Data flows correctly: UI → API → Script → Database → UI
- ✅ Logs show structured output
- ✅ No race conditions or concurrent execution issues

---

### Phase 6: Code Quality Checks

**Goal**: Verify code quality standards

1. **Run linting**:
   ```bash
   cd ~/portfolio-ai
   bash scripts/lint.sh
   ```
   Expected: All checks pass (ruff + mypy)

2. **Check file sizes**:
   ```bash
   wc -l backend/app/scripts/*.py
   wc -l backend/app/api/maintenance.py
   wc -l frontend/components/status/MaintenanceCard.tsx
   ```
   Expected: All files under 500 lines

3. **Run backend tests**:
   ```bash
   cd ~/portfolio-ai/backend
   source .venv/bin/activate
   pytest tests/ -v -k maintenance
   ```
   Expected: Tests pass (if any exist)

4. **Check for SQL injection vulnerabilities**:
   ```bash
   grep -r "execute(f\"" backend/app/scripts/
   grep -r "execute(f\"" backend/app/api/maintenance.py
   ```
   Expected: No f-string SQL queries (all use parameterized queries)

**Verification**:
- ✅ Linting passes (ruff + mypy)
- ✅ File sizes within guidelines
- ✅ No SQL injection vulnerabilities
- ✅ Proper type hints on all functions
- ✅ Tests pass (if implemented)

---

## Expected Behaviors

### Dry Run Mode
- **ON**: Scripts preview what would be done without making changes
- **OFF**: Scripts execute actual operations (delete, vacuum, fix)
- Default: ON for cleanup/validate, OFF for vacuum

### Confirmation Dialogs
- First time: Dialog appears with "Don't ask me again" checkbox
- After "don't ask": Task executes immediately
- Storage: Uses localStorage with key `status.confirm.<taskName>`

### Error States
- Script execution fails: Shows error message in alert and card
- Backend unreachable: Shows fetch error in alert
- Invalid parameters: API returns 400 with helpful message

### Performance
- Scripts run asynchronously (don't block UI)
- Card refreshes automatically after task completion
- Manual refresh available via refresh button

---

## Troubleshooting

### Migration doesn't apply
- Check backend logs: `tail -f /var/log/portfolio-ai/backend.log`
- Verify migration file syntax: `cat backend/migrations/001_maintenance_log.sql`
- Check schema_migrations table: `SELECT * FROM schema_migrations;`

### CLI script fails
- Check Python path: `which python` should be venv python
- Verify imports: `python -c "from app.scripts import cleanup_old_news"`
- Check database connection: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT 1;"`

### API returns 500
- Check backend logs for Python exceptions
- Verify scripts are executable: `ls -l backend/app/scripts/*.py`
- Test script manually first

### UI doesn't show data
- Check browser console for errors (F12)
- Verify API is accessible: `curl http://192.168.8.233:8000/api/maintenance/last-run`
- Check CORS configuration in backend

### Dry run doesn't work
- Verify `dry_run` parameter is passed in request body
- Check script receives `--dry-run` flag in logs
- Test script manually with --dry-run

---

## Success Criteria

✅ **All phases completed successfully**:
- [ ] Phase 1: Migration applied and table created
- [ ] Phase 2: All three CLI scripts work standalone
- [ ] Phase 3: API endpoints trigger scripts and store results
- [ ] Phase 4: Frontend UI displays and triggers tasks
- [ ] Phase 5: End-to-end workflows complete successfully
- [ ] Phase 6: Code quality checks pass

✅ **Functional requirements met**:
- [ ] Cleanup script removes old news (with dry-run support)
- [ ] Vacuum script optimizes database tables
- [ ] Validation script checks data integrity
- [ ] API stores results in maintenance_log table
- [ ] UI shows last run times and summaries
- [ ] Dry-run toggle works correctly
- [ ] Confirmation dialogs prevent accidents

✅ **No regressions**:
- [ ] Existing status page features still work
- [ ] Backend starts without errors
- [ ] All existing tests still pass
- [ ] No new mypy or ruff errors

---

## Next Steps After Testing

1. **If all tests pass**:
   - Update WORK_TRACKER.md to mark task as complete
   - Create PR description summarizing changes
   - Merge to main branch

2. **If issues found**:
   - Document issues in task file
   - Create follow-up tasks for fixes
   - Prioritize based on severity

3. **Future enhancements** (not required now):
   - Schedule automatic cleanup via Celery Beat
   - Add email notifications for failures
   - Export maintenance history to CSV
   - Add more integrity checks
   - Create admin UI for scheduling

---

## Contact

If you encounter issues or have questions:
- Check logs: `/var/log/portfolio-ai/`
- Review task file: `tasks/tasks-0001-maintenance-system.md`
- See architecture: `docs/core/ARCHITECTURE.md`
- Development guide: `docs/core/DEVELOPMENT.md`

---

**Happy Testing! 🚀**
