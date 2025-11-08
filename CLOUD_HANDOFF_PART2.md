# Cloud Agent Handoff: Watchlist Part 2 Foundation

**Status**: ⚠️  PARTIAL (Foundation Complete, Implementation Remaining)
**Date**: 2025-11-08
**Agent**: Cloud Claude Code (Session: 011CUvqDioH4JoBobHQRa8nD)
**Task List**: tasks/tasks-cloud-watchlist-part2-foundation.md

---

## Summary

Completed 3 of 9 tasks from Part 2 Foundation. Core architecture and models are ready - implementation of scoring logic, volume calculations, and UI components remain.

### ✅ **COMPLETED**
1. ✅ **Task 1**: Research & Validation - Comprehensive codebase analysis
2. ✅ **Task 2**: 4-Pillar Fundamental Scoring - 5 new functions added to fundamentals.py
3. ✅ **Task 3**: 3-Pillar Models Updated - ScoreWeights/ScoreComponent/ScoreBreakdown

### ❌ **REMAINING** (Local Dev Must Complete)
4. ❌ **Task 4**: Add fundamental component calculation to scoring.py
5. ❌ **Task 5**: Integrate fundamental scoring into refresh_processor.py
6. ❌ **Task 6**: Create volume/timeframe/percentile calculation modules
7. ❌ **Task 7**: Database migration 019 for weight configuration
8. ❌ **Task 8**: Frontend settings sliders for ALL sub-metrics
9. ❌ **Task 9**: Frontend score breakdown display in ExpandedRow

**Estimated Remaining Time**: 6-8 hours (local dev environment)

---

## 🎨 Design References

**IMPORTANT:** All UI implementation must align with these design references:

1. **Text Guide**: `docs/watchlist_design_guide.md`
   - Complete ASCII mockups of all views
   - Column descriptions and data flow
   - Color scheme and accessibility guidelines

2. **Visual Mockups**: `docs/design_references/watchlist_design_reference/`
   - `watchlist_main_table_view/` - Main table layout (screen.png + code.html)
   - `expanded_row_-_full_intelligence_view/` - Expanded row details (screen.png + code.html)
   - `watchlist_settings_panel/` - Settings sliders (screen.png + code.html)
   - `search_and_filter_bar/` - Search and filter UI (screen.png + code.html)
   - **NOTE**: Each folder has `code.html` with Tailwind CSS implementation - USE THIS for exact styling!

**⚠️ Known Discrepancy:**
- Mockup shows Sentiment as 4th top-level weight (Price/Technical/Fundamental/Sentiment)
- Implementation has Sentiment as sub-weight of Fundamental (Valuation/Growth/Health/Sentiment)
- **Current approach:** Keep implementation (3-pillar), update mockup if needed

---

## ✅ Changes Completed by Cloud Agent

### Backend (3 files modified)

#### 1. `backend/app/watchlist/fundamentals.py`
**Lines Added**: 175 new lines
**Changes**:
- Added 5 score fields to `FundamentalData` model (lines 48-53):
  - `fundamental_score`, `valuation_score`, `growth_score`, `health_score`, `sentiment_score`
- Added 5 new scoring functions (lines 307-462):
  - `calculate_valuation_score()` - Profit margin based (30% weight)
  - `calculate_growth_score()` - Revenue growth based (35% weight)
  - `calculate_health_score()` - Debt + profitability (25% weight)
  - `calculate_sentiment_score()` - Analyst ratings (10% weight)
  - `calculate_fundamental_score()` - Weighted composite (30/35/25/10)

#### 2. `backend/app/watchlist/models.py`
**Lines Modified**: 3 model classes
**Changes**:
- `ScoreWeights` (lines 66-86):
  - Changed from 2-pillar (50/50) to 3-pillar (33/33/34)
  - Added `fundamental: float = 34.0` field
  - Updated `normalized()` to include fundamental weight
- `ScoreComponent` (lines 89-100):
  - Added `sub_scores: dict[str, float]` field for sub-metric tracking
- `ScoreBreakdown` (lines 108-130):
  - Added `fundamental: ScoreComponent | None` field
  - Updated `to_snapshot_payload()` to serialize fundamental component

#### 3. AVOID Signal Bug Investigation
**Finding**: ✅ **ALREADY FIXED!**
- `sma_5_prev` is fetched in refresh_processor.py (lines 427-436)
- `news_sentiment` is already passed to `classify_signal()` (line 467)
- No changes needed - Task 5 from original plan is COMPLETE

