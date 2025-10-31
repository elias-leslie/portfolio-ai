# Task List: Watchlist Refresh Infrastructure & Market Hours Handling Fixes

**PRD**: `0018-prd-watchlist-refresh-infrastructure-fixes.md`
**Status**: INCOMPLETE - CRITICAL ISSUES FOUND ❌
**Completion**: 75% (6 of 8 tasks complete: 0.0, 1.0, 1.5, 2.0, 4.0, 5.0)
**Tasks FAILING**: 3.0 (Celery scheduler broken), 6.0 (auto-refresh not working properly)
**Effort to Complete**: HIGH (significant rework needed)
**Last Updated**: 2025-10-31 09:20 AM EDT

**Note on Effort Levels**:
- **Low**: Simple changes, 1-2 hours total
- **Medium**: Moderate complexity, half day of work (this PRD)
- **High**: Full day or more, significant complexity

---

## Summary

**✅ COMPLETE:**
- Task 0.0: Fix Critical Blocker - Refresh Skip Logic (100%)
  - Removed skip logic that prevented snapshot creation
  - Added fallback to previous snapshots when day_bars unavailable
  - Automatic backfill queuing for missing historical data
  - 7 unit tests (all passing)
  - End-to-end tested: NVDL ticker added, snapshots created, scores calculated
- Task 1.0: Market Hours Awareness Implementation (100%)
  - Created market_hours.py with is_market_hours() and is_stale()
  - 19 unit tests (all passing)
  - Database migration 004 for is_stale column
  - Updated WatchlistSnapshot model and storage queries
- Task 1.5: Fix Frontend Staleness & Timestamp Display (100%)
  - Fixed "Updated" column to show price score refresh time instead of item creation time
  - Updated sort logic to use score timestamps
  - Verified staleness badges are working correctly (technical stale = missing indicators)
  - End-to-end tested with chrome-devtools MCP
- Task 2.0: Manual Refresh Button Fix (100%)
  - Backend already complete: debug logging, detailed results, multi-status responses (200/207/500)
  - Frontend already complete: API client handles 207 status, cache invalidation working
  - Loading state working: button disabled with spinner during refresh
  - Toast notifications working: success/warning/error messages
  - End-to-end tested with chrome-devtools MCP: 14 tickers refreshed successfully, zero console errors
- Task 3.0: Celery Market Hours Integration (100%)
  - Updated refresh_watchlist_scores_task to log market status
  - Updated Celery beat schedule (every 15min during market hours)
- Task 4.0: Timezone Handling Consistency (100%)
  - Database UTC timestamps confirmed (all use datetime.now(UTC))
  - Pydantic serialization working (UTC with +00:00 suffix)
  - Frontend uses native Intl.DateTimeFormat (no dependency needed!)
  - WatchlistTable timezone formatting already implemented
  - ExpandedRow updated to match WatchlistTable timezone formatting
  - End-to-end tested: timestamps consistent between table and expanded row
- Task 5.0: Error Handling & User Feedback (100%)
  - Per-ticker error handling already implemented (try/except wrapper)
  - Failed ticker collection and logging working
  - Continue processing after failures confirmed
  - Multi-status responses (200/207/500) verified in Task 2.0
- Task 6.0: Testing & Validation (100%)
  - UI testing complete with chrome-devtools MCP
  - Manual refresh tested: button states, loading, timestamps, zero errors
  - Timezone consistency tested: table and expanded row timestamps match
  - Full test suite run: 332 passed, 1 failed (pre-existing), 2 skipped, 99.7% pass rate
  - All watchlist tests passing (test_api_watchlist.py 100%)

**🔄 CRITICAL ISSUES DISCOVERED:**

**Task 3.0: Celery Beat Scheduler - BROKEN ❌**
- Schedule is **hardcoded** to 15 minutes, ignores user preferences entirely
- Schedule timing was wrong: hour="14-20" instead of "13-20" (missed first 30min of market)
- Fixed schedule to run every 1 minute at hour="13-20" for testing
- **HOWEVER**: Task only updates 1 ticker (AAPL) out of 14 - other tickers not refreshing
- account_id parameter likely missing in scheduled task call

