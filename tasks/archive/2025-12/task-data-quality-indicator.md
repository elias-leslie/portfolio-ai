# Task: Data Quality Indicator

**Status**: Not Started
**Created**: 2025-12-10
**Complexity**: Medium
**Estimated Effort**: MEDIUM (multiple components, frontend + backend)

## Overview

Add a "Data Quality" indicator to the watchlist UI that shows users the completeness and freshness of data powering each stock's AI score. This provides transparency into scoring confidence and helps users understand when data may be incomplete or stale.

## Description

The Data Quality Indicator will:
- Display a single percentage value representing overall data completeness
- Show per-pillar status on hover (Technical, Fundamental, Catalyst, Options, Price)
- Indicate data freshness (complete, partial, stale, n/a)
- Calculate weighted average based on pillar importance
- Help users make informed decisions about score reliability

## Acceptance Criteria

### AC-1: Data Quality Column in Watchlist UI
- [ ] New "Data Quality" column appears in watchlist table
- [ ] Shows percentage (e.g., "85%") with color coding:
  - Green: 90-100% (excellent)
  - Yellow: 70-89% (good)
  - Orange: 50-69% (fair)
  - Red: <50% (poor)
- [ ] Column is sortable
- [ ] Responsive design (hides on mobile, shows on tablet+)

### AC-2: Tooltip with Per-Pillar Breakdown
- [ ] Hovering over percentage shows tooltip
- [ ] Tooltip lists all 5 pillars with individual status:
  - Technical Analysis: complete | partial | stale | n/a
  - Fundamental Analysis: complete | partial | stale | n/a
  - Catalyst Events: complete | partial | stale | n/a
  - Options Flow: complete | partial | stale | n/a
  - Price Action: complete | partial | stale | n/a
- [ ] Each pillar shows icon and color based on status
- [ ] Tooltip includes last updated timestamp

### AC-3: Backend Data Quality Calculation
- [ ] New API endpoint: `GET /api/watchlist/{symbol}/data-quality`
- [ ] Returns structure:
  ```json
  {
    "symbol": "AAPL",
    "overall_quality": 85,
    "pillars": {
      "technical": {"status": "complete", "last_updated": "2025-12-10T10:30:00Z", "weight": 0.25},
      "fundamental": {"status": "complete", "last_updated": "2025-12-09T22:00:00Z", "weight": 0.25},
      "catalyst": {"status": "partial", "last_updated": "2025-12-10T08:00:00Z", "weight": 0.20},
      "options": {"status": "complete", "last_updated": "2025-12-10T10:00:00Z", "weight": 0.15},
      "price": {"status": "complete", "last_updated": "2025-12-10T10:35:00Z", "weight": 0.15}
    },
    "calculated_at": "2025-12-10T10:35:00Z"
  }
  ```
- [ ] Calculation logic accounts for data age thresholds:
  - Intraday data: stale after 1 hour
  - Daily data: stale after 24 hours
  - Fundamental data: stale after 7 days
  - News/catalyst: stale after 24 hours

### AC-4: Pillar Status Logic
- [ ] **Complete**: All required fields present, data fresh
- [ ] **Partial**: Some fields missing or incomplete data coverage
- [ ] **Stale**: Data exists but exceeds freshness threshold
- [ ] **N/A**: Pillar not applicable (e.g., fundamentals for ETFs)

### AC-5: Weighted Average Calculation
- [ ] Overall percentage = weighted average of pillar completeness
- [ ] Pillar weights configurable (default: Tech 25%, Fund 25%, Cat 20%, Opt 15%, Price 15%)
- [ ] N/A pillars excluded from calculation (weights redistributed)
- [ ] Stale data counts as 50% complete
- [ ] Partial data counts as 70% complete
- [ ] Complete data counts as 100%

### AC-6: Integration with Existing Watchlist
- [ ] Data quality included in watchlist snapshot (no extra API call per row)
- [ ] Calculation runs during `calculate_watchlist_scores()`
- [ ] Stored in `watchlist_snapshots.raw_metrics` JSONB field
- [ ] Cached with 60-second TTL (same as score)

