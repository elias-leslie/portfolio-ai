# PRD-0028: Real-Time Status Dashboard - Phase 1 (MVP)

**Status**: Draft
**Created**: 2025-11-03
**Effort**: MEDIUM (2-3 hours)
**Priority**: HIGH
**Phase**: 1 of 6 (MVP)

---

## Introduction

**Problem**: Currently, monitoring portfolio-ai platform health requires SSH access to check service status, read log files, and inspect processes. There's no centralized dashboard to quickly assess system health, identify failing services, or view recent errors.

**Goal**: Build a comprehensive real-time status dashboard accessible via browser at `/status` that shows all critical system health metrics, service status, and live log viewers with minimal setup time (2-3 hours for MVP).

**Impact**:
- Eliminate SSH requirement for routine health checks
- Reduce time to identify issues from minutes to seconds
- Provide visibility into service health, data freshness, and errors
- Foundation for advanced monitoring (Phases 2-6)

---

## User Stories

**US-1**: As the platform operator, I want to see all service statuses (API, DB, Celery, Redis, Frontend) at a glance so I can quickly identify which services are down.

**US-2**: As the platform operator, I want to view recent log entries from each service so I can diagnose errors without SSH'ing into the server.

**US-3**: As the platform operator, I want to see data source health (yfinance, twelvedata, etc.) so I know if my data is fresh or stale.

**US-4**: As the platform operator, I want color-coded health indicators (green/yellow/red) so I can instantly identify problems.

**US-5**: As the platform operator, I want the page to auto-refresh so I don't need to manually reload to see current status.

---

## Goals

### Primary Goals
1. **Service Health Visibility**: Show real-time status of all 6 core services
2. **Log Access**: View last 100 lines from service logs without SSH
3. **Data Health**: Leverage existing `/health` endpoint metrics for data sources
4. **Auto-Update**: Refresh status every 2-5 seconds via React Query polling
5. **Quick Delivery**: Complete MVP in 2-3 hours of implementation

### Success Metrics
- Status page loads in <2 seconds
- All 6 services show correct status (green/yellow/red)
- Log viewers display last 100 lines correctly
- Page auto-refreshes every 2-5 seconds
- Manual refresh button provides immediate update
- Zero new backend dependencies required

---

## Functional Requirements

### Backend Requirements

**FR-1: Extend `/api/health` Endpoint**
- Add service process details to existing health check response
- Include for each service:
  - `pid`: Process ID (integer or null if not running)
  - `status`: "running" | "stopped" | "degraded"
  - `uptime_seconds`: Time since process start (integer or null)
  - `memory_mb`: Memory usage in megabytes (integer or null)
  - `status_message`: Human-readable reason for status (string)
- Services to monitor: Backend API, Celery Worker, Celery Beat, Frontend, Redis
- Reuse existing service detection logic from `scripts/status.sh`

**FR-2: Create `/api/status/logs/{service}` Endpoint**
- New GET endpoint accepting service name as path parameter
- Valid service names: "backend", "celery-worker", "celery-beat", "frontend"
- Returns JSON response with:
  ```json
  {
    "service": "backend",
    "log_file": "/tmp/portfolio-backend.log",
    "lines": ["line 1", "line 2", ...],  // Last 100 lines
    "total_lines": 1523,
    "status": "ok" | "error" | "not_found" | "permission_denied",
    "message": "Human-readable status/error message"
  }
  ```
- Error handling:
  - **File not found**: Return `status: "not_found"`, `message: "Log file /tmp/portfolio-backend.log not found. Service may not have started yet."`
  - **Permission denied**: Return `status: "permission_denied"`, `message: "Cannot read log file. Check file permissions."`
  - **Service not running**: Return `status: "error"`, `message: "Backend service is not running. Start service to generate logs."`
- Read last 100 lines using `tail -n 100` or Python equivalent
- Strip ANSI color codes from log output for clean display

