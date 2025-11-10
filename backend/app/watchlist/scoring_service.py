"""Watchlist scoring service for background refresh tasks.

This module handles:
- Watchlist score calculation and refresh orchestration
- Background scoring tasks
- Batch processing with rate limiting

Per-ticker processing logic extracted to refresh_processor.py for modularity.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from typing import Any

import polars as pl
import redis

from ..logging_config import get_logger
from ..portfolio.price_fetcher import PriceDataFetcher
from ..services import NewsService
from ..storage import PortfolioStorage
from ..storage.credential_loader import load_credentials_from_database
from ..utils.preferences_loader import UserPreferences
from ..utils.watchlist_cache import get_watchlist_symbols_cached
from .models import ScoreWeights, TechnicalSnapshot
from .refresh_processor import detect_missing_historical_data, process_ticker_snapshot

logger = get_logger(__name__)

# Redis client for tracking refresh progress
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_redis_client: Any = None


def _get_redis_client() -> Any:  # redis.Redis with decode_responses=True
    """Get or create Redis client for progress tracking."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _load_watchlist_items(storage: PortfolioStorage, account_id: str | None = None) -> pl.DataFrame:
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
        """
    )


def _load_latest_technical(
    storage: PortfolioStorage, symbols: list[str]
) -> dict[str, TechnicalSnapshot]:
    """Load latest technical indicators for symbols."""
    if not symbols:
        return {}

    placeholders = ",".join(["?"] * len(symbols))
    df = storage.query(
        f"""
        SELECT *
        FROM technical_indicators
        WHERE ticker IN ({placeholders})
        ORDER BY ticker, date DESC
        """,
        symbols,
    )

    if df.is_empty():
        return {}

    grouped = df.group_by("ticker").agg(pl.all().first())
    snapshots: dict[str, TechnicalSnapshot] = {}
    for row in grouped.iter_rows(named=True):
        calculated_at = row.get("calculated_at")
        if isinstance(calculated_at, datetime) and calculated_at.tzinfo is None:
            calculated_at = calculated_at.replace(tzinfo=UTC)
        snapshots[row["ticker"]] = TechnicalSnapshot(
            rsi_14=row.get("rsi_14"),
            sma_20=row.get("sma_20"),
            sma_5=row.get("sma_5"),
            sma_50=row.get("sma_50"),
            sma_200=row.get("sma_200"),
            ema_20=row.get("ema_20"),
            ema_50=row.get("ema_50"),
            ema_200=row.get("ema_200"),
            macd=row.get("macd"),
            macd_signal=row.get("macd_signal"),
            price=None,
            calculated_at=calculated_at,
        )
    return snapshots


# NOTE: User preferences loading moved to UserPreferences.load_all()
# in app.utils.preferences_loader to eliminate duplicate queries (Issue #3)


def _trigger_auto_backfill(storage: PortfolioStorage, symbols: list[str]) -> None:
    """Trigger automatic backfill for tickers with missing or stale data."""
    tickers_needing_backfill = detect_missing_historical_data(
        storage=storage,
        symbols=symbols,
        min_days=30,
        stale_threshold_days=7,
    )

    if tickers_needing_backfill:
        try:
            from ..tasks.data_ingestion_tasks import ingest_historical_ohlcv  # noqa: PLC0415

            logger.info(
                "auto_backfill_triggered",
                ticker_count=len(tickers_needing_backfill),
                tickers=tickers_needing_backfill,
            )

            # Trigger async backfill task (non-blocking)
            ingest_historical_ohlcv.delay(tickers_needing_backfill, days=252)

            logger.info(
                "auto_backfill_task_dispatched",
                ticker_count=len(tickers_needing_backfill),
                message="Historical data will be backfilled in background",
            )
        except Exception as e:
            logger.error(
                "auto_backfill_failed_to_trigger",
                error=str(e),
                error_type=type(e).__name__,
            )


def _init_redis_refresh_status(account_id: str | None, symbols: list[str], total_items: int) -> str:
    """Initialize refresh status in Redis and return the key."""
    redis_key = f"watchlist:refresh:{account_id or 'all'}"
    try:
        redis_client = _get_redis_client()
        redis_client.setex(
            redis_key,
            900,  # 15 minute TTL
            json.dumps(
                {
                    "status": "running",
                    "started_at": datetime.now(UTC).isoformat(),
                    "total_items": total_items,
                    "processed_items": 0,
                    "current_symbol": None,
                    "symbols": symbols,
                }
            ),
        )
    except Exception as e:
        logger.warning("Failed to initialize Redis refresh status", error=str(e))
    return redis_key


def _update_redis_progress(redis_key: str, symbol: str, processed: int) -> None:
    """Update Redis with current refresh progress."""
    try:
        redis_client = _get_redis_client()
        redis_value = redis_client.get(redis_key)
        status_data = json.loads(str(redis_value) if redis_value else "{}")
        status_data.update(
            {
                "current_symbol": symbol,
                "processed_items": processed,
            }
        )
        redis_client.setex(redis_key, 900, json.dumps(status_data))
    except Exception as e:
        logger.debug("Failed to update Redis refresh status", error=str(e))


def _complete_redis_refresh(redis_key: str, total_items: int, processed: int) -> None:
    """Mark refresh as completed in Redis."""
    try:
        redis_client = _get_redis_client()
        redis_value = redis_client.get(redis_key)
        existing_data = json.loads(str(redis_value) if redis_value else "{}")
        completed_data = {
            "status": "completed",
            "started_at": existing_data.get("started_at"),
            "total_items": total_items,
            "processed_items": processed,
            "current_symbol": None,
            "is_refreshing": False,
        }
        redis_client.setex(redis_key, 5, json.dumps(completed_data))
    except Exception as e:
        logger.warning("Failed to update Redis refresh completion status", error=str(e))


def _fetch_prices_in_batches(
    fetcher: PriceDataFetcher,
    symbols: list[str],
    batch_size: int,
    batch_delay_seconds: float,
) -> dict[str, Any]:
    """Fetch price data in batches to respect API rate limits."""
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


def _fetch_news_batch(
    news_service: NewsService, symbols: list[str], max_articles: int
) -> dict[str, Any]:
    """Batch-fetch news for all symbols to reduce API calls."""
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


def _initialize_scoring_context(
    storage: PortfolioStorage,
    symbols: list[str],
    account_id: str | None,
    price_fetcher: PriceDataFetcher | None,
    batch_size: int,
    batch_delay_seconds: float,
) -> tuple[
    pl.DataFrame,
    int,
    str,
    PriceDataFetcher,
    UserPreferences,
    NewsService,
    dict[str, TechnicalSnapshot],
    ScoreWeights,
    int,
    float,
    dict[str, Any],
    int,
    dict[str, Any],
]:
    """Initialize all context needed for watchlist scoring.

    Args:
        storage: Database storage instance
        symbols: Sorted list of watchlist symbols (already fetched)
        account_id: Optional account ID
        price_fetcher: Optional price fetcher instance
        batch_size: Batch size for price fetching
        batch_delay_seconds: Delay between batches

    Returns:
        Tuple containing:
        - items_df: DataFrame with watchlist items
        - total_items: Count of total items
        - redis_key: Redis key for progress tracking
        - fetcher: Price data fetcher instance
        - prefs: User preferences
        - news_service: News service instance
        - technical_map: Technical indicators for symbols
        - default_weights: Score weights from preferences
        - stale_ttl_minutes: Stale data TTL
        - risk_budget: Risk budget from preferences
        - price_map: Pre-fetched price data for all symbols
        - total_batches: Number of price fetch batches
        - news_bundles: Pre-fetched news for all symbols
    """

    # Load full item data for processing (we still need IDs for snapshots)
    items_df = _load_watchlist_items(storage, account_id)
    total_items = len(items_df)

    # AUTO-BACKFILL: Check for missing or stale historical data
    _trigger_auto_backfill(storage, symbols)

    # Initialize refresh status in Redis
    redis_key = _init_redis_refresh_status(account_id, symbols, total_items)

    # Setup fetcher and load credentials
    fetcher = price_fetcher or PriceDataFetcher(storage)
    load_credentials_from_database()

    # Load ALL user preferences in ONE query (Issue #3 fix)
    prefs = UserPreferences.load_all(storage)

    # Setup news service with preferences
    news_service = NewsService(storage)
    news_service.lookback_hours = prefs.news_lookback_hours
    news_max_articles = prefs.news_max_articles

    # Load technical indicators and extract preferences
    technical_map = _load_latest_technical(storage, symbols)
    default_weights = ScoreWeights(
        price=prefs.watchlist_price_weight,
        technical=prefs.watchlist_technical_weight,
    )
    stale_ttl_minutes = prefs.get_stale_ttl_minutes()
    risk_budget = prefs.watchlist_risk_budget

    # Batch-fetch price data and news BEFORE processing loop
    price_map = _fetch_prices_in_batches(fetcher, symbols, batch_size, batch_delay_seconds)
    total_batches = len([symbols[i : i + batch_size] for i in range(0, len(symbols), batch_size)])
    news_bundles = _fetch_news_batch(news_service, symbols, news_max_articles)

    return (
        items_df,
        total_items,
        redis_key,
        fetcher,
        prefs,
        news_service,
        technical_map,
        default_weights,
        stale_ttl_minutes,
        risk_budget,
        price_map,
        total_batches,
        news_bundles,
    )


def _process_single_ticker(
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
) -> tuple[str, str, list[str], list[dict[str, str]]]:
    """Process a single ticker and persist its snapshot.

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

    # Process ticker and generate snapshot (extracted to refresh_processor.py)
    # Pass pre-fetched news bundle (Issue #2 fix)
    snapshot = process_ticker_snapshot(
        storage=storage,
        symbol=symbol,
        item_id=item_id,
        price_data=price_data,
        technical_map=technical_map,
        default_weights=default_weights,
        stale_ttl_minutes=stale_ttl_minutes,
        risk_budget=risk_budget,
        now=now,
        news_service=news_service,
        max_news_articles=news_max_articles,
        news_bundle=news_bundles.get(symbol),  # Use pre-fetched bundle
    )

    storage.query_mgr.upsert_watchlist_snapshot(**snapshot.to_upsert_params())
    success_list.append(symbol)

    return symbol, item_id, success_list, failed_list


