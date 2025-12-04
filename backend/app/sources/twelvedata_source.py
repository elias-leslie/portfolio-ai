"""Twelve Data API source adapter with rate limiting.

Implements BaseSource interface for Twelve Data API with support for
daily OHLCV data and company profile information.

Rate limits:
- Free tier: 800 API credits per day
- 8 requests per minute sub-limit
"""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
from collections.abc import Iterable
from typing import Any

import polars as pl

from ..logging_config import get_logger
from .base import BaseSource, DatasetRequest, standardize_dates
from .base_http_client import BaseHTTPClient

logger = get_logger(__name__)


class TwelveDataClient(BaseHTTPClient):
    """Synchronous Twelve Data REST API client with rate limiting.

    Features:
    - Thread-safe rate limiting (8 requests/min)
    - Automatic retries with exponential backoff
    - Request tracking for performance monitoring
    """

    BASE_URL = "https://api.twelvedata.com"

    def __init__(
        self,
        api_key: str | None = None,
        rate_calls_per_minute: int | None = 8,
        timeout: float = 30.0,
    ) -> None:
        """Initialize Twelve Data client.

        Args:
            api_key: Twelve Data API key (defaults to TWELVEDATA_API_KEY env var)
            rate_calls_per_minute: Maximum requests per minute (default: 8, None = no limit)
            timeout: Request timeout in seconds (default: 30)

        Raises:
            RuntimeError: If API key not provided and not in environment
        """
        super().__init__(
            api_key=api_key, rate_calls_per_minute=rate_calls_per_minute, timeout=timeout
        )

    def get_api_key_env_var(self) -> str:
        """Return environment variable name for API key."""
        return "TWELVEDATA_API_KEY"

    def get_client_name(self) -> str:
        """Return client name for logging."""
        return "twelvedata_client"

    def get_api_key_param_name(self) -> str:
        """Return query parameter name for API key."""
        return "apikey"

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute GET request.

        Args:
            path: API path
            params: Query parameters

        Returns:
            Parsed JSON response
        """
        result: dict[str, Any] = self.request(path, params, method="GET")
        return result

    def get_time_series(
        self,
        ticker: str,
        interval: str = "1day",
        outputsize: int = 252,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Fetch time series data (OHLCV) for a ticker.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            interval: Time interval (default: "1day")
            outputsize: Number of data points (default: 252 for ~1 year)
            start_date: Start date (YYYY-MM-DD format, optional)
            end_date: End date (YYYY-MM-DD format, optional)

        Returns:
            Dict with "values" key containing list of OHLCV dicts

        Example:
            >>> client.get_time_series("AAPL", outputsize=5)
            {"values": [{"datetime": "2024-01-05", "open": "184.35", ...}], "status": "ok"}
        """
        params: dict[str, Any] = {
            "symbol": ticker,
            "interval": interval,
            "outputsize": outputsize,
        }

        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return self.get("/time_series", params)

    def get_profile(self, ticker: str) -> dict[str, Any]:
        """Fetch company profile and metadata.

        Args:
            ticker: Stock symbol (e.g., "AAPL")

        Returns:
            Dict with company profile information

        Example:
            >>> client.get_profile("AAPL")
            {"symbol": "AAPL", "name": "Apple Inc", "sector": "Technology", ...}
        """
        params = {"symbol": ticker}
        return self.get("/profile", params)


# Module-level singleton state
class _ClientState:
    """Holds singleton client instance."""

    client: TwelveDataClient | None = None
    lock = threading.Lock()


def get_client() -> TwelveDataClient:
    """Get or create the Twelve Data client singleton.

    Thread-safe lazy initialization.

    Returns:
        TwelveDataClient instance

    Raises:
        RuntimeError: If TWELVEDATA_API_KEY not set
    """
    if _ClientState.client is None:
        with _ClientState.lock:
            # Double-check after acquiring lock
            if _ClientState.client is None:
                _ClientState.client = TwelveDataClient()
    return _ClientState.client