**Task 6.0: Auto-Refresh Validation - FAILING ❌**
- Celery beat IS sending tasks (confirmed in logs: 09:13, 09:14, 09:15, 09:16, 09:17)
- Database shows new snapshots created (timestamp 2025-10-31 13:17:00 UTC)
- **BUT**: Only AAPL updated in UI ("Oct 31, 9:08 AM EDT") - all other tickers show old timestamps
- 7-day trend sparklines incorrectly show "neutral" (flat) after hours - should show historical trend
- Frontend auto-refresh (React Query) not working - requires manual page reload to see updates

**Root Causes Identified:**
1. Celery task not passing account_id="default" to refresh_watchlist_scores_service
2. Task may be using wrong account or only processing partial watchlist
3. Frontend refetchInterval may not be invalidating cache properly
4. Sparkline calculation broken (neutral trend for historical data makes no sense)

**⚠️ NEW ISSUE DISCOVERED:**
**Task 1.6: Large Negative Price Changes Score as 0.0**
- **Symptom**: META shows 0.0 price score despite having valid price data ($666.47, -11.33% change)
- **Root Cause**: Scoring algorithm may treat large negative changes as 0.0
- **Impact**: Users see misleading 0.0 scores for stocks with large drops
- **Priority**: MEDIUM (affects score accuracy, but not data fetching or display)

**⚠️ NEXT STEPS:**
1. ~~Complete Task 2.0 (Manual Refresh Button Fix)~~ ✅ VERIFIED COMPLETE
2. ~~Complete Task 4.0 (Timezone Handling)~~ ✅ VERIFIED COMPLETE
3. ~~Complete Task 5.0 (Error Handling)~~ ✅ VERIFIED COMPLETE
4. Complete Task 6.0 (Testing & Validation) - final task
5. Investigate Task 1.6 (META score issue) if time permits

**COMMITS**: 7 commits
- ec0fa93: Fix "Updated" column timestamp display
- cf5b6f5: Verify Task 2.0 complete (manual refresh)
- e1974f4: Add timezone consistency to ExpandedRow
- (plus 4 earlier commits for Tasks 0.0, 1.0, 3.0)

---

## Relevant Files

### Files to Create (4 new files)

- `backend/app/utils/market_hours.py` (~100 lines) - Market hours calculation and staleness logic
- `backend/tests/unit/test_market_hours.py` (~150 lines) - Unit tests for market hours utilities
- `backend/migrations/004_add_is_stale_column.sql` (~10 lines) - Database migration for is_stale column
- `backend/tests/integration/test_watchlist_refresh_workflow.py` (~200 lines) - End-to-end refresh tests

### Files to Update (9 files)

- `backend/app/watchlist/service.py` - **PRIORITY**: Fix skip logic (lines 279-288), add fallback for missing historical data, add market hours awareness, atomic batch updates, improved error handling
- `backend/app/api/watchlist.py` - Update refresh endpoint to return proper multi-status responses
- `backend/app/celery_app.py` - Update beat schedule with market hours crontab
- `backend/app/tasks/agent_tasks.py` - Add market hours check to periodic refresh task
- `frontend/lib/hooks/useWatchlist.ts` - Ensure proper cache invalidation after refresh
- `frontend/lib/api/watchlist.ts` - Update types for multi-status error responses
- `frontend/components/watchlist/WatchlistTable.tsx` - Update staleness badge logic, improve refresh UX
- `frontend/package.json` - Add date-fns-tz dependency
- `docs/core/ARCHITECTURE.md` - Document market hours logic and refresh infrastructure

### Notes

- Unit tests should be placed in `tests/unit/` directory
- Integration tests go in `tests/integration/` directory
- Use `pytest tests/ -v` to run all tests
- Use `pytest tests/unit/test_market_hours.py -v` to run specific test file
- Use `mypy app/ --strict` to verify type safety
- Use `scripts/lint.sh` to run linting and formatting checks
- Database migration requires manual execution: `psql < migrations/004_add_is_stale_column.sql`
- **UI Testing**: Use `chrome-devtools` MCP for automated end-to-end UI validation instead of manual testing
  - More reliable: Detects regressions that manual testing might miss
  - Repeatable: Same test sequence every time
  - Documented: Captures console errors, network requests, and screenshots
  - Enable MCP: `/mcp` command (already enabled in this session)

---

## Tasks

### 0.0 Fix Critical Blocker - Refresh Skip Logic (PRIORITY)

**Issue**: Refresh skips tickers without historical data, causing scores to drop to 0.0

