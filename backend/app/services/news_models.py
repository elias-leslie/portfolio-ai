"""News service data models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SentimentScore(BaseModel):
    """Normalized sentiment score for a headline."""

    score: float = Field(
        ..., description="Normalized score between -1.0 (negative) and +1.0 (positive)"
    )
    label: Literal["positive", "neutral", "negative"]
    confidence: float = Field(..., description="Model confidence between 0.0 and 1.0")
    model: str = Field(..., description="Sentiment model identifier (e.g., finbert, vader)")
    probabilities: dict[str, float] = Field(default_factory=dict)


class NewsArticle(BaseModel):
    """Processed and scored news article."""

    symbol: str
    headline: str
    url: str | None = None
    summary: str | None = None
    source: str | None = None
    author: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime
    sentiment: SentimentScore
    content_hash: str
    raw: dict[str, Any] = Field(default_factory=dict)
    vendor: str | None = None
    # SEC filing metadata
    filing_type: str | None = None
    is_material_event: bool = False
    plain_language_headline: str | None = None
    # Story clustering metadata
    story_id: str | None = None
    is_primary_article: bool = False
    coverage_count: int = 1
    # Plain language insights
    impact_summary: str | None = None
    actionable_insight: str | None = None
    # ML quality prediction
    quality_prediction: bool | None = None
    quality_confidence: float | None = None


class NewsSummary(BaseModel):
    """Aggregated sentiment summary for a set of articles."""

    symbol: str
    score: float | None
    score_change: float | None
    positive_count: int
    neutral_count: int
    negative_count: int
    article_count: int
    latest_published_at: datetime | None
    top_positive: NewsArticle | None = None
    top_negative: NewsArticle | None = None
    model_breakdown: dict[str, int] = Field(default_factory=dict)


class NewsBundle(BaseModel):
    """Bundle of articles with aggregated summary."""

    symbol: str
    summary: NewsSummary
    articles: list[NewsArticle]
