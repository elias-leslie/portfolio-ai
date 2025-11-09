# Watchlist Improvements - Implementation Task List

**Created**: 2025-11-08
**Based on**: Multi-pass code review (3 passes completed)
**User Feedback**: Integrated all 5 clarifications
**Status**: Ready for implementation

---

## Implementation Notes

**Key Changes from Original Plan**:
1. ✅ Show price/technical/fundamental score breakdowns (not just fundamental)
2. ✅ Add weight sliders for ALL sub-metrics (RSI, MACD, trend, change_pct, valuation, growth, health, sentiment)
3. ✅ NO arbitrary cap on priority indicators (show all relevant ones)
4. ✅ Automated scheduled task for sparkline data (not manual backfill)
5. ✅ All tiers included (Quick Wins + Foundation + Polish)

---

## Sprint 1: Quick Wins (Day 1, ~6 hours)

### Task 1.1: Priority Indicators - Backend (2 hours)

**Goal**: Create priority indicator calculation system (ALL 8 indicators, no cap)

#### 1.1.1 Create priority indicators module
**File**: `backend/app/watchlist/priority.py` (NEW)
**Lines**: ~200 lines

```python
"""Priority indicator calculation for watchlist items."""

from __future__ import annotations

from pydantic import BaseModel

class PriorityIndicator(BaseModel):
    """Priority indicator model."""
    icon: str  # "🔥", "📋", "📰", "📈", "📉", "💎", "⚡", "⚠️"
    label: str  # "Hot Opportunity", "Earnings Alert", etc.
    tooltip: str  # Full explanation for hover
    priority: int  # 1-8 for sorting (1 = highest)
    category: str  # "time_sensitive", "risk", "opportunity", "caution"

# Constants
PRIORITY_ORDER = {
    "hot_opportunity": 1,
    "earnings_alert": 2,
    "breaking_news": 3,
    "insider_buying": 4,
    "negative_catalyst": 5,
    "value_play": 6,
    "momentum": 7,
    "caution": 8,
}

def check_hot_opportunity(item: dict, rank: int) -> PriorityIndicator | None:
    """Top 3 BUY signals by overall score."""
    if item.get("signal_type") == "BUY" and rank <= 3:
        return PriorityIndicator(
            icon="🔥",
            label="Hot Opportunity",
            tooltip=f"Top #{rank} highest-scoring BUY signal. Strong technical and fundamental alignment.",
            priority=PRIORITY_ORDER["hot_opportunity"],
            category="opportunity",
        )
    return None

def check_earnings_alert(item: dict) -> PriorityIndicator | None:
    """Earnings within 7 days."""
    days_away = item.get("earnings_days_away")
    if days_away is not None and 0 <= days_away <= 7:
        return PriorityIndicator(
            icon="📋",
            label="Earnings Alert",
            tooltip=f"Earnings report in {days_away} days. Volatility expected.",
            priority=PRIORITY_ORDER["earnings_alert"],
            category="time_sensitive",
        )
    return None

def check_breaking_news(item: dict) -> PriorityIndicator | None:
    """10+ articles in 24h."""
    news_intel = item.get("news_intelligence")
    if news_intel and news_intel.get("article_count_24h", 0) >= 10:
        count = news_intel["article_count_24h"]
        return PriorityIndicator(
            icon="📰",
            label="Breaking News",
            tooltip=f"{count} articles in 24h. Major news flow - investigate.",
            priority=PRIORITY_ORDER["breaking_news"],
            category="time_sensitive",
        )
    return None

def check_insider_buying(item: dict) -> PriorityIndicator | None:
    """Insider trades >$1M (from news_intelligence.key_events)."""
    news_intel = item.get("news_intelligence")
    if not news_intel:
        return None

    key_events = news_intel.get("key_events", [])
    for event in key_events:
        if event.get("event_category") == "insider_trade":
            # Parse transaction value from text if available
            # For now, just check category existence
            return PriorityIndicator(
                icon="📈",
                label="Insider Buying",
                tooltip="Recent insider purchases detected. Bullish signal.",
                priority=PRIORITY_ORDER["insider_buying"],
                category="opportunity",
            )
    return None

def check_negative_catalyst(item: dict) -> PriorityIndicator | None:
    """News sentiment <-0.3."""
    sentiment = item.get("news_sentiment_score")
    if sentiment is not None and sentiment < -0.3:
        return PriorityIndicator(
            icon="📉",
            label="Negative Catalyst",
            tooltip=f"Bearish news flow (sentiment: {sentiment:.2f}). Wait for clarity.",
            priority=PRIORITY_ORDER["negative_catalyst"],
            category="risk",
        )
    return None

def check_value_play(item: dict) -> PriorityIndicator | None:
    """High fundamental (>70), low price score (<50)."""
    score = item.get("score")
    if not score:
        return None

    fundamental = score.get("fundamental", {}).get("score")
    price = score.get("price", {}).get("score")

    if fundamental and price and fundamental > 70 and price < 50:
        return PriorityIndicator(
            icon="💎",
            label="Value Play",
            tooltip=f"Strong fundamentals ({fundamental:.0f}) but low price momentum ({price:.0f}). Contrarian opportunity.",
            priority=PRIORITY_ORDER["value_play"],
            category="opportunity",
        )
    return None

def check_momentum(item: dict) -> PriorityIndicator | None:
    """Price >70 AND technical >70."""
    score = item.get("score")
    if not score:
        return None

    price = score.get("price", {}).get("score")
    technical = score.get("technical", {}).get("score")

    if price and technical and price > 70 and technical > 70:
        return PriorityIndicator(
            icon="⚡",
            label="Momentum",
            tooltip=f"Strong price ({price:.0f}) and technical ({technical:.0f}) momentum. Trend play.",
            priority=PRIORITY_ORDER["momentum"],
            category="opportunity",
        )
    return None

def check_caution(item: dict) -> PriorityIndicator | None:
    """Score misalignment: (price >70 AND fundamental <40) OR (price <30 AND fundamental >70)."""
    score = item.get("score")
    if not score:
        return None

    price = score.get("price", {}).get("score")
    fundamental = score.get("fundamental", {}).get("score")

    if not price or not fundamental:
        return None

    if (price > 70 and fundamental < 40) or (price < 30 and fundamental > 70):
        return PriorityIndicator(
            icon="⚠️",
            label="Caution",
            tooltip=f"Score mismatch (price: {price:.0f}, fundamental: {fundamental:.0f}). Mixed signals - wait for confirmation.",
            priority=PRIORITY_ORDER["caution"],
            category="caution",
        )
    return None

def calculate_priority_indicators(
    all_items: list[dict],
    current_item: dict,
) -> list[PriorityIndicator]:
    """Calculate priority indicators for a watchlist item.

    NO ARBITRARY CAP - returns ALL applicable indicators, sorted by priority.

    Args:
        all_items: All watchlist items (for ranking)
        current_item: Item being evaluated

    Returns:
        List of priority indicators, sorted by priority (highest first)
    """
    # Rank items by overall score for hot_opportunity check
    sorted_items = sorted(
        all_items,
        key=lambda x: x.get("score", {}).get("overall", 0),
        reverse=True,
    )
    rank = sorted_items.index(current_item) + 1 if current_item in sorted_items else 999

    # Run all 8 checks
    indicators: list[PriorityIndicator] = []

    checks = [
        check_hot_opportunity(current_item, rank),
        check_earnings_alert(current_item),
        check_breaking_news(current_item),
        check_insider_buying(current_item),
        check_negative_catalyst(current_item),
        check_value_play(current_item),
        check_momentum(current_item),
        check_caution(current_item),
    ]

    # Collect non-None results
    indicators = [ind for ind in checks if ind is not None]

    # Sort by priority (1 = highest)
    indicators.sort(key=lambda x: x.priority)

    return indicators
```