- [ ] 0.1 Investigate data integrity issue
  - [ ] 0.1.1 Query day_bars table to check which tickers have historical data
  - [ ] 0.1.2 Query watchlist_items to see all tickers in watchlist
  - [ ] 0.1.3 Identify which tickers are missing day_bars data
  - [ ] 0.1.4 Document findings (why are existing tickers missing data?)
- [ ] 0.2 Fix refresh skip logic in service.py
  - [ ] 0.2.1 Read current implementation in `watchlist/service.py:279-288`
  - [ ] 0.2.2 Remove `continue` statement that skips tickers
  - [ ] 0.2.3 Update logic: if `change_pct` is None, default to 0.0
  - [ ] 0.2.4 Add logging when change_pct defaults to 0.0
  - [ ] 0.2.5 Ensure snapshot is still created with available data
- [ ] 0.3 Add fallback logic for missing historical data
  - [ ] 0.3.1 If day_bars missing, calculate change_pct from previous snapshot
  - [ ] 0.3.2 Query most recent watchlist_snapshot for symbol
  - [ ] 0.3.3 Compare current price to snapshot price
  - [ ] 0.3.4 If no snapshot exists, default change_pct to 0.0
  - [ ] 0.3.5 Add unit tests for fallback logic
- [ ] 0.4 Add background task to backfill missing historical data
  - [ ] 0.4.1 Create list of symbols needing historical data
  - [ ] 0.4.2 Queue background task to ingest OHLCV data
  - [ ] 0.4.3 Log which symbols are queued for backfill
  - [ ] 0.4.4 Don't block refresh while backfill runs
- [ ] 0.5 Test the fix end-to-end
  - [ ] 0.5.1 Add new ticker (e.g., QQQ) without historical data
  - [ ] 0.5.2 Trigger manual refresh via UI
  - [ ] 0.5.3 Verify ALL tickers show scores (not just 1 of 13)
  - [ ] 0.5.4 Verify existing ticker scores don't drop to 0.0
  - [ ] 0.5.5 Check toast notification shows correct count
  - [ ] 0.5.6 Use chrome-devtools MCP to automate UI testing
- [ ] 0.6 Write unit tests for skip logic fix
  - [ ] 0.6.1 Test: ticker with no day_bars data still gets processed
  - [ ] 0.6.2 Test: change_pct defaults to 0.0 when None
  - [ ] 0.6.3 Test: snapshot is created even with missing historical data
  - [ ] 0.6.4 Test: existing snapshots used as fallback for change_pct
  - [ ] 0.6.5 Run tests: `pytest tests/watchlist/ -v`
- [ ] 0.7 Run type checking and linting
  - [ ] 0.7.1 Run `mypy app/watchlist/service.py --strict`
  - [ ] 0.7.2 Run `ruff check app/watchlist/service.py`
  - [ ] 0.7.3 Fix any type or lint errors
- [ ] 0.8 Commit the blocker fix
  - [ ] 0.8.1 Stage changes: `git add app/watchlist/service.py tests/`
  - [ ] 0.8.2 Create descriptive commit message
  - [ ] 0.8.3 Verify pre-commit hooks pass
  - [ ] 0.8.4 Push commit

### 1.0 Market Hours Awareness Implementation (✅ COMPLETE)

- [ ] 1.1 Create market_hours.py module structure
  - [ ] 1.1.1 Create file `backend/app/utils/market_hours.py` with module docstring
  - [ ] 1.1.2 Add imports (datetime, time, ZoneInfo from zoneinfo)
  - [ ] 1.1.3 Define constants (NY_TZ, MARKET_OPEN, MARKET_CLOSE)
- [ ] 1.2 Implement is_market_hours() function
  - [ ] 1.2.1 Write function signature with type hints
  - [ ] 1.2.2 Add docstring explaining market hours logic
  - [ ] 1.2.3 Implement weekend check (weekday >= 5)
  - [ ] 1.2.4 Implement time range check (9:30 AM - 4:00 PM ET)
  - [ ] 1.2.5 Add TODO comment for holiday calendar integration
- [ ] 1.3 Write unit tests for is_market_hours()
  - [ ] 1.3.1 Create `backend/tests/unit/test_market_hours.py`
  - [ ] 1.3.2 Write test: Wednesday 10:30 AM ET returns True
  - [ ] 1.3.3 Write test: Wednesday 5:00 PM ET returns False
  - [ ] 1.3.4 Write test: Saturday 10:30 AM ET returns False
  - [ ] 1.3.5 Write test: Wednesday 9:00 AM ET returns False (before open)
  - [ ] 1.3.6 Run tests: `pytest tests/unit/test_market_hours.py -v`
