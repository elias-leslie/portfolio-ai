"""Symbol Intelligence response models.

Pydantic models for the symbol intelligence API response.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class PillarScore(BaseModel):
    """Individual pillar score with metadata."""

    score: float | None
    weight: float
    sub_scores: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    stale: bool = False


class ScoresSection(BaseModel):
    """All scoring data for a symbol."""

    overall: float | None
    signal_type: str | None
    signal_strength: int | None
    pillars: dict[str, PillarScore]
    data_quality: dict[str, Any] | None = None


class SignalSection(BaseModel):
    """Signal classification with reasoning."""

    type: str | None
    strength: int | None
    confirmations: int | None = None
    reasons: dict[str, list[str]] | None = None
    avoid_flags: int = 0


class TradingSection(BaseModel):
    """Trading style and position guidance."""

    style: str | None
    confidence: int | None
    holding_period: str | None
    risk_level: str | None
    entry_price: float | None
    stop_loss: float | None
    profit_target: float | None
    position_size_shares: int | None
    position_size_dollars: float | None


class QuoteSection(BaseModel):
    """Canonical current quote for the symbol."""

    price: float | None = None
    source: str | None = None
    cached_at: datetime | None = None
    session: str | None = None
    freshness_status: str
    freshness_label: str
    error: str | None = None


class CompanySection(BaseModel):
    """Company fundamentals and timing."""

    health: str | None = None
    earnings_date: str | None = None
    earnings_days_away: int | None = None


class TrendSection(BaseModel):
    """Trend alignment and volume data."""

    short_term_aligned: bool | None = None
    long_term_aligned: bool | None = None
    volume_relative: float | None = None


class NewsArticle(BaseModel):
    """Recent news article."""

    headline: str
    url: str | None = None
    source: str | None = None
    published_at: str | None = None


class AlertIndicator(BaseModel):
    """Priority alert indicator."""

    icon: str
    label: str
    tooltip: str | None = None
    priority: int = 0
    category: str | None = None


class PositionInfo(BaseModel):
    """Portfolio position details."""

    shares: float
    cost_basis: float
    current_value: float | None = None
    gain: float | None = None
    gain_pct: float | None = None
    weight_pct: float | None = None
    concentration_weight_pct: float | None = None
    concentration_method: str | None = None
    top_exposure_name: str | None = None


class PortfolioContext(BaseModel):
    """Portfolio-level context."""

    total_value: float
    num_holdings: int
    diversification_score: float | None = None
    sector_weight: float | None = None
    concentration_top3: float | None = None


class PortfolioSection(BaseModel):
    """Portfolio position and context."""

    held: bool
    position: PositionInfo | None = None
    context: PortfolioContext | None = None


class StrategyInfo(BaseModel):
    """Strategy summary."""

    id: str
    name: str
    strategy_type: str
    expected_sharpe: float | None = None
    live_sharpe: float | None = None
    win_rate: float | None = None
    current_signal: str | None = None


class StrategiesSection(BaseModel):
    """Active strategies for symbol."""

    active_count: int
    strategies: list[StrategyInfo] = []
    best_strategy: StrategyInfo | None = None


class KeyEvent(BaseModel):
    """Material news event."""

    icon: str
    text: str
    time_ago: str


class NewsSection(BaseModel):
    """News and sentiment data."""

    sentiment_score: float | None = None
    sentiment_label: str | None = None
    article_count_24h: int = 0
    key_events: list[KeyEvent] = []
    headline: str | None = None
    recent_articles: list[NewsArticle] = []


class SectorInfo(BaseModel):
    """Sector performance context."""

    name: str | None = None
    signal: str | None = None
    daily_change: float | None = None
    relative_to_spy: float | None = None


class MarketSection(BaseModel):
    """Broader market context."""

    fear_greed_score: int | None = None
    fear_greed_label: str | None = None
    fear_greed_as_of_date: date | None = None
    health_score: int | None = None
    vix: float | None = None
    vix_as_of_date: date | None = None
    sp500_change: float | None = None
    sp500_as_of_date: date | None = None
    sector: SectorInfo | None = None


class RecommendationSection(BaseModel):
    """Personalized recommendation."""

    action: str
    reasoning: list[str]
    if_not_held: dict[str, Any] | None = None


class DecisionSection(BaseModel):
    """Current decision resolved across Jenny context and live signals."""

    action: str
    headline: str
    summary: str
    reasoning: list[str] = Field(default_factory=list)
    source_kind: str
    source_label: str
    source_timestamp: str | None = None
    severity: str | None = None


class SymbolSectionIssue(BaseModel):
    """One unavailable intelligence section in an otherwise usable response."""

    section: str
    message: str


class SymbolIntelligenceResponse(BaseModel):
    """Complete symbol intelligence response."""

    symbol: str
    generated_at: datetime

    scores: ScoresSection | None = None
    signal: SignalSection | None = None
    trading: TradingSection | None = None
    quote: QuoteSection | None = None
    company: CompanySection | None = None
    trends: TrendSection | None = None
    portfolio: PortfolioSection | None = None
    strategies: StrategiesSection | None = None
    news: NewsSection | None = None
    market: MarketSection | None = None
    alerts: list[AlertIndicator] = []
    recommendation: RecommendationSection | None = None
    decision: DecisionSection | None = None
    section_issues: list[SymbolSectionIssue] = Field(default_factory=list)

    error: str | None = None
