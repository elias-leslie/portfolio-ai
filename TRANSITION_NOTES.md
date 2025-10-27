# Transition Notes: Market-Sim → Portfolio-AI

**Date**: 2025-10-27
**Action**: Transitioned development focus from market-sim to portfolio-ai

---

## What Was Done

### 1. Market-Sim Services Stopped ✅

All Docker services stopped to conserve resources:

```bash
$ docker compose ps
NAME      IMAGE     COMMAND   SERVICE   CREATED   STATUS    PORTS
# All services stopped
```

**Services stopped**:
- market-sim-ui-1 (port 3000)
- market-sim-api-1 (port 8000)
- market-sim-ingestor-1

**Why**: Portfolio-ai is now the active development project. Market-sim can be restarted when needed with `docker compose up`.

---

### 2. Current Tailscale Configuration

**Market-Sim Setup** (currently active):
```
https://davion-gem.tail661dd0.ts.net (tailnet only)
|-- / proxy http://localhost:3000
```

**Note**: This configuration is still pointing to market-sim's port 3000. Needs to be updated for portfolio-ai (Task 8.1).

---

### 3. Current Restic Backup Configuration

**File**: `~/.local/bin/restic-backup.sh`

**Current targets**:
```bash
BACKUP_TARGETS=(
  /home/kasadis/market-sim
)
```

**Needs update**: Add `/home/kasadis/portfolio-ai` (Task 8.4)

**Backup Schedule**:
- Runs via systemd timer: `restic-smart-backup.timer`
- Frequency: Daily
- Retention: 7 daily, 4 weekly, 6 monthly
- Destination: SFTP server at 192.168.8.128

---

### 4. Tasks Added to Portfolio-AI

**Task 8.0: Remote Access & Backup Configuration** (9 subtasks)

1. **8.1**: Configure Tailscale serve for frontend (port 3000)
2. **8.2**: Configure Tailscale serve for backend API (port 8000)
3. **8.3**: Test remote access from phone/other devices
4. **8.4**: Update restic backup script to include portfolio-ai
5. **8.5**: Verify backup includes data directory
6. **8.6**: Document Tailscale setup in OPERATIONS.md
7. **8.7**: Document backup configuration in OPERATIONS.md
8. **8.8**: Create troubleshooting guide
9. **8.9**: Test backup restoration

---

### 5. Documentation Created

**New file**: `docs/REMOTE_ACCESS_SETUP.md`

Comprehensive guide covering:
- Tailscale serve configuration (2 options)
- Restic backup integration
- Service management commands
- Testing procedures
- Troubleshooting guide
- Security considerations

---

## Port Allocation Plan

### Option 1: Same Ports (Recommended)
Since market-sim is stopped, reuse the ports:
- **Frontend**: Port 3000
- **Backend**: Port 8000
- **Tailscale**: Update existing config to point to portfolio-ai

**Advantages**:
- Simple configuration
- No port conflicts
- Existing Tailscale URL works

**Disadvantages**:
- Can't run both projects simultaneously

### Option 2: Different Ports
Use new ports for portfolio-ai:
- **Frontend**: Port 3001
- **Backend**: Port 8001
- **Tailscale**: Add new paths (/portfolio, /portfolio/api)

**Advantages**:
- Can run both projects simultaneously
- Clear separation

**Disadvantages**:
- More complex configuration
- Need to remember different ports

**Decision**: Use Option 1 initially. Can switch to Option 2 if needed later.

---

## Next Steps (Task 8.0)

### Immediate Actions Required

1. **Update Tailscale serve** (requires manual intervention):
   ```bash
   # Stop old configuration
   tailscale serve off

   # Start portfolio-ai services
   cd /home/kasadis/portfolio-ai/backend
   source .venv/bin/activate
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &

   cd /home/kasadis/portfolio-ai/frontend
   npm run dev &

   # Configure Tailscale
   tailscale serve --bg --https=443 3000
   ```

2. **Update restic backup** (requires manual intervention):
   ```bash
   # Edit the backup script
   nano ~/.local/bin/restic-backup.sh

   # Add portfolio-ai to BACKUP_TARGETS
   BACKUP_TARGETS=(
     /home/kasadis/market-sim
     /home/kasadis/portfolio-ai
   )

   # Test backup
   ~/.local/bin/restic-backup.sh
   ```

3. **Test from phone**:
   - Ensure Tailscale is running on phone
   - Navigate to: https://davion-gem.tail661dd0.ts.net
   - Should see portfolio-ai dashboard

---

## Rollback Procedure

If you need to switch back to market-sim:

```bash
# Stop portfolio-ai services
# (Ctrl+C in terminals running uvicorn and npm)

# Start market-sim services
cd /home/kasadis/market-sim
docker compose up -d ui api

# Tailscale will automatically proxy to port 3000
# (market-sim UI)
```

---

## Resource Conservation

### What's Stopped
- Market-sim Docker containers (3 containers)
- Frees up:
  - Memory: ~500MB-1GB (Docker overhead + containers)
  - CPU: Background Docker processes
  - Disk I/O: No active containers writing logs

### What's Still Running
- System services (Tailscale, restic timer, etc.)
- Portfolio-ai will run natively (not Docker)
- Lower resource footprint than Docker Compose

---

## Future Considerations

### Running Both Projects Simultaneously

If needed later, use different ports:

**Market-Sim**:
- UI: Port 3000
- API: Port 8000
- Tailscale: `/market` path

**Portfolio-AI**:
- Frontend: Port 3001
- Backend: Port 8001
- Tailscale: `/portfolio` path

Configuration:
```bash
tailscale serve --bg --https=443 --set-path=/market 3000
tailscale serve --bg --https=443 --set-path=/market/api 8000
tailscale serve --bg --https=443 --set-path=/portfolio 3001
tailscale serve --bg --https=443 --set-path=/portfolio/api 8001
```

### Systemd Service Units

Consider creating systemd units for portfolio-ai for persistent operation:
- Auto-start on boot
- Auto-restart on failure
- Easier management

Files to create:
- `~/.config/systemd/user/portfolio-ai-backend.service`
- `~/.config/systemd/user/portfolio-ai-frontend.service`

---

## Summary

**Status**: ✅ Market-sim stopped, tasks added, documentation created

**Action Required**: Manual configuration of Tailscale and restic backup (Task 8.0)

**Next Step**: Run `/do_it tasks/tasks-0009-prd-portfolio-ai-platform.md` to continue with Task 8.0

**Reference**: See `docs/REMOTE_ACCESS_SETUP.md` for detailed instructions

---

**Last Updated**: 2025-10-27
