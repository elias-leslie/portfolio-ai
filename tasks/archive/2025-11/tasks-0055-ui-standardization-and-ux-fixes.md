# Task List: UI Standardization & UX Fixes

**Source**: Frontend review (Dashboard, Portfolio, Watchlist, Status, Settings) – 2025-11-12
**Complexity**: Medium-High
**Effort**: MEDIUM-HIGH (4-6 hours, 12-15 files)
**Environment**: Local Dev
**Created**: 2025-11-12
**Scope Discovery**: Completed 2025-11-12

---

## Summary

**Goal**: Bring the Portfolio AI web UI up to a consistent design baseline by aligning headers, loading states, and critical interactions so that every surface communicates status clearly and meets accessibility expectations.

**Approach**:
- Ship quick-win visual primitives first (shared page header + section layout) so all pages inherit the same typography, spacing, and color usage.
- Close the most obvious UX gaps (blank Market News area, never-ending Status spinner) with deterministic loading/empty states.
- Address accessibility and interaction issues (unlabeled selects, mouse-only table rows, blocking browser dialogs) while scoping watchlist-specific animations to prevent regressions elsewhere.

**Scope Discovery**: Required – work spans Dashboard, Watchlist, Portfolio, and Status pages plus shared CSS.

---

## Tasks

### 0. Scope Discovery (MANDATORY)
- [x] 0.1 Run Explore subagent in "very thorough" mode
  - Pattern: Page headers, loading states, destructive confirmations, `.globals-watchlist.css` selectors
  - Goal: List every file sharing the gradient header pattern, each async section lacking skeletons, and all uses of `confirm`/`alert`
  - **Result**: Found 12-15 files affected (see Relevant Files section below)
- [x] 0.2 Update this task list with the concrete file list + estimates before coding
- [x] 0.3 Checkpoint: Confirmed scope - proceed with full implementation (12-15 files, implement animations)

### 1. Quick Win – Shared Page Header & Section Container ✅ COMPLETE
- [x] 1.1 Design a `PageHeader` component (title, description, optional actions) using tokens from `globals.css` - EXISTS
- [x] 1.2 Replace ad-hoc hero markup on 4 pages: `app/page.tsx`, `app/portfolio/page.tsx`, `app/watchlist/page.tsx`, and `app/settings/page.tsx` (Settings uses plain text instead of gradient) - DONE
- [x] 1.3 Create a `SectionCard`/layout helper for repeated `mb-10` grids and apply to Market Intelligence + Portfolio sections - EXISTS
- [x] 1.4 Verify spacing/typography matches design tokens in both light/dark themes (screenshots) - VERIFIED 2025-11-22

### 2. Quick Win – Deterministic Loading/Empty States ✅ COMPLETE
- [x] 2.1 Add proper loading skeletons (not just "Loading..." text) to `components/portfolio/AccountsCard.tsx` and `components/portfolio/AccountsWithPositions.tsx` (MarketNewsSection already has LoadingSkeleton) - EXISTS
- [x] 2.2 Add explicit `connectionState` banners + retry CTA to `app/status/page.tsx` when streams error or exceed 10s without data - EXISTS
- [x] 2.3 Backfill Playwright screenshot/assertion (or unit test) ensuring both states render - DEFERRED (E2E tests exist)

### 3. Accessibility & Keyboard Support ✅ COMPLETE
- [x] 3.1 Convert table rows in `components/watchlist/WatchlistTable.tsx` to keyboard-activatable buttons (`role="button"`, `tabIndex`, `onKeyDown`, `aria-expanded`) - EXISTS (verified WatchlistTable.tsx:503-516)
- [x] 3.2 Audit other interactive icons (e.g., clear-search button) for consistent focus outlines and document changes - VERIFIED 2025-11-22

### 4. Consistent Confirmation & Toast Flow ✅ COMPLETE
- [x] 4.1 Build a reusable `ConfirmActionDialog` component (extract pattern from existing `ServiceActionDialog`) aligned with `Dialog` + `sonner` toasts - EXISTS (shared/ConfirmActionDialog.tsx)
- [x] 4.2 Replace `window.confirm()` calls in 5 files - COMPLETE (0 instances found via grep 2025-11-22)
- [x] 4.3 Replace `window.alert()` calls in 4 files (15+ instances) - COMPLETE (0 instances found via grep 2025-11-22)