#### 1.1.2 Integrate into API response
**File**: `backend/app/watchlist/response_builders.py`
**Location**: After line 96 (after news_intelligence field)

Add to `WatchlistItemResponse` model:
```python
priority_indicators: list[dict[str, Any]] = Field(default_factory=list)
```

**File**: `backend/app/watchlist/response_builders.py`
**Location**: In `from_service_dict()` method, after line 168

Add:
```python
priority_indicators=item.get("priority_indicators", []),
```

#### 1.1.3 Calculate in watchlist service
**File**: `backend/app/watchlist/watchlist_service.py`
**Location**: In `get_items_with_scores()` method

Add import at top:
```python
from app.watchlist.priority import calculate_priority_indicators
```

After building all items (search for "return items" at end of method), add:
```python
# Calculate priority indicators (after all items built)
for item in items:
    indicators = calculate_priority_indicators(items, item)
    item["priority_indicators"] = [ind.model_dump() for ind in indicators]

return items
```

---

### Task 1.2: Priority Indicators - Frontend (1 hour)

#### 1.2.1 Update TypeScript types
**File**: `frontend/lib/api/watchlist.ts`
**Location**: After WatchlistItem interface

Add:
```typescript
export interface PriorityIndicator {
  icon: string;
  label: string;
  tooltip: string;
  priority: number;
  category: "time_sensitive" | "risk" | "opportunity" | "caution";
}
```

