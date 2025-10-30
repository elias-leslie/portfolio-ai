"""YFinance data source adapter.

Implements BaseSource interface for yfinance library with support for
daily OHLCV data and company reference information.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable

import polars as pl
import yfinance as yf  # type: ignore[import-untyped]  # yfinance doesn't ship type stubs

from ..logging_config import get_logger
from .base import BaseSource, DatasetRequest

logger = get_logger(__name__)


class YFinanceSource(BaseSource):
    """YFinance data source adapter.

    Free tier with no API key required.
    Note: yfinance has quirks - delays of 0.5-2s between requests recommended.
    """

    name = "yfinance"
    priority = 1  # Highest priority (free, no rate limits for basic usage)
    supports_day = True
    supports_reference = True
    supports_news = False  # News not implemented yet

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        """Fetch daily OHLCV bars from yfinance.

        Args:
            request: DatasetRequest with tickers, start, end dates

        Returns:
            Polars DataFrame with OHLCV data, or None if fetch fails
        """
        frames: list[pl.DataFrame] = []

        # Convert dates to string format for yfinance
        start_date = (
            request.start
            if isinstance(request.start, dt.date) and not isinstance(request.start, dt.datetime)
            else request.start.date()
            if isinstance(request.start, dt.datetime)
            else request.start
        )
        end_date = (
            request.end
            if isinstance(request.end, dt.date) and not isinstance(request.end, dt.datetime)
            else request.end.date()
            if isinstance(request.end, dt.datetime)
            else request.end
        )

        logger.info(
            "yfinance_fetch_day_bars_start",
            num_tickers=len(list(request.tickers)),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        for ticker in request.tickers:
            try:
                # Fetch historical data
                yf_ticker = yf.Ticker(ticker)
                hist = yf_ticker.history(
                    start=start_date.isoformat(),
                    end=end_date.isoformat(),
                    auto_adjust=True,  # Adjust for splits/dividends
                )

                if hist.empty:
                    logger.debug("yfinance_no_data", ticker=ticker)
                    continue

                # Convert pandas DataFrame to Polars
                # Reset index to get Date as a column
                hist = hist.reset_index()

                # Map column names to our schema
                df = pl.from_pandas(hist).select(
                    [
                        pl.col("Date").cast(pl.Date).alias("date"),
                        pl.lit(ticker).alias("ticker"),
                        pl.col("Open").alias("open"),
                        pl.col("High").alias("high"),
                        pl.col("Low").alias("low"),
                        pl.col("Close").alias("close"),
                        pl.col("Volume").cast(pl.Int64).alias("volume"),
                        pl.lit(None)
                        .cast(pl.Float64)
                        .alias("vwap"),  # yfinance doesn't provide VWAP
                        pl.lit("yfinance").alias("source"),
                    ]
                )

                # Add ingest_run_id if provided
                if request.ingest_run_id:
                    df = df.with_columns(pl.lit(request.ingest_run_id).alias("ingest_run_id"))

                frames.append(df)

                logger.debug(
                    "yfinance_fetch_success",
                    ticker=ticker,
                    rows=len(df),
                )

            except Exception as e:
                logger.warning(
                    "yfinance_fetch_error",
                    ticker=ticker,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Continue to next ticker
                continue

        if not frames:
            logger.warning("yfinance_no_data_fetched")
            return None

        # Combine all tickers
        combined = pl.concat(frames, how="vertical_relaxed")

        logger.info(
            "yfinance_fetch_day_bars_complete",
            total_rows=len(combined),
            unique_tickers=combined["ticker"].n_unique(),
        )

        return combined

    def fetch_reference_payload(
        self, tickers: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Fetch company reference data from yfinance.

        Args:
            tickers: List of ticker symbols
            as_of: As-of date for reference data

        Returns:
            Polars DataFrame with reference data, or None if fetch fails
        """
        records = []

        logger.info(
            "yfinance_fetch_reference_start",
            num_tickers=len(list(tickers)),
            as_of_date=as_of.isoformat(),
        )

        for ticker in tickers:
            try:
                yf_ticker = yf.Ticker(ticker)
                info = yf_ticker.info

                if not info:
                    logger.debug("yfinance_no_reference_data", ticker=ticker)
                    continue

                # Extract relevant fields
                # Note: Store as JSON string for flexibility
                # CRITICAL: Include price fields for watchlist functionality
                price = (
                    info.get("currentPrice")
                    or info.get("regularMarketPrice")
                    or info.get("previousClose")
                )
                beta = info.get("beta")

                # Calculate volatility from 52-week high/low if available
                volatility = None
                high_52 = info.get("fiftyTwoWeekHigh")
                low_52 = info.get("fiftyTwoWeekLow")
                if high_52 and low_52 and high_52 > 0:
                    # Approximate annualized volatility from 52-week range
                    volatility = (high_52 - low_52) / high_52

                payload_json = json.dumps(
                    {
                        "symbol": ticker,
                        "price": price,  # Current market price
                        "beta": beta,  # Market beta
                        "volatility": volatility,  # Calculated from 52-week range
                        "longName": info.get("longName"),
                        "shortName": info.get("shortName"),
                        "sector": info.get("sector"),
                        "industry": info.get("industry"),
                        "marketCap": info.get("marketCap"),
                        "currency": info.get("currency"),
                        "exchange": info.get("exchange"),
                        "country": info.get("country"),
                        "website": info.get("website"),
                        "description": info.get("longBusinessSummary"),
                    }
                )

                records.append(
                    {
                        "ticker": ticker,
                        "as_of_date": as_of,
                        "payload": payload_json,
                        "source": "yfinance",
                    }
                )

                logger.debug("yfinance_reference_fetched", ticker=ticker)

            except Exception as e:
                logger.warning(
                    "yfinance_reference_error",
                    ticker=ticker,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                continue

        if not records:
            logger.warning("yfinance_no_reference_data_fetched")
            return None

        logger.info(
            "yfinance_reference_complete",
            num_tickers=len(records),
        )

        return pl.DataFrame(records)

    def fetch_news_payload(
        self, tickers: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles from yfinance (not implemented yet)."""
        logger.warning("yfinance_news_not_implemented")
        return None
