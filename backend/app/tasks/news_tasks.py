"""Celery tasks for news sentiment refresh."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.services import NewsBundle, NewsService, NewsSummary
from app.storage import PortfolioStorage, get_storage
from app.storage.credential_loader import load_credentials_from_database
from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)


def _get_refresh_interval_minutes(storage: PortfolioStorage) -> int:
    row: Any = storage.query(
        """
        SELECT COALESCE(news_refresh_override, default_refresh_minutes, 15) AS refresh_minutes
        FROM user_preferences
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    if row.is_empty():
        return 30
    value = row.to_dicts()[0].get("refresh_minutes")
    if value is None:
        return 30
    return int(value)


def _last_market_refresh_at(storage: PortfolioStorage) -> datetime | None:
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT MAX(fetched_at) FROM news_cache WHERE ticker = %s
            """,
            ["__MARKET__"],
        ).fetchone()
    if not result or result[0] is None:
        return None
    fetched_at = result[0]
    if not isinstance(fetched_at, datetime):
        return None
    return fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=UTC)


def _record_summary(
    storage: PortfolioStorage,
    summary: NewsSummary,
    ttl: timedelta,
    as_of: datetime,
) -> None:
    window_start = as_of - ttl
    model_breakdown = summary.model_breakdown or {}
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO news_summary_log (
                ticker,
                window_start,
                window_end,
                sentiment_score,
                sentiment_delta,
                positive_count,
                neutral_count,
                negative_count,
                article_count,
                model_breakdown
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                summary.ticker,
                window_start,
                as_of,
                summary.score,
                summary.score_change,
                summary.positive_count,
                summary.neutral_count,
                summary.negative_count,
                summary.article_count,
                json.dumps(model_breakdown),
            ],
        )
        conn.commit()


def _refresh_news_sentiment_task(
    self: Any, account_id: str = "default"
) -> dict[str, int | str | float]:
    """Refresh market and watchlist news sentiment caches."""
    start_time = time.time()  # Track task duration
    storage = get_storage()
    load_credentials_from_database()
    news_service = NewsService(storage)
    lookback_hours = news_service.refresh_ttl_from_preferences()
    news_max_articles = news_service.refresh_max_articles_from_preferences()
    watchlist_service = WatchlistService(storage)

    interval_minutes = _get_refresh_interval_minutes(storage)
    now = datetime.now(UTC)
    last_refresh = _last_market_refresh_at(storage)
    should_force_refresh = last_refresh is None or now - last_refresh >= timedelta(
        minutes=interval_minutes
    )

    logger.info(
        "news_refresh_started",
        account_id=account_id,
        force_refresh=should_force_refresh,
        interval_minutes=interval_minutes,
        lookback_hours=lookback_hours,
        max_articles=news_max_articles,
    )

    # Always fetch market bundle; service decides whether to hit external APIs
    market_bundle = news_service.get_news_intelligence(
        None,
        max_articles=news_max_articles,
        force_refresh=should_force_refresh,
    )
    _record_summary(storage, market_bundle.summary, news_service.ttl, now)

    items_with_scores: list[dict[str, Any]] = watchlist_service.get_items_with_scores()
    symbols = [item["symbol"] for item in items_with_scores]
    watchlist_count = 0
    if symbols:
        bundles: dict[str, NewsBundle] = news_service.get_watchlist_news(
            symbols,
            max_articles=news_max_articles,
            force_refresh=should_force_refresh,
        )
        watchlist_count = len(bundles)
        for bundle in bundles.values():
            _record_summary(storage, bundle.summary, news_service.ttl, now)

    logger.info(
        "news_refresh_completed",
        account_id=account_id,
        symbols=len(symbols),
        market_articles=len(market_bundle.articles),
        watchlist_symbols=watchlist_count,
        lookback_hours=news_service.lookback_hours,
    )

    return {
        "account_id": account_id,
        "symbols": len(symbols),
        "market_articles": len(market_bundle.articles),
        "forced": int(should_force_refresh),
        "duration_seconds": round(time.time() - start_time, 2),
    }


refresh_news_sentiment_task = cast(
    Callable[[Any, str], dict[str, int | str | float]],
    celery_app.task(
        name="refresh_news_sentiment",
        bind=True,
    )(_refresh_news_sentiment_task),
)