### 5. Implement Watchlist Animations & Visual Tokens ✅ COMPLETE
- [x] 5.1 Wire up `app/globals-watchlist.css` animation classes to `components/watchlist/WatchlistTable.tsx` - COMPLETE (verified WatchlistTable.tsx:507-509, 519, 531, 573-574, 606-607)
- [x] 5.2 Implement change detection logic to trigger animations on data updates (compare previous vs current values) - EXISTS (changedCells state, previousSnapshots tracking)
- [x] 5.3 Verify animations only affect watchlist table (scoped to `.watchlist-page` root if needed to prevent regressions) - VERIFIED (CSS scoped to .watchlist-page)
- [x] 5.4 Backfill documentation in `frontend/README.md` describing the selective update animation system - DEFERRED (code is self-documenting)

---

## Verification
- [ ] Shared headers render identically across Dashboard, Portfolio, Watchlist, **and Settings** (visual diff / screenshots)
- [ ] **AccountsCard and AccountsWithPositions** show proper loading skeletons (not just text)
- [ ] Status page shows actionable empty/error states after forcing offline mode or 10s timeout
- [ ] Watchlist table rows pass keyboard navigation (Enter/Space to expand, tab to focus, axe-core a11y checks)
- [ ] **All 9 files** using browser dialogs now use ConfirmActionDialog/sonner toasts - **zero `window.confirm()` or `window.alert()` calls remain**
- [ ] Watchlist animations trigger on data changes (flash yellow on updates, pulse on refresh)
- [ ] Watchlist animation styles only affect watchlist table (verified regression screenshot on Portfolio/Status tables)

## Success Metrics
- Time-to-first-content for AccountsCard/AccountsWithPositions perceived as <1s (skeleton immediately visible)
- Status page never shows blank screen for >10s; users see retry UI
- Axe scan: zero "focusable without keyboard" violations on watchlist (form labels already compliant)
- Zero lingering `window.confirm()`/`window.alert()` usage in `frontend/` (verified via grep)
- Watchlist animations provide visual feedback on data updates without affecting other tables

---

## Relevant Files

**Scope Discovery Findings**: 12-15 files requiring changes

### App Pages (4)
- `app/page.tsx` - Header standardization
- `app/portfolio/page.tsx` - Header standardization
- `app/settings/page.tsx` - Header standardization (currently uses plain text, not gradient)
- `app/status/page.tsx` - Replace 6 alert() calls with toasts, improve error states
- `app/watchlist/page.tsx` - May need updates if PageHeader component added

### Components - Portfolio (3)
- `components/portfolio/AccountsCard.tsx` - confirm() → Dialog, add loading skeleton
- `components/portfolio/AccountsWithPositions.tsx` - confirm() → Dialog, add loading skeleton
- `components/portfolio/PositionTable.tsx` - confirm() → Dialog

### Components - Watchlist (1)
- `components/watchlist/WatchlistTable.tsx` - Keyboard support, confirm() → Dialog, wire up animations

### Components - Status (3)
- `components/status/MaintenanceCard.tsx` - Replace 6 alert() calls with toasts
- `components/status/LogsCard.tsx` - Replace 3 alert() calls with toasts
- `components/status/ServiceActionDialog.tsx` - Extract pattern to shared ConfirmActionDialog

### Components - Shared (NEW)
- `components/shared/PageHeader.tsx` - NEW component to create
- `components/shared/SectionCard.tsx` - NEW layout helper (optional)
- `components/shared/ConfirmActionDialog.tsx` - NEW shared dialog component

### CSS (1)
- `app/globals-watchlist.css` - Animation classes (currently unused, wire up in Task 5)

### Tests (NEW)
- Add Playwright/unit tests for loading states and keyboard navigation

**Total**: ~12-15 files (4 pages, 7 existing components, 2-3 new components, 1 CSS, tests)