def _process_all_tickers(
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
        _update_redis_progress(redis_key, symbol, processed)

        try:
            # Process ticker and collect results
            _, _, ticker_success, ticker_failed = _process_single_ticker(
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
            )

            # Aggregate results
            if ticker_success:
                processed += 1
                processed_symbols.append(symbol)
                success_list.extend(ticker_success)
            if ticker_failed:
                failed_list.extend(ticker_failed)

        except Exception as e:
            # Log error and continue processing remaining tickers
            logger.warning(
                "watchlist_refresh_ticker_failed",
                symbol=symbol,
                item_id=item_id,
                error=str(e),
            )
            failed_list.append({"symbol": symbol, "reason": str(e)})

    return processed, processed_symbols, success_list, failed_list


def _aggregate_results(
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


def refresh_watchlist_scores(
    storage: PortfolioStorage,
    *,
    account_id: str | None = None,
    price_fetcher: PriceDataFetcher | None = None,
    batch_size: int = 20,
    batch_delay_seconds: float = 2.0,
) -> dict[str, Any]:
    """Refresh watchlist scores for all items or a specific account.

    Args:
        storage: Database storage instance
        account_id: Optional account ID to filter items (None = all accounts)
        price_fetcher: Optional price fetcher instance (creates new if None)
        batch_size: Number of symbols to fetch in each batch (default: 20)
        batch_delay_seconds: Delay between batches to respect rate limits (default: 2.0)

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
    ) = _initialize_scoring_context(
        storage, symbols, account_id, price_fetcher, batch_size, batch_delay_seconds
    )

    # Process all tickers
    processed, processed_symbols, success_list, failed_list = _process_all_tickers(
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
    _complete_redis_refresh(redis_key, total_items, processed)

    # Return aggregated results
    return _aggregate_results(processed_symbols, success_list, failed_list, total_batches)
