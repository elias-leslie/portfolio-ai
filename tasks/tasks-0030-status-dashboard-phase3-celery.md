# Task List: Status Dashboard - Phase 3 (Celery Deep Dive)

**PRD**: `tasks/0029-prd-status-page-advanced.md` (Phase 3)
**Depends On**: tasks-0028-status-dashboard-mvp.md (MUST be complete)
**Status**: Ready for Implementation (after Phase 1)
**Completion**: 0%
**Effort**: MEDIUM (1-2 hours)
**Priority**: HIGH
**Created**: 2025-11-03
**Updated**: 2025-11-03

---

## Summary

**✅ COMPLETE:** (None)
**🔄 IN PROGRESS:** (Not started)
**⚠️ NEXT:** Task 1.0 - Backend: Celery Inspection Service

---

## Relevant Files

### Create (8 files)
- `backend/app/services/celery_inspector.py` (~250 lines) - Celery inspection logic
- `backend/app/api/celery_endpoints.py` (~150 lines) - Celery status endpoints
- `frontend/components/status/CeleryTaskTable.tsx` (~200 lines) - Unified task table
- `frontend/components/status/QueueDepthCard.tsx` (~80 lines) - Queue depth visualization
- `frontend/components/status/BeatScheduleCard.tsx` (~100 lines) - Beat schedule display
- `frontend/lib/api/celery.ts` (~60 lines) - Celery API client
- `frontend/lib/hooks/useCeleryTasks.ts` (~40 lines) - React Query hook
- `tests/services/test_celery_inspector.py` (~150 lines) - Celery inspector tests

### Update (3 files)
- `backend/app/main.py` - Register celery endpoints router
- `frontend/app/status/page.tsx` - Add Celery section with tables/cards
- `frontend/components/ui/table.tsx` - Verify table component exists (may need shadcn add)

### Notes
- Uses Celery inspect() API (already available via celery_app)
- Queries celery_taskmeta table in PostgreSQL for completed/failed tasks
- Tests: `pytest tests/services/test_celery_inspector.py -v`

---

## Tasks

- [ ] **1.0 Backend: Celery Inspection Service** (45 min)
  - [ ] 1.1 Create celery_inspector.py module (35 min)
    - [ ] 1.1.1 Create backend/app/services/celery_inspector.py with imports (1 min)
    - [ ] 1.1.2 Write failing test for get_active_tasks() (3 min)
    - [ ] 1.1.3 Implement get_active_tasks() using celery_app.control.inspect().active() (5 min)
    - [ ] 1.1.4 Write failing test for get_pending_tasks() (3 min)
    - [ ] 1.1.5 Implement get_pending_tasks() using inspect().reserved() (4 min)
    - [ ] 1.1.6 Write failing test for get_recent_completed() (3 min)
    - [ ] 1.1.7 Implement get_recent_completed() querying celery_taskmeta table (5 min)
    - [ ] 1.1.8 Write failing test for get_recent_failed() (3 min)
    - [ ] 1.1.9 Implement get_recent_failed() querying celery_taskmeta table (4 min)
    - [ ] 1.1.10 Implement get_queue_depth() using celery inspect (4 min)

  - [ ] 1.2 Create unified task list function (10 min)
    - [ ] 1.2.1 Write failing test for get_unified_task_list() (3 min)
    - [ ] 1.2.2 Implement get_unified_task_list() merging all task sources (4 min)
    - [ ] 1.2.3 Add filtering by status (active/pending/completed/failed/all) (3 min)

