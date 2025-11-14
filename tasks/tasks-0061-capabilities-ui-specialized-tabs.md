# Task List: System Capabilities UI - Specialized Tabs Refactor

**Source**: User request via /task_it
**Complexity**: Complex
**Effort**: HIGH (6-8 hours)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-13 21:45

---

## Summary

**Goal**: Replace the unified "All" tab approach with specialized, optimized tabs for each capability type (Database, Tasks, Endpoints). Add a Dashboard/Overview tab for system-wide health summary. Each tab gets type-specific tables, columns, filters, and visualizations optimized for that data type's unique structure.

**Approach**: Remove lowest-common-denominator table structure. Create dedicated components for each capability type with appropriate visualizations (completeness bars, success rate charts, HTTP method badges). Refactor modals to be type-specific. Add Dashboard tab with health summary cards.

**Scope Discovery**: Required (find all affected frontend components)

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run Explore subagent in "very thorough" mode
  - Pattern: All frontend components related to capabilities (tables, tabs, modals, API clients)
  - Goal: Find ALL components that need refactoring or creation
  - Search: `frontend/app/capabilities/`, `frontend/components/capabilities/`, `frontend/lib/api/capabilities.ts`
  - Output: Complete list of existing components + identify what needs to be created
- [ ] 0.2 Update this task list with component-specific tasks
  - List all components to modify
  - List all new components to create
  - Estimate effort per component
- [ ] 0.3 Checkpoint: Confirm scope before proceeding
  - Total components affected: [TBD]
  - New components needed: [TBD]
  - Estimated effort: [TBD]
  - Design decisions needed: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

---

### 1.0 Design Dashboard/Overview Tab

- [ ] 1.1 Create health summary card components
  - Database health card (total tables, % current, % stale, % unknown)
  - Tasks health card (total tasks, avg success rate, failures last 7d)
  - Endpoints health card (total endpoints, categories breakdown)
- [ ] 1.2 Add quick actions section
  - Scan Now button (triggers manual scan)
  - View Recent Insights link
  - System-wide search input
- [ ] 1.3 Create overview statistics component
  - Recent scan timestamp
  - Next scheduled scan countdown
  - Total capabilities count
- [ ] 1.4 Implement responsive grid layout for dashboard

### 2.0 Create Specialized Database Table Component

- [ ] 2.1 Design DatabaseCapabilitiesTable component
  - Columns: Table Name | Category | Rows | Completeness | Freshness | Age | Actions
  - Remove generic "Source/Schedule" column
  - Add completeness as visual progress bar (0-100%)
- [ ] 2.2 Implement freshness color coding
  - Current: green badge
  - Acceptable: yellow badge
  - Stale: orange badge
  - Critical: red badge
  - Unknown: gray badge with question mark
- [ ] 2.3 Add age formatting helper
  - Convert `age_hours` to human format: "2h", "3d", "1w", "2mo"
  - Show "—" for null/unknown
- [ ] 2.4 Create database-specific filters
  - Filter by category (Infrastructure, Analytics, Market Data, etc.)
  - Filter by freshness status
  - Filter by completeness range (0-25%, 25-50%, 50-75%, 75-100%)
- [ ] 2.5 Implement database-specific sorting
  - Sort by staleness (days since update)
  - Sort by completeness percentage
  - Sort by row count

### 3.0 Create Specialized Tasks Table Component

- [ ] 3.1 Design TasksCapabilitiesTable component
  - Columns: Task Name | Schedule | Last Run | Success Rate | Avg Duration | Actions
  - Remove generic columns not relevant to tasks
- [ ] 3.2 Implement schedule display
  - Show human-readable schedule ("Every 1 minutes", "Daily at 03:00 UTC")
  - Show crontab on hover tooltip
  - Visual indicator for frequency (high-frequency tasks get badge)
- [ ] 3.3 Add success rate visualization
  - Circular progress or pie chart badge (0-100%)
  - Color coding: >95% green, 90-95% yellow, <90% red
  - Show success/failure counts on hover
