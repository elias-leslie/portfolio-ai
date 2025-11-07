# Task List: Status Dashboard - Phases 4-6 (Resources, Controls, History)

**PRD**: `tasks/0029-prd-status-page-advanced.md` (Phases 4, 5, 6)
**Depends On**: tasks-0028-status-dashboard-mvp.md (MUST be complete)
**Status**: Phase 4 COMPLETE ✅
**Completion**: 33% (Phase 4 of 3 phases)
**Effort**: HIGH (4-6 hours total)
**Priority**: MEDIUM-LOW
**Created**: 2025-11-03
**Updated**: 2025-11-04

---

## Summary

**✅ COMPLETE:** Phase 4 - System Resources
**🔄 IN PROGRESS:** (None)
**⚠️ NEXT:** Phase 5 - Service Controls (optional)

This task list combines three lower-priority phases:
- **Phase 4**: System resource monitoring (disk, memory, CPU, DB pool)
- **Phase 5**: Service control buttons (restart, cache clear, manual refresh)
- **Phase 6**: Historical metrics and uptime trends

Each phase is independently implementable.

---

## PHASE 4: System Resource Monitoring (1 hour)

### Relevant Files (Phase 4)

#### Create (5 files)
- `backend/app/services/resource_monitor.py` (~200 lines) - System resource monitoring
- `frontend/components/status/ResourceCard.tsx` (~80 lines) - Resource usage card
- `frontend/components/status/DatabasePoolCard.tsx` (~100 lines) - DB pool visualization
- `frontend/lib/api/resources.ts` (~30 lines) - Resources API client
- `tests/services/test_resource_monitor.py` (~100 lines) - Resource monitor tests

#### Update (2 files)
- `backend/app/api/status.py` - Add GET /api/status/resources endpoint
- `frontend/app/status/page.tsx` - Add resource monitoring section

#### Dependencies
- `psutil` - Already installed in Phase 1 (Task 1.1)

### Tasks - Phase 4 ✅ COMPLETE

- [x] **4.1 Backend: Resource Monitoring Service** (30 min)
  - [x] 4.1.1 Create backend/app/services/resource_monitor.py with imports (1 min)
  - [x] 4.1.2 Write failing test for get_disk_usage() (2 min)
  - [x] 4.1.3 Implement get_disk_usage() using shutil.disk_usage() (4 min)
  - [x] 4.1.4 Add disk usage thresholds (80% warning, 90% critical) (2 min)
  - [x] 4.1.5 Write failing test for get_memory_usage() (2 min)
  - [x] 4.1.6 Implement get_memory_usage() using psutil.virtual_memory() (3 min)
  - [x] 4.1.7 Add memory thresholds (85% warning, 95% critical) (2 min)
  - [x] 4.1.8 Write failing test for get_cpu_usage() (2 min)
  - [x] 4.1.9 Implement get_cpu_usage() using psutil.cpu_percent() (2 min)
  - [x] 4.1.10 Write failing test for get_db_pool_stats() (3 min)
  - [x] 4.1.11 Implement get_db_pool_stats() querying SQLAlchemy pool (5 min)
  - [x] 4.1.12 Add pool thresholds (75% warning, 90% critical) (2 min)

- [x] **4.2 Backend: Resources Endpoint** (10 min)
  - [x] 4.2.1 Create ResourcesResponse Pydantic model in status.py (3 min)
  - [x] 4.2.2 Write tests for resource monitoring service (2 min)
  - [x] 4.2.3 Implement GET /api/status/resources endpoint (3 min)
  - [x] 4.2.4 Test: curl http://localhost:8000/api/status/resources | jq (2 min)

- [x] **4.3 Frontend: Resource Components** (20 min)
  - [x] 4.3.1 Create frontend/lib/api/resources.ts API client (2 min)
  - [x] 4.3.2 Create ResourceCard component with progress bar (6 min)
  - [x] 4.3.3 Add color coding by threshold (green/yellow/red) (2 min)
  - [x] 4.3.4 Add warning icon and tooltip for exceeded thresholds (3 min)
  - [x] 4.3.5 Create DatabasePoolCard component (5 min)
  - [x] 4.3.6 Add to status page resource section (2 min)

---

## PHASE 5: Service Controls (1 hour)

### Relevant Files (Phase 5)

#### Create (4 files)
- `frontend/components/status/ServiceActionDialog.tsx` (~100 lines) - Confirmation dialog
- `frontend/lib/api/service-control.ts` (~60 lines) - Service control API client
- `tests/api/test_service_control.py` (~120 lines) - Service control tests
- `scripts/restart-service.sh` (~50 lines) - Individual service restart script

#### Update (2 files)
- `backend/app/api/status.py` - Add service control endpoints (restart, cache clear, manual refresh)
- `frontend/components/status/ServiceCard.tsx` - Add action buttons

### Tasks - Phase 5

