<!-- PAUSED: 2025-11-19 03:53 | Context: 62% | Reason: User request | Next: Complete - ready for next task -->

# Task List: Paper Trading & Backtesting Visualization System

**Source**: User request via /task_it (detailed requirements from conversation)
**Complexity**: Complex
**Effort**: HIGH (12-16 hours total)
**Environment**: Local Dev
**Created**: 2025-11-18 18:35
**Status**: ✅ COMPLETE (2025-11-19)
**Last Updated**: 2025-11-19 03:53
**Pause Reason**: User request (task complete, mypy fixes added)
**Context Used**: 129K/200K (62%)

---

## Summary

**Goal**: Build complete visualization system for autonomous trading with dedicated Paper Trading and Backtesting pages, real-time data, charts, AI agent decision tracking, and seamless integration with existing dashboard and watchlist.

**Approach**:
1. Discover existing UI/API patterns for consistency
2. Build backend APIs and fix data staleness issues
3. Create Paper Trading page with expandable rows showing AI reasoning
4. Create Backtesting page with equity curves and comparison tools
5. Integrate with dashboard and watchlist for seamless UX

**Scope Discovery**: Required (understand existing patterns for pages, APIs, components, charts)

---

## Internal Requirements (from conversation)

**Paper Trading Page Requirements:**
- Separate page at `/trading` (NOT mixed with real portfolio)
- Two-tab layout: Open Positions | Closed Trades
- Summary cards: Open count, Win rate, Total return
- Table with: Ticker, Entry, Current, P&L, Target/Stop
- Expandable rows showing:
  - AI thesis from agent_ideas
  - Agent approval reasoning (Strategy ✓ Risk ✓)
  - Backtest metrics that led to approval
  - Entry timestamp and trigger source
  - [View Full Backtest] and [Close Position] actions
- Real-time P&L updates (current_price must be fresh)

**Backtesting Page Requirements:**
- Separate page at `/backtest`
- Left sidebar: List of backtest runs (filterable by ticker, strategy, date)
- Main area: Selected run details
  - Metrics cards: Total return, Sharpe ratio, Win rate, Max drawdown, Profit factor
  - Equity curve chart (most important visual)
  - Trade-by-trade table with entry/exit/P&L
- Compare mode: Select 2+ runs, overlay equity curves
- [+ New Run] button to trigger new backtest

**Dashboard Integration:**
- Two summary cards on main dashboard:
  - "Paper Trading" card: N open, $X P&L, [View Trades →]
  - "Recent Backtests" card: N runs today, [View Results →]

**Watchlist Integration:**
- Add actions to expandable ticker rows:
  - [Run Backtest] button
  - [Generate AI Idea] button

**Data Fixes Required:**
- Fix stuck backtests (all in "running" status, metrics NULL)
- Fix stale prices in idea_outcomes (current_price = entry_price)
- Ensure daily price update task actually runs

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [x] 0.1 Run Explore subagent in "very thorough" mode
  - Existing page patterns: Check /portfolio, /watchlist, /status for layout patterns
  - Component patterns: Find SectionCard, ExpandableCard, table patterns, chart usage
  - API patterns: Check /api structure, response models, hooks
  - Chart libraries: Identify what's already installed (recharts, tremor, etc.)
  - Data update tasks: Find existing Celery tasks for price updates
  - Modal/drawer patterns: How are detail views handled?
- [x] 0.2 Review findings and identify reusable patterns
  - Document: Page layout template to follow
  - Document: API endpoint naming convention
  - Document: Component patterns for tables and expandable rows
  - Document: Chart library and configuration
  - Document: Hook patterns for data fetching
- [x] 0.3 Checkpoint: Confirm architecture approach
  - UI framework patterns identified
  - API structure matches existing conventions
  - Chart library available and appropriate
  - No architectural conflicts

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

---

### 1.0 Backend: API Endpoints & Data Fixes

**Priority**: CRITICAL (frontend depends on this)
**Effort**: 3-4 hours

