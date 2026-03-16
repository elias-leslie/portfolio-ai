"""Multi-symbol processing and result aggregation for watchlist scoring.

This module handles:
- Processing all watchlist items in sequence
- Progress tracking via Redis
- Error handling and retry logic
- Result aggregation and summary statistics
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import polars as pl

from ...logging_config import get_logger
from ...services import NewsService
from ...storage import PortfolioStorage
from ..models import ScoreWeights, TechnicalSnapshot
from .processor import process_single_symbol
from .redis_tracker import update_progress

logger = get_logger(__name__)


def process_all_symbols(
    storage: PortfolioStorage,
    items_df: pl.DataFrame,
    redis_key: str,
    price_map: dict[str, Any],
    technical_map: dict[str, TechnicalSnapshot],
    default_weights: ScoreWeights,
    stale_ttl_minutes: int,
    risk_budget: float,
    news_service: NewsService,
    news_max_articles: int,
    news_bundles: dict[str, Any],
    include_news: bool,
) -> tuple[int, list[str], list[str], list[dict[str, str]]]:
    """Process all watchlist items and collect results.

    Args:
        storage: Database storage instance
        items_df: DataFrame with watchlist items
        redis_key: Redis key for progress tracking
        price_map: Pre-fetched price data for all symbols
        technical_map: Technical indicators for symbols
        default_weights: Score weights
        stale_ttl_minutes: Stale data TTL
        risk_budget: Risk budget
        news_service: News service instance
        news_max_articles: Max news articles to fetch
        news_bundles: Pre-fetched news bundles
        include_news: Whether this refresh should fetch/use news data

    Returns:
        Tuple of (processed, processed_symbols, success_list, failed_list)
    """
    processed = 0
    now = datetime.now(UTC)
    processed_symbols: list[str] = []
    success_list: list[str] = []
    failed_list: list[dict[str, str]] = []

    for row in items_df.iter_rows(named=True):
        symbol = row["symbol"]
        item_id = row["id"]

        # Update refresh status for current symbol
        update_progress(redis_key, symbol, processed)

        try:
            # Process symbol and collect results
            _, _, symbol_success, symbol_failed = process_single_symbol(
                storage=storage,
                symbol=symbol,
                item_id=item_id,
                price_map=price_map,
                technical_map=technical_map,
                default_weights=default_weights,
                stale_ttl_minutes=stale_ttl_minutes,
                risk_budget=risk_budget,
                now=now,
                news_service=news_service,
                news_max_articles=news_max_articles,
                news_bundles=news_bundles,
                include_news=include_news,
            )

            # Aggregate results
            if symbol_success:
                processed += 1
                processed_symbols.append(symbol)
                success_list.extend(symbol_success)
            if symbol_failed:
                failed_list.extend(symbol_failed)

        except Exception as e:
            # Log error and continue processing remaining symbols
            logger.warning(
                "watchlist_refresh_symbol_failed",
                symbol=symbol,
                item_id=item_id,
                error=str(e),
            )
            failed_list.append({"symbol": symbol, "reason": str(e)})

    return processed, processed_symbols, success_list, failed_list


def aggregate_results(
    processed_symbols: list[str],
    success_list: list[str],
    failed_list: list[dict[str, str]],
    total_batches: int,
) -> dict[str, Any]:
    """Aggregate processing results into summary statistics.

    Args:
        processed_symbols: List of all processed symbols
        success_list: List of successfully processed symbols
        failed_list: List of failed items with reasons
        total_batches: Number of batches executed

    Returns:
        Summary dict with counts and lists
    """
    return {
        "processed": len(success_list),
        "symbols": processed_symbols,
        "batches": total_batches,
        "success_count": len(success_list),
        "failed_count": len(failed_list),
        "success": success_list,
        "failed": failed_list,
    }
