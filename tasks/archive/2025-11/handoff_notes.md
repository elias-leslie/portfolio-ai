# Handoff Notes: UI Fixes

**To**: Fixer Agent
**From**: Reviewer Agent
**Date**: 2025-11-29

## Context
A comprehensive UI review identified several critical (P0) bugs that are causing crashes and data failures. The detailed findings are in `tasks/ui_review_findings.md`.

## Critical Tasks (Prioritized)

### 1. Fix Hydration Error (Trading Page Crash)
*   **Issue**: `RootLayout` has a `className="dark"` mismatch with client-side hydration.
*   **File**: `frontend/app/layout.tsx`
*   **Reproduction**: Navigate to `/trading`, click any ticker. Watch for "Hydration failed" or page crash.
*   **Fix**: Ensure server/client class names match or use `suppressHydrationWarning` correctly on the `body` tag if needed (it's currently on `html`).

### 2. Fix Runtime TypeError (Trade Details Crash)
*   **Issue**: `TypeError: Cannot read properties of null (reading 'toFixed')`.
*   **File**: `frontend/components/trading/TradeDetails.tsx` (Line ~115)
*   **Reproduction**: Expand a trade row in `/trading`.
*   **Fix**: Add null checks for `trade.backtest_sharpe` and other metrics before calling `.toFixed()`.

### 3. Fix Capabilities Page Data
*   **Issue**: "Scan System" button triggers a scan but UI shows "NaNM", "Unknown", or empty data in expanded rows. **Insights and Gaps tabs are completely empty.**
*   **File**: `frontend/app/capabilities/page.tsx` (and likely the backend endpoint it calls).
*   **Reproduction**: Go to `/capabilities`, click "Scan System", expand any row in Database/Tasks tabs, or check Insights/Gaps tabs.
*   **Fix**: Debug the data flow. Ensure the backend returns the expected structure and the frontend maps it correctly.

### 4. Optimize Trading Load
*   **Issue**: `/trading` takes 15s+ to load open positions.
*   **File**: `frontend/app/trading/page.tsx` (and backend `trading` router).
*   **Fix**: Investigate N+1 queries or unoptimized data fetching.

## References
*   [UI Review Findings](./ui_review_findings.md)
*   [Task Tracker](./tasks-0075-vision-gap-analysis.md)