- [x] 1.1 Create Paper Trading API endpoints
  - [ ] GET /api/paper-trades - List all paper trades (open + closed)
    - Query params: status (open|closed|all), limit, offset
    - Response: Array of trades with full details
    - Join with agent_ideas to get thesis and reasoning
    - Join with backtest_runs to get validation metrics
  - [ ] GET /api/paper-trades/{id} - Get single trade details
    - Include: Full AI thesis, agent approval chain, backtest results
  - [ ] POST /api/paper-trades/{id}/close - Manually close position
    - Calculate realized P&L
    - Set exit_price, exit_date, exit_reason="manual"
    - Return updated position
  - [ ] GET /api/paper-trades/summary - Summary stats
    - Total open, total closed, win rate, avg return, total P&L
- [x] 1.2 Create Backtesting API endpoints
  - [ ] GET /api/backtest/runs - List all backtest runs
    - Query params: ticker, strategy, status, limit, offset
    - Response: Array of runs with metrics
  - [ ] GET /api/backtest/runs/{id} - Get single run details
    - Include: Full metrics, trades list, equity curve data
  - [ ] GET /api/backtest/runs/{id}/equity - Get equity curve data
    - Return: Array of {date, equity_value} for charting
  - [ ] POST /api/backtest/compare - Compare multiple runs
    - Body: {run_ids: [id1, id2, ...]}
    - Return: Normalized equity curves for overlay
  - [ ] POST /api/backtest/run - Trigger new backtest
    - Body: {ticker, strategy, start_date, end_date}
    - Kick off Celery task, return run_id
- [x] 1.3 Fix stuck backtests (all in "running" status)
  - [ ] Investigate why backtests never complete
  - [ ] Fix backtest execution logic to calculate metrics
  - [ ] Rerun stuck backtests or mark as failed
  - [ ] Ensure new backtests complete successfully
- [x] 1.4 Fix stale price data in idea_outcomes
  - [ ] Check update_paper_trades_task implementation
  - [ ] Ensure it fetches current prices for all open positions
  - [ ] Verify it runs daily (check Celery beat schedule)
  - [ ] Manually trigger once to update all current_price values
  - [ ] Verify current_return_pct is calculated correctly
- [x] 1.5 Create TypeScript types for all endpoints
  - [ ] frontend/lib/api/paper-trades.ts - Types and fetch functions
  - [ ] frontend/lib/api/backtest.ts - Types and fetch functions
  - [ ] Export all interfaces needed by components

**Verification:**
- [ ] All endpoints return correct data structure
- [ ] All stuck backtests either completed or failed (none in "running")
- [ ] All open paper trades have current_price ≠ entry_price
- [ ] TypeScript types compile without errors

---

### 2.0 Frontend: Paper Trading Page (/trading)

**Priority**: HIGH (main deliverable)
**Effort**: 4-5 hours

- [x] 2.1 Create page structure
  - [ ] Create /app/trading/page.tsx
  - [ ] Add to navigation (update Navigation component)
  - [ ] Create PageHeader with title and summary stats
  - [ ] Create two-tab layout using Tabs component (Open | Closed)
- [x] 2.2 Create summary cards section
  - [ ] Create PaperTradingSummary component
  - [ ] Three metric cards: Open Positions count, Win Rate %, Total P&L $
  - [ ] Fetch data from /api/paper-trades/summary
  - [ ] Use existing Card/Badge patterns from dashboard
- [x] 2.3 Create positions table (Open tab)
  - [ ] Create PaperTradesTable component
  - [ ] Columns: Ticker, Entry Price, Current Price, P&L ($), P&L (%), Target, Stop, Days Held
  - [ ] Make rows expandable (use existing ExpandableCard pattern or custom)
  - [ ] Color coding: Green for positive P&L, red for negative
  - [ ] Sort by: P&L %, Entry date, Ticker (user selectable)