- [ ] **5.1 Backend: Service Control Endpoints** (25 min)
  - [ ] 5.1.1 Create scripts/restart-service.sh script (accepts service name) (5 min)
  - [ ] 5.1.2 Write failing test for POST /api/status/services/{service}/restart (3 min)
  - [ ] 5.1.3 Implement POST /api/status/services/{service}/restart endpoint (5 min)
  - [ ] 5.1.4 Add service name validation (whitelist) (2 min)
  - [ ] 5.1.5 Write failing test for POST /api/status/cache/clear (2 min)
  - [ ] 5.1.6 Implement POST /api/status/cache/clear (DELETE FROM price_cache) (3 min)
  - [ ] 5.1.7 Write failing test for POST /api/status/watchlist/refresh (2 min)
  - [ ] 5.1.8 Implement POST /api/status/watchlist/refresh (trigger Celery task) (3 min)

- [ ] **5.2 Frontend: Service Control UI** (25 min)
  - [ ] 5.2.1 Create frontend/lib/api/service-control.ts API client (3 min)
  - [ ] 5.2.2 Create ServiceActionDialog component with confirmation (8 min)
  - [ ] 5.2.3 Add "Don't ask again" checkbox with localStorage (3 min)
  - [ ] 5.2.4 Add "Restart Service" button to ServiceCard (3 min)
  - [ ] 5.2.5 Add "Clear Cache" and "Refresh Watchlist" buttons to page header (3 min)
  - [ ] 5.2.6 Implement toast notifications (success/error/progress) (5 min)

- [ ] **5.3 Testing** (10 min)
  - [ ] 5.3.1 Test restart endpoint: curl -X POST http://localhost:8000/api/status/services/backend/restart (2 min)
  - [ ] 5.3.2 Verify backend restarts and returns new PID (2 min)
  - [ ] 5.3.3 Test cache clear: curl -X POST http://localhost:8000/api/status/cache/clear (2 min)
  - [ ] 5.3.4 Test UI buttons via browser automation (click restart, verify dialog) (4 min)

---

## PHASE 6: Historical Metrics (2-3 hours)

### Relevant Files (Phase 6)

#### Create (9 files)
- `backend/app/storage/migrations/add_system_status_history.sql` (~30 lines) - History table migration
- `backend/app/tasks/monitoring_tasks.py` (~100 lines) - Background snapshot task
- `frontend/components/status/UptimeChart.tsx` (~120 lines) - Uptime bar chart
- `frontend/components/status/PerformanceTrendChart.tsx` (~100 lines) - Memory line chart
- `frontend/components/status/StatusTimeline.tsx` (~100 lines) - Status change timeline
- `frontend/lib/api/history.ts` (~50 lines) - History API client
- `frontend/lib/hooks/useStatusHistory.ts` (~40 lines) - History query hook
- `tests/tasks/test_monitoring_tasks.py` (~80 lines) - Snapshot task tests
- `tests/api/test_status_history.py` (~100 lines) - History endpoint tests

#### Update (3 files)
- `backend/app/api/status.py` - Add GET /api/status/history endpoint
- `backend/app/celery_app.py` - Add store_status_snapshot to beat schedule
- `frontend/app/status/page.tsx` - Add history/charts section

### Tasks - Phase 6

- [ ] **6.1 Backend: History Table & Migration** (15 min)
  - [ ] 6.1.1 Create backend/app/storage/migrations/add_system_status_history.sql (5 min)
  - [ ] 6.1.2 Run migration: psql portfolio_ai -f migrations/add_system_status_history.sql (2 min)
  - [ ] 6.1.3 Verify table created: psql -c "\d system_status_history" (1 min)
  - [ ] 6.1.4 Add indexes on timestamp and service_name (3 min)
  - [ ] 6.1.5 Write test verifying table schema (4 min)

- [ ] **6.2 Backend: Snapshot Task** (25 min)
  - [ ] 6.2.1 Create backend/app/tasks/monitoring_tasks.py (2 min)
  - [ ] 6.2.2 Write failing test for store_status_snapshot task (3 min)
  - [ ] 6.2.3 Implement store_status_snapshot() Celery task (8 min)
  - [ ] 6.2.4 Add snapshot storage for each service (4 min)
  - [ ] 6.2.5 Add cleanup logic (delete records >30 days) (3 min)
  - [ ] 6.2.6 Write test for cleanup logic (3 min)
  - [ ] 6.2.7 Add to beat schedule (every 5 minutes) in celery_app.py (2 min)

- [ ] **6.3 Backend: History Endpoint** (15 min)
  - [ ] 6.3.1 Create HistoryResponse Pydantic model (3 min)
  - [ ] 6.3.2 Write failing test for GET /api/status/history (3 min)
  - [ ] 6.3.3 Implement GET /api/status/history with query params (service, period, metric) (6 min)
  - [ ] 6.3.4 Add time-series aggregation logic (group by hour/day) (3 min)