- [ ] **2.0 Backend: Celery Endpoints** (25 min)
  - [ ] 2.1 Create Pydantic models (10 min)
    - [ ] 2.1.1 Create backend/app/api/celery_endpoints.py with imports (1 min)
    - [ ] 2.1.2 Define TaskInfo model (id, name, status, started_at, duration, worker, args, result, error) (3 min)
    - [ ] 2.1.3 Define TaskListResponse model (tasks, total, active_count, pending_count, completed_count, failed_count) (3 min)
    - [ ] 2.1.4 Define QueueInfo model (name, depth, consumers) (2 min)
    - [ ] 2.1.5 Define ScheduleInfo model (name, task, schedule, last_run, next_run) (1 min)

  - [ ] 2.2 Implement endpoints (12 min)
    - [ ] 2.2.1 Write failing test for GET /api/status/celery/tasks (3 min)
    - [ ] 2.2.2 Implement GET /api/status/celery/tasks with query params (status, limit, sort) (4 min)
    - [ ] 2.2.3 Write failing test for GET /api/status/celery/queue (2 min)
    - [ ] 2.2.4 Implement GET /api/status/celery/queue endpoint (2 min)
    - [ ] 2.2.5 Implement GET /api/status/celery/schedule endpoint (1 min)

  - [ ] 2.3 Register router (3 min)
    - [ ] 2.3.1 Import celery_endpoints router in backend/app/main.py (1 min)
    - [ ] 2.3.2 Add app.include_router(celery_endpoints.router) (1 min)
    - [ ] 2.3.3 Test endpoints: curl http://localhost:8000/api/status/celery/tasks | jq (1 min)

- [ ] **3.0 Frontend: Celery Components** (50 min)
  - [ ] 3.1 Install table component (2 min)
    - [ ] 3.1.1 Check if table exists: ls frontend/components/ui/table.tsx (1 min)
    - [ ] 3.1.2 If missing, install: cd ~/portfolio-ai/frontend && npx shadcn@latest add table (1 min)

  - [ ] 3.2 Create Celery API client (5 min)
    - [ ] 3.2.1 Create frontend/lib/api/celery.ts with type definitions (2 min)
    - [ ] 3.2.2 Implement fetchCeleryTasks(status?, limit?, sort?) function (2 min)
    - [ ] 3.2.3 Implement fetchQueueDepth() and fetchBeatSchedule() functions (1 min)

  - [ ] 3.3 Create useCeleryTasks hook (5 min)
    - [ ] 3.3.1 Create frontend/lib/hooks/useCeleryTasks.ts (2 min)
    - [ ] 3.3.2 Implement useQuery with 5s refetchInterval (2 min)
    - [ ] 3.3.3 Add status filter parameter (1 min)

  - [ ] 3.4 Create CeleryTaskTable component (20 min)
    - [ ] 3.4.1 Create frontend/components/status/CeleryTaskTable.tsx with props (2 min)
    - [ ] 3.4.2 Add filter dropdown (All | Active | Pending | Completed | Failed) (4 min)
    - [ ] 3.4.3 Implement Table with columns: Status, Task Name, Started, Duration, Worker, Actions (5 min)
    - [ ] 3.4.4 Add sortable headers (click to sort by time/duration/name) (4 min)
    - [ ] 3.4.5 Add expandable rows for args/result/error details (3 min)
    - [ ] 3.4.6 Add status badges with colors (Active=blue pulsing, Pending=yellow, Completed=green, Failed=red) (2 min)

  - [ ] 3.5 Create QueueDepthCard component (8 min)
    - [ ] 3.5.1 Create frontend/components/status/QueueDepthCard.tsx (2 min)
    - [ ] 3.5.2 Display queue depth with visual indicator (2 min)
    - [ ] 3.5.3 Add warning thresholds (>50 yellow, >100 red) (2 min)
    - [ ] 3.5.4 Display: "X tasks pending across Y workers" (2 min)

  - [ ] 3.6 Create BeatScheduleCard component (10 min)
    - [ ] 3.6.1 Create frontend/components/status/BeatScheduleCard.tsx (2 min)
    - [ ] 3.6.2 Display list of scheduled tasks (3 min)
    - [ ] 3.6.3 Add countdown timer to next run (4 min)
    - [ ] 3.6.4 Format schedule string (every X seconds/minutes) (1 min)

