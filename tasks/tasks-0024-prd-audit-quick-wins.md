# Task List: Audit Quick Wins - High Impact, Low Effort Fixes

**PRD**: `tasks/0024-prd-audit-quick-wins.md`
**Status**: Ready for Implementation
**Completion**: 0%
**Effort**: LOW (3 hours total)
**Updated**: 2025-11-03

---

## Summary

**✅ COMPLETE:** (None)
**🔄 IN PROGRESS:** (Not started)
**⚠️ NEXT:** Task 1.0 - Database Performance Indexes

---

## Relevant Files

### Create (1 file)
- `backend/migrations/0004_audit_quick_wins_indexes.sql` (~30 lines) - Index creation statements

### Update (3 files)
- `docs/core/OPERATIONS.md` - Remove 8 DuckDB references, update backup/restore to PostgreSQL
- `docs/core/SETUP.md` - Remove 4 DuckDB references, update setup instructions
- `.claude/commands/do_it.md` - Clarify service management policy (allow scripts, forbid manual nohup)

### Notes
- Tests: Verify indexes with `\di` in psql, test query performance with EXPLAIN ANALYZE
- Documentation: `grep -r "duckdb\|\.db\|\.wal" docs/core/` should return nothing
- No code changes required (pure infrastructure + documentation)

---

## Tasks

- [ ] 1.0 Database Performance Indexes (15 min, LOW)
  - [ ] 1.1 Create migration SQL file (5 min)
    - Create `backend/migrations/0004_audit_quick_wins_indexes.sql`
    - Add CREATE INDEX IF NOT EXISTS for 4 missing indexes:
      - `idx_portfolio_positions_account_id` ON portfolio_positions(account_id)
      - `idx_agent_ideas_agent_run_id` ON agent_ideas(agent_run_id)
      - `idx_agent_tool_calls_agent_run_id` ON agent_tool_calls(agent_run_id)
      - `idx_validation_results_idea_id` ON validation_results(idea_id)
    - Add DROP INDEX IF EXISTS statements for rollback
  - [ ] 1.2 Run migration on portfolio_ai database (3 min)
    - Execute: `psql -U portfolio_ai_user -d portfolio_ai -f backend/migrations/0004_audit_quick_wins_indexes.sql`
    - Verify no errors in output
  - [ ] 1.3 Run migration on portfolio_ai_test database (3 min)
    - Execute: `psql -U portfolio_ai_user -d portfolio_ai_test -f backend/migrations/0004_audit_quick_wins_indexes.sql`
    - Verify no errors in output
  - [ ] 1.4 Verify indexes created successfully (2 min)
    - Run: `psql -U portfolio_ai_user -d portfolio_ai -c "\di" | grep -E "idx_portfolio_positions_account_id|idx_agent_ideas_agent_run_id|idx_agent_tool_calls_agent_run_id|idx_validation_results_idea_id"`
    - Confirm all 4 indexes appear
  - [ ] 1.5 Test portfolio query performance (2 min)
    - Run: `psql -U portfolio_ai_user -d portfolio_ai -c "EXPLAIN ANALYZE SELECT * FROM portfolio_positions WHERE account_id = 'default' LIMIT 10;"`
    - Verify query plan shows "Index Scan using idx_portfolio_positions_account_id"
    - Response time should be <100ms

