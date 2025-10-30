# Task List: Watchlist Page Fixes - Timezone Display and Sparkline Data

**PRD**: `prd-watchlist-fixes.md`
**Status**: Ready for Implementation
**Completion**: 0% (Not started)
**Effort to Complete**: Medium
**Last Updated**: 2025-10-30

**Note on Effort Levels**:
- **Low**: 1-2 hours of straightforward work
- **Medium**: Half day of work with some complexity
- **High**: Full day or more, significant complexity

---

## Summary

**✅ COMPLETE:**
- (None yet)

**🔄 IN PROGRESS:**
- (Not started)

**⚠️ NEXT STEPS:**
1. Begin with Task 1.0
2. Follow checklist sequentially
3. Update this summary as work progresses

**EFFORT TO COMPLETE:** Medium

---

## Relevant Files

### Files to Create (2 new files)

- `backend/migrations/003_add_display_timezone.sql` (~20 lines) - Migration to add display_timezone column to user_preferences
- `frontend/components/watchlist/SparklineWithHistory.tsx` (~80 lines) - Component to fetch and display real historical score data

### Files to Update (4 files)

- `backend/app/api/preferences.py` - Add display_timezone field to Pydantic models and CRUD operations
- `frontend/components/watchlist/WatchlistTable.tsx` - Replace hardcoded sparkline, add timezone-aware formatDate
- `frontend/app/settings/page.tsx` - Add timezone selector in Display Preferences section
- `frontend/lib/api/preferences.ts` - Add display_timezone to TypeScript types

### Notes

- This project uses DuckDB with SQL migrations in `backend/migrations/` directory
- Migration files follow pattern: `NNN_description.sql` (e.g., `003_add_display_timezone.sql`)
- Existing migrations: 001 (schema_migrations), 002 (watchlist_preferences)
- Backend uses Pydantic for API models with strict type validation
- Frontend uses React Query for data fetching with automatic caching
- Existing `useScoreHistory` hook and `fetchScoreHistory` API confirmed working
- Use `pytest tests/` to run all tests
- Use `mypy app/ --strict` to verify type safety
- Use `scripts/lint.sh` to run linting and formatting checks

---

## Tasks

- [x] 1.0 Add Timezone Preference to Backend Database and API
  - [x] 1.1 Create database migration file for display_timezone column
    - [x] 1.1.1 Create `backend/migrations/003_add_display_timezone.sql` file
    - [x] 1.1.2 Add ALTER TABLE statement to add `display_timezone VARCHAR` column with default `'America/New_York'`
    - [x] 1.1.3 Add UPDATE statement to set default timezone for existing rows
    - [x] 1.1.4 Add CHECK constraint to validate timezone values (6 USA timezones only)
  - [x] 1.2 Run migration to apply database changes
    - [x] 1.2.1 Start backend server to trigger automatic migration
    - [x] 1.2.2 Verify migration applied successfully via logs
    - [x] 1.2.3 Query user_preferences table to confirm display_timezone column exists
  - [x] 1.3 Update PreferencesResponse Pydantic model
    - [x] 1.3.1 Add `display_timezone: str` field to PreferencesResponse class (line ~36)
    - [x] 1.3.2 Add Field descriptor with description "User's preferred display timezone"
  - [x] 1.4 Update PreferencesUpdate Pydantic model
    - [x] 1.4.1 Add `display_timezone: str | None` field to PreferencesUpdate class (line ~60)
    - [x] 1.4.2 Add Field descriptor with validation constraints (must be one of 6 USA timezones)
    - [x] 1.4.3 Add timezone validator function to reject invalid IANA names
  - [x] 1.5 Update _get_or_create_preferences function
    - [x] 1.5.1 Add display_timezone to SELECT query (line ~67)
    - [x] 1.5.2 Add display_timezone to INSERT statement with default 'America/New_York' (line ~80-86)
    - [x] 1.5.3 Add display_timezone to default return dict (line ~107-122)
  - [x] 1.6 Update GET preferences endpoint
    - [x] 1.6.1 Add display_timezone cast to PreferencesResponse return (line ~141)
  - [x] 1.7 Update POST preferences endpoint
    - [x] 1.7.1 Add display_timezone to update logic (line ~174)
    - [x] 1.7.2 Add display_timezone to UPDATE SQL statement (line ~187)
    - [x] 1.7.3 Add display_timezone to PreferencesResponse return (line ~223)
  - [x] 1.8 Write unit tests for timezone preference
    - [x] 1.8.1 Write test for GET /api/preferences returns display_timezone field
    - [x] 1.8.2 Write test for POST /api/preferences updates display_timezone
    - [x] 1.8.3 Write test for invalid timezone rejection (e.g., 'Europe/London')
    - [x] 1.8.4 Write test for default timezone on new user creation
  - [x] 1.9 Run backend tests and fix any failures
    - [x] 1.9.1 Run `pytest tests/api/test_preferences.py -v`
    - [x] 1.9.2 Fix any failing tests
    - [x] 1.9.3 Run `mypy app/api/preferences.py --strict` and fix type errors

