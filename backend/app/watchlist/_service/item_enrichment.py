"""Item enrichment helpers for watchlist service.

This module provides:
- News intelligence enrichment
- Data quality enrichment
- Priority indicators enrichment
"""

from __future__ import annotations

from collections import defaultdict
from importlib import import_module
from typing import TYPE_CHECKING, Any, cast

from ...api.symbols.builders import build_portfolio_section, build_quote_section
from ...api.symbols.data_fetchers import get_market_data
from ...api.symbols.decisions import build_symbol_decision
from ...api.symbols.portfolio_context import fetch_symbol_portfolio_context
from ...api.symbols.recommendations import generate_recommendation
from ...logging_config import get_logger
from ...portfolio.price_fetcher import PriceDataFetcher
from ...utils.market_hours import get_market_status
from ..data_quality import calculate_data_quality
from ..models import WatchlistItemDict
from ..priority import calculate_priority_indicators

if TYPE_CHECKING:
    from ...storage import PortfolioStorage
    from ..watchlist_repository import WatchlistRepository

from .intelligence import build_news_intelligence, build_news_intelligence_batch

logger = get_logger(__name__)

_WATCHLIST_QUOTE_DISPLAY_MAX_AGE_MINUTES = 24 * 60


def _get_jenny_dashboard() -> Any:
    service_cls = import_module("app.services.jenny_operator_service").JennyOperatorService
    return service_cls().get_dashboard()


def _build_portfolio_context(
    storage: PortfolioStorage,
    symbols: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    return fetch_symbol_portfolio_context(storage, symbols)


def _serialize_data_quality(dq: Any) -> dict[str, Any]:
    """Serialize a DataQuality object into a JSON-compatible dict."""
    return {
        "overall_pct": dq.overall_pct,
        "pillars": {
            name: {
                "status": pq.status,
                "score": pq.score,
                "details": pq.details,
            }
            for name, pq in dq.pillars.items()
        },
    }


def enrich_news_intelligence(
    repo: WatchlistRepository, symbol: str, item_data: dict[str, Any]
) -> None:
    """Enrich item_data with news intelligence in place."""
    try:
        news_intel = build_news_intelligence(repo, symbol)
        item_data["news_intelligence"] = (
            news_intel.model_dump(mode="json") if news_intel else None
        )
    except Exception as e:
        logger.warning(
            "watchlist_news_intelligence_failed",
            symbol=symbol,
            error=str(e),
        )
        item_data["news_intelligence"] = None


def enrich_data_quality(
    storage: PortfolioStorage, symbol: str, item_data: dict[str, Any]
) -> None:
    """Enrich item_data with data quality in place."""
    try:
        quality_map = calculate_data_quality(storage, [symbol])
        dq = quality_map.get(symbol)
        if dq:
            item_data["data_quality"] = _serialize_data_quality(dq)
        else:
            item_data["data_quality"] = None
    except Exception as e:
        logger.warning(
            "watchlist_data_quality_failed",
            symbol=symbol,
            error=str(e),
        )
        item_data["data_quality"] = None


def build_news_intelligence_map(
    repo: WatchlistRepository, symbols: list[str]
) -> dict[str, Any]:
    """Pre-fetch news intelligence for all symbols in one DB round-trip.

    Returns:
        Dict mapping symbol -> serialized news_intelligence dict (or None)
    """
    try:
        intel_by_symbol = build_news_intelligence_batch(repo, symbols)
        return {
            symbol: (news_intel.model_dump(mode="json") if news_intel else None)
            for symbol, news_intel in intel_by_symbol.items()
        }
    except Exception as e:
        logger.warning("watchlist_news_intelligence_batch_failed", error=str(e))
        return {}


def build_data_quality_map(
    storage: PortfolioStorage, symbols: list[str]
) -> dict[str, Any]:
    """Pre-fetch data quality for all symbols in one batch call.

    Returns:
        Dict mapping symbol -> serialized data_quality dict (or None)
    """
    try:
        quality_map = calculate_data_quality(storage, symbols)
        result: dict[str, Any] = {}
        for symbol, dq in quality_map.items():
            if dq:
                result[symbol] = _serialize_data_quality(dq)
            else:
                result[symbol] = None
        return result
    except Exception as e:
        logger.warning("watchlist_data_quality_batch_failed", error=str(e))
        return {}


def build_quote_map(storage: PortfolioStorage, symbols: list[str]) -> dict[str, Any]:
    """Return canonical current quotes for visible watchlist price fields."""
    normalized_symbols = list(
        dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip())
    )
    if not normalized_symbols:
        return {}

    try:
        fetcher = PriceDataFetcher(storage)
        price_data = fetcher.fetch_cached_price_data(
            normalized_symbols,
            max_age_minutes=_WATCHLIST_QUOTE_DISPLAY_MAX_AGE_MINUTES,
        )
    except Exception as exc:
        logger.warning("watchlist_quote_fetch_failed", error=str(exc))
        return {}

    quotes: dict[str, Any] = {}

    for symbol in normalized_symbols:
        quote = price_data.get(symbol)
        if quote is None or quote.price <= 0 or quote.error:
            continue

        section = build_quote_section(
            {
                "price": quote.price if quote.price > 0 and not quote.error else None,
                "source": quote.source,
                "cached_at": quote.cached_at,
                "session": get_market_status(quote.cached_at),
                "error": quote.error,
            }
        )
        quotes[symbol] = section.model_dump(mode="json") if section else None

    return quotes