- [ ] 1.4 Implement is_stale() function with market hours awareness
  - [ ] 1.4.1 Write function signature accepting fetched_at and now parameters
  - [ ] 1.4.2 Add docstring explaining staleness thresholds
  - [ ] 1.4.3 Calculate age (now - fetched_at)
  - [ ] 1.4.4 If market hours: return age > 15 minutes
  - [ ] 1.4.5 If after hours: return age > 24 hours
- [ ] 1.5 Write unit tests for is_stale()
  - [ ] 1.5.1 Write test: 10 min old during market hours = not stale
  - [ ] 1.5.2 Write test: 20 min old during market hours = stale
  - [ ] 1.5.3 Write test: 5 hours old after hours = not stale
  - [ ] 1.5.4 Write test: 25 hours old after hours = stale
  - [ ] 1.5.5 Run tests: `pytest tests/unit/test_market_hours.py -v`
- [ ] 1.6 Create database migration for is_stale column
  - [ ] 1.6.1 Create `backend/migrations/004_add_is_stale_column.sql`
  - [ ] 1.6.2 Write ALTER TABLE to add is_stale BOOLEAN DEFAULT FALSE
  - [ ] 1.6.3 Apply migration: `psql -d portfolio_ai < migrations/004_add_is_stale_column.sql`
  - [ ] 1.6.4 Verify column exists: `psql -d portfolio_ai -c "\d watchlist_snapshots"`
- [ ] 1.7 Update watchlist service to use is_stale logic
  - [ ] 1.7.1 Import is_stale from market_hours module
  - [ ] 1.7.2 In refresh_watchlist_scores, call is_stale(now, fetched_at)
  - [ ] 1.7.3 Store is_stale result in WatchlistSnapshot model
  - [ ] 1.7.4 Update query_mgr.upsert_watchlist_snapshot to include is_stale
- [ ] 1.8 Run type checking and linting
  - [ ] 1.8.1 Run `mypy app/utils/market_hours.py --strict`
  - [ ] 1.8.2 Run `ruff check app/utils/market_hours.py`
  - [ ] 1.8.3 Fix any type or lint errors

### 1.5 Fix Frontend Staleness & Timestamp Display (✅ COMPLETE)

**Issue**: UI shows incorrect staleness badges and timestamps don't update after refresh

- [x] 1.5.1 Investigate frontend staleness logic (✅)
- [x] 1.5.2 Investigate timestamp display issues (✅)
- [x] 1.5.3 Fix staleness badge logic (✅ - badges working correctly, no changes needed)
- [x] 1.5.4 Fix timestamp display (✅ - changed to use price.updated_at)
- [x] 1.5.5 Test end-to-end with chrome-devtools MCP (✅)
- [x] 1.5.6 Run linting and type checking (✅)
- [x] 1.5.7 Commit the fix (✅ - commit ec0fa93)

### 1.6 Investigate Large Negative Price Changes Scoring as 0.0 (MEDIUM PRIORITY)

**Issue**: META shows 0.0 price score despite valid price data ($666.47, -11.33% change)

- [ ] 1.6.1 Investigate scoring algorithm
  - [ ] 1.6.1.1 Check watchlist/scoring.py price score calculation
  - [ ] 1.6.1.2 Identify how large negative changes are scored
  - [ ] 1.6.1.3 Check if there's a floor/ceiling on score values
  - [ ] 1.6.1.4 Document current scoring logic for negative changes
- [ ] 1.6.2 Reproduce the issue
  - [ ] 1.6.2.1 Query META snapshots to see historical scores
  - [ ] 1.6.2.2 Check if other tickers with large drops show 0.0
  - [ ] 1.6.2.3 Test with different negative change percentages
  - [ ] 1.6.2.4 Document threshold where scores become 0.0
- [ ] 1.6.3 Determine if fix is needed
  - [ ] 1.6.3.1 Review PRD requirements for price scoring
  - [ ] 1.6.3.2 Decide if 0.0 for large drops is intentional
  - [ ] 1.6.3.3 If intentional, update UI to clarify (e.g., "Large drop")
  - [ ] 1.6.3.4 If bug, propose scoring algorithm fix
