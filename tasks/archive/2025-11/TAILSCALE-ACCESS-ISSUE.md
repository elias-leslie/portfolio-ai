# Tailscale Access Issue - Session Handoff

**Date**: 2025-11-17
**Status**: ⚠️ PARTIALLY FIXED - Frontend loads but returns 500 error
**Priority**: HIGH - User on vacation, needs remote access

---

## Problem

User cannot access full data on http://100.123.190.81:3000 (Tailscale IP) from vacation.

---

## Work Completed This Session

### ✅ Backend Fixes
1. **Log permissions** - Fixed `/var/log/portfolio-ai/` ownership (portfolio-ai:portfolio-ai)
2. **File permissions** - Fixed `llm_client.py` and other Python files (664)
3. **Directory permissions** - Fixed `gap_detection/` and all directories (775)
4. **Python cache** - Deleted all `__pycache__` with wrong permissions
5. **Backend running** - Service active, health check passing

### ✅ Frontend Fixes
1. **Dynamic API URL** - Auto-detects backend based on hostname
   - File: `frontend/lib/api/client.ts`
   - Tailscale (100.123.190.81) → http://100.123.190.81:8000
   - Local (192.168.8.233) → http://192.168.8.233:8000
   - Localhost → http://localhost:8000
2. **Turbopack fix** - Lazy evaluation to avoid build errors
3. **Frontend running** - Service active

### 📝 Commits
- `8472e7a` - Dynamic API URL detection for Tailscale
- `de4bd16` - Lazy-evaluate API URL to fix Turbopack

---

## Current Issue

**Frontend returns 500 Internal Server Error when accessed via Tailscale IP:**

```bash
$ curl -I http://100.123.190.81:3000
HTTP/1.1 500 Internal Server Error
```

**Working:**
- ✅ Backend: http://localhost:8000/health (200 OK)
- ✅ Frontend: systemd service active
- ❌ Frontend: 500 error on Tailscale IP

---

## Next Steps for Debugging

1. **Check frontend logs for 500 error**:
   ```bash
   journalctl -u portfolio-frontend -n 50 --no-pager
   # OR
   tail -50 /var/log/portfolio-ai/frontend-error.log
   ```

2. **Test direct localhost access**:
   ```bash
   curl -I http://localhost:3000
   # If this works but Tailscale doesn't, it's a network/binding issue
   ```

3. **Check if frontend is binding to correct interface**:
   ```bash
   netstat -tln | grep :3000
   # Should show: 0.0.0.0:3000 (not 127.0.0.1:3000)
   ```

4. **Check frontend systemd service**:
   ```bash
   cat /etc/systemd/system/portfolio-frontend.service
   # Look for --hostname parameter in ExecStart
   ```

5. **Possible causes**:
   - Frontend not bound to `0.0.0.0` (only listening on localhost)
   - CORS issue (though we fixed backend CORS)
   - SSR/build error in Next.js
   - Environment variable issue (NEXT_PUBLIC_API_URL)

---

## Quick Test Commands

```bash
# Check services
systemctl status portfolio-backend portfolio-frontend

# Test backend API
curl http://localhost:8000/health

# Test frontend locally
curl -I http://localhost:3000

# Test frontend via Tailscale
curl -I http://100.123.190.81:3000

# Check what's listening on port 3000
netstat -tln | grep :3000

# View frontend errors
tail -50 /var/log/portfolio-ai/frontend-error.log
```

---

## Files Modified This Session

1. `frontend/lib/api/client.ts` - Dynamic API URL detection
2. `scripts/fix-log-permissions.sh` - Log permission fix script
3. `backend/app/tasks/agent_tasks.py` - DualProviderClient integration
4. `backend/tests/integration/agents/test_agents_with_cli.py` - CLI agent tests

---

## Known Working Configuration

**Backend** (`/etc/systemd/system/portfolio-backend.service`):
```
ExecStart=/home/kasadis/portfolio-ai/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**CORS** (`backend/app/main.py`):
```python
allow_origins=[
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.8.233:3000",
    "http://100.123.190.81:3000",  # Tailscale
]
```

---

## Resources

- Previous Tailscale fix: Commit `1e727f6` (Nov 1, 2025)
- Remote access docs: `docs/archive/legacy-20251027-v1/REMOTE_ACCESS_SETUP.md`
- Similar issue: Task mentioned proxy issues resolved by using direct network IP calls
