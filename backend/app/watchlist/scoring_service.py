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


def _load_watchlist_items(storage: PortfolioStorage, account_id: str | None) -> pl.DataFrame:
    """Load watchlist items from database."""
    params: list[Any] = []
    sql = """
        SELECT id, account_id, symbol
        FROM watchlist_items
    """
    if account_id:
        sql += " WHERE account_id = ?"
        params.append(account_id)
    return storage.query(sql, params)


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


def _load_default_weights(storage: PortfolioStorage) -> ScoreWeights:
    """Load score weights from user preferences."""
    df = storage.query(
        """
        SELECT watchlist_price_weight, watchlist_technical_weight
        FROM user_preferences
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    if df.is_empty():
        return ScoreWeights()

    row = df.to_dicts()[0]
    return ScoreWeights(
        price=row.get("watchlist_price_weight", 50.0) or 0.0,
        technical=row.get("watchlist_technical_weight", 50.0) or 0.0,
    )


def _load_stale_ttl_minutes(storage: PortfolioStorage) -> int:
    """Load stale TTL from preferences (3x refresh interval).

    Priority: watchlist_refresh_override → default_refresh_minutes → fallback (15min)
    """
    df = storage.query(
        """
        SELECT watchlist_refresh_override, default_refresh_minutes
        FROM user_preferences
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    if df.is_empty():
        return 45  # Default: 3x 15min refresh = 45min

    row = df.to_dicts()[0]

    # Use override if set, otherwise use default, otherwise fallback to 15
    refresh_override = row.get("watchlist_refresh_override")
    default_refresh = row.get("default_refresh_minutes", 15)

    if refresh_override is not None:
        refresh_minutes = int(refresh_override)
    else:
        refresh_minutes = int(default_refresh) if default_refresh is not None else 15

    return int(refresh_minutes * 3)  # Stale = 3x refresh interval


def _load_risk_budget(storage: PortfolioStorage) -> float:
    """Load risk budget from user preferences.

    Returns the amount a user is willing to risk per trade for position sizing.

    Returns:
        Risk budget in dollars (default: $500)
    """
    df = storage.query(
        """
        SELECT watchlist_risk_budget
        FROM user_preferences
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    if df.is_empty():
        return 500.0  # Default risk budget

    row = df.to_dicts()[0]
    risk_budget = row.get("watchlist_risk_budget", 500)
    return float(risk_budget) if risk_budget is not None else 500.0


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
    items_df = _load_watchlist_items(storage, account_id)
    if items_df.is_empty():
        logger.info("watchlist_refresh_no_items", account_id=account_id)
        return {"processed": 0, "symbols": [], "batches": 0}

    symbols = sorted(set(items_df["symbol"]))
    total_items = len(items_df)

    # AUTO-BACKFILL: Check for missing or stale historical data
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

    # Initialize refresh status in Redis
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

    fetcher = price_fetcher or PriceDataFetcher(storage)
    load_credentials_from_database()
    news_service = NewsService(storage)
    news_service.refresh_ttl_from_preferences()
    news_max_articles = news_service.refresh_max_articles_from_preferences()
    technical_map = _load_latest_technical(storage, symbols)
    default_weights = _load_default_weights(storage)
    stale_ttl_minutes = _load_stale_ttl_minutes(storage)
    risk_budget = _load_risk_budget(storage)

    # Batch symbols to respect API rate limits
    symbol_batches = [symbols[i : i + batch_size] for i in range(0, len(symbols), batch_size)]
    total_batches = len(symbol_batches)

    logger.info(
        "watchlist_refresh_batching",
        total_symbols=len(symbols),
        batch_size=batch_size,
        total_batches=total_batches,
        delay_seconds=batch_delay_seconds,
    )

    # Fetch price data in batches with delays
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

    processed = 0
    now = datetime.now(UTC)
    processed_symbols: list[str] = []
    success_list: list[str] = []
    failed_list: list[dict[str, str]] = []

    for row in items_df.iter_rows(named=True):
        symbol = row["symbol"]
        item_id = row["id"]

        # Update refresh status for current symbol
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

        # Process ticker
        try:
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
                continue

            # Process ticker and generate snapshot (extracted to refresh_processor.py)
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
            )

            storage.query_mgr.upsert_watchlist_snapshot(**snapshot.to_upsert_params())
            processed += 1
            processed_symbols.append(symbol)
            success_list.append(symbol)

        except Exception as e:
            # Log error and continue processing remaining tickers
            logger.warning(
                "watchlist_refresh_ticker_failed",
                symbol=symbol,
                item_id=item_id,
                error=str(e),
            )
            failed_list.append({"symbol": symbol, "reason": str(e)})

    logger.info(
        "watchlist_refresh_completed",
        processed=processed,
        symbols=processed_symbols,
        batches=total_batches,
        success_count=len(success_list),
        failed_count=len(failed_list),
    )

    # Update refresh status to completed
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

    return {
        "processed": processed,
        "symbols": processed_symbols,
        "batches": total_batches,
        "success_count": len(success_list),
        "failed_count": len(failed_list),
        "success": success_list,
        "failed": failed_list,
    }