class TwelveDataSource(BaseSource):
    """Twelve Data source adapter implementing BaseSource interface.

    Priority: 2 (lower than YFinance, higher than Polygon)
    Rate limits: 8 requests/min, 800 credits/day
    """

    name = "twelvedata"
    priority = 2  # Lower priority than YFinance (1), higher than Polygon (10)
    supports_day = True
    supports_reference = True
    supports_news = False  # Not implemented yet

    def __init__(self) -> None:
        """Initialize Twelve Data source."""
        self.client = get_client()
        logger.info("twelvedata_source_initialized")

    def is_enabled(self) -> bool:
        """Check if Twelve Data API key is configured."""
        return os.getenv("TWELVEDATA_API_KEY") is not None

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        """Fetch daily OHLCV bars from Twelve Data.

        Args:
            request: DatasetRequest with tickers, start, end dates

        Returns:
            Polars DataFrame with OHLCV data, or None if fetch fails
        """
        frames: list[pl.DataFrame] = []

        # Convert dates to date objects
        start_date, end_date = standardize_dates(request)

        # Calculate outputsize based on date range
        days_requested = (end_date - start_date).days + 1
        outputsize = min(5000, max(30, days_requested))  # Twelve Data max is 5000

        logger.info(
            "twelvedata_fetch_day_bars_start",
            num_tickers=len(list(request.tickers)),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            outputsize=outputsize,
        )

        for ticker in request.tickers:
            try:
                # Fetch time series data
                response = self.client.get_time_series(
                    ticker=ticker,
                    interval="1day",
                    outputsize=outputsize,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )

                # Check for error response
                if "status" in response and response["status"] == "error":
                    error_msg = response.get("message", "Unknown error")
                    logger.warning(
                        "twelvedata_api_error",
                        ticker=ticker,
                        error=error_msg,
                    )
                    continue

                # Extract values array
                values = response.get("values", [])
                if not values:
                    logger.debug("twelvedata_no_data", ticker=ticker)
                    continue

                # Parse OHLCV data
                records = []
                for bar in values:
                    try:
                        records.append(
                            {
                                "date": dt.date.fromisoformat(bar["datetime"]),
                                "ticker": ticker,
                                "open": float(bar["open"]),
                                "high": float(bar["high"]),
                                "low": float(bar["low"]),
                                "close": float(bar["close"]),
                                "volume": int(bar["volume"]),
                                "vwap": None,  # Twelve Data doesn't provide VWAP in basic plan
                                "source": "twelvedata",
                            }
                        )
                    except (KeyError, ValueError) as e:
                        logger.warning(
                            "twelvedata_bar_parse_error",
                            ticker=ticker,
                            bar=bar,
                            error=str(e),
                        )
                        continue

                if not records:
                    logger.debug("twelvedata_no_valid_bars", ticker=ticker)
                    continue

                # Create DataFrame
                df = pl.DataFrame(records)

                # Add ingest_run_id if provided
                if request.ingest_run_id:
                    df = df.with_columns(pl.lit(request.ingest_run_id).alias("ingest_run_id"))

                frames.append(df)

                logger.debug(
                    "twelvedata_fetch_success",
                    ticker=ticker,
                    rows=len(df),
                )

            except Exception as e:
                logger.warning(
                    "twelvedata_fetch_error",
                    ticker=ticker,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Continue to next ticker
                continue

        if not frames:
            logger.warning("twelvedata_no_data_fetched")
            return None

        # Combine all tickers
        combined = pl.concat(frames, how="vertical_relaxed")

        logger.info(
            "twelvedata_fetch_day_bars_complete",
            total_rows=len(combined),
            unique_tickers=combined["ticker"].n_unique(),
        )

        return combined

    def fetch_reference_payload(
        self, tickers: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Fetch company profile data from Twelve Data.

        Args:
            tickers: List of ticker symbols
            as_of: As-of date for reference data

        Returns:
            Polars DataFrame with reference data, or None if fetch fails
        """
        records = []

        logger.info(
            "twelvedata_fetch_reference_start",
            num_tickers=len(list(tickers)),
            as_of_date=as_of.isoformat(),
        )

        for ticker in tickers:
            try:
                response = self.client.get_profile(ticker)

                # Check for error response
                if "status" in response and response["status"] == "error":
                    error_msg = response.get("message", "Unknown error")
                    logger.warning(
                        "twelvedata_profile_api_error",
                        ticker=ticker,
                        error=error_msg,
                    )
                    continue

                if not response or "symbol" not in response:
                    logger.debug("twelvedata_no_reference_data", ticker=ticker)
                    continue

                # Store profile as JSON string
                payload_json = json.dumps(response)

                records.append(
                    {
                        "ticker": ticker,
                        "as_of_date": as_of,
                        "payload": payload_json,
                        "source": "twelvedata",
                    }
                )

                logger.debug("twelvedata_reference_fetched", ticker=ticker)

            except Exception as e:
                logger.warning(
                    "twelvedata_reference_error",
                    ticker=ticker,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                continue

        if not records:
            logger.warning("twelvedata_no_reference_data_fetched")
            return None

        logger.info(
            "twelvedata_reference_complete",
            num_tickers=len(records),
        )

        return pl.DataFrame(records)

    def fetch_news_payload(
        self, tickers: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles from Twelve Data (not implemented yet)."""
        logger.warning("twelvedata_news_not_implemented")
        return None