Add to `WatchlistItem` interface:
```typescript
priority_indicators?: PriorityIndicator[];
```

#### 1.2.2 Display in WatchlistTable
**File**: `frontend/components/watchlist/WatchlistTable.tsx`
**Location**: In the Signal column rendering (search for "signal_type")

Replace signal cell with:
```typescript
<TableCell>
  <div className="flex items-center gap-1">
    {/* Signal Badge */}
    <Badge variant={getSignalVariant(item.signal_type || "HOLD")}>
      {item.signal_type || "HOLD"}
    </Badge>

    {/* Priority Indicators (NO CAP - show all) */}
    {item.priority_indicators && item.priority_indicators.length > 0 && (
      <div className="flex gap-0.5 ml-1">
        {item.priority_indicators.map((indicator, idx) => (
          <span
            key={`${item.id}-${indicator.label}-${idx}`}
            className="text-base cursor-help"
            title={indicator.tooltip}
          >
            {indicator.icon}
          </span>
        ))}
      </div>
    )}
  </div>
</TableCell>
```

---

### Task 1.3: Display Actionable Insights (30 min)

**File**: `frontend/components/watchlist/NewsIntelligenceCard.tsx`
**Location**: After impact_summary display (line 204)

Add between lines 204-205:
```typescript
{article.actionable_insight && (
  <p className="text-xs text-primary font-medium">
    💡 {article.actionable_insight}
  </p>
)}
```

---

### Task 1.4: Sparklines - Automated Backfill Task (2.5 hours)

#### 1.4.1 Create backfill task
**File**: `backend/app/tasks/watchlist_tasks.py`
**Location**: After existing watchlist tasks

Add:
```python
@celery_app.task(name="backfill_watchlist_snapshots", bind=True)
def backfill_watchlist_snapshots_task(self) -> dict[str, Any]:
    """Backfill historical watchlist snapshots for sparklines.

    Strategy:
    - For each watchlist item
    - Check how many days of history exist
    - If <30 days, backfill missing days up to 30
    - Uses existing refresh logic to generate snapshots
    - Scheduled daily to gradually fill bucket
    """
    from app.storage import get_storage
    from app.watchlist.service import refresh_watchlist_scores
    from datetime import datetime, UTC, timedelta

    storage = get_storage()
    results = {
        "backfilled_count": 0,
        "skipped_count": 0,
        "failed": [],
    }

    # Get all watchlist items
    items_df = storage.query("SELECT id, symbol, created_at FROM watchlist_items")

    for row in items_df.iter_rows(named=True):
        item_id = row["id"]
        symbol = row["symbol"]
        created_at = row["created_at"]

        # Check existing snapshot history
        snapshots_df = storage.query(
            """
            SELECT COUNT(*) as count, MIN(fetched_at) as oldest
            FROM watchlist_snapshots
            WHERE item_id = %s
            """,
            [item_id],
        )

        count = snapshots_df.row(0, named=True)["count"]
        oldest = snapshots_df.row(0, named=True)["oldest"]

        # Determine how many days of history we have
        if count > 0 and oldest:
            days_available = (datetime.now(UTC) - oldest).days
        else:
            days_available = 0

        # Skip if already have 30+ days or item <7 days old
        days_since_creation = (datetime.now(UTC) - created_at).days
        if days_available >= 30 or days_since_creation < 7:
            results["skipped_count"] += 1
            continue

        # Backfill up to 30 days (or item creation date, whichever is more recent)
        target_days = min(30, days_since_creation)
        missing_days = target_days - days_available

        if missing_days <= 0:
            results["skipped_count"] += 1
            continue

        # Generate snapshots for missing days (work backwards from today)
        for day_offset in range(1, missing_days + 1):
            backfill_date = datetime.now(UTC) - timedelta(days=day_offset)

            try:
                # Reuse refresh logic but with historical date
                # Note: This will use current price/technical data
                # For true historical backfill, would need historical OHLCV data
                refresh_watchlist_scores(symbol, as_of_date=backfill_date)
                results["backfilled_count"] += 1
            except Exception as e:
                results["failed"].append({
                    "symbol": symbol,
                    "date": backfill_date.isoformat(),
                    "error": str(e),
                })

    return results
```

