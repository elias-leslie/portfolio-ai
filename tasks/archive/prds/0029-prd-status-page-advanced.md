# PRD-0029: Status Dashboard Advanced Features (Phases 2-6)

**Status**: Draft
**Created**: 2025-11-03
**Effort**: MEDIUM-HIGH (6-9 hours total)
**Priority**: MEDIUM
**Depends On**: PRD-0028 (Status Dashboard MVP)

---

## Introduction

**Problem**: The MVP status dashboard (PRD-0028) provides essential monitoring via HTTP polling, but lacks real-time updates, deep Celery visibility, system resource monitoring, service control capabilities, and historical trend analysis.

**Goal**: Enhance the status dashboard with professional-grade monitoring features: real-time updates via Server-Sent Events, comprehensive Celery task inspection, system resource monitoring, service management controls, and historical metrics for trend analysis.

**Impact**:
- Real-time updates reduce server load (SSE vs polling)
- Celery visibility prevents task backlog and identifies stuck tasks
- Resource monitoring catches disk/memory issues before failures
- Service controls eliminate SSH for routine operations
- Historical metrics identify reliability patterns and SLA compliance

---

## Phases Overview

| Phase | Feature | Effort | Priority | Description |
|-------|---------|--------|----------|-------------|
| 2 | Real-time Updates (SSE) | 1-2h | HIGH | Replace polling with Server-Sent Events |
| 3 | Celery Deep Dive | 1-2h | HIGH | Task inspection, queue depth, beat schedule |
| 4 | System Resources | 1h | MEDIUM | Disk/memory/CPU, DB pool stats |
| 5 | Service Controls | 1h | MEDIUM | Restart services, clear cache, trigger refresh |
| 6 | Metrics History | 2-3h | LOW | Historical trends, uptime charts |

**Total**: 6-9 hours (incremental enhancement on MVP foundation)

---

## User Stories

**US-1 (Phase 2)**: As a platform operator, I want real-time status updates without refreshing the page so I can see issues immediately as they occur.

**US-2 (Phase 3)**: As a platform operator, I want to see all Celery tasks (active, pending, completed, failed) in one sortable list so I can identify stuck or failing background jobs.

**US-3 (Phase 4)**: As a platform operator, I want to see disk space and memory usage so I can prevent service crashes from resource exhaustion.

**US-4 (Phase 5)**: As a platform operator, I want to restart services from the browser so I don't need to SSH for routine maintenance.

**US-5 (Phase 6)**: As a platform operator, I want to see uptime trends over 30 days so I can measure reliability and identify patterns.

---

## Goals

### Primary Goals

1. **Professional Monitoring**: Upgrade to real-time updates (industry standard)
2. **Celery Transparency**: Full visibility into background task execution
3. **Proactive Alerts**: Catch resource issues before they cause outages
4. **Operational Efficiency**: Manage services without SSH access
5. **Reliability Metrics**: Measure and track uptime over time

### Success Metrics

- **Phase 2**: SSE connection stable, <1% fallback to polling
- **Phase 3**: All Celery tasks visible, queue depth accurately reflects backlog
- **Phase 4**: Resource warnings trigger before 90% thresholds
- **Phase 5**: 90% of restarts done via UI (vs SSH)
- **Phase 6**: 30 days of history stored, charts render in <2s

---

## PHASE 2: Real-time Updates via Server-Sent Events

### Functional Requirements

**FR-2.1: SSE Streaming Endpoint**
- New endpoint: `GET /api/status/stream`
- Returns `text/event-stream` content type
- Streams comprehensive status every 2 seconds
- Includes all data from `/api/health` + service details
- Format:
  ```
  data: {"status": "healthy", "services": {...}, "timestamp": "..."}

  data: {"status": "healthy", "services": {...}, "timestamp": "..."}
  ```

**FR-2.2: EventSource Hook**
- Create `useStatusStream()` hook in `frontend/lib/hooks/useStatusStream.ts`
- Uses browser `EventSource` API (built-in, no dependencies)
- Auto-reconnect on disconnect (EventSource handles this automatically)
- Fallback to polling if EventSource fails after 3 connection attempts
- Return: `{ status, isConnected, connectionState }`

