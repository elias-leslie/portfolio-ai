# Task List: Status Dashboard - Phase 2 (Real-time SSE Updates)

**PRD**: `tasks/0029-prd-status-page-advanced.md` (Phase 2)
**Depends On**: tasks-0028-status-dashboard-mvp.md (MUST be complete)
**Status**: Ready for Implementation (after Phase 1)
**Completion**: 0%
**Effort**: LOW-MEDIUM (1-2 hours)
**Priority**: HIGH
**Created**: 2025-11-03
**Updated**: 2025-11-03

---

## Summary

**✅ COMPLETE:** (None)
**🔄 IN PROGRESS:** (Not started)
**⚠️ NEXT:** Task 1.0 - Backend: SSE Streaming Endpoint

---

## Relevant Files

### Create (3 files)
- `backend/app/api/status_stream.py` (~100 lines) - SSE streaming logic
- `frontend/lib/hooks/useStatusStream.ts` (~80 lines) - EventSource hook with fallback
- `tests/api/test_status_stream.py` (~100 lines) - SSE endpoint tests

### Update (2 files)
- `backend/app/api/status.py` - Add SSE endpoint (or import from status_stream.py)
- `frontend/app/status/page.tsx` - Switch from polling to SSE with fallback

### Notes
- SSE is built into FastAPI and browser EventSource API (no new dependencies)
- Automatic fallback to polling after 3 failed connection attempts
- Tests: `pytest tests/api/test_status_stream.py -v`

---

## Tasks

- [ ] **1.0 Backend: SSE Streaming Endpoint** (30 min)
  - [ ] 1.1 Create SSE streaming module (20 min)
    - [ ] 1.1.1 Create backend/app/api/status_stream.py with imports (1 min)
    - [ ] 1.1.2 Implement gather_comprehensive_status() function (reuses health logic) (5 min)
    - [ ] 1.1.3 Write failing test for status_event_stream() generator (3 min)
    - [ ] 1.1.4 Implement async status_event_stream() generator with 2s interval (5 min)
    - [ ] 1.1.5 Handle asyncio.CancelledError for clean client disconnect (2 min)
    - [ ] 1.1.6 Write test for SSE format (data: {...}\n\n) (4 min)

  - [ ] 1.2 Add SSE endpoint (10 min)
    - [ ] 1.2.1 Write failing test for GET /api/status/stream (3 min)
    - [ ] 1.2.2 Implement GET /api/status/stream endpoint with StreamingResponse (4 min)
    - [ ] 1.2.3 Add proper headers (text/event-stream, no-cache, keep-alive) (2 min)
    - [ ] 1.2.4 Test endpoint manually: curl -N http://localhost:8000/api/status/stream (1 min)

- [ ] **2.0 Frontend: EventSource Hook with Fallback** (40 min)
  - [ ] 2.1 Create useStatusStream hook (25 min)
    - [ ] 2.1.1 Create frontend/lib/hooks/useStatusStream.ts with type definitions (2 min)
    - [ ] 2.1.2 Add state: status, connectionState, failCount (2 min)
    - [ ] 2.1.3 Implement EventSource connection setup (4 min)
    - [ ] 2.1.4 Add onopen handler (sets connected, resets failCount) (2 min)
    - [ ] 2.1.5 Add onmessage handler (parses JSON, updates status) (3 min)
    - [ ] 2.1.6 Add onerror handler (increments failCount, closes connection) (3 min)
    - [ ] 2.1.7 Implement automatic fallback after 3 failures (4 min)
    - [ ] 2.1.8 Add cleanup in useEffect return (1 min)
    - [ ] 2.1.9 Add manual retry function (resets failCount, re-connects) (4 min)

  - [ ] 2.2 Create connection state indicator (10 min)
    - [ ] 2.2.1 Create ConnectionIndicator component in status/page.tsx (3 min)
    - [ ] 2.2.2 Add status badges: Connected (green), Connecting (yellow), Disconnected (gray), Fallback (blue) (4 min)
    - [ ] 2.2.3 Add "Retry Live Connection" button for manual retry (3 min)

  - [ ] 2.3 Update status page to use SSE (5 min)
    - [ ] 2.3.1 Replace useSystemStatus with useStatusStream in page.tsx (2 min)
    - [ ] 2.3.2 Keep useSystemStatus as fallback when connectionState === 'fallback' (3 min)

