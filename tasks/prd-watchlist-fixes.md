# PRD: Watchlist Page Fixes - Timezone Display and Sparkline Data

**Status**: Ready for Implementation
**Priority**: High
**Created**: 2025-10-30
**Complexity**: Medium

---

## Problem Statement

The Watchlist Intelligence Hub has several UX issues that need to be addressed:

1. **Sparkline charts show hardcoded dummy data** instead of actual 7-day historical scores
2. **Timestamp display lacks timezone context** - users don't know if times are in EST, UTC, or their local timezone
3. **No timezone preference setting** - users in different timezones need to configure their preferred display timezone
4. **Market hours not considered** - stale data indicators show correctly (3x refresh interval), but users need timezone context to understand why data is stale after market close

### Current Behavior

- Sparkline in WatchlistTable.tsx uses `[65, 68, 72, 70, 73, 71, overall]` hardcoded values
- Timestamps display using browser's default `toLocaleDateString("en-US")` with no timezone label
- No user preference for timezone display exists in backend or frontend
- Users see times like "Oct 30, 3:21 PM" without knowing the timezone

### Desired Behavior

- Sparkline displays actual 7-day historical overall scores from `watchlist_snapshots` table
- Timestamps display with timezone abbreviation (e.g., "Oct 30, 3:21 PM EST")
- Settings page includes timezone selector (USA timezones only: EST, CST, MST, PST, AKST, HST)
- Default timezone is America/New_York (EST)
- All timestamps across the app respect user's timezone preference

---

## Technical Requirements

### Backend Changes

#### 1. Add Timezone Preference to Database

**File**: `backend/app/storage/migrations/` (new migration file)

Add `display_timezone` column to `user_preferences` table:
- Column: `display_timezone` (VARCHAR)
- Default: `'America/New_York'` (EST)
- Allowed values: Standard IANA timezone names for USA

#### 2. Update Preferences API Models

**File**: `backend/app/api/preferences.py`

Update Pydantic models:
- Add `display_timezone: str` to `PreferencesResponse` (line ~36)
- Add `display_timezone: str | None` to `PreferencesUpdate` (line ~60)
- Update `_get_or_create_preferences()` to include timezone (lines ~75-122)
- Update GET endpoint to return timezone (lines ~125-142)
- Update POST endpoint to handle timezone updates (lines ~145-224)

Validation: `display_timezone` must be one of:
- `America/New_York` (EST/EDT)
- `America/Chicago` (CST/CDT)
- `America/Denver` (MST/MDT)
- `America/Los_Angeles` (PST/PDT)
- `America/Anchorage` (AKST/AKDT)
- `America/Adak` (HST/HDT)

### Frontend Changes

#### 3. Create SparklineWithHistory Component

**File**: `frontend/components/watchlist/SparklineWithHistory.tsx` (NEW)

Create component that:
- Accepts `itemId: string` prop
- Uses `useScoreHistory(itemId)` hook to fetch 7-day historical data
- Renders `<Sparkline>` with actual `overall` scores from history
- Shows loading state while fetching
- Falls back to placeholder if no history available

#### 4. Update WatchlistTable Component

**File**: `frontend/components/watchlist/WatchlistTable.tsx`

Changes:
- Import `SparklineWithHistory` component
- Replace hardcoded sparkline at line ~334:
  ```tsx
  // OLD:
  <Sparkline data={[65, 68, 72, 70, 73, 71, overall]} width={80} height={24} />

  // NEW:
  <SparklineWithHistory itemId={item.id} width={80} height={24} />
  ```
- Update `formatDate` function (line ~130) to:
  - Accept `timezone` parameter
  - Use `toLocaleString` with `timeZone` option
  - Append timezone abbreviation (EST, CST, etc.)
- Fetch user preferences to get `display_timezone`
- Pass timezone to all `formatDate` calls

#### 5. Add Timezone Setting to Settings Page

**File**: `frontend/app/settings/page.tsx`

Add new section:
- **Section Title**: "Display Preferences"
- **Field Label**: "Timezone"
- **Field Type**: Select dropdown
- **Options**:
  - Eastern Time (EST/EDT)
  - Central Time (CST/CDT)
  - Mountain Time (MST/MDT)
  - Pacific Time (PST/PDT)
  - Alaska Time (AKST/AKDT)
  - Hawaii Time (HST/HDT)
- **API Update**: Call `POST /api/preferences` with `display_timezone`
- **Position**: Add after watchlist settings section

#### 6. Update Frontend API Types

**File**: `frontend/lib/api/preferences.ts`