- [ ] 2.0 Update OPERATIONS.md for PostgreSQL (45 min, LOW)
  - [ ] 2.1 Remove DuckDB file path references (10 min)
    - Line 354: Replace `du -h ~/portfolio-ai/backend/data/portfolio-ai.db` with PostgreSQL table size query
    - Line 364: Remove "Database: `~/portfolio-ai/backend/data/portfolio-ai.db`" reference
    - Line 438: Update backup command from cp .db file to pg_dump
    - Line 455: Update restore command from cp to psql
  - [ ] 2.2 Remove WAL file references (5 min)
    - Lines 512-513: Remove `rm -f ~/portfolio-ai/backend/data/portfolio-ai.db.wal` and `.db-shm` commands
    - Replace with note: "PostgreSQL manages WAL files automatically"
  - [ ] 2.3 Update file permissions section (5 min)
    - Line 752: Remove `chmod 600 ~/portfolio-ai/backend/data/portfolio-ai.db`
    - Replace with PostgreSQL data directory permissions (managed by PostgreSQL)
  - [ ] 2.4 Update backup encryption section (10 min)
    - Line 760: Replace DuckDB file encryption with PostgreSQL dump encryption
    - Add: `pg_dump -U portfolio_ai_user -d portfolio_ai | gzip | gpg --encrypt --recipient your@email.com > backup.sql.gz.gpg`
  - [ ] 2.5 Update monitoring section (5 min)
    - Line 910: Replace `du -h ~/portfolio-ai/backend/data/portfolio-ai.db` with PostgreSQL database size query:
    - `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT pg_size_pretty(pg_database_size('portfolio_ai'));"`
  - [ ] 2.6 Add PostgreSQL connection string reference (5 min)
    - Add section: "Database Connection"
    - Format: `postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai`
    - Note: Connection details in .env file
  - [ ] 2.7 Verify all DuckDB references removed (5 min)
    - Run: `grep -i "duckdb\|portfolio-ai\.db\|\.wal" docs/core/OPERATIONS.md`
    - Should return: no matches
    - Run: `grep -c "postgresql\|psql\|pg_dump" docs/core/OPERATIONS.md`
    - Should return: multiple matches (>5)

- [ ] 3.0 Update SETUP.md for PostgreSQL (30 min, LOW)
  - [ ] 3.1 Remove DuckDB environment variable (5 min)
    - Lines 127-128: Remove `DB_PATH=../data/portfolio-ai.db` from .env instructions
    - Replace with PostgreSQL connection string instructions
  - [ ] 3.2 Update database initialization section (10 min)
    - Line 150: Remove "This creates `~/portfolio-ai/backend/data/portfolio-ai.db`"
    - Replace with: "This initializes the PostgreSQL database 'portfolio_ai'"
    - Update command to reference PostgreSQL setup script if exists
  - [ ] 3.3 Remove WAL cleanup instructions (5 min)
    - Line 305: Remove `rm -f ~/portfolio-ai/backend/data/portfolio-ai.db.wal`
    - Add note: "PostgreSQL handles cleanup automatically"
  - [ ] 3.4 Add PostgreSQL prerequisites section (5 min)
    - Add before database setup: PostgreSQL 16 installation requirements
    - Reference: Ubuntu/Debian: `apt install postgresql-16`
    - Reference: Arch: `pacman -S postgresql`
  - [ ] 3.5 Cross-reference with OPERATIONS.md (3 min)
    - Verify backup/restore commands match OPERATIONS.md
    - Verify connection string format matches
  - [ ] 3.6 Verify all DuckDB references removed (2 min)
    - Run: `grep -i "duckdb\|portfolio-ai\.db\|\.wal" docs/core/SETUP.md`
    - Should return: no matches

- [ ] 4.0 Clarify Service Management Policy (30 min, LOW)
  - [ ] 4.1 Read current service management section (5 min)
    - Read .claude/commands/do_it.md lines 1-150
    - Identify conflicting or unclear language about background processes
    - Note specific sections that need clarification
  - [ ] 4.2 Update policy statement (10 min)
    - Replace blanket prohibition with nuanced policy:
      - ✅ ALLOWED: Project scripts (start.sh, restart.sh, shutdown.sh)
      - ✅ ALLOWED: Using scripts that internally use nohup/&
      - ❌ FORBIDDEN: Manual nohup commands (e.g., `nohup uvicorn &`)
      - ❌ FORBIDDEN: Manual & background processes
    - Rationale: Scripts provide consistent, testable operations
  - [ ] 4.3 Add clear examples (10 min)
    - ✅ Good: `bash ~/portfolio-ai/scripts/start.sh`
    - ✅ Good: `bash ~/portfolio-ai/scripts/restart.sh`
    - ❌ Bad: `nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 &`
    - ❌ Bad: `celery -A app.celery_app worker &`
  - [ ] 4.4 Align with OPERATIONS.md (3 min)
    - Verify OPERATIONS.md uses project scripts
    - Ensure no conflict between documents
  - [ ] 4.5 Verify policy clarity (2 min)
    - Re-read updated section
    - Confirm no ambiguity remains
    - Confirm aligns with actual practice

