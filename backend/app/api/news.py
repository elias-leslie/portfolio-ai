"""News API router."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.api.news_responses import (
    NewsBundleResponse,
    serialize_bundle,
)
from app.middleware.cache import cache_response

if TYPE_CHECKING:
    from app.services import NewsService
    from app.watchlist.watchlist_service import WatchlistService

router = APIRouter(prefix="/api/news", tags=["news"])


@lru_cache(maxsize=1)
def _news_service() -> NewsService:
    storage = import_module("app.storage").get_storage()
    import_module("app.services.news_cache_refresh").ensure_credentials_loaded()
    service = import_module("app.services").NewsService(storage, auto_load_credentials=False)
    service.refresh_ttl_from_preferences()
    service.refresh_max_articles_from_preferences()
    return service


# Public alias so tests can ``from app.api.news import news_service``
news_service = _news_service


@lru_cache(maxsize=1)
def _watchlist_service() -> WatchlistService:
    storage = import_module("app.storage").get_storage()
    return import_module("app.watchlist.watchlist_service").WatchlistService(storage)


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

    status: str
    message: str
    finbert_available: bool
    finbert_install_hint: str | None = None
    market_last_refreshed_at: str | None = None
    watchlist_last_refreshed_at: str | None = None
    latest_refreshed_at: str | None = None
    latest_refresh_age_hours: float | None = None
    fallback_headlines_24h: int
    headlines_24h: int
    cache_ttl_hours: float
    lookback_window_hours: int
    fallback_rate_24h: float
    fallback_avg_latency_ms_24h: float | None = None
    fallback_p95_latency_ms_24h: float | None = None
    fallback_last_event_at: str | None = None
    vendors: dict[str, VendorHealthResponse] = Field(default_factory=dict)


def _get_news_bundle(
    symbol: str | None,
    limit: int,
    force_refresh: bool,
) -> tuple[object, int]:
    svc = _news_service()
    final_limit = min(limit, svc.max_articles) if limit else svc.max_articles
    bundle = svc.get_news_intelligence(
        symbol=symbol,
        max_articles=final_limit,
        force_refresh=force_refresh,
    )
    return bundle, final_limit


def _get_watchlist_news_payload(
    account_id: str,
    max_results: int | None,
    force_refresh: bool,
) -> WatchlistNewsResponse:
    watchlist_service = _watchlist_service()
    items = watchlist_service.get_items_with_scores()
    if not items:
        return WatchlistNewsResponse(account_id=account_id, items=[])

    svc = _news_service()
    limit = max_results or svc.max_articles
    symbols = [item["symbol"] for item in items]
    bundles = svc.get_watchlist_news(
        symbols,
        max_articles=limit,
        force_refresh=force_refresh,
    )

    serialized_items: list[NewsBundleResponse] = []
    for symbol in symbols:
        bundle = bundles.get(symbol.upper())
        if not bundle:
            continue
        serialized_items.append(serialize_bundle(bundle, limit=limit))

    return WatchlistNewsResponse(account_id=account_id, items=serialized_items)


def _get_news_health_payload() -> NewsHealthResponse:
    metrics = _news_service().get_health()
    return NewsHealthResponse(**metrics)


def _search_news_bundle(query: str, max_results: int | None) -> tuple[object, int]:
    svc = _news_service()
    limit = max_results or svc.max_articles
    bundle = svc.get_custom_news(query, max_articles=limit)
    return bundle, limit


@router.get("", response_model=NewsBundleResponse)
@cache_response(ttl=120)  # 2 minutes cache for news (frequently accessed)
async def get_news_intelligence(
    request: Request,
    symbol: str | None = Query(
        None,
        description="Optional symbol. If omitted, returns market-wide news. If provided, returns symbol-specific news.",
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
    """Get unified news intelligence for market or specific symbol.

    This endpoint consolidates market-level and symbol-specific news into a single API.
    Use the optional symbol parameter to switch between modes:
    - No symbol parameter: Returns broad market news
    - symbol=AAPL: Returns Apple-specific news

    The response includes sentiment summary and scored articles with AI insights.
    """
    bundle, final_limit = await run_in_threadpool(_get_news_bundle, symbol, limit, force_refresh)
    return serialize_bundle(bundle, limit=final_limit)


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
    return await run_in_threadpool(
        _get_watchlist_news_payload,
        account_id,
        max_results,
        force_refresh,
    )


@router.get("/health", response_model=NewsHealthResponse)
async def get_news_health() -> NewsHealthResponse:
    """Return health information for the news ingestion pipeline."""
    return await run_in_threadpool(_get_news_health_payload)


@router.get("/search", response_model=NewsBundleResponse)
async def search_news(
    query: str = Query(..., description="Free-form news query"),
    max_results: int | None = Query(None, ge=1, le=50),
) -> NewsBundleResponse:
    """Search news without caching results."""
    bundle, limit = await run_in_threadpool(_search_news_bundle, query, max_results)
    return serialize_bundle(bundle, limit=limit)