**FR-2.3: Connection State Indicator**
- Show connection status in page header
- States:
  - **Connected** (green dot): "Live • Updated 1s ago"
  - **Connecting** (yellow dot): "Connecting..."
  - **Disconnected** (gray dot): "Disconnected • Using fallback"
  - **Fallback** (blue dot): "Polling mode (5s refresh)"

**FR-2.4: Automatic Fallback**
- If SSE connection fails 3 times in a row, switch to polling
- Show toast notification: "Switched to polling mode due to connection issues"
- User can manually retry SSE via "Retry Live Connection" button
- Simplest, most self-healing approach

### Implementation Notes

**Backend** (`backend/app/api/status.py`):
```python
from fastapi.responses import StreamingResponse
import asyncio
import json

async def status_event_stream():
    """Stream status updates via SSE every 2 seconds."""
    try:
        while True:
            # Gather comprehensive status (reuse existing health logic)
            status_data = await gather_comprehensive_status()

            # Format as SSE event
            yield f"data: {json.dumps(status_data)}\n\n"

            # Wait 2 seconds before next update
            await asyncio.sleep(2)
    except asyncio.CancelledError:
        # Client disconnected, clean up
        pass

@router.get("/stream")
async def stream_status():
    """SSE endpoint for real-time status streaming."""
    return StreamingResponse(
        status_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
```

**Frontend** (`frontend/lib/hooks/useStatusStream.ts`):
```typescript
export function useStatusStream() {
  const [status, setStatus] = useState<HealthResponse | null>(null);
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected' | 'fallback'>('connecting');
  const [failCount, setFailCount] = useState(0);

  useEffect(() => {
    // Fallback to polling if SSE fails 3 times
    if (failCount >= 3) {
      setConnectionState('fallback');
      return; // Let polling hook take over
    }

    const eventSource = new EventSource('/api/status/stream');

    eventSource.onopen = () => {
      setConnectionState('connected');
      setFailCount(0);
    };

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStatus(data);
    };

    eventSource.onerror = () => {
      setConnectionState('disconnected');
      setFailCount(prev => prev + 1);
      eventSource.close();
    };

    return () => eventSource.close();
  }, [failCount]);

  return { status, connectionState, isConnected: connectionState === 'connected' };
}
```

---

## PHASE 3: Celery Deep Dive

### Functional Requirements

**FR-3.1: Celery Task List Endpoint**
- New endpoint: `GET /api/status/celery/tasks`
- Query params:
  - `status`: Filter by "active" | "pending" | "completed" | "failed" | "all" (default: "all")
  - `limit`: Max results (default: 50)
  - `sort`: "time" | "duration" | "name" (default: "time")
- Returns unified task list with:
  ```json
  {
    "tasks": [
      {
        "id": "abc-123",
        "name": "refresh_watchlist_scores",
        "status": "active" | "pending" | "completed" | "failed",
        "started_at": "2025-11-03T19:30:00Z",
        "completed_at": "2025-11-03T19:30:15Z" | null,
        "duration_seconds": 15.2 | null,
        "worker": "celery@localhost",
        "args": ["AAPL", "MSFT"],
        "result": {...} | null,
        "error": "error message" | null
      }
    ],
    "total": 127,
    "active_count": 3,
    "pending_count": 12,
    "completed_count": 100,
    "failed_count": 12
  }
  ```

**FR-3.2: Queue Depth Endpoint**
- New endpoint: `GET /api/status/celery/queue`
- Returns queue statistics:
  ```json
  {
    "queues": [
      {
        "name": "celery",
        "depth": 12,
        "consumers": 4
      }
    ],
    "total_pending": 12
  }
  ```

**FR-3.3: Beat Schedule Display**
- New endpoint: `GET /api/status/celery/schedule`
- Returns scheduled tasks with next run time:
  ```json
  {
    "schedules": [
      {
        "name": "refresh-watchlist-scores",
        "task": "refresh_watchlist_scores",
        "schedule": "every 60 seconds",
        "last_run": "2025-11-03T19:30:00Z",
        "next_run": "2025-11-03T19:31:00Z"
      }
    ]
  }
  ```

**FR-3.4: Unified Task Table Component**
- Component: `CeleryTaskTable.tsx`
- Features:
  - Single sortable table showing all tasks (default: sorted by time descending)
  - Filter dropdown: All | Active | Pending | Completed | Failed
  - Columns: Status badge, Task name, Started, Duration, Worker, Actions
  - Expandable row showing args, result, error message
  - Color coding:
    - Active: Blue pulsing indicator
    - Pending: Yellow clock icon
    - Completed: Green checkmark
    - Failed: Red X with error tooltip
  - Auto-refresh every 5 seconds (via React Query)

