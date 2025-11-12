# Task List: Unified Journald Logging System

**Source**: Ad-hoc session work (captured from /pause_it)
**Complexity**: Complex
**Effort**: MEDIUM (completed in 1 session)
**Environment**: Local Dev
**Created**: 2025-11-10
**Status**: 90% Complete (testing + docs pending)

---

## Summary

**Goal**: Implement unified chronological log stream across all 6 services (Backend, Celery Worker/Beat, Frontend, Redis, PostgreSQL) using systemd journald for true event sequence tracking and debugging.

**Approach**:
- Reconfigure PostgreSQL and Redis to log to journald (stderr) instead of files
- Create unified API endpoint that merges logs from all services with journald timestamps
- Build frontend UI to display chronological interleaved log stream with filtering
- Filter out systemd noise, merge multi-line SQL statements

**Scope Discovery**: Not needed (infrastructure change, all 6 services known)

---

## Tasks

### 1.0 Configure Services for Journald Logging ✅

- [x] 1.1 Create configuration script for Redis journald logging
  - Script: `scripts/configure-journald-logging.sh`
  - Changes: `logfile ""`, `daemonize no` in `/etc/redis/redis.conf`
- [x] 1.2 Configure PostgreSQL to log to stderr/journald
  - Script: `scripts/configure-postgresql-stderr.sh`
  - Changes: `logging_collector = off`, `log_destination = 'stderr'`
- [x] 1.3 Update PostgreSQL audit logging config for journald
  - Script: `scripts/update-postgresql-logging-journald.sh`
  - Updated: `/etc/postgresql/16/main/conf.d/postgresql-logging.conf`
  - Preserves: `log_statement = 'mod'` (INSERT/UPDATE/DELETE audit trail)
- [x] 1.4 Fix PostgreSQL systemd service configuration
  - Script: `scripts/fix-postgresql-type.sh`
  - Changes: Direct postgres execution with `Type=exec`
  - Override: `/etc/systemd/system/postgresql@16-main.service.d/direct-exec.conf`
- [x] 1.5 Verify all 6 services logging to journald
  - Tested: journalctl output from all services with unified timestamps

### 2.0 Backend API Implementation ✅

- [x] 2.1 Create unified logs API endpoint
  - File: `backend/app/api/status.py`
  - Endpoint: `GET /api/status/unified-logs`
  - Parameters: `lines`, `service`, `level`, `since`
- [x] 2.2 Implement journald JSON parsing
  - Reads from: `journalctl -o json`
  - Extracts: `__REALTIME_TIMESTAMP`, `_SYSTEMD_UNIT`, `MESSAGE`
- [x] 2.3 Add service-specific log level detection
  - Redis: Detect `#` (warn), `*` (info), `.` (debug)
  - PostgreSQL: Detect LOG, ERROR, FATAL, NOTICE
  - Backend/Celery: Detect INFO, ERROR, WARN, DEBUG
- [x] 2.4 Filter systemd noise and merge multi-line logs
  - Skip: "Starting/Started/Stopping/Stopped" messages
  - Merge: Consecutive entries with same timestamp+service (SQL statements)
- [x] 2.5 Add Pydantic models with mutation support
  - Model: `UnifiedLogEntry` with `frozen = False` for merging

### 3.0 Frontend UI Implementation ✅

- [x] 3.1 Refactor LogsCard to use unified API
  - File: `frontend/components/status/LogsCard.tsx`
  - Replaced: Individual service hooks with single SWR call
- [x] 3.2 Install dependencies
  - Added: `swr` package for data fetching
- [x] 3.3 Implement chronological text stream display
  - Format: `[HH:MM:SS] [Service] [LEVEL] message`
  - Preserves: Multi-line messages with `<pre>` tag
- [x] 3.4 Add service and level filtering UI
  - Dropdowns: Service filter, Level filter
  - Badge: Log count display
- [x] 3.5 Add sort toggle (Newest/Oldest first)
  - Button: ArrowUpDown icon with sort direction
- [x] 3.6 Add copy-to-clipboard functionality
  - Button: Copies formatted logs to clipboard

### 4.0 Testing & Validation ⏳

- [ ] 4.1 Test chronological ordering across all services
  - Verify: Event sequence (PostgreSQL → Backend → Celery → Frontend)
  - Trigger: Cross-service operations to generate interleaved logs
- [ ] 4.2 Verify audit logging captures destructive actions
  - Test: INSERT/UPDATE/DELETE in PostgreSQL appear in unified stream
  - Verify: User and database context preserved
- [ ] 4.3 Test filtering functionality
  - Service filter: Each of 6 services individually
  - Level filter: ERROR, WARN, INFO, DEBUG
  - Combined filters
- [ ] 4.4 Verify multi-line SQL statements display correctly
  - Check: INSERT statements with multiple columns not fragmented
  - Check: Complex queries formatted with whitespace preserved

### 5.0 Documentation & Commands ⏳

- [ ] 5.1 Document unified logging API
  - Location: `docs/core/API_REFERENCE.md`
  - Endpoint: `/api/status/unified-logs` with parameters
  - Examples: Curl commands for dev/troubleshooting
- [ ] 5.2 Document journald configuration scripts
  - Location: `docs/core/OPERATIONS.md`
  - Scripts: Purpose, rollback instructions
- [ ] 5.3 Add troubleshooting guide
  - Location: `docs/core/OPERATIONS.md` or new file
  - Topics: View logs via API/UI, filter for errors, debug event sequences
- [ ] 5.4 Update DEVELOPMENT.md with logging best practices
  - Add: How to view unified logs for debugging
  - Add: Log level conventions per service

---

## Verification

- [x] Functional: 6 services logging to journald with unified timestamps
- [x] API: `/api/status/unified-logs` returns chronological merged stream
- [x] UI: Status page displays interleaved logs with filtering
- [x] Quality: Backend linting passes (no new errors introduced)
- [ ] Tests: Manual testing complete (automated tests not required for infra)
- [ ] Docs: Updated with new logging system (pending)

---

## Scripts Created

1. `scripts/configure-journald-logging.sh` - Initial Redis/PostgreSQL journald config
2. `scripts/configure-postgresql-stderr.sh` - PostgreSQL stderr logging
3. `scripts/update-postgresql-logging-journald.sh` - Update audit logging for journald
4. `scripts/setup-postgresql-direct-systemd.sh` - Direct postgres systemd execution
5. `scripts/fix-postgresql-type.sh` - Fix systemd Type=exec configuration
6. `scripts/enable-postgresql-audit-logging.sh` - Enable audit logging (reference)

---

## Files Modified

**Backend:**
- `backend/app/api/status.py` - Added `/api/status/unified-logs` endpoint

**Frontend:**
- `frontend/components/status/LogsCard.tsx` - Refactored to unified API
- `frontend/package.json` - Added `swr` dependency

**Configuration:**
- `/etc/redis/redis.conf` - Journald logging
- `/etc/postgresql/16/main/postgresql.conf` - Stderr logging
- `/etc/postgresql/16/main/conf.d/postgresql-logging.conf` - Audit + journald
- `/etc/systemd/system/postgresql@16-main.service.d/direct-exec.conf` - Direct execution

---

## Notes

**Audit Logging Preserved:**
- PostgreSQL `log_statement = 'mod'` still active
- All INSERT/UPDATE/DELETE/TRUNCATE logged
- Slow queries (>1s) logged
- Connection/disconnection logged
- Now all visible in unified chronological stream

**Future Enhancements (Optional):**
- Dynamic log level control per service (API + UI)
- Log export functionality (download as file)
- Real-time log streaming (WebSocket)
- Log search/highlighting within UI