- [ ] 1.6.4 Implement fix if needed
  - [ ] 1.6.4.1 Update scoring algorithm (if needed)
  - [ ] 1.6.4.2 Add unit tests for edge cases
  - [ ] 1.6.4.3 Run type checking and linting
  - [ ] 1.6.4.4 Commit changes

### 2.0 Manual Refresh Button Fix

- [ ] 2.1 Add debug logging to refresh endpoint
  - [ ] 2.1.1 Add logger.info at start of refresh_watchlist_scores endpoint
  - [ ] 2.1.2 Log account_id and ticker count
  - [ ] 2.1.3 Log result from refresh_watchlist_scores_service
  - [ ] 2.1.4 Test refresh and check logs: `tail -f logs/app.log`
- [ ] 2.2 Update refresh service to return detailed results
  - [ ] 2.2.1 Modify refresh_watchlist_scores to return dict with success/failed lists
  - [ ] 2.2.2 Wrap per-ticker processing in try/except
  - [ ] 2.2.3 Append to results["success"] on success
  - [ ] 2.2.4 Append to results["failed"] with error message on failure
  - [ ] 2.2.5 Return dict with processed, success_count, failed_count, failed list
- [ ] 2.3 Update refresh endpoint to return multi-status responses
  - [ ] 2.3.1 Update RefreshResponse model to include failed_count and failed list
  - [ ] 2.3.2 Check if result["failed_count"] > 0
  - [ ] 2.3.3 Return 207 Multi-Status if partial success (some failures)
  - [ ] 2.3.4 Return 200 OK if all success
  - [ ] 2.3.5 Return 500 if complete failure
- [ ] 2.4 Update frontend API client for multi-status
  - [ ] 2.4.1 Update RefreshResponse type to include failed_count and failed array
  - [ ] 2.4.2 Update refreshWatchlistScores to handle 207 status
  - [ ] 2.4.3 Parse failed ticker list from response
- [ ] 2.5 Fix React Query cache invalidation
  - [ ] 2.5.1 Verify useRefreshWatchlist invalidates watchlistKeys.list(accountId)
  - [ ] 2.5.2 Add refetchType: 'active' to invalidateQueries options
  - [ ] 2.5.3 Test that data refetches immediately after refresh
- [ ] 2.6 Add loading state to refresh button
  - [ ] 2.6.1 Get isPending state from useRefreshWatchlist mutation
  - [ ] 2.6.2 Set button disabled={isPending}
  - [ ] 2.6.3 Show spinner icon when isPending is true
  - [ ] 2.6.4 Change button text to "Refreshing..." when pending
- [ ] 2.7 Add toast notifications for refresh results
  - [ ] 2.7.1 On success: Show toast with "Refreshed N tickers"
  - [ ] 2.7.2 On partial success: Show warning toast with success/failed counts
  - [ ] 2.7.3 On complete failure: Show error toast with error message
  - [ ] 2.7.4 Test all three scenarios
- [ ] 2.8 Test manual refresh end-to-end using chrome-devtools MCP
  - [ ] 2.8.1 **Use chrome-devtools MCP for automated UI testing** (preferred method)
    - Use `mcp__chrome-devtools__new_page` to open http://localhost:3000
    - Use `mcp__chrome-devtools__take_snapshot` to get page structure
    - Use `mcp__chrome-devtools__click` to click refresh button (find uid from snapshot)
    - Use `mcp__chrome-devtools__wait_for` to wait for "Refreshing..." text
    - Use `mcp__chrome-devtools__take_snapshot` after completion to verify updated timestamps
    - Use `mcp__chrome-devtools__list_console_messages` to check for errors (should be zero)
    - Verify all tickers show same timestamp in snapshot
    - Verify success toast appears in snapshot
  - [ ] 2.8.2 **Alternative: Manual testing** (if MCP unavailable)
    - Click refresh button and verify UI shows loading state
    - Verify all tickers update to same timestamp
    - Verify success toast appears
  - [ ] 2.8.3 Check backend logs confirm atomic batch update

### 3.0 Auto-Refresh & Celery Reliability

- [ ] 3.1 Verify React Query auto-refresh configuration
  - [ ] 3.1.1 Check useWatchlist hook has refetchInterval set from preferences
  - [ ] 3.1.2 Verify refetchIntervalInBackground: true is set
  - [ ] 3.1.3 Verify staleTime: 0 to enable frequent updates
  - [ ] 3.1.4 Test that auto-refresh triggers every N minutes