---

## ❌ Remaining Implementation (Local Dev)

### Task 4: Add Fundamental Component to Scoring.py

**File**: `backend/app/watchlist/scoring.py`
**Location**: After `_compute_technical_component()` (after line 156)

**Step 1**: Add import at top:
```python
from .fundamentals import FundamentalData
```

**Step 2**: Add new function after line 156:
```python
def _compute_fundamental_component(
    fundamental_data: FundamentalData | None,
    weight: float,
    now: datetime,
) -> ScoreComponent:
    """Compute fundamental score component from FundamentalData.

    Args:
        fundamental_data: FundamentalData object with calculated scores
        weight: Weight for this component (0.0-1.0)
        now: Current timestamp

    Returns:
        ScoreComponent with fundamental score and sub-scores
    """
    if not fundamental_data or not fundamental_data.fundamental_score:
        return ScoreComponent(
            score=0.0,
            weight=weight,
            stale=True,
            metadata={"reason": "missing_fundamental_data"},
            sub_scores={},
        )

    score = fundamental_data.fundamental_score

    # Sub-scores breakdown (4 pillars)
    sub_scores = {
        "valuation": fundamental_data.valuation_score or 0.0,
        "growth": fundamental_data.growth_score or 0.0,
        "health": fundamental_data.health_score or 0.0,
        "sentiment": fundamental_data.sentiment_score or 0.0,
    }

    metadata = {
        "profit_margin": fundamental_data.profit_margin,
        "revenue_growth": fundamental_data.revenue_growth,
        "debt_to_equity": fundamental_data.debt_to_equity,
        "recommendation_mean": fundamental_data.recommendation_mean,
    }

    component = ScoreComponent(
        score=score,
        weight=weight,
        stale=False,  # Fundamental data cached for 24h
        metadata=metadata,
        sub_scores=sub_scores,
    )

    return component
```

**Step 3**: Update `calculate_watchlist_scores()` (replace lines 159-201):
```python
def calculate_watchlist_scores(inputs: WatchlistScoreInputs) -> ScoreBreakdown:
    """Compute watchlist price/technical/fundamental scores and overall composite (3-pillar)."""
    # Ensure timestamps are timezone-aware
    now = inputs.now if inputs.now.tzinfo is not None else inputs.now.replace(tzinfo=UTC)

    weights = inputs.weights.normalized()

    # Price component (with sub-scores)
    price_component = _compute_price_component(
        PriceComponentInputs(
            price_data=inputs.price,
            change_pct=inputs.price_change_pct,
            now=now,
        ),
        weight=weights["price"],
        stale_ttl_minutes=inputs.stale_ttl_minutes,
    )
    price_component.sub_scores = {"change_pct": price_component.score}

    # Technical component (with sub-scores)
    technical_component = _compute_technical_component(
        inputs.technical,
        weight=weights["technical"],
        now=now,
        stale_ttl_minutes=inputs.stale_ttl_minutes,
    )

    # Extract technical sub-scores from metadata
    technical_component.sub_scores = {
        "rsi_14": technical_component.metadata.get("rsi_14", 0.0),
        "trend": technical_component.metadata.get("trend_score", 0.0),
        "macd": technical_component.metadata.get("macd", 0.0) if technical_component.metadata.get("macd") else 0.0,
    }

    # Fundamental component (if available)
    fundamental_component = None
    if hasattr(inputs, "fundamental") and inputs.fundamental:
        fundamental_component = _compute_fundamental_component(
            inputs.fundamental,
            weight=weights["fundamental"],
            now=now,
        )

    # Calculate overall score
    if fundamental_component and not fundamental_component.stale:
        # 3-pillar formula
        overall = (
            price_component.score * weights["price"] +
            technical_component.score * weights["technical"] +
            fundamental_component.score * weights["fundamental"]
        )
    else:
        # Fallback to 2-pillar (renormalize weights)
        price_weight = weights["price"] / (weights["price"] + weights["technical"])
        technical_weight = weights["technical"] / (weights["price"] + weights["technical"])
        overall = (
            price_component.score * price_weight +
            technical_component.score * technical_weight
        )

    breakdown = ScoreBreakdown(
        price=price_component,
        technical=technical_component,
        fundamental=fundamental_component,
        overall=overall,
    )

    logger.info(
        "watchlist_scores_computed",
        symbol=inputs.price.symbol,
        overall=breakdown.overall,
        price_score=breakdown.price.score,
        technical_score=breakdown.technical.score,
        fundamental_score=breakdown.fundamental.score if breakdown.fundamental else None,
    )

    return breakdown
```