#### 1.4.2 Add to beat schedule
**File**: `backend/app/celery_app.py`
**Location**: After "update-technical-indicators-daily" task (around line 164)

Add:
```python
"backfill-watchlist-history-daily": {
    "task": "backfill_watchlist_snapshots",
    "schedule": 86400.0,  # Daily (24 hours)
    "options": {"expires": 7200},  # 2 hour expiry
    # Notes:
    # - Runs daily at ~03:00 UTC
    # - Gradually fills snapshot history up to 30 days
    # - Stops backfilling once 30 days achieved
    # - Runs automatically (no manual intervention needed)
},
```

#### 1.4.3 Re-enable sparklines in UI
**File**: `frontend/components/watchlist/WatchlistTable.tsx`
**Location**: Line 14

Change:
```typescript
// OLD (commented):
// import { SparklineWithHistory } from "@/components/watchlist/SparklineWithHistory";

// NEW (uncommented):
import { SparklineWithHistory } from "@/components/watchlist/SparklineWithHistory";
```

**Location**: Around line 480 (in table rendering)

Uncomment the sparkline usage (should already exist but be commented out).

---

## Sprint 2: Foundation (Days 2-3, ~12 hours)

### Task 2.1: 4-Pillar Fundamental Scoring (3 hours)

#### 2.1.1 Extend fundamentals module with scoring functions
**File**: `backend/app/watchlist/fundamentals.py`
**Location**: After `classify_company_health()` function (after line 297)

Add:
```python
def calculate_valuation_score(data: FundamentalData) -> float:
    """Calculate valuation score (0-100) based on P/E, P/B, PEG ratios.

    Weight: 30% of fundamental score

    Scoring:
    - P/E ratio: <15 = 100, 15-25 = 75, 25-40 = 50, >40 = 25
    - P/B ratio: <2 = 100, 2-4 = 75, 4-6 = 50, >6 = 25
    - PEG ratio: <1 = 100, 1-2 = 75, 2-3 = 50, >3 = 25
    - Average the 3 component scores

    Returns:
        Score 0-100 (higher = better value)
    """
    # Note: P/E, P/B, PEG not in FundamentalData model yet
    # For now, use profit_margin and target_mean_price as proxies
    # TODO: Add P/E, P/B, PEG to FundamentalData model and data sources

    # Proxy scoring using available data
    profit_margin = data.profit_margin or 0.06

    # Simple scoring: High profit margin = good valuation
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
    - Earnings growth (from profit margin trend) similar
    - Average the 2 scores

    Returns:
        Score 0-100 (higher = faster growth)
    """
    revenue_growth = data.revenue_growth or 0.06

    # Revenue growth scoring
    if revenue_growth > 0.30:
        rev_score = 100.0
    elif revenue_growth > 0.20:
        rev_score = 80.0
    elif revenue_growth > 0.10:
        rev_score = 60.0
    elif revenue_growth > 0.05:
        rev_score = 40.0
    else:
        rev_score = 20.0

    # No earnings growth data yet, use revenue as proxy
    return rev_score

def calculate_health_score(data: FundamentalData) -> float:
    """Calculate financial health score (0-100) based on debt and profitability.

    Weight: 25% of fundamental score

    Scoring:
    - Debt/Equity: <0.3 = 100, 0.3-0.7 = 80, 0.7-1.5 = 60, 1.5-2.5 = 40, >2.5 = 20
    - Profit margin: >20% = 100, 10-20% = 80, 5-10% = 60, 0-5% = 40, <0% = 0
    - Average the 2 scores

    Returns:
        Score 0-100 (higher = healthier)
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
    - 1.0-1.5 (strong buy) = 100
    - 1.5-2.0 (buy) = 80
    - 2.0-2.5 (overweight) = 60
    - 2.5-3.5 (hold) = 40
    - 3.5-4.5 (underweight) = 20
    - >4.5 (sell) = 0

    Returns:
        Score 0-100 (higher = more bullish)
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
    - Valuation: 30% (P/E, P/B, PEG)
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

    # Weighted average
    overall = (
        valuation * 0.30 +
        growth * 0.35 +
        health * 0.25 +
        sentiment * 0.10
    )

    return overall
```

#### 2.1.2 Update FundamentalData model to include sub-scores
**File**: `backend/app/watchlist/fundamentals.py`
**Location**: In `FundamentalData` model (around line 37-46)