- [ ] **4.0 Integration & Testing** (30 min)
  - [ ] 4.1 Add to status page (10 min)
    - [ ] 4.1.1 Update frontend/app/status/page.tsx to add Celery section (2 min)
    - [ ] 4.1.2 Add QueueDepthCard and BeatScheduleCard to grid (3 min)
    - [ ] 4.1.3 Add CeleryTaskTable below service cards (3 min)
    - [ ] 4.1.4 Test layout with all components (2 min)

  - [ ] 4.2 Backend tests (10 min)
    - [ ] 4.2.1 Run pytest tests/services/test_celery_inspector.py -v (3 min)
    - [ ] 4.2.2 Verify all task queries work (active, pending, completed, failed) (3 min)
    - [ ] 4.2.3 Verify queue depth calculation (2 min)
    - [ ] 4.2.4 Check coverage: pytest --cov=app.services.celery_inspector (2 min)

  - [ ] 4.3 UI testing with browser automation (10 min)
    - [ ] 4.3.1 Restart services: bash ~/portfolio-ai/scripts/restart.sh (2 min)
    - [ ] 4.3.2 Trigger Celery task to generate test data (1 min)
    - [ ] 4.3.3 Navigate to /status and scroll to Celery section (1 min)
    - [ ] 4.3.4 Take screenshot: node ~/.claude/skills/browser-automation/scripts/screenshot.js http://192.168.8.233:3000/status /tmp/status-celery.png true (1 min)
    - [ ] 4.3.5 Test filter dropdown (click "Active" filter) via interact.js (2 min)
    - [ ] 4.3.6 Test row expansion (click expand icon) via interact.js (2 min)
    - [ ] 4.3.7 Verify queue depth shows correct number (1 min)

---

## Verification (MANDATORY before "COMPLETE ✅")

- [ ] **Functional**: All Phase 3 requirements met
  - [ ] AC-3.1: Unified task table shows active, pending, completed, failed tasks
  - [ ] AC-3.2: Table is sortable by time (default), duration, name
  - [ ] AC-3.3: Filter dropdown works (All | Active | Pending | Completed | Failed)
  - [ ] AC-3.4: Queue depth displays correctly, warns if >50, critical if >100
  - [ ] AC-3.5: Beat schedule shows next run countdown
  - [ ] AC-3.6: Task details expand on row click (args, result, error)

- [ ] **Tests**: Coverage >80%, all passing
  - [ ] pytest tests/services/test_celery_inspector.py -v passes
  - [ ] All task query tests pass (active, pending, completed, failed)
  - [ ] Queue depth calculation tests pass

- [ ] **Quality**: Linting passes
  - [ ] Run: ~/portfolio-ai/scripts/lint.sh
  - [ ] No type errors
  - [ ] All functions have type hints

- [ ] **Ops**: Service restart verified
  - [ ] bash ~/portfolio-ai/scripts/restart.sh
  - [ ] Trigger test task: from CLI or via watchlist refresh
  - [ ] Verify task appears in table

---

## Notes

### Celery Inspection API
```python
from app.celery_app import celery_app

inspect = celery_app.control.inspect()

# Get active tasks
active = inspect.active()  # {worker_name: [task_dict, ...]}

# Get reserved (pending) tasks
reserved = inspect.reserved()

# Get scheduled tasks
scheduled = inspect.scheduled()

# Get registered tasks
registered = inspect.registered()

# Get queue stats (requires rabbitmq/redis broker stats)
stats = inspect.stats()
```

### Celery Result Backend (PostgreSQL)
```sql
-- Query celery_taskmeta table
SELECT task_id, task, status, date_done, result, traceback
FROM celery_taskmeta
WHERE status = 'SUCCESS'
ORDER BY date_done DESC
LIMIT 50;

-- Task statuses: SUCCESS, FAILURE, PENDING, RETRY, STARTED
```

### Task Status Colors
- **Active** (running): Blue with pulsing animation
- **Pending** (queued): Yellow with clock icon
- **Completed** (success): Green with checkmark
- **Failed** (error): Red with X icon

### API Testing
```bash
# Get all tasks
curl http://localhost:8000/api/status/celery/tasks | jq

# Get only active tasks
curl 'http://localhost:8000/api/status/celery/tasks?status=active' | jq

# Get queue depth
curl http://localhost:8000/api/status/celery/queue | jq

# Get beat schedule
curl http://localhost:8000/api/status/celery/schedule | jq
```

### Triggering Test Tasks
```bash
# From backend directory with venv activated
cd ~/portfolio-ai/backend && source .venv/bin/activate

# Trigger refresh_watchlist_scores task
python -c "from app.tasks.watchlist_tasks import refresh_watchlist_scores; refresh_watchlist_scores.delay()"
```

---

**Status**: Ready for /do_it execution (after Phase 1 complete)
**Next**: Run `/do_it tasks-0030-status-dashboard-phase3-celery.md` after Phase 1