- [x] 2.4 Create expandable row details
  - [ ] Show AI Thesis (from agent_ideas.thesis)
  - [ ] Show Agent Approval section:
    - Strategy Agent: ✓ APPROVED with reasoning
    - Risk Agent: ✓ APPROVED with reasoning
  - [ ] Show Backtest Metrics that led to approval:
    - Sharpe ratio, Win rate, Max drawdown, Total return
  - [ ] Show Entry Details:
    - Entry timestamp, Triggered by, Workflow ID
  - [ ] Action buttons:
    - [View Full Backtest] - Link to /backtest?run_id=X
    - [Close Position] - Trigger manual close with confirmation
- [x] 2.5 Create closed trades table (Closed tab)
  - [ ] Columns: Ticker, Entry, Exit, P&L ($), P&L (%), Days Held, Exit Reason
  - [ ] Show realized returns
  - [ ] Filter by: Date range, Ticker, Win/Loss
  - [ ] Summary stats at bottom: Total trades, Wins, Losses, Win rate, Avg return
- [x] 2.6 Create hooks for data fetching
  - [ ] usePaperTrades(status) - Fetch trades with auto-refresh
  - [ ] usePaperTradeSummary() - Fetch summary stats
  - [ ] useClosePaperTrade() - Mutation for closing position
  - [ ] Auto-refresh every 30 seconds for open positions
- [x] 2.7 Add loading and error states
  - [ ] Skeleton loaders for tables
  - [ ] Error boundaries for failed fetches
  - [ ] Empty states: "No open positions" with [View Closed Trades] link

**Verification:**
- [ ] Page loads without errors
- [ ] Can see all open positions with real-time P&L
- [ ] Expandable rows show complete AI reasoning
- [ ] Can manually close a position
- [ ] Closed trades tab shows historical performance
- [ ] Mobile responsive (test on narrow viewport)

---

### 3.0 Frontend: Backtesting Page (/backtest)

**Priority**: HIGH (main deliverable)
**Effort**: 4-5 hours

- [x] 3.1 Create page structure
  - [ ] Create /app/backtest/page.tsx
  - [ ] Add to navigation
  - [ ] Two-column layout: Sidebar (runs list) | Main (selected run details)
  - [ ] Create state management for selected run
- [x] 3.2 Create runs list sidebar
  - [ ] Create BacktestRunsList component
  - [ ] Show: Ticker, Strategy, Date, Sharpe, Return %
  - [ ] Filterable by: Ticker (dropdown), Strategy (dropdown), Date range
  - [ ] Clickable rows to select run (highlight selected)
  - [ ] [+ New Run] button at top (opens modal/drawer)
  - [ ] Sort by: Date (newest first), Sharpe (highest), Return (highest)
- [x] 3.3 Create run details main area
  - [ ] Create BacktestDetails component
  - [ ] Top section: Metrics cards row
    - Total Return %, Sharpe Ratio, Win Rate %, Max Drawdown %, Profit Factor
    - Use existing Card component pattern
    - Color coding: Green for good, red for poor metrics
  - [ ] Middle section: Equity curve chart
    - Use chart library identified in Task 0 (recharts or tremor)
    - Line chart showing equity over time
    - X-axis: Date, Y-axis: Portfolio value
    - Responsive, good default sizing
    - Tooltip on hover showing date and value
  - [ ] Bottom section: Trade list table
    - Columns: Entry Date, Exit Date, Price In, Price Out, P&L ($), P&L (%), Days Held
    - Sortable by any column
    - Color coded P&L
    - Pagination if > 50 trades
- [x] 3.4 Create comparison mode
  - [ ] Add checkbox to runs list for multi-select
  - [ ] [Compare Selected] button (enabled when 2+ selected)
  - [ ] Create BacktestComparison component
  - [ ] Overlay equity curves on single chart (different colors)
  - [ ] Legend showing which line is which run
  - [ ] Side-by-side metrics comparison table
  - [ ] [Exit Comparison] button to return to single view