- [ ] 2.0 Create SparklineWithHistory Component with Real Data
  - [ ] 2.1 Create SparklineWithHistory component file
    - [ ] 2.1.1 Create `frontend/components/watchlist/SparklineWithHistory.tsx` file
    - [ ] 2.1.2 Add "use client" directive at top
    - [ ] 2.1.3 Import useScoreHistory hook from @/lib/hooks/useWatchlist
    - [ ] 2.1.4 Import Sparkline component from @/components/ui/sparkline
  - [ ] 2.2 Define component props interface
    - [ ] 2.2.1 Create SparklineWithHistoryProps interface with itemId, width, height props
    - [ ] 2.2.2 Add optional className prop for styling flexibility
  - [ ] 2.3 Implement component logic to fetch historical data
    - [ ] 2.3.1 Call useScoreHistory(itemId) hook to fetch 7-day history
    - [ ] 2.3.2 Extract data, isLoading, error from hook response
  - [ ] 2.4 Add loading state UI
    - [ ] 2.4.1 Return skeleton placeholder during isLoading (gray rectangle with pulse animation)
  - [ ] 2.5 Add error/empty state UI
    - [ ] 2.5.1 Return "—" placeholder if error or no data available
  - [ ] 2.6 Transform historical data for sparkline
    - [ ] 2.6.1 Map history array to extract overall scores: data.map(h => h.overall)
    - [ ] 2.6.2 Sort by timestamp ascending (oldest to newest)
    - [ ] 2.6.3 Limit to last 7 data points if more exist
  - [ ] 2.7 Render Sparkline with real data
    - [ ] 2.7.1 Pass transformed data array to <Sparkline> component
    - [ ] 2.7.2 Pass width and height props
    - [ ] 2.7.3 Add aria-label for accessibility
  - [ ] 2.8 Add TypeScript types and exports
    - [ ] 2.8.1 Ensure all props are properly typed
    - [ ] 2.8.2 Export SparklineWithHistory as named export

- [ ] 3.0 Update WatchlistTable to Use Sparkline and Timezone
  - [ ] 3.1 Import SparklineWithHistory component
    - [ ] 3.1.1 Add import statement at top of WatchlistTable.tsx
  - [ ] 3.2 Add timezone utility functions
    - [ ] 3.2.1 Create getTimezoneAbbreviation function (extracts EST, CST, etc. from Date + timezone)
    - [ ] 3.2.2 Use Intl.DateTimeFormat with timeZoneName: 'short' to extract abbreviation
  - [ ] 3.3 Fetch user timezone preference
    - [ ] 3.3.1 Import usePreferences hook from @/lib/hooks/usePreferences
    - [ ] 3.3.2 Call usePreferences() in component body
    - [ ] 3.3.3 Extract display_timezone from preferences data
    - [ ] 3.3.4 Fallback to 'America/New_York' if preference not loaded
  - [ ] 3.4 Update formatDate function to accept timezone parameter
    - [ ] 3.4.1 Change formatDate signature to (dateStr: string, timezone: string)
    - [ ] 3.4.2 Use toLocaleString with timeZone option instead of toLocaleDateString
    - [ ] 3.4.3 Call getTimezoneAbbreviation to get abbreviation (e.g., "EST")
    - [ ] 3.4.4 Append abbreviation to formatted date string
  - [ ] 3.5 Replace hardcoded sparkline with SparklineWithHistory
    - [ ] 3.5.1 Find line ~334 with hardcoded data array
    - [ ] 3.5.2 Replace <Sparkline data={[...]} /> with <SparklineWithHistory itemId={item.id} />
    - [ ] 3.5.3 Pass width={80} height={24} props
  - [ ] 3.6 Update formatDate calls to pass timezone
    - [ ] 3.6.1 Find all formatDate(item.updated_at) calls
    - [ ] 3.6.2 Update to formatDate(item.updated_at, userTimezone)
  - [ ] 3.7 Test WatchlistTable in browser
    - [ ] 3.7.1 Start frontend dev server: npm run dev
    - [ ] 3.7.2 Navigate to /watchlist page
    - [ ] 3.7.3 Verify sparklines show real data (not hardcoded dummy data)
    - [ ] 3.7.4 Verify timestamps show timezone abbreviation (e.g., "Oct 30, 3:21 PM EST")

