# Task List: Status Dashboard MVP (PRD-0028)

**PRD**: `tasks/0028-prd-status-page-mvp.md`
**Status**: Ready for Implementation
**Completion**: 0%
**Effort**: MEDIUM (2-3 hours)
**Created**: 2025-11-03
**Updated**: 2025-11-03

---

## Summary

**✅ COMPLETE:** (None)
**🔄 IN PROGRESS:** (Not started)
**⚠️ NEXT:** Task 1.0 - Backend: Extend Health Endpoint with Service Status

---

## Relevant Files

### Create (10 files)
- `backend/app/api/status.py` (~200 lines) - New status endpoints (logs, SSE future)
- `backend/app/services/service_monitor.py` (~250 lines) - Service process detection logic
- `frontend/lib/api/status.ts` (~50 lines) - Status API client
- `frontend/lib/hooks/useSystemStatus.ts` (~40 lines) - React Query hook for polling
- `frontend/lib/hooks/useServiceLogs.ts` (~40 lines) - React Query hook for logs
- `frontend/components/status/SystemStatusCard.tsx` (~80 lines) - Overview card
- `frontend/components/status/ServiceCard.tsx` (~120 lines) - Individual service card
- `frontend/components/status/LogViewer.tsx` (~150 lines) - Log display component
- `frontend/app/status/page.tsx` (~100 lines) - Main status page
- `tests/api/test_status_endpoints.py` (~200 lines) - Status endpoint tests

### Update (4 files)
- `backend/app/api/health.py` - Add services field to HealthResponse model
- `backend/app/main.py` - Register status router
- `backend/requirements.txt` - Add psutil dependency
- `frontend/components/Navigation.tsx` - Add status page link

### Install (shadcn components)
- `scroll-area` - For log viewers
- `collapsible` - For expandable log sections

### Notes
- Tests: `cd ~/portfolio-ai/backend && pytest tests/api/test_status_endpoints.py -v`
- Lint: `~/portfolio-ai/scripts/lint.sh`
- UI Test: Browser automation skill for E2E verification

---

## Tasks

- [ ] **1.0 Backend: Extend Health Endpoint with Service Status** (45 min)
  - [ ] 1.1 Add psutil to requirements.txt (1 min)
    - [ ] 1.1.1 Add `psutil==5.9.6` to backend/requirements.txt
    - [ ] 1.1.2 Install: `cd ~/portfolio-ai/backend && source .venv/bin/activate && pip install psutil`

  - [ ] 1.2 Create service_monitor.py module (20 min)
    - [ ] 1.2.1 Write failing test for get_service_status() (3 min)
    - [ ] 1.2.2 Create backend/app/services/service_monitor.py with type stubs (2 min)
    - [ ] 1.2.3 Implement ServiceStatus Pydantic model (2 min)
    - [ ] 1.2.4 Implement get_process_by_pattern() using pgrep subprocess (4 min)
    - [ ] 1.2.5 Implement get_service_status() with psutil integration (5 min)
    - [ ] 1.2.6 Write tests for process detection edge cases (4 min)

  - [ ] 1.3 Implement service-specific health checks (15 min)
    - [ ] 1.3.1 Write failing test for check_backend_api() (2 min)
    - [ ] 1.3.2 Implement check_backend_api() with /health ping + thresholds (3 min)
    - [ ] 1.3.3 Write failing test for check_celery_worker() (2 min)
    - [ ] 1.3.4 Implement check_celery_worker() with celery inspect (3 min)
    - [ ] 1.3.5 Implement check_celery_beat() (2 min)
    - [ ] 1.3.6 Implement check_frontend() (1 min)
    - [ ] 1.3.7 Implement check_redis() with redis-cli ping (2 min)

  - [ ] 1.4 Update health.py to include services (9 min)
    - [ ] 1.4.1 Update HealthCheckResponse model to include services: dict[str, ServiceStatus] (2 min)
    - [ ] 1.4.2 Update HealthCheckService.perform_health_check() to call service checks (3 min)
    - [ ] 1.4.3 Write test verifying services field in health response (4 min)