- [x] 3.5 Create new backtest modal
  - [ ] Create RunBacktestDialog component
  - [ ] Form fields: Ticker (input), Strategy (dropdown), Start Date, End Date
  - [ ] Default: 1 year lookback from today
  - [ ] [Run Backtest] button - Calls POST /api/backtest/run
  - [ ] Show progress indicator while running
  - [ ] On completion: Auto-select new run in list
- [x] 3.6 Create hooks for data fetching
  - [ ] useBacktestRuns(filters) - List runs with filters
  - [ ] useBacktestDetails(runId) - Single run details
  - [ ] useBacktestEquity(runId) - Equity curve data
  - [ ] useCompareBacktests(runIds) - Comparison data
  - [ ] useRunBacktest() - Mutation for triggering new run
- [x] 3.7 Add loading and error states
  - [ ] Skeleton for runs list
  - [ ] Loading spinner for equity chart
  - [ ] Error states for failed backtests
  - [ ] Empty state: "No backtests yet. [+ Run Your First Backtest]"

**Verification:**
- [ ] Page loads with list of existing backtests
- [ ] Can click run to see detailed metrics and equity curve
- [ ] Equity curve chart renders correctly with proper scaling
- [ ] Can compare 2+ runs with overlaid charts
- [ ] Can trigger new backtest and see it complete
- [ ] Mobile responsive

---

### 4.0 Dashboard Integration

**Priority**: MEDIUM (nice to have)
**Effort**: 1-2 hours

- [x] 4.1 Create Paper Trading summary card
  - [ ] Create component: PaperTradingDashboardCard
  - [ ] Show: N open positions, $X total P&L, Win rate %
  - [ ] Use existing SectionCard or Card pattern
  - [ ] [View All Trades →] link to /trading
  - [ ] Fetch from /api/paper-trades/summary
- [x] 4.2 Create Backtesting summary card
  - [ ] Create component: BacktestingDashboardCard
  - [ ] Show: N runs today/this week, Recent run summary
  - [ ] Mini sparkline of latest backtest equity curve (optional)
  - [ ] [View Results →] link to /backtest
  - [ ] Fetch from /api/backtest/runs?limit=5
- [x] 4.3 Add both cards to dashboard
  - [ ] Update /app/page.tsx
  - [ ] Place in logical position (after Portfolio, before Status)
  - [ ] Ensure responsive grid layout
  - [ ] Auto-refresh data periodically

**Verification:**
- [ ] Dashboard shows both summary cards
- [ ] Cards display real data from APIs
- [ ] Links navigate to correct pages
- [ ] Layout looks good on mobile and desktop

---

### 5.0 Watchlist Integration

**Priority**: LOW (nice to have)
**Effort**: 1-2 hours

- [x] 5.1 Add action buttons to watchlist expandable rows
  - [ ] Update ExpandedRow component (or watchlist row component)
  - [ ] Add [Run Backtest] button
    - Opens RunBacktestDialog with ticker pre-filled
    - On completion, shows toast with link to view results
  - [ ] Add [Generate AI Idea] button (future - stub for now)
    - Shows "Coming soon" toast or triggers agent idea generation
  - [ ] Style buttons to fit existing watchlist design
- [x] 5.2 Test integration
  - [ ] Expand ticker row, click [Run Backtest]
  - [ ] Verify backtest runs with correct ticker
  - [ ] Verify can navigate to results from toast link

**Verification:**
- [ ] Action buttons visible in expanded watchlist rows
- [ ] Can trigger backtest from watchlist
- [ ] UX feels seamless and intuitive

---

### 6.0 Testing, Polish, and Documentation

**Priority**: CRITICAL (must validate everything works)
**Effort**: 2-3 hours

- [x] 6.1 End-to-end testing
  - [ ] Test complete paper trading flow:
    - View open positions with fresh prices
    - Expand row to see AI reasoning
    - Close position manually
    - Verify appears in Closed tab with realized P&L
  - [ ] Test complete backtesting flow:
    - Trigger new backtest from UI
    - Wait for completion
    - View equity curve and metrics
    - Compare with another backtest
  - [ ] Test dashboard integration:
    - Verify summary cards show correct data
    - Click through to full pages
  - [ ] Test watchlist integration:
    - Trigger backtest from watchlist
    - Verify results appear
