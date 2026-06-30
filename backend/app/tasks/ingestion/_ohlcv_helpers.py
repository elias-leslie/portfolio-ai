"""Private helper functions for OHLCV price data ingestion.

This module contains internal helpers used by price_ingestion.py.
Not part of the public API — import from price_ingestion instead.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

import polars as pl

from app.logging_config import get_logger
from app.sources import initialize_data_sources
from app.sources.base import DATASET_DAY, DatasetRequest
from app.sources.multi_source_fetcher import MultiSourceFetcher
from app.storage import PortfolioStorage, get_storage
from app.storage.credential_loader import load_credentials_from_database
from app.utils.db_helpers import ensure_symbols_exist
from app.utils.market_hours import get_expected_data_date, is_trading_day

# Used by callers that import the watchlist helpers
__all__ = [
    "build_fetcher",
    "build_ingestion_result",
    "calculate_date_range",
    "empty_result",
    "fetch_ohlcv_data",
    "initialize_sources_with_credentials",
    "insert_ohlcv_data",
    "load_watchlist_symbols",
    "prepare_dataframe",
    "run_ingestion_pipeline",
    "run_watchlist_pipeline",
    "upsert_watchlist_data",
]

logger = get_logger(__name__)

# Column order expected by the day_bars table schema
_DAY_BARS_COLUMNS = [
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

_REQUIRED_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume", "source"]

_VWAP_SOURCE_NAMES = {"fmp", "polygon"}


def initialize_sources_with_credentials() -> list[Any]:
    """Load credentials from database then initialize data sources.

    Returns:
        List of configured data source instances in priority order.
    """
    load_credentials_from_database()
    return initialize_data_sources()


def calculate_date_range(days: int) -> tuple[dt.date, dt.date]:
    """Calculate start and end dates for a historical data fetch.

    Args:
        days: Number of trading days to backfill.

    Returns:
        Tuple of (start_date, end_date).
    """
    end_date = get_expected_data_date(dt.datetime.now(dt.UTC))
    # Extra buffer to account for weekends/holidays
    calendar_days = int(days * 1.5)
    start_date = end_date - dt.timedelta(days=calendar_days)
    return start_date, end_date


def _completed_trading_dates(dates: list[dt.date], max_date: dt.date) -> list[dt.date]:
    return sorted({value for value in dates if value <= max_date and is_trading_day(value)})


def filter_completed_trading_rows(result_df: pl.DataFrame, ingest_run_id: str) -> pl.DataFrame:
    """Keep only rows for completed US trading days.

    Some upstream daily feeds can emit weekend rows for cross-asset proxies or
    current-session partial rows before the US market closes. Downstream
    analytics treat `day_bars` as completed market-session bars, so reject those
    rows at ingestion.
    """
    if "date" not in result_df.columns or result_df.is_empty():
        return result_df

    normalized_df = result_df.with_columns(pl.col("date").cast(pl.Date, strict=False))
    max_date = get_expected_data_date(dt.datetime.now(dt.UTC))
    raw_dates = normalized_df.select(pl.col("date").drop_nulls().unique()).to_series().to_list()
    allowed_dates = _completed_trading_dates(
        [value for value in raw_dates if isinstance(value, dt.date)],
        max_date,
    )
    filtered_df = normalized_df.filter(pl.col("date").is_in(allowed_dates))
    dropped_rows = len(normalized_df) - len(filtered_df)
    if dropped_rows > 0:
        logger.info(
            "ohlcv_incomplete_or_non_trading_rows_dropped",
            ingest_run_id=ingest_run_id,
            dropped_rows=dropped_rows,
            max_completed_trading_date=str(max_date),
        )
    return filtered_df


def prepare_dataframe(result_df: Any, ingest_run_id: str) -> tuple[Any, list[str]]:
    """Validate and prepare a DataFrame for insertion into day_bars.

    Args:
        result_df: Raw DataFrame from data sources.
        ingest_run_id: Unique ID for this ingestion run.

    Returns:
        Tuple of (prepared_df, unique_symbols).

    Raises:
        ValueError: If required columns are missing.
    """
    missing_cols = [c for c in _REQUIRED_COLUMNS if c not in result_df.columns]
    if missing_cols:
        logger.error(
            "ingest_missing_columns",
            ingest_run_id=ingest_run_id,
            missing_cols=missing_cols,
        )
        raise ValueError(f"Result DataFrame missing required columns: {missing_cols}")

    if "vwap" not in result_df.columns:
        result_df = result_df.with_columns(pl.lit(None).alias("vwap"))

    if "ingest_run_id" not in result_df.columns:
        result_df = result_df.with_columns(pl.lit(ingest_run_id).alias("ingest_run_id"))

    result_df = filter_completed_trading_rows(result_df, ingest_run_id)
    result_df = result_df.select(_DAY_BARS_COLUMNS)
    unique_symbols: list[str] = result_df["symbol"].unique().to_list()
    return result_df, unique_symbols


def _usable_vwap_rows(result_df: Any) -> pl.DataFrame | None:
    """Return rows with a finite positive vendor VWAP."""
    if result_df is None or len(result_df) == 0 or "vwap" not in result_df.columns:
        return None
    with_vwap = result_df.with_columns(
        pl.col("vwap").cast(pl.Float64, strict=False).alias("vwap")
    ).filter(pl.col("vwap").is_not_null() & pl.col("vwap").is_finite() & (pl.col("vwap") > 0))
    return with_vwap if len(with_vwap) > 0 else None


def fetch_ohlcv_data(
    fetcher: MultiSourceFetcher,
    request: DatasetRequest,
    ingest_run_id: str,
) -> tuple[Any, int, dict[str, Any]]:
    """Fetch OHLCV data using the multi-source fetcher.

    Args:
        fetcher: Multi-source fetcher instance.
        request: Dataset request with symbols and date range.
        ingest_run_id: Unique ID for this ingestion run.

    Returns:
        Tuple of (result_df, error_count, errors_dict).
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