- [ ] 4.0 Add Timezone Selector to Settings Page
  - [ ] 4.1 Update frontend preferences TypeScript types
    - [ ] 4.1.1 Open `frontend/lib/api/preferences.ts`
    - [ ] 4.1.2 Add `display_timezone: string` to PreferencesResponse interface
    - [ ] 4.1.3 Add `display_timezone?: string` to PreferencesUpdate interface
  - [ ] 4.2 Create timezone options constant
    - [ ] 4.2.1 Define TIMEZONE_OPTIONS object in settings/page.tsx
    - [ ] 4.2.2 Map IANA names to friendly labels (e.g., 'America/New_York': 'Eastern Time (EST/EDT)')
    - [ ] 4.2.3 Include all 6 USA timezones
  - [ ] 4.3 Add displayTimezone state variable
    - [ ] 4.3.1 Add useState hook: const [displayTimezone, setDisplayTimezone] = useState('America/New_York')
    - [ ] 4.3.2 Update useEffect to set displayTimezone from preferences.display_timezone
  - [ ] 4.4 Add displayTimezone to hasChanges function
    - [ ] 4.4.1 Add displayTimezone !== preferences.display_timezone check
  - [ ] 4.5 Add displayTimezone to handleSave mutation
    - [ ] 4.5.1 Include display_timezone: displayTimezone in updatePreferences.mutate payload
  - [ ] 4.6 Create Display Preferences Card in JSX
    - [ ] 4.6.1 Add new Card component after Watchlist Preferences section
    - [ ] 4.6.2 Set CardTitle to "Display Preferences"
    - [ ] 4.6.3 Set CardDescription to "Customize how data is displayed"
  - [ ] 4.7 Add timezone select dropdown
    - [ ] 4.7.1 Add Label with text "Timezone"
    - [ ] 4.7.2 Add Select component (import from @/components/ui/select)
    - [ ] 4.7.3 Map TIMEZONE_OPTIONS to SelectItem components
    - [ ] 4.7.4 Bind value={displayTimezone} and onValueChange={setDisplayTimezone}
  - [ ] 4.8 Test timezone selector in browser
    - [ ] 4.8.1 Navigate to /settings page
    - [ ] 4.8.2 Verify "Display Preferences" section appears
    - [ ] 4.8.3 Change timezone dropdown to "Pacific Time (PST/PDT)"
    - [ ] 4.8.4 Click "Save Changes" button
    - [ ] 4.8.5 Verify success toast appears
    - [ ] 4.8.6 Navigate to /watchlist page
    - [ ] 4.8.7 Verify timestamps now show "PST" instead of "EST"

