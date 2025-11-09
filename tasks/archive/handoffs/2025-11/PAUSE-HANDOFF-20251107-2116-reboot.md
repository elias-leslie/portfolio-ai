# Work Session Handoff - Server Reboot Verification

**Date**: 2025-11-07 21:16 | **Type**: System Reboot Verification
**Reason**: Testing service account setup survives reboot

## Current Status

✅ **Done This Session:** Service account setup for portfolio-ai services
- Created `portfolio-ai` system user (no login, no home directory)
- Updated all 4 systemd service files (backend, celery, beat, frontend)
- Fixed permissions: backend/frontend directories, numba cache, log files
- Added backup permissions to sudoers (Veeam + restic)
- Services running successfully as `portfolio-ai` user before reboot

❌ **Blocked:** `!requiretty` in sudoers works for user manually but not for Claude Bash tool
🔄 **Next:** Reboot server and verify services start automatically

## Code State

**Git:** Clean working directory
**Branch:** main
**Last Commit:**
- e902892 feat: add sudo permissions setup script
- All service account changes applied via scripts (not committed yet)

## Environment Before Reboot

**Services:** All active (running) as `portfolio-ai` user
- Backend: ✅ active (PID 125622)
- Celery Worker: ✅ active (2 workers)
- Celery Beat: ✅ active
- Frontend: ✅ active

**Key Directories:**
- `/var/log/portfolio-ai/` - Log files (owned by portfolio-ai)
- `/var/cache/portfolio-ai/numba/` - Numba cache (for pandas_ta)
- `/run/portfolio-ai/` - Runtime directory (will be recreated by systemd)

**Service Files:**
- All 4 services configured with:
  - User=portfolio-ai, Group=portfolio-ai
  - EnvironmentFile=-$DIR/.env
  - RuntimeDirectory=portfolio-ai
  - NUMBA_CACHE_DIR=/var/cache/portfolio-ai/numba
  - Restart=always, RestartSec=10

## Issues Discovered & Fixed

**Issue 1: app/ subdirectories had 700 permissions**
- **Symptom:** Services crashed with "cannot import name 'agent_tasks'"
- **Root Cause:** `app/tasks/`, `app/models/`, `app/utils/` were 700 (kasadis-only)
- **Fix:** `chmod -R g+rX ~/portfolio-ai/backend/app`
- **Script Updated:** Added to setup-service-account.sh (line 72)

**Issue 2: Numba caching error**
- **Symptom:** RuntimeError: cannot cache function 'fibonacci'
- **Root Cause:** portfolio-ai user has no home directory, numba can't write cache
- **Fix:** Created `/var/cache/portfolio-ai/numba` + added NUMBA_CACHE_DIR env var
- **Scripts:** fix-numba-cache.sh + updated setup-service-account.sh

**Issue 3: Log file write permission**
- **Symptom:** PermissionError: portfolio-ai.log
- **Root Cause:** Existing log file had 644 permissions (group read-only)
- **Fix:** `chmod g+w ~/portfolio-ai/backend/logs/portfolio-ai.log`
- **Script Updated:** Added to setup-service-account.sh (line 95-98)

**Issue 4: Script exited early on inactive services**
- **Symptom:** setup-service-account.sh exited at step 9 without completing
- **Root Cause:** `systemctl is-active` returns exit code 3 for inactive services, `set -e` caused exit
- **Fix:** Added `|| echo "inactive"` to capture status gracefully
- **Script Updated:** Lines 348-351

## Post-Reboot Verification Steps

### 1. SSH back in and verify services auto-started

```bash
# Check all services are active
sudo systemctl status portfolio-backend --no-pager | head -10
sudo systemctl status portfolio-celery --no-pager | head -10
sudo systemctl status portfolio-beat --no-pager | head -10
sudo systemctl status portfolio-frontend --no-pager | head -10

# Verify process ownership (should all be portfolio-ai)
ps aux | grep -E "(uvicorn|celery|next)" | grep -v grep

# Check service start times (should be after boot)
systemctl show portfolio-backend -p ActiveEnterTimestamp
systemctl show portfolio-celery -p ActiveEnterTimestamp
```

### 2. Verify RuntimeDirectory was created

```bash
# Should exist and be owned by portfolio-ai
ls -ld /run/portfolio-ai
```

### 3. Check logs for errors

```bash
tail -50 /var/log/portfolio-ai/backend-error.log
tail -50 /var/log/portfolio-ai/celery-worker-error.log
tail -50 /var/log/portfolio-ai/celery-beat-error.log
tail -50 /var/log/portfolio-ai/frontend-error.log
```