- [ ] **3.0 Testing & Verification** (20 min)
  - [ ] 3.1 Backend tests (8 min)
    - [ ] 3.1.1 Run pytest tests/api/test_status_stream.py -v (2 min)
    - [ ] 3.1.2 Verify SSE format tests pass (2 min)
    - [ ] 3.1.3 Verify cancellation handling tests pass (2 min)
    - [ ] 3.1.4 Check coverage: pytest --cov=app.api.status_stream (2 min)

  - [ ] 3.2 UI testing with browser automation (12 min)
    - [ ] 3.2.1 Restart services: bash ~/portfolio-ai/scripts/restart.sh (2 min)
    - [ ] 3.2.2 Navigate to /status and verify "Connected" indicator (1 min)
    - [ ] 3.2.3 Monitor network for EventSource connection: node ~/.claude/skills/browser-automation/scripts/network.js http://192.168.8.233:3000/status 10000 (2 min)
    - [ ] 3.2.4 Verify status updates without page refresh (watch for changes >5s) (2 min)
    - [ ] 3.2.5 Simulate SSE failure: stop backend, verify fallback to polling (2 min)
    - [ ] 3.2.6 Restart backend, click "Retry Live Connection", verify reconnects (2 min)
    - [ ] 3.2.7 Take screenshot of connection indicators: node ~/.claude/skills/browser-automation/scripts/screenshot.js http://192.168.8.233:3000/status /tmp/status-sse.png (1 min)

---

## Verification (MANDATORY before "COMPLETE ✅")

- [ ] **Functional**: All Phase 2 requirements met
  - [ ] AC-2.1: SSE endpoint streams status every 2 seconds
  - [ ] AC-2.2: EventSource connection auto-reconnects on disconnect
  - [ ] AC-2.3: Fallback to polling after 3 failed SSE attempts
  - [ ] AC-2.4: Connection indicator shows current state (connected/disconnected/fallback)
  - [ ] AC-2.5: Page updates without manual refresh
  - [ ] AC-2.6: <1% of users fall back to polling under normal conditions

- [ ] **Tests**: Coverage >80%, all passing
  - [ ] pytest tests/api/test_status_stream.py -v passes
  - [ ] SSE format validation tests pass
  - [ ] Connection error handling tests pass

- [ ] **Quality**: Linting passes
  - [ ] Run: ~/portfolio-ai/scripts/lint.sh
  - [ ] No type errors
  - [ ] All functions have type hints

- [ ] **Ops**: Service restart verified
  - [ ] bash ~/portfolio-ai/scripts/restart.sh
  - [ ] Verify SSE connection in browser DevTools Network tab
  - [ ] Test fallback by stopping/starting backend

---

## Notes

### SSE vs Polling Benefits
- Reduces server load (push vs pull)
- Lower latency (events sent immediately)
- More efficient (single connection vs repeated requests)
- Industry standard for real-time updates

### EventSource API (Built-in)
- Native browser support (no libraries needed)
- Automatic reconnection (built-in)
- Text/event-stream format (simple)
- Falls back gracefully to polling

### SSE Format Example
```
data: {"status": "healthy", "services": {...}, "timestamp": "2025-11-03T20:00:00Z"}

data: {"status": "healthy", "services": {...}, "timestamp": "2025-11-03T20:00:02Z"}

```

### Testing SSE Endpoint
```bash
# Test SSE stream (use -N to disable buffering)
curl -N http://localhost:8000/api/status/stream

# Should see data: {...} every 2 seconds
```

### Connection States
1. **connecting** - Initial EventSource setup
2. **connected** - EventSource open, receiving updates
3. **disconnected** - Connection lost, retrying
4. **fallback** - 3 failures, switched to polling (5s interval)

---

**Status**: Ready for /do_it execution (after Phase 1 complete)
**Next**: Run `/do_it tasks-0029-status-dashboard-phase2-sse.md` after Phase 1
