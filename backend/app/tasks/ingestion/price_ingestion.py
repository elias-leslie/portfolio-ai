"""Celery tasks for OHLCV price data ingestion.

This module defines background tasks for ingesting historical and daily OHLCV data.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.sources import initialize_data_sources
from app.sources.base import DatasetRequest
from app.sources.multi_source_fetcher import MultiSourceFetcher
from app.storage import PortfolioStorage, get_storage
from app.storage.credential_loader import load_credentials_from_database
from app.utils.task_locks import generate_task_lock_key, task_lock

logger = get_logger(__name__)


def _initialize_data_sources_with_credentials() -> list[Any]:
    """Initialize data sources after loading credentials from database.

    This wrapper ensures Celery workers have access to API keys stored in
    source_credentials table before initializing the sources.

    Returns:
        List of configured data source instances in priority order
    """
    # Load API credentials from database into environment variables
    load_credentials_from_database()

    return initialize_data_sources()


def _calculate_date_range(days: int) -> tuple[dt.date, dt.date]:
    """Calculate start and end dates for historical data fetch.

    Args:
        days: Number of trading days to backfill

    Returns:
        Tuple of (start_date, end_date) for data request
    """
    end_date = dt.date.today()
    # Add extra days to account for weekends/holidays (252 trading days ≈ 365 calendar days)
    calendar_days = int(days * 1.5)
    start_date = end_date - dt.timedelta(days=calendar_days)
    return start_date, end_date


def _prepare_dataframe(result_df: Any, ingest_run_id: str) -> tuple[Any, list[str]]:
    """Prepare and validate DataFrame for insertion into day_bars table.

    Args:
        result_df: Raw DataFrame from data sources
        ingest_run_id: Unique ID for this ingestion run

    Returns:
        Tuple of (prepared_df, unique_symbols)

    Raises:
        ValueError: If required columns are missing
    """
    # Ensure required columns exist
    required_cols = ["symbol", "date", "open", "high", "low", "close", "volume", "source"]
    missing_cols = [col for col in required_cols if col not in result_df.columns]
    if missing_cols:
        logger.error(
            "ingest_missing_columns",
            ingest_run_id=ingest_run_id,
            missing_cols=missing_cols,
        )
        raise ValueError(f"Result DataFrame missing required columns: {missing_cols}")

    # Add vwap column if not present (optional field)
    if "vwap" not in result_df.columns:
        result_df = result_df.with_columns(vwap=None)

    # Add ingest_run_id column
    if "ingest_run_id" not in result_df.columns:
        result_df = result_df.with_columns(ingest_run_id=ingest_run_id)

    # Reorder columns to match day_bars table schema
    # Table expects: symbol, date, open, high, low, close, volume, vwap, source, ingest_run_id
    column_order = [
        "symbol",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
        "source",
        "ingest_run_id",
    ]
    result_df = result_df.select(column_order)

    # Get unique symbols for database cleanup
    unique_symbols = result_df["symbol"].unique().to_list()

    return result_df, unique_symbols


def _fetch_ohlcv_data(
    fetcher: MultiSourceFetcher,
    request: DatasetRequest,
    ingest_run_id: str,
) -> tuple[Any, int, dict[str, Any]]:
    """Fetch OHLCV data using multi-source fetcher.

    Args:
        fetcher: Multi-source fetcher instance
        request: Dataset request with symbols and date range
        ingest_run_id: Unique ID for this ingestion run

    Returns:
        Tuple of (result_df, error_count, errors_dict)
    """
    logger.info(
        "ingest_fetching_data",
        ingest_run_id=ingest_run_id,
        start_date=str(request.start),
        end_date=str(request.end),
    )

    result_df, errors = fetcher.fetch_with_fallback(request, verbose=True)
    error_count = len([e for e in errors.values() if e])

    return result_df, error_count, errors


def _insert_ohlcv_data(storage: PortfolioStorage, result_df: Any, ingest_run_id: str) -> int:
    """Insert OHLCV data into day_bars table using UPSERT.

    Uses UPSERT (ON CONFLICT DO UPDATE) to:
    1. Prevent deadlocks from concurrent tasks
    2. Preserve existing historical data
    3. Update only the rows that changed

    Args:
        storage: Storage instance for database operations
        result_df: Prepared DataFrame to insert
        ingest_run_id: Unique ID for this ingestion run

    Returns:
        Number of rows upserted
    """
    # Prepare DataFrame and get unique symbols
    result_df, unique_symbols = _prepare_dataframe(result_df, ingest_run_id)

    # Log insertion start
    logger.info(
        "ingest_upserting_data",
        ingest_run_id=ingest_run_id,
        rows=len(result_df),
        symbols=unique_symbols,
    )

    # Use UPSERT mode to prevent deadlocks and preserve historical data
    # This replaces DELETE + INSERT pattern which caused PostgreSQL deadlocks
    # when multiple tasks ran concurrently
    storage.insert_dataframe("day_bars", result_df, mode="upsert")
    rows_upserted = len(result_df)

    # Log insertion completion
    logger.info(
        "ingest_data_upserted",
        ingest_run_id=ingest_run_id,
        rows_upserted=rows_upserted,
    )

    return rows_upserted


def _build_ingestion_result(
    task_id: str,
    ingest_run_id: str,
    symbols: list[str],
    rows_inserted: int,
    error_count: int,
    start_time: dt.datetime,
) -> dict[str, int | str | float]:
    """Build result dictionary for ingestion task.

    Args:
        task_id: Celery task ID
        ingest_run_id: Unique ID for this ingestion run
        symbols: List of symbols processed
        rows_inserted: Number of rows inserted
        error_count: Number of errors encountered
        start_time: Task start time

    Returns:
        Dict with task results
    """
    end_time = dt.datetime.now(dt.UTC)
    duration = (end_time - start_time).total_seconds()

    result: dict[str, int | str | float] = {
        "task_id": task_id,
        "ingest_run_id": ingest_run_id,
        "symbols_count": len(symbols),
        "rows_inserted": rows_inserted,
        "duration_seconds": duration,
        "errors": error_count,
    }

    logger.info("ingest_historical_ohlcv_completed", **result)

    return result


def _ingest_historical_ohlcv_impl(
    symbols: list[str], days: int = 252, task_id: str | None = None
) -> dict[str, int | str | float]:
    """Implementation of OHLCV ingestion logic (shared by task and direct calls).

    This is the actual implementation that can be called both from the Celery task
    and directly from other tasks (like refresh_daily_ohlcv).

    Args:
        symbols: List of symbols to fetch data for
        days: Number of trading days to backfill (default: 252 = ~1 year)
        task_id: Optional Celery task ID (for logging)

    Returns:
        Dict with ingestion results
    """
    ingest_run_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)

    logger.info(
        "ingest_historical_ohlcv_started",
        task_id=task_id,
        ingest_run_id=ingest_run_id,
        symbols_count=len(symbols),
        days=days,
    )

    try:
        storage = get_storage()

        # Initialize all available sources
        sources = _initialize_data_sources_with_credentials()

        # Create multi-source fetcher with priority-based failover
        fetcher = MultiSourceFetcher(sources, storage)

        # Calculate date range (lookback from today)
        start_date, end_date = _calculate_date_range(days)

        # Create dataset request
        request = DatasetRequest(
            dataset="day",
            profile=None,
            symbols=symbols,
            start=start_date,
            end=end_date,
            timezone="UTC",
            ingest_run_id=ingest_run_id,
        )

        # Fetch data with multi-source failover
        result_df, error_count, errors = _fetch_ohlcv_data(fetcher, request, ingest_run_id)

        # Insert data into day_bars table
        rows_inserted = 0
        if result_df is not None and len(result_df) > 0:
            rows_inserted = _insert_ohlcv_data(storage, result_df, ingest_run_id)
        else:
            logger.warning(
                "ingest_no_data_fetched",
                ingest_run_id=ingest_run_id,
                errors=errors,
            )

        # Build and return result
        return _build_ingestion_result(
            task_id=task_id or "direct",
            ingest_run_id=ingest_run_id,
            symbols=symbols,
            rows_inserted=rows_inserted,
            error_count=error_count,
            start_time=start_time,
        )

    except Exception as e:
        logger.error(
            "ingest_historical_ohlcv_failed",
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


@celery_app.task(
    bind=True,
    name="refresh_daily_ohlcv",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)  # type: ignore[misc]
def refresh_daily_ohlcv(  # type: ignore[no-untyped-def]
    self, symbols: list[str] | None = None
) -> dict[str, int | str | float]:
    """Refresh latest OHLCV data for critical symbols (SPY by default).

    Fetches the most recent 5 trading days to ensure fresh data,
    scheduled to run daily to keep day_bars table current.

    Args:
        symbols: List of symbols (default: ["SPY"])

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - ingest_run_id: Unique ID for this ingestion run
        - symbols_count: Number of symbols processed
        - rows_inserted: Total rows inserted into day_bars table
        - errors: Number of symbols that failed to fetch

    Example:
        >>> refresh_daily_ohlcv.delay()  # Refreshes SPY
        >>> refresh_daily_ohlcv.delay(["SPY", "QQQ", "IWM"])  # Custom list
    """
    if symbols is None:
        symbols = ["SPY"]  # Default to SPY for Fear & Greed calculations

    task_id = self.request.id

    logger.info(
        "refresh_daily_ohlcv_started",
        task_id=task_id,
        symbols=symbols,
    )

    try:
        # Fetch last 5 trading days to ensure we have the latest data
        # (accounts for holidays, weekends, and delayed data feeds)
        # Call the implementation function directly (not as a task) to avoid Celery's
        # synchronous subtask prohibition. This runs within the refresh_daily_ohlcv task context.
        result = _ingest_historical_ohlcv_impl(symbols, days=5, task_id=task_id)
        return result

    except Exception as e:
        logger.error(
            "refresh_daily_ohlcv_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


@celery_app.task(
    bind=True,
    name="refresh_watchlist_ohlcv",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)  # type: ignore[misc]
def refresh_watchlist_ohlcv(  # type: ignore[no-untyped-def]
    self,
) -> dict[str, int | str | float]:
    """Refresh latest OHLCV data for all watchlist symbols.

    Fetches the most recent 5 trading days to ensure fresh data.
    Uses UPSERT to preserve existing historical data while updating recent bars.
    Scheduled to run daily at 02:15 UTC (after refresh-daily-ohlcv).

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - ingest_run_id: Unique ID for this ingestion run
        - symbols_count: Number of symbols processed
        - rows_inserted: Total rows upserted into day_bars table
        - errors: Number of symbols that failed to fetch

    Example:
        >>> refresh_watchlist_ohlcv.delay()  # Refreshes all watchlist symbols
    """
    task_id = self.request.id
    ingest_run_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)

    try:
        # Get all watchlist symbols from database
        storage = get_storage()
        with storage.connection() as conn:
            result = conn.execute(
                "SELECT DISTINCT symbol FROM watchlist_items ORDER BY symbol"
            ).fetchall()
            symbols = [str(row[0]) for row in result if row[0] is not None]

        if not symbols:
            logger.info(
                "refresh_watchlist_ohlcv_no_symbols",
                task_id=task_id,
            )
            return {
                "task_id": task_id,
                "ingest_run_id": ingest_run_id,
                "symbols_count": 0,
                "rows_inserted": 0,
                "errors": 0,
            }

        logger.info(
            "refresh_watchlist_ohlcv_started",
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            symbols=symbols,
            symbols_count=len(symbols),
        )

        # Initialize all available sources
        sources = _initialize_data_sources_with_credentials()

        # Create multi-source fetcher with priority-based failover
        fetcher = MultiSourceFetcher(sources, storage)

        # Calculate date range (last 5 trading days)
        start_date, end_date = _calculate_date_range(days=5)

        # Create dataset request
        request = DatasetRequest(
            dataset="day",
            profile=None,
            symbols=symbols,
            start=start_date,
            end=end_date,
            timezone="UTC",
            ingest_run_id=ingest_run_id,
        )

        # Fetch data with multi-source failover
        result_df, error_count, errors = _fetch_ohlcv_data(fetcher, request, ingest_run_id)

        # UPSERT data into day_bars table (preserves existing historical data)
        rows_inserted = 0
        if result_df is not None and len(result_df) > 0:
            # Prepare DataFrame (add ingest_run_id, vwap, etc.)
            result_df, _unique_symbols = _prepare_dataframe(result_df, ingest_run_id)

            logger.info(
                "refresh_watchlist_ohlcv_upserting",
                ingest_run_id=ingest_run_id,
                rows=len(result_df),
            )

            # Use UPSERT mode instead of deleting existing data
            # This preserves historical bars while updating recent days
            storage.insert_dataframe("day_bars", result_df, mode="upsert")
            rows_inserted = len(result_df)

            logger.info(
                "refresh_watchlist_ohlcv_data_upserted",
                ingest_run_id=ingest_run_id,
                rows_upserted=rows_inserted,
            )
        else:
            logger.warning(
                "refresh_watchlist_ohlcv_no_data_fetched",
                ingest_run_id=ingest_run_id,
                errors=errors,
            )

        # Build and return result
        end_time = dt.datetime.now(dt.UTC)
        duration = (end_time - start_time).total_seconds()

        result_dict: dict[str, int | str | float] = {
            "task_id": task_id,
            "ingest_run_id": ingest_run_id,
            "symbols_count": len(symbols),
            "rows_inserted": rows_inserted,
            "duration_seconds": duration,
            "errors": error_count,
        }

        logger.info("refresh_watchlist_ohlcv_completed", **result_dict)

        return result_dict

    except Exception as e:
        logger.error(
            "refresh_watchlist_ohlcv_failed",
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


@celery_app.task(
    bind=True,
    name="ingest_historical_ohlcv",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)  # type: ignore[misc]
def ingest_historical_ohlcv(  # type: ignore[no-untyped-def]
    self, symbols: list[str], days: int = 252
) -> dict[str, int | str | float]:
    """Backfill historical OHLCV data using multi-source fetcher.

    Fetches historical daily bars for the specified symbols and lookback period,
    storing results in the day_bars table with source lineage tracking.

    Uses Redis-based task lock to prevent duplicate concurrent executions
    for the same symbol set.

    Args:
        symbols: List of symbols to fetch data for
        days: Number of trading days to backfill (default: 252 = ~1 year)

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - ingest_run_id: Unique ID for this ingestion run
        - symbols_count: Number of symbols processed
        - rows_inserted: Total rows inserted into day_bars table
        - duration_seconds: Total execution time
        - errors: Number of symbols that failed to fetch
        - skipped: True if task was skipped due to duplicate lock

    Example:
        >>> ingest_historical_ohlcv.delay(["AAPL", "MSFT", "GOOGL"], days=252)
        >>> # Backfills 252 days of OHLCV data for 3 symbols
    """
    # Use task lock to prevent duplicate concurrent executions
    # Lock key includes sorted symbols and days for deduplication
    lock_key = generate_task_lock_key("ingest_historical_ohlcv", symbols, days)

    with task_lock(lock_key, ttl=600) as acquired:  # 10-minute lock (matches task_time_limit)
        if not acquired:
            logger.info(
                "ingest_historical_ohlcv_skipped_duplicate",
                task_id=self.request.id,
                symbols=symbols,
                days=days,
                reason="duplicate_task_running",
            )
            return {
                "task_id": self.request.id,
                "skipped": True,
                "reason": "duplicate_task_running",
                "symbols_count": len(symbols),
            }

        return _ingest_historical_ohlcv_impl(symbols, days, self.request.id)