- [ ] 5.0 Verification and Integration Testing
  - [ ] 5.1 Run full backend test suite
    - [ ] 5.1.1 Run `cd ~/portfolio-ai/backend && pytest tests/ -v`
    - [ ] 5.1.2 Fix any failing tests
    - [ ] 5.1.3 Verify 80%+ test coverage: `pytest tests/ --cov=app --cov-report=term-missing`
  - [ ] 5.2 Run backend type checking
    - [ ] 5.2.1 Run `mypy app/ --strict`
    - [ ] 5.2.2 Fix all type errors (target: zero errors)
  - [ ] 5.3 Run backend linting
    - [ ] 5.3.1 Run `~/portfolio-ai/scripts/lint.sh`
    - [ ] 5.3.2 Fix all linting errors
  - [ ] 5.4 Test end-to-end timezone change workflow
    - [ ] 5.4.1 Open browser to /settings
    - [ ] 5.4.2 Change timezone from EST to CST
    - [ ] 5.4.3 Save and verify success
    - [ ] 5.4.4 Navigate to /watchlist
    - [ ] 5.4.5 Verify all timestamps show "CST" abbreviation
    - [ ] 5.4.6 Verify times are correctly offset by 1 hour
  - [ ] 5.5 Test sparkline with new and old tickers
    - [ ] 5.5.1 Verify existing tickers (with 7+ days history) show populated sparklines
    - [ ] 5.5.2 Add a brand new ticker via "Add Ticker" button
    - [ ] 5.5.3 Verify new ticker shows placeholder sparkline (not enough history yet)
    - [ ] 5.5.4 Verify loading states display correctly during fetch
  - [ ] 5.6 Test stale data behavior remains correct
    - [ ] 5.6.1 Note current time and refresh interval setting (e.g., 5 minutes)
    - [ ] 5.6.2 Wait for 3x refresh interval (e.g., 15 minutes)
    - [ ] 5.6.3 Verify "(stale)" indicator appears next to price scores
    - [ ] 5.6.4 Click "Refresh" button
    - [ ] 5.6.5 Verify stale indicators disappear after refresh completes
  - [ ] 5.7 Test auto-refresh functionality
    - [ ] 5.7.1 Open /watchlist page and leave it open
    - [ ] 5.7.2 Wait for auto-refresh interval (default: 5 minutes)
    - [ ] 5.7.3 Verify page updates automatically without manual refresh
    - [ ] 5.7.4 Check browser console for no errors
  - [ ] 5.8 Cross-browser testing
    - [ ] 5.8.1 Test in Chrome: verify timezone abbreviation extraction works
    - [ ] 5.8.2 Test in Firefox: verify Intl.DateTimeFormat compatibility
    - [ ] 5.8.3 Test in Safari: verify sparkline rendering
  - [ ] 5.9 Performance testing
    - [ ] 5.9.1 Add 15+ items to watchlist
    - [ ] 5.9.2 Measure page load time (target: < 2 seconds)
    - [ ] 5.9.3 Verify React Query caching reduces redundant API calls
    - [ ] 5.9.4 Check Network tab: each sparkline should fetch history only once
  - [ ] 5.10 Update documentation
    - [ ] 5.10.1 Update REFACTOR_STATUS.md to mark timezone + sparkline features complete
    - [ ] 5.10.2 Add notes about timezone preference in API_REFERENCE.md
    - [ ] 5.10.3 Document SparklineWithHistory component usage

---

## Verification & Production Readiness

**MANDATORY before marking task "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All PRD requirements implemented
  - [ ] Sparkline displays real 7-day historical data
  - [ ] Timestamps show timezone abbreviation
  - [ ] Settings page has timezone selector
  - [ ] Timezone preference persists across sessions
  - [ ] Integration points working correctly
  - [ ] Zero known bugs or regressions

- [ ] **Test Coverage** (target: 80%+)
  - [ ] Unit tests written for timezone preference API
  - [ ] Unit tests for formatDate timezone logic
  - [ ] Integration tests for cross-module interactions
  - [ ] End-to-end test of timezone change workflow
  - [ ] All tests passing: `pytest tests/ -v`
  - [ ] Coverage verified: `pytest tests/ --cov=app --cov-report=term-missing`

- [ ] **Type Safety & Code Quality**
  - [ ] 100% type hints on all functions: `mypy app/ --strict` passes
  - [ ] Linting passes: `scripts/lint.sh` returns zero errors
  - [ ] Code formatting applied: `ruff format app/`
  - [ ] TypeScript types match backend Pydantic models
  - [ ] No `any` types in TypeScript

- [ ] **Clean Implementation (No Band-Aids)**
  - [ ] Timezone validation uses proper enum/constants (not magic strings)
  - [ ] formatDate function is pure (no side effects)
  - [ ] SparklineWithHistory handles all edge cases (loading, error, empty)
  - [ ] Migration is idempotent (can run multiple times safely)
  - [ ] No hardcoded timezone values (all come from user preference)

- [ ] **Documentation**
  - [ ] All public functions/classes have docstrings
  - [ ] REFACTOR_STATUS.md updated (mark features complete)
  - [ ] API_REFERENCE.md documents new display_timezone field
  - [ ] Migration file has clear description comment

- [ ] **Security & Performance**
  - [ ] SQL migration uses parameterized queries
  - [ ] Timezone values validated on backend (prevent injection)
  - [ ] React Query caching prevents excessive API calls
  - [ ] Page load time < 2 seconds with 15+ watchlist items

- [ ] **Operational Readiness**
  - [ ] Migration applies cleanly to existing database
  - [ ] Default timezone set for existing users
  - [ ] Clear error messages if timezone API fails
  - [ ] Manual end-to-end test via UI successful
  - [ ] No console errors in browser

**See**: `docs/core/DEVELOPMENT.md` → "Production Readiness Requirements" for complete checklist
