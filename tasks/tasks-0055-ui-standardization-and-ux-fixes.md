# Task List: UI Standardization & UX Fixes

**Source**: Frontend review (Dashboard, Portfolio, Watchlist, Status, Settings) – 2025-11-12
**Complexity**: Medium
**Effort**: MEDIUM (3-5 hours)
**Environment**: Local Dev
**Created**: 2025-11-12

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
- [ ] 0.1 Run Explore subagent in "very thorough" mode
  - Pattern: Page headers, loading states, destructive confirmations, `.globals-watchlist.css` selectors
  - Goal: List every file sharing the gradient header pattern, each async section lacking skeletons, and all uses of `confirm`/`alert`
- [ ] 0.2 Update this task list with the concrete file list + estimates before coding
- [ ] 0.3 Checkpoint: Confirm scope (files, effort, risks) before proceeding

### 1. Quick Win – Shared Page Header & Section Container
- [ ] 1.1 Design a `PageHeader` component (title, description, optional actions) using tokens from `globals.css`
- [ ] 1.2 Replace ad-hoc hero markup on `app/page.tsx`, `app/portfolio/page.tsx`, and `app/watchlist/page.tsx`
- [ ] 1.3 Create a `SectionCard`/layout helper for repeated `mb-10` grids and apply to Market Intelligence + Portfolio sections
- [ ] 1.4 Verify spacing/typography matches design tokens in both light/dark themes (screenshots)

### 2. Quick Win – Deterministic Loading/Empty States
- [ ] 2.1 Update `MarketNewsSection` to render a capped skeleton + description even before `IntersectionObserver` fires, and add a timeout-based empty state
- [ ] 2.2 Add explicit `connectionState` banners + retry CTA to `app/status/page.tsx` when streams error or exceed 10s without data
- [ ] 2.3 Backfill Playwright screenshot/assertion (or unit test) ensuring both states render

### 3. Accessibility & Keyboard Support
- [ ] 3.1 Wrap watchlist filter `Select` components (`app/watchlist/page.tsx`) with visible labels or `aria-label`s tied to descriptive IDs
- [ ] 3.2 Convert table rows in `components/watchlist/WatchlistTable.tsx` to keyboard-activatable buttons (`role="button"`, `tabIndex`, `onKeyDown`)
- [ ] 3.3 Audit other interactive icons (e.g., clear-search button) for consistent focus outlines and document changes

### 4. Consistent Confirmation & Toast Flow
- [ ] 4.1 Build a reusable `ConfirmActionDialog` aligned with `Dialog` + `sonner` toasts
- [ ] 4.2 Replace `confirm()` usages in `AccountsWithPositions.tsx` for account/position deletion
- [ ] 4.3 Replace `alert()` success/error handling in `app/status/page.tsx` service actions with the new dialog + toasts, ensuring the existing `ServiceActionDialog` is leveraged or simplified

### 5. Scope Watchlist Animations & Visual Tokens
- [ ] 5.1 Move rules from `app/globals-watchlist.css` into a `@layer utilities` block scoped under a `.watchlist-page` root (or CSS module)
- [ ] 5.2 Update `WatchlistPage` root node to add the scoping class/data attribute and verify other tables remain unaffected
- [ ] 5.3 Backfill documentation in `frontend/README.md` describing how to opt-in to the watchlist animation helpers

---

## Verification
- [ ] Shared headers render identically across Dashboard, Portfolio, and Watchlist (visual diff / screenshots)
- [ ] Market News and Status pages show skeletons + actionable empty/error states after forcing offline mode
- [ ] Watchlist filters and rows pass keyboard navigation + axe-core a11y checks
- [ ] Destructive actions use the new confirmation dialog and emit `sonner` toasts with success/failure copy
- [ ] Watchlist animation styles no longer affect tables on other routes (verified via regression screenshot/tests)

## Success Metrics
- Time-to-first-content for Market News perceived as <1s (skeleton immediately visible)
- Status page never shows blank screen for >10s; users see retry UI
- Axe scan: zero "form label" and "focusable without keyboard" violations on watchlist
- Zero lingering `confirm`/`alert` usage in `frontend/`
