# Status Page Consolidation - Testing & Verification Handoff

**Branch**: `claude/consolidate-status-page-011CUycnZBzcMgMGe8VvzRaP`
**Commit**: `d313d57` - "feat(status): consolidate status page with improved UX"
**Status**: Code complete, needs testing with live services
**Created**: 2025-11-10

## 📋 Overview

Consolidated the status page to reduce scrolling while maintaining all functionality:
- **New**: Unified LogsCard with filtering/sorting for all service logs
- **Updated**: DataSourcesCard now has collapsible healthy/unhealthy sections
- **Simplified**: ServiceCard no longer has individual log viewers
- **Result**: Same data, better organization, less scrolling

## ✅ Completed Work

### 1. Created LogsCard Component
**File**: `frontend/components/status/LogsCard.tsx`

**Features**:
- Aggregates logs from all services (backend, celery_worker, celery_beat, frontend, redis)
- Filter by service (ALL, backend, celery_worker, celery_beat, frontend, redis)
- Filter by log level (ALL, ERROR, WARN, INFO, DEBUG)
- Sort by service, level, or timestamp (click headers to toggle asc/desc)
- Expandable rows to view full log entry
- Auto-parsing of log levels and timestamps
- Live count badges (filtered/total, level distribution)

**Implementation Notes**:
- Uses `useServiceLogs` hook for each service
- Parses log lines to extract level (ERROR, WARN, INFO, DEBUG) and timestamp
- Supports common timestamp formats (ISO8601, bracketed)
- Color-coded level badges (red=ERROR, yellow=WARN, blue=INFO, gray=DEBUG)

### 2. Refactored DataSourcesCard
**File**: `frontend/components/status/DataSourcesCard.tsx`

**Changes**:
- Split sources into "Unhealthy" and "Healthy" collapsible sections
- Unhealthy section: expanded by default (priority visibility)
- Healthy section: collapsed by default (reduces clutter)
- Same source details preserved (success rate, latency, cooldowns, rate limits)

### 3. Simplified ServiceCard
**File**: `frontend/components/status/ServiceCard.tsx`

**Changes**:
- Removed `showLogs` prop and individual log viewer
- Removed imports: `useState`, `ChevronDown`, `ChevronRight`, `Collapsible*`, `useServiceLogs`, `LogViewer`
- Cleaner UI: just PID, uptime, memory, status message, restart button

### 4. Updated Status Page
**File**: `frontend/app/status/page.tsx`

**Changes**:
- Added `LogsCard` import
- Removed `showLogs={true}` prop from ServiceCard instances
- Inserted `<LogsCard />` after service cards grid (before System Resources section)

## 🧪 Testing Checklist

### Prerequisites
- [ ] Services are running (`bash ~/portfolio-ai/scripts/start.sh`)
- [ ] Verify all 5 services active (`bash ~/portfolio-ai/scripts/status.sh`)
- [ ] Frontend accessible at http://192.168.8.233:3000

### Test 1: LogsCard Functionality
Navigate to http://192.168.8.233:3000/status

- [ ] **Initial Load**: LogsCard appears below service cards
- [ ] **Data Loading**: Shows logs from all services (backend, celery_worker, celery_beat, frontend, redis)
- [ ] **Badge Counts**: "X / Y logs" badge shows correct totals
- [ ] **Service Filter**:
  - [ ] Change dropdown to "Backend" → only backend logs shown
  - [ ] Change to "Celery Worker" → only celery_worker logs shown
  - [ ] Change back to "All Services" → all logs shown
- [ ] **Level Filter**:
  - [ ] Change to "Error (N)" → only ERROR logs shown
  - [ ] Change to "Warning (N)" → only WARN logs shown
  - [ ] Change to "Info (N)" → only INFO logs shown
  - [ ] Level counts in dropdown match actual log counts
- [ ] **Sorting**:
  - [ ] Click "Service" header → logs sort by service (A→Z)
  - [ ] Click "Service" again → logs sort reverse (Z→A)
  - [ ] Click "Level" header → logs sort by level
  - [ ] Click "Timestamp" header → logs sort by time
  - [ ] Chevron icon shows sort direction
- [ ] **Row Expansion**:
  - [ ] Click chevron on any row → full log line appears below
  - [ ] Click chevron again → log collapses
  - [ ] Dark code block shows full, untruncated log line