**FR-3: Service-Specific Status Thresholds**
- Define custom status logic per service:
  - **Backend API**:
    - Green: Process running, responds to /health within 2s
    - Yellow: Process running but /health slow (>2s) or last_success >15min
    - Red: Process not running or /health unreachable
  - **Celery Worker**:
    - Green: Process running, inspect stats succeeds
    - Yellow: Process running but no tasks completed in last 15min
    - Red: Process not running
  - **Celery Beat**:
    - Green: Process running
    - Yellow: Process running but no scheduled task sent in last 2min
    - Red: Process not running
  - **Frontend**:
    - Green: Process running
    - Yellow: Process running but port 3000 not responding
    - Red: Process not running
  - **Redis**:
    - Green: Process running, redis-cli ping succeeds
    - Red: Process not running or ping fails
  - **Database**:
    - Reuse existing `/health` endpoint logic (already excellent)

**FR-4: Response Model Updates**
- Update Pydantic models in `backend/app/api/health.py`:
  ```python
  class ServiceStatus(BaseModel):
      pid: int | None
      status: Literal["running", "stopped", "degraded"]
      uptime_seconds: int | None
      memory_mb: int | None
      status_message: str

  class HealthResponse(BaseModel):
      # Existing fields...
      services: dict[str, ServiceStatus]  # NEW
  ```

### Frontend Requirements

**FR-5: Create `/status` Page**
- New Next.js page at `frontend/app/status/page.tsx`
- Layout: Grid of status cards (responsive: 1 column mobile, 2-3 desktop)
- Page title: "System Status Dashboard"
- Include timestamp of last update ("Last updated: 2 seconds ago")

**FR-6: SystemStatusCard Component**
- Location: `frontend/components/status/SystemStatusCard.tsx`
- Shows overall system health summary:
  - Total services: X/6 healthy
  - Database status
  - Data sources status (aggregated from /health)
  - Overall system status badge (green if all ok, yellow if any degraded, red if any down)
- Props: `status: HealthResponse`

**FR-7: ServiceCard Component**
- Location: `frontend/components/status/ServiceCard.tsx`
- Shows individual service status:
  - Service name (e.g., "Backend API")
  - Status badge (green/yellow/red with icon)
  - Status message (reason for yellow/red)
  - Process details: PID, uptime, memory
  - Expand/collapse log viewer on click
- Props: `service: ServiceStatus, serviceName: string, logs?: LogResponse`
- Visual:
  ```
  [Frontend Service]           [🟢 Running]
  PID: 12345 | Uptime: 2h 34m | Memory: 245 MB
  Status: Process healthy, responding normally

  [▼ View Logs] (click to expand)
  ```

**FR-8: LogViewer Component**
- Location: `frontend/components/status/LogViewer.tsx`
- Displays last 100 lines from log file
- Features:
  - Syntax highlighting for log levels (ERROR=red, WARN=yellow, INFO=blue)
  - Monospace font (font-mono)
  - Scrollable container (max-height: 400px)
  - Copy to clipboard button
  - Auto-scroll to bottom option (checkbox)
- Error states:
  - Log not found: Show message with icon and troubleshooting tip
  - Permission denied: Show message with fix instructions
  - Service down: Show message linking to service status
- Props: `logs: LogResponse, service: string`

**FR-9: Auto-Refresh with React Query**
- Use `useQuery` with `refetchInterval: 5000` (5 seconds)
- Hook: `useSystemStatus()` in `frontend/lib/hooks/useSystemStatus.ts`
- Query key: `["system-status"]`
- Stale time: 0 (always consider stale)
- Cache time: 10 seconds

**FR-10: Manual Refresh Button**
- Button in page header: "Refresh Now"
- Calls `refetch()` from React Query
- Shows loading spinner while refreshing
- Toast notification on refresh complete

**FR-11: Connection Status Indicator**
- Show connection state in page header
- Green dot: "Connected • Last updated 3s ago"
- Gray dot: "Connecting..."
- Red dot: "Disconnected • Retrying..."
- Uses React Query `isLoading`, `isError` states