**Step 4**: Update `WatchlistScoreInputs` in models.py (around line 136):
```python
class WatchlistScoreInputs(BaseModel):
    """Inputs required to compute watchlist scores."""

    price: PriceData
    price_change_pct: float | None = None
    technical: TechnicalSnapshot = Field(default_factory=TechnicalSnapshot)
    fundamental: Any | None = None  # FundamentalData (avoid circular import)
    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    now: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stale_ttl_minutes: int = 15
```

---

### Task 5: Integrate Fundamental Scoring into Refresh Processor

**File**: `backend/app/watchlist/refresh_processor.py`
**Location**: Where `WatchlistScoreInputs` is created and fundamental data is fetched

**Step 1**: Add imports at top:
```python
from .fundamentals import (
    calculate_valuation_score,
    calculate_growth_score,
    calculate_health_score,
    calculate_sentiment_score,
    calculate_fundamental_score,
)
```

**Step 2**: Find where fundamental data is fetched (search for "fetch_fundamentals_cached")

**Step 3**: After fetching fundamental data, calculate scores:
```python
if fundamental_data:
    # Calculate 4-pillar scores
    fundamental_data.valuation_score = calculate_valuation_score(fundamental_data)
    fundamental_data.growth_score = calculate_growth_score(fundamental_data)
    fundamental_data.health_score = calculate_health_score(fundamental_data)
    fundamental_data.sentiment_score = calculate_sentiment_score(fundamental_data)
    fundamental_data.fundamental_score = calculate_fundamental_score(fundamental_data)
```

**Step 4**: Pass fundamental data to scoring inputs:
```python
score_inputs = WatchlistScoreInputs(
    price=price_data,
    price_change_pct=change_pct,
    technical=technical_snapshot,
    fundamental=fundamental_data,  # ADD THIS
    weights=weights,
    now=now,
    stale_ttl_minutes=stale_ttl_minutes,
)
```

---

### Task 6: Volume/Timeframe/Percentile Calculations

**Create 2 new files:**

#### File 1: `backend/app/watchlist/timeframe.py` (NEW - 60 lines)
```python
"""Multi-timeframe alignment analysis for watchlist items."""

from __future__ import annotations


def calculate_timeframe_alignment(
    price: float,
    sma_20: float | None,
    sma_50: float | None,
    sma_200: float | None,
) -> tuple[bool, bool]:
    """Calculate short-term and long-term timeframe alignment.

    Short-term aligned: Price > SMA_20 > SMA_50
    Long-term aligned: SMA_50 > SMA_200

    Args:
        price: Current price
        sma_20: 20-day simple moving average
        sma_50: 50-day simple moving average
        sma_200: 200-day simple moving average

    Returns:
        Tuple of (short_aligned, long_aligned)
    """
    short_aligned = False
    long_aligned = False

    # Short-term alignment (Price > SMA_20 > SMA_50)
    if sma_20 and sma_50:
        short_aligned = price > sma_20 and sma_20 > sma_50

    # Long-term alignment (SMA_50 > SMA_200)
    if sma_50 and sma_200:
        long_aligned = sma_50 > sma_200

    return (short_aligned, long_aligned)


def calculate_volume_relative(
    current_volume: float,
    avg_volume_50d: float | None,
) -> float | None:
    """Calculate volume relative to 50-day average.

    Args:
        current_volume: Today's volume
        avg_volume_50d: 50-day average volume

    Returns:
        Ratio (e.g., 2.3 = 2.3x above average), or None if missing data
    """
    if not avg_volume_50d or avg_volume_50d <= 0:
        return None

    return current_volume / avg_volume_50d
```

#### File 2: `backend/app/watchlist/percentiles.py` (NEW - 30 lines)
```python
"""Percentile rank calculation for watchlist scores."""

from __future__ import annotations


def calculate_percentile_rank(
    current_score: float,
    historical_scores: list[float],
) -> float:
    """Calculate percentile rank of current score vs historical scores.

    Args:
        current_score: Today's overall score
        historical_scores: List of scores from last 30 days

    Returns:
        Percentile rank 0-100 (e.g., 85.0 = top 15%)
    """
    if not historical_scores:
        return 50.0  # Default to median if no history

    # Count how many historical scores are below current
    below_count = sum(1 for score in historical_scores if score < current_score)

    # Percentile = (count below / total count) * 100
    percentile = (below_count / len(historical_scores)) * 100.0

    return percentile
```

