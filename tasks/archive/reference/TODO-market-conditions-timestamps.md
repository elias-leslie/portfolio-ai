# TODO: Add Per-Item Timestamps to Market Conditions

**Priority:** Medium
**Estimated Effort:** LOW (30-45 minutes)
**Created:** 2025-11-07
**Status:** Not Started

---

## Problem

The Market Conditions card displays multiple data points but only shows one overall `last_updated` timestamp. Users cannot verify the freshness of individual metrics.

**Current behavior:**
- S&P 500, VIX, 10Y Treasury, US Dollar - no individual timestamps
- 11 sector ETFs - no individual timestamps
- Only one overall timestamp: `health.last_updated`

**User impact:**
- Cannot tell if one data source is stale while others are fresh
- No visibility into which specific metric might need manual refresh
- Reduced trust in data accuracy

---

## Acceptance Criteria

### Backend (API Changes)

**File:** `backend/app/api/market.py`

Update response models to include timestamps:

1. **MarketConditionsResponse** - Add timestamps to each indicator:
   ```python
   sp500: dict[str, float | None | str] = {
       "price": 6675.97,
       "change_pct": null,
       "last_updated": "2025-11-07T19:10:58Z"  # NEW
   }

   vix: dict[str, float | None | str] = {
       "price": 20.82,
       "level": null,
       "last_updated": "2025-11-07T19:10:58Z"  # NEW
   }

   # Same for tnx, dxy
   ```

2. **SectorScore** - Add timestamp field:
   ```python
   class SectorScore(BaseModel):
       symbol: str
       name: str
       price: float | None
       change_pct: float | None
       signal: str
       last_updated: str | None = None  # NEW
   ```

3. **ComponentScore** - Add timestamp field:
   ```python
   class ComponentScore(BaseModel):
       name: str
       score: int
       value: float | None
       interpretation: str
       signal: str
       last_updated: str | None = None  # NEW
   ```

4. **Populate timestamps** in `get_market_conditions()`:
   - Get timestamp from `day_bars.date` for sector data
   - Use current fetch time for real-time price data
   - Format as ISO 8601: `"2025-11-07T19:10:58Z"`

### Frontend (UI Changes)

**File:** `frontend/components/portfolio/MarketConditions.tsx`

Display timestamps for data freshness visibility:

1. **Top-level indicators** (S&P 500, VIX, Treasury, Dollar):
   - Show small gray timestamp below each value
   - Format: "Updated 2m ago" or "Updated at 7:10 PM"

2. **Component breakdown** (when expanded):
   - Show timestamp next to each component score bar
   - Format: "2m ago" (compact)

3. **Sector Performance**:
   - Show timestamp for each sector in the grid
   - Format: "Updated 5m ago" (compact, gray text)
   - Or group timestamp if all sectors updated together

4. **UI Guidelines**:
   - Use muted text color (text-muted-foreground)
   - Small font size (text-xs)
   - Relative time format preferred ("2m ago", "1h ago")
   - Fallback to absolute time for > 24h ("Nov 7, 7:10 PM")

### Helper Function

Create `frontend/lib/utils/time.ts` (or add to existing utils):

```typescript
export function formatRelativeTime(timestamp: string): string {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  // Format as absolute time for > 24h
  return then.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  });
}
```

---

## Implementation Steps

1. **Backend API** (15 min):
   - Add timestamp fields to Pydantic models
   - Update `get_market_conditions()` to populate timestamps
   - Test API response includes all timestamps

2. **Frontend Display** (20 min):
   - Add `formatRelativeTime()` helper function
   - Update MarketConditions component to display timestamps
   - Test all timestamps render correctly

3. **Testing** (10 min):
   - Verify timestamps update when data refreshes
   - Check relative time formatting (1m, 5m, 1h, 24h+)
   - Ensure timestamps don't break UI layout

---

## Files to Modify

- `backend/app/api/market.py` - Add timestamp fields and population logic
- `frontend/components/portfolio/MarketConditions.tsx` - Display timestamps
- `frontend/lib/utils/time.ts` (new) - Time formatting helper
- `frontend/lib/api/market.ts` - Update TypeScript types

---

## Testing Checklist

- [ ] API returns timestamp for S&P 500, VIX, Treasury, Dollar
- [ ] API returns timestamps for all 11 sector ETFs
- [ ] API returns timestamps for health components
- [ ] Frontend displays timestamps on all indicators
- [ ] Timestamps update when data refreshes
- [ ] Relative time formats correctly (1m, 1h, 24h+)
- [ ] Dark mode colors work correctly
- [ ] No UI layout breaks

---

## Reference

**Related PR:** Enhanced Market Conditions (commit 6974a42)
**Current Status:** 95% complete (missing only timestamps)
**Screenshot:** `/tmp/market-conditions-expanded.png`

---

## Notes

- Use ISO 8601 format for all timestamps: `"2025-11-07T19:10:58Z"`
- Consider using a library like `date-fns` for time formatting if available
- Timestamps should be in UTC from backend, converted to local time in frontend
- This is purely a display/UX improvement - no functional changes to data fetching

---

**Created by:** Claude Code
**Date:** 2025-11-07