Update TypeScript types:
- Add `display_timezone: string` to preferences interface
- Update mutation to handle timezone field

---

## Acceptance Criteria

### Sparkline Fixes
- [ ] Sparkline displays actual 7-day historical overall scores
- [ ] Sparkline shows loading state while fetching data
- [ ] Sparkline handles empty history gracefully (shows placeholder or flat line)
- [ ] Each watchlist item fetches its own history independently

### Timezone Display
- [ ] All timestamps in watchlist show timezone abbreviation (e.g., "Oct 30, 3:21 PM EST")
- [ ] Timezone abbreviation updates based on user preference
- [ ] Default timezone is EST (America/New_York) for new users
- [ ] Timezone preference persists across sessions

### Settings Page
- [ ] Timezone selector appears in Settings page under "Display Preferences"
- [ ] Dropdown shows all 6 USA timezone options with friendly names
- [ ] Changing timezone immediately updates all displayed timestamps
- [ ] Success toast appears when timezone is saved

### Data Integrity
- [ ] Stale data logic continues to work correctly (3x refresh interval)
- [ ] Backend continues to store all timestamps in UTC
- [ ] Only frontend display converts to user's preferred timezone
- [ ] Historical data fetching doesn't impact page performance

---

## Implementation Notes

### Timezone Mapping

Frontend should map IANA names to friendly display:
```typescript
const TIMEZONE_OPTIONS = {
  'America/New_York': 'Eastern Time (EST/EDT)',
  'America/Chicago': 'Central Time (CST/CDT)',
  'America/Denver': 'Mountain Time (MST/MDT)',
  'America/Los_Angeles': 'Pacific Time (PST/PDT)',
  'America/Anchorage': 'Alaska Time (AKST/AKDT)',
  'America/Adak': 'Hawaii-Aleutian Time (HST/HDT)',
};
```

### Timezone Abbreviation Extraction

Use browser API to extract abbreviation:
```typescript
function getTimezoneAbbreviation(date: Date, timezone: string): string {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    timeZoneName: 'short',
  });
  const parts = formatter.formatToParts(date);
  const tzPart = parts.find(part => part.type === 'timeZoneName');
  return tzPart?.value || '';
}
```

### Performance Considerations

- **Sparkline Data**: Each item fetches independently - consider batching if performance is an issue
- **React Query Caching**: Leverage existing caching for score history (staleTime: 5 minutes)
- **Memoization**: Memoize timezone formatting function to avoid repeated calculations

### Database Migration

Migration should:
1. Add `display_timezone` column with default `'America/New_York'`
2. Update existing rows to use default timezone
3. Add CHECK constraint to validate timezone values

---

## Testing Checklist

### Backend Tests
- [ ] Preferences API returns `display_timezone` field
- [ ] Preferences API validates timezone values (rejects invalid timezones)
- [ ] Default timezone is set for new users
- [ ] Timezone updates persist correctly

### Frontend Tests
- [ ] SparklineWithHistory fetches and displays real data
- [ ] SparklineWithHistory handles loading states
- [ ] SparklineWithHistory handles empty/missing data
- [ ] formatDate displays correct timezone abbreviation
- [ ] Settings page updates timezone preference
- [ ] Timestamp display updates when timezone changes

### Integration Tests
- [ ] End-to-end: Change timezone in Settings, verify watchlist timestamps update
- [ ] End-to-end: Add new ticker, verify sparkline appears after 7 days of history
- [ ] Verify stale data calculation still works correctly after timezone changes

---

## Dependencies

- Existing `fetchScoreHistory` API endpoint (confirmed working)
- Existing `useScoreHistory` hook in `useWatchlist.ts`
- Existing `Sparkline` component
- Browser `Intl.DateTimeFormat` API for timezone conversion

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Fetching history for 12 items may be slow | Medium | Use React Query caching, consider batching |
| Invalid timezone values in database | Low | Add backend validation, CHECK constraint |
| Browser timezone API incompatibility | Low | Test across browsers, provide fallback |
| Historical data missing for new tickers | Low | Show placeholder or "No data yet" message |

---

## Success Metrics

- Users can see their preferred timezone on all timestamps
- Sparkline charts display actual historical trends
- Page load time remains under 2 seconds
- No errors in console related to timezone or sparkline rendering

---

## Future Enhancements

- Add automatic timezone detection based on browser
- Show market hours indicator (open/closed) based on timezone
- Add tooltip to sparkline showing exact date/score for each point
- Support non-USA timezones (UTC, Europe, Asia)
