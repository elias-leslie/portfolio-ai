"""Celery tasks for data ingestion.

This module defines background tasks for ingesting market data (OHLCV, fundamentals, etc.).
"""

from __future__ import annotations

import datetime as dt
import json
import uuid

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.sources.alphavantage_source import AlphaVantageSource
from app.sources.base import DatasetRequest
from app.sources.finnhub_source import FinnhubSource
from app.sources.fmp_source import FMPSource
from app.sources.fred import FREDSource
from app.sources.multi_source_fetcher import MultiSourceFetcher
from app.sources.polygon_source import PolygonSource
from app.sources.twelvedata_source import TwelveDataSource
from app.sources.yfinance_source import YFinanceSource
from app.storage import get_storage

logger = get_logger(__name__)


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
) -> dict[str, int | str]:
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
        sources = [
            YFinanceSource(),
            TwelveDataSource(),
            FMPSource(),
            PolygonSource(),
            FinnhubSource(),
            AlphaVantageSource(),
        ]

        # Create multi-source fetcher with priority-based failover
        fetcher = MultiSourceFetcher(sources, storage)

        # Calculate date range (lookback from today)
        end_date = dt.date.today()
        # Add extra days to account for weekends/holidays (252 trading days ≈ 365 calendar days)
        calendar_days = int(days * 1.5)
        start_date = end_date - dt.timedelta(days=calendar_days)

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
        logger.info(
            "ingest_fetching_data",
            ingest_run_id=ingest_run_id,
            start_date=str(start_date),
            end_date=str(end_date),
        )

        result_df, errors = fetcher.fetch_with_fallback(request, verbose=True)

        # Track errors
        error_count = len([e for e in errors.values() if e])

        # Insert data into day_bars table
        rows_inserted = 0
        if result_df is not None and len(result_df) > 0:
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
                result_df = result_df.with_columns(
                    vwap=None,
                )

            # Add ingest_run_id column
            if "ingest_run_id" not in result_df.columns:
                result_df = result_df.with_columns(
                    ingest_run_id=ingest_run_id,
                )

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

            # Insert into database: Delete only the specific (ticker, date) pairs we're updating
            # to avoid wiping ALL day_bars data (which would break concurrent backfills)
            logger.info(
                "ingest_inserting_data",
                ingest_run_id=ingest_run_id,
                rows=len(result_df),
            )

            # Get unique tickers from the result DataFrame
            unique_tickers = result_df["ticker"].unique().to_list()

            # Delete only the rows for these specific tickers
            with storage.connection() as conn:
                placeholders = ", ".join(["%s"] * len(unique_tickers))
                conn.execute(
                    f"DELETE FROM day_bars WHERE ticker IN ({placeholders})",
                    unique_tickers,
                )
                conn.commit()

            # Now insert the new data (using append since we already deleted the old rows)
            storage.insert_dataframe("day_bars", result_df, mode="append")
            rows_inserted = len(result_df)

            logger.info(
                "ingest_data_inserted",
                ingest_run_id=ingest_run_id,
                rows_inserted=rows_inserted,
            )
        else:
            logger.warning(
                "ingest_no_data_fetched",
                ingest_run_id=ingest_run_id,
                errors=errors,
            )

        # Calculate duration
        end_time = dt.datetime.now(dt.UTC)
        duration = (end_time - start_time).total_seconds()

        result = {
            "task_id": task_id,
            "ingest_run_id": ingest_run_id,
            "tickers_count": len(tickers),
            "rows_inserted": rows_inserted,
            "duration_seconds": duration,
            "errors": error_count,
        }

        logger.info(
            "ingest_historical_ohlcv_completed",
            **result,
        )

        return result

    except Exception as e:
        logger.error(
            "ingest_historical_ohlcv_failed",
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


@celery_app.task(name="backfill_fred_indicators", bind=True)  # type: ignore[misc]
def backfill_fred_indicators(  # type: ignore[no-untyped-def]
    self, days: int = 252
) -> dict[str, int | str]:
    """Backfill FRED indicators (VIX, HY Spread) for Fear & Greed Index.

    Fetches historical data from FRED API and stores in fear_greed_inputs table.
    This is a one-time backfill task to populate historical percentile windows.

    Args:
        days: Number of trading days to backfill (default: 252 = ~1 year)

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - days_requested: Number of days requested
        - vix_rows: Number of VIX data points fetched
        - hy_spread_rows: Number of HY Spread data points fetched
        - rows_inserted: Total rows inserted/updated in fear_greed_inputs
        - duration_seconds: Total execution time

    Example:
        >>> backfill_fred_indicators.delay(days=252)
        >>> # Backfills 252 days of VIX and HY Spread data
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info(
        "backfill_fred_indicators_started",
        task_id=task_id,
        days=days,
    )

    try:
        storage = get_storage()
        fred = FREDSource()

        # Calculate date range (lookback from today)
        end_date = dt.datetime.now()
        # Add extra days to account for weekends/holidays (252 trading days ≈ 365 calendar days)
        calendar_days = int(days * 1.5)
        start_date = end_date - dt.timedelta(days=calendar_days)

        logger.info(
            "backfill_fetching_fred_data",
            task_id=task_id,
            start_date=str(start_date.date()),
            end_date=str(end_date.date()),
        )

        # Fetch VIX data
        vix_data = fred.fetch("VIXCLS", start_date, end_date)
        vix_rows = len(vix_data) if vix_data else 0
        logger.info("backfill_vix_fetched", task_id=task_id, rows=vix_rows)

        # Fetch HY Spread data
        hy_data = fred.fetch("BAMLH0A0HYM2", start_date, end_date)
        hy_rows = len(hy_data) if hy_data else 0
        logger.info("backfill_hy_spread_fetched", task_id=task_id, rows=hy_rows)

        # Combine data by date
        data_by_date: dict[dt.date, dict[str, float]] = {}

        if vix_data:
            for row in vix_data:
                date = row["date"]
                if date not in data_by_date:
                    data_by_date[date] = {}
                data_by_date[date]["vix_close"] = float(row["value"])

        if hy_data:
            for row in hy_data:
                date = row["date"]
                if date not in data_by_date:
                    data_by_date[date] = {}
                data_by_date[date]["hy_spread"] = float(row["value"])

        # Insert/update data in fear_greed_inputs table
        rows_inserted = 0
        with storage.connection() as conn:
            for date, values in data_by_date.items():
                source_map = {}
                if "vix_close" in values:
                    source_map["vix"] = "FRED"
                if "hy_spread" in values:
                    source_map["hy_spread"] = "FRED"

                conn.execute(
                    """
                    INSERT INTO fear_greed_inputs
                    (as_of_date, vix_close, hy_spread, source_map)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (as_of_date)
                    DO UPDATE SET
                    vix_close = COALESCE(EXCLUDED.vix_close, fear_greed_inputs.vix_close),
                    hy_spread = COALESCE(EXCLUDED.hy_spread, fear_greed_inputs.hy_spread),
                    source_map = fear_greed_inputs.source_map || EXCLUDED.source_map,
                    created_at = NOW()
                    """,
                    (
                        date,
                        values.get("vix_close"),
                        values.get("hy_spread"),
                        json.dumps(source_map),
                    ),
                )
                rows_inserted += 1

            conn.commit()

        logger.info(
            "backfill_data_inserted",
            task_id=task_id,
            rows_inserted=rows_inserted,
        )

        # Calculate duration
        end_time = dt.datetime.now(dt.UTC)
        duration = (end_time - start_time).total_seconds()

        result = {
            "task_id": task_id,
            "days_requested": days,
            "vix_rows": vix_rows,
            "hy_spread_rows": hy_rows,
            "rows_inserted": rows_inserted,
            "duration_seconds": duration,
        }

        logger.info(
            "backfill_fred_indicators_completed",
            **result,
        )

        return result

    except Exception as e:
        logger.error(
            "backfill_fred_indicators_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