- [ ] **Level Icons**: Correct icons/colors (ERROR=red alert, WARN=yellow triangle, INFO=blue info, DEBUG=gray bug)
- [ ] **Combined Filters**: Filter by service="Backend" + level="ERROR" → shows only backend errors

### Test 2: DataSourcesCard Collapsibility
Navigate to http://192.168.8.233:3000/status

- [ ] **Initial State**:
  - [ ] "Unhealthy Data Sources" section exists if any sources are unhealthy
  - [ ] Unhealthy section is expanded by default
  - [ ] "Healthy Data Sources" section exists
  - [ ] Healthy section is collapsed by default
  - [ ] Badge shows "N/M Healthy" correctly
- [ ] **Unhealthy Section**:
  - [ ] Click button to collapse → sources hide
  - [ ] Click button to expand → sources show again
  - [ ] Chevron icon rotates correctly
  - [ ] Badge shows count
- [ ] **Healthy Section**:
  - [ ] Click button to expand → healthy sources show
  - [ ] Each source shows: status icon, name, last success, success rate, avg latency
  - [ ] Click to collapse → sources hide
- [ ] **Source Details**: All original fields still present (success_rate, avg_latency_ms, cooldowns, rate_limit_hits)

### Test 3: ServiceCard Simplification
Navigate to http://192.168.8.233:3000/status

For each service card (backend, celery_worker, celery_beat, frontend, redis):
- [ ] **No Log Viewer**: "Show Logs" button is NOT present
- [ ] **Metrics Shown**: PID, Uptime, Memory displayed correctly
- [ ] **Status Badge**: Shows "running", "degraded", or "down" with correct color
- [ ] **Status Icon**: Green checkmark (running), yellow alert (degraded), red alert (down)
- [ ] **Restart Button**: Hover shows "Restart [service]"
- [ ] **Status Message**: Shows if service has a message (border-left yellow)

### Test 4: Integration & Layout
- [ ] **Page Layout**:
  - [ ] System Status card at top
  - [ ] News Health card
  - [ ] Data Sources card (collapsible sections)
  - [ ] API Quotas card
  - [ ] Service cards grid (3 columns on large screens)
  - [ ] **LogsCard appears here** (new section)
  - [ ] System Resources section
  - [ ] Celery Monitoring section
- [ ] **Scrolling**: Less vertical scrolling required compared to before
- [ ] **Responsive**: Check on smaller screen (md/lg breakpoints) - grid adjusts correctly
- [ ] **No Console Errors**: Browser console shows no React errors or warnings

### Test 5: Log Parsing Edge Cases
Manually check logs to verify parsing works correctly:

- [ ] **ERROR logs**: Correctly identified and badged
- [ ] **WARN logs**: Correctly identified and badged
- [ ] **INFO logs**: Correctly identified and badged
- [ ] **Timestamp extraction**: Timestamps appear in "Timestamp" column
- [ ] **Logs without timestamps**: Show "—" in timestamp column
- [ ] **Logs without recognized level**: Badged as "UNKNOWN" (gray)

### Test 6: Performance
- [ ] **Initial Load**: Page loads in reasonable time (<3s)
- [ ] **Log Fetching**: All service logs load within 5s
- [ ] **Filtering**: Filter changes are instant (<100ms)
- [ ] **Sorting**: Sort changes are instant (<100ms)
- [ ] **No Memory Leaks**: Leave page open for 5 minutes, check browser memory doesn't grow excessively

### Test 7: Error Handling
Test how the UI handles service failures:

- [ ] **Service Down**: Stop backend (`sudo systemctl stop portfolio-backend`)
  - [ ] ServiceCard shows "down" status
  - [ ] LogsCard shows error or empty state for that service
  - [ ] Other services' logs still load
- [ ] **Missing Log File**:
  - [ ] Check LogsCard behavior when log file doesn't exist
  - [ ] Should show error state, not crash
- [ ] **Restart Service**: Verify logs start flowing again after restart

## 🐛 Known Issues / Edge Cases to Verify

1. **Log File Permissions**:
   - Verify LogsCard can read all log files in `/tmp/` and `/var/log/redis/`
   - Check for 403/404 errors in Network tab

