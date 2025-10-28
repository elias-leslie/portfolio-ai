"""Polygon data source adapter using PolygonClient.

Adapted from market-sim for portfolio-ai.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable

import polars as pl

from ..logging_config import get_logger
from .base import BaseSource, DatasetRequest
from .jsonpath_mapper import map_response_to_schema
from .polygon_client import get_client

logger = get_logger(__name__)


class PolygonSource(BaseSource):
    """Polygon data source with automatic rate limiting."""

    name = "polygon"
    priority = 10  # Medium priority - rate limited on free tier (5/min)
    supports_day = True
    supports_reference = True
    supports_news = False  # Not implemented yet

    def __init__(self, include_otc: bool = True) -> None:
        """Initialize Polygon source.

        Args:
            include_otc: Whether to include OTC (over-the-counter) securities
        """
        self.include_otc = include_otc
        self.client = get_client()
        logger.info("polygon_source_initialized", include_otc=include_otc)

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        """Fetch daily OHLCV bars using Polygon grouped_daily endpoint.

        Strategy: Fetch all tickers for each date, then filter to requested tickers.
        This is more efficient than per-ticker requests for multiple tickers.
        """
        frames: list[pl.DataFrame] = []
        dates = _iterate_dates(request.start, request.end)

        logger.info(
            "polygon_fetch_day_bars_start",
            num_dates=len(dates),
            num_tickers=len(list(request.tickers)),
        )

        for iso_date in dates:
            try:
                # Use grouped_daily endpoint: get all tickers for a date
                # Polygon API path: /v2/aggs/grouped/locale/us/market/stocks/{date}
                path = f"/v2/aggs/grouped/locale/us/market/stocks/{iso_date}"
                params = {
                    "adjusted": "true",
                    "include_otc": "true" if self.include_otc else "false",
                }

                response = self.client.get(path, params)

                # Map response to schema
                mapping_config = {
                    "field_mapping": {
                        "T": "ticker",
                        "o": "open",
                        "h": "high",
                        "l": "low",
                        "c": "close",
                        "v": "volume",
                        "vw": "vwap",
                        "n": "trade_count",
                    },
                    "data_path": "results",
                }

                df = map_response_to_schema(response, mapping_config)
                if df is None or len(df) == 0:
                    logger.debug("polygon_no_data_for_date", date=iso_date)
                    continue

                # Add date column
                df = df.with_columns(pl.lit(dt.date.fromisoformat(iso_date)).alias("date_utc"))

                # Add source and ingest_run_id
                df = df.with_columns(pl.lit("polygon").alias("source"))
                if request.ingest_run_id:
                    df = df.with_columns(pl.lit(request.ingest_run_id).alias("ingest_run_id"))

                frames.append(df)

            except Exception as e:
                logger.warning(
                    "polygon_fetch_date_error",
                    date=iso_date,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                continue

        if not frames:
            logger.warning("polygon_no_data_fetched")
            return None

        # Combine all dates
        df_all = pl.concat(frames, how="vertical_relaxed")

        # Filter to requested tickers
        if request.tickers:
            ticker_list = list(request.tickers)
            df_all = df_all.filter(pl.col("ticker").is_in(ticker_list))

        logger.info(
            "polygon_fetch_day_bars_complete",
            total_rows=len(df_all),
            unique_tickers=df_all["ticker"].n_unique(),
        )

        return df_all

    def fetch_reference_payload(
        self, tickers: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Fetch company reference data (ticker details) from Polygon.

        Returns:
            DataFrame with columns: ticker, as_of_date, payload (JSON string), source
        """
        records = []

        for ticker in tickers:
            try:
                # Use ticker details endpoint
                response = self.client.get_ticker_details(ticker)

                # Extract the results payload
                payload_dict = response.get("results", {})
                if not payload_dict:
                    logger.debug("polygon_no_reference_data", ticker=ticker)
                    continue

                # Convert to JSON string for storage
                payload_json = json.dumps(payload_dict)

                records.append(
                    {
                        "ticker": ticker,
                        "as_of_date": as_of,
                        "payload": payload_json,
                        "source": "polygon",
                    }
                )

                logger.debug("polygon_reference_fetched", ticker=ticker)

            except Exception as e:
                logger.warning(
                    "polygon_reference_error",
                    ticker=ticker,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                continue

        if not records:
            logger.warning("polygon_no_reference_data_fetched")
            return None

        logger.info(
            "polygon_reference_complete",
            num_tickers=len(records),
        )

        return pl.DataFrame(records)

    def fetch_news_payload(
        self, tickers: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles from Polygon (not implemented yet)."""
        logger.warning("polygon_news_not_implemented")
        return None


def _iterate_dates(start: dt.date | dt.datetime, end: dt.date | dt.datetime) -> list[str]:
    """Generate list of ISO date strings between start and end.

    Args:
        start: Start date
        end: End date

    Returns:
        List of ISO date strings (e.g., ["2024-01-01", "2024-01-02", ...])
    """
    start_date = start.date() if isinstance(start, dt.datetime) else start
    end_date = end.date() if isinstance(end, dt.datetime) else end

    if end_date < start_date:
        return []

    days: list[str] = []
    current = start_date
    while current <= end_date:
        days.append(current.isoformat())
        current += dt.timedelta(days=1)

    return days