## Implementation Steps

### Step 1: Backend - Data Quality Service
**File**: `backend/app/services/data_quality_service.py` (new)

1. Create `DataQualityService` class
2. Implement `calculate_pillar_status()` method:
   - Check data presence in respective tables
   - Check data freshness vs thresholds
   - Return status enum (complete, partial, stale, n/a)
3. Implement `calculate_overall_quality()` method:
   - Call pillar status for all 5 pillars
   - Apply weights
   - Calculate weighted average
   - Return DataQuality dataclass
4. Add configurable staleness thresholds
5. Write unit tests (20+ tests for edge cases)

**Files to create**:
- `backend/app/services/data_quality_service.py`
- `backend/tests/unit/test_data_quality_service.py`

### Step 2: Backend - Integrate with Watchlist Scoring
**File**: `backend/app/watchlist/watchlist_service.py`

1. Import `DataQualityService`
2. In `calculate_watchlist_scores()`, after calculating score:
   - Call `data_quality_service.calculate_overall_quality(symbol)`
   - Store result in `raw_metrics["data_quality"]`
3. Update `WatchlistItemResponse` model to include `data_quality` field
4. Update serialization to include data quality in response

**Files to modify**:
- `backend/app/watchlist/watchlist_service.py` (lines ~200-300)
- `backend/app/api/watchlist.py` (WatchlistItemResponse model)

### Step 3: Backend - Add Dedicated Endpoint (Optional)
**File**: `backend/app/api/data_quality.py` (new, optional)

1. Create endpoint: `GET /api/watchlist/{symbol}/data-quality`
2. Call `DataQualityService.calculate_overall_quality(symbol)`
3. Return detailed breakdown for debugging/future use

**Files to create** (optional):
- `backend/app/api/data_quality.py`

### Step 4: Frontend - TypeScript Types
**File**: `frontend/lib/api/watchlist.ts`

1. Add `DataQualityPillar` interface:
   ```typescript
   interface DataQualityPillar {
     status: 'complete' | 'partial' | 'stale' | 'n/a';
     last_updated: string;
     weight: number;
   }
   ```
2. Add `DataQuality` interface:
   ```typescript
   interface DataQuality {
     overall_quality: number;
     pillars: {
       technical: DataQualityPillar;
       fundamental: DataQualityPillar;
       catalyst: DataQualityPillar;
       options: DataQualityPillar;
       price: DataQualityPillar;
     };
     calculated_at: string;
   }
   ```
3. Add `data_quality?: DataQuality` to `WatchlistItem` interface

**Files to modify**:
- `frontend/lib/api/watchlist.ts`

### Step 5: Frontend - Data Quality Badge Component
**File**: `frontend/components/watchlist/DataQualityBadge.tsx` (new)

1. Create `DataQualityBadge` component
2. Display percentage with color coding
3. Implement hover tooltip with pillar breakdown
4. Use icons for pillar status (✓ complete, ⚠ partial, ⏰ stale, - n/a)
5. Format timestamps as relative time ("2 hours ago")

**Files to create**:
- `frontend/components/watchlist/DataQualityBadge.tsx`

### Step 6: Frontend - Add Column to Watchlist Table
**File**: `frontend/components/watchlist/WatchlistTable.tsx`

1. Add "Data Quality" column header
2. Add `<DataQualityBadge />` to table row
3. Make column sortable by `data_quality.overall_quality`
4. Add responsive classes (hide on mobile)
5. Update column widths

**Files to modify**:
- `frontend/components/watchlist/WatchlistTable.tsx`

### Step 7: Testing

#### Backend Tests
```bash
# Unit tests for data quality service
cd ~/portfolio-ai/backend
pytest tests/unit/test_data_quality_service.py -v

# Integration tests for watchlist API
pytest tests/integration/test_watchlist_api.py -v -k data_quality

# Full test suite
pytest tests/ -v
```