### UI/UX Requirements

**FR-12: Color-Coded Health Indicators**
- **Green** (Healthy):
  - Badge: `bg-green-100 text-green-800 border-green-200`
  - Icon: `CheckCircle` from lucide-react
- **Yellow** (Degraded):
  - Badge: `bg-yellow-100 text-yellow-800 border-yellow-200`
  - Icon: `AlertTriangle` from lucide-react
- **Red** (Down):
  - Badge: `bg-red-100 text-red-800 border-red-200`
  - Icon: `XCircle` from lucide-react

**FR-13: Responsive Design**
- Mobile (<768px): 1 column layout
- Tablet (768-1024px): 2 column layout
- Desktop (>1024px): 3 column layout
- All cards same height in row (use `grid-auto-rows-fr`)

**FR-14: shadcn/ui Components**
- Use existing shadcn/ui primitives:
  - `Card, CardHeader, CardTitle, CardContent` for containers
  - `Badge` for status indicators
  - `Button` for refresh and copy actions
  - `ScrollArea` for log viewers
  - `Collapsible` for expandable log sections
- Follow existing color scheme and typography

---

## Non-Goals (Phase 1 MVP)

**Explicitly Out of Scope**:
- ❌ WebSocket / Server-Sent Events (Phase 2)
- ❌ Celery task inspection (active/pending tasks) (Phase 3)
- ❌ System resource monitoring (CPU/disk/memory) (Phase 4)
- ❌ Service control buttons (restart, stop) (Phase 5)
- ❌ Historical metrics and uptime trends (Phase 6)
- ❌ Authentication / authorization
- ❌ Alerting or notifications
- ❌ Mobile app
- ❌ Export status to JSON/CSV

---

## Technical Considerations

### Backend Implementation

**Leverage Existing Infrastructure**:
- Extend `backend/app/api/health.py` (already 514 lines with excellent metrics)
- Reuse service detection patterns from `scripts/status.sh`
- No new dependencies required (use stdlib for process/file operations)

**Service Process Detection**:
```python
import psutil
import subprocess

def get_service_status(process_pattern: str) -> ServiceStatus:
    """Detect service by process pattern (e.g., 'uvicorn.*main:app')."""
    try:
        # Use pgrep to find PIDs
        result = subprocess.run(
            ["pgrep", "-f", process_pattern],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            pid = int(result.stdout.split()[0])
            proc = psutil.Process(pid)
            return ServiceStatus(
                pid=pid,
                status="running",
                uptime_seconds=int(time.time() - proc.create_time()),
                memory_mb=proc.memory_info().rss // (1024 * 1024),
                status_message="Service is running normally"
            )
        else:
            return ServiceStatus(
                pid=None,
                status="stopped",
                uptime_seconds=None,
                memory_mb=None,
                status_message="Process not found"
            )
    except Exception as e:
        return ServiceStatus(
            pid=None,
            status="stopped",
            uptime_seconds=None,
            memory_mb=None,
            status_message=f"Error detecting process: {str(e)}"
        )
```

**Log File Reading**:
```python
def tail_log_file(file_path: str, lines: int = 100) -> LogResponse:
    """Read last N lines from log file."""
    try:
        if not os.path.exists(file_path):
            return LogResponse(
                service=service_name,
                log_file=file_path,
                lines=[],
                total_lines=0,
                status="not_found",
                message=f"Log file {file_path} not found. Service may not have started yet."
            )

        with open(file_path, 'r') as f:
            # Use deque for efficient tail
            from collections import deque
            last_lines = deque(f, maxlen=lines)

        # Strip ANSI codes
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_lines = [ansi_escape.sub('', line.rstrip()) for line in last_lines]

        return LogResponse(
            service=service_name,
            log_file=file_path,
            lines=clean_lines,
            total_lines=len(clean_lines),
            status="ok",
            message="Successfully read log file"
        )
    except PermissionError:
        return LogResponse(
            service=service_name,
            log_file=file_path,
            lines=[],
            total_lines=0,
            status="permission_denied",
            message="Cannot read log file. Check file permissions."
        )
    except Exception as e:
        return LogResponse(
            service=service_name,
            log_file=file_path,
            lines=[],
            total_lines=0,
            status="error",
            message=f"Error reading log file: {str(e)}"
        )
```