- [ ] 5.0 Review CODE_AUDIT.md Findings (10 min, LOW)
  - [ ] 5.1 Read CODE_AUDIT.md thoroughly (5 min)
    - Open and read entire file
    - Note 7 files exceeding 500-line limit
    - Understand findings #1-7 in detail
  - [ ] 5.2 Document large files for future work (3 min)
    - Note: watchlist/service.py (1306 lines)
    - Note: tasks/agent_tasks.py (786 lines)
    - Note: api/watchlist.py (745 lines)
    - Note: watchlist/narrative.py (628 lines)
    - Note: api/health.py (572 lines)
    - Note: sources/rest_api_source.py (544 lines)
    - Note: analytics/paper_trading.py (504 lines)
  - [ ] 5.3 Acknowledge refactoring PRD needed (2 min)
    - Confirm PRD #0025 exists for code refactoring
    - No immediate action required in this PRD
    - Mark this task as complete (awareness only)

---

## Verification (MANDATORY before "COMPLETE ✅")

- [ ] **Functional**: All PRD requirements met
  - [ ] 4 database indexes created and verified
  - [ ] OPERATIONS.md has zero DuckDB references
  - [ ] SETUP.md has zero DuckDB references
  - [ ] Service management policy clearly stated
  - [ ] CODE_AUDIT.md reviewed and understood
- [ ] **Tests**: Infrastructure validation
  - [ ] `\di` shows all 4 new indexes
  - [ ] EXPLAIN ANALYZE shows index usage for portfolio queries
  - [ ] grep finds no DuckDB/WAL references in core docs
  - [ ] grep finds multiple PostgreSQL references
- [ ] **Quality**: Documentation consistency
  - [ ] OPERATIONS.md backup/restore uses pg_dump/psql
  - [ ] SETUP.md references PostgreSQL only
  - [ ] do_it.md policy aligns with OPERATIONS.md
  - [ ] Cross-references between docs are accurate
- [ ] **Clean**: No regressions
  - [ ] No code changes made (infrastructure + docs only)
  - [ ] Existing tests still pass
  - [ ] Services run normally after index creation
- [ ] **Docs**: Updated accurately
  - [ ] Database size queries use PostgreSQL commands
  - [ ] Connection strings use PostgreSQL format
  - [ ] No conflicting service management instructions
- [ ] **Security**: No issues
  - [ ] Index creation uses IF NOT EXISTS (safe to re-run)
  - [ ] No credentials in documentation
- [ ] **Ops**: Services healthy
  - [ ] Portfolio queries <100ms with new indexes
  - [ ] All services restart successfully
  - [ ] No WAL file references remain

---

## Notes

### Database Index Creation Details
The 4 missing indexes are:
1. **portfolio_positions.account_id** - CRITICAL for portfolio queries (eliminates full table scan)
2. **agent_ideas.agent_run_id** - HIGH for agent analysis performance
3. **agent_tool_calls.agent_run_id** - HIGH for agent analysis performance
4. **validation_results.idea_id** - MEDIUM for idea tracing performance

### DuckDB References Found
- **OPERATIONS.md**: 8 references (lines 354, 364, 438, 455, 512, 513, 752, 760, 910)
- **SETUP.md**: 4 references (lines 127, 128, 150, 305)
- **Other files**: Backup archives only (ignore)

### Service Management Clarification
Current state: Blanket prohibition on background processes conflicts with scripts/start.sh usage
Desired state: Allow project scripts, forbid manual nohup/& commands
Rationale: Scripts provide consistent, testable operations (OPERATIONS.md already uses them)

### Success Criteria
✅ All 4 indexes created and performant
✅ Zero DuckDB references in OPERATIONS.md and SETUP.md
✅ Service management policy clear and unambiguous
✅ CODE_AUDIT.md reviewed (refactoring deferred to PRD #0025)
✅ Query performance <100ms for portfolio queries
✅ Documentation cross-referenced and consistent

### Time Breakdown
- Database indexes: 15 min
- OPERATIONS.md update: 45 min
- SETUP.md update: 30 min
- Service management clarification: 30 min
- Code audit review: 10 min
- **Total**: ~2.5 hours (well under 3-hour estimate)

---

## Execution Notes for /do_it

- **No code changes** - Pure infrastructure + documentation
- **No test updates needed** - Infrastructure changes only
- **No service restart required** - Indexes created online
- **Run in order** - Database first, then docs (docs reference new indexes)
- **Autonomous friendly** - All tasks are straightforward, no decisions needed
- **Verification built-in** - Each task has clear success criteria
