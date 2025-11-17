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

    Returns:
        List of configured data source instances in priority order
    """
    return [
        YFinanceSource(),
        TwelveDataSource(),
        FMPSource(),
        PolygonSource(),
        FinnhubSource(),
        AlphaVantageSource(),
    ]


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


def _delete_existing_data(storage: PortfolioStorage, tickers: list[str]) -> None:
    """Delete existing data for the specified tickers to avoid duplicates.

    Args:
        storage: Storage instance for database operations
        tickers: List of tickers to delete data for
    """
    with storage.connection() as conn:
        placeholders = ", ".join(["%s"] * len(tickers))
        conn.execute(
            f"DELETE FROM day_bars WHERE ticker IN ({placeholders})",
            tickers,
        )
        conn.commit()


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
    """Insert OHLCV data into day_bars table.

    Args:
        storage: Storage instance for database operations
        result_df: Prepared DataFrame to insert
        ingest_run_id: Unique ID for this ingestion run

    Returns:
        Number of rows inserted
    """
    # Prepare DataFrame and get unique tickers
    result_df, unique_tickers = _prepare_dataframe(result_df, ingest_run_id)

    # Log insertion start
    logger.info(
        "ingest_inserting_data",
        ingest_run_id=ingest_run_id,
        rows=len(result_df),
    )

    # Delete existing data for these tickers to avoid duplicates
    _delete_existing_data(storage, unique_tickers)

    # Insert new data (using append since we already deleted the old rows)
    storage.insert_dataframe("day_bars", result_df, mode="append")
    rows_inserted = len(result_df)

    # Log insertion completion
    logger.info(
        "ingest_data_inserted",
        ingest_run_id=ingest_run_id,
        rows_inserted=rows_inserted,
    )

    return rows_inserted


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


@celery_app.task(name="refresh_daily_ohlcv", bind=True)  # type: ignore[misc]
def refresh_daily_ohlcv(  # type: ignore[no-untyped-def]
    self, tickers: list[str] | None = None
) -> dict[str, int | str]:
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
        result: dict[str, int | str] = ingest_historical_ohlcv(self, tickers=tickers, days=5)
        return result

    except Exception as e:
        logger.error(
            "refresh_daily_ohlcv_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


@celery_app.task(name="ingest_historical_ohlcv", bind=True)  # type: ignore[misc]
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
    task_id = self.request.id
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
            task_id=task_id,
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