### Frontend Implementation

**API Client** (`frontend/lib/api/status.ts`):
```typescript
export async function fetchSystemStatus(): Promise<HealthResponse> {
  return get<HealthResponse>("/api/health");
}

export async function fetchServiceLogs(service: string): Promise<LogResponse> {
  return get<LogResponse>(`/api/status/logs/${service}`);
}
```

**Hook** (`frontend/lib/hooks/useSystemStatus.ts`):
```typescript
export function useSystemStatus() {
  return useQuery<HealthResponse, Error>({
    queryKey: ["system-status"],
    queryFn: fetchSystemStatus,
    refetchInterval: 5000,  // 5 seconds
    staleTime: 0,
    cacheTime: 10000,
  });
}

export function useServiceLogs(service: string, enabled: boolean = true) {
  return useQuery<LogResponse, Error>({
    queryKey: ["service-logs", service],
    queryFn: () => fetchServiceLogs(service),
    enabled,  // Only fetch when log viewer is expanded
    refetchInterval: 5000,
  });
}
```

**Component Structure** (`frontend/app/status/page.tsx`):
```typescript
"use client";

import { useSystemStatus } from "@/lib/hooks/useSystemStatus";
import { SystemStatusCard } from "@/components/status/SystemStatusCard";
import { ServiceCard } from "@/components/status/ServiceCard";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";

export default function StatusPage() {
  const { data: status, isLoading, refetch, dataUpdatedAt } = useSystemStatus();

  if (isLoading) return <div>Loading status...</div>;
  if (!status) return <div>Error loading status</div>;

  const timeSinceUpdate = Math.floor((Date.now() - dataUpdatedAt) / 1000);

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">System Status Dashboard</h1>
          <p className="text-muted-foreground">
            Last updated {timeSinceUpdate}s ago
          </p>
        </div>
        <Button onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh Now
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <SystemStatusCard status={status} />

        {Object.entries(status.services).map(([name, service]) => (
          <ServiceCard
            key={name}
            serviceName={name}
            service={service}
          />
        ))}
      </div>
    </div>
  );
}
```

### Dependencies

**Backend**:
- ✅ `psutil` - Already installed (check requirements.txt)
- ✅ `fastapi` - Already installed
- ✅ No new dependencies needed

**Frontend**:
- ✅ `@tanstack/react-query` - Already installed (v5.90.5)
- ✅ `lucide-react` - Already installed (icons)
- ✅ shadcn/ui components - Already installed
- ✅ No new dependencies needed

---

## Design Considerations

### Status Page Mockup (Text-based)