def build_watchlist_decision_map(
    storage: PortfolioStorage,
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Resolve current decision payloads for a batch of watchlist items."""
    if not items:
        return {}

    positions_by_symbol, summary = _build_portfolio_context(
        storage,
        [str(item.get("symbol") or "") for item in items],
    )
    market = get_market_data(storage)

    notifications_by_symbol: dict[str, list[Any]] = defaultdict(list)
    reviews_by_symbol: dict[str, Any] = {}
    try:
        dashboard = _get_jenny_dashboard()
    except Exception as exc:
        logger.warning("watchlist_jenny_dashboard_failed", error=str(exc))
    else:
        for notification in getattr(dashboard, "notifications", []):
            if notification.symbol:
                notifications_by_symbol[str(notification.symbol).upper()].append(notification)
        for review in getattr(dashboard, "symbol_reviews", []):
            if review.symbol:
                reviews_by_symbol.setdefault(str(review.symbol).upper(), review)

    decisions: dict[str, dict[str, Any]] = {}
    for item in items:
        symbol = str(item.get("symbol") or "").upper()
        if not symbol:
            continue

        notifications = notifications_by_symbol.get(symbol, [])
        latest_review = reviews_by_symbol.get(symbol)
        has_live_setup = bool(item.get("signal_type"))
        if not has_live_setup and not notifications and latest_review is None:
            continue

        recommendation = generate_recommendation(
            item,
            {
                "position": positions_by_symbol.get(symbol),
                "summary": summary,
            },
            market,
        )
        portfolio_section = build_portfolio_section(
            positions_by_symbol.get(symbol),
            summary,
        )
        decision = build_symbol_decision(
            symbol=symbol,
            recommendation=recommendation,
            generated_at=item.get("decision_generated_at") or item.get("updated_at"),
            notifications=notifications,
            latest_review=latest_review,
            portfolio_position=portfolio_section.position,
        )
        decisions[symbol] = decision.model_dump(mode="json")

    return decisions


def enrich_priority_indicators(results: list[dict[str, Any]]) -> None:
    """Enrich each item in results with priority indicators in place."""
    typed_results = cast(list[WatchlistItemDict], results)
    for item in results:
        indicators = calculate_priority_indicators(
            typed_results, cast(WatchlistItemDict, item)
        )
        item["priority_indicators"] = [ind.model_dump() for ind in indicators]


__all__ = [
    "build_data_quality_map",
    "build_news_intelligence_map",
    "build_quote_map",
    "build_watchlist_decision_map",
    "enrich_data_quality",
    "enrich_news_intelligence",
    "enrich_priority_indicators",
]