2. **Log Parsing Accuracy**:
   - Some logs may not have timestamps → verify "—" displays correctly
   - Some logs may not match ERROR/WARN/INFO patterns → verify "UNKNOWN" badge works

3. **Empty States**:
   - No logs available: Should show "No logs available" message
   - No logs match filter: Should show "No logs match the selected filters"

4. **TypeScript Errors**:
   - Current environment couldn't run full TS check (missing node_modules)
   - Local dev should run: `cd frontend && npx tsc --noEmit` to verify no type errors

5. **Performance with Large Logs**:
   - Currently fetches last 100 lines per service (500 total max)
   - If services have been running for days, test with large log files

## 🔧 Verification Commands

```bash
# 1. Start all services
bash ~/portfolio-ai/scripts/start.sh

# 2. Verify services are running
bash ~/portfolio-ai/scripts/status.sh
# Expected: All 5 services should show green checkmarks

# 3. Check service logs are being written
tail -f /tmp/portfolio-backend.log       # Should show live backend logs
tail -f /tmp/portfolio-celery-worker.log # Should show celery worker logs
tail -f /tmp/portfolio-celery-beat.log   # Should show beat scheduler logs
tail -f /tmp/portfolio-frontend.log      # Should show Next.js logs
tail -f /var/log/redis/redis-server.log  # Should show Redis logs

# 4. TypeScript check (if node_modules installed)
cd ~/portfolio-ai/frontend
npx tsc --noEmit

# 5. Frontend linting (if node_modules installed)
cd ~/portfolio-ai/frontend
npx eslint components/status/LogsCard.tsx --max-warnings=0
npx eslint components/status/DataSourcesCard.tsx --max-warnings=0
npx eslint components/status/ServiceCard.tsx --max-warnings=0
npx eslint app/status/page.tsx --max-warnings=0

# 6. Check backend is accessible
curl http://192.168.8.233:8000/health
# Expected: {"status":"healthy",...}

# 7. Check frontend is accessible
curl http://192.168.8.233:3000
# Expected: HTML response

# 8. Test log endpoint directly
curl http://192.168.8.233:8000/api/status/logs/backend?lines=10
# Expected: {"service":"backend","lines":[...],"total_lines":10,...}
```

## 📊 Acceptance Criteria

**This task is complete when**:

✅ All testing checklist items pass
✅ No TypeScript errors in modified files
✅ No console errors when using LogsCard
✅ Logs from all 5 services appear correctly
✅ Filtering and sorting work as expected
✅ DataSourcesCard collapsible sections work correctly
✅ ServiceCards no longer have individual log viewers
✅ Page loads and performs well
✅ Error states handle gracefully

## 🚀 Next Steps After Testing

If testing passes:
1. ✅ Mark this task complete
2. ✅ Update WORK_TRACKER.md if needed
3. ✅ Consider creating PR for review (if applicable)
4. ✅ Document any bugs found in GitHub issues

If testing fails:
1. 📝 Document specific failures in new task file
2. 📝 Include error messages, screenshots, or logs
3. 📝 Assign back to appropriate agent for fixes

## 📁 Files Changed

```
frontend/components/status/LogsCard.tsx          (new)     +433 lines
frontend/components/status/ServiceCard.tsx       (modified) -30 lines
frontend/components/status/DataSourcesCard.tsx   (modified) +52 lines
frontend/app/status/page.tsx                     (modified) +4 lines
```

**Total**: +587 insertions, -86 deletions

## 🔗 Related Documentation

- Backend logs endpoint: `backend/app/api/status.py:89` (`/api/status/logs/{service}`)
- Log file paths: `backend/app/api/status.py:30` (LOG_PATHS dict)
- Service monitoring: `docs/core/OPERATIONS.md`
- Status page design: Original issue/request from user

## 💡 Testing Tips

1. **Use browser DevTools**: Network tab shows log API calls
2. **Check React DevTools**: Verify component state updates correctly
3. **Test with real load**: Trigger celery tasks to generate logs
4. **Compare before/after**: Check old screenshots if available
5. **Mobile testing**: Verify responsive design on mobile breakpoints

---

**Assignee**: Local Dev Agent
**Priority**: Medium
**Estimated Testing Time**: 30-45 minutes
**Last Updated**: 2025-11-10