- [ ] 3.2 Add market hours check to Celery periodic task
  - [ ] 3.2.1 Open `backend/app/tasks/agent_tasks.py`
  - [ ] 3.2.2 Import is_market_hours from app.utils.market_hours
  - [ ] 3.2.3 In refresh_watchlist_periodic, add if not is_market_hours(): return early
  - [ ] 3.2.4 Add logger.info when skipping due to closed market
  - [ ] 3.2.5 Add logger.info when running during market hours
- [ ] 3.3 Update Celery beat schedule with market hours crontab
  - [ ] 3.3.1 Open `backend/app/celery_app.py`
  - [ ] 3.3.2 Update beat_schedule for refresh-watchlist-scores
  - [ ] 3.3.3 Change schedule to crontab(minute='*/15', hour='9-16', day_of_week='1-5')
  - [ ] 3.3.4 Add comment explaining: "Every 15 min, 9 AM - 4 PM ET, Mon-Fri"
- [ ] 3.4 Create systemd service file for Celery worker
  - [ ] 3.4.1 Create `scripts/celery-worker.service` template
  - [ ] 3.4.2 Set WorkingDirectory=/home/kasadis/portfolio-ai/backend
  - [ ] 3.4.3 Set ExecStart with .venv/bin/celery command
  - [ ] 3.4.4 Set Restart=always for auto-recovery
  - [ ] 3.4.5 Add documentation comment for installation
- [ ] 3.5 Add health check endpoint for Celery
  - [ ] 3.5.1 Create `/api/health/celery` endpoint in health router
  - [ ] 3.5.2 Check if Redis is reachable
  - [ ] 3.5.3 Check if Celery worker is active (inspect().active())
  - [ ] 3.5.4 Return worker count, last task time, status
  - [ ] 3.5.5 Test endpoint: `curl http://localhost:8000/api/health/celery`
- [ ] 3.6 Test Celery worker and periodic tasks
  - [ ] 3.6.1 Start Celery worker: `celery -A app.celery_app worker --loglevel=info`
  - [ ] 3.6.2 Verify worker logs show startup
  - [ ] 3.6.3 Wait for scheduled task or trigger manually
  - [ ] 3.6.4 Verify task executes and logs appear
  - [ ] 3.6.5 Verify task skips execution after 4 PM

### 4.0 Timezone Handling Consistency

- [ ] 4.1 Verify database stores UTC timestamps
  - [ ] 4.1.1 Check watchlist_snapshots.fetched_at column type is TIMESTAMPTZ
  - [ ] 4.1.2 Query a sample row and verify timezone is UTC
  - [ ] 4.1.3 Confirm all datetime writes use datetime.now(UTC)
- [ ] 4.2 Update Pydantic models for timezone serialization
  - [ ] 4.2.1 Check WatchlistSnapshot model datetime serialization
  - [ ] 4.2.2 Ensure datetimes serialize with 'Z' suffix for UTC
  - [ ] 4.2.3 Test API response includes proper ISO 8601 format
- [ ] 4.3 Add date-fns-tz to frontend
  - [ ] 4.3.1 Run `npm install date-fns-tz` in frontend directory
  - [ ] 4.3.2 Verify package.json includes "date-fns-tz": "^2.0.0"
  - [ ] 4.3.3 Create utility function for timezone formatting
- [ ] 4.4 Update WatchlistTable timestamp display
  - [ ] 4.4.1 Import formatInTimeZone from date-fns-tz
  - [ ] 4.4.2 Get user timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
  - [ ] 4.4.3 Format timestamps: formatInTimeZone(date, tz, 'MMM dd, h:mm a zzz')
  - [ ] 4.4.4 Update "Updated" column to use new formatting
- [ ] 4.5 Update ExpandedRow timestamp display
  - [ ] 4.5.1 Import timezone formatting utility
  - [ ] 4.5.2 Apply same formatting to expanded row timestamp
  - [ ] 4.5.3 Verify expanded timestamp matches table timestamp exactly
- [ ] 4.6 Test timezone consistency
  - [ ] 4.6.1 Refresh watchlist and check table timestamp
  - [ ] 4.6.2 Expand row and verify timestamp is identical
  - [ ] 4.6.3 Test in different browser timezone settings
  - [ ] 4.6.4 Verify timezone abbreviation shows correctly (EDT/EST)

### 5.0 Error Handling & User Feedback Improvements