#### Integration into refresh_processor.py

Add imports:
```python
from .timeframe import calculate_timeframe_alignment, calculate_volume_relative
from .percentiles import calculate_percentile_rank
```

Add calculations before snapshot creation:
```python
# Calculate timeframe alignment
short_aligned, long_aligned = calculate_timeframe_alignment(
    price=price_data.price,
    sma_20=technical_snapshot.sma_20,
    sma_50=technical_snapshot.sma_50,
    sma_200=technical_snapshot.sma_200,
)

# Calculate volume relative
# TODO: Query day_bars for 50-day average volume
# This requires fetching OHLCV data - may need storage query
volume_relative = None  # Placeholder - needs implementation

# Calculate percentile rank (need last 30 days of snapshots)
with storage.connection() as conn:
    historical_scores_query = """
        SELECT overall_score
        FROM watchlist_snapshots
        WHERE item_id = %s
          AND fetched_at >= NOW() - INTERVAL '30 days'
        ORDER BY fetched_at DESC
    """
    historical_scores = conn.execute(historical_scores_query, [item_id]).fetchall()
    historical_score_list = [row[0] for row in historical_scores if row[0] is not None]

percentile_rank = calculate_percentile_rank(
    current_score=score_breakdown.overall,
    historical_scores=historical_score_list,
)

# Assign to snapshot
snapshot.timeframe_short_aligned = short_aligned
snapshot.timeframe_long_aligned = long_aligned
snapshot.volume_relative = volume_relative
snapshot.percentile_rank_30d = percentile_rank
```

**⚠️  CRITICAL LIMITATION**: Volume calculation requires querying `day_bars` table for 50-day average. This needs database access which cloud agent cannot test. Local dev must implement and verify.

---

### Task 7: Database Migration 019

**Create File**: `backend/migrations/019_score_weight_sliders.sql`

```sql
-- Migration 019: Score weight sliders for all sub-metrics
-- Add JSONB fields for detailed weight configuration

ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS watchlist_score_weights JSONB DEFAULT '{"price": 33, "technical": 33, "fundamental": 34}';

ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS price_sub_weights JSONB DEFAULT '{"change_pct": 100}';

ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS technical_sub_weights JSONB DEFAULT '{"rsi_14": 33, "trend": 34, "macd": 33}';

ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS fundamental_sub_weights JSONB DEFAULT '{"valuation": 30, "growth": 35, "health": 25, "sentiment": 10}';

COMMENT ON COLUMN user_preferences.watchlist_score_weights IS 'Top-level weights: price, technical, fundamental (must sum to 100)';
COMMENT ON COLUMN user_preferences.price_sub_weights IS 'Price component sub-weights (currently only change_pct, future: beta, volatility)';
COMMENT ON COLUMN user_preferences.technical_sub_weights IS 'Technical component sub-weights: rsi_14, trend, macd (must sum to 100)';
COMMENT ON COLUMN user_preferences.fundamental_sub_weights IS 'Fundamental component sub-weights: valuation, growth, health, sentiment (must sum to 100)';
```

**Execute**:
```bash
psql -U portfolio_ai_user -d portfolio_ai -f backend/migrations/019_score_weight_sliders.sql
```

---

### Task 8: Frontend Settings Sliders

**File**: `frontend/components/settings/WatchlistPreferences.tsx`
**Location**: Replace score weights section (lines 525-586)

See tasks/tasks-cloud-watchlist-part2-foundation.md lines 922-1108 for complete implementation (150 lines).

**Key features**:
- 3 top-level sliders (price/technical/fundamental)
- 3 technical sub-sliders (RSI/Trend/MACD)
- 4 fundamental sub-sliders (Valuation/Growth/Health/Sentiment)
- Real-time validation (must sum to 100%)
- Reset buttons for each section

---

### Task 9: Frontend Score Breakdown Display

**File**: `frontend/components/watchlist/ExpandedRow.tsx`
**Location**: In "Trading Intelligence" section

See tasks/tasks-cloud-watchlist-part2-foundation.md lines 1123-1216 for complete implementation (90 lines).

**Key features**:
- Overall score bar
- 3 pillar breakdown (price/technical/fundamental)
- Sub-scores for each pillar displayed as bullet list
- Weight percentages shown
- Progress bars for visual representation

---

## Known Issues & Limitations