- [ ] **6.4 Frontend: Chart Components** (60 min)
  - [ ] 6.4.1 Install chart library: npm install recharts (2 min)
  - [ ] 6.4.2 Create frontend/lib/api/history.ts API client (3 min)
  - [ ] 6.4.3 Create useStatusHistory hook with period selection (5 min)
  - [ ] 6.4.4 Create UptimeChart component with bar chart (15 min)
  - [ ] 6.4.5 Calculate uptime percentage per day (5 min)
  - [ ] 6.4.6 Add period selector (24h/7d/30d) (3 min)
  - [ ] 6.4.7 Create PerformanceTrendChart component with line chart (12 min)
  - [ ] 6.4.8 Show memory usage over time with threshold lines (5 min)
  - [ ] 6.4.9 Create StatusTimeline component (10 min)
  - [ ] 6.4.10 Show major status changes (service stops/starts) (5 min)

- [ ] **6.5 Integration & Testing** (25 min)
  - [ ] 6.5.1 Add history section to status page (3 min)
  - [ ] 6.5.2 Wait 15 minutes for 3 snapshots to be stored (15 min)
  - [ ] 6.5.3 Verify snapshots in database: psql -c "SELECT * FROM system_status_history LIMIT 10" (2 min)
  - [ ] 6.5.4 Test history endpoint: curl 'http://localhost:8000/api/status/history?period=24h' | jq (2 min)
  - [ ] 6.5.5 Verify charts render in UI with test data (3 min)

---

## Combined Verification (MANDATORY before "COMPLETE ✅")

### Phase 4 Verification ✅ COMPLETE
- [x] **Functional**: All Phase 4 requirements met
  - [x] AC-4.1: Disk, memory, CPU usage display with correct percentages
  - [x] AC-4.2: Warning badges show at correct thresholds
  - [x] AC-4.3: Database pool stats show active vs idle connections
  - [x] AC-4.4: Resource cards update every 5 seconds
  - [x] AC-4.5: Critical warnings visible when >90% usage

- [x] **Tests**: pytest tests/services/test_resource_monitor.py -v passes (6/6 tests)
- [x] **Quality**: ~/portfolio-ai/scripts/lint.sh passes (All checks passed!)

### Phase 5 Verification
- [ ] **Functional**: All Phase 5 requirements met
  - [ ] AC-5.1: Restart button restarts services successfully
  - [ ] AC-5.2: Confirmation dialog appears (unless "don't ask again")
  - [ ] AC-5.3: Toast notifications show success/error
  - [ ] AC-5.4: Cache clear removes entries from price_cache
  - [ ] AC-5.5: Manual watchlist refresh triggers task immediately
  - [ ] AC-5.6: Buttons disabled during action execution

- [ ] **Tests**: pytest tests/api/test_service_control.py -v passes
- [ ] **Quality**: ~/portfolio-ai/scripts/lint.sh passes

### Phase 6 Verification
- [ ] **Functional**: All Phase 6 requirements met
  - [ ] AC-6.1: History data stored every 5 minutes
  - [ ] AC-6.2: Uptime chart renders for 24h/7d/30d periods
  - [ ] AC-6.3: Performance trend shows memory usage over time
  - [ ] AC-6.4: Status timeline shows service stop/start events
  - [ ] AC-6.5: Data auto-deleted after 30 days
  - [ ] AC-6.6: Charts render in <2 seconds

- [ ] **Tests**: pytest tests/tasks/test_monitoring_tasks.py -v passes
- [ ] **Quality**: ~/portfolio-ai/scripts/lint.sh passes

---

## Notes

### Phase 4: Resource Thresholds Summary
- **Disk**: OK <80%, Warning 80-90%, Critical >90%
- **Memory**: OK <85%, Warning 85-95%, Critical >95%
- **CPU**: OK <80%, Warning 80-90%, Critical >90%
- **DB Pool**: OK <75%, Warning 75-90%, Critical >90%

### Phase 5: Security Considerations
- Service name whitelist (prevent arbitrary command execution)
- Restart script runs with user permissions (no sudo needed)
- Subprocess timeout (30s max)
- Rate limiting on control endpoints (future enhancement)

### Phase 6: Data Retention
- Snapshots every 5 minutes = 288 per day
- 30 days retention = 8,640 records per service
- 6 services × 8,640 = ~52K records total
- Auto-cleanup prevents unbounded growth

### Phase 6: Chart Libraries
- **Option 1**: Recharts (recommended, React-friendly, lightweight)
- **Option 2**: Chart.js with react-chartjs-2 (more features)
- **Option 3**: Victory (accessible, customizable)

### Phase Implementation Order
1. **Phase 4** (Resource Monitoring) - Independent, high value
2. **Phase 5** (Service Controls) - Depends on UI patterns from Phase 4
3. **Phase 6** (Historical Metrics) - Depends on data from Phases 4+5, takes longest

---

**Status**: Ready for /do_it execution (after Phase 1 complete)
**Priority**: Implement incrementally based on operational needs
**Next**: Run `/do_it tasks-0031-status-dashboard-phases4-6.md` after completing desired phases
