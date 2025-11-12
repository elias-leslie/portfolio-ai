# Task List: Portfolio-Watchlist Integration & News Cleanup

**Task ID**: TASK-0036
**Status**: Complete (Ready to Commit)
**Completion**: 100%
**Effort**: MEDIUM (~4 hours)
**Created**: 2025-11-08 23:00
**Completed**: 2025-11-09 00:17
**Type**: Standalone task list

<!-- SESSION PAUSED: 2025-11-09 00:27 - Task complete, uncommitted changes ready -->

---

## Summary

Remove redundant `/news` page, integrate market news into dashboard, and create seamless portfolio-watchlist integration with visual indicators and navigation.

**✅ COMPLETE:** All tasks
**🔄 IN PROGRESS:** (None)
**⚠️ NEXT:** (Complete)

---

## Relevant Files

### Backend Changes (3 files)
- `backend/app/portfolio/portfolio_service.py` - Add watchlist sync logic
- `backend/app/watchlist/watchlist_service.py` - Add portfolio source tracking
- `backend/app/api/portfolio.py` - Trigger sync on portfolio fetch

### Frontend Changes (7 files)
- `frontend/components/watchlist/WatchlistTable.tsx` - Add portfolio indicator badge
- `frontend/components/portfolio/PortfolioOverview.tsx` - Add clickable tickers, color coding
- `frontend/app/dashboard/page.tsx` - Add market news card
- `frontend/components/dashboard/MarketNewsCard.tsx` - NEW - Market news component
- `frontend/app/layout.tsx` or navigation - Remove /news link
- `frontend/app/news/page.tsx` - DELETE
- `frontend/lib/hooks/useNews.ts` - Clean up unused exports

### Tests
- `backend/tests/unit/portfolio/test_watchlist_sync.py` - NEW - Auto-sync tests
- Manual UI testing via browser automation

---

## Tasks

### 1.0 Portfolio-Watchlist Auto-Sync (Backend)

- [ ] 1.1 Add `source` column to watchlist_items table
  - [ ] 1.1.1 Create migration 022_watchlist_source_tracking.sql
  - [ ] 1.1.2 Add `source TEXT DEFAULT 'manual'` column
  - [ ] 1.1.3 Add index on (account_id, source) for filtering
  - [ ] 1.1.4 Execute on both production and test databases
  - **Time**: 5 min

- [ ] 1.2 Implement watchlist sync function in portfolio_service.py
  - [ ] 1.2.1 Create `sync_portfolio_to_watchlist(account_id, tickers)` function
  - [ ] 1.2.2 Query existing watchlist tickers for account
  - [ ] 1.2.3 Find missing tickers (set difference)
  - [ ] 1.2.4 Insert missing tickers with source='portfolio'
  - [ ] 1.2.5 Use INSERT...ON CONFLICT DO NOTHING (idempotent)
  - [ ] 1.2.6 NO cascade deletes or foreign keys
  - **Time**: 10 min