def insert_ohlcv_data(storage: PortfolioStorage, result_df: Any, ingest_run_id: str) -> int:
    """Insert OHLCV data into day_bars using UPSERT.

    Uses UPSERT (ON CONFLICT DO UPDATE) to prevent deadlocks and preserve
    existing historical data while updating only changed rows.

    Args:
        storage: Storage instance for database operations.
        result_df: Raw DataFrame to insert.
        ingest_run_id: Unique ID for this ingestion run.

    Returns:
        Number of rows upserted.
    """
    result_df, unique_symbols = prepare_dataframe(result_df, ingest_run_id)

    logger.info(
        "ingest_upserting_data",
        ingest_run_id=ingest_run_id,
        rows=len(result_df),
        symbols=unique_symbols,
    )

    with storage.connection() as conn:
        ensure_symbols_exist(conn, unique_symbols)
        conn.commit()
    storage.insert_dataframe("day_bars", result_df, mode="upsert")
    rows_upserted = len(result_df)

    logger.info(
        "ingest_data_upserted",
        ingest_run_id=ingest_run_id,
        rows_upserted=rows_upserted,
    )
    return rows_upserted


def build_ingestion_result(
    task_id: str,
    ingest_run_id: str,
    symbols: list[str],
    rows_inserted: int,
    error_count: int,
    start_time: dt.datetime,
    log_event: str = "ingest_historical_ohlcv_completed",
) -> dict[str, int | str | float]:
    """Build a standardised result dictionary for an ingestion task.

    Args:
        task_id: Task ID.
        ingest_run_id: Unique ID for this ingestion run.
        symbols: List of symbols processed.
        rows_inserted: Number of rows inserted.
        error_count: Number of errors encountered.
        start_time: Task start time.
        log_event: Structured-log event name to emit.

    Returns:
        Dict with task results.
    """
    duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
    result: dict[str, int | str | float] = {
        "task_id": task_id,
        "ingest_run_id": ingest_run_id,
        "symbols_count": len(symbols),
        "rows_inserted": rows_inserted,
        "duration_seconds": duration,
        "errors": error_count,
    }
    logger.info(log_event, **result)
    return result


def build_fetcher(symbols: list[str]) -> tuple[MultiSourceFetcher, PortfolioStorage]:
    """Initialise storage and a multi-source fetcher ready for use.

    Args:
        symbols: Symbols that will be fetched (unused here, kept for context).

    Returns:
        Tuple of (fetcher, storage).
    """
    storage = get_storage()
    sources = initialize_sources_with_credentials()
    fetcher = MultiSourceFetcher(sources, storage)
    return fetcher, storage


# ---------------------------------------------------------------------------
# Watchlist-specific helpers
# ---------------------------------------------------------------------------


