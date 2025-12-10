"""Snapshot building and payload preparation for watchlist refresh.

This module handles:
- News article payload building and publisher extraction
- Technical snapshot preparation
- Final watchlist snapshot construction
- Price change handling and backfill queuing

Extracted from refresh_processor.py to improve modularity.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from ..logging_config import get_logger
from ..portfolio.models import PriceData
from ..services.news_models import NewsArticle, NewsBundle
from ..storage import PortfolioStorage
from ..utils.market_hours import is_stale
from .models import TechnicalSnapshot, WatchlistSnapshot
from .refresh_data_fetchers import calculate_price_change
from .refresh_narrative import NarrativeResultDict

logger = get_logger(__name__)

WATCHLIST_NEWS_ARTICLE_LIMIT = 5


def _normalize_publisher_field(value: Any) -> str | None:
    """Normalize publisher field from various formats."""
    if isinstance(value, dict):
        for key in ("title", "name"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    elif isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _get_article_attr(article: NewsArticle | Mapping[str, Any], field: str) -> Any:
    """Get attribute from article (handles both object and dict)."""
    if isinstance(article, dict):
        return article.get(field)
    return getattr(article, field, None)


def _extract_article_vendor(article: NewsArticle | Mapping[str, Any]) -> str | None:
    """Extract vendor information from article."""
    vendor = _get_article_attr(article, "vendor")
    if isinstance(vendor, str) and vendor.strip():
        return vendor.strip()

    raw_payload = _get_article_attr(article, "raw") or {}
    fallback_vendor = raw_payload.get("vendor")
    if isinstance(fallback_vendor, str) and fallback_vendor.strip():
        return fallback_vendor.strip()

    inner_raw = raw_payload.get("raw")
    if isinstance(inner_raw, dict):
        nested_vendor = inner_raw.get("vendor")
        if isinstance(nested_vendor, str) and nested_vendor.strip():
            return nested_vendor.strip()

    return None


def _extract_article_publisher(article: NewsArticle | Mapping[str, Any]) -> str | None:
    """Extract publisher information from article."""
    publisher = _get_article_attr(article, "source")
    if isinstance(publisher, str) and publisher.strip():
        return publisher.strip()

    raw_payload = _get_article_attr(article, "raw") or {}
    for key in ("news_source_name", "source"):
        candidate = _normalize_publisher_field(raw_payload.get(key))
        if candidate:
            return candidate

    inner_raw = raw_payload.get("raw")
    if isinstance(inner_raw, dict):
        for key in ("news_source_name", "source"):
            candidate = _normalize_publisher_field(inner_raw.get(key))
            if candidate:
                return candidate

    return None


def build_recent_news_payload(
    news_bundle: NewsBundle,
    *,
    max_articles: int = WATCHLIST_NEWS_ARTICLE_LIMIT,
) -> dict[str, Any]:
    """Serialize recent news bundle for watchlist snapshots."""

    articles_payload: list[dict[str, Any]] = []
    for article in news_bundle.articles[:max_articles]:
        article_payload = article.model_dump(mode="json")

        vendor = _extract_article_vendor(article)
        if vendor:
            article_payload["vendor"] = vendor
        elif "vendor" not in article_payload:
            article_payload["vendor"] = None

        publisher = _extract_article_publisher(article)
        if publisher:
            article_payload["source"] = publisher
        elif not article_payload.get("source"):
            article_payload["source"] = None

        # Explicit publisher alias to simplify UI rendering logic
        article_payload.setdefault("publisher", article_payload.get("source"))

        articles_payload.append(article_payload)

    return {
        "summary": news_bundle.summary.model_dump(mode="json"),
        "articles": articles_payload,
    }


def handle_price_change_and_backfill(
    storage: PortfolioStorage,
    symbol: str,
    price: float,
    item_id: str,
) -> float:
    """Calculate price change and queue backfill if needed.

    Returns:
        Price change percentage (defaults to 0.0 if no historical data)
    """
    change_pct, has_historical_data = calculate_price_change(storage, symbol, price, item_id)

    # Queue backfill task if historical data is missing
    if not has_historical_data:
        try:
            from ..tasks.ingestion import (  # noqa: PLC0415 - avoid circular dependency
                ingest_historical_ohlcv,
            )

            # Queue backfill for 1260 trading days (~5 years)
            ingest_historical_ohlcv.delay([symbol], days=1260)
            logger.info(
                "watchlist_refresh_queued_backfill",
                symbol=symbol,
                item_id=item_id,
                reason="Missing day_bars data - queued historical backfill task",
            )
        except Exception as e:
            logger.warning(
                "watchlist_refresh_backfill_queue_failed",
                symbol=symbol,
                item_id=item_id,
                error=str(e),
            )

    # Default to 0.0% change if no comparison data available
    if change_pct is None:
        logger.info(
            "watchlist_refresh_defaulted_change_pct",
            symbol=symbol,
            item_id=item_id,
            change_pct=0.0,
            reason="No comparison data (first snapshot) - defaulting to 0.0%",
        )
        change_pct = 0.0

    return change_pct


def prepare_technical_snapshot(
    technical_map: dict[str, TechnicalSnapshot],
    symbol: str,
    price: float,
) -> TechnicalSnapshot:
    """Get technical snapshot and set current price.

    Returns:
        TechnicalSnapshot with current price set
    """
    technical_snapshot = technical_map.get(symbol, TechnicalSnapshot())
    technical_snapshot.price = price
    return technical_snapshot


def build_watchlist_snapshot(
    item_id: str,
    now: datetime,
    price_data: PriceData,
    change_pct: float,
    breakdown: Any,
    narrative_result: NarrativeResultDict,
    company_health_str: str | None,
    earnings_date_obj: datetime | None,
    earnings_days_away_val: int | None,
    news_sentiment_value: float | None,
    recent_news_value: dict[str, Any] | None,
    timeframe_short_aligned: bool = False,
    timeframe_long_aligned: bool = False,
    volume_relative: float | None = None,
) -> WatchlistSnapshot:
    """Build final WatchlistSnapshot from all processed data.

    Args:
        item_id: Watchlist item ID
        now: Current timestamp
        price_data: Price data object
        change_pct: Price change percentage
        breakdown: Score breakdown object
        narrative_result: Dict with narrative/trade results
        company_health_str: Company health classification
        earnings_date_obj: Earnings date
        earnings_days_away_val: Days until earnings
        news_sentiment_value: News sentiment score
        recent_news_value: Recent news payload

    Returns:
        Complete WatchlistSnapshot ready to persist
    """
    # Calculate staleness
    data_is_stale = is_stale(fetched_at=now, now=now)

    # Create snapshot
    snapshot = WatchlistSnapshot(
        item_id=item_id,
        fetched_at=now,
        price=price_data.price,
        change_pct=change_pct,
        beta=price_data.beta,
        volatility=price_data.volatility,
        overall_score=breakdown.overall,
        technical_score=breakdown.technical.score,
        fundamental_score=breakdown.fundamental.score if breakdown.fundamental else None,
        is_stale=data_is_stale,
        raw_metrics=breakdown.to_snapshot_payload(),
        # Narrative fields
        signal_type=narrative_result["signal_type"],
        signal_strength=narrative_result["signal_strength"],
        narrative_headline=narrative_result["headline"],
        recommended_style=narrative_result["style_result"]["style"],
        style_confidence=narrative_result["style_result"]["confidence"],
        optimal_holding_period=narrative_result["style_result"]["holding_period"],
        risk_level=narrative_result["style_result"]["risk_level"],
        # Trade calculation fields
        entry_price=narrative_result["entry_price"],
        stop_loss=narrative_result["stop_loss"],
        profit_target=narrative_result["profit_target"],
        position_size_shares=narrative_result["position_size"],
        # Narrative text fields
        narrative_action_plan=narrative_result["action_plan"],
        narrative_position_sizing=narrative_result["position_sizing"],
        narrative_company_health={"bullets": narrative_result["company_health_bullets"]}
        if narrative_result["company_health_bullets"]
        else None,
        narrative_special_notes=narrative_result["special_notes"],
        # Fundamental/earnings fields
        company_health=company_health_str,
        earnings_date=earnings_date_obj,
        earnings_days_away=earnings_days_away_val,
        # News/sentiment fields
        news_sentiment_score=news_sentiment_value,
        recent_news_headlines=recent_news_value,
        # Timeframe alignment fields (FEAT-183)
        timeframe_short_aligned=timeframe_short_aligned,
        timeframe_long_aligned=timeframe_long_aligned,
        volume_relative=volume_relative,
    )

    return snapshot