- [ ] 3.4 Format duration display
  - Show average duration in human format (ms, s, m)
  - Show max duration on hover
- [ ] 3.5 Create task-specific filters
  - Filter by schedule frequency (high/medium/low)
  - Filter by success rate threshold (>99%, >95%, >90%, <90%)
  - Filter by category
- [ ] 3.6 Implement task-specific sorting
  - Sort by last run (most recent first)
  - Sort by success rate (lowest first to highlight issues)
  - Sort by execution frequency

### 4.0 Create Specialized Endpoints Table Component

- [ ] 4.1 Design EndpointsCapabilitiesTable component
  - Columns: Path | Method | Category | Dependencies | Performance | Actions
  - Remove non-relevant columns
- [ ] 4.2 Implement HTTP method badges
  - Color-coded badges: GET=blue, POST=green, PUT=orange, DELETE=red
  - Icon per method type
- [ ] 4.3 Create dependency chips display
  - Show depends_on_tables as clickable chips
  - Click chip → navigate to that table in Database tab
  - Truncate long lists with "+N more" expandable
- [ ] 4.4 Add performance metrics placeholders
  - Show "—" for null metrics (Phase 2 not implemented)
  - Design structure for future: Avg Response Time | P95 | P99
- [ ] 4.5 Create endpoint-specific filters
  - Filter by HTTP method
  - Filter by category
  - Filter by has dependencies (yes/no)
- [ ] 4.6 Implement endpoint-specific sorting
  - Sort by path (alphabetical)
  - Sort by method
  - Sort by category

### 5.0 Refactor Tab Navigation

- [ ] 5.1 Update tab order and structure
  - New order: Dashboard | Database (42) | Tasks (13) | Endpoints (16) | Insights | Gaps
  - Remove "All (71)" tab completely
  - Update tab component to handle new structure
- [ ] 5.2 Implement tab-specific routing
  - URL routes: `/capabilities` (dashboard), `/capabilities?tab=database`, etc.
  - Persist selected tab in URL
  - Deep linking support
- [ ] 5.3 Add tab badges with counts
  - Show dynamic counts from API
  - Update counts after scan completes
- [ ] 5.4 Create tab-specific loading states
  - Different skeleton loaders per tab type
  - Show appropriate placeholders

### 6.0 Create Type-Specific Detail Modals

- [ ] 6.1 Create DatabaseDetailModal component
  - Overview tab: Show all DB-specific fields (row_count, completeness_pct, columns list, date_range)
  - Columns tab: List columns_with_data (✅) vs columns_mostly_null (❌)
  - History tab: Show update history, freshness timeline
  - Insights/Notes tabs: Keep existing structure
- [ ] 6.2 Create TaskDetailModal component
  - Overview tab: Schedule details, execution stats, populated tables
  - Execution History tab: Last 20 runs with status, duration, timestamps
  - Dependencies tab: Show populates_tables, depends_on_tasks
  - Insights/Notes tabs: Keep existing structure
- [ ] 6.3 Create EndpointDetailModal component
  - Overview tab: Full path, method, category, route file, function name
  - Dependencies tab: Show depends_on_tables with links
  - Usage tab: Placeholder for future performance metrics
  - Insights/Notes tabs: Keep existing structure
- [ ] 6.4 Remove generic CapabilityDetailModal
  - Migrate any shared logic to utils
  - Each type now has its own optimized modal

### 7.0 Update API Client and Data Fetching

