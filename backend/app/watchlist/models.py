"""Pydantic models for watchlist domain objects."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, Field, field_validator

from ..portfolio.models import PriceData

# TypedDict models for structured dictionaries


class ScoreDict(TypedDict, total=False):
    """Score breakdown dictionary structure (overall + pillar scores)."""

    overall: float
    price: float
    technical: float
    fundamental: float


class NewsIntelligenceDict(TypedDict, total=False):
    """News intelligence summary dictionary (used before NewsIntelligence BaseModel)."""

    article_count_24h: int
    key_events: list[dict[str, Any]]  # KeyEvent as dict form
    sentiment_score: float
    sentiment_label: str
    headline: str


class NarrativeBulletsDict(TypedDict):
    """Narrative bullets structure (company health, technical, why bullets)."""

    bullets: list[str]


class RawMetricsDict(TypedDict, total=False):
    """Raw technical metrics dictionary (indicators and calculations)."""

    rsi_14: float
    macd: float
    sma_5: float
    sma_20: float
    sma_50: float
    sma_200: float
    ema_20: float
    price: float
    volume: float
    volume_avg_20: float


class RecentNewsDict(TypedDict, total=False):
    """Recent news headlines dictionary structure."""

    headlines: list[str]
    sentiment_avg: float
    article_count: int


class WatchlistItemDict(TypedDict, total=False):
    """Watchlist item dictionary structure (used in priority/signal processing)."""

    symbol: str
    signal_type: str  # "BUY", "HOLD", "AVOID"
    score: ScoreDict  # Typed score structure
    earnings_days_away: int | None
    news_intelligence: NewsIntelligenceDict  # Typed news intelligence
    news_sentiment_score: float | None


class SignalInputsDict(TypedDict, total=False):
    """Signal classification input dictionary structure (raw, before normalization)."""

    price: float | None
    ema_20: float | None
    sma_5: float | None
    sma_5_prev: float | None
    rsi_14: float | None
    macd: float | None
    volume: float | None
    volume_avg_20: float | None
    volume_avg_20d: float | None  # Alias for volume_avg_20
    company_health: str | None  # "EXCELLENT", "GOOD", "WEAK"
    news_sentiment: float | None
    earnings_days_away: int | None
    # Fundamental component fields (Task 0074)
    profit_margin: float | None  # 0.20 = 20%
    revenue_growth: float | None  # 0.25 = 25%
    debt_to_equity: float | None  # 0.5 = 50%
    # Analyst component fields (Task 0074)
    recommendation_mean: float | None  # 1.0-5.0 (1=strong buy, 5=sell)
    analyst_buy_pct: float | None  # 0.0-1.0 (0.75 = 75% buy)
    # Options flow fields (GAP-031)
    options_call_pct: float | None  # 0.0-1.0 (0.55 = 55% calls, bullish)
    options_near_term_pct: float | None  # 0.0-1.0 (high = speculative)
    symbol_in_active_sector: bool | None  # True if sector has high options activity
    # Earnings surprise fields (GAP-003)
    earnings_surprise_score: int | None  # -1 to +4 points (pre-computed)
    earnings_surprise_reasons: list[str] | None  # Reasons for the score


class NormalizedSignalInputsDict(TypedDict):
    """Normalized signal inputs with non-null defaults (after _extract_signal_inputs)."""

    price: float
    ema_20: float
    sma_5: float
    sma_5_prev: float
    rsi_14: float
    macd: float
    volume: float
    volume_avg_20: float
    company_health: str
    news_sentiment: float
    earnings_days_away: int | None  # Can remain None
    # Fundamental component fields (Task 0074) - can be None if data unavailable
    profit_margin: float | None
    revenue_growth: float | None
    debt_to_equity: float | None
    # Analyst component fields (Task 0074) - can be None if data unavailable
    recommendation_mean: float | None
    analyst_buy_pct: float | None
    # Options flow fields (GAP-031) - can be None if data unavailable
    options_call_pct: float | None
    options_near_term_pct: float | None
    symbol_in_active_sector: bool | None
    # Earnings surprise fields (GAP-003) - can be None if data unavailable
    earnings_surprise_score: int | None
    earnings_surprise_reasons: list[str] | None


class TradingStyleDict(TypedDict):
    """Trading style classification result dictionary."""

    style: str  # "Index", "Trend", "Value", "Swing", "Event"
    confidence: int  # 0-10
    holding_period: str  # "Hold indefinitely", "Days to weeks", etc.
    risk_level: str  # "Low", "Medium-Low", "Medium", "High"


class KeyEvent(BaseModel):
    """Key event for news intelligence display."""

    icon: str  # "📋", "📈", "📰"
    text: str  # Plain language event description
    time_ago: str  # "8 hours ago"
    is_material: bool
    event_category: str | None = None
    published_at: datetime | None = None


class NewsArticleDict(TypedDict, total=False):
    """News article dictionary structure (recent articles in news intelligence)."""

    headline: str
    published_at: str  # ISO datetime string
    source: str
    sentiment: float
    url: str


class NewsIntelligence(BaseModel):
    """News intelligence summary for watchlist items."""

    headline: str  # "Insider confidence + positive earnings surprise"
    sentiment_score: float  # +0.45
    sentiment_label: str  # "Positive"
    article_count_24h: int  # 12
    key_events: list[KeyEvent] = Field(default_factory=list)  # Top 3 events
    recent_articles: list[NewsArticleDict] = Field(default_factory=list)  # Top 5 articles


class SignalType(str, Enum):
    """Signal classification type for watchlist items."""

    BUY = "BUY"
    HOLD = "HOLD"
    AVOID = "AVOID"


class SignalStrength(BaseModel):
    """Signal strength on a 0-10 scale."""

    value: int = Field(ge=0, le=10)

    @field_validator("value")
    @classmethod
    def validate_range(cls, v: int) -> int:
        """Validate that value is between 0 and 10."""
        if not 0 <= v <= 10:
            raise ValueError("Signal strength must be between 0 and 10")
        return v


class SignalClassification(BaseModel):
    """Signal classification with type, strength, and reasoning."""

    signal_type: SignalType
    strength: SignalStrength
    reasons: list[str] = Field(default_factory=list)


class ScoreWeights(BaseModel):
    """Weights used to compute overall watchlist score (4-pillar system)."""

    price: float = 25.0
    technical: float = 25.0
    fundamental: float = 30.0
    catalyst: float = 20.0  # NEW: Fourth pillar (event-driven signals)

    @property
    def total(self) -> float:
        return self.price + self.technical + self.fundamental + self.catalyst

    def normalized(self) -> dict[str, float]:
        """Normalize weights to sum to 1.0."""
        total = self.total
        if total <= 0:
            return {"price": 0.25, "technical": 0.25, "fundamental": 0.30, "catalyst": 0.20}
        return {
            "price": self.price / total,
            "technical": self.technical / total,
            "fundamental": self.fundamental / total,
            "catalyst": self.catalyst / total,
        }


class ScoreComponent(BaseModel):
    """Individual score component."""

    score: float = 0.0
    weight: float = 0.0
    stale: bool = False
    updated_at: datetime | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    sub_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Sub-metric scores (e.g., rsi_14, trend, macd for technical)",
    )

    @classmethod
    @field_validator("score", mode="before")
    def clamp_score(cls, value: float) -> float:
        return max(0.0, min(100.0, float(value)))


class ScoreBreakdown(BaseModel):
    """Score breakdown for a watchlist item (5-pillar system)."""

    price: ScoreComponent
    technical: ScoreComponent
    fundamental: ScoreComponent | None = None  # May be None if not fetched
    catalyst: ScoreComponent | None = None  # Fourth pillar (may be None if no news)
    options_flow: ScoreComponent | None = None  # Fifth pillar (GAP-031, may be None)

    overall: float

    @classmethod
    @field_validator("overall", mode="before")
    def clamp_overall(cls, value: float) -> float:
        """Clamp overall score to 0-100."""
        return max(0.0, min(100.0, float(value)))

    def to_snapshot_payload(self) -> dict[str, Any]:
        """Serialize score metadata for persistence."""
        return {
            "price": self.price.model_dump(mode="json"),
            "technical": self.technical.model_dump(mode="json"),
            "fundamental": self.fundamental.model_dump(mode="json") if self.fundamental else None,
            "catalyst": self.catalyst.model_dump(mode="json") if self.catalyst else None,
            "options_flow": self.options_flow.model_dump(mode="json")
            if self.options_flow
            else None,
            "overall": self.overall,
        }


class TechnicalSnapshot(BaseModel):
    """Technical indicator snapshot used for scoring."""

    rsi_14: float | None = None
    sma_5: float | None = None  # 5-day simple moving average (for AVOID detection)
    sma_20: float | None = None  # 20-day simple moving average
    sma_50: float | None = None
    sma_200: float | None = None
    ema_20: float | None = None  # 20-day exponential moving average
    ema_50: float | None = None
    ema_200: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    bb_upper: float | None = None  # Bollinger Band upper (20, 2.0)
    bb_middle: float | None = None  # Bollinger Band middle (SMA-20)
    bb_lower: float | None = None  # Bollinger Band lower (20, 2.0)
    stoch_k: float | None = None  # Stochastic %K (14, 3, 3)
    stoch_d: float | None = None  # Stochastic %D (signal line)
    price: float | None = None
    calculated_at: datetime | None = None


class WatchlistScoreInputs(BaseModel):
    """Inputs required to compute watchlist scores."""

    price: PriceData
    price_change_pct: float | None = None
    technical: TechnicalSnapshot = Field(default_factory=TechnicalSnapshot)
    fundamental: Any | None = None  # FundamentalData (avoid circular import)
    news_articles: list[dict[str, str | datetime | float | None]] = Field(
        default_factory=list
    )  # For catalyst scoring
    options_data: Any | None = None  # OptionsFlowData (GAP-031, avoid circular import)
    symbol_in_active_sector: bool = (
        False  # GAP-031: True if symbol's sector has high options activity
    )
    weights: ScoreWeights = Field(default_factory=ScoreWeights)
    now: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stale_ttl_minutes: int = 15  # Default to 15 minutes (3x default 5min refresh)


class WatchlistItem(BaseModel):
    """Watchlist item model."""

    id: str
    account_id: str
    symbol: str
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WatchlistSnapshot(BaseModel):
    """Watchlist scoring snapshot for persistence and analytics."""

    item_id: str
    fetched_at: datetime
    price: float | None = None
    change_pct: float | None = None
    beta: float | None = None
    volatility: float | None = None
    news_score: float | None = None
    technical_score: float | None = None
    fundamental_score: float | None = None
    ai_score: float | None = None
    ai_confidence: float | None = None
    sector_score: float | None = None
    competitor_score: float | None = None
    overall_score: float | None = None
    is_stale: bool = False
    raw_metrics: RawMetricsDict | dict[str, Any] = Field(default_factory=dict)

    # Narrative intelligence fields
    signal_type: str | None = None
    signal_strength: int | None = None
    narrative_headline: str | None = None
    narrative_why_bullets: NarrativeBulletsDict | None = None
    narrative_company_health: NarrativeBulletsDict | None = None
    narrative_technical: NarrativeBulletsDict | None = None
    narrative_action_plan: str | None = None
    narrative_position_sizing: str | None = None
    narrative_special_notes: str | None = None

    # Trade calculation fields
    entry_price: float | None = None
    stop_loss: float | None = None
    profit_target: float | None = None
    position_size_shares: int | None = None

    # Trading style fields
    recommended_style: str | None = None
    style_confidence: int | None = None
    optimal_holding_period: str | None = None
    risk_level: str | None = None

    # Fundamental & news data fields
    company_health: str | None = None
    earnings_date: datetime | None = None
    earnings_days_away: int | None = None
    news_sentiment_score: float | None = None
    recent_news_headlines: dict[str, Any] | None = None

    # Volume & timeframe analysis fields (PRD #0022)
    volume_relative: float | None = None  # Current volume / 50-day avg (e.g., 2.3 = 2.3x)
    timeframe_short_aligned: bool = False  # Price > SMA_20 > SMA_50
    timeframe_long_aligned: bool = False  # SMA_50 > SMA_200
    percentile_rank_30d: float | None = None  # 0-100 percentile vs 30-day history

    # News Intelligence (Phase 2)
    news_intelligence: NewsIntelligence | None = None

    def to_upsert_params(self) -> dict[str, Any]:
        """Return dictionary for persistence helpers."""
        payload = self.model_dump()
        payload["raw_metrics"] = self.raw_metrics or None
        # Convert JSONB fields
        payload["narrative_why_bullets"] = self.narrative_why_bullets or None
        payload["narrative_company_health"] = self.narrative_company_health or None
        payload["narrative_technical"] = self.narrative_technical or None
        payload["recent_news_headlines"] = self.recent_news_headlines or None
        # Exclude computed fields (not persisted)
        payload.pop("news_intelligence", None)
        return payload
