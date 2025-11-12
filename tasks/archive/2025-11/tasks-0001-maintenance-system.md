# Task 0001: Maintenance System with CLI Scripts and Status Page

**Created**: 2025-11-11
**Completed**: 2025-11-11
**Status**: Complete (Cloud) - Ready for Local Testing
**Environment**: Cloud (code + handoff) → Local (testing)

---

## Summary

### Goal
Create a comprehensive maintenance system with CLI scripts for database cleanup, vacuum, and integrity checking, plus API endpoints and UI for monitoring and triggering these operations from the status page.

### Approach
1. **Backend CLI Scripts** (`backend/app/scripts/`):
   - `cleanup_old_news.py` - Delete news older than 90 days
   - `vacuum_database.py` - Optimize PostgreSQL tables with VACUUM ANALYZE
   - `validate_data_integrity.py` - Check for orphaned records, missing FKs, data consistency
   - Each script: `--dry-run` flag, structured logging, JSON summary output

2. **Database Migration** (`backend/migrations/`):
   - Create `maintenance_log` table to store execution history and results

3. **Backend API** (`backend/app/api/maintenance.py` - NEW):
   - POST `/api/maintenance/cleanup-news` - Trigger cleanup with dry_run param
   - POST `/api/maintenance/vacuum-database` - Trigger vacuum operation
   - POST `/api/maintenance/validate-integrity` - Trigger validation
   - GET `/api/maintenance/last-run` - Get last run timestamps and results
   - GET `/api/maintenance/history` - Get full execution history

4. **Frontend UI** (`frontend/components/status/MaintenanceCard.tsx` - NEW):
   - Card showing last run times for each maintenance task
   - Buttons to trigger each task with confirmation dialogs
   - Toggle for `--dry-run` mode
   - Display results/logs after running
   - Show "Never run" if no history
   - Follow ServiceActionDialog pattern for confirmations

5. **Integration** (`frontend/app/status/page.tsx`):
   - Add MaintenanceCard below Celery Monitoring section

### Scope Discovery
This is a new feature with well-defined requirements. No additional scope discovery needed.

---

## Tasks

### Task 1: Create Database Migration for Maintenance Log

- [x] Create migration file `backend/migrations/001_maintenance_log.sql`
- [x] Define `maintenance_log` table with columns:
  - `id` (serial primary key)
  - `task_name` (text: 'cleanup_news', 'vacuum_database', 'validate_integrity')
  - `started_at` (timestamp)
  - `completed_at` (timestamp, nullable)
  - `status` (text: 'running', 'success', 'error')
  - `dry_run` (boolean)
  - `summary` (jsonb: results, counts, errors)
  - `error_message` (text, nullable)
- [x] Add indexes for common queries (task_name, started_at DESC)

### Task 2: Implement Backend CLI Scripts

- [x] Create `backend/app/scripts/__init__.py`
- [x] Implement `cleanup_old_news.py`:
  - Accept `--dry-run` flag
  - Query news older than 90 days (configurable via `--days` arg)
  - Log each deletion with structured logging
  - Return JSON summary: `{"deleted": N, "dry_run": bool, "oldest_date": "...", "newest_date": "..."}`
  - Handle errors gracefully with rollback
- [x] Implement `vacuum_database.py`:
  - Accept `--dry-run` flag (shows ANALYZE only)
  - Get table sizes before operation
  - Run VACUUM ANALYZE on specified tables or all tables
  - Show size before/after for each table
  - Return JSON summary: `{"tables": [{name, before_mb, after_mb, reclaimed_mb}], "total_reclaimed_mb": N}`
- [x] Implement `validate_data_integrity.py`:
  - Accept `--dry-run` flag (report only)
  - Check for orphaned records in key tables
  - Check for missing foreign key relationships
  - Validate data consistency rules
  - Return JSON summary: `{"orphaned_records": [{table, count, details}], "missing_fks": [...], "consistency_errors": [...]}`
- [x] Add proper CLI argument parsing with argparse
- [x] Use `get_logger()` from `logging_config` for all scripts

### Task 3: Implement Backend API Endpoints

- [x] Create `backend/app/api/maintenance.py`
- [x] Add router with prefix `/api/maintenance`
- [x] Implement POST `/cleanup-news`:
  - Accept `dry_run` boolean param (default: true)
  - Accept `days` integer param (default: 90)
  - Run `cleanup_old_news.py` as subprocess
  - Store result in `maintenance_log` table
  - Return execution ID and summary
- [x] Implement POST `/vacuum-database`:
  - Accept `dry_run` boolean param (default: false)
  - Accept `tables` list param (default: all)
  - Run `vacuum_database.py` as subprocess
  - Store result in `maintenance_log` table
  - Return execution ID and summary
- [x] Implement POST `/validate-integrity`:
  - Accept `dry_run` boolean param (default: true)
  - Run `validate_data_integrity.py` as subprocess
  - Store result in `maintenance_log` table
  - Return execution ID and summary
