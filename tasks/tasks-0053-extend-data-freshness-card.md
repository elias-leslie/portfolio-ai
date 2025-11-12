# Task List: Extend Data Freshness Card on Status Page

**Source**: User request - comprehensive table freshness monitoring
**Complexity**: Medium
**Effort**: MEDIUM (2-3 hours)
**Environment**: Local Dev
**Created**: 2025-11-11 21:30

---

## Summary

**Goal**: Extend the "Day Bars Data Freshness" card to show fresh/stale status for ALL important tables, not just day_bars.

**Current State**: Status page has a single card showing day_bars table freshness with ticker-level detail.

**Target State**: Unified "Data Freshness" card showing:
- Collapsed: "X Fresh / Y Stale tables" summary
- Expanded: Table-by-table breakdown with last update times
- Color coding: Green (<24h), Yellow (24-48h), Red (>48h)

**Approach**:
1. Backend: Create comprehensive freshness check endpoint
2. Frontend: Replace current card with accordion-style component
3. Include all regularly-updating tables
4. Apply consistent color coding

**Tables to Monitor**:
- `day_bars` - OHLCV market data
- `fear_greed_inputs` - F&G raw inputs
- `fear_greed_daily` - F&G calculated scores
- `fear_greed_components` - F&G component scores
- `news` - News articles
- `watchlist_items` - User watchlist entries
- `positions` - Portfolio positions
- `accounts` - Portfolio accounts
- `price_cache` - Real-time price cache

---

## Tasks

### 1.0 Backend API Endpoint

- [ ] 1.1 Create `/api/status/table-freshness` endpoint
  - Returns array of table status objects
  - Each object: `{name, last_updated, status, row_count}`
  - Status: "fresh" (<24h), "stale" (24-48h), "critical" (>48h)
- [ ] 1.2 Implement freshness check logic
  - Query MAX(updated_at/cached_at/date) for each table
  - Calculate age in hours
  - Determine status based on thresholds
- [ ] 1.3 Handle tables with different timestamp columns
  - `day_bars`: MAX(date)
  - `fear_greed_*`: MAX(as_of_date)
  - `news`: MAX(published_at)
  - `watchlist_items`: MAX(updated_at)
  - `positions`: MAX(updated_at)
  - `price_cache`: MAX(cached_at)
- [ ] 1.4 Add response model with TypeScript types
  - `TableFreshnessStatus` interface
  - `TableFreshnessResponse` interface

### 2.0 Frontend Component Updates

- [ ] 2.1 Create new `TableFreshnessCard.tsx` component
  - Replace existing `DayBarsDataFreshness.tsx`
  - Accordion-style UI (collapsed by default)
  - Summary shows: "12 Fresh / 3 Stale tables"
- [ ] 2.2 Implement collapsed state UI
  - Show aggregate counts (fresh/stale/critical)
  - Color-coded summary (green if all fresh, yellow/red if any stale)
  - Expand/collapse icon
- [ ] 2.3 Implement expanded state UI
  - Table list with: name, last update, status badge
  - Color coding: Green badge (fresh), Yellow (stale), Red (critical)
  - Relative time format: "2 hours ago", "1 day ago"
- [ ] 2.4 Add hover tooltips
  - Show exact timestamp on hover
  - Explain status thresholds

### 3.0 Integration and Polish

- [ ] 3.1 Update Status page layout
  - Remove old `DayBarsDataFreshness` component
  - Add new `TableFreshnessCard` component
  - Maintain grid layout consistency
- [ ] 3.2 Add loading and error states
  - Skeleton loader while fetching
  - Error message if endpoint fails
  - Retry mechanism
- [ ] 3.3 Style consistency
  - Match existing Status page card styling
  - Responsive design (mobile/desktop)
  - Dark mode support

### 4.0 Testing and Verification

- [ ] 4.1 Backend tests
  - Test freshness calculation logic
  - Test with tables at different ages
  - Test missing/null timestamps
- [ ] 4.2 Frontend tests
  - Test collapsed/expanded states
  - Test color coding logic
  - Test responsive layout
- [ ] 4.3 Manual verification
  - Check Status page in browser
  - Verify all tables show correct status
  - Test expand/collapse interaction
  - Verify color coding works

### 5.0 Documentation and Cleanup

- [ ] 5.1 Update API documentation
  - Add `/api/status/table-freshness` to API_REFERENCE.md
  - Document response schema
- [ ] 5.2 Remove deprecated code
  - Delete old `DayBarsDataFreshness.tsx` if fully replaced
  - Remove unused imports
- [ ] 5.3 Update WORK_TRACKER.md
  - Mark task as complete
  - Document any follow-up improvements

---

## Verification Checklist

- [ ] Functional: All 9 tables show in freshness card
- [ ] Functional: Color coding works (green/yellow/red)
- [ ] Functional: Accordion expands/collapses smoothly
- [ ] Functional: Summary shows correct "X Fresh / Y Stale"
- [ ] Tests: Backend endpoint tested
- [ ] Tests: Frontend component tested
- [ ] Quality: mypy --strict passes
- [ ] Quality: ruff passes
- [ ] UI/UX: Responsive on mobile and desktop
- [ ] UI/UX: Dark mode works correctly
- [ ] Docs: API_REFERENCE.md updated

---

## Notes

**Design Decisions**:
- Thresholds: <24h = fresh, 24-48h = stale, >48h = critical
- Tables included: Core operational tables only (not migration metadata, etc.)
- Default state: Collapsed (less visual clutter)

**Future Enhancements** (not in scope):
- Configurable freshness thresholds per table
- Historical freshness trends/charts
- Email alerts for critical staleness
- Auto-refresh every 5 minutes