Add fields:
```python
# 4-pillar scores (calculated)
fundamental_score: float | None = None  # Overall 0-100
valuation_score: float | None = None  # 0-100
growth_score: float | None = None  # 0-100
health_score: float | None = None  # 0-100
sentiment_score: float | None = None  # 0-100
```

#### 2.1.3 Calculate fundamental scores in refresh processor
**File**: `backend/app/watchlist/refresh_processor.py`
**Location**: Search for where fundamental data is fetched

Add after fetching:
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

### Task 2.2: 3-Pillar Score Formula & Models (2 hours)

#### 2.2.1 Update ScoreWeights model
**File**: `backend/app/watchlist/models.py`
**Location**: Replace ScoreWeights class (lines 66-81)

```python
class ScoreWeights(BaseModel):
    """Weights used to compute overall watchlist score (3-pillar system)."""

    price: float = 33.0
    technical: float = 33.0
    fundamental: float = 34.0

    @property
    def total(self) -> float:
        return self.price + self.technical + self.fundamental

    def normalized(self) -> dict[str, float]:
        total = self.total
        if total <= 0:
            return {"price": 0.33, "technical": 0.33, "fundamental": 0.34}
        return {
            "price": self.price / total,
            "technical": self.technical / total,
            "fundamental": self.fundamental / total,
        }
```

#### 2.2.2 Update ScoreComponent to include sub-metric weights
**File**: `backend/app/watchlist/models.py`
**Location**: In ScoreComponent (around line 83-91)

Add field:
```python
sub_scores: dict[str, float] = Field(default_factory=dict)  # Sub-metric breakdown
```

#### 2.2.3 Update ScoreBreakdown model
**File**: `backend/app/watchlist/models.py`
**Location**: Replace ScoreBreakdown class (lines 98-117)