- [ ] 1.3 Integrate sync into portfolio data flow
  - [ ] 1.3.1 Call sync_portfolio_to_watchlist in get_portfolio()
  - [ ] 1.3.2 Extract unique tickers from positions
  - [ ] 1.3.3 Call sync after fetching portfolio data
  - [ ] 1.3.4 Handle errors gracefully (log but don't fail request)
  - **Time**: 5 min

- [ ] 1.4 Write tests for portfolio-watchlist sync
  - [ ] 1.4.1 Test: Portfolio ticker auto-added to empty watchlist
  - [ ] 1.4.2 Test: Existing manual watchlist ticker not modified
  - [ ] 1.4.3 Test: Multiple portfolio tickers synced correctly
  - [ ] 1.4.4 Test: Idempotent (calling twice doesn't duplicate)
  - [ ] 1.4.5 Test: Source column correctly set to 'portfolio'
  - **Time**: 15 min

### 2.0 Watchlist Portfolio Indicator (Frontend)

- [ ] 2.1 Update watchlist API response to include source
  - [ ] 2.1.1 Add `source` field to WatchlistItemResponse model
  - [ ] 2.1.2 Include source in watchlist_service.get_items_with_scores()
  - [ ] 2.1.3 Verify API returns source='portfolio' or 'manual'
  - **Time**: 5 min

- [ ] 2.2 Add portfolio indicator badge to WatchlistTable
  - [ ] 2.2.1 Check if item.source === 'portfolio'
  - [ ] 2.2.2 Add small badge/icon next to ticker symbol
  - [ ] 2.2.3 Use briefcase icon or "P" badge
  - [ ] 2.2.4 Add tooltip: "In your portfolio"
  - [ ] 2.2.5 Style: subtle, non-intrusive (muted color)
  - **Time**: 10 min

- [ ] 2.3 Test portfolio indicator updates dynamically
  - [ ] 2.3.1 Add position to portfolio via UI
  - [ ] 2.3.2 Verify ticker appears in watchlist with indicator
  - [ ] 2.3.3 Remove position from portfolio
  - [ ] 2.3.4 Verify indicator remains (ticker not removed)
  - **Time**: 5 min

### 3.0 Portfolio Row Navigation (Frontend)

- [ ] 3.1 Make ticker symbol clickable in PortfolioOverview
  - [ ] 3.1.1 Wrap ticker symbol in Link or button
  - [ ] 3.1.2 Add hover state (underline, color change)
  - [ ] 3.1.3 Navigate to `/watchlist?ticker=${symbol}`
  - [ ] 3.1.4 Style as inline link (not disruptive to table)
  - **Time**: 8 min

- [ ] 3.2 Implement scroll-to-ticker in WatchlistTable
  - [ ] 3.2.1 Read `ticker` query parameter on mount
  - [ ] 3.2.2 Find matching row by ticker symbol
  - [ ] 3.2.3 Use scrollIntoView({ behavior: 'smooth', block: 'center' })
  - [ ] 3.2.4 Optionally auto-expand the target row
  - [ ] 3.2.5 Add subtle highlight animation (fade out after 2s)
  - **Time**: 12 min

- [ ] 3.3 Test navigation flow
  - [ ] 3.3.1 Click ticker in portfolio table
  - [ ] 3.3.2 Verify navigates to watchlist page
  - [ ] 3.3.3 Verify scrolls to correct ticker row
  - [ ] 3.3.4 Verify row expands (if implemented)
  - **Time**: 5 min

### 4.0 Portfolio Visual Enhancement (Frontend)

- [ ] 4.1 Add color coding to PortfolioOverview rows
  - [ ] 4.1.1 Calculate gain/loss from position.total_gain
  - [ ] 4.1.2 Apply text color to change % column
  - [ ] 4.1.3 Green for positive (text-green-600 dark:text-green-400)
  - [ ] 4.1.4 Red for negative (text-red-600 dark:text-red-400)
  - [ ] 4.1.5 Gray/muted for zero/neutral
  - **Time**: 8 min

- [ ] 4.2 Add subtle row background tint
  - [ ] 4.2.1 Very subtle green tint for positive rows (bg-green-50/30 dark:bg-green-950/10)
  - [ ] 4.2.2 Very subtle red tint for negative rows (bg-red-50/30 dark:bg-red-950/10)
  - [ ] 4.2.3 Ensure hover state still visible
  - [ ] 4.2.4 Test in both light and dark mode
  - **Time**: 10 min

- [ ] 4.3 Visual polish and accessibility
  - [ ] 4.3.1 Ensure sufficient contrast ratios (WCAG AA)
  - [ ] 4.3.2 Test with screen reader (gains announced correctly)
  - [ ] 4.3.3 Add up/down arrow icons for change column
  - **Time**: 7 min

### 5.0 Market News on Dashboard (Frontend)

- [ ] 5.1 Create MarketNewsCard component
  - [ ] 5.1.1 Create frontend/components/dashboard/MarketNewsCard.tsx
  - [ ] 5.1.2 Use useMarketNews hook (already exists)
  - [ ] 5.1.3 Show top 5 headlines in compact card
  - [ ] 5.1.4 Display: headline, source, time ago, sentiment badge
  - [ ] 5.1.5 Click headline opens article in new tab
  - [ ] 5.1.6 Add loading and error states
  - [ ] 5.1.7 Match dashboard card styling (consistent with other cards)
  - **Time**: 20 min

- [ ] 5.2 Integrate MarketNewsCard into dashboard
  - [ ] 5.2.1 Import MarketNewsCard in dashboard/page.tsx
  - [ ] 5.2.2 Add card to dashboard grid layout
  - [ ] 5.2.3 Position below market overview, above portfolio
  - [ ] 5.2.4 Ensure responsive layout (mobile, tablet, desktop)
  - **Time**: 8 min

- [ ] 5.3 Test market news integration
  - [ ] 5.3.1 Verify news loads on dashboard
  - [ ] 5.3.2 Test clicking headlines (opens in new tab)
  - [ ] 5.3.3 Verify sentiment badges display correctly
  - [ ] 5.3.4 Test loading states
  - **Time**: 5 min

### 6.0 Remove News Page (Frontend Cleanup)

- [ ] 6.1 Remove /news page and route
  - [ ] 6.1.1 Delete frontend/app/news/page.tsx
  - [ ] 6.1.2 Check for frontend/app/news/layout.tsx and delete if exists
  - [ ] 6.1.3 Verify no other files in app/news/ directory
  - **Time**: 3 min

- [ ] 6.2 Remove news navigation link
  - [ ] 6.2.1 Find navigation component (layout.tsx or separate nav file)
  - [ ] 6.2.2 Remove "News" link from navigation menu
  - [ ] 6.2.3 Update navigation order if needed
  - **Time**: 5 min

- [ ] 6.3 Clean up unused news hooks/utilities
  - [ ] 6.3.1 Check useNews.ts exports (keep useMarketNews for dashboard)
  - [ ] 6.3.2 Remove useWatchlistNews and usePortfolioNews if unused
  - [ ] 6.3.3 Keep underlying API functions (fetchMarketNews, etc.)
  - [ ] 6.3.4 Search codebase for remaining /news references
  - **Time**: 10 min

- [ ] 6.4 Update any documentation/links
  - [ ] 6.4.1 Search docs for /news page references
  - [ ] 6.4.2 Update README if /news is mentioned
  - [ ] 6.4.3 Check for broken internal links
  - **Time**: 5 min

### 7.0 Integration Testing & Verification

- [ ] 7.1 End-to-end workflow test
  - [ ] 7.1.1 Add new position to portfolio
  - [ ] 7.1.2 Verify ticker auto-appears in watchlist with badge
  - [ ] 7.1.3 Click ticker in portfolio, verify navigates to watchlist
  - [ ] 7.1.4 Verify scrolls to correct ticker and expands
  - [ ] 7.1.5 Verify portfolio has color coding
  - [ ] 7.1.6 Check dashboard shows market news
  - [ ] 7.1.7 Verify /news page returns 404
  - **Time**: 15 min

- [ ] 7.2 Browser automation testing
  - [ ] 7.2.1 Screenshot dashboard with market news card
  - [ ] 7.2.2 Screenshot portfolio with color coding
  - [ ] 7.2.3 Screenshot watchlist with portfolio indicators
  - [ ] 7.2.4 Test navigation flow via interact.js
  - [ ] 7.2.5 Monitor console for errors
  - **Time**: 10 min

- [ ] 7.3 Backend tests
  - [ ] 7.3.1 Run: pytest backend/tests/ -v
  - [ ] 7.3.2 Ensure all portfolio/watchlist tests pass
  - [ ] 7.3.3 Check coverage for sync function
  - **Time**: 5 min

- [ ] 7.4 Quality checks
  - [ ] 7.4.1 Run: ~/portfolio-ai/scripts/lint.sh
  - [ ] 7.4.2 Fix any ruff or mypy errors
  - [ ] 7.4.3 Verify no new TODOs or debug code
  - [ ] 7.4.4 Check file sizes (<500 lines)
  - **Time**: 10 min

---

## Verification Checklist (MANDATORY before "COMPLETE ✅")

- [ ] **Functional**:
  - [ ] Portfolio tickers auto-sync to watchlist
  - [ ] Watchlist shows portfolio indicator badge
  - [ ] Clicking portfolio ticker navigates to watchlist
  - [ ] Portfolio has green/red color coding
  - [ ] Dashboard shows market news card
  - [ ] /news page removed (404)

- [ ] **Tests**:
  - [ ] Backend tests pass (pytest)
  - [ ] Portfolio-watchlist sync tests added
  - [ ] Manual UI testing complete

- [ ] **Quality**:
  - [ ] scripts/lint.sh passes
  - [ ] No new type errors
  - [ ] Files within size limits

- [ ] **Clean**:
  - [ ] No debug console.logs
  - [ ] No commented code
  - [ ] No broken links

- [ ] **UX**:
  - [ ] Navigation smooth and intuitive
  - [ ] Color coding accessible (contrast)
  - [ ] Loading states handled
  - [ ] Error states handled

---

## Success Criteria

✅ Portfolio ticker appears in watchlist automatically with indicator
✅ Clicking portfolio ticker smoothly navigates to watchlist row
✅ Portfolio has clear visual indicators for gains/losses
✅ Dashboard shows relevant market news headlines
✅ No /news page exists, no broken navigation
✅ All integrations work seamlessly together

---

## Notes

- **Database Safety**: NO cascade deletes between portfolio and watchlist
- **Sync Strategy**: One-way, additive only (portfolio → watchlist)
- **User Control**: Users can manually remove portfolio-sourced tickers from watchlist
- **Performance**: Sync is fast (simple INSERT...ON CONFLICT), no user-facing delay
- **Accessibility**: Color coding supplemented with icons/text for colorblind users

**Estimated Total Time**: 3-4 hours

---

## Implementation Notes

### Portfolio Badge Logic (Fixed)
Initially, the portfolio badge was shown based on the `source` field (historical). This was incorrect because:
- Items synced from portfolio kept `source='portfolio'` even after being removed from portfolio
- Badge showed "Portfolio" for tickers no longer in the portfolio

**Fix Applied**: Changed badge logic to check current portfolio state:
- Fetch current portfolio positions in WatchlistTable
- Show badge only if `portfolioSymbols.has(item.symbol)`
- Now accurately reflects what's in your portfolio RIGHT NOW

### Files Modified (Additional)
- `frontend/components/watchlist/WatchlistTable.tsx` - Fixed portfolio badge logic
- `backend/app/watchlist/priority.py` - Fixed None value handling
- `frontend/components/dashboard/` - Fixed directory permissions (755)
- `package.json` - Added date-fns dependency

### Database Changes
- Migration 022: Added `source` column with check constraint
- Created index on `source` for efficient filtering
- 7 new test cases in `test_watchlist_sync.py` (all passing)

**Total Time**: ~4 hours (including bug fixes and testing)
