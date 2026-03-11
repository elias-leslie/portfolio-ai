"""Batch data loading operations for watchlist scoring.

This module handles:
- Watchlist item loading from database
- Technical indicator batch loading
- Price data batch fetching with rate limiting
- News data batch fetching
- Auto-backfill trigger for missing data
"""

from __future__ import annotations

import time
from typing import Any

import polars as pl

from ...constants import DEFAULT_BACKFILL_DAYS
from ...logging_config import get_logger
from ...portfolio.price_fetcher import PriceDataFetcher
from ...services import NewsService
from ...storage import PortfolioStorage
from ..data_loaders import load_latest_technical as load_latest_technical_snapshots
from ..models import TechnicalSnapshot
from ..refresh_data_fetchers import detect_missing_historical_data

logger = get_logger(__name__)


def load_watchlist_items(storage: PortfolioStorage, account_id: str | None = None) -> pl.DataFrame:
    """Load watchlist items from database.

    Args:
        storage: Database storage instance
        account_id: DEPRECATED - Watchlist is now user-level, this parameter is ignored

    Returns:
        DataFrame with all watchlist items
    """
    # Note: account_id parameter is deprecated but kept for backward compatibility
    # Watchlist is now user-level, not account-specific
    return storage.query(
        """
        SELECT id, symbol
        FROM watchlist_items
        WHERE symbol NOT LIKE 'ZZTEST%%'
        """
    )


def load_latest_technical(
    storage: PortfolioStorage, symbols: list[str]
) -> dict[str, TechnicalSnapshot]:
    """Load latest technical indicators for symbols.

    Args:
        storage: Database storage instance
        symbols: List of symbols to load indicators for

    Returns:
        Map of symbol to TechnicalSnapshot
    """
    return load_latest_technical_snapshots(storage, symbols)


def trigger_auto_backfill(storage: PortfolioStorage, symbols: list[str]) -> None:
    """Trigger automatic backfill for symbols with missing or stale data.

    Args:
        storage: Database storage instance
        symbols: List of symbols to check for missing data
    """
    symbols_needing_backfill = detect_missing_historical_data(
        storage=storage,
        symbols=symbols,
        min_days=30,
        stale_threshold_days=7,
    )

    if symbols_needing_backfill:
        try:
            from ...tasks.ingestion import ingest_historical_ohlcv  # noqa: PLC0415

            logger.info(
                "auto_backfill_triggered",
                symbol_count=len(symbols_needing_backfill),
                symbols=symbols_needing_backfill,
            )

            # Trigger async backfill task (non-blocking)
            ingest_historical_ohlcv(symbols_needing_backfill, days=DEFAULT_BACKFILL_DAYS)

            logger.info(
                "auto_backfill_task_dispatched",
                symbol_count=len(symbols_needing_backfill),
                message="Historical data will be backfilled in background",
            )
        except Exception as e:
            logger.error(
                "auto_backfill_failed_to_trigger",
                error=str(e),
                error_type=type(e).__name__,
            )


def fetch_prices_in_batches(
    fetcher: PriceDataFetcher,
    symbols: list[str],
    batch_size: int,
    batch_delay_seconds: float,
) -> dict[str, Any]:
    """Fetch price data in batches to respect API rate limits.

    Args:
        fetcher: Price data fetcher instance
        symbols: List of symbols to fetch prices for
        batch_size: Number of symbols per batch
        batch_delay_seconds: Delay between batches in seconds

    Returns:
        Map of symbol to price data
    """
    symbol_batches = [symbols[i : i + batch_size] for i in range(0, len(symbols), batch_size)]
    total_batches = len(symbol_batches)

    logger.info(
        "watchlist_refresh_batching",
        total_symbols=len(symbols),
        batch_size=batch_size,
        total_batches=total_batches,
        delay_seconds=batch_delay_seconds,
    )

    price_map: dict[str, Any] = {}
    for batch_idx, batch_symbols in enumerate(symbol_batches, start=1):
        logger.debug(
            "watchlist_refresh_batch",
            batch=batch_idx,
            total_batches=total_batches,
            batch_size=len(batch_symbols),
        )

        batch_prices = fetcher.fetch_price_data(batch_symbols)
        price_map.update(batch_prices)

        # Delay between batches (except after last batch)
        if batch_idx < total_batches and batch_delay_seconds > 0:
            time.sleep(batch_delay_seconds)

    return price_map


def fetch_news_batch(
    news_service: NewsService, symbols: list[str], max_articles: int
) -> dict[str, Any]:
    """Batch-fetch news for all symbols to reduce API calls.

    Args:
        news_service: News service instance
        symbols: List of symbols to fetch news for
        max_articles: Maximum articles per symbol

    Returns:
        Map of symbol to news bundles
    """
    logger.info("watchlist_refresh_news_batch", total_symbols=len(symbols))
    try:
        return news_service.get_watchlist_news(
            symbols=symbols,
            max_articles=max_articles,
            force_refresh=False,  # Respect cache
        )
    except Exception as e:
        logger.warning("watchlist_refresh_news_batch_failed", error=str(e))
        return {}