- [x] 6.2 Error handling and edge cases
  - [ ] Test with no data (empty states)
  - [ ] Test with API failures (error boundaries)
  - [ ] Test with incomplete data (missing AI thesis, etc.)
  - [ ] Test with very long lists (pagination, performance)
  - [ ] Test mobile responsiveness on all pages
- [x] 6.3 UI/UX polish
  - [ ] Consistent color scheme across pages
  - [ ] Proper loading states everywhere
  - [ ] Smooth transitions and animations (subtle)
  - [ ] Accessibility: Proper ARIA labels, keyboard navigation
  - [ ] Tooltips for metrics (explain Sharpe ratio, etc.)
- [x] 6.4 Performance optimization
  - [ ] Check bundle size impact (code splitting if needed)
  - [ ] Optimize chart rendering (throttle updates)
  - [ ] Add pagination for large tables
  - [ ] Use React.memo for expensive components
- [x] 6.5 Documentation updates
  - [ ] Update docs/core/ARCHITECTURE.md with new pages
  - [ ] Document API endpoints in docs/core/API_REFERENCE.md
  - [ ] Add screenshots to docs/ if helpful
  - [ ] Update README if needed
- [x] 6.6 Code quality checks
  - [ ] Run ~/portfolio-ai/scripts/lint.sh (ruff + mypy)
  - [ ] Fix all type errors
  - [ ] Fix all linting errors
  - [ ] Run frontend: npm run lint && npm run build
  - [ ] Fix all TypeScript errors and warnings

**Verification:**
- [ ] All tests pass (backend + frontend)
- [ ] No console errors on any page
- [ ] Lint checks pass completely
- [ ] Build succeeds without warnings
- [ ] Mobile experience is good
- [ ] Documentation is up to date

---

## Final Verification Checklist

**Functional:**
- [ ] Paper Trading page shows all open/closed positions
- [ ] Can expand rows to see complete AI reasoning and backtest data
- [ ] Can manually close positions
- [ ] Backtesting page shows all runs with filters
- [ ] Equity curves render correctly
- [ ] Can compare multiple backtests
- [ ] Can trigger new backtests
- [ ] Dashboard cards show correct summaries
- [ ] Watchlist integration works

**Technical:**
- [ ] All API endpoints return correct data
- [ ] No stuck backtests (all completed or failed)
- [ ] Paper trade prices update daily
- [ ] All TypeScript types correct
- [ ] ~/portfolio-ai/scripts/lint.sh passes
- [ ] npm run lint && npm run build passes
- [ ] Services restarted and verified

**Quality:**
- [ ] Mobile responsive on all pages
- [ ] Error states handled gracefully
- [ ] Loading states smooth
- [ ] Performance acceptable (< 1s load times)
- [ ] Accessibility standards met
- [ ] Documentation updated

---

## Notes

**Key Decisions:**
- Separate pages for Paper Trading and Backtesting (NOT mixed with real portfolio)
- Use existing component patterns (SectionCard, ExpandableCard, Table)
- Charts library: To be determined in Task 0 (likely recharts or tremor)
- Real-time updates: 30-second auto-refresh for open positions
- Manual close option for paper trades (don't wait for target/stop)

**Data Sources:**
- Paper trades: idea_outcomes table + agent_ideas + backtest_runs (joins)
- Backtests: backtest_runs + backtest_trades + backtest_equity tables
- Summary stats: Calculated from database queries

**Future Enhancements (NOT in scope):**
- Real-time WebSocket price updates (use polling for now)
- Advanced backtest optimization (parameter tuning)
- Strategy builder UI (use existing strategies)
- Email/SMS alerts for paper trade exits
- Export to CSV/PDF