- [ ] **2.0 Backend: Create Log Viewing Endpoint** (30 min)
  - [ ] 2.1 Create status.py router (20 min)
    - [ ] 2.1.1 Write failing test for GET /api/status/logs/backend (3 min)
    - [ ] 2.1.2 Create backend/app/api/status.py with router stub (2 min)
    - [ ] 2.1.3 Create LogResponse Pydantic model (2 min)
    - [ ] 2.1.4 Implement tail_log_file() function with deque (5 min)
    - [ ] 2.1.5 Add ANSI escape code stripping with regex (2 min)
    - [ ] 2.1.6 Implement GET /api/status/logs/{service} endpoint (3 min)
    - [ ] 2.1.7 Write tests for error cases (not found, permissions, invalid service) (3 min)

  - [ ] 2.2 Register status router in main.py (2 min)
    - [ ] 2.2.1 Import status router in backend/app/main.py (1 min)
    - [ ] 2.2.2 Add app.include_router(status.router) (1 min)

  - [ ] 2.3 Manual API testing (8 min)
    - [ ] 2.3.1 Restart backend: bash ~/portfolio-ai/scripts/restart.sh (2 min)
    - [ ] 2.3.2 Test health endpoint: curl http://localhost:8000/api/health | jq .services (2 min)
    - [ ] 2.3.3 Test log endpoint: curl http://localhost:8000/api/status/logs/backend | jq (2 min)
    - [ ] 2.3.4 Test invalid service: curl http://localhost:8000/api/status/logs/invalid (2 min)

- [ ] **3.0 Frontend: API Client & Hooks** (20 min)
  - [ ] 3.1 Create status API client (5 min)
    - [ ] 3.1.1 Create frontend/lib/api/status.ts with type definitions (2 min)
    - [ ] 3.1.2 Implement fetchSystemStatus() function (1 min)
    - [ ] 3.1.3 Implement fetchServiceLogs(service: string) function (2 min)

  - [ ] 3.2 Create useSystemStatus hook (8 min)
    - [ ] 3.2.1 Create frontend/lib/hooks/useSystemStatus.ts (2 min)
    - [ ] 3.2.2 Implement useQuery with 5s refetchInterval (3 min)
    - [ ] 3.2.3 Add staleTime: 0, cacheTime: 10000 config (1 min)
    - [ ] 3.2.4 Export hook with proper TypeScript types (2 min)

  - [ ] 3.3 Create useServiceLogs hook (7 min)
    - [ ] 3.3.1 Create frontend/lib/hooks/useServiceLogs.ts (2 min)
    - [ ] 3.3.2 Implement useQuery with enabled prop for conditional fetching (3 min)
    - [ ] 3.3.3 Add 5s refetchInterval when expanded (2 min)

- [ ] **4.0 Frontend: Status Page Components** (60 min)
  - [ ] 4.1 Install shadcn components (3 min)
    - [ ] 4.1.1 Run: cd ~/portfolio-ai/frontend && npx shadcn@latest add scroll-area (1 min)
    - [ ] 4.1.2 Run: cd ~/portfolio-ai/frontend && npx shadcn@latest add collapsible (1 min)
    - [ ] 4.1.3 Verify components installed in frontend/components/ui/ (1 min)

  - [ ] 4.2 Create LogViewer component (15 min)
    - [ ] 4.2.1 Create frontend/components/status/LogViewer.tsx with props interface (2 min)
    - [ ] 4.2.2 Implement ScrollArea container with max-height: 400px (2 min)
    - [ ] 4.2.3 Add log line rendering with syntax highlighting (ERROR=red, WARN=yellow, INFO=blue) (4 min)
    - [ ] 4.2.4 Add copy to clipboard button (3 min)
    - [ ] 4.2.5 Add auto-scroll to bottom checkbox (2 min)
    - [ ] 4.2.6 Implement error states (not found, permission denied, service down) (2 min)

  - [ ] 4.3 Create ServiceCard component (15 min)
    - [ ] 4.3.1 Create frontend/components/status/ServiceCard.tsx with props interface (2 min)
    - [ ] 4.3.2 Implement Card layout with service name and status badge (3 min)
    - [ ] 4.3.3 Add process details (PID, uptime formatting, memory MB) (4 min)
    - [ ] 4.3.4 Add status message display (2 min)
    - [ ] 4.3.5 Integrate Collapsible for log viewer expansion (2 min)
    - [ ] 4.3.6 Add useServiceLogs hook integration with enabled prop (2 min)

  - [ ] 4.4 Create SystemStatusCard component (12 min)
    - [ ] 4.4.1 Create frontend/components/status/SystemStatusCard.tsx with props (2 min)
    - [ ] 4.4.2 Calculate overall system health (X/6 services healthy) (3 min)
    - [ ] 4.4.3 Display database status from health response (2 min)
    - [ ] 4.4.4 Display data sources aggregated status (3 min)
    - [ ] 4.4.5 Add overall system status badge with color logic (2 min)

  - [ ] 4.5 Create status page (15 min)
    - [ ] 4.5.1 Create frontend/app/status/page.tsx as client component (2 min)
    - [ ] 4.5.2 Integrate useSystemStatus hook (2 min)
    - [ ] 4.5.3 Add page header with title and "Last updated Xs ago" (3 min)
    - [ ] 4.5.4 Add manual refresh button with RefreshCw icon (2 min)
    - [ ] 4.5.5 Implement responsive grid layout (1/2/3 columns) (3 min)
    - [ ] 4.5.6 Render SystemStatusCard and ServiceCards (2 min)
    - [ ] 4.5.7 Add loading and error states (1 min)

  - [ ] 4.6 Add navigation link (3 min)
    - [ ] 4.6.1 Read frontend/components/Navigation.tsx to understand structure (1 min)
    - [ ] 4.6.2 Add "Status" link to navigation menu (2 min)