- [ ] 7.1 Refactor API hooks for type-specific queries
  - Update `useCapabilities` hook to handle type filtering
  - Create `useDatabaseCapabilities`, `useTaskCapabilities`, `useEndpointCapabilities` hooks
  - Optimize data fetching (don't fetch all types if viewing one tab)
- [ ] 7.2 Add dashboard summary API call
  - New endpoint or aggregate existing data
  - Fetch health metrics for summary cards
- [ ] 7.3 Update TypeScript interfaces
  - Create specific types: `DatabaseCapability`, `TaskCapability`, `EndpointCapability`
  - Remove overly generic `Capability` union type
  - Ensure type safety for each specialized component

### 8.0 Add Visualizations and Polish

- [ ] 8.1 Create completeness progress bar component
  - Reusable visual bar (0-100%)
  - Color gradient: red → yellow → green
  - Show percentage text overlay
- [ ] 8.2 Create success rate circular chart
  - Small circular progress indicator
  - Color coding based on threshold
  - Tooltip with details
- [ ] 8.3 Add category icons/emojis
  - Infrastructure: ⚙️
  - Analytics: 📊
  - Market Data: 💰
  - Portfolio: 📈
  - News: 📰
- [ ] 8.4 Implement responsive design
  - Mobile: Stack cards vertically
  - Tablet: 2-column grid
  - Desktop: 3-column grid

### 9.0 Update Search and Filtering

- [ ] 9.1 Create tab-specific search logic
  - Database tab: Search table names, categories
  - Tasks tab: Search task names, schedules
  - Endpoints tab: Search paths, methods
- [ ] 9.2 Implement filter persistence
  - Store active filters in URL params
  - Restore filters on page reload
- [ ] 9.3 Add filter reset button
  - Clear all active filters
  - Reset to default view

### 10.0 Testing and Verification

- [ ] 10.1 Test Dashboard tab
  - Verify health cards show correct data
  - Test quick actions (Scan Now button)
  - Verify responsive layout
- [ ] 10.2 Test Database tab
  - Verify completeness bars render correctly
  - Test freshness color coding
  - Verify age formatting (hours → days → weeks)
  - Test filters and sorting
- [ ] 10.3 Test Tasks tab
  - Verify schedule display
  - Test success rate visualization
  - Verify duration formatting
  - Test filters and sorting
- [ ] 10.4 Test Endpoints tab
  - Verify HTTP method badges
  - Test dependency chips (click navigation)
  - Verify filters and sorting
- [ ] 10.5 Test detail modals
  - Verify type-specific modals open correctly
  - Test all tabs within each modal
  - Verify data displays correctly
- [ ] 10.6 Test navigation and routing
  - Verify tab switching works
  - Test deep linking (URL params)
  - Verify browser back/forward
- [ ] 10.7 Run frontend tests
  - Component tests for new components
  - Integration tests for tab switching
  - Accessibility tests (a11y)

### 11.0 Documentation and Cleanup

- [ ] 11.1 Update component documentation
  - Add JSDoc comments to new components
  - Document props and behavior
- [ ] 11.2 Remove old unified table code
  - Delete CapabilitiesTable.tsx if fully replaced
  - Clean up unused utility functions
  - Remove obsolete type definitions
- [ ] 11.3 Update user documentation
  - Update docs/reference/system-capabilities-registry.md
  - Add screenshots of new UI
  - Document how to use each tab
- [ ] 11.4 Add code comments for future enhancements
  - Mark performance metrics placeholders
  - Note where AI insights integration will go
  - Document extension points for new capability types

---

## Verification

- [ ] Functional: All 6 tabs working (Dashboard, Database, Tasks, Endpoints, Insights, Gaps)
- [ ] UI: Each tab shows type-appropriate columns and visualizations
- [ ] Data: All 71 capabilities display correctly in their respective tabs
- [ ] Filters: Type-specific filters work correctly on each tab
- [ ] Modals: Type-specific detail modals open and display all data
- [ ] Navigation: Tab switching, URL routing, deep linking all work
- [ ] Responsive: UI works on mobile, tablet, desktop
- [ ] Tests: Frontend tests passing (npm test)
- [ ] Quality: ESLint/TypeScript checks pass
- [ ] Clean: No console errors or warnings
- [ ] Docs: Updated with new UI structure and screenshots