def load_watchlist_symbols(storage: PortfolioStorage, task_id: str) -> list[str]:
    """Query watchlist_items and return distinct symbols.

    Args:
        storage: PortfolioStorage instance.
        task_id: Task ID used for logging when no symbols are found.

    Returns:
        Sorted list of symbol strings (may be empty).
    """
    with storage.connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT symbol FROM watchlist_items ORDER BY symbol"
        ).fetchall()
    symbols = [str(row[0]) for row in rows if row[0] is not None]

    if not symbols:
        logger.info("refresh_watchlist_ohlcv_no_symbols", task_id=task_id)

    return symbols


def empty_result(task_id: str, ingest_run_id: str) -> dict[str, int | str | float]:
    """Return a zero-count result dict when there are no symbols to process."""
    return {
        "task_id": task_id,
        "ingest_run_id": ingest_run_id,
        "symbols_count": 0,
        "rows_inserted": 0,
        "errors": 0,
    }


def upsert_watchlist_data(
    storage: PortfolioStorage,
    result_df: Any,
    ingest_run_id: str,
    errors: dict[str, Any],
) -> int:
    """UPSERT watchlist OHLCV rows into day_bars and return the row count.

    Args:
        storage: PortfolioStorage instance.
        result_df: DataFrame returned by the fetcher (may be None).
        ingest_run_id: Unique ID for this ingestion run.
        errors: Error dict from the fetcher (used only for warning logging).

    Returns:
        Number of rows upserted (0 if no data).
    """
    if result_df is None or len(result_df) == 0:
        logger.warning(
            "refresh_watchlist_ohlcv_no_data_fetched",
            ingest_run_id=ingest_run_id,
            errors=errors,
        )
        return 0

    result_df, _ = prepare_dataframe(result_df, ingest_run_id)

    logger.info(
        "refresh_watchlist_ohlcv_upserting",
        ingest_run_id=ingest_run_id,
        rows=len(result_df),
    )

    storage.insert_dataframe("day_bars", result_df, mode="upsert")
    rows_inserted: int = len(result_df)

    logger.info(
        "refresh_watchlist_ohlcv_data_upserted",
        ingest_run_id=ingest_run_id,
        rows_upserted=rows_inserted,
    )
    return rows_inserted


def fetch_watchlist_vwap_data(
    fetcher: MultiSourceFetcher,
    request: DatasetRequest,
) -> tuple[pl.DataFrame | None, int, dict[str, list[str]]]:
    """Fetch true VWAP from VWAP-capable day-bar sources for watchlist symbols."""
    sources = [
        source
        for source in fetcher.get_sources_for_dataset(DATASET_DAY)
        if source.name in _VWAP_SOURCE_NAMES
    ]
    if not sources:
        logger.info("refresh_watchlist_vwap_no_configured_source")
        return None, 0, {}

    frames: list[pl.DataFrame] = []
    errors: dict[str, list[str]] = {}
    symbols_remaining = {str(symbol).upper() for symbol in request.symbols}
    metrics_manager = getattr(fetcher, "metrics_manager", None)

    for source in sources:
        if not symbols_remaining:
            break
        try:
            source_request = DatasetRequest(
                dataset=request.dataset,
                profile="vwap",
                symbols=sorted(symbols_remaining),
                start=request.start,
                end=request.end,
                timezone=request.timezone,
                ingest_run_id=request.ingest_run_id,
            )
            started_at = time.monotonic()
            data = source.fetch_day_bars(source_request)
            usable = _usable_vwap_rows(data)
            if usable is None:
                logger.info("refresh_watchlist_vwap_source_no_usable_rows", source=source.name)
                continue
            if metrics_manager is not None:
                metrics_manager.record_success(source.name, int((time.monotonic() - started_at) * 1000))
            frames.append(usable)
            fetched_symbols = {str(symbol).upper() for symbol in usable["symbol"].unique().to_list()}
            symbols_remaining -= fetched_symbols
            logger.info(
                "refresh_watchlist_vwap_source_fetched",
                source=source.name,
                rows=len(usable),
                symbols_fetched=len(fetched_symbols),
                symbols_remaining=len(symbols_remaining),
            )
        except Exception as e:
            errors.setdefault(source.name, []).append(str(e))
            if metrics_manager is not None:
                metrics_manager.record_failure(source.name, e)
            logger.warning(
                "refresh_watchlist_vwap_source_failed",
                source=source.name,
                error=str(e),
                error_type=type(e).__name__,
            )

    if not frames:
        return None, len(errors), errors
    return pl.concat(frames, how="diagonal_relaxed"), len(errors), errors


