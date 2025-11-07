"""Alpha Vantage API source adapter with rate limiting.

Implements BaseSource interface for Alpha Vantage API with support for
daily OHLCV data. Note: Reference data not supported in free tier.

Rate limits:
- Free tier: 25 API calls per day, 5 API calls per minute
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterable
from typing import Any

import polars as pl

from ..logging_config import get_logger
from .base import BaseSource, DatasetRequest
from .base_http_client import BaseHTTPClient

logger = get_logger(__name__)


class AlphaVantageClient(BaseHTTPClient):
    """Synchronous Alpha Vantage REST API client with rate limiting.

    Features:
    - Thread-safe rate limiting (5 requests/min, 25 requests/day)
    - Automatic retries with exponential backoff
    - Request tracking for performance monitoring
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize Alpha Vantage client.

        Args:
            api_key: Alpha Vantage API key (defaults to ALPHAVANTAGE_API_KEY env var)
            timeout: Request timeout in seconds (default: 30)

        Raises:
            RuntimeError: If API key not provided and not in environment
        """
        super().__init__(
            api_key=api_key,
            rate_calls_per_minute=5,
            rate_calls_per_day=25,
            timeout=timeout,
        )

    def get_api_key_env_var(self) -> str:
        """Return environment variable name for API key."""
        return "ALPHAVANTAGE_API_KEY"

    def get_client_name(self) -> str:
        """Return client name for logging."""
        return "alphavantage_client"

    def get_api_key_param_name(self) -> str:
        """Return query parameter name for API key."""
        return "apikey"

    def get(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute GET request to Alpha Vantage query endpoint.

        Args:
            params: Query parameters (function, symbol, etc.)

        Returns:
            Parsed JSON response
        """
        # Alpha Vantage uses query endpoint with params, not path-based API
        result: dict[str, Any] = self.request("", params, method="GET")
        return result

    def get_daily_time_series(
        self,
        ticker: str,
        outputsize: str = "compact",
    ) -> dict[str, Any]:
        """Fetch daily time series data for a ticker.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            outputsize: "compact" (100 days) or "full" (20+ years)

        Returns:
            Dict with "Time Series (Daily)" key containing OHLCV data

        Example:
            >>> client.get_daily_time_series("AAPL")
            {"Time Series (Daily)": {"2024-01-31": {"1. open": "184.35", ...}}}
        """
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": outputsize,
        }
        result: dict[str, Any] = self.get(params)
        return result


# Module-level singleton state
class _ClientState:
    """Holds singleton client instance."""

    client: AlphaVantageClient | None = None
    lock = threading.Lock()


def get_client() -> AlphaVantageClient:
    """Get or create the Alpha Vantage client singleton.

    Thread-safe lazy initialization.

    Returns:
        AlphaVantageClient instance

    Raises:
        RuntimeError: If ALPHAVANTAGE_API_KEY not set
    """
    if _ClientState.client is None:
        with _ClientState.lock:
            # Double-check after acquiring lock
            if _ClientState.client is None:
                _ClientState.client = AlphaVantageClient()
    return _ClientState.client


class AlphaVantageSource(BaseSource):
    """Alpha Vantage source adapter implementing BaseSource interface.

    Priority: 30 (lowest priority - very restrictive rate limits)
    Rate limits: 5 calls/min, 25 calls/day
    Note: Reference data not supported in free tier
    """

    name = "alphavantage"
    priority = 30  # Lowest priority due to restrictive rate limits
    supports_day = True
    supports_reference = False  # Not available in free tier
    supports_news = False  # Not implemented

    def __init__(self) -> None:
        """Initialize Alpha Vantage source."""
        self.client = get_client()
        logger.info("alphavantage_source_initialized")

    def is_enabled(self) -> bool:
        """Check if Alpha Vantage API key is configured."""
        return os.getenv("ALPHAVANTAGE_API_KEY") is not None

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        """Fetch daily OHLCV bars from Alpha Vantage.

        Args:
            request: DatasetRequest with tickers, start, end dates

        Returns:
            Polars DataFrame with OHLCV data, or None if fetch fails
        """
        frames: list[pl.DataFrame] = []

        # Convert dates for filtering
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
            "alphavantage_fetch_day_bars_start",
            num_tickers=len(list(request.tickers)),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        for ticker in request.tickers:
            try:
                # Fetch time series data (compact = 100 days)
                response = self.client.get_daily_time_series(ticker, outputsize="compact")

                # Check for error messages
                if "Error Message" in response:
                    logger.warning(
                        "alphavantage_api_error",
                        ticker=ticker,
                        error=response["Error Message"],
                    )
                    continue

                if "Note" in response:
                    # API rate limit message
                    logger.warning(
                        "alphavantage_rate_limit_message",
                        ticker=ticker,
                        note=response["Note"],
                    )
                    continue

                # Extract time series data
                time_series = response.get("Time Series (Daily)", {})
                if not time_series:
                    logger.debug("alphavantage_no_data", ticker=ticker)
                    continue

                # Parse OHLCV data
                records = []
                for date_str, bar in time_series.items():
                    try:
                        bar_date = dt.date.fromisoformat(date_str)

                        # Filter by date range
                        if bar_date < start_date or bar_date > end_date:
                            continue

                        records.append(
                            {
                                "date": bar_date,
                                "ticker": ticker,
                                "open": float(bar["1. open"]),
                                "high": float(bar["2. high"]),
                                "low": float(bar["3. low"]),
                                "close": float(bar["4. close"]),
                                "volume": int(bar["5. volume"]),
                                "vwap": None,  # Alpha Vantage doesn't provide VWAP
                                "source": "alphavantage",
                            }
                        )
                    except (KeyError, ValueError) as e:
                        logger.warning(
                            "alphavantage_bar_parse_error",
                            ticker=ticker,
                            date=date_str,
                            error=str(e),
                        )
                        continue

                if not records:
                    logger.debug("alphavantage_no_valid_bars", ticker=ticker)
                    continue

                # Create DataFrame
                df = pl.DataFrame(records)

                # Add ingest_run_id if provided
                if request.ingest_run_id:
                    df = df.with_columns(pl.lit(request.ingest_run_id).alias("ingest_run_id"))

                frames.append(df)

                logger.debug(
                    "alphavantage_fetch_success",
                    ticker=ticker,
                    rows=len(df),
                )

            except Exception as e:
                logger.warning(
                    "alphavantage_fetch_error",
                    ticker=ticker,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Continue to next ticker
                continue

        if not frames:
            logger.warning("alphavantage_no_data_fetched")
            return None

        # Combine all tickers
        combined = pl.concat(frames, how="vertical_relaxed")

        logger.info(
            "alphavantage_fetch_day_bars_complete",
            total_rows=len(combined),
            unique_tickers=combined["ticker"].n_unique(),
        )

        return combined

    def fetch_reference_payload(
        self, tickers: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Fetch company reference data from Alpha Vantage (not supported in free tier)."""
        logger.warning("alphavantage_reference_not_supported")
        return None

    def fetch_news_payload(
        self, tickers: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles from Alpha Vantage (not implemented)."""
        logger.warning("alphavantage_news_not_implemented")
        return None
