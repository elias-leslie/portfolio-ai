"""News API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services import NewsService
from app.storage import get_storage
from app.storage.credential_loader import load_credentials_from_database
from app.watchlist.watchlist_service import WatchlistService

router = APIRouter(prefix="/api/news", tags=["news"])

storage = get_storage()
load_credentials_from_database()
news_service = NewsService(storage)
news_service.refresh_ttl_from_preferences()
news_service.refresh_max_articles_from_preferences()
watchlist_service = WatchlistService(storage)


class SentimentScoreResponse(BaseModel):
    """Serialized sentiment score metadata."""

    score: float
    label: str
    confidence: float
    model: str
    probabilities: dict[str, float] | None = Field(default=None)


class NewsArticleResponse(BaseModel):
    """Serialized news article."""

    ticker: str
    headline: str
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
    plain_language_headline: str | None = None
    impact_summary: str | None = None
    actionable_insight: str | None = None


class NewsSummaryResponse(BaseModel):
    """Aggregated sentiment summary."""

    ticker: str
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

    ticker: str
    summary: NewsSummaryResponse
    articles: list[NewsArticleResponse]


class WatchlistNewsResponse(BaseModel):
    """Watchlist-level news response."""

    account_id: str
    items: list[NewsBundleResponse]


class VendorHealthResponse(BaseModel):
    """Vendor-specific health metadata for news ingestion."""

    configured: bool
    enabled: bool
    active: bool
    last_attempt_at: str | None = None
    last_success_at: str | None = None
    last_error_at: str | None = None
    last_error: str | None = None
    articles_last_fetch: int = 0
    articles_last_24h: int = 0
    last_article_at: str | None = None
    notes: str | None = None
    reason: str | None = None


class NewsHealthResponse(BaseModel):
    """Health metrics for news ingestion and sentiment pipeline."""

    finbert_available: bool
    market_last_refreshed_at: str | None = None
    watchlist_last_refreshed_at: str | None = None
    fallback_headlines_24h: int
    headlines_24h: int
    cache_ttl_hours: float
    lookback_window_hours: int
    fallback_rate_24h: float
    fallback_avg_latency_ms_24h: float | None = None
    fallback_p95_latency_ms_24h: float | None = None
    fallback_last_event_at: str | None = None
    vendors: dict[str, VendorHealthResponse] = Field(default_factory=dict)


def _serialize_sentiment(payload: Any) -> SentimentScoreResponse:
    return SentimentScoreResponse(
        score=payload.score,
        label=payload.label,
        confidence=payload.confidence,
        model=payload.model,
        probabilities=payload.probabilities or None,
    )


def _serialize_article(article: Any) -> NewsArticleResponse:
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

    return NewsArticleResponse(
        ticker=article.ticker,
        headline=article.headline,
        url=article.url,
        summary=article.summary,
        source=article.source,
        author=article.author,
        image_url=article.image_url,
        published_at=published_at,
        fetched_at=fetched_at or "",
        sentiment=_serialize_sentiment(article.sentiment),
        vendor=getattr(article, "vendor", None),
        # AI-generated insights
        impact_summary=getattr(article, "impact_summary", None),
        actionable_insight=getattr(article, "actionable_insight", None),
        plain_language_headline=getattr(article, "plain_language_headline", None),
    )


def _serialize_summary(summary: Any) -> NewsSummaryResponse:
    latest_published_at = (
        summary.latest_published_at.isoformat().replace("+00:00", "Z")
        if getattr(summary, "latest_published_at", None)
        else None
    )
    return NewsSummaryResponse(
        ticker=summary.ticker,
        score=summary.score,
        score_change=summary.score_change,
        positive_count=summary.positive_count,
        neutral_count=summary.neutral_count,
        negative_count=summary.negative_count,
        article_count=summary.article_count,
        latest_published_at=latest_published_at,
        top_positive=_serialize_article(summary.top_positive)
        if getattr(summary, "top_positive", None)
        else None,
        top_negative=_serialize_article(summary.top_negative)
        if getattr(summary, "top_negative", None)
        else None,
        model_breakdown=summary.model_breakdown or {},
    )


def _serialize_bundle(bundle: Any, *, limit: int) -> NewsBundleResponse:
    articles = [_serialize_article(article) for article in bundle.articles[:limit]]
    return NewsBundleResponse(
        ticker=bundle.ticker,
        summary=_serialize_summary(bundle.summary),
        articles=articles,
    )


@router.get("", response_model=NewsBundleResponse)
async def get_news_intelligence(
    ticker: str | None = Query(
        None,
        description="Optional ticker symbol. If omitted, returns market-wide news. If provided, returns ticker-specific news.",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Maximum number of articles to return",
    ),
    force_refresh: bool = Query(
        False,
        description="Force refresh of cached headlines before returning results",
    ),
) -> NewsBundleResponse:
    """Get unified news intelligence for market or specific ticker.

    This endpoint consolidates market-level and ticker-specific news into a single API.
    Use the optional ticker parameter to switch between modes:
    - No ticker parameter: Returns broad market news
    - ticker=AAPL: Returns Apple-specific news

    The response includes sentiment summary and scored articles with AI insights.
    """
    news_service.refresh_ttl_from_preferences()
    pref_limit = news_service.refresh_max_articles_from_preferences()
    final_limit = min(limit, pref_limit) if limit else pref_limit

    bundle = news_service.get_news_intelligence(
        ticker=ticker,
        max_articles=final_limit,
        force_refresh=force_refresh,
    )
    return _serialize_bundle(bundle, limit=final_limit)


@router.get("/watchlist", response_model=WatchlistNewsResponse)
async def get_watchlist_news(
    account_id: str = Query(
        "default",
        description="DEPRECATED: Account ID (watchlist is now user-level, not account-specific)",
    ),
    max_results: int | None = Query(
        None, ge=1, le=20, description="Maximum number of articles per symbol"
    ),
    force_refresh: bool = Query(False),
) -> WatchlistNewsResponse:
    """Get news bundles for all symbols in a watchlist.

    Note: Watchlist is now user-level (not account-specific). The account_id parameter
    is kept for backward compatibility but is ignored.
    """
    items = watchlist_service.get_items_with_scores()
    if not items:
        return WatchlistNewsResponse(account_id=account_id, items=[])

    news_service.refresh_ttl_from_preferences()
    pref_limit = news_service.refresh_max_articles_from_preferences()
    limit = max_results or pref_limit
    symbols = [item["symbol"] for item in items]
    bundles = news_service.get_watchlist_news(
        symbols,
        max_articles=limit,
        force_refresh=force_refresh,
    )

    serialized_items: list[NewsBundleResponse] = []
    for symbol in symbols:
        bundle = bundles.get(symbol.upper())
        if not bundle:
            continue
        serialized_items.append(_serialize_bundle(bundle, limit=limit))

    return WatchlistNewsResponse(account_id=account_id, items=serialized_items)


@router.get("/health", response_model=NewsHealthResponse)
async def get_news_health() -> NewsHealthResponse:
    """Return health information for the news ingestion pipeline."""
    news_service.refresh_ttl_from_preferences()
    news_service.refresh_max_articles_from_preferences()
    metrics = news_service.get_health()
    return NewsHealthResponse(**metrics)


@router.get("/search", response_model=NewsBundleResponse)
async def search_news(
    query: str = Query(..., description="Free-form news query"),
    max_results: int | None = Query(None, ge=1, le=50),
) -> NewsBundleResponse:
    """Search news without caching results."""
    news_service.refresh_ttl_from_preferences()
    pref_limit = news_service.refresh_max_articles_from_preferences()
    limit = max_results or pref_limit
    bundle = news_service.get_custom_news(query, max_articles=limit)
    return _serialize_bundle(bundle, limit=limit)
