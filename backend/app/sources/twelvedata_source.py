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
import time
from collections import deque
from collections.abc import Iterable
from typing import Any

import httpx
import polars as pl
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ..logging_config import get_logger
from .base import BaseSource, DatasetRequest

logger = get_logger(__name__)


def _should_retry_exception(exc: BaseException) -> bool:
    """Determine if exception should trigger a retry.

    Retries on:
    - 429 (rate limit)
    - 500, 502, 503, 504 (server errors)
    - Network errors (timeout, connection errors)
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else None
        return status in {429, 500, 502, 503, 504}
    return isinstance(exc, httpx.RequestError)


class TwelveDataClient:
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
        rate_calls_per_minute: int = 8,
        timeout: float = 30.0,
    ) -> None:
        """Initialize Twelve Data client.

        Args:
            api_key: Twelve Data API key (defaults to TWELVEDATA_API_KEY env var)
            rate_calls_per_minute: Maximum requests per minute (default: 8)
            timeout: Request timeout in seconds (default: 30)

        Raises:
            RuntimeError: If API key not provided and not in environment
        """
        self.api_key = api_key or os.getenv("TWELVEDATA_API_KEY")
        if not self.api_key:
            raise RuntimeError("TWELVEDATA_API_KEY is not set")

        self._client = httpx.Client(timeout=timeout)
        self._interval = 60.0 / max(1, rate_calls_per_minute)
        self._lock = threading.Lock()
        self._last_request_times: deque[float] = deque(maxlen=rate_calls_per_minute)
        self.request_count = 0

        logger.info(
            "twelvedata_client_initialized",
            rate_limit=f"{rate_calls_per_minute}/min",
            timeout=timeout,
        )

    def close(self) -> None:
        """Close HTTP client and release resources."""
        self._client.close()
        logger.debug("twelvedata_client_closed", request_count=self.request_count)

    def _throttle(self) -> None:
        """Thread-safe rate limiting using sliding window.

        Blocks until a request slot is available based on configured rate limit.
        """
        with self._lock:
            now = time.monotonic()

            # If we've hit the rate limit, wait until oldest request is old enough
            if (
                self._last_request_times.maxlen is not None
                and len(self._last_request_times) >= self._last_request_times.maxlen
            ):
                oldest = self._last_request_times[0]
                wait_for = 60.0 - (now - oldest)
                if wait_for > 0:
                    logger.debug("twelvedata_rate_limit_wait", wait_seconds=wait_for)
                    time.sleep(wait_for)
                    now = time.monotonic()

            self._last_request_times.append(now)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, max=30),
        retry=retry_if_exception(_should_retry_exception),
        reraise=True,
    )
    def _request_json(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute HTTP request with rate limiting and retries.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/time_series")
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            HTTPStatusError: On HTTP errors after retries exhausted
            RequestError: On network errors after retries exhausted
        """
        self._throttle()

        query: dict[str, Any] = dict(params or {})
        query["apikey"] = self.api_key

        start_time = time.time()
        response = self._client.request(method.upper(), f"{self.BASE_URL}{path}", params=query)
        duration_ms = int((time.time() - start_time) * 1000)

        response.raise_for_status()
        self.request_count += 1

        logger.info(
            "twelvedata_request_success",
            method=method.upper(),
            path=path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_count=self.request_count,
        )

        result: dict[str, Any] = response.json()
        return result

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute GET request.

        Args:
            path: API path
            params: Query parameters

        Returns:
            Parsed JSON response
        """
        result: dict[str, Any] = self._request_json("GET", path, params)
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

    def __del__(self) -> None:
        """Close client on garbage collection."""
        if hasattr(self, "_client"):
            self.close()


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

        # Convert dates to string format for Twelve Data API
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