### 1. Volume Relative Calculation
**Issue**: Requires 50-day average volume from `day_bars` table
**Status**: ❌ NOT IMPLEMENTED
**Reason**: Cloud agent cannot query database to verify data availability
**Solution**: Local dev must:
1. Check if `day_bars` table has sufficient history (50+ days)
2. Implement SQL query to calculate 50-day volume average
3. Handle missing data gracefully (return None if <50 days)

### 2. Fundamental Data Historical Backfill
**Issue**: Fundamental scores only calculated going forward (no historical backfill)
**Status**: ⚠️  LIMITATION BY DESIGN
**Reason**: APIs only provide current fundamental data, not historical
**Impact**: Historical snapshots will have `fundamental_score: None` until data accumulates organically
**Mitigation**: This is acceptable - 3-pillar scoring will fall back to 2-pillar for old snapshots

### 3. Sub-Scores Persistence
**Issue**: `sub_scores` dict is NOT currently persisted to database
**Status**: ⚠️  DESIGN DECISION NEEDED
**Reason**: `raw_metrics` JSONB field exists in snapshots, but currently unused
**Question**: Should sub_scores be stored in `raw_metrics` for historical analysis?
**Recommendation**: Add to `to_snapshot_payload()` if historical sub-metric tracking is desired

---

## Testing Required (Local Dev MUST DO)

### Backend Tests

#### 1. Fundamental Scoring Tests
```bash
cd backend && source .venv/bin/activate

# Test individual scoring functions
python3 -c "
from app.watchlist.fundamentals import *
data = FundamentalData(
    symbol='AAPL',
    profit_margin=0.25,
    revenue_growth=0.15,
    debt_to_equity=0.4,
    recommendation_mean=1.8
)
print('Valuation:', calculate_valuation_score(data))
print('Growth:', calculate_growth_score(data))
print('Health:', calculate_health_score(data))
print('Sentiment:', calculate_sentiment_score(data))
print('Overall:', calculate_fundamental_score(data))
"
```

Expected output:
- Valuation: 90.0
- Growth: 60.0
- Health: ~93.0 (average of 100 and 80)
- Sentiment: 80.0
- Overall: ~80.5 (weighted average)

#### 2. Model Validation
```bash
# Test 3-pillar weight normalization
python3 -c "
from app.watchlist.models import ScoreWeights
weights = ScoreWeights(price=33, technical=33, fundamental=34)
print('Normalized:', weights.normalized())
print('Total:', weights.total)
"
```

Expected output:
- Normalized: {'price': 0.33, 'technical': 0.33, 'fundamental': 0.34}
- Total: 100.0

#### 3. Integration Test
```bash
# Full watchlist refresh test
pytest tests/integration/watchlist/ -v -k "test_watchlist_refresh"
```

### Frontend Tests

#### 1. Settings Page
1. Navigate to Settings → Watchlist Preferences
2. Verify 3 top-level sliders appear
3. Verify technical sub-sliders expand when technical slider is active
4. Verify fundamental sub-sliders expand when fundamental slider is active
5. Change values and verify validation (must sum to 100%)
6. Click "Reset" and verify defaults restore (33/33/34)

#### 2. Score Breakdown Display
1. Navigate to Watchlist page
2. Expand a watchlist row
3. Verify "Score Breakdown" section appears
4. Verify 3 progress bars (price/technical/fundamental)
5. Verify sub-scores display under each pillar
6. Verify weights show correctly (e.g., "Price (33%)")

---

## Static Analysis Results

```bash
# Run ruff check
ruff check backend/app/watchlist/fundamentals.py backend/app/watchlist/models.py
# ✅ All checks passed

# Run mypy (expected pre-existing errors only)
mypy backend/app/watchlist/ --strict
# ⚠️  Only pre-existing pydantic/polars stub errors (not new)
```

---

## Architecture Decisions

### Decision 1: Graceful Degradation for Missing Fundamentals
**Rationale**: Not all stocks have complete fundamental data (e.g., IPOs, small caps, foreign stocks)
**Implementation**: 3-pillar formula automatically falls back to 2-pillar (price + technical) when fundamental component is None or stale
**Trade-off**: Consistent user experience vs. missing data warnings
**Outcome**: Users don't see errors, but scores may vary based on data availability

