<!-- PAUSED: 2025-11-22 13:42 | Context: 85% | Reason: Context limit | Next: Task 2.3 - Register router in main.py -->

# Task List: Customizable Dashboard Layouts

**Source**: User request - Add drag-and-drop card repositioning/resizing
**Complexity**: COMPLEX
**Effort**: MEDIUM-HIGH (6-10 hours)
**Environment**: Local Dev
**Created**: 2025-11-11 01:00
**Status**: PAUSED (2025-11-22 13:42)
**Pause Reason**: Context 85% (approaching threshold)
**Completion**: 2/10 tasks (20%)
**Next Action**: Task 2.3 - Register layouts router in backend/app/main.py
**Resume Command**: `/do_it tasks-0042-customizable-dashboard-layouts.md` or just `/do_it`

---

## Summary

**Goal**: Enable users to customize dashboard layouts by dragging/resizing cards, with persistence to PostgreSQL backend

**Approach**:
- Use `react-grid-layout` for drag/drop/resize functionality
- Backend API + PostgreSQL for layout persistence (NOT local storage)
- System-wide layouts (one layout per page, no user_id)
- Start with Status page, extend to all pages via generic wrapper
- Support responsive breakpoints (desktop, tablet, mobile)
- Include lock/unlock toggle, visual feedback, reset to default

**Key Decisions** (from user):
- ✅ System-wide layouts (no user table needed)
- ✅ All pages should support customization
- ✅ Include "Reset to Default" button
- ✅ Database persistence (not local storage)

---

## Tasks

### 1.0 Database Schema and Migration ✅ COMPLETE

- [x] 1.1 Create database migration for `page_layouts` table (migrations/013_page_layouts.sql)
- [ ] 1.2 Create SQLAlchemy model `PageLayout` - NOT NEEDED (using storage.execute directly)
- [x] 1.3 Run migration and verify table created ✅

### 2.0 Backend API Endpoints ✅ COMPLETE

- [x] 2.1 Create `backend/app/api/layouts.py` with FastAPI router (GET/PUT/DELETE endpoints)
- [x] 2.2 Add Pydantic models (LayoutConfig, LayoutResponse)
- [ ] 2.3 Register router in `backend/app/main.py` - TODO next session
- [x] 2.4 Add error handling (404, 500 errors)
- [ ] 2.5 Test endpoints manually with curl - TODO next session

### 3.0 Frontend Library Integration

- [ ] 3.1 Install react-grid-layout dependencies
  - `npm install react-grid-layout @types/react-grid-layout`
  - Already done ✅
- [ ] 3.2 Create reusable `GridLayoutWrapper` component
  - Path: `frontend/components/layout/GridLayoutWrapper.tsx`
  - Props: `pageName`, `children`, `defaultLayout`
  - Dynamically load `react-grid-layout` (SSR compatibility)
- [ ] 3.3 Add grid layout styles
  - Import CSS: `react-grid-layout/css/styles.css`
  - Import CSS: `react-resizable/css/styles.css`
  - Add custom styles for lock/unlock states

### 4.0 Layout State Management and Persistence

- [ ] 4.1 Create custom hook `useGridLayout`
  - Path: `frontend/lib/hooks/useGridLayout.ts`
  - Manages: isLocked state, current layout, default layout
  - Fetches layout from backend on mount
  - Provides: saveLayout, resetLayout, toggleLock functions
- [ ] 4.2 Implement layout persistence functions
  - `saveLayout()` - PUT to `/api/layouts/{page}`
  - `resetLayout()` - DELETE from `/api/layouts/{page}`, revert to default
  - `loadLayout()` - GET from `/api/layouts/{page}`, fallback to default
- [ ] 4.3 Add optimistic updates with SWR
  - Cache layout locally for performance
  - Revalidate on focus/reconnect
  - Handle errors gracefully

### 5.0 Lock/Unlock UI and Visual Feedback

- [ ] 5.1 Add lock/unlock toggle button
  - Icon: Lock (locked) / Unlock (unlocked)
  - Position: Top-right of page header (near other action buttons)
  - Tooltip: "Unlock to customize layout" / "Lock to save layout"
- [ ] 5.2 Implement visual feedback when unlocked
  - Grid overlay (dashed lines showing grid cells)
  - Resize handles on card corners/edges
  - Cursor changes (grab/grabbing)
  - Card hover effects
- [ ] 5.3 Add "Reset to Default" button
  - Only visible when unlocked
  - Confirmation dialog before reset
  - Position: Next to lock/unlock button

### 6.0 Responsive Breakpoints

- [ ] 6.1 Define responsive breakpoints in GridLayoutWrapper
  - lg: 1200px (12 columns)
  - md: 996px (8 columns)
  - sm: 768px (4 columns)
  - xs: 480px (2 columns, auto-stack)
