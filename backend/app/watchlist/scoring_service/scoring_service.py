"""Watchlist scoring service for background refresh tasks.

This module handles:
- Watchlist score calculation and refresh orchestration
- Background scoring tasks
- Batch processing with rate limiting

Per-symbol processing logic extracted to refresh_processor.py for modularity.
"""

from __future__ import annotations

from typing import Any

from ...logging_config import get_logger
from ...portfolio.price_fetcher import PriceDataFetcher
from ...storage import PortfolioStorage
from ...utils.watchlist_cache import get_watchlist_symbols_cached
from .aggregator import aggregate_results, process_all_symbols
from .context import initialize_scoring_context
from .redis_tracker import complete_refresh

logger = get_logger(__name__)


def refresh_watchlist_scores(
    storage: PortfolioStorage,
    *,
    account_id: str | None = None,
    price_fetcher: PriceDataFetcher | None = None,
    batch_size: int = 20,
    batch_delay_seconds: float = 2.0,
    symbols_filter: list[str] | None = None,
) -> dict[str, Any]:
    """Refresh watchlist scores for all items or a specific account.

    Args:
        storage: Database storage instance
        account_id: Optional account ID to filter items (None = all accounts)
        price_fetcher: Optional price fetcher instance (creates new if None)
        batch_size: Number of symbols to fetch in each batch (default: 20)
        batch_delay_seconds: Delay between batches to respect rate limits (default: 2.0)
        symbols_filter: Optional list of specific symbols to refresh (None = all)

    Returns:
        Dict with processing statistics:
        - processed: Number of items successfully processed
        - symbols: List of symbols processed
        - batches: Number of batches executed
        - success_count: Number of successful items
        - failed_count: Number of failed items
        - success: List of successful symbols
        - failed: List of failed items with reasons

    Note:
        Batching strategy respects API quota limits:
        - YFinance: Unlimited (primary source, handles bulk requests)
        - TwelveData: 8 req/min, 800/day (batch_size=20, delay=2s = 6/min conservative)
        - Polygon: 5 req/min (batch_size=20, delay=2s = well under limit)
        Conservative defaults ensure we stay within free tier quotas even with failover.
    """
    # Get symbols early to check if empty (Issue #4 fix - use Redis cache)
    # BEFORE: Multiple tasks query watchlist_items independently (2+ queries)
    # AFTER: First task caches, subsequent tasks use cache (1 query, rest from cache)
    symbols = get_watchlist_symbols_cached(storage, account_id, ttl_seconds=60)
    if not symbols:
        logger.info("watchlist_refresh_no_items", account_id=account_id)
        return {"processed": 0, "symbols": [], "batches": 0}

    # Apply symbols filter if provided (for targeted single-symbol refreshes)
    if symbols_filter:
        symbols = [s for s in symbols if s in symbols_filter]
        if not symbols:
            logger.info(
                "watchlist_refresh_no_matching_symbols",
                account_id=account_id,
                filter=symbols_filter,
            )
            return {"processed": 0, "symbols": [], "batches": 0}

    symbols = sorted(symbols)

    # Initialize all scoring context
    (
        items_df,
        total_items,
        redis_key,
        _,  # fetcher not needed after initialization
        prefs,
        news_service,
        technical_map,
        default_weights,
        stale_ttl_minutes,
        risk_budget,
        price_map,
        total_batches,
        news_bundles,
    ) = initialize_scoring_context(
        storage, symbols, account_id, price_fetcher, batch_size, batch_delay_seconds
    )

    # Process all symbols
    processed, processed_symbols, success_list, failed_list = process_all_symbols(
        storage=storage,
        items_df=items_df,
        redis_key=redis_key,
        price_map=price_map,
        technical_map=technical_map,
        default_weights=default_weights,
        stale_ttl_minutes=stale_ttl_minutes,
        risk_budget=risk_budget,
        news_service=news_service,
        news_max_articles=prefs.news_max_articles,
        news_bundles=news_bundles,
    )

    # Log completion and update Redis
    logger.info(
        "watchlist_refresh_completed",
        processed=processed,
        symbols=processed_symbols,
        batches=total_batches,
        success_count=len(success_list),
        failed_count=len(failed_list),
    )
    complete_refresh(redis_key, total_items, processed)

    # Return aggregated results
    return aggregate_results(processed_symbols, success_list, failed_list, total_batches)
