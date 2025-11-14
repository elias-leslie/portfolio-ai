# Task List: System Capabilities UI - Specialized Tabs Refactor

**Source**: User request via /task_it
**Complexity**: Medium (simplified from original)
**Effort**: MEDIUM (10-12 hours, reduced from 30-40h)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-13 21:45
**Revised**: 2025-11-13 23:30 (simplified approach)

---

## Summary

**Goal**: Improve capabilities UI by removing modal popups, adding expandable inline details, and showing maximum data in collapsed rows. Add Dashboard tab for health summary. Automate orphan/health detection with backend scripts (no complex UI).

**Approach**:
- Keep existing unified table (don't build 3 specialized tables)
- Remove 545-line modal, replace with expandable accordion rows
- Pack maximum data into main row (~10 columns, no expansion needed for quick scan)
- Add simple Dashboard tab with summary cards
- Backend: Add health_status field + automated health reporting script
- Focus on data density and quick scanning, not fancy visualizations

**Scope Discovery**: Required (find all affected frontend components)

---

## Tasks

### 0.0 Scope Discovery (COMPLETE)

- [x] 0.1 Run Explore subagent ✅
- [x] 0.2 Analyze findings and simplify approach ✅
- [x] 0.3 Finalized plan ✅

**Simplified Scope:**
- Files to modify: 3 (page.tsx, CapabilitiesTable.tsx, capabilities.ts)
- Files to delete: 1 (CapabilityDetailModal.tsx - 545L)
- New files: 1 (CapabilitiesDashboard.tsx - simple summary cards)
- Backend: Add health_status field + health report script
- Total effort: 10-12 hours (vs original 30-40h)

---

### 1.0 Backend - Health Detection (3-4 hours) ✅ COMPLETE

- [x] 1.1 Add health_status calculation to capability_scanner.py ✅
  - Detect orphaned (no readers/writers, low row count)
  - Detect legacy (stale >30d, 0 rows, not scheduled)
  - Detect suspect (depends on orphaned, low success rate)
  - Default: active
- [x] 1.2 Add health_status field to database scan results ✅
  - Update save_capabilities() to store health_status
  - Add health_status to db_capabilities table (migration 039 applied)
- [x] 1.3 Create health report automation script ✅
  - Script: backend/scripts/health_report.py
  - Output: logs + JSON file with orphan/legacy counts
  - Schedule: runs after capabilities scan (03:15 UTC)
- [x] 1.4 Add health filter to capabilities API ✅
  - Support: GET /api/capabilities?health_status=orphaned
  - Add health summary endpoint: GET /api/capabilities/health/summary

### 2.0 Frontend - Remove Modal, Add Expandable Rows (3-4 hours) ✅ COMPLETE

- [x] 2.1 Delete CapabilityDetailModal.tsx (545L) ✅
  - Remove file completely
  - Remove imports from page.tsx
- [x] 2.2 Update CapabilitiesTable.tsx - add accordion rows ✅
  - Keep existing unified table structure (don't split into 3 tables)
  - Add expandable row state (track which rows are expanded)
  - Add click handler to toggle row expansion
  - Design: Row click or ▶ arrow toggles expand/collapse
- [x] 2.3 Design expanded row content sections ✅
  - All: Overview (metadata), Insights (inline list), Notes (inline list + add form)
  - Database: + Columns section (list with data vs null), Dependencies (who populates/reads)
  - Tasks: + Execution History (last 10 runs), Schedule details, Dependencies
  - Endpoints: + Full path, Dependencies (tables + freshness status)
- [x] 2.4 Implement inline notes functionality ✅
  - Simple textarea + Type dropdown (Info/Warning/Critical) + Save/Cancel
  - Show existing notes in expanded row
  - Edit/Delete buttons for existing notes
- [x] 2.5 Add visual indicators for expandable rows ✅
  - ▶ arrow (collapsed) / ▼ arrow (expanded)
  - Subtle hover effect on row
  - Expanded row has distinct background color

### 3.0 Frontend - Maximize Data in Main Row (2-3 hours) ✅ COMPLETE

- [x] 3.1 Update table columns for maximum data density ✅
  - **Database tables** (11 cols): Icon | Name | Category | Rows | Health | Freshness | Age | Insights | Notes | Updated | Actions
  - **Tasks** (11 cols): Icon | Name | Category | Schedule | Last Run | Success % | Health | Duration | Insights | Notes | Actions
  - **Endpoints** (10 cols): Icon | Path | Method | Category | Deps | Health | Insights | Notes | File | Actions
  - Use compact formatting, abbreviations where needed
- [x] 3.2 Add health status column with color coding ✅
  - Active: green text/badge
  - Suspect: yellow text/badge
  - Orphaned: red text/badge
  - Legacy: gray text/badge (strikethrough)
- [x] 3.3 Format columns for readability ✅
  - Rows: Show "1.2k", "45k" (abbreviated)
  - Age: Show "2h", "3d", "1w" (compact)
  - Success %: Show "95%" with color (green >95%, yellow >90%, red <90%)
  - Schedule: Show "Every 5m", "Daily 06:00" (compact)
  - Duration: Show "1.2s", "450ms" (compact)
- [x] 3.4 Add tooltips for truncated data ✅
  - Hover over compact values to see full details
  - Hover over health status to see why (orphan reason, etc.)

### 4.0 Frontend - Dashboard Tab (2-3 hours)

- [ ] 4.1 Create CapabilitiesDashboard.tsx component
  - Simple summary cards layout (3-column grid)
  - Keep minimal - just numbers and health distribution
- [ ] 4.2 Add health summary cards
  - Database card: Total, Active, Orphaned, Legacy counts
  - Tasks card: Total, Active, Orphaned, Avg success rate
  - Endpoints card: Total, Active, Orphaned
- [ ] 4.3 Add recent insights section
  - Show top 5-10 insights (critical/warning only)
  - Simple list with severity badge + message
  - Click insight → navigate to relevant tab + expand that row
- [ ] 4.4 Add quick actions
  - "Scan Now" button (trigger manual scan)
  - Last scan timestamp
  - Next scan countdown (if scheduled)
- [ ] 4.5 Update page.tsx to use Dashboard as default tab
  - Replace "All" tab with "Dashboard" tab
  - Keep: Dashboard | Database | Tasks | Endpoints | Insights | Gaps

### 5.0 Frontend - Health Filtering & Polish (1-2 hours)

- [ ] 5.1 Add health filter dropdown
  - Filter: All | Active Only | Orphaned Only | Legacy Only | Suspect Only
  - Apply to current tab's table view
  - Persist filter in URL params
- [ ] 5.2 Add visual polish for health status
  - Color-code entire row based on health (subtle background tint)
  - Orphaned/Legacy rows slightly dimmed (lower opacity?)
  - Active rows normal, Suspect rows yellow tint
- [ ] 5.3 Update existing filters to work with health
  - Combine category filter + health filter
  - Show result counts: "Showing 5 orphaned tables (5 total)"
- [ ] 5.4 Add sort by health status
  - Priority order: Orphaned > Legacy > Suspect > Active
  - Allow sorting by any column including health

### 6.0 Testing and Verification (1-2 hours)

- [ ] 6.1 Test expandable rows
  - Click to expand/collapse works
  - All type-specific sections render correctly
  - Inline notes add/edit/delete works
- [ ] 6.2 Test Dashboard tab
  - Summary cards show correct counts
  - Health distribution accurate
  - Recent insights link to correct rows
- [ ] 6.3 Test health filtering
  - Health filter dropdown works on all tabs
  - Correct results for each health status
  - URL params persist filters
- [ ] 6.4 Test data density
  - All 9-10 columns visible without horizontal scroll (1920px width)
  - Compact formatting readable
  - Tooltips show full details
- [ ] 6.5 Run automated tests
  - Frontend component tests (npm test)
  - TypeScript checks (no errors)
  - ESLint (no warnings)

### 7.0 Documentation (30min - 1hr)

- [ ] 7.1 Update docs/reference/system-capabilities-registry.md
  - Document new expandable row UI
  - Document health status meanings
  - Document inline notes workflow
  - Add screenshots of Dashboard + expandable rows
- [ ] 7.2 Add code comments
  - JSDoc for health_status calculation logic
  - Comment health detection edge cases
  - Note future enhancements (performance metrics, etc.)

---

## Verification

- [ ] Backend: health_status field in scanner output and API responses
- [ ] Backend: Health filter works (`?health_status=orphaned`)
- [ ] Backend: Health summary endpoint returns correct counts
- [ ] Backend: Health report script runs and outputs logs/JSON
- [ ] Frontend: NO MORE MODAL - deleted CapabilityDetailModal.tsx
- [ ] Frontend: Expandable rows work (click to expand, shows all details inline)
- [ ] Frontend: Maximum data in main row (9-10 columns, readable without scrolling)
- [ ] Frontend: Inline notes work (add/edit/delete in expanded row)
- [ ] Frontend: Dashboard tab shows summary cards + recent insights
- [ ] Frontend: Health filter dropdown works on all tabs
- [ ] Frontend: Health color coding visible (green/yellow/red rows)
- [ ] Tests: All frontend tests passing (npm test)
- [ ] Tests: TypeScript + ESLint clean
- [ ] Docs: Updated with screenshots and health status documentation