### Decision 2: Sub-Scores as Dict (Not Persisted)
**Rationale**: Sub-scores provide UI transparency but may not need historical tracking
**Implementation**: Stored in-memory in `ScoreComponent.sub_scores`, not persisted to database
**Trade-off**: Faster implementation vs. historical sub-metric analysis capability
**Outcome**: Can display current sub-scores in UI, but cannot chart historical sub-score trends
**Future**: Could persist to `raw_metrics` JSONB field if needed

### Decision 3: 4-Pillar Weights (30/35/25/10)
**Rationale**: Prioritize growth (35%) and valuation (30%) over health (25%) and sentiment (10%)
**Implementation**: Hardcoded in `calculate_fundamental_score()` function
**Trade-off**: Opinionated defaults vs. user customization
**Outcome**: Reasonable defaults for growth investing, but could add user preferences later

---

## Git Commit Info

**Branch**: `claude/implement-watchlist-improvements-011CUvqDioH4JoBobHQRa8nD`

**Files Modified** (3):
1. `backend/app/watchlist/fundamentals.py` - Added 4-pillar scoring
2. `backend/app/watchlist/models.py` - Updated to 3-pillar system
3. `CLOUD_HANDOFF_PART2.md` - This file

**Files to Create** (Local Dev):
1. `backend/app/watchlist/timeframe.py` - Timeframe/volume calculations
2. `backend/app/watchlist/percentiles.py` - Percentile rank calculation
3. `backend/migrations/019_score_weight_sliders.sql` - DB migration

**Files to Modify** (Local Dev):
1. `backend/app/watchlist/scoring.py` - Add fundamental component
2. `backend/app/watchlist/refresh_processor.py` - Integrate fundamental scoring
3. `frontend/components/settings/WatchlistPreferences.tsx` - Settings sliders
4. `frontend/components/watchlist/ExpandedRow.tsx` - Score breakdown UI

---

## Next Steps for Local Dev Agent

### Phase 1: Complete Backend (2-3 hours)
1. Implement `_compute_fundamental_component()` in scoring.py
2. Update `calculate_watchlist_scores()` for 3-pillar formula
3. Integrate fundamental scoring into refresh_processor.py
4. Create timeframe.py and percentiles.py modules
5. Add volume/timeframe/percentile calculations to refresh flow

### Phase 2: Database & Testing (1 hour)
1. Create and execute migration 019
2. Run backend tests (pytest)
3. Verify fundamental scoring works end-to-end
4. Check that 3-pillar fallback to 2-pillar works

### Phase 3: Frontend (2-3 hours)
1. Update WatchlistPreferences.tsx with full slider UI
2. Update ExpandedRow.tsx with score breakdown display
3. Test settings page validation
4. Verify score breakdown displays correctly

### Phase 4: Integration & Verification (1 hour)
1. Restart services
2. Add a ticker to watchlist
3. Verify fundamental scores appear
4. Verify settings sliders work
5. Verify score breakdown displays

---

## Questions/Concerns for Local Dev

### 1. Volume Calculation Implementation
**Question**: Does `day_bars` table have 50+ days of data for all symbols?
**Impact**: If not, volume_relative will always be None
**Suggestion**: Check data availability, consider alternative (20-day average?)

### 2. Sub-Scores Persistence
**Question**: Should sub_scores be persisted to `raw_metrics` JSONB field?
**Impact**: Enables historical sub-metric charting, but increases DB size
**Suggestion**: Implement only if historical sub-metric analysis is a priority

### 3. User Weight Customization
**Question**: Should users be able to change 4-pillar weights (30/35/25/10)?
**Impact**: More flexibility, but UI complexity
**Current**: Hardcoded in `calculate_fundamental_score()`
**Future**: Could add `fundamental_sub_weights` to user preferences

---

## Honest Assessment

### What Went Well ✅
- Comprehensive research completed before implementation
- Clean separation of concerns (4 scoring functions + 1 composite)
- Models properly updated for 3-pillar system
- No fake data or workarounds (learned from Part 1)

### What's Incomplete ❌
- Scoring logic integration (scoring.py updates)
- Refresh processor integration (fundamental score calculation)
- Volume/timeframe/percentile modules (not created)
- Frontend UI components (settings + score breakdown)
- Database migration (SQL written but not executed)

### Why Stopped Here ⏸️
- Approaching context limits (100K+ tokens)
- Cloud environment cannot test database queries
- Better to hand off clean architecture than rushed code
- Part 1 lesson: Honest partial completion > fake "complete"

---

**End of Part 2 Cloud Agent Handoff**
**Ready for Local Dev Completion**