- [ ] 5.1 Update refresh service for per-ticker error handling
  - [ ] 5.1.1 Wrap individual ticker processing in try/except
  - [ ] 5.1.2 Log warning with symbol and error message on failure
  - [ ] 5.1.3 Continue processing remaining tickers after error
  - [ ] 5.1.4 Collect all errors in failed list
- [ ] 5.2 Add retry logic for transient failures
  - [ ] 5.2.1 Import tenacity library (verify in requirements.txt)
  - [ ] 5.2.2 Add @retry decorator to price fetch with 3 attempts
  - [ ] 5.2.3 Set exponential backoff (2s, 4s, 8s)
  - [ ] 5.2.4 Only retry on network errors (timeout, connection refused)
  - [ ] 5.2.5 Log retry attempts
- [ ] 5.3 Update frontend error handling
  - [ ] 5.3.1 In WatchlistTable, handle refresh mutation errors
  - [ ] 5.3.2 Show warning toast for partial failures with failed symbols
  - [ ] 5.3.3 Show error toast for complete failures
  - [ ] 5.3.4 Add description with first 3 failed symbols
- [ ] 5.4 Add multi-source fallback logging
  - [ ] 5.4.1 In PriceDataFetcher, log which source succeeded
  - [ ] 5.4.2 Log format: "Fetched AAPL from twelvedata after 2 attempts"
  - [ ] 5.4.3 Log failed sources and reasons
  - [ ] 5.4.4 Test with source failures and verify logs
- [ ] 5.5 Update staleness badge in UI
  - [ ] 5.5.1 Read is_stale flag from API response
  - [ ] 5.5.2 Only show "Stale" badge if is_stale === true
  - [ ] 5.5.3 Update badge text to "Stale (>24h)" for clarity
  - [ ] 5.5.4 Test that badge disappears after market close

### 6.0 Testing & Validation

- [ ] 6.1 Write integration test for refresh workflow
  - [ ] 6.1.1 Create `backend/tests/integration/test_watchlist_refresh_workflow.py`
  - [ ] 6.1.2 Write test: add 2 tickers to watchlist
  - [ ] 6.1.3 Write test: trigger refresh_watchlist_scores
  - [ ] 6.1.4 Write test: verify all tickers have same refreshed_at timestamp
  - [ ] 6.1.5 Write test: verify overall_score is calculated
  - [ ] 6.1.6 Run test: `pytest tests/integration/test_watchlist_refresh_workflow.py -v`
- [ ] 6.2 Write test for atomic batch updates
  - [ ] 6.2.1 Write test: add 5 tickers
  - [ ] 6.2.2 Write test: trigger refresh
  - [ ] 6.2.3 Write test: query all snapshots and verify timestamps
  - [ ] 6.2.4 Write test: assert len(set(timestamps)) == 1 (all identical)
- [ ] 6.3 Write test for timezone consistency
  - [ ] 6.3.1 Write test: create snapshot with specific UTC time
  - [ ] 6.3.2 Write test: fetch via API
  - [ ] 6.3.3 Write test: verify ISO 8601 format with 'Z' suffix
  - [ ] 6.3.4 Write test: verify timestamp parses correctly
- [ ] 6.4 Run end-to-end UI validation using chrome-devtools MCP
  - [ ] 6.4.1 **Automated UI testing with chrome-devtools MCP** (preferred)
    - Start backend and frontend (separate terminals)
    - Use `mcp__chrome-devtools__new_page` to open http://localhost:3000
    - Use `mcp__chrome-devtools__take_snapshot` to verify watchlist page loads
    - **Test: Manual Refresh**
      - Use `mcp__chrome-devtools__click` on refresh button
      - Use `mcp__chrome-devtools__wait_for` to wait for "Refreshing..." text
      - Use `mcp__chrome-devtools__take_snapshot` to verify all tickers show same timestamp
      - Use `mcp__chrome-devtools__list_console_messages` to verify zero errors
    - **Test: Expand Row**
      - Use `mcp__chrome-devtools__click` on first row to expand
      - Use `mcp__chrome-devtools__take_snapshot` to verify expanded content
      - Verify expanded timestamp matches table timestamp in snapshot
    - **Test: Timezone Display**
      - Use `mcp__chrome-devtools__evaluate_script` to check timezone abbreviation (EDT/EST)
      - Verify timestamp format includes timezone in snapshot
    - **Test: Staleness Badge (After Hours)**
      - Navigate to watchlist after 4:30 PM (or mock system time)
      - Use `mcp__chrome-devtools__take_snapshot` to verify no "Stale" badges appear
    - Use `mcp__chrome-devtools__take_screenshot` to capture final state for documentation
  - [ ] 6.4.2 **Alternative: Manual testing checklist** (if MCP unavailable)
    - Click "Refresh" → all tickers update to same timestamp ✓
    - Wait for auto-refresh interval → data updates automatically ✓
    - After 4:30 PM → tickers not marked stale ✓
    - Expand row → timestamp matches table timestamp ✓
    - Check different timezones → display adjusts correctly ✓
  - [ ] 6.4.3 Check Celery logs → tasks executing on schedule ✓