```
┌─────────────────────────────────────────────────────────────┐
│  System Status Dashboard              [🔄 Refresh Now]      │
│  Last updated 3 seconds ago                                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────┬────────────────────┬──────────────┐ │
│  │ System Overview    │ Backend API        │ Celery Worker│ │
│  │                    │                    │              │ │
│  │ 🟢 6/6 Services OK │ 🟢 Running         │ 🟢 Running   │ │
│  │ 🟢 Database OK     │ PID: 1234          │ PID: 5678    │ │
│  │ 🟢 5/5 Sources OK  │ Uptime: 2h 15m     │ Uptime: 2h   │ │
│  │                    │ Memory: 245 MB     │ Memory: 89MB │ │
│  │                    │ [▼ View Logs]      │ [▼ View Logs]│ │
│  └────────────────────┴────────────────────┴──────────────┘ │
│                                                               │
│  ┌────────────────────┬────────────────────┬──────────────┐ │
│  │ Celery Beat        │ Frontend           │ Redis Server │ │
│  │                    │                    │              │ │
│  │ 🟢 Running         │ 🟢 Running         │ 🟢 Running   │ │
│  │ PID: 9012          │ PID: 3456          │ PID: 7890    │ │
│  │ Uptime: 2h 15m     │ Uptime: 1h 30m     │ Uptime: 5d   │ │
│  │ Memory: 45 MB      │ Memory: 312 MB     │ Memory: 28MB │ │
│  │ [▼ View Logs]      │ [▼ View Logs]      │ Status: OK   │ │
│  └────────────────────┴────────────────────┴──────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Expanded Log Viewer Example

```
┌──────────────────────────────────────────────────────────┐
│ Backend API                              🟢 Running       │
│ PID: 1234 | Uptime: 2h 15m | Memory: 245 MB             │
│                                                           │
│ [▲ Hide Logs]                         [📋 Copy] [↓ Auto] │
│ ┌────────────────────────────────────────────────────┐  │
│ │ 2025-11-03 19:25:12 [INFO] Server started          │  │
│ │ 2025-11-03 19:25:13 [INFO] Connected to database   │  │
│ │ 2025-11-03 19:26:45 [WARN] Slow query detected     │  │
│ │ 2025-11-03 19:27:01 [ERROR] Failed to fetch data   │  │
│ │ 2025-11-03 19:27:02 [INFO] Retrying request...     │  │
│ │ ... (95 more lines)                                 │  │
│ └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## Acceptance Criteria

### Must-Have (MVP)

**AC-1**: Status page accessible at `http://localhost:3000/status`

**AC-2**: All 6 services show correct status:
- Backend API, Celery Worker, Celery Beat, Frontend, Redis, Database
- Each shows: PID, status badge, uptime, memory, status message

**AC-3**: Status thresholds implemented per service:
- Custom logic for each service (not binary up/down)
- Status message explains why yellow/red

**AC-4**: Log viewers functional for 4 services:
- Backend, Celery Worker, Celery Beat, Frontend
- Show last 100 lines from `/tmp/portfolio-*.log`
- Click to expand/collapse
- Handle missing files, permissions errors, service down states

**AC-5**: Auto-refresh working:
- React Query polls every 5 seconds
- Manual refresh button works
- Shows "Last updated Xs ago" timestamp

**AC-6**: Color-coded health indicators:
- Green/yellow/red badges with correct icons
- Consistent with design system

**AC-7**: Responsive layout:
- 1 column mobile, 2-3 columns desktop
- All cards same height

**AC-8**: Data source health displayed:
- Reuse existing `/health` endpoint source_performance data
- Show status for each source (yfinance, twelvedata, etc.)

### Nice-to-Have (Future Phases)

- Real-time updates via SSE (Phase 2)
- Celery active tasks view (Phase 3)
- System resources (CPU/disk) (Phase 4)
- Restart service buttons (Phase 5)
- Historical uptime charts (Phase 6)

---

## Edge Cases & Error Handling

**EC-1: Service Process Not Running**
- Status: Red, "stopped"
- Message: "Process not found. Start service with scripts/start.sh"
- Log viewer: Show "Service is not running. Logs may be outdated."

**EC-2: Log File Not Found**
- Status: "not_found"
- Message: "Log file /tmp/portfolio-backend.log not found. Service may not have started yet."
- UI: Show icon with message and troubleshooting steps

**EC-3: Log File Permission Denied**
- Status: "permission_denied"
- Message: "Cannot read log file. Check file permissions: chmod 644 /tmp/portfolio-backend.log"
- UI: Show warning with fix command

**EC-4: API Endpoint Unreachable**
- Use React Query error handling
- Show error state: "Failed to fetch system status. Check if backend is running."
- Retry automatically (React Query default behavior)

**EC-5: Stale Data Sources**
- Reuse existing `/health` logic:
  - Last success >15min: Yellow "degraded"
  - Last success >1hr: Red "down"