- [ ] 6.2 Create default layouts for each breakpoint
  - Desktop (lg): Custom multi-column layouts
  - Mobile (xs/sm): Auto-stack vertically
  - Tablet (md): Hybrid approach
- [ ] 6.3 Test layout adaptation across breakpoints
  - Verify cards resize/reflow correctly
  - Ensure no overlaps or gaps

### 7.0 Status Page Integration (POC)

- [ ] 7.1 Define card IDs for Status page
  - "system-status", "news-health", "data-sources", "api-quotas"
  - "unified-logs", "service-cards", "system-resources", "celery-monitoring"
- [ ] 7.2 Create default layout configuration
  - Define x, y, w, h for each card
  - Set min/max constraints (minW, maxW, minH, maxH)
- [ ] 7.3 Wrap Status page with GridLayoutWrapper
  - Replace static layout with grid layout
  - Pass pageName="status"
  - Pass default layout config
- [ ] 7.4 Test drag, resize, save, reset on Status page
  - Verify persistence to database
  - Verify reset restores default
  - Check responsive behavior

### 8.0 Extend to All Pages (Generic System)

- [ ] 8.1 Identify all pages with card layouts
  - Status (/status) ✅
  - Watchlist (/watchlist)
  - Portfolio (/portfolio)
  - Any other card-based pages
- [ ] 8.2 Define default layouts for each page
  - Create layout configs in `frontend/lib/layouts/defaults.ts`
  - Export: `DEFAULT_LAYOUTS = { status: [...], watchlist: [...], ... }`
- [ ] 8.3 Wrap each page with GridLayoutWrapper
  - Pass appropriate pageName and defaultLayout
  - Ensure card IDs are unique per page
- [ ] 8.4 Test layout customization on all pages
  - Verify independent layouts (changing one doesn't affect others)
  - Check persistence for each page

### 9.0 Polish and Edge Cases

- [ ] 9.1 Add loading states
  - Show skeleton while loading layout from backend
  - Handle slow network gracefully
- [ ] 9.2 Handle errors
  - Backend unavailable → use default layout
  - Invalid layout_config → fallback to default
  - Show user-friendly error messages
- [ ] 9.3 Add keyboard shortcuts (optional)
  - `Ctrl+L` to toggle lock/unlock
  - `Ctrl+R` to reset layout
- [ ] 9.4 Add animation/transitions
  - Smooth drag animations
  - Fade in/out for resize handles
  - Lock/unlock state transitions

### 10.0 Testing and Documentation

- [ ] 10.1 Write backend tests
  - Test GET /api/layouts/{page} (found, not found)
  - Test PUT /api/layouts/{page} (create, update)
  - Test DELETE /api/layouts/{page}
  - Path: `backend/tests/integration/test_layouts_api.py`
- [ ] 10.2 Write frontend component tests
  - Test GridLayoutWrapper drag/resize
  - Test useGridLayout hook
  - Mock backend API calls
- [ ] 10.3 Manual E2E testing
  - Test full workflow: unlock → drag → resize → lock → refresh → verify
  - Test across browsers (Chrome, Firefox, Safari)
  - Test responsive behavior on mobile
- [ ] 10.4 Update documentation
  - Add section to `docs/core/ARCHITECTURE.md` (Layout Customization)
  - Update `frontend/README.md` with usage examples
  - Document layout_config JSONB structure

---

## Verification Checklist

- [ ] Functional: All drag/resize/save/reset operations work
- [ ] Persistence: Layouts survive page refresh and browser restart
- [ ] Responsive: Layouts adapt correctly to mobile/tablet/desktop
- [ ] Performance: No lag during drag/resize operations
- [ ] Tests: Backend API tests passing, frontend components tested
- [ ] Quality: mypy --strict passes, ruff passes, no TypeScript errors
- [ ] UX: Visual feedback clear, lock/unlock intuitive
- [ ] Docs: Architecture and usage documented

---

## Technical Notes

**Database Schema:**
```sql
CREATE TABLE page_layouts (
    id SERIAL PRIMARY KEY,
    page_name VARCHAR(50) UNIQUE NOT NULL,
    layout_config JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Layout Config Structure (JSONB):**
```json
{
  "lg": [
    {"i": "card-id", "x": 0, "y": 0, "w": 6, "h": 2, "minW": 3, "maxW": 12},
    {"i": "another-card", "x": 6, "y": 0, "w": 6, "h": 2}
  ],
  "md": [...],
  "sm": [...]
}
```

**react-grid-layout Configuration:**
- Draggable: Enabled when unlocked
- Resizable: Enabled when unlocked
- Collision prevention: Enabled (cards can't overlap)
- Compact type: "vertical" (cards snap to top)
- Margin: [16, 16] (gap between cards)

**API Endpoints:**
- `GET /api/layouts/{page_name}` → 200 (layout) or 404 (use default)
- `PUT /api/layouts/{page_name}` → 200 (created/updated)
- `DELETE /api/layouts/{page_name}` → 204 (deleted, use default)
