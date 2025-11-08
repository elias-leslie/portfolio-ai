# Watchlist Improvements - Part 2: Foundation

**Created**: 2025-11-08
**Tier**: Foundation (Sprint 2)
**Estimated Effort**: 12 hours
**Environment**: Cloud Claude Code (sandbox, limited runtime)
**Priority**: HIGH
**Depends On**: Part 1 (Quick Wins) must be complete

**Status**: ⏸️ PAUSED
**Completion**: 44% (7/16 tasks complete)
**Last Updated**: 2025-11-08 14:40

**✅ COMPLETE:** Tasks 1-3 (Cloud), scoring layer integration (Local #1)
**🔄 IN PROGRESS:** None (clean handoff)
**⚠️ NEXT:** Task 4 - Integrate fundamental scoring into refresh_processor.py
**PAUSED**: 2025-11-08 14:40 (Strategic session handoff - context 79%)

<!-- PAUSED: 2025-11-08 14:40 - Resume with Task 4 integration -->

---

## 🎨 Design References (MUST FOLLOW)

**All UI implementation must align with these design references:**

1. **Text Guide**: `docs/watchlist_design_guide.md`
   - ASCII mockups showing exact layout for all views
   - Complete feature descriptions
   - Data flow architecture

2. **Visual Mockups**: `docs/design_references/watchlist_design_reference/`
   - High-fidelity UI mockups showing target design
   - Each folder contains: `screen.png` (visual reference) + `code.html` (HTML structure example)
   - Main table view, expanded row, settings panel, search/filter bar

**Implementation Priority:**
- Backend: Follow text guide for data structures and API responses
- Frontend: Use visual mockups and HTML files as **design guidelines**
  - **Layout & Structure**: Follow HTML examples for component arrangement and hierarchy
  - **Spacing**: Use similar spacing patterns (margins, padding, gaps)
  - **Colors**: **USE PROJECT'S EXISTING GLOBAL COLOR SCHEME** (not HTML colors)
    - Check existing app components for color variables/classes
    - Maintain consistency with current Portfolio AI theme
  - **Typography**: Use existing font configuration (Inter already set up)
  - HTML files show "what to build", existing codebase shows "how to style it"

**⚠️ Known Discrepancy - Sentiment Placement:**
- **Mockup**: Shows Sentiment as 4th top-level pillar (Price/Technical/Fundamental/Sentiment)
- **Implementation**: Sentiment is sub-weight of Fundamental (one of 4 pillars: Valuation/Growth/Health/Sentiment)
- **Decision**: Using implementation approach (3 main pillars) - architecturally cleaner

---

## ⚠️ IMPORTANT: Cloud Environment Constraints

**See Part 1 (tasks-cloud-watchlist-part1-quick-wins.md) for full cloud environment constraints.**

**Quick Reference**:
- ✅ CAN: Read code, write code, static analysis (ruff/mypy), git operations
- ❌ CANNOT: Run services, execute tests, database commands, curl requests
- ✅ MUST: Run ruff + mypy before committing
- ❌ NEVER: Use restart.sh, pytest, psql, curl localhost

**Your Workflow**:
1. Research thoroughly (Task 1)
2. Implement code changes
3. Run static analysis
4. Commit to git
5. Handoff to local dev for testing

---

## Overview

**Part 2 Focus**: Foundation - Core scoring system overhaul

**Part 2 Deliverables**:
- **4-Pillar Fundamental Scoring**: Valuation/Growth/Health/Sentiment (30%/35%/25%/10%)
- **3-Pillar Overall Formula**: Price 33% / Technical 33% / Fundamental 34%
- **Sub-Metric Tracking**: Price, technical, fundamental sub-scores exposed
- **Volume/Timeframe/Percentile**: Calculate and populate DB columns
- **AVOID Signal Fixes**: Pass sma_5_prev and news_sentiment correctly
- **Settings Sliders**: Weight configuration for ALL sub-metrics
- **Score Breakdown UI**: Display 3 pillars + sub-scores in expanded row
- **Database Migration**: Migration 019 for weight configuration

**Dependencies**:
- Part 1 must be complete (priority indicators, sparklines)
- Database migration script created (not executed - provide SQL)
- Static analysis must pass before commit

---

## Task 1: Research & Validation (DO THIS FIRST - Cloud Agent)

**Objective**: Understand scoring architecture, verify data models, prepare for 3-pillar implementation

**CRITICAL**: Complete ALL research before implementation. Do NOT skip.

### 1.1 Scoring System Architecture Research

#### Core Scoring Modules
- [ ] **File**: `backend/app/watchlist/scoring.py`
  - Read calculate_watchlist_scores() function completely (lines 159-201)
  - Note current formula (2-pillar: price + technical only)
  - Check _compute_price_component() function
  - Check _compute_technical_component() function
  - Understand ScoreComponent structure

- [ ] **File**: `backend/app/watchlist/models.py`
  - Read ScoreWeights class (lines 66-81)
  - Read ScoreComponent class (lines 83-91)
  - Read ScoreBreakdown class (lines 98-117)
  - Check if sub_scores field exists in ScoreComponent
  - Check if fundamental field exists in ScoreWeights

#### Fundamental Data System
- [ ] **File**: `backend/app/watchlist/fundamentals.py`
  - Read FundamentalData model (lines 37-46)
  - Check existing scoring functions
  - Check classify_company_health() function (line 297)
  - Note available fundamental metrics
  - Check if 4-pillar scoring functions exist (they don't - you'll create them)

### 1.2 Data Flow & Integration Points

#### Refresh Processor
- [ ] **File**: `backend/app/watchlist/refresh_processor.py`
  - Find where fundamental data is fetched
  - Find where scoring is called
  - Find where snapshots are created
  - Note available technical data (SMA values)
  - Check if volume data is accessible

#### Signal Classifier
- [ ] **File**: `backend/app/watchlist/signal_classifier.py`
  - Read classify_signal() function signature
  - Check AVOID detection logic
  - Note which parameters are used for AVOID flags
  - Verify sma_5_prev parameter (may be missing)

### 1.3 Database Schema & Migrations

#### Check Existing Schema
- [ ] **Migration Files**: `backend/migrations/`
  - Find latest migration number (likely 009 or later)
  - Check if user_preferences table exists
  - Check for JSONB columns in user_preferences
  - Note migration naming pattern (###_description.sql)

#### Check Snapshot Columns
- [ ] **Migration 009** (if exists):
  - Verify volume_relative column in watchlist_snapshots
  - Verify timeframe_short_aligned column
  - Verify timeframe_long_aligned column
  - Verify percentile_rank_30d column
  - Verify sma_5 column in technical_indicators table

### 1.4 Frontend Components Research

#### Settings Page
- [ ] **File**: `frontend/components/settings/WatchlistPreferences.tsx`
  - Find score weights section (lines 525-586)
  - Check existing slider implementation
  - Note state management pattern
  - Check if fundamental weight exists (it doesn't - only price/technical)

#### Expanded Row Component
- [ ] **File**: `frontend/components/watchlist/ExpandedRow.tsx`
  - Find Trading Intelligence section
  - Check how scores are currently displayed
  - Note available space for score breakdown
  - Check item.current_score structure

### 1.5 Document Findings

#### Implementation Plan (update after research):

**4-Pillar Fundamental Scoring**:
- Files to modify:
  - `backend/app/watchlist/fundamentals.py` - Add 5 new functions (~150 lines)
  - `backend/app/watchlist/models.py` - Add sub_scores field to ScoreComponent
  - `backend/app/watchlist/scoring.py` - Add _compute_fundamental_component()
  - `backend/app/watchlist/refresh_processor.py` - Calculate fundamental sub-scores

**3-Pillar Formula**:
- Files to modify:
  - `backend/app/watchlist/models.py` - Update ScoreWeights (add fundamental: 34.0)
  - `backend/app/watchlist/models.py` - Update ScoreBreakdown (add fundamental: ScoreComponent | None)
  - `backend/app/watchlist/scoring.py` - Update calculate_watchlist_scores() to handle 3 pillars

**Volume/Timeframe/Percentile**:
- Files to create:
  - `backend/app/watchlist/timeframe.py` (~60 lines)
  - `backend/app/watchlist/percentiles.py` (~30 lines)
- Files to modify:
  - `backend/app/watchlist/refresh_processor.py` - Calculate all 4 values before snapshot

**AVOID Signal Fixes**:
- Files to modify:
  - `backend/app/watchlist/signal_classifier.py` - Add sma_5_prev parameter
  - Caller of classify_signal() - Pass sma_5_prev and news_sentiment

**Settings Sliders**:
- Files to create:
  - `backend/migrations/019_score_weight_sliders.sql` (~25 lines)
- Files to modify:
  - `frontend/components/settings/WatchlistPreferences.tsx` - Replace score weights section (~200 lines)

**Score Breakdown UI**:
- Files to modify:
  - `frontend/components/watchlist/ExpandedRow.tsx` - Add score breakdown section (~90 lines)

#### Dependencies Map:
```
1. Fundamental scoring → 3-pillar formula
2. 3-pillar formula → Sub-scores tracking
3. Sub-scores tracking → Settings sliders
4. Settings sliders → Database migration
5. All backend changes → UI score breakdown
```

#### Risks & Mitigations:
- **Risk**: Fundamental data may be NULL for some stocks
  - **Mitigation**: Fallback to 2-pillar scoring, graceful degradation
- **Risk**: Volume calculations need OHLCV data
  - **Mitigation**: Query day_bars table, handle missing data
- **Risk**: Percentile needs 30 days of history
  - **Mitigation**: Default to 50.0 if no history, accumulates over time

---

## Task 2: 4-Pillar Fundamental Scoring

**Goal**: Implement valuation/growth/health/sentiment scoring system

**Estimated Time**: 3 hours

### 2.1 Add Fundamental Scoring Functions

**File**: `backend/app/watchlist/fundamentals.py`
**Location**: After `classify_company_health()` function (after line 297)

Add 5 new functions (~150 lines):

```python
def calculate_valuation_score(data: FundamentalData) -> float:
    """Calculate valuation score (0-100) based on P/E, P/B, profit margin.

    Weight: 30% of fundamental score

    Scoring:
    - Profit margin >20% = 90, >10% = 70, >5% = 50, else 30
    - TODO: Add P/E, P/B, PEG ratios when available

    Args:
        data: FundamentalData with company metrics

    Returns:
        Valuation score 0-100 (higher = better value)
    """
    profit_margin = data.profit_margin or 0.06

    # Simple scoring using available data
    if profit_margin > 0.20:
        return 90.0
    elif profit_margin > 0.10:
        return 70.0
    elif profit_margin > 0.05:
        return 50.0
    else:
        return 30.0


def calculate_growth_score(data: FundamentalData) -> float:
    """Calculate growth score (0-100) based on revenue and earnings growth.

    Weight: 35% of fundamental score

    Scoring:
    - Revenue growth >30% = 100, 20-30% = 80, 10-20% = 60, 5-10% = 40, <5% = 20

    Args:
        data: FundamentalData with company metrics

    Returns:
        Growth score 0-100 (higher = faster growth)
    """
    revenue_growth = data.revenue_growth or 0.06

    if revenue_growth > 0.30:
        return 100.0
    elif revenue_growth > 0.20:
        return 80.0
    elif revenue_growth > 0.10:
        return 60.0
    elif revenue_growth > 0.05:
        return 40.0
    else:
        return 20.0


def calculate_health_score(data: FundamentalData) -> float:
    """Calculate financial health score (0-100) based on debt and profitability.

    Weight: 25% of fundamental score

    Scoring:
    - Debt/Equity: <0.3 = 100, <0.7 = 80, <1.5 = 60, <2.5 = 40, else 20
    - Profit margin: >20% = 100, >10% = 80, >5% = 60, >0% = 40, else 0
    - Average the 2 scores

    Args:
        data: FundamentalData with company metrics

    Returns:
        Health score 0-100 (higher = healthier)
    """
    debt_to_equity = data.debt_to_equity or 1.0
    profit_margin = data.profit_margin or 0.06

    # Debt scoring
    if debt_to_equity < 0.3:
        debt_score = 100.0
    elif debt_to_equity < 0.7:
        debt_score = 80.0
    elif debt_to_equity < 1.5:
        debt_score = 60.0
    elif debt_to_equity < 2.5:
        debt_score = 40.0
    else:
        debt_score = 20.0

    # Profit margin scoring
    if profit_margin > 0.20:
        margin_score = 100.0
    elif profit_margin > 0.10:
        margin_score = 80.0
    elif profit_margin > 0.05:
        margin_score = 60.0
    elif profit_margin > 0:
        margin_score = 40.0
    else:
        margin_score = 0.0

    return (debt_score + margin_score) / 2.0


def calculate_sentiment_score(data: FundamentalData) -> float:
    """Calculate analyst sentiment score (0-100) based on recommendations.

    Weight: 10% of fundamental score

    Scoring based on recommendation_mean (1=strong buy, 5=sell):
    - 1.0-1.5 = 100, 1.5-2.0 = 80, 2.0-2.5 = 60, 2.5-3.5 = 40, 3.5-4.5 = 20, >4.5 = 0

    Args:
        data: FundamentalData with company metrics

    Returns:
        Sentiment score 0-100 (higher = more bullish)
    """
    rec_mean = data.recommendation_mean or 3.0

    if rec_mean < 1.5:
        return 100.0
    elif rec_mean < 2.0:
        return 80.0
    elif rec_mean < 2.5:
        return 60.0
    elif rec_mean < 3.5:
        return 40.0
    elif rec_mean < 4.5:
        return 20.0
    else:
        return 0.0


def calculate_fundamental_score(data: FundamentalData) -> float:
    """Calculate overall fundamental score (0-100) using 4-pillar system.

    Pillars:
    - Valuation: 30% (P/E, P/B, profit margin)
    - Growth: 35% (revenue, earnings)
    - Health: 25% (debt, margins)
    - Sentiment: 10% (analyst ratings)

    Args:
        data: FundamentalData with company metrics

    Returns:
        Overall fundamental score (0-100)
    """
    valuation = calculate_valuation_score(data)
    growth = calculate_growth_score(data)
    health = calculate_health_score(data)
    sentiment = calculate_sentiment_score(data)

    # Weighted average (30/35/25/10)
    overall = (
        valuation * 0.30 +
        growth * 0.35 +
        health * 0.25 +
        sentiment * 0.10
    )

    return overall
```

### 2.2 Update FundamentalData Model

**File**: `backend/app/watchlist/fundamentals.py`
**Location**: In `FundamentalData` model (around line 37-46)

Add fields to FundamentalData:
```python
# 4-pillar scores (calculated)
fundamental_score: float | None = None  # Overall 0-100
valuation_score: float | None = None  # 0-100
growth_score: float | None = None  # 0-100
health_score: float | None = None  # 0-100
sentiment_score: float | None = None  # 0-100
```

### 2.3 Calculate Fundamental Scores in Refresh Processor

**File**: `backend/app/watchlist/refresh_processor.py`
**Location**: After fundamental data is fetched (search for "fundamental_data")

Add imports at top:
```python
from app.watchlist.fundamentals import (
    calculate_valuation_score,
    calculate_growth_score,
    calculate_health_score,
    calculate_sentiment_score,
    calculate_fundamental_score,
)
```

After fetching fundamental_data, add:
```python
if fundamental_data:
    # Calculate 4-pillar scores
    fundamental_data.valuation_score = calculate_valuation_score(fundamental_data)
    fundamental_data.growth_score = calculate_growth_score(fundamental_data)
    fundamental_data.health_score = calculate_health_score(fundamental_data)
    fundamental_data.sentiment_score = calculate_sentiment_score(fundamental_data)
    fundamental_data.fundamental_score = calculate_fundamental_score(fundamental_data)
```

---

## Task 3: 3-Pillar Score Formula & Models

**Goal**: Update scoring system to support price/technical/fundamental (33/33/34)

**Estimated Time**: 2 hours

### 3.1 Update ScoreWeights Model

**File**: `backend/app/watchlist/models.py`
**Location**: Replace ScoreWeights class (lines 66-81)

```python
class ScoreWeights(BaseModel):
    """Weights used to compute overall watchlist score (3-pillar system)."""

    price: float = 33.0
    technical: float = 33.0
    fundamental: float = 34.0  # NEW: Third pillar

    @property
    def total(self) -> float:
        return self.price + self.technical + self.fundamental

    def normalized(self) -> dict[str, float]:
        """Normalize weights to sum to 1.0."""
        total = self.total
        if total <= 0:
            return {"price": 0.33, "technical": 0.33, "fundamental": 0.34}
        return {
            "price": self.price / total,
            "technical": self.technical / total,
            "fundamental": self.fundamental / total,
        }
```

### 3.2 Update ScoreComponent Model

**File**: `backend/app/watchlist/models.py`
**Location**: In ScoreComponent (around line 83-91)

Add field:
```python
sub_scores: dict[str, float] = Field(
    default_factory=dict,
    description="Sub-metric scores (e.g., rsi_14, trend, macd for technical)",
)
```

### 3.3 Update ScoreBreakdown Model

**File**: `backend/app/watchlist/models.py`
**Location**: Replace ScoreBreakdown class (lines 98-117)

```python
class ScoreBreakdown(BaseModel):
    """Score breakdown for a watchlist item (3-pillar system)."""

    price: ScoreComponent
    technical: ScoreComponent
    fundamental: ScoreComponent | None = None  # NEW: May be None if not fetched

    overall: float

    @field_validator("overall", mode="before")
    @classmethod
    def clamp_overall(cls, value: float) -> float:
        """Clamp overall score to 0-100."""
        return max(0.0, min(100.0, float(value)))

    def to_snapshot_payload(self) -> dict[str, Any]:
        """Serialize score metadata for persistence."""
        return {
            "price": self.price.model_dump(mode="json"),
            "technical": self.technical.model_dump(mode="json"),
            "fundamental": self.fundamental.model_dump(mode="json") if self.fundamental else None,
            "overall": self.overall,
        }
```

### 3.4 Add Fundamental Component Calculation

**File**: `backend/app/watchlist/scoring.py`
**Location**: After `_compute_technical_component()` function (after line 156)

Add new function (~50 lines):
```python
def _compute_fundamental_component(
    fundamental_data: Any,  # FundamentalData with scores
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
    if not fundamental_data or not hasattr(fundamental_data, "fundamental_score"):
        return ScoreComponent(
            score=0.0,
            weight=weight,
            stale=True,
            metadata={"reason": "missing_fundamental_data"},
            sub_scores={},
        )

    score = fundamental_data.fundamental_score or 0.0

    # Sub-scores breakdown (4 pillars)
    sub_scores = {
        "valuation": fundamental_data.valuation_score or 0.0,
        "growth": fundamental_data.growth_score or 0.0,
        "health": fundamental_data.health_score or 0.0,
        "sentiment": fundamental_data.sentiment_score or 0.0,
    }

    metadata = {
        "health_classification": fundamental_data.company_health if hasattr(fundamental_data, "company_health") else None,
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

### 3.5 Update Scoring Formula to 3-Pillar

**File**: `backend/app/watchlist/scoring.py`
**Location**: Replace `calculate_watchlist_scores()` function (lines 159-201)

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
        "macd": technical_component.metadata.get("macd", 0.0),
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

---

## Task 4: Volume, Timeframe, Percentile Calculations

**Goal**: Calculate and populate volume_relative, timeframe_short_aligned, timeframe_long_aligned, percentile_rank_30d

**Estimated Time**: 3 hours

### 4.1 Create Timeframe Analysis Module

**File**: `backend/app/watchlist/timeframe.py` (NEW)

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

### 4.2 Create Percentile Calculation Module

**File**: `backend/app/watchlist/percentiles.py` (NEW)

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

### 4.3 Integrate into Refresh Processor

**File**: `backend/app/watchlist/refresh_processor.py`
**Location**: Where snapshot is created (search for "WatchlistSnapshot")

Add imports:
```python
from app.watchlist.timeframe import calculate_timeframe_alignment, calculate_volume_relative
from app.watchlist.percentiles import calculate_percentile_rank
```

Add calculations before snapshot creation:
```python
# Calculate timeframe alignment
short_aligned, long_aligned = calculate_timeframe_alignment(
    price=price_data.price,
    sma_20=technical.sma_20,
    sma_50=technical.sma_50,
    sma_200=technical.sma_200,
)

# Calculate volume relative
# TODO: Query day_bars for 50-day average volume
# For now, use placeholder logic
volume_relative = calculate_volume_relative(
    current_volume=current_volume,  # Get from latest OHLCV
    avg_volume_50d=avg_volume_50d,  # Calculate from day_bars
)

# Calculate percentile rank (need last 30 days of snapshots)
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

---

## Task 5: Fix AVOID Signal Bugs

**Goal**: Ensure sma_5_prev and news_sentiment are passed to signal classifier

**Estimated Time**: 2 hours

### 5.1 Update Signal Classifier Function

**File**: `backend/app/watchlist/signal_classifier.py`
**Location**: In `classify_signal()` function

Verify parameters include:
```python
def classify_signal(
    price_score: float,
    technical_score: float,
    fundamental_score: float | None,
    sma_5: float | None,
    sma_5_prev: float | None,  # VERIFY THIS EXISTS
    news_sentiment: float | None,  # VERIFY THIS EXISTS
    volume_relative: float | None,
    ...
) -> SignalClassification:
    """Classify watchlist signal (BUY/HOLD/AVOID)."""

    # ... existing logic ...

    # AVOID detection (2+ flags)
    avoid_flags = 0

    # Flag 1: Declining 5-day trend
    if sma_5 and sma_5_prev and sma_5 < sma_5_prev:
        avoid_flags += 1

    # Flag 2: Negative news
    if news_sentiment and news_sentiment < -0.3:
        avoid_flags += 1

    # Flag 3: Low price score
    if price_score < 30:
        avoid_flags += 1

    # Flag 4: Poor fundamentals
    if fundamental_score and fundamental_score < 30:
        avoid_flags += 1

    # AVOID threshold: 2+ flags (changed from 3)
    if avoid_flags >= 2:
        return SignalClassification(
            signal_type=SignalType.AVOID,
            strength=SignalStrength(value=avoid_flags * 2),
            reasons=[...],
        )
```

### 5.2 Update Caller to Pass sma_5_prev

**File**: Where classify_signal() is called (likely `refresh_processor.py` or `watchlist_service.py`)

Query previous SMA_5 value:
```python
# Fetch previous SMA_5 from technical_indicators
sma_5_prev_query = """
    SELECT sma_5
    FROM technical_indicators
    WHERE symbol = %s
      AND fetched_at < %s
    ORDER BY fetched_at DESC
    LIMIT 1
"""
sma_5_prev_result = conn.execute(sma_5_prev_query, [symbol, current_timestamp]).fetchone()
sma_5_prev = sma_5_prev_result[0] if sma_5_prev_result else None

# Pass to classify_signal
signal = classify_signal(
    ...,
    sma_5=technical.sma_5,
    sma_5_prev=sma_5_prev,  # ADD THIS
    news_sentiment=news_intel.sentiment_score if news_intel else None,  # VERIFY THIS
    ...
)
```

---

## Task 6: Settings Page - Weight Sliders for ALL Sub-Metrics

**Goal**: Add weight configuration UI for price/technical/fundamental and ALL their sub-metrics

**Estimated Time**: 2 hours

### 6.1 Create Database Migration

**File**: `backend/migrations/019_score_weight_sliders.sql` (NEW)

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

**DO NOT EXECUTE** - Provide SQL file for local dev environment to execute.

### 6.2 Update WatchlistPreferences Component

**File**: `frontend/components/settings/WatchlistPreferences.tsx`
**Location**: Replace score weights section (lines 525-586)

Add state variables at top:
```typescript
// Top-level weights
const [priceWeight, setPriceWeight] = useState(33);
const [technicalWeight, setTechnicalWeight] = useState(33);
const [fundamentalWeight, setFundamentalWeight] = useState(34);

// Technical sub-weights
const [rsiWeight, setRsiWeight] = useState(33);
const [trendWeight, setTrendWeight] = useState(34);
const [macdWeight, setMacdWeight] = useState(33);

// Fundamental sub-weights
const [valuationWeight, setValuationWeight] = useState(30);
const [growthWeight, setGrowthWeight] = useState(35);
const [healthWeight, setHealthWeight] = useState(25);
const [sentimentWeight, setSentimentWeight] = useState(10);
```

Replace score weights section with (~150 lines):
```typescript
{/* Score Weights - 3 Pillars */}
<div className="space-y-4 rounded-md border border-border bg-surface-muted/30 p-4">
  <div className="flex items-center justify-between">
    <h4 className="text-sm font-medium text-text">
      Score Weights (3-Pillar System)
    </h4>
    <Button
      variant="outline"
      size="sm"
      onClick={() => {
        setPriceWeight(33);
        setTechnicalWeight(33);
        setFundamentalWeight(34);
      }}
    >
      Reset to 33/33/34
    </Button>
  </div>

  {/* Price Weight */}
  <div className="space-y-3">
    <Label htmlFor="price-weight">
      💰 Price Score: {priceWeight.toFixed(1)}%
    </Label>
    <Slider
      id="price-weight"
      min={0}
      max={100}
      step={0.1}
      value={[priceWeight]}
      onValueChange={(value) => setPriceWeight(value[0])}
    />
  </div>

  {/* Technical Weight + Sub-Metrics */}
  <div className="space-y-3">
    <Label htmlFor="technical-weight">
      📊 Technical Score: {technicalWeight.toFixed(1)}%
    </Label>
    <Slider
      id="technical-weight"
      min={0}
      max={100}
      step={0.1}
      value={[technicalWeight]}
      onValueChange={(value) => setTechnicalWeight(value[0])}
    />

    {/* Technical Sub-Weights */}
    <div className="ml-4 space-y-2">
      <p className="text-xs text-text-muted">Sub-metrics:</p>

      <div className="space-y-2">
        <Label className="text-xs">RSI: {rsiWeight.toFixed(1)}%</Label>
        <Slider
          min={0}
          max={100}
          step={0.1}
          value={[rsiWeight]}
          onValueChange={(value) => setRsiWeight(value[0])}
        />
      </div>

      <div className="space-y-2">
        <Label className="text-xs">Trend: {trendWeight.toFixed(1)}%</Label>
        <Slider
          min={0}
          max={100}
          step={0.1}
          value={[trendWeight]}
          onValueChange={(value) => setTrendWeight(value[0])}
        />
      </div>

      <div className="space-y-2">
        <Label className="text-xs">MACD: {macdWeight.toFixed(1)}%</Label>
        <Slider
          min={0}
          max={100}
          step={0.1}
          value={[macdWeight]}
          onValueChange={(value) => setMacdWeight(value[0])}
        />
      </div>

      <p className={`text-xs ${Math.abs(rsiWeight + trendWeight + macdWeight - 100) < 0.1 ? 'text-text-muted' : 'text-loss'}`}>
        Total: {(rsiWeight + trendWeight + macdWeight).toFixed(1)}% (must be 100%)
      </p>
    </div>
  </div>

  {/* Fundamental Weight + Sub-Metrics */}
  <div className="space-y-3">
    <Label htmlFor="fundamental-weight">
      🏢 Fundamental Score: {fundamentalWeight.toFixed(1)}%
    </Label>
    <Slider
      id="fundamental-weight"
      min={0}
      max={100}
      step={0.1}
      value={[fundamentalWeight]}
      onValueChange={(value) => setFundamentalWeight(value[0])}
    />

    {/* Fundamental Sub-Weights */}
    <div className="ml-4 space-y-2">
      <p className="text-xs text-text-muted">Sub-metrics (4-pillar):</p>

      <div className="space-y-2">
        <Label className="text-xs">Valuation: {valuationWeight.toFixed(1)}%</Label>
        <Slider
          min={0}
          max={100}
          step={0.1}
          value={[valuationWeight]}
          onValueChange={(value) => setValuationWeight(value[0])}
        />
      </div>

      <div className="space-y-2">
        <Label className="text-xs">Growth: {growthWeight.toFixed(1)}%</Label>
        <Slider
          min={0}
          max={100}
          step={0.1}
          value={[growthWeight]}
          onValueChange={(value) => setGrowthWeight(value[0])}
        />
      </div>

      <div className="space-y-2">
        <Label className="text-xs">Health: {healthWeight.toFixed(1)}%</Label>
        <Slider
          min={0}
          max={100}
          step={0.1}
          value={[healthWeight]}
          onValueChange={(value) => setHealthWeight(value[0])}
        />
      </div>

      <div className="space-y-2">
        <Label className="text-xs">Sentiment: {sentimentWeight.toFixed(1)}%</Label>
        <Slider
          min={0}
          max={100}
          step={0.1}
          value={[sentimentWeight]}
          onValueChange={(value) => setSentimentWeight(value[0])}
        />
      </div>

      <p className={`text-xs ${Math.abs(valuationWeight + growthWeight + healthWeight + sentimentWeight - 100) < 0.1 ? 'text-text-muted' : 'text-loss'}`}>
        Total: {(valuationWeight + growthWeight + healthWeight + sentimentWeight).toFixed(1)}% (must be 100%)
      </p>
    </div>
  </div>

  {/* Top-Level Validation */}
  <div className="flex items-center justify-between pt-2 border-t">
    <p className={`text-sm ${Math.abs(priceWeight + technicalWeight + fundamentalWeight - 100) < 0.1 ? 'text-text-muted' : 'text-loss'}`}>
      Overall Total: {(priceWeight + technicalWeight + fundamentalWeight).toFixed(1)}%
      {Math.abs(priceWeight + technicalWeight + fundamentalWeight - 100) >= 0.1 && " (must be 100%)"}
    </p>
  </div>
</div>
```

---

## Task 7: Score Breakdown Display in UI

**Goal**: Show 3-pillar breakdown with sub-metrics in ExpandedRow

**Estimated Time**: 1 hour

**File**: `frontend/components/watchlist/ExpandedRow.tsx`
**Location**: In "Trading Intelligence" section

Add new section (~90 lines):
```typescript
{/* Score Breakdown (3-Pillar) */}
<div className="space-y-3">
  <h4 className="text-sm font-semibold text-text">📊 Score Breakdown</h4>

  <div className="space-y-2">
    {/* Overall Score */}
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="text-text-muted">Overall</span>
        <span className="font-bold text-text">{item.current_score?.overall.toFixed(0)}</span>
      </div>
      <div className="h-2 bg-surface-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-primary"
          style={{ width: `${item.current_score?.overall || 0}%` }}
        />
      </div>
    </div>

    {/* Price Component */}
    {item.current_score?.price && (
      <div>
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-text-muted">💰 Price ({(item.current_score.price.weight * 100).toFixed(0)}%)</span>
          <span className="font-medium">{item.current_score.price.score.toFixed(0)}</span>
        </div>
        <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-gain"
            style={{ width: `${item.current_score.price.score}%` }}
          />
        </div>
        {/* Sub-scores */}
        {item.current_score.price.sub_scores && (
          <div className="ml-4 mt-1 text-[10px] text-text-muted">
            {Object.entries(item.current_score.price.sub_scores).map(([key, value]) => (
              <div key={key}>• {key}: {typeof value === 'number' ? value.toFixed(1) : value}</div>
            ))}
          </div>
        )}
      </div>
    )}

    {/* Technical Component */}
    {item.current_score?.technical && (
      <div>
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-text-muted">📊 Technical ({(item.current_score.technical.weight * 100).toFixed(0)}%)</span>
          <span className="font-medium">{item.current_score.technical.score.toFixed(0)}</span>
        </div>
        <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary"
            style={{ width: `${item.current_score.technical.score}%` }}
          />
        </div>
        {/* Sub-scores */}
        {item.current_score.technical.sub_scores && (
          <div className="ml-4 mt-1 text-[10px] text-text-muted">
            {Object.entries(item.current_score.technical.sub_scores).map(([key, value]) => (
              <div key={key}>• {key}: {typeof value === 'number' ? value.toFixed(1) : value}</div>
            ))}
          </div>
        )}
      </div>
    )}

    {/* Fundamental Component */}
    {item.current_score?.fundamental && (
      <div>
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-text-muted">🏢 Fundamental ({(item.current_score.fundamental.weight * 100).toFixed(0)}%)</span>
          <span className="font-medium">{item.current_score.fundamental.score.toFixed(0)}</span>
        </div>
        <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-gain"
            style={{ width: `${item.current_score.fundamental.score}%` }}
          />
        </div>
        {/* Sub-scores (4-pillar) */}
        {item.current_score.fundamental.sub_scores && (
          <div className="ml-4 mt-1 text-[10px] text-text-muted space-y-0.5">
            <div>• Valuation: {item.current_score.fundamental.sub_scores.valuation?.toFixed(0) || 'N/A'}</div>
            <div>• Growth: {item.current_score.fundamental.sub_scores.growth?.toFixed(0) || 'N/A'}</div>
            <div>• Health: {item.current_score.fundamental.sub_scores.health?.toFixed(0) || 'N/A'}</div>
            <div>• Sentiment: {item.current_score.fundamental.sub_scores.sentiment?.toFixed(0) || 'N/A'}</div>
          </div>
        )}
      </div>
    )}
  </div>
</div>
```

---

## Task 8: Static Analysis & Code Quality

**Goal**: Ensure all code passes linting and type checking

**Estimated Time**: 30 minutes

### 8.1 Run Backend Linting

```bash
# All modified watchlist modules
ruff check backend/app/watchlist/
ruff format backend/app/watchlist/
```

### 8.2 Run Backend Type Checking

```bash
# Strict type checking
mypy backend/app/watchlist/ --strict
```

### 8.3 Fix All Errors

- [ ] Fix ALL ruff errors
- [ ] Fix ALL mypy errors
- [ ] Document any `# type: ignore` with justification
- [ ] Verify all imports at module level

---

## Task 9: Git Commit & Handoff

**Goal**: Commit Part 2 changes and handoff to local dev

**Estimated Time**: 15 minutes

### 9.1 Commit

```bash
git add -A
git commit -m "feat(watchlist): Part 2 Foundation - 3-pillar scoring, settings sliders

Backend Changes:
- 4-pillar fundamental scoring (valuation/growth/health/sentiment)
- 3-pillar overall formula (price 33%, technical 33%, fundamental 34%)
- Sub-scores tracking for all components
- Volume/timeframe/percentile calculation modules
- AVOID signal bug fixes (sma_5_prev, news_sentiment)
- Migration 019 for weight configuration

Frontend Changes:
- Settings sliders for ALL sub-metrics (12 total)
- 3-pillar score breakdown in expanded row
- Sub-score display for each pillar

Part 2 of 3 (Foundation tier, 12 hours)"
```

---

## Handoff Instructions

**What Cloud Agent Completed**:
- 4-pillar fundamental scoring ✅
- 3-pillar formula ✅
- Settings sliders ✅
- Score breakdown UI ✅
- Static analysis passed ✅

**What Local Dev Must Do**:
1. Pull branch
2. Execute migration 019: `psql -U portfolio_ai_user -d portfolio_ai -f backend/migrations/019_score_weight_sliders.sql`
3. Restart services
4. Test fundamental scoring
5. Test settings sliders
6. Test score breakdown UI
7. Run test suite

**Branch**: `[branch-name]`

---

**END OF PART 2**
