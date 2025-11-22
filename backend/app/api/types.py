"""TypedDict definitions for API endpoints across all routers.

Provides type-safe response models and helper function return types
for capabilities, news, indicators, and status endpoints.
"""

from __future__ import annotations

from typing import TypedDict


class CapabilityDict(TypedDict, total=False):
    """Single capability record from database."""

    id: int
    name: str
    category: str
    health_status: str
    capability_type: str
    insights_count: int
    notes_count: int
    # db_capability fields
    days_since_update: int | None
    age_hours: int | None
    source: str | None
    description: str
    freshness_status: str | None
    # celery_capability fields
    populates_tables: list[str]
    depends_on_tasks: list[str]
    # api_capability fields
    depends_on_tables: list[str]


class HealthSummaryDict(TypedDict):
    """System health summary with counts by type and status."""

    total: int
    by_type: dict[str, dict[str, int]]
    by_status: dict[str, int]


class DependenciesDict(TypedDict, total=False):
    """Dependencies extracted from capability records."""

    populates_tables: list[str]
    depends_on_tasks: list[str]
    depends_on_tables: list[str]


class InsightDict(TypedDict, total=False):
    """Capability insight record."""

    id: int
    capability_type: str
    capability_id: int
    status: str
    severity: str
    insight_type: str
    message: str
    generated_at: str
    reviewed_at: str | None
    reviewed_by: str | None
    fixed_at: str | None


class NoteDict(TypedDict, total=False):
    """Capability note record."""

    id: int
    capability_type: str
    capability_id: int | None
    insight_id: int | None
    note_type: str
    note: str
    created_by: str
    created_at: str


class SentimentDict(TypedDict, total=False):
    """Sentiment score with metadata."""

    score: float
    label: str
    confidence: float
    model: str
    probabilities: dict[str, float] | None


class NewsArticleDict(TypedDict, total=False):
    """News article record."""

    ticker: str
    headline: str
    url: str | None
    summary: str | None
    source: str | None
    author: str | None
    image_url: str | None
    published_at: str | None
    fetched_at: str
    sentiment: SentimentDict
    vendor: str | None
    filing_type: str | None
    is_material_event: bool
    plain_language_headline: str | None
    impact_summary: str | None
    actionable_insight: str | None
    quality_prediction: bool | None
    quality_confidence: float | None


class NewsSummaryDict(TypedDict, total=False):
    """Aggregated news sentiment summary."""

    ticker: str
    score: float | None
    score_change: float | None
    positive_count: int
    neutral_count: int
    negative_count: int
    article_count: int
    latest_published_at: str | None
    top_positive: NewsArticleDict | None
    top_negative: NewsArticleDict | None
    model_breakdown: dict[str, int]


class IndicatorValuesDict(TypedDict, total=False):
    """Dictionary of indicator values keyed by indicator name."""

    rsi_14: float
    macd_12_26_9: dict[str, float]
    bbands_20_2: dict[str, float]
    sma_20: float
    sma_50: float
    sma_200: float
    ema_20: float
    ema_50: float
    ema_200: float
    atr_14: float
    stoch_14_3_3: dict[str, float]


class InterpretationValuesDict(TypedDict, total=False):
    """Dictionary of human-readable indicator interpretations."""

    rsi: str
    macd: str
    bbands_position: str
    price_vs_sma_200: str
    stoch: str


class SystemStatusDict(TypedDict):
    """Comprehensive system status snapshot."""

    status: str
    services: dict[str, object]
    timestamp: str
    uptime_seconds: float
    checks: dict[str, object]
    sources: dict[str, object]


class ArticleRowDict(TypedDict, total=False):
    """Row dict from database query for article."""

    ticker: str
    headline: str
    url: str | None
    summary: str | None
    source: str | None
    author: str | None
    image_url: str | None
    published_at: str | None
    fetched_at: str
    sentiment: SentimentDict
    vendor: str | None
    filing_type: str | None
    is_material_event: bool
    plain_language_headline: str | None
    impact_summary: str | None
    actionable_insight: str | None
    quality_prediction: bool | None
    quality_confidence: float | None


class IndicatorRowDict(TypedDict, total=False):
    """Row dict from technical_indicators table."""

    ticker: str
    date: str
    close_price: float | None
    rsi_14: float | None
    macd_12_26_9_macd: float | None
    macd_12_26_9_signal: float | None
    macd_12_26_9_histogram: float | None
    bbands_20_2_upper: float | None
    bbands_20_2_middle: float | None
    bbands_20_2_lower: float | None
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    ema_20: float | None
    ema_50: float | None
    ema_200: float | None
    atr_14: float | None
    stoch_14_3_3_k: float | None
    stoch_14_3_3_d: float | None


class SourceMetricsDict(TypedDict):
    """Source quality metrics record."""

    vendor: str
    duplicate_rate: float
    diversity_score: float
    confidence_avg: float
    freshness_score: float
    user_useful_rate: float | None
    quality_score: float
    article_count: int
    sample_period_start: str
    calculated_at: str


class ResetSourceMetricsDict(TypedDict):
    """Response from reset_source_metrics endpoint."""

    status: str
    task_id: str
    message: str
