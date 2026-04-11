"""Pydantic response models and serializers for the news API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.news_decision_support import assess_news_article


class SentimentScoreResponse(BaseModel):
    """Serialized sentiment score metadata."""

    score: float
    label: str
    confidence: float
    model: str
    probabilities: dict[str, float] | None = Field(default=None)


class NewsArticleResponse(BaseModel):
    """Serialized news article."""

    symbol: str
    headline: str
    article_hash: str | None = None
    url: str | None = None
    summary: str | None = None
    source: str | None = None
    author: str | None = None
    image_url: str | None = None
    published_at: str | None = None
    fetched_at: str
    sentiment: SentimentScoreResponse
    vendor: str | None = None
    # SEC filing metadata
    filing_type: str | None = None
    is_material_event: bool = False
    # AI-generated insights
    impact_summary: str | None = None
    actionable_insight: str | None = None
    # ML quality prediction
    quality_prediction: bool | None = None
    quality_confidence: float | None = None
    # Story clustering metadata
    story_id: str | None = None
    is_primary_article: bool = False
    coverage_count: int = 1
    event_category: str | None = None
    market_context_topic: str | None = None
    source_signal_tier: str | None = None
    canonical_headline: str | None = None
    decision_value_score: float | None = None
    decision_value_label: str | None = None
    decision_value_reason: str | None = None


class NewsSummaryResponse(BaseModel):
    """Aggregated sentiment summary."""

    symbol: str
    score: float | None
    score_change: float | None
    positive_count: int
    neutral_count: int
    negative_count: int
    article_count: int
    latest_published_at: str | None
    top_positive: NewsArticleResponse | None = None
    top_negative: NewsArticleResponse | None = None
    model_breakdown: dict[str, int]


class NewsBundleResponse(BaseModel):
    """Bundle of news articles with sentiment summary."""

    symbol: str
    summary: NewsSummaryResponse
    articles: list[NewsArticleResponse]


def serialize_sentiment(payload: object) -> SentimentScoreResponse:
    """Serialize a sentiment domain object to a response model."""
    return SentimentScoreResponse(
        score=payload.score,
        label=payload.label,
        confidence=payload.confidence,
        model=payload.model,
        probabilities=payload.probabilities or None,
    )


def serialize_article(article: object) -> NewsArticleResponse:
    """Serialize a news article domain object to a response model."""
    published_at = (
        article.published_at.isoformat().replace("+00:00", "Z")
        if getattr(article, "published_at", None)
        else None
    )
    fetched_at = (
        article.fetched_at.isoformat().replace("+00:00", "Z")
        if getattr(article, "fetched_at", None)
        else ""
    )

    assessment = assess_news_article(article)

    return NewsArticleResponse(
        symbol=article.symbol,
        headline=article.headline,
        article_hash=getattr(article, "content_hash", None),
        url=article.url,
        summary=article.summary,
        source=article.source,
        author=article.author,
        image_url=article.image_url,
        published_at=published_at,
        fetched_at=fetched_at or "",
        sentiment=serialize_sentiment(article.sentiment),
        vendor=getattr(article, "vendor", None),
        impact_summary=getattr(article, "impact_summary", None),
        actionable_insight=getattr(article, "actionable_insight", None),
        quality_prediction=getattr(article, "quality_prediction", None),
        quality_confidence=getattr(article, "quality_confidence", None),
        story_id=getattr(article, "story_id", None),
        is_primary_article=getattr(article, "is_primary_article", False),
        coverage_count=getattr(article, "coverage_count", 1),
        event_category=assessment.event_category,
        market_context_topic=assessment.market_context_topic,
        source_signal_tier=assessment.source_signal_tier,
        canonical_headline=assessment.canonical_headline,
        decision_value_score=assessment.decision_value_score,
        decision_value_label=assessment.decision_value_label,
        decision_value_reason=assessment.decision_value_reason,
    )


def serialize_summary(summary: object) -> NewsSummaryResponse:
    """Serialize a news summary domain object to a response model."""
    latest_published_at = (
        summary.latest_published_at.isoformat().replace("+00:00", "Z")
        if getattr(summary, "latest_published_at", None)
        else None
    )
    return NewsSummaryResponse(
        symbol=summary.symbol,
        score=summary.score,
        score_change=summary.score_change,
        positive_count=summary.positive_count,
        neutral_count=summary.neutral_count,
        negative_count=summary.negative_count,
        article_count=summary.article_count,
        latest_published_at=latest_published_at,
        top_positive=serialize_article(summary.top_positive)
        if getattr(summary, "top_positive", None)
        else None,
        top_negative=serialize_article(summary.top_negative)
        if getattr(summary, "top_negative", None)
        else None,
        model_breakdown=summary.model_breakdown or {},
    )


def serialize_bundle(bundle: object, *, limit: int) -> NewsBundleResponse:
    """Serialize a news bundle domain object to a response model."""
    articles = [serialize_article(article) for article in bundle.articles[:limit]]
    return NewsBundleResponse(
        symbol=bundle.symbol,
        summary=serialize_summary(bundle.summary),
        articles=articles,
    )
