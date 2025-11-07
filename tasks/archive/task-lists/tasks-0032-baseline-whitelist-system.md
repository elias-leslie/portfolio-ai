# TASK-0032: Baseline/Whitelist System for Clean State Management

**Created:** 2025-11-04
**Priority:** HIGH (Foundational - run IMMEDIATELY after reboot)
**Effort:** MEDIUM (~2 hours)
**Status:** Pending (awaiting server reboot)

---

## Context

Background bash processes and service processes are being left behind, causing conflicts. Need a robust system to achieve clean state between runs.

**Approach:** After server reboot, capture baseline processes, create whitelist, and implement fresh-start.sh script with interactive whitelist editing.

---

## Implementation Tasks

### Phase 1: Baseline Capture (FIRST - Run After Reboot)

- [ ] **Task 1.1: Create baseline capture script**
  - File: `scripts/capture-baseline.sh`
  - Captures: `ps aux` output with PID, USER, %CPU, %MEM, COMMAND
  - Saves to: `scripts/baseline/processes.txt`
  - Include timestamp and system info (uname, date)
  - Make executable (chmod +x)

- [ ] **Task 1.2: Run baseline capture**
  - Execute: `bash scripts/capture-baseline.sh`
  - Verify: `scripts/baseline/processes.txt` exists and contains data
  - Review captured processes manually
  - Identify any unexpected processes

- [ ] **Task 1.3: Research scheduled processes**
  - Check: `crontab -l` and `/etc/cron.*`
  - Check: `systemctl list-timers` (user and system)
  - Check: Celery beat schedule in `backend/app/celery_app.py`
  - Document findings in capture script comments

### Phase 2: Whitelist Creation

- [ ] **Task 2.1: Create whitelist config file**
  - File: `scripts/baseline/whitelist.conf`
  - Format: One pattern per line, comments with `#`
  - Categories:
    - System essentials (systemd, dbus, etc.)
    - User session (bash, ssh, claude)
    - Development tools (vim, code, etc.)
    - Database (postgresql, redis if system service)
  - Add patterns for scheduled processes (from Task 1.3)

- [ ] **Task 2.2: Define portfolio-ai kill patterns**
  - Patterns to KILL (these will be restarted):
    - `uvicorn.*main:app`
    - `celery.*worker`
    - `celery.*beat`
    - `next.*dev`
    - `node.*next`
    - `python.*uvicorn`
  - Document in whitelist.conf as "DO NOT WHITELIST" section

### Phase 3: Fresh Start Script Implementation