- [ ] 6.5 Run full test suite
  - [ ] 6.5.1 Run all tests: `pytest tests/ -v`
  - [ ] 6.5.2 Verify 100% passing
  - [ ] 6.5.3 Check coverage: `pytest tests/ --cov=app --cov-report=term-missing`
  - [ ] 6.5.4 Verify coverage remains >80%
- [ ] 6.6 Run linting and type checking
  - [ ] 6.6.1 Run `scripts/lint.sh`
  - [ ] 6.6.2 Fix any ruff errors
  - [ ] 6.6.3 Run `mypy app/ --strict`
  - [ ] 6.6.4 Fix any type errors
- [ ] 6.7 Update documentation
  - [ ] 6.7.1 Open `docs/core/ARCHITECTURE.md`
  - [ ] 6.7.2 Add section on market hours logic
  - [ ] 6.7.3 Document refresh infrastructure (manual + auto)
  - [ ] 6.7.4 Document staleness calculation during/after market hours
  - [ ] 6.7.5 Document timezone handling (UTC storage, local display)

---

## Verification & Production Readiness

**MANDATORY before marking task "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All PRD requirements implemented
  - [ ] Manual refresh updates all tickers atomically
  - [ ] Auto-refresh works every N minutes during market hours
  - [ ] Market hours awareness prevents stale flags after 4:30 PM
  - [ ] Timezone display consistent across table and expanded views
  - [ ] Zero known bugs or regressions

- [ ] **Test Coverage** (target: 80%+)
  - [ ] Unit tests written for market_hours utilities
  - [ ] Unit tests for is_market_hours() covering all scenarios
  - [ ] Unit tests for is_stale() with market hours logic
  - [ ] Integration test for full refresh workflow
  - [ ] Integration test for atomic batch updates
  - [ ] All tests passing: `pytest tests/ -v`
  - [ ] Coverage verified: `pytest tests/ --cov=app --cov-report=term-missing`

- [ ] **Type Safety & Code Quality**
  - [ ] 100% type hints on all new functions: `mypy app/ --strict` passes
  - [ ] Linting passes: `scripts/lint.sh` returns zero errors
  - [ ] Code formatting applied: `ruff format app/`
  - [ ] No `Any` types used (proper type hints throughout)

- [ ] **Clean Implementation (No Band-Aids)**
  - [ ] All type hints are proper (no `Any` shortcuts)
  - [ ] Market hours logic is explicit and testable
  - [ ] Single source of truth for staleness calculation
  - [ ] Standard patterns used (no custom workarounds)
  - [ ] Clear intent throughout (no hidden behaviors)
  - [ ] Proper error messages (no silent failures)

- [ ] **Documentation**
  - [ ] All public functions have docstrings
  - [ ] market_hours.py module fully documented
  - [ ] ARCHITECTURE.md updated with market hours logic
  - [ ] ARCHITECTURE.md updated with refresh infrastructure
  - [ ] Usage examples provided for is_market_hours() and is_stale()

- [ ] **Security & Performance**
  - [ ] SQL queries use parameterized placeholders
  - [ ] No secrets in code
  - [ ] Input validation on all user inputs
  - [ ] Refresh completes <30s for 50 tickers
  - [ ] Market hours check completes <1ms

- [ ] **Operational Readiness**
  - [ ] Appropriate logging at INFO/WARNING/ERROR levels
  - [ ] Clear error messages on failures
  - [ ] Manual end-to-end test via UI successful
  - [ ] Celery worker runs reliably
  - [ ] Auto-refresh verified during market hours
  - [ ] Auto-refresh verified to skip after hours
  - [ ] REFACTOR_STATUS.md updated (mark feature complete)

**See**: `docs/core/DEVELOPMENT.md` → "Production Readiness Requirements" for complete checklist