**FR-3.5: Queue Depth Visualization**
- Component: `QueueDepthCard.tsx`
- Shows current queue depth with visual indicator
- Warning if depth >50 (yellow), critical if >100 (red)
- Display: "12 tasks pending across 4 workers"

**FR-3.6: Beat Schedule Card**
- Component: `BeatScheduleCard.tsx`
- Lists all scheduled tasks with countdown to next run
- Example: "refresh-watchlist-scores runs in 45 seconds"

### Implementation Notes

**Celery Inspection** (`backend/app/services/celery_inspector.py`):
```python
from celery import current_app
from app.celery_app import celery_app

def get_active_tasks() -> list[dict]:
    """Get currently running tasks from all workers."""
    inspect = celery_app.control.inspect()
    active = inspect.active()
    if not active:
        return []

    tasks = []
    for worker, task_list in active.items():
        for task in task_list:
            tasks.append({
                "id": task['id'],
                "name": task['name'],
                "status": "active",
                "started_at": task['time_start'],
                "worker": worker,
                "args": task['args'],
            })
    return tasks

def get_pending_tasks() -> list[dict]:
    """Get queued tasks waiting for workers."""
    inspect = celery_app.control.inspect()
    reserved = inspect.reserved()
    if not reserved:
        return []

    tasks = []
    for worker, task_list in reserved.items():
        for task in task_list:
            tasks.append({
                "id": task['id'],
                "name": task['name'],
                "status": "pending",
                "worker": worker,
                "args": task['args'],
            })
    return tasks

def get_recent_completed() -> list[dict]:
    """Get last 50 completed tasks from result backend."""
    # Query celery_taskmeta table in PostgreSQL
    from app.storage import get_storage
    storage = get_storage()

    results = storage.query("""
        SELECT task_id, task, status, date_done, result
        FROM celery_taskmeta
        WHERE status = 'SUCCESS'
        ORDER BY date_done DESC
        LIMIT 50
    """)
    # ... format results

def get_recent_failed() -> list[dict]:
    """Get last 50 failed tasks from result backend."""
    # Query celery_taskmeta table
    results = storage.query("""
        SELECT task_id, task, status, date_done, result, traceback
        FROM celery_taskmeta
        WHERE status IN ('FAILURE', 'RETRY')
        ORDER BY date_done DESC
        LIMIT 50
    """)
    # ... format results
```

---

## PHASE 4: System Resources

### Functional Requirements

**FR-4.1: System Resources Endpoint**
- New endpoint: `GET /api/status/resources`
- Returns system resource usage:
  ```json
  {
    "disk": {
      "path": "/",
      "total_gb": 500,
      "used_gb": 250,
      "available_gb": 250,
      "percent_used": 50.0,
      "status": "ok" | "warning" | "critical"
    },
    "memory": {
      "total_gb": 16,
      "used_gb": 8.5,
      "available_gb": 7.5,
      "percent_used": 53.1,
      "status": "ok" | "warning" | "critical"
    },
    "cpu": {
      "percent_used": 45.2,
      "core_count": 8,
      "status": "ok" | "warning" | "critical"
    },
    "database_pool": {
      "pool_size": 20,
      "active_connections": 5,
      "idle_connections": 15,
      "overflow": 0,
      "max_overflow": 10,
      "percent_used": 25.0,
      "status": "ok" | "warning" | "critical"
    }
  }
  ```

**FR-4.2: Resource Thresholds**
- **Disk**:
  - OK: <80% used
  - Warning: 80-90% used
  - Critical: >90% used
- **Memory**:
  - OK: <85% used
  - Warning: 85-95% used
  - Critical: >95% used
- **CPU**:
  - OK: <80% used
  - Warning: 80-90% used
  - Critical: >90% used
- **DB Pool**:
  - OK: <75% connections used
  - Warning: 75-90% used
  - Critical: >90% used

**FR-4.3: Resource Cards**
- Component: `ResourceCard.tsx`
- Shows resource usage with progress bar
- Color-coded by threshold (green/yellow/red)
- Warning icon if threshold exceeded
- Tooltip with recommended action