### 4. Test application functionality

```bash
# Backend health check
curl http://localhost:8000/api/health | jq

# Check frontend is accessible
curl -I http://localhost:3000

# Verify watchlist API
curl http://localhost:8000/api/watchlist | jq '.items | length'
```

### 5. Test sudo commands (still blocked for Claude)

```bash
# This should work for you manually
sudo systemctl restart portfolio-backend

# But Claude's Bash tool still can't use sudo (TTY issue)
# This is expected - not critical for operation
```

### 6. Test backup triggers

```bash
# Veeam backup (should work now)
sudo systemctl start veeam-smart-backup.service
sudo tail -20 /var/log/veeam-smart-backup.log

# Restic backup (will fail - SSH host not configured)
systemctl --user start restic-smart-backup.service
# Expected to fail: "Could not resolve hostname restic-backup"
```

## Files Modified This Session

**Created:**
- `scripts/setup-service-account.sh` - Complete service account setup (updated with all fixes)
- `scripts/fix-numba-cache.sh` - Numba caching fix
- `scripts/setup-backup-sudo.sh` - Backup permissions (superseded by service account script)

**Updated:**
- `/etc/systemd/system/portfolio-backend.service` - User, NUMBA_CACHE_DIR, EnvironmentFile
- `/etc/systemd/system/portfolio-celery.service` - User, NUMBA_CACHE_DIR, EnvironmentFile
- `/etc/systemd/system/portfolio-beat.service` - User, NUMBA_CACHE_DIR, EnvironmentFile
- `/etc/systemd/system/portfolio-frontend.service` - User, EnvironmentFile
- `/etc/sudoers.d/portfolio-ai-services` - !requiretty + backup permissions

**Permissions Fixed:**
- `~/portfolio-ai/backend/app/` - Recursive g+rX (755)
- `~/portfolio-ai/backend/logs/portfolio-ai.log` - g+w (664)
- `/var/cache/portfolio-ai/numba/` - Created, owned by portfolio-ai
- `/var/log/portfolio-ai/` - Created, owned by portfolio-ai

## Key Decisions

**Architecture:**
- Service account pattern (portfolio-ai user) for security and persistence
- Systemd-only management (no manual process spawning)
- Logs to /var/log/portfolio-ai/ instead of systemd journal only
- Numba cache in /var/cache/ (persistent across restarts)

**Security:**
- portfolio-ai user: system user, no login, no home directory
- Group membership: portfolio-ai is in kasadis group (read code)
- Sudoers: !requiretty + NOPASSWD for specific systemctl commands only
- Backup permissions: Veeam (sudo) + restic (user service)

## Known Issues

**Sudo from Bash tool:**
- Sudoers configured correctly with `!requiretty`
- Works manually for user
- Bash tool still gets "terminal required" error
- **Impact:** Claude can't autonomously restart services (user must do it)
- **Workaround:** User runs `sudo systemctl restart portfolio-backend` when needed

**Restic backup:**
- SSH host "restic-backup" not configured in ~/.ssh/config
- Restic backup will fail until DNS/SSH is configured
- **Impact:** Only Veeam backup works
- **Workaround:** User configures SSH alias or updates restic env file

## Success Criteria Post-Reboot

- ✅ All 4 services active and running as portfolio-ai
- ✅ RuntimeDirectory /run/portfolio-ai/ exists
- ✅ No errors in logs
- ✅ Backend API responds to /api/health
- ✅ Frontend loads on http://localhost:3000
- ✅ Services persist after user logout
- ✅ Veeam backup can be triggered

## To Resume After Reboot

1. **Reboot the server:**
   ```bash
   sudo reboot
   ```

2. **After reboot, run verification steps 1-6 above**

3. **Report results to Claude:**
   ```
   Resume conversation and share:
   - Output of systemctl status commands
   - ps aux output showing process ownership
   - Any errors from logs
   - Results of application functionality tests
   ```

4. **Next steps based on results:**
   - If all services running → SUCCESS, commit changes to git
   - If services failed → Debug with Claude, fix issues
   - If partial success → Identify and fix failing services

## Quick Stats

**Session Duration:** ~2 hours
**Scripts Created:** 3 (setup-service-account.sh, fix-numba-cache.sh, setup-backup-sudo.sh)
**Service Files Updated:** 4 (all portfolio services)
**Bugs Fixed:** 4 (permissions, numba cache, log write, script exit)
**Services Managed:** 6 (backend, celery, beat, frontend, veeam, restic)
**Context Used:** 37% (75K / 200K tokens)
