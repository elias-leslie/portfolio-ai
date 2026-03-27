"""Pydantic response models and serializers for the news API."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
        score=payload.score,  # type: ignore[attr-defined]
        label=payload.label,  # type: ignore[attr-defined]
        confidence=payload.confidence,  # type: ignore[attr-defined]
        model=payload.model,  # type: ignore[attr-defined]
        probabilities=payload.probabilities or None,  # type: ignore[attr-defined]
    )


def serialize_article(article: object) -> NewsArticleResponse:
    """Serialize a news article domain object to a response model."""
    published_at = (
        article.published_at.isoformat().replace("+00:00", "Z")  # type: ignore[attr-defined]
        if getattr(article, "published_at", None)
        else None
    )
    fetched_at = (
        article.fetched_at.isoformat().replace("+00:00", "Z")  # type: ignore[attr-defined]
        if getattr(article, "fetched_at", None)
        else ""
    )

    return NewsArticleResponse(
        symbol=article.symbol,  # type: ignore[attr-defined]
        headline=article.headline,  # type: ignore[attr-defined]
        article_hash=getattr(article, "content_hash", None),
        url=article.url,  # type: ignore[attr-defined]
        summary=article.summary,  # type: ignore[attr-defined]
        source=article.source,  # type: ignore[attr-defined]
        author=article.author,  # type: ignore[attr-defined]
        image_url=article.image_url,  # type: ignore[attr-defined]
        published_at=published_at,
        fetched_at=fetched_at or "",
        sentiment=serialize_sentiment(article.sentiment),  # type: ignore[attr-defined]
        vendor=getattr(article, "vendor", None),
        impact_summary=getattr(article, "impact_summary", None),
        actionable_insight=getattr(article, "actionable_insight", None),
        quality_prediction=getattr(article, "quality_prediction", None),
        quality_confidence=getattr(article, "quality_confidence", None),
        story_id=getattr(article, "story_id", None),
        is_primary_article=getattr(article, "is_primary_article", False),
        coverage_count=getattr(article, "coverage_count", 1),
    )


def serialize_summary(summary: object) -> NewsSummaryResponse:
    """Serialize a news summary domain object to a response model."""
    latest_published_at = (
        summary.latest_published_at.isoformat().replace("+00:00", "Z")  # type: ignore[attr-defined]
        if getattr(summary, "latest_published_at", None)
        else None
    )
    return NewsSummaryResponse(
        symbol=summary.symbol,  # type: ignore[attr-defined]
        score=summary.score,  # type: ignore[attr-defined]
        score_change=summary.score_change,  # type: ignore[attr-defined]
        positive_count=summary.positive_count,  # type: ignore[attr-defined]
        neutral_count=summary.neutral_count,  # type: ignore[attr-defined]
        negative_count=summary.negative_count,  # type: ignore[attr-defined]
        article_count=summary.article_count,  # type: ignore[attr-defined]
        latest_published_at=latest_published_at,
        top_positive=serialize_article(summary.top_positive)  # type: ignore[attr-defined]
        if getattr(summary, "top_positive", None)
        else None,
        top_negative=serialize_article(summary.top_negative)  # type: ignore[attr-defined]
        if getattr(summary, "top_negative", None)
        else None,
        model_breakdown=summary.model_breakdown or {},  # type: ignore[attr-defined]
    )


def serialize_bundle(bundle: object, *, limit: int) -> NewsBundleResponse:
    """Serialize a news bundle domain object to a response model."""
    articles = [serialize_article(article) for article in bundle.articles[:limit]]  # type: ignore[attr-defined]
    return NewsBundleResponse(
        symbol=bundle.symbol,  # type: ignore[attr-defined]
        summary=serialize_summary(bundle.summary),  # type: ignore[attr-defined]
        articles=articles,
    )
