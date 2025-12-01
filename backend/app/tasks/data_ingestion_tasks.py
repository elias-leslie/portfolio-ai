"""Celery tasks for data ingestion.

This module defines background tasks for ingesting market data (OHLCV, fundamentals, etc.).
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.sources.alphavantage_source import AlphaVantageSource
from app.sources.base import DatasetRequest
from app.sources.finnhub_source import FinnhubSource
from app.sources.fmp_source import FMPSource
from app.sources.multi_source_fetcher import MultiSourceFetcher
from app.sources.polygon_source import PolygonSource
from app.sources.twelvedata_source import TwelveDataSource
from app.sources.yfinance_source import YFinanceSource
from app.storage import PortfolioStorage, get_storage
from app.storage.credential_loader import load_credentials_from_database

logger = get_logger(__name__)


def _initialize_data_sources() -> list[
    YFinanceSource
    | TwelveDataSource
    | FMPSource
    | PolygonSource
    | FinnhubSource
    | AlphaVantageSource
]:
    """Initialize all available OHLCV data sources for multi-source fetching.

    Only instantiates sources that have their API keys configured.
    YFinanceSource is always included as it doesn't require an API key.

    Returns:
        List of configured data source instances in priority order
    """
    # Load API credentials from database into environment variables
    # This ensures Celery workers have access to API keys stored in source_credentials table
    load_credentials_from_database()

    sources: list[
        YFinanceSource
        | TwelveDataSource
        | FMPSource
        | PolygonSource
        | FinnhubSource
        | AlphaVantageSource
    ] = []

    # YFinanceSource doesn't require API key - always available
    sources.append(YFinanceSource())

    # Try to initialize other sources - skip if API key missing
    source_classes = [
        TwelveDataSource,
        FMPSource,
        PolygonSource,
        FinnhubSource,
        AlphaVantageSource,
    ]

    for source_class in source_classes:
        try:
            source = source_class()
            sources.append(source)
            logger.debug(f"data_source_initialized source={source_class.__name__}")
        except (RuntimeError, ValueError) as e:
            # API key not configured - skip this source
            logger.info(
                "data_source_skipped",
                source=source_class.__name__,
                reason=str(e),
            )

    logger.info(
        "data_sources_initialized",
        sources=[type(s).__name__ for s in sources],
        count=len(sources),
    )

    return sources


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
        Tuple of (prepared_df, unique_tickers)

    Raises:
        ValueError: If required columns are missing
    """
    # Ensure required columns exist
    required_cols = ["ticker", "date", "open", "high", "low", "close", "volume", "source"]
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
    # Table expects: ticker, date, open, high, low, close, volume, vwap, source, ingest_run_id
    column_order = [
        "ticker",
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

    # Get unique tickers for database cleanup
    unique_tickers = result_df["ticker"].unique().to_list()

    return result_df, unique_tickers


def _fetch_ohlcv_data(
    fetcher: MultiSourceFetcher,
    request: DatasetRequest,
    ingest_run_id: str,
) -> tuple[Any, int, dict[str, Any]]:
    """Fetch OHLCV data using multi-source fetcher.

    Args:
        fetcher: Multi-source fetcher instance
        request: Dataset request with tickers and date range
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
    # Prepare DataFrame and get unique tickers
    result_df, unique_tickers = _prepare_dataframe(result_df, ingest_run_id)

    # Log insertion start
    logger.info(
        "ingest_upserting_data",
        ingest_run_id=ingest_run_id,
        rows=len(result_df),
        tickers=unique_tickers,
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
    tickers: list[str],
    rows_inserted: int,
    error_count: int,
    start_time: dt.datetime,
) -> dict[str, int | str | float]:
    """Build result dictionary for ingestion task.

    Args:
        task_id: Celery task ID
        ingest_run_id: Unique ID for this ingestion run
        tickers: List of tickers processed
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
        "tickers_count": len(tickers),
        "rows_inserted": rows_inserted,
        "duration_seconds": duration,
        "errors": error_count,
    }

    logger.info("ingest_historical_ohlcv_completed", **result)

    return result


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
    self, tickers: list[str] | None = None
) -> dict[str, int | str | float]:
    """Refresh latest OHLCV data for critical tickers (SPY by default).

    Fetches the most recent 5 trading days to ensure fresh data,
    scheduled to run daily to keep day_bars table current.

    Args:
        tickers: List of ticker symbols (default: ["SPY"])

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - ingest_run_id: Unique ID for this ingestion run
        - tickers_count: Number of tickers processed
        - rows_inserted: Total rows inserted into day_bars table
        - errors: Number of tickers that failed to fetch

    Example:
        >>> refresh_daily_ohlcv.delay()  # Refreshes SPY
        >>> refresh_daily_ohlcv.delay(["SPY", "QQQ", "IWM"])  # Custom list
    """
    if tickers is None:
        tickers = ["SPY"]  # Default to SPY for Fear & Greed calculations

    task_id = self.request.id

    logger.info(
        "refresh_daily_ohlcv_started",
        task_id=task_id,
        tickers=tickers,
    )

    try:
        # Fetch last 5 trading days to ensure we have the latest data
        # (accounts for holidays, weekends, and delayed data feeds)
        # Call the implementation function directly (not as a task) to avoid Celery's
        # synchronous subtask prohibition. This runs within the refresh_daily_ohlcv task context.
        result = _ingest_historical_ohlcv_impl(tickers, days=5, task_id=task_id)
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
    """Refresh latest OHLCV data for all watchlist tickers.

    Fetches the most recent 5 trading days to ensure fresh data.
    Uses UPSERT to preserve existing historical data while updating recent bars.
    Scheduled to run daily at 02:15 UTC (after refresh-daily-ohlcv).

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - ingest_run_id: Unique ID for this ingestion run
        - tickers_count: Number of tickers processed
        - rows_inserted: Total rows upserted into day_bars table
        - errors: Number of tickers that failed to fetch

    Example:
        >>> refresh_watchlist_ohlcv.delay()  # Refreshes all watchlist tickers
    """
    task_id = self.request.id
    ingest_run_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)

    try:
        # Get all watchlist tickers from database
        storage = get_storage()
        with storage.connection() as conn:
            result = conn.execute(
                "SELECT DISTINCT symbol FROM watchlist_items ORDER BY symbol"
            ).fetchall()
            tickers = [str(row[0]) for row in result if row[0] is not None]

        if not tickers:
            logger.info(
                "refresh_watchlist_ohlcv_no_tickers",
                task_id=task_id,
            )
            return {
                "task_id": task_id,
                "ingest_run_id": ingest_run_id,
                "tickers_count": 0,
                "rows_inserted": 0,
                "errors": 0,
            }

        logger.info(
            "refresh_watchlist_ohlcv_started",
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            tickers=tickers,
            tickers_count=len(tickers),
        )

        # Initialize all available sources
        sources = _initialize_data_sources()

        # Create multi-source fetcher with priority-based failover
        fetcher = MultiSourceFetcher(sources, storage)

        # Calculate date range (last 5 trading days)
        start_date, end_date = _calculate_date_range(days=5)

        # Create dataset request
        request = DatasetRequest(
            dataset="day",
            profile=None,
            tickers=tickers,
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
            result_df, _unique_tickers = _prepare_dataframe(result_df, ingest_run_id)

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
            "tickers_count": len(tickers),
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


def _ingest_historical_ohlcv_impl(
    tickers: list[str], days: int = 252, task_id: str | None = None
) -> dict[str, int | str | float]:
    """Implementation of OHLCV ingestion logic (shared by task and direct calls).

    This is the actual implementation that can be called both from the Celery task
    and directly from other tasks (like refresh_daily_ohlcv).

    Args:
        tickers: List of ticker symbols to fetch data for
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
        tickers_count=len(tickers),
        days=days,
    )

    try:
        storage = get_storage()

        # Initialize all available sources
        sources = _initialize_data_sources()

        # Create multi-source fetcher with priority-based failover
        fetcher = MultiSourceFetcher(sources, storage)

        # Calculate date range (lookback from today)
        start_date, end_date = _calculate_date_range(days)

        # Create dataset request
        request = DatasetRequest(
            dataset="day",
            profile=None,
            tickers=tickers,
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
            tickers=tickers,
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
    name="ingest_historical_ohlcv",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)  # type: ignore[misc]
def ingest_historical_ohlcv(  # type: ignore[no-untyped-def]
    self, tickers: list[str], days: int = 252
) -> dict[str, int | str | float]:
    """Backfill historical OHLCV data using multi-source fetcher.

    Fetches historical daily bars for the specified tickers and lookback period,
    storing results in the day_bars table with source lineage tracking.

    Args:
        tickers: List of ticker symbols to fetch data for
        days: Number of trading days to backfill (default: 252 = ~1 year)

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - ingest_run_id: Unique ID for this ingestion run
        - tickers_count: Number of tickers processed
        - rows_inserted: Total rows inserted into day_bars table
        - duration_seconds: Total execution time
        - errors: Number of tickers that failed to fetch

    Example:
        >>> ingest_historical_ohlcv.delay(["AAPL", "MSFT", "GOOGL"], days=252)
        >>> # Backfills 252 days of OHLCV data for 3 tickers
    """
    return _ingest_historical_ohlcv_impl(tickers, days, self.request.id)


@celery_app.task(
    bind=True,
    name="update_portfolio_covariance",
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)  # type: ignore[misc]
def update_portfolio_covariance(  # type: ignore[no-untyped-def]
    self,
    tickers: list[str] | None = None,
    lookback_days: int = 252,
) -> dict[str, int | str]:
    """Update portfolio covariance matrix for proper risk calculation (GAP-020).

    Calculates pairwise covariance matrix from historical returns in day_bars.
    Uses the formula: sigma_portfolio = sqrt(w' * Cov * w)

    Args:
        tickers: Optional list of tickers. If None, uses all watchlist + portfolio tickers.
        lookback_days: Number of trading days for calculation (default: 252 = 1 year)

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - tickers_count: Number of unique tickers processed
        - pairs_updated: Number of covariance pairs calculated
        - status: 'success' or 'error'

    Example:
        >>> update_portfolio_covariance.delay()  # Updates all watchlist/portfolio tickers
        >>> update_portfolio_covariance.delay(["AAPL", "MSFT", "GOOGL"])  # Custom list
    """
    from app.analytics.covariance import update_covariance_matrix  # noqa: PLC0415

    task_id = self.request.id
    logger.info(
        "update_portfolio_covariance_started",
        task_id=task_id,
        tickers=tickers,
        lookback_days=lookback_days,
    )

    try:
        storage = get_storage()

        # If no tickers specified, get all watchlist + portfolio tickers
        if tickers is None:
            # Get watchlist tickers
            watchlist_result = storage.query(
                "SELECT DISTINCT ticker FROM watchlist_items"
            )
            watchlist_tickers = (
                watchlist_result.get_column("ticker").to_list()
                if not watchlist_result.is_empty()
                else []
            )

            # Get portfolio tickers
            portfolio_result = storage.query(
                "SELECT DISTINCT ticker FROM portfolio_positions"
            )
            portfolio_tickers = (
                portfolio_result.get_column("ticker").to_list()
                if not portfolio_result.is_empty()
                else []
            )

            # Combine and deduplicate
            all_tickers = list(set(watchlist_tickers + portfolio_tickers))
            tickers = all_tickers if all_tickers else ["SPY"]

        # Update covariance matrix
        pairs_updated = update_covariance_matrix(storage, tickers, lookback_days)

        logger.info(
            "update_portfolio_covariance_completed",
            task_id=task_id,
            tickers_count=len(tickers),
            pairs_updated=pairs_updated,
        )

        return {
            "task_id": str(task_id),
            "tickers_count": len(tickers),
            "pairs_updated": pairs_updated,
            "status": "success",
        }

    except Exception as e:
        logger.error(
            "update_portfolio_covariance_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