```python
class ScoreBreakdown(BaseModel):
    """Score breakdown for a watchlist item (3-pillar system)."""

    price: ScoreComponent
    technical: ScoreComponent
    fundamental: ScoreComponent | None = None  # May be None if not fetched
    overall: float

    @classmethod
    @field_validator("overall", mode="before")
    def clamp_overall(cls, value: float) -> float:
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

#### 2.2.4 Update scoring formula
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
        "rsi_14": technical_component.metadata.get("rsi_14"),
        "trend": technical_component.metadata.get("trend_score"),
        "macd": technical_component.metadata.get("macd"),
    }

    # Fundamental component (if available)
    fundamental_component = None
    if hasattr(inputs, "fundamental") and inputs.fundamental:
        fundamental_component = _compute_fundamental_component(
            inputs.fundamental,
            weight=weights["fundamental"],
            now=now,
        )

    # Calculate overall score (2-pillar if no fundamental, 3-pillar if fundamental)
    if fundamental_component:
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

#### 2.2.5 Add fundamental component calculation
**File**: `backend/app/watchlist/scoring.py`
**Location**: After `_compute_technical_component()` function (after line 156)

Add:
```python
def _compute_fundamental_component(
    fundamental_data: Any,  # FundamentalData with scores
    weight: float,
    now: datetime,
) -> ScoreComponent:
    """Compute fundamental score component from FundamentalData.

    Args:
        fundamental_data: FundamentalData object with calculated scores
        weight: Weight for this component
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
        )

    score = fundamental_data.fundamental_score or 0.0

    # Sub-scores breakdown
    sub_scores = {
        "valuation": fundamental_data.valuation_score,
        "growth": fundamental_data.growth_score,
        "health": fundamental_data.health_score,
        "sentiment": fundamental_data.sentiment_score,
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
    )
    component.sub_scores = sub_scores

    return component
```

---

### Task 2.3: Volume, Timeframe, Percentile Calculations (3 hours)

#### 2.3.1 Create timeframe analysis module
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

#### 2.3.2 Create percentile calculation module
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

#### 2.3.3 Integrate into refresh processor
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

# Calculate volume relative (need to fetch 50-day avg volume from OHLCV)
# TODO: Add avg_volume_50d to day_bars query
volume_relative = calculate_volume_relative(
    current_volume=current_volume,  # Get from latest OHLCV
    avg_volume_50d=avg_volume_50d,  # Calculate from day_bars
)

# Calculate percentile rank (need last 30 days of snapshots)
historical_scores = conn.execute(
    """
    SELECT overall_score
    FROM watchlist_snapshots
    WHERE item_id = %s
      AND fetched_at >= NOW() - INTERVAL '30 days'
    ORDER BY fetched_at DESC
    """,
    [item_id],
).fetchall()
historical_score_list = [row[0] for row in historical_scores if row[0] is not None]

percentile_rank = calculate_percentile_rank(
    current_score=score_breakdown.overall,
    historical_scores=historical_score_list,
)

# Add to snapshot
snapshot.timeframe_short_aligned = short_aligned
snapshot.timeframe_long_aligned = long_aligned
snapshot.volume_relative = volume_relative
snapshot.percentile_rank_30d = percentile_rank
```

---

### Task 2.4: Fix AVOID Signal Bugs (2 hours)

**File**: `backend/app/watchlist/signal_classifier.py`
**Location**: In `classify_signal()` function

Verify that `sma_5_prev` and `news_sentiment` are passed as parameters and used in logic.

If missing, add:
```python
def classify_signal(
    price_score: float,
    technical_score: float,
    fundamental_score: float | None,
    sma_5: float | None,
    sma_5_prev: float | None,  # ADD THIS
    news_sentiment: float | None,  # ADD THIS
    volume_relative: float | None,
    ...
) -> SignalClassification:
    # ... existing logic ...

    # AVOID detection
    avoid_flags = 0

    # Flag 1: Declining 5-day trend
    if sma_5 and sma_5_prev and sma_5 < sma_5_prev:
        avoid_flags += 1

    # Flag 2: Negative news
    if news_sentiment and news_sentiment < -0.3:
        avoid_flags += 1

    # Flag 3: Low scores
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
            reasons=[...list reasons...],
        )
```

Update caller to pass these values.

---

### Task 2.5: Settings Page - Weight Sliders for ALL Sub-Metrics (2 hours)

#### 2.5.1 Update user preferences schema
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

Run migration:
```bash
psql -U portfolio_ai_user -d portfolio_ai -f backend/migrations/019_score_weight_sliders.sql
```

#### 2.5.2 Update WatchlistPreferences component
**File**: `frontend/components/settings/WatchlistPreferences.tsx`
**Location**: Replace score weights section (lines 525-586)

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
      className="h-8"
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
      className="w-full"
    />

    {/* Price Sub-Weights */}
    <div className="ml-4 space-y-2 text-xs text-text-muted">
      <p>Sub-metrics (informational):</p>
      <div className="grid grid-cols-2 gap-2">
        <div>• Change %: {priceChangeWeight.toFixed(1)}%</div>
        <div>• Beta: {priceBetaWeight.toFixed(1)}%</div>
        <div>• Volatility: {priceVolWeight.toFixed(1)}%</div>
      </div>
    </div>
  </div>

  {/* Technical Weight */}
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
      className="w-full"
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
          className="h-2"
        />
      </div>

      <div className="space-y-2">
        <Label className="text-xs">Trend (SMA): {trendWeight.toFixed(1)}%</Label>
        <Slider
          min={0}
          max={100}
          step={0.1}
          value={[trendWeight]}
          onValueChange={(value) => setTrendWeight(value[0])}
          className="h-2"
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
          className="h-2"
        />
      </div>

      <p className={`text-xs ${Math.abs(rsiWeight + trendWeight + macdWeight - 100) < 0.1 ? 'text-text-muted' : 'text-loss'}`}>
        Total: {(rsiWeight + trendWeight + macdWeight).toFixed(1)}% (must be 100%)
      </p>
    </div>
  </div>

  {/* Fundamental Weight */}
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
      className="w-full"
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
          className="h-2"
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
          className="h-2"
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
          className="h-2"
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
          className="h-2"
        />
      </div>

      <p className={`text-xs ${Math.abs(valuationWeight + growthWeight + healthWeight + sentimentWeight - 100) < 0.1 ? 'text-text-muted' : 'text-loss'}`}>
        Total: {(valuationWeight + growthWeight + healthWeight + sentimentWeight).toFixed(1)}% (must be 100%)
      </p>
    </div>
  </div>

  {/* Top-Level Weight Validation */}
  <div className="flex items-center justify-between pt-2 border-t border-border">
    <p className={`text-sm ${Math.abs(priceWeight + technicalWeight + fundamentalWeight - 100) < 0.1 ? 'text-text-muted' : 'text-loss'}`}>
      Overall Total: {(priceWeight + technicalWeight + fundamentalWeight).toFixed(1)}%{" "}
      {Math.abs(priceWeight + technicalWeight + fundamentalWeight - 100) >= 0.1 && "(must be 100%)"}
    </p>
  </div>
</div>
```

Add state variables at top of component:
```typescript
// Top-level weights
const [priceWeight, setPriceWeight] = useState(33);
const [technicalWeight, setTechnicalWeight] = useState(33);
const [fundamentalWeight, setFundamentalWeight] = useState(34);

// Price sub-weights (informational only for now)
const [priceChangeWeight] = useState(100);
const [priceBetaWeight] = useState(0);
const [priceVolWeight] = useState(0);

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

---

### Task 2.6: Score Breakdown Display in UI (1 hour)

**File**: `frontend/components/watchlist/ExpandedRow.tsx`
**Location**: In "Trading Intelligence" section (search for existing score display)

Add new section:
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
        {/* Sub-scores */}
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

## Sprint 3: Polish (Day 4, ~6 hours)

### Task 3.1: Improve Plain Language Coverage (2 hours)

**Goal**: Increase coverage from 32% to 90%+

**Investigation**:
1. Check Celery logs: `tail -f /var/log/portfolio-ai/celery-worker.log | grep plain_language`
2. Check LLM task queue length: `redis-cli LLEN celery`
3. Check failed tasks: `SELECT COUNT(*) FROM news_cache WHERE plain_language_headline IS NULL`

**Fixes** (depends on findings):
- If LLM failing: Check API keys, rate limits, timeout settings
- If tasks not running: Increase Celery workers or reduce batch size
- Add fallback: If LLM fails, use original headline (better than NULL)

---

### Task 3.2: Search and Advanced Filtering (3 hours)

**File**: `frontend/app/watchlist/page.tsx`
**Location**: In header section (before WatchlistTable)

Add:
```typescript
{/* Search and Filters */}
<div className="flex gap-2 items-center">
  {/* Search Box */}
  <div className="relative flex-1 max-w-md">
    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
    <Input
      placeholder="Search by symbol or company..."
      value={searchQuery}
      onChange={(e) => setSearchQuery(e.target.value)}
      className="pl-10"
    />
  </div>

  {/* Signal Filter */}
  <Select value={signalFilter} onValueChange={setSignalFilter}>
    <SelectTrigger className="w-[140px]">
      <SelectValue placeholder="All Signals" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">All Signals</SelectItem>
      <SelectItem value="BUY">BUY</SelectItem>
      <SelectItem value="HOLD">HOLD</SelectItem>
      <SelectItem value="AVOID">AVOID</SelectItem>
    </SelectContent>
  </Select>

  {/* News Sentiment Filter */}
  <Select value={sentimentFilter} onValueChange={setSentimentFilter}>
    <SelectTrigger className="w-[140px]">
      <SelectValue placeholder="All Sentiment" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">All Sentiment</SelectItem>
      <SelectItem value="bullish">Bullish</SelectItem>
      <SelectItem value="neutral">Neutral</SelectItem>
      <SelectItem value="bearish">Bearish</SelectItem>
    </SelectContent>
  </Select>

  {/* Score Range Filter */}
  <Popover>
    <PopoverTrigger asChild>
      <Button variant="outline" size="sm">
        <SlidersHorizontal className="mr-2 h-4 w-4" />
        Score Filter
      </Button>
    </PopoverTrigger>
    <PopoverContent className="w-80">
      <div className="space-y-4">
        <div>
          <Label>Overall Score: {scoreRange[0]} - {scoreRange[1]}</Label>
          <Slider
            min={0}
            max={100}
            step={1}
            value={scoreRange}
            onValueChange={setScoreRange}
            className="mt-2"
          />
        </div>
      </div>
    </PopoverContent>
  </Popover>

  {/* Active Filters Badge */}
  {activeFilterCount > 0 && (
    <Badge variant="secondary">{activeFilterCount} active</Badge>
  )}
</div>
```

Add filtering logic:
```typescript
const filteredItems = useMemo(() => {
  let results = watchlistData?.items || [];

  // Search filter
  if (searchQuery) {
    const query = searchQuery.toLowerCase();
    results = results.filter(item =>
      item.symbol.toLowerCase().includes(query)
    );
  }

  // Signal filter
  if (signalFilter !== "all") {
    results = results.filter(item => item.signal_type === signalFilter);
  }

  // Sentiment filter
  if (sentimentFilter !== "all") {
    results = results.filter(item => {
      const sentiment = item.news_intelligence?.sentiment_label?.toLowerCase();
      return sentiment === sentimentFilter;
    });
  }

  // Score range filter
  results = results.filter(item => {
    const score = item.current_score?.overall || 0;
    return score >= scoreRange[0] && score <= scoreRange[1];
  });

  // Style filter (existing)
  if (styleFilter !== "all") {
    results = results.filter(item => item.recommended_style === styleFilter);
  }

  return results;
}, [watchlistData, searchQuery, signalFilter, sentimentFilter, scoreRange, styleFilter]);

const activeFilterCount = [
  searchQuery !== "",
  signalFilter !== "all",
  sentimentFilter !== "all",
  scoreRange[0] > 0 || scoreRange[1] < 100,
  styleFilter !== "all",
].filter(Boolean).length;
```

---

### Task 3.3: Documentation (1 hour)

Update documentation to reflect all changes:
- `docs/core/API_REFERENCE.md` - Document priority_indicators field
- `docs/core/DEVELOPMENT.md` - Update score calculation section
- `frontend/components/settings/README.md` (create if not exists) - Document all sliders
- Comment code with clear explanations

---

## Testing & Validation

### Pre-Deployment Checklist

**Static Analysis**:
```bash
# Backend
cd ~/portfolio-ai/backend
ruff check backend/
ruff format backend/
mypy backend/app/

# Frontend
cd ~/portfolio-ai/frontend
npx eslint frontend/
npm run type-check
```

**Unit Tests**:
```bash
cd ~/portfolio-ai/backend && source .venv/bin/activate
pytest tests/unit/watchlist/ -v
pytest tests/integration/watchlist/ -v
```

**Manual Testing**:
1. Restart services: `bash ~/portfolio-ai/scripts/restart.sh`
2. Verify services started: `bash ~/portfolio-ai/scripts/status.sh`
3. Test watchlist page: http://192.168.8.233:3000/watchlist
4. Test settings page: http://192.168.8.233:3000/settings
5. Verify priority indicators appear
6. Verify actionable insights display
7. Verify sparklines appear (after backfill runs)
8. Verify score breakdown shows 3 pillars
9. Verify weight sliders save correctly

---

## Git Workflow

**Branch**: Create feature branch for each sprint
```bash
git checkout -b feature/watchlist-sprint-1-quick-wins
# Make changes
git add -A
git commit -m "feat: Sprint 1 - priority indicators, actionable insights, sparklines"
git push -u origin feature/watchlist-sprint-1-quick-wins
```

**After all sprints complete**:
```bash
git checkout main
git merge feature/watchlist-sprint-1-quick-wins
git merge feature/watchlist-sprint-2-foundation
git merge feature/watchlist-sprint-3-polish
git push origin main
```

---

## Files Created (Summary)

**New Backend Files** (7):
1. `backend/app/watchlist/priority.py` (~200 lines)
2. `backend/app/watchlist/timeframe.py` (~60 lines)
3. `backend/app/watchlist/percentiles.py` (~30 lines)
4. `backend/migrations/019_score_weight_sliders.sql` (~20 lines)
5. `backend/tasks/watchlist_tasks.py` - add backfill task (~80 lines)

**Modified Backend Files** (8):
1. `backend/app/watchlist/models.py` - Updated ScoreWeights, ScoreBreakdown
2. `backend/app/watchlist/scoring.py` - 3-pillar formula, fundamental component
3. `backend/app/watchlist/fundamentals.py` - 4-pillar scoring functions
4. `backend/app/watchlist/response_builders.py` - priority_indicators field
5. `backend/app/watchlist/watchlist_service.py` - calculate priority indicators
6. `backend/app/watchlist/refresh_processor.py` - volume/timeframe/percentile calculations
7. `backend/app/watchlist/signal_classifier.py` - AVOID bug fixes
8. `backend/app/celery_app.py` - backfill task schedule

**Modified Frontend Files** (5):
1. `frontend/lib/api/watchlist.ts` - PriorityIndicator type
2. `frontend/components/watchlist/WatchlistTable.tsx` - priority indicators display, re-enable sparklines
3. `frontend/components/watchlist/NewsIntelligenceCard.tsx` - actionable_insight display
4. `frontend/components/watchlist/ExpandedRow.tsx` - 3-pillar score breakdown
5. `frontend/components/settings/WatchlistPreferences.tsx` - all sub-metric sliders

---

## Estimated Timeline

**Sprint 1** (Day 1): 6 hours
**Sprint 2** (Days 2-3): 12 hours
**Sprint 3** (Day 4): 6 hours
**Total**: ~24 hours (3-4 days of focused work)

---

**END OF TASK LIST**
