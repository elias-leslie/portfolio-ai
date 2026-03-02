"""Item enrichment helpers for watchlist service.

This module provides:
- News intelligence enrichment
- Data quality enrichment
- Priority indicators enrichment
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ...logging_config import get_logger
from ..data_quality import calculate_data_quality
from ..models import WatchlistItemDict
from ..priority import calculate_priority_indicators

if TYPE_CHECKING:
    from ...storage import PortfolioStorage
    from ..watchlist_repository import WatchlistRepository

from .intelligence import build_news_intelligence

logger = get_logger(__name__)


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
            item_data["data_quality"] = {
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
        else:
            item_data["data_quality"] = None
    except Exception as e:
        logger.warning(
            "watchlist_data_quality_failed",
            symbol=symbol,
            error=str(e),
        )
        item_data["data_quality"] = None


def enrich_priority_indicators(results: list[dict[str, Any]]) -> None:
    """Enrich each item in results with priority indicators in place."""
    for item in results:
        indicators = calculate_priority_indicators(
            cast(list[WatchlistItemDict], results), cast(WatchlistItemDict, item)
        )
        item["priority_indicators"] = [ind.model_dump() for ind in indicators]


__all__ = [
    "enrich_data_quality",
    "enrich_news_intelligence",
    "enrich_priority_indicators",
]
