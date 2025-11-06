"""Financial Modeling Prep (FMP) API source adapter with rate limiting.

Implements BaseSource interface for FMP API with support for
daily OHLCV data and company profile information.

Rate limits:
- Free tier: 250 API calls per day
- No sub-minute rate limit enforced by API
"""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
from collections import deque
from collections.abc import Iterable
from contextlib import suppress
from typing import Any

import httpx
import polars as pl
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

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


class FMPClient:
    """Synchronous FMP REST API client with rate limiting.

    Features:
    - Thread-safe rate limiting (250 calls/day)
    - Automatic retries with exponential backoff
    - Request tracking for performance monitoring
    """

    BASE_URL = "https://financialmodelingprep.com/api/v3"

    def __init__(
        self,
        api_key: str | None = None,
        rate_calls_per_day: int = 250,
        timeout: float = 30.0,
    ) -> None:
        """Initialize FMP client.

        Args:
            api_key: FMP API key (defaults to FMP_API_KEY env var)
            rate_calls_per_day: Maximum requests per day (default: 250)
            timeout: Request timeout in seconds (default: 30)

        Raises:
            RuntimeError: If API key not provided and not in environment
        """
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        if not self.api_key:
            raise RuntimeError("FMP_API_KEY is not set")

        self._client = httpx.Client(timeout=timeout)
        self._lock = threading.Lock()
        # Track requests in last 24 hours
        self._last_request_times: deque[float] = deque(maxlen=rate_calls_per_day)
        self._rate_calls_per_day = rate_calls_per_day
        self.request_count = 0

        logger.info(
            "fmp_client_initialized",
            rate_limit=f"{rate_calls_per_day}/day",
            timeout=timeout,
        )

    def close(self) -> None:
        """Close HTTP client and release resources."""
        self._client.close()
        logger.debug("fmp_client_closed", request_count=self.request_count)

    def _throttle(self) -> None:
        """Thread-safe rate limiting using sliding 24-hour window.

        Blocks until a request slot is available based on daily rate limit.
        """
        with self._lock:
            now = time.monotonic()

            # Remove requests older than 24 hours
            cutoff_time = now - 86400  # 24 hours in seconds
            while self._last_request_times and self._last_request_times[0] < cutoff_time:
                self._last_request_times.popleft()

            # If we've hit the daily limit, wait until oldest request is 24h old
            if len(self._last_request_times) >= self._rate_calls_per_day:
                oldest = self._last_request_times[0]
                wait_for = 86400 - (now - oldest)
                if wait_for > 0:
                    logger.warning(
                        "fmp_rate_limit_hit",
                        wait_seconds=wait_for,
                        daily_limit=self._rate_calls_per_day,
                    )
                    # Don't actually wait 24 hours in practice - just raise error
                    raise RuntimeError(
                        f"FMP daily rate limit ({self._rate_calls_per_day} calls) exceeded. "
                        f"Reset in {wait_for:.0f} seconds"
                    )

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
    ) -> Any:
        """Execute HTTP request with rate limiting and retries.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/historical-price-full/AAPL")
            params: Query parameters

        Returns:
            Parsed JSON response (can be dict or list)

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
            "fmp_request_success",
            method=method.upper(),
            path=path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_count=self.request_count,
        )

        return response.json()

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Execute GET request.

        Args:
            path: API path
            params: Query parameters

        Returns:
            Parsed JSON response
        """
        return self._request_json("GET", path, params)

    def get_historical_price(
        self,
        ticker: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        """Fetch historical daily OHLCV bars for a ticker.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            from_date: Start date (YYYY-MM-DD format, optional)
            to_date: End date (YYYY-MM-DD format, optional)

        Returns:
            Dict with "historical" key containing list of OHLCV dicts

        Example:
            >>> client.get_historical_price("AAPL", "2024-01-01", "2024-01-31")
            {"symbol": "AAPL", "historical": [{"date": "2024-01-31", "open": 184.35, ...}]}
        """
        path = f"/historical-price-full/{ticker}"
        params: dict[str, Any] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        result: dict[str, Any] = self.get(path, params)
        return result

    def get_profile(self, ticker: str) -> list[dict[str, Any]]:
        """Fetch company profile and metadata.

        Args:
            ticker: Stock symbol (e.g., "AAPL")

        Returns:
            List with single dict containing company profile

        Example:
            >>> client.get_profile("AAPL")
            [{"symbol": "AAPL", "companyName": "Apple Inc", "sector": "Technology", ...}]
        """
        path = f"/profile/{ticker}"
        result: list[dict[str, Any]] = self.get(path)
        return result

    def __del__(self) -> None:
        """Close client on garbage collection."""
        if hasattr(self, "_client"):
            self.close()


# Module-level singleton state
class _ClientState:
    """Holds singleton client instance."""

    client: FMPClient | None = None
    lock = threading.Lock()


def get_client() -> FMPClient:
    """Get or create the FMP client singleton.

    Thread-safe lazy initialization.

    Returns:
        FMPClient instance

    Raises:
        RuntimeError: If FMP_API_KEY not set
    """
    if _ClientState.client is None:
        with _ClientState.lock:
            # Double-check after acquiring lock
            if _ClientState.client is None:
                _ClientState.client = FMPClient()
    return _ClientState.client


class FMPSource(BaseSource):
    """Financial Modeling Prep source adapter implementing BaseSource interface.

    Priority: 3 (lower than YFinance and Twelve Data)
    Rate limits: 250 calls/day
    """

    name = "fmp"
    priority = 3  # Lower priority than YFinance (1) and Twelve Data (2)
    supports_day = True
    supports_reference = True
    supports_news = True

    def __init__(self) -> None:
        """Initialize FMP source."""
        self.client = get_client()
        logger.info("fmp_source_initialized")

    def is_enabled(self) -> bool:
        """Check if FMP API key is configured."""
        return os.getenv("FMP_API_KEY") is not None

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        """Fetch daily OHLCV bars from FMP.

        Args:
            request: DatasetRequest with tickers, start, end dates

        Returns:
            Polars DataFrame with OHLCV data, or None if fetch fails
        """
        frames: list[pl.DataFrame] = []

        # Convert dates to string format for FMP API
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
            "fmp_fetch_day_bars_start",
            num_tickers=len(list(request.tickers)),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        for ticker in request.tickers:
            try:
                # Fetch historical data
                response = self.client.get_historical_price(
                    ticker=ticker,
                    from_date=start_date.isoformat(),
                    to_date=end_date.isoformat(),
                )

                # Check for error response
                if "Error Message" in response:
                    error_msg = response.get("Error Message", "Unknown error")
                    logger.warning(
                        "fmp_api_error",
                        ticker=ticker,
                        error=error_msg,
                    )
                    continue

                # Extract historical data
                historical = response.get("historical", [])
                if not historical:
                    logger.debug("fmp_no_data", ticker=ticker)
                    continue

                # Parse OHLCV data
                records = []
                for bar in historical:
                    try:
                        records.append(
                            {
                                "date": dt.date.fromisoformat(bar["date"]),
                                "ticker": ticker,
                                "open": float(bar["open"]),
                                "high": float(bar["high"]),
                                "low": float(bar["low"]),
                                "close": float(bar["close"]),
                                "volume": int(bar["volume"]),
                                "vwap": float(bar["vwap"]) if "vwap" in bar else None,
                                "source": "fmp",
                            }
                        )
                    except (KeyError, ValueError) as e:
                        logger.warning(
                            "fmp_bar_parse_error",
                            ticker=ticker,
                            bar=bar,
                            error=str(e),
                        )
                        continue

                if not records:
                    logger.debug("fmp_no_valid_bars", ticker=ticker)
                    continue

                # Create DataFrame
                df = pl.DataFrame(records)

                # Add ingest_run_id if provided
                if request.ingest_run_id:
                    df = df.with_columns(pl.lit(request.ingest_run_id).alias("ingest_run_id"))

                frames.append(df)

                logger.debug(
                    "fmp_fetch_success",
                    ticker=ticker,
                    rows=len(df),
                )

            except Exception as e:
                logger.warning(
                    "fmp_fetch_error",
                    ticker=ticker,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Continue to next ticker
                continue

        if not frames:
            logger.warning("fmp_no_data_fetched")
            return None

        # Combine all tickers
        combined = pl.concat(frames, how="vertical_relaxed")

        logger.info(
            "fmp_fetch_day_bars_complete",
            total_rows=len(combined),
            unique_tickers=combined["ticker"].n_unique(),
        )

        return combined

    def fetch_reference_payload(
        self, tickers: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Fetch company profile data from FMP.

        Args:
            tickers: List of ticker symbols
            as_of: As-of date for reference data

        Returns:
            Polars DataFrame with reference data, or None if fetch fails
        """
        records = []

        logger.info(
            "fmp_fetch_reference_start",
            num_tickers=len(list(tickers)),
            as_of_date=as_of.isoformat(),
        )

        for ticker in tickers:
            try:
                response = self.client.get_profile(ticker)

                # Check for empty response
                if not response:
                    logger.warning(
                        "fmp_profile_api_error",
                        ticker=ticker,
                        error="No data",
                    )
                    continue

                # FMP returns a list with single profile dict
                profile = response[0]

                # Store profile as JSON string
                payload_json = json.dumps(profile)

                records.append(
                    {
                        "ticker": ticker,
                        "as_of_date": as_of,
                        "payload": payload_json,
                        "source": "fmp",
                    }
                )

                logger.debug("fmp_reference_fetched", ticker=ticker)

            except Exception as e:
                logger.warning(
                    "fmp_reference_error",
                    ticker=ticker,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                continue

        if not records:
            logger.warning("fmp_no_reference_data_fetched")
            return None

        logger.info(
            "fmp_reference_complete",
            num_tickers=len(records),
        )

        return pl.DataFrame(records)

    def fetch_news_payload(
        self, tickers: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles from FMP stock news endpoint."""
        records: list[dict[str, Any]] = []
        start_date = start.astimezone(dt.UTC).date().isoformat()
        end_date = end.astimezone(dt.UTC).date().isoformat()

        ticker_list = list(tickers) or ["__MARKET__"]
        for ticker in ticker_list:
            is_market = ticker in (None, "__MARKET__")
            params: dict[str, Any] = {
                "from": start_date,
                "to": end_date,
                "limit": 50,
            }
            if not is_market:
                params["tickers"] = ticker

            try:
                response = self.client.get("/stock_news", params)
            except Exception as exc:
                logger.warning(
                    "fmp_news_error",
                    ticker="__MARKET__" if is_market else ticker,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                continue

            items = response if isinstance(response, list) else []
            if not items:
                logger.debug(
                    "fmp_news_empty",
                    ticker="__MARKET__" if is_market else ticker,
                )
                continue

            for item in items:
                headline = item.get("title")
                if not headline:
                    continue

                published_at = None
                published_raw = item.get("publishedDate")
                if isinstance(published_raw, str):
                    with suppress(Exception):
                        published_at = dt.datetime.fromisoformat(
                            published_raw.replace("Z", "+00:00")
                        )

                records.append(
                    {
                        "ticker": "__MARKET__" if is_market else (item.get("symbol") or ticker),
                        "headline": headline,
                        "url": item.get("url"),
                        "summary": item.get("text"),
                        "news_source_name": item.get("site"),
                        "author": item.get("author"),
                        "image_url": item.get("image"),
                        "published_at": published_at,
                        "raw_payload": json.dumps(item),
                        "source": "fmp",
                    }
                )

            logger.debug(
                "fmp_news_fetched",
                ticker="__MARKET__" if is_market else ticker,
                articles=len(items),
            )

        if not records:
            logger.info("fmp_news_no_articles", tickers=list(ticker_list))
            return None

        return pl.DataFrame(records)