**FR-4.4: Database Pool Card**
- Component: `DatabasePoolCard.tsx`
- Shows active vs idle connections
- Pool size and max overflow
- Warning if pool exhausted or near limit

### Implementation Notes

**Add Dependency**: `psutil` (likely already installed, verify)

**Resource Monitoring** (`backend/app/services/resource_monitor.py`):
```python
import psutil
import shutil
from sqlalchemy import inspect

def get_disk_usage() -> dict:
    """Get disk usage for root partition."""
    usage = shutil.disk_usage("/")
    total_gb = usage.total / (1024**3)
    used_gb = usage.used / (1024**3)
    available_gb = usage.free / (1024**3)
    percent = (usage.used / usage.total) * 100

    status = "ok"
    if percent >= 90:
        status = "critical"
    elif percent >= 80:
        status = "warning"

    return {
        "path": "/",
        "total_gb": round(total_gb, 1),
        "used_gb": round(used_gb, 1),
        "available_gb": round(available_gb, 1),
        "percent_used": round(percent, 1),
        "status": status
    }

def get_memory_usage() -> dict:
    """Get system memory usage."""
    mem = psutil.virtual_memory()
    percent = mem.percent

    status = "ok"
    if percent >= 95:
        status = "critical"
    elif percent >= 85:
        status = "warning"

    return {
        "total_gb": round(mem.total / (1024**3), 1),
        "used_gb": round(mem.used / (1024**3), 1),
        "available_gb": round(mem.available / (1024**3), 1),
        "percent_used": round(percent, 1),
        "status": status
    }

def get_db_pool_stats() -> dict:
    """Get database connection pool statistics."""
    from app.storage.connection import get_connection_manager
    conn_mgr = get_connection_manager()
    pool = conn_mgr.engine.pool

    active = pool.checkedout()
    idle = pool.size() - active
    overflow = pool.overflow()

    total_capacity = pool.size() + pool._max_overflow
    percent_used = (active / total_capacity) * 100 if total_capacity > 0 else 0

    status = "ok"
    if percent_used >= 90:
        status = "critical"
    elif percent_used >= 75:
        status = "warning"

    return {
        "pool_size": pool.size(),
        "active_connections": active,
        "idle_connections": idle,
        "overflow": overflow,
        "max_overflow": pool._max_overflow,
        "percent_used": round(percent_used, 1),
        "status": status
    }
```

---

## PHASE 5: Service Controls

### Functional Requirements

**FR-5.1: Service Restart Endpoint**
- New endpoint: `POST /api/status/services/{service}/restart`
- Valid services: "backend" | "celery-worker" | "celery-beat" | "frontend" | "all"
- Calls `scripts/restart.sh` subprocess
- Returns:
  ```json
  {
    "service": "backend",
    "action": "restart",
    "status": "success" | "error",
    "message": "Backend API restarted successfully",
    "pid": 12345
  }
  ```

**FR-5.2: Cache Clear Endpoint**
- New endpoint: `POST /api/status/cache/clear`
- Clears price_cache table
- Returns count of cleared entries

**FR-5.3: Manual Watchlist Refresh Endpoint**
- New endpoint: `POST /api/status/watchlist/refresh`
- Triggers immediate `refresh_watchlist_scores` Celery task
- Returns task ID for tracking

**FR-5.4: Confirmation Dialog Component**
- Component: `ServiceActionDialog.tsx`
- Shows before destructive actions
- Includes:
  - Warning about service impact
  - Estimated downtime
  - Checkbox: "Don't ask me again" (stored in localStorage)
  - Confirm / Cancel buttons

**FR-5.5: Action Buttons**
- Add to each ServiceCard:
  - "Restart Service" button (with confirmation)
  - Disabled if service already stopped
- Add to page header:
  - "Clear Cache" button
  - "Refresh Watchlist Now" button

**FR-5.6: Toast Notifications**
- Success: Green toast "Backend API restarted successfully"
- Error: Red toast "Failed to restart service: [error message]"
- Progress: Blue toast "Restarting service..."

### Implementation Notes