#### Frontend Tests
```bash
# Type check
cd ~/portfolio-ai/frontend
npm run type-check

# Component tests
npm test -- DataQualityBadge
```

#### Manual Testing
1. Restart services: `bash ~/portfolio-ai/scripts/restart.sh`
2. Trigger watchlist refresh: `curl -X POST http://localhost:8000/api/watchlist/refresh`
3. View watchlist in browser: `http://192.168.8.233:3000/watchlist`
4. Verify:
   - [ ] Data Quality column appears
   - [ ] Percentages display correctly
   - [ ] Colors match thresholds
   - [ ] Tooltip shows on hover
   - [ ] Pillar breakdown is accurate
   - [ ] Sorting works
   - [ ] No console errors

### Step 8: Evidence Capture
```bash
# Capture screenshot for verification
curl -s -X POST "http://localhost:8000/api/artifacts/refresh" \
  -H "Content-Type: application/json" \
  -d '{"feature_id": "FEAT-XXX", "criterion_id": "ac-001", "url": "http://192.168.8.233:3000/watchlist"}'
```

### Step 9: Documentation
Update documentation with data quality feature:
- [ ] Add to `docs/core/API_REFERENCE.md` (watchlist endpoint response)
- [ ] Add to `docs/core/ARCHITECTURE.md` (data quality service)
- [ ] Update `docs/core/DEVELOPMENT.md` (data quality patterns)

## Files Likely to Change

### Backend (New)
- `backend/app/services/data_quality_service.py` (new, ~200 lines)
- `backend/tests/unit/test_data_quality_service.py` (new, ~300 lines)
- `backend/app/api/data_quality.py` (optional, ~50 lines)

### Backend (Modified)
- `backend/app/watchlist/watchlist_service.py` (~20 lines added)
- `backend/app/api/watchlist.py` (~10 lines modified)

### Frontend (New)
- `frontend/components/watchlist/DataQualityBadge.tsx` (new, ~150 lines)

### Frontend (Modified)
- `frontend/lib/api/watchlist.ts` (~30 lines added)
- `frontend/components/watchlist/WatchlistTable.tsx` (~20 lines modified)

### Documentation
- `docs/core/API_REFERENCE.md`
- `docs/core/ARCHITECTURE.md`
- `docs/core/DEVELOPMENT.md`

## Dependencies

- Existing watchlist scoring system
- Access to data tables: `news_cache`, `price_data`, `fundamentals`, `options_flow`
- `watchlist_snapshots.raw_metrics` JSONB storage

## Known Considerations

### Data Freshness Thresholds
Needs careful tuning based on market hours and data source update frequencies:
- Market hours: stricter thresholds
- After hours: more lenient
- Weekends: exclude from staleness calculation

### Performance
- Calculation should add <100ms to watchlist scoring
- Consider caching pillar status checks
- Batch database queries where possible

### Future Enhancements
- Historical data quality tracking (trend over time)
- Data quality alerts (notify when quality drops)
- Per-source attribution (which API provided which data)
- Data quality impact on score confidence intervals

## References

- Watchlist scoring: `backend/app/watchlist/watchlist_service.py`
- Snapshot storage: `backend/app/storage/schema.sql` (watchlist_snapshots table)
- Existing badge patterns: `frontend/components/ui/badge.tsx`
- Tooltip patterns: `frontend/components/ui/tooltip.tsx`

## Success Criteria

**Feature is complete when**:
1. ✅ Data Quality column appears in watchlist UI
2. ✅ Percentage displays with correct color coding
3. ✅ Tooltip shows per-pillar breakdown on hover
4. ✅ Backend calculates quality accurately based on data freshness
5. ✅ Quality updates when data is refreshed
6. ✅ All tests pass (backend + frontend)
7. ✅ No performance degradation (<100ms added to scoring)
8. ✅ Documentation updated
9. ✅ Evidence captured and verified

---

**Priority**: High (improves user trust and score transparency)
**Effort**: MEDIUM (3-4 components, cross-stack changes)