def upsert_watchlist_vwap_data(
    storage: PortfolioStorage,
    result_df: Any,
    ingest_run_id: str,
    errors: dict[str, Any],
) -> int:
    """UPSERT VWAP-capable vendor rows into day_bars for watchlist scanner use."""
    usable = _usable_vwap_rows(result_df)
    if usable is None:
        logger.info(
            "refresh_watchlist_vwap_no_data_fetched",
            ingest_run_id=ingest_run_id,
            errors=errors,
        )
        return 0

    prepared_df, _ = prepare_dataframe(usable, ingest_run_id)
    prepared_df = _usable_vwap_rows(prepared_df)
    if prepared_df is None:
        logger.info("refresh_watchlist_vwap_no_completed_rows", ingest_run_id=ingest_run_id)
        return 0

    storage.insert_dataframe("day_bars", prepared_df, mode="upsert")
    rows_inserted: int = len(prepared_df)
    logger.info(
        "refresh_watchlist_vwap_data_upserted",
        ingest_run_id=ingest_run_id,
        rows_upserted=rows_inserted,
    )
    return rows_inserted


def run_ingestion_pipeline(
    symbols: list[str],
    days: int,
    task_id: str | None,
    ingest_run_id: str,
    start_time: dt.datetime,
) -> dict[str, int | str | float]:
    """Core OHLCV ingestion pipeline: fetch, insert, and return results."""
    fetcher, storage = build_fetcher(symbols)
    start_date, end_date = calculate_date_range(days)
    request = DatasetRequest(
        dataset="day",
        profile=None,
        symbols=symbols,
        start=start_date,
        end=end_date,
        timezone="UTC",
        ingest_run_id=ingest_run_id,
    )
    result_df, error_count, errors = fetch_ohlcv_data(fetcher, request, ingest_run_id)
    rows_inserted = 0
    if result_df is not None and len(result_df) > 0:
        rows_inserted = insert_ohlcv_data(storage, result_df, ingest_run_id)
    else:
        logger.warning("ingest_no_data_fetched", ingest_run_id=ingest_run_id, errors=errors)
    return build_ingestion_result(
        task_id=task_id or "direct",
        ingest_run_id=ingest_run_id,
        symbols=symbols,
        rows_inserted=rows_inserted,
        error_count=error_count,
        start_time=start_time,
    )


def run_watchlist_pipeline(
    storage: PortfolioStorage,
    symbols: list[str],
    task_id: str,
    ingest_run_id: str,
    start_time: dt.datetime,
) -> dict[str, int | str | float]:
    """Core watchlist OHLCV pipeline: fetch, upsert, and return results."""
    logger.info(
        "refresh_watchlist_ohlcv_started",
        task_id=task_id,
        ingest_run_id=ingest_run_id,
        symbols=symbols,
        symbols_count=len(symbols),
    )
    fetcher, _ = build_fetcher(symbols)
    start_date, end_date = calculate_date_range(days=5)
    request = DatasetRequest(
        dataset="day",
        profile=None,
        symbols=symbols,
        start=start_date,
        end=end_date,
        timezone="UTC",
        ingest_run_id=ingest_run_id,
    )
    result_df, error_count, errors = fetch_ohlcv_data(fetcher, request, ingest_run_id)
    rows_inserted = upsert_watchlist_data(storage, result_df, ingest_run_id, errors)
    vwap_result_df, vwap_error_count, vwap_errors = fetch_watchlist_vwap_data(fetcher, request)
    vwap_rows_inserted = upsert_watchlist_vwap_data(
        storage, vwap_result_df, ingest_run_id, vwap_errors
    )
    result = build_ingestion_result(
        task_id=task_id,
        ingest_run_id=ingest_run_id,
        symbols=symbols,
        rows_inserted=rows_inserted,
        error_count=error_count + vwap_error_count,
        start_time=start_time,
        log_event="refresh_watchlist_ohlcv_completed",
    )
    result["vwap_rows_inserted"] = vwap_rows_inserted
    result["vwap_errors"] = vwap_error_count
    return result