- [ ] **Task 3.1: Create fresh-start.sh skeleton**
  - File: `scripts/fresh-start.sh`
  - Functions:
    - `read_whitelist()` - Load patterns from whitelist.conf
    - `find_non_whitelisted()` - Get processes to kill
    - `show_interactive_menu()` - Display list with add option
    - `add_to_whitelist()` - Append selected patterns to conf
    - `kill_processes()` - Graceful → force kill
    - `clean_temp_files()` - Remove /tmp/portfolio-*, /tmp/*.png
    - `verify_clean_state()` - Check no portfolio-ai processes remain
    - `start_services()` - Call scripts/start.sh
    - `verify_startup()` - Check services started successfully

- [ ] **Task 3.2: Implement interactive menu**
  - Show numbered list of processes to kill
  - Options: [k]ill all, [a]dd to whitelist, [q]uit
  - If [a] selected: prompt for numbers (comma-separated)
  - Extract process patterns from selected PIDs
  - Append to whitelist.conf with timestamp comment
  - Re-run find_non_whitelisted() with updated whitelist
  - Continue with kill

- [ ] **Task 3.3: Implement kill logic**
  - Exclude root-owned processes (safety)
  - Exclude PIDs < 1000 (system processes)
  - Try `kill <PID>` first (graceful, 5s timeout)
  - Fallback to `kill -9 <PID>` if still running
  - Log all kills to /tmp/fresh-start.log
  - Report success/failure for each process

- [ ] **Task 3.4: Implement cleanup and verification**
  - Clean temp files: `/tmp/portfolio-*.log`, `/tmp/*.png`, `/tmp/*.txt`
  - Verify no portfolio-ai processes remain (pgrep)
  - Call `bash scripts/start.sh`
  - Wait 10 seconds for startup
  - Verify services (curl health checks)
  - Report final status

### Phase 4: Bug Fix - start.sh Missing Celery Beat

- [ ] **Task 4.1: Add celery beat to start.sh**
  - Currently: start.sh does NOT start celery beat
  - Currently: restart.sh DOES start celery beat
  - Add celery beat startup to start.sh (after celery worker)
  - Use same pattern as restart.sh
  - Ensure consistency between start/restart

- [ ] **Task 4.2: Verify start.sh parity**
  - Test: `bash scripts/start.sh` starts all 5 services:
    1. redis-server
    2. uvicorn (backend)
    3. celery worker
    4. celery beat
    5. next dev (frontend)
  - Verify: `bash scripts/status.sh` shows all running
  - Compare: start.sh and restart.sh should have same services

### Phase 5: Documentation

- [ ] **Task 5.1: Create baseline/whitelist system docs**
  - File: `docs/reference/baseline-whitelist-system.md`
  - Sections:
    - Purpose and rationale
    - When to update baseline (after system changes)
    - How to run capture-baseline.sh
    - How to manually edit whitelist.conf
    - How to use fresh-start.sh
    - Troubleshooting guide
    - Examples

- [ ] **Task 5.2: Update OPERATIONS.md**
  - Add reference to baseline/whitelist system
  - Add fresh-start.sh to service management section
  - Link to detailed docs

### Phase 6: Testing and Validation

- [ ] **Task 6.1: Test fresh-start.sh on current system**
  - Run: `bash scripts/fresh-start.sh`
  - Test interactive mode (add process to whitelist)
  - Verify: All portfolio-ai processes killed
  - Verify: Services restart successfully
  - Verify: Whitelisted processes remain running
  - Check: /tmp/fresh-start.log for any errors

- [ ] **Task 6.2: Test complete workflow**
  - Stop services: `bash scripts/shutdown.sh`
  - Start background process (simulate lingering): `sleep 3600 &`
  - Run fresh-start.sh
  - Verify: sleep process killed (if not whitelisted)
  - Verify: Services started and healthy

- [ ] **Task 6.3: Code review and cleanup**
  - Review all scripts for errors
  - Check bash best practices (shellcheck if available)
  - Add error handling (set -e, set -u)
  - Add usage/help text to scripts
  - Ensure scripts are executable

### Phase 7: Commit and Update Tracker

- [ ] **Task 7.1: Commit all changes**
  - Stage: scripts/capture-baseline.sh
  - Stage: scripts/baseline/processes.txt
  - Stage: scripts/baseline/whitelist.conf
  - Stage: scripts/fresh-start.sh
  - Stage: scripts/start.sh (bug fix)
  - Stage: docs/reference/baseline-whitelist-system.md
  - Stage: docs/core/OPERATIONS.md (update)
  - Commit message: "feat: add baseline/whitelist system for clean state management (TASK-0032)"

- [ ] **Task 7.2: Update WORK_TRACKER.md**
  - Move TASK-0032 from Active → Recently Completed
  - Add completion date and results summary
  - Add file artifacts created

---

## Verification Checklist

**After all tasks complete:**
- [ ] `scripts/capture-baseline.sh` exists and runs successfully
- [ ] `scripts/baseline/processes.txt` contains baseline snapshot
- [ ] `scripts/baseline/whitelist.conf` contains comprehensive whitelist
- [ ] `scripts/fresh-start.sh` exists and is executable
- [ ] Fresh-start.sh interactive mode works (can add to whitelist)
- [ ] Fresh-start.sh successfully kills non-whitelisted processes
- [ ] Fresh-start.sh successfully starts services
- [ ] `scripts/start.sh` now starts celery beat (bug fixed)
- [ ] Documentation complete and accurate
- [ ] All scripts tested and working
- [ ] Changes committed to git

---

## Success Criteria

1. **Baseline captured** with all natural post-reboot processes
2. **Whitelist accurate** - keeps essential, kills portfolio-ai
3. **fresh-start.sh works** - achieves clean state reliably
4. **Interactive mode works** - can add processes to whitelist during execution
5. **start.sh parity** - celery beat bug fixed
6. **Documentation complete** - future updates possible
7. **All tests pass** - manual validation successful

---

## Relevant Files

**Created:**
- `scripts/capture-baseline.sh` - Baseline capture script
- `scripts/baseline/processes.txt` - Process baseline (single source of truth)
- `scripts/baseline/whitelist.conf` - Process whitelist config
- `scripts/fresh-start.sh` - Clean state script with interactive mode
- `docs/reference/baseline-whitelist-system.md` - System documentation

**Modified:**
- `scripts/start.sh` - Add celery beat startup (bug fix)
- `docs/core/OPERATIONS.md` - Add baseline/whitelist system reference

**Reference:**
- `scripts/shutdown.sh` - Graceful kill patterns (reuse logic)
- `scripts/restart.sh` - Celery beat startup (template for start.sh fix)
- `scripts/status.sh` - Service verification (reuse for fresh-start.sh)
- `backend/app/celery_app.py` - Celery beat schedule (scheduled processes)

---

## Notes

- **MUST run Task 1.2 (baseline capture) immediately after server reboot** - this is the whole point!
- **Server must be rebooted BEFORE starting this task** - otherwise baseline is polluted
- Interactive mode allows real-time whitelist correction on first run
- Future baseline updates: Just re-run `capture-baseline.sh` and review diffs
- Whitelist patterns use grep -E extended regex (same as pgrep -f)
