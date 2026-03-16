"""Single symbol processing for watchlist scoring.

This module handles:
- Individual symbol snapshot processing
- Price data validation
- Score calculation via refresh_processor
- Snapshot persistence to database
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ...logging_config import get_logger
from ...services import NewsService
from ...storage import PortfolioStorage
from ..models import ScoreWeights, TechnicalSnapshot
from ..refresh_processor import ProcessorConfig, TickerInputData, process_symbol_snapshot

logger = get_logger(__name__)


def process_single_symbol(
    storage: PortfolioStorage,
    symbol: str,
    item_id: str,
    price_map: dict[str, Any],
    technical_map: dict[str, TechnicalSnapshot],
    default_weights: ScoreWeights,
    stale_ttl_minutes: int,
    risk_budget: float,
    now: datetime,
    news_service: NewsService,
    news_max_articles: int,
    news_bundles: dict[str, Any],
    include_news: bool,
) -> tuple[str, str, list[str], list[dict[str, str]]]:
    """Process a single symbol and persist its snapshot.

    Args:
        storage: Database storage instance
        symbol: Ticker symbol to process
        item_id: Watchlist item ID
        price_map: Pre-fetched price data for all symbols
        technical_map: Technical indicators for symbols
        default_weights: Score weights
        stale_ttl_minutes: Stale data TTL
        risk_budget: Risk budget
        now: Current timestamp
        news_service: News service instance
        news_max_articles: Max news articles to fetch
        news_bundles: Pre-fetched news bundles
        include_news: Whether this refresh should fetch/use news data

    Returns:
        Tuple of (symbol, item_id, success_list, failed_list)
    """
    success_list: list[str] = []
    failed_list: list[dict[str, str]] = []

    price_data = price_map.get(symbol)
    if not price_data or price_data.price <= 0:
        logger.warning(
            "watchlist_refresh_missing_price",
            symbol=symbol,
            item_id=item_id,
        )
        failed_list.append(
            {
                "symbol": symbol,
                "reason": "Unable to fetch price data or invalid price",
            }
        )
        return symbol, item_id, success_list, failed_list

    # Process symbol and generate snapshot (extracted to refresh_processor.py)
    # Pass pre-fetched news bundle (Issue #2 fix)
    snapshot = process_symbol_snapshot(
        storage=storage,
        symbol=symbol,
        item_id=item_id,
        input_data=TickerInputData(
            price_data=price_data,
            technical_map=technical_map,
            news_bundle=news_bundles.get(symbol),
        ),
        config=ProcessorConfig(
            default_weights=default_weights,
            stale_ttl_minutes=stale_ttl_minutes,
            risk_budget=risk_budget,
            max_news_articles=news_max_articles,
            now=now,
            include_news=include_news,
        ),
        news_service=news_service,
    )

    storage.query_mgr.upsert_watchlist_snapshot(**snapshot.to_upsert_params())
    success_list.append(symbol)

    return symbol, item_id, success_list, failed_list