- Show freshness: "Last success: 23 minutes ago"

**EC-6: Database Connection Pool Full**
- Reuse existing `/health` database check
- If connection fails: Red "down"
- Message from health endpoint

**EC-7: Celery Worker Alive But Idle**
- Check last task completion time (from celery result backend)
- If no tasks in last 15min: Yellow "degraded"
- Message: "Worker alive but no tasks completed recently"

**EC-8: Frontend Process Running But Port Not Responding**
- Check if port 3000 responds (timeout 2s)
- If timeout: Yellow "degraded"
- Message: "Process running but port 3000 not responding"

---

## Open Questions

**Q1**: Should we add a link to status page in main navigation?
- **Answer**: Yes, add to settings dropdown or header

**Q2**: Should logs auto-scroll to bottom when new lines arrive?
- **Answer**: Yes, add checkbox "Auto-scroll to bottom" (default: ON)

**Q3**: Should we cache service status to reduce process checks?
- **Answer**: No for Phase 1 (5s interval is fine), consider in Phase 2 with SSE

**Q4**: Should Redis be monitored differently (it's critical infrastructure)?
- **Answer**: Yes, use redis-cli PING command, not just process check

**Q5**: Should we add a "Copy all logs" button?
- **Answer**: Yes, in log viewer header

---

## Implementation Plan

### Phase 1.1: Backend Extension (1 hour)

**Tasks**:
1. Extend `backend/app/api/health.py`:
   - Add `ServiceStatus` Pydantic model
   - Add `get_service_status()` helper function
   - Add `services` field to `HealthResponse`
   - Implement service detection for all 6 services
2. Create `backend/app/api/status.py`:
   - New router with `/api/status/logs/{service}` endpoint
   - Add `LogResponse` Pydantic model
   - Implement `tail_log_file()` function
   - Add error handling for all edge cases
3. Register new router in `backend/app/main.py`
4. Test endpoints manually:
   - `curl http://localhost:8000/api/health` (verify services field)
   - `curl http://localhost:8000/api/status/logs/backend`

### Phase 1.2: Frontend Components (1-1.5 hours)

**Tasks**:
1. Create API client (`frontend/lib/api/status.ts`)
2. Create hooks:
   - `frontend/lib/hooks/useSystemStatus.ts`
   - `frontend/lib/hooks/useServiceLogs.ts`
3. Create components:
   - `frontend/components/status/SystemStatusCard.tsx`
   - `frontend/components/status/ServiceCard.tsx`
   - `frontend/components/status/LogViewer.tsx`
4. Create page: `frontend/app/status/page.tsx`
5. Test UI in browser:
   - Navigate to http://localhost:3000/status
   - Verify all services show
   - Click expand/collapse logs
   - Test refresh button

### Phase 1.3: Polish & Testing (30 min)

**Tasks**:
1. Add loading states (skeletons)
2. Add error boundaries
3. Test edge cases:
   - Stop a service, verify red status
   - Remove a log file, verify error message
   - Restart service, verify green status
4. Verify responsive design (mobile/tablet/desktop)
5. Verify auto-refresh works (wait 5s, see update)

---

## Future Phases (Reference)

**Phase 2**: Real-time Updates (SSE)
**Phase 3**: Celery Deep Dive (task inspection)
**Phase 4**: System Resources (CPU/disk/memory)
**Phase 5**: Service Controls (restart buttons)
**Phase 6**: Metrics History (uptime trends)

See separate PRDs for each phase.

---

## Notes

- Reuses excellent existing `/health` endpoint infrastructure
- Zero new backend dependencies (stdlib + psutil already installed)
- Zero new frontend dependencies (React Query + shadcn/ui already installed)
- Progressive enhancement path: polling → SSE → WebSocket
- Builds foundation for advanced monitoring in future phases

---

**Next Steps**: Create task list with `/task_it tasks/0028-prd-status-page-mvp.md`