- [ ] **5.0 Testing & Verification** (30 min)
  - [ ] 5.1 Backend unit tests (10 min)
    - [ ] 5.1.1 Run pytest tests/api/test_status_endpoints.py -v (2 min)
    - [ ] 5.1.2 Verify all service detection tests pass (2 min)
    - [ ] 5.1.3 Verify log endpoint tests pass (2 min)
    - [ ] 5.1.4 Verify error handling tests pass (2 min)
    - [ ] 5.1.5 Check test coverage >80%: pytest --cov=app.api.status (2 min)

  - [ ] 5.2 Manual UI testing with browser automation (15 min)
    - [ ] 5.2.1 Restart all services: bash ~/portfolio-ai/scripts/restart.sh (2 min)
    - [ ] 5.2.2 Verify services started: bash ~/portfolio-ai/scripts/status.sh (1 min)
    - [ ] 5.2.3 Take initial screenshot: node ~/.claude/skills/browser-automation/scripts/screenshot.js http://192.168.8.233:3000/status /tmp/status-initial.png (1 min)
    - [ ] 5.2.4 Monitor console errors: node ~/.claude/skills/browser-automation/scripts/console.js http://192.168.8.233:3000/status 10000 (2 min)
    - [ ] 5.2.5 Monitor network requests: node ~/.claude/skills/browser-automation/scripts/network.js http://192.168.8.233:3000/status 10000 (2 min)
    - [ ] 5.2.6 Wait for auto-refresh (5+ seconds) (1 min)
    - [ ] 5.2.7 Take post-refresh screenshot: node ~/.claude/skills/browser-automation/scripts/screenshot.js http://192.168.8.233:3000/status /tmp/status-refreshed.png (1 min)
    - [ ] 5.2.8 Verify all 6 services show correct status (green badges) (2 min)
    - [ ] 5.2.9 Test log expansion via interact.js (click expand button) (2 min)
    - [ ] 5.2.10 Verify backend health via API: curl http://localhost:8000/api/health | jq .services (1 min)

  - [ ] 5.3 Responsive design verification (5 min)
    - [ ] 5.3.1 Test mobile layout (resize to 375px width): node ~/.claude/skills/browser-automation/scripts/emulate.js resize http://192.168.8.233:3000/status 375 812 (2 min)
    - [ ] 5.3.2 Test tablet layout (768px width): node ~/.claude/skills/browser-automation/scripts/emulate.js resize http://192.168.8.233:3000/status 768 1024 (2 min)
    - [ ] 5.3.3 Test desktop layout (1920px width): node ~/.claude/skills/browser-automation/scripts/emulate.js resize http://192.168.8.233:3000/status 1920 1080 (1 min)

---

## Verification (MANDATORY before "COMPLETE ✅")

- [ ] **Functional**: All PRD requirements met
  - [ ] AC-1: Status page accessible at /status
  - [ ] AC-2: All 6 services show correct status (PID, status badge, uptime, memory, message)
  - [ ] AC-3: Status thresholds implemented per service (custom logic, not binary)
  - [ ] AC-4: Log viewers functional for 4 services (last 100 lines, expand/collapse, error handling)
  - [ ] AC-5: Auto-refresh working (5s polling, manual refresh button, timestamp)
  - [ ] AC-6: Color-coded health indicators (green/yellow/red with icons)
  - [ ] AC-7: Responsive layout (1/2/3 columns)
  - [ ] AC-8: Data source health displayed (from existing /health endpoint)

