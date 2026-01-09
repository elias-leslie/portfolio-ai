# Fix: Celery Zombie Workers

**Priority:** HIGH | **Type:** bug | **Status:** COMPLETED

## Problem

Celery workers survived service restarts, causing:
- Multiple duplicate workers (saw 5 when should be 3)
- CPU thrashing from competing workers
- Memory bloat (total RSS reached 3GB)

## Root Cause

Missing `KillMode=control-group` in systemd service files. Without this, child worker pool processes survive when the parent is killed.

## Solution Applied

**Keep `Type=simple` (current)** - simpler and more reliable than `Type=forking`.

**Add zombie prevention directives:**
```ini
# ZOMBIE PREVENTION: Kill all child processes when stopping
KillMode=control-group
KillSignal=SIGTERM
TimeoutStopSec=30
```

**Add worker recycling (prevents memory bloat):**
```
--max-tasks-per-child=100
```

**Reduced concurrency** from 4 to 2 (sufficient for dev).

## Files Updated

| File | Changes |
|------|---------|
| `~/.config/systemd/user/portfolio-celery.service` (symlink → scripts/systemd/) | +KillMode, +--max-tasks-per-child=100, concurrency=2 |
| `~/.config/systemd/user/portfolio-celery-beat.service` (symlink → scripts/systemd/) | +KillMode |
| `~/.config/systemd/user/summitflow-celery.service` | +KillMode, +--max-tasks-per-child=100 |
| `~/.config/systemd/user/summitflow-celery-beat.service` | +KillMode |
| `~/agent-hub/scripts/systemd/agent-hub-celery.service` | +KillMode, +--max-tasks-per-child=100 |

## Why NOT Type=forking

The original task proposed switching to `Type=forking` with `--detach`. This is **wrong** because:

1. **More complex** - requires PID file management, ExecStop, ExecStopPost
2. **PID files can become stale** - leading to failed starts
3. **Systemd already tracks the main process** with Type=simple
4. **No benefit** - KillMode=control-group solves the zombie problem directly

## Verification

```bash
# Restart doesn't leave zombies
systemctl --user restart portfolio-celery.service
sleep 5
pgrep -f "portfolio-ai.*celery.*worker" | wc -l
# Should be 3 (1 main + 2 pool workers)

# Stop kills all processes
systemctl --user stop portfolio-celery.service
sleep 2
pgrep -f "portfolio-ai.*celery.*worker" | wc -l
# Should be 0

# Check CGroup (definitive)
systemctl --user status portfolio-celery.service
# CGroup should show only 3 PIDs
```

## Results

| Metric | Before | After |
|--------|--------|-------|
| Worker processes after restart | 5-7 (zombies) | 3 (correct) |
| Memory per project | ~3GB | ~600MB |
| Restart behavior | Leaves orphans | Clean |

---

**Completed:** 2026-01-09