- [x] Implement GET `/last-run`:
  - Query `maintenance_log` for most recent run of each task
  - Return object: `{cleanup_news: {...}, vacuum_database: {...}, validate_integrity: {...}}`
  - Include: started_at, completed_at, status, dry_run, summary
- [x] Implement GET `/history`:
  - Accept `task_name` filter (optional)
  - Accept `limit` param (default: 50, max: 200)
  - Return chronological list of maintenance runs
- [x] Add Pydantic models for request/response validation
- [x] Add proper error handling and logging
- [x] Register router in main.py

### Task 4: Implement Frontend Maintenance Card

- [x] Create `frontend/components/status/MaintenanceCard.tsx`
- [x] Use Card component from shadcn/ui
- [x] Show three sections for each maintenance task:
  - Cleanup Old News
  - Vacuum Database
  - Validate Data Integrity
- [x] For each task show:
  - Last run timestamp (or "Never run")
  - Status badge (success/error/running)
  - Dry run indicator
  - Summary stats from last run
  - Action button to trigger task
- [x] Add global dry-run toggle switch at top of card
- [x] Implement confirmation dialogs using ServiceActionDialog pattern
- [x] Add loading states during execution
- [x] Display results after task completes (show summary JSON in formatted way)
- [x] Add refresh button to update status
- [x] Use icons from lucide-react (Trash2, Database, CheckCircle2)
- [x] Handle errors with proper user feedback

### Task 5: Create API Client Functions

- [x] Create `frontend/lib/api/maintenance.ts`
- [x] Implement API client functions:
  - `cleanupOldNews(dryRun: boolean, days?: number)`
  - `vacuumDatabase(dryRun: boolean, tables?: string[])`
  - `validateIntegrity(dryRun: boolean)`
  - `getMaintenanceLastRun()`
  - `getMaintenanceHistory(taskName?: string, limit?: number)`
- [x] Add TypeScript types for request/response models
- [x] Handle errors and return typed responses

### Task 6: Integrate into Status Page

- [x] Update `frontend/app/status/page.tsx`
- [x] Import MaintenanceCard component
- [x] Add new section "Database Maintenance" after Celery Monitoring
- [x] Add descriptive header text
- [x] Ensure proper spacing and layout

### Task 7: Create Handoff Documentation

- [x] Create `tasks/HANDOFF-maintenance-system-local-testing.md`
- [x] Document step-by-step testing instructions:
  - Apply database migration
  - Test CLI scripts manually
  - Restart backend service
  - Test API endpoints with curl
  - Test UI in browser
  - Verify maintenance_log table updates
- [x] Include verification checklist
- [x] Document expected behaviors and edge cases

---

## Verification

### Functional Requirements
- [ ] All three CLI scripts can be run standalone with --dry-run
- [ ] CLI scripts log structured output and return valid JSON
- [ ] Database migration creates maintenance_log table successfully
- [ ] API endpoints trigger scripts and store results
- [ ] API last-run endpoint returns correct data
- [ ] Frontend card displays "Never run" for new tasks
- [ ] Frontend card shows last run timestamps and summaries
- [ ] Dry-run toggle works correctly
- [ ] Confirmation dialogs prevent accidental execution
- [ ] Results display after task completion
- [ ] Error states show user-friendly messages

### Tests
- [ ] (Local) Run all CLI scripts with --dry-run flag
- [ ] (Local) Run integration tests for API endpoints
- [ ] (Local) Verify maintenance_log table updates correctly
- [ ] (Local) Test frontend UI interactions
- [ ] (Local) Test error handling (invalid params, script failures)

### Quality Checks
- [ ] All Python code passes ruff + mypy
- [ ] All TypeScript code passes ESLint
- [ ] File sizes within guidelines (<500 lines)
- [ ] Functions under 50 lines
- [ ] No exposed secrets or SQL injection vulnerabilities
- [ ] Proper type hints on all Python functions
- [ ] Proper TypeScript types on all frontend code

### Documentation
- [ ] Handoff doc complete with all testing steps
- [ ] Code comments explain non-obvious logic
- [ ] API endpoints documented with Pydantic models

---

## Notes

**Design Decisions:**
- Using subprocess to run CLI scripts from API (keeps scripts usable standalone)
- Storing results in database for history and auditing
- Dry-run default to true for destructive operations (cleanup)
- Dry-run default to false for safe operations (vacuum)
- JSON summary format allows flexible storage and display

**Dependencies:**
- Requires PostgreSQL for VACUUM operations
- Uses existing database connection pooling
- Follows existing patterns from status.py and service-control

**Future Enhancements:**
- Schedule automatic cleanup via Celery Beat
- Add email notifications for failed maintenance tasks
- Add more integrity checks based on discovered issues
- Export maintenance history to CSV