- [ ] **Tests**: 80%+ coverage, all passing
  - [ ] All pytest tests pass: cd ~/portfolio-ai/backend && pytest tests/api/test_status_endpoints.py -v
  - [ ] Service detection tests cover all 6 services
  - [ ] Log endpoint tests cover all error cases
  - [ ] Coverage: pytest --cov=app.api.status --cov=app.services.service_monitor

- [ ] **Quality**: mypy --strict, scripts/lint.sh pass
  - [ ] Run: ~/portfolio-ai/scripts/lint.sh (ruff + mypy)
  - [ ] No Any types in new code
  - [ ] All functions have type hints
  - [ ] No f-string SQL with user input

- [ ] **Clean**: Single source of truth, no duplication
  - [ ] Service detection logic centralized in service_monitor.py
  - [ ] No hardcoded service lists (use config if needed)
  - [ ] Reuses existing /health endpoint infrastructure

- [ ] **Docs**: Docstrings present
  - [ ] All public functions have docstrings
  - [ ] Pydantic models have field descriptions
  - [ ] API endpoints have summary/description

- [ ] **Security**: No secrets, parameterized queries
  - [ ] Log paths validated (no path traversal)
  - [ ] Service names validated (whitelist)
  - [ ] No shell injection in subprocess calls

- [ ] **Ops**: Service restart verified
  - [ ] Run: bash ~/portfolio-ai/scripts/restart.sh
  - [ ] Verify: bash ~/portfolio-ai/scripts/status.sh shows all services healthy
  - [ ] UI test: Navigate to http://192.168.8.233:3000/status
  - [ ] API test: curl http://localhost:8000/api/health | jq .services
  - [ ] Monitor scheduled tasks for 2+ cycles

---

## Notes

### Service Process Patterns (from status.sh)
- Backend API: `uvicorn.*main:app`
- Celery Worker: `celery.*worker`
- Celery Beat: `celery.*beat`
- Frontend: `next.*dev`
- Redis: `redis-server` (exact match)

### Log File Paths
- Backend: `/tmp/portfolio-backend.log`
- Celery Worker: `/tmp/portfolio-celery-worker.log`
- Celery Beat: `/tmp/portfolio-celery-beat.log`
- Frontend: `/tmp/portfolio-frontend.log` (if exists)

### Service Health Thresholds (from PRD)
- **Backend API**: Green (process + /health <2s), Yellow (slow >2s or stale >15min), Red (down)
- **Celery Worker**: Green (process + inspect OK), Yellow (no tasks 15min), Red (down)
- **Celery Beat**: Green (process), Yellow (no tasks sent 2min), Red (down)
- **Frontend**: Green (process), Yellow (port 3000 timeout), Red (down)
- **Redis**: Green (process + ping OK), Red (down or ping fail)
- **Database**: Reuse existing /health logic

### Dependencies Already Available
- ✅ fastapi, pydantic - Already installed
- ✅ @tanstack/react-query - Already installed (v5.x)
- ✅ lucide-react - Already installed
- ✅ shadcn/ui - Already configured
- ❌ psutil - **MUST INSTALL** (Task 1.1)
- ❌ scroll-area, collapsible - **MUST INSTALL** (Task 4.1)

### Browser Automation Scripts (0 context cost)
All scripts located at: `~/.claude/skills/browser-automation/scripts/`
- `screenshot.js <url> <output>` - Take screenshots
- `console.js <url> [duration]` - Capture console logs
- `network.js <url> [duration]` - Monitor network traffic
- `interact.js <action> <url> <args>` - Click, fill, scroll
- `emulate.js resize <url> <width> <height>` - Test responsive layouts

### API Testing Commands
```bash
# Health check with services
curl http://localhost:8000/api/health | jq .services

# Log endpoint
curl http://localhost:8000/api/status/logs/backend | jq

# Service status check
bash ~/portfolio-ai/scripts/status.sh
```

---

**Status**: Ready for /do_it execution
**Next**: Run `/do_it tasks-0028-status-dashboard-mvp.md` to start implementation