**Service Control** (`backend/app/api/status.py`):
```python
import subprocess
from pathlib import Path

@router.post("/services/{service}/restart")
async def restart_service(service: str):
    """Restart a service using scripts/restart.sh."""
    if service not in ["backend", "celery-worker", "celery-beat", "frontend", "all"]:
        raise HTTPException(status_code=400, detail="Invalid service name")

    try:
        # Call restart script
        script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "restart.sh"
        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            # Get new PID
            new_pid = get_service_pid(service)
            return {
                "service": service,
                "action": "restart",
                "status": "success",
                "message": f"{service} restarted successfully",
                "pid": new_pid
            }
        else:
            return {
                "service": service,
                "action": "restart",
                "status": "error",
                "message": f"Failed to restart: {result.stderr}"
            }
    except Exception as e:
        return {
            "service": service,
            "action": "restart",
            "status": "error",
            "message": str(e)
        }
```

**Confirmation Dialog** (`frontend/components/status/ServiceActionDialog.tsx`):
```typescript
export function ServiceActionDialog({ service, action, onConfirm, onCancel }) {
  const [dontAskAgain, setDontAskAgain] = useState(false);

  const handleConfirm = () => {
    if (dontAskAgain) {
      localStorage.setItem(`skip-confirm-${action}`, 'true');
    }
    onConfirm();
  };

  return (
    <Dialog>
      <DialogContent>
        <DialogTitle>Restart {service}?</DialogTitle>
        <DialogDescription>
          This will briefly interrupt the {service} service.
          Estimated downtime: ~5 seconds.
        </DialogDescription>
        <div className="flex items-center space-x-2">
          <Checkbox
            checked={dontAskAgain}
            onCheckedChange={setDontAskAgain}
          />
          <label>Don't ask me again</label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={handleConfirm}>Restart Service</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

---

## PHASE 6: Metrics History (Optional)

### Functional Requirements

**FR-6.1: History Table Schema**
- New table: `system_status_history`
  ```sql
  CREATE TABLE system_status_history (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    service_name TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'running', 'stopped', 'degraded'
    pid INTEGER,
    uptime_seconds INTEGER,
    memory_mb INTEGER,
    metrics JSONB,  -- Flexible field for additional metrics
    created_at TIMESTAMPTZ DEFAULT NOW()
  );

  CREATE INDEX idx_status_history_timestamp ON system_status_history(timestamp DESC);
  CREATE INDEX idx_status_history_service ON system_status_history(service_name, timestamp DESC);
  ```

**FR-6.2: Background Snapshot Task**
- New Celery task: `store_status_snapshot`
- Runs every 5 minutes (via Beat schedule)
- Captures current system status and stores in `system_status_history`
- Deletes records older than 30 days (matches Celery result retention)

**FR-6.3: History Query Endpoint**
- New endpoint: `GET /api/status/history`
- Query params:
  - `service`: Filter by service name (optional, default: all)
  - `period`: "24h" | "7d" | "30d" (default: "24h")
  - `metric`: "uptime" | "memory" | "status_changes" (default: "uptime")
- Returns time-series data for charting

**FR-6.4: Uptime Chart Component**
- Component: `UptimeChart.tsx`
- Shows service uptime percentage over selected period
- Example: "Backend API: 99.8% uptime (last 30 days)"
- Bar chart showing daily uptime

**FR-6.5: Performance Trend Chart**
- Component: `PerformanceTrendChart.tsx`
- Shows memory usage over time
- Line chart with warning thresholds marked

**FR-6.6: Status Timeline**
- Component: `StatusTimeline.tsx`
- Shows major status changes (service stops/starts)
- Example: "Nov 1: Backend down for 3 minutes"

### Implementation Notes

**Snapshot Task** (`backend/app/tasks/monitoring_tasks.py`):
```python
from celery import shared_task
from datetime import datetime, timedelta

@shared_task(name="store_status_snapshot")
def store_status_snapshot():
    """Store current system status in history table."""
    from app.storage import get_storage
    from app.services.system_monitor import gather_comprehensive_status

    storage = get_storage()
    status = gather_comprehensive_status()

    # Store snapshot for each service
    for service_name, service_status in status['services'].items():
        storage.execute("""
            INSERT INTO system_status_history
            (service_name, status, pid, uptime_seconds, memory_mb, metrics)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            service_name,
            service_status['status'],
            service_status['pid'],
            service_status['uptime_seconds'],
            service_status['memory_mb'],
            json.dumps(service_status)  # Store full status as JSONB
        ])

    # Cleanup old records (>30 days)
    cutoff = datetime.now() - timedelta(days=30)
    storage.execute("""
        DELETE FROM system_status_history
        WHERE timestamp < ?
    """, [cutoff])
```

**Add to Beat Schedule** (`backend/app/celery_app.py`):
```python
app.conf.beat_schedule = {
    # ... existing schedules
    'store-status-snapshot': {
        'task': 'store_status_snapshot',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}
```

---

## Non-Goals

**Explicitly Out of Scope**:
- ❌ Mobile app or native notifications
- ❌ Multi-user access control / authentication
- ❌ External alerting (email, Slack, PagerDuty)
- ❌ Custom dashboards or widget configuration
- ❌ Export to external monitoring (Prometheus, Grafana)
- ❌ Kubernetes/Docker container monitoring
- ❌ Network monitoring or external endpoint checks
- ❌ Log aggregation (ELK stack integration)

---

## Dependencies

### New Dependencies

**Backend**:
- Phase 4: Verify `psutil` is installed (likely already in requirements.txt)
- No other new dependencies needed

**Frontend**:
- No new dependencies needed
- All features use existing stack (React Query, shadcn/ui, EventSource API)

---

## Acceptance Criteria

### Phase 2: Real-time Updates (SSE)

**AC-2.1**: SSE endpoint streams status every 2 seconds
**AC-2.2**: EventSource connection auto-reconnects on disconnect
**AC-2.3**: Fallback to polling after 3 failed SSE attempts
**AC-2.4**: Connection indicator shows current state (connected/disconnected/fallback)
**AC-2.5**: Page updates without manual refresh
**AC-2.6**: <1% of users fall back to polling under normal conditions

### Phase 3: Celery Deep Dive

**AC-3.1**: Unified task table shows active, pending, completed, failed tasks
**AC-3.2**: Table is sortable by time (default), duration, name
**AC-3.3**: Filter dropdown works (All | Active | Pending | Completed | Failed)
**AC-3.4**: Queue depth displays correctly, warns if >50, critical if >100
**AC-3.5**: Beat schedule shows next run countdown
**AC-3.6**: Task details expand on row click (args, result, error)

### Phase 4: System Resources

**AC-4.1**: Disk, memory, CPU usage display with correct percentages
**AC-4.2**: Warning badges show at correct thresholds (80%/85%/80%)
**AC-4.3**: Database pool stats show active vs idle connections
**AC-4.4**: Resource cards update every 5 seconds
**AC-4.5**: Critical warnings visible when >90% usage

### Phase 5: Service Controls

**AC-5.1**: Restart button restarts services successfully
**AC-5.2**: Confirmation dialog appears (unless "don't ask again" checked)
**AC-5.3**: Toast notifications show success/error
**AC-5.4**: Cache clear removes entries from price_cache table
**AC-5.5**: Manual watchlist refresh triggers Celery task immediately
**AC-5.6**: Buttons disabled during action execution

### Phase 6: Metrics History

**AC-6.1**: History data stored every 5 minutes
**AC-6.2**: Uptime chart renders for 24h/7d/30d periods
**AC-6.3**: Performance trend shows memory usage over time
**AC-6.4**: Status timeline shows service stop/start events
**AC-6.5**: Data auto-deleted after 30 days
**AC-6.6**: Charts render in <2 seconds

---

## Edge Cases & Error Handling

**EC-1: SSE Connection Interrupted**
- EventSource auto-reconnects (built-in)
- If reconnect fails 3x, switch to polling fallback
- Show toast: "Connection interrupted, using polling mode"

**EC-2: Celery Inspect Commands Fail**
- If no workers respond, show "No active workers"
- Gracefully handle timeout (5s limit)
- Fall back to result backend queries only

**EC-3: Celery Result Backend Empty**
- If no tasks in history, show "No recent tasks"
- Explain: "Tasks appear after first execution"

**EC-4: Resource Monitoring Unavailable**
- If psutil fails, show "Resource monitoring unavailable"
- Don't crash page, continue showing other metrics

**EC-5: Service Restart Fails**
- Show error toast with stderr output
- Provide troubleshooting: "Check logs: tail -f /tmp/portfolio-backend.log"

**EC-6: Database Pool Exhausted**
- Critical warning if 100% pool usage
- Message: "Connection pool exhausted. Increase pool_size or reduce connections."

**EC-7: History Table Growth**
- Auto-cleanup after 30 days prevents unbounded growth
- Monitor table size in resource dashboard

**EC-8: Beat Schedule Not Running**
- If no scheduled tasks detected, show warning
- Message: "Celery Beat not running. Start with scripts/start.sh"

---

## Implementation Plan

### Phase 2: Real-time Updates (1-2 hours)

**Tasks**:
1. Add SSE endpoint to `backend/app/api/status.py`
2. Create `useStatusStream` hook
3. Add connection indicator to status page
4. Implement fallback logic (SSE → polling)
5. Test: Open status page, verify real-time updates without refresh
6. Test: Kill SSE connection, verify fallback

### Phase 3: Celery Deep Dive (1-2 hours)

**Tasks**:
1. Create `backend/app/services/celery_inspector.py`
2. Add endpoints: `/api/status/celery/tasks`, `/queue`, `/schedule`
3. Create `CeleryTaskTable`, `QueueDepthCard`, `BeatScheduleCard` components
4. Add to status page
5. Test: Start task, verify appears in active list
6. Test: Filter by failed, verify only failed tasks shown

### Phase 4: System Resources (1 hour)

**Tasks**:
1. Verify `psutil` installed, add if needed
2. Create `backend/app/services/resource_monitor.py`
3. Add `/api/status/resources` endpoint
4. Create `ResourceCard` and `DatabasePoolCard` components
5. Test: Fill disk to 85%, verify warning appears
6. Test: Create many DB connections, verify pool stats

### Phase 5: Service Controls (1 hour)

**Tasks**:
1. Add POST endpoints: `/services/{service}/restart`, `/cache/clear`, `/watchlist/refresh`
2. Create `ServiceActionDialog` component
3. Add action buttons to service cards
4. Implement toast notifications
5. Test: Restart backend, verify downtime <10s
6. Test: Check "don't ask again", verify stored in localStorage

### Phase 6: Metrics History (2-3 hours)

**Tasks**:
1. Create migration for `system_status_history` table
2. Add `store_status_snapshot` Celery task
3. Update beat schedule to run every 5 minutes
4. Add `/api/status/history` endpoint
5. Create chart components: `UptimeChart`, `PerformanceTrendChart`, `StatusTimeline`
6. Test: Wait 15 minutes, verify 3 snapshots stored
7. Test: View 30-day chart, verify data renders

---

## Testing Strategy

### Manual Testing Checklist

**Phase 2**:
- [ ] Open status page, verify updates without refresh
- [ ] Disconnect network, verify fallback to polling
- [ ] Reconnect network, verify SSE reconnects
- [ ] Check connection indicator shows correct state

**Phase 3**:
- [ ] Trigger Celery task, verify appears in active list
- [ ] Wait for task completion, verify moves to completed
- [ ] Filter by failed, verify only failed tasks shown
- [ ] Check queue depth matches actual queue

**Phase 4**:
- [ ] Verify resource percentages match `df -h` and `free -h`
- [ ] Check DB pool stats match SQLAlchemy pool
- [ ] Trigger warning threshold, verify badge color

**Phase 5**:
- [ ] Restart service, verify confirmation dialog
- [ ] Click "don't ask again", restart again, verify no dialog
- [ ] Clear cache, verify price_cache table empty
- [ ] Trigger watchlist refresh, verify task starts

**Phase 6**:
- [ ] Wait 5 minutes, verify snapshot stored
- [ ] View history chart, verify data points
- [ ] Check 30-day retention cleanup works

---

## Future Enhancements (Beyond Phase 6)

- Custom alert thresholds per user
- Email/Slack notifications on critical events
- Grafana/Prometheus integration
- Multi-server monitoring (if scaling to multiple instances)
- Custom dashboard widgets
- Export status reports to PDF/CSV
- Mobile responsive improvements
- Dark mode optimization

---

## Notes

- All phases build incrementally on PRD-0028 MVP
- Each phase is independently deployable
- No breaking changes to existing MVP functionality
- Zero new frontend dependencies
- Minimal backend dependencies (only psutil for Phase 4)
- Progressive enhancement: polling → SSE → WebSocket (future)

---

**Next Steps**:
1. Implement PRD-0028 (MVP) first
2. Create task lists for desired phases: `/task_it tasks/0029-prd-status-page-advanced.md`
3. Implement phases incrementally based on priority
