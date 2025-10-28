"""Polygon API client with rate limiting and retry logic.

Adapted from market-sim for portfolio-ai.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ..logging_config import get_logger

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


class PolygonClient:
    """Synchronous Polygon REST API client with rate limiting.

    Features:
    - Thread-safe rate limiting (5 requests/min default)
    - Automatic retries with exponential backoff
    - Request tracking for performance monitoring
    """

    BASE_URL = "https://api.polygon.io"

    def __init__(
        self,
        api_key: str | None = None,
        rate_calls_per_minute: int = 5,
        timeout: float = 60.0,
    ) -> None:
        """Initialize Polygon client.

        Args:
            api_key: Polygon API key (defaults to POLYGON_API_KEY env var)
            rate_calls_per_minute: Maximum requests per minute (default: 5)
            timeout: Request timeout in seconds (default: 60)

        Raises:
            RuntimeError: If API key not provided and not in environment
        """
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        if not self.api_key:
            raise RuntimeError("POLYGON_API_KEY is not set")

        self._client = httpx.Client(timeout=timeout)
        self._interval = 60.0 / max(1, rate_calls_per_minute)
        self._lock = threading.Lock()
        self._last_request_times: deque[float] = deque(maxlen=rate_calls_per_minute)
        self.request_count = 0

        logger.info(
            "polygon_client_initialized",
            rate_limit=f"{rate_calls_per_minute}/min",
            timeout=timeout,
        )

    def close(self) -> None:
        """Close HTTP client and release resources."""
        self._client.close()
        logger.debug("polygon_client_closed", request_count=self.request_count)

    def _throttle(self) -> None:
        """Thread-safe rate limiting using sliding window.

        Blocks until a request slot is available based on configured rate limit.
        """
        with self._lock:
            now = time.monotonic()

            # If we've hit the rate limit, wait until oldest request is old enough
            if len(self._last_request_times) >= self._last_request_times.maxlen:  # type: ignore
                oldest = self._last_request_times[0]
                wait_for = 60.0 - (now - oldest)
                if wait_for > 0:
                    logger.debug("polygon_rate_limit_wait", wait_seconds=wait_for)
                    time.sleep(wait_for)
                    now = time.monotonic()

            self._last_request_times.append(now)

    @retry(  # type: ignore[misc]
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
            path: API path (e.g., "/v2/aggs/ticker/AAPL/range/1/day/...")
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            HTTPStatusError: On HTTP errors after retries exhausted
            RequestError: On network errors after retries exhausted
        """
        self._throttle()

        query: dict[str, Any] = dict(params or {})
        query["apiKey"] = self.api_key

        start_time = time.time()
        response = self._client.request(method.upper(), f"{self.BASE_URL}{path}", params=query)
        duration_ms = int((time.time() - start_time) * 1000)

        response.raise_for_status()
        self.request_count += 1

        logger.info(
            "polygon_request_success",
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

    def get_day_bars(
        self,
        ticker: str,
        from_date: str,
        to_date: str,
        adjusted: bool = True,
    ) -> dict[str, Any]:
        """Fetch daily OHLCV bars for a ticker.

        Args:
            ticker: Stock symbol (e.g., "AAPL")
            from_date: Start date (ISO format: "2024-01-01")
            to_date: End date (ISO format: "2024-12-31")
            adjusted: Whether to adjust for splits/dividends

        Returns:
            Dict with "results" key containing list of bar dicts

        Example:
            >>> client.get_day_bars("AAPL", "2024-01-01", "2024-01-31")
            {"results": [{"t": 1704067200000, "o": 184.35, ...}], "resultsCount": 20}
        """
        path = f"/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
        params = {
            "adjusted": "true" if adjusted else "false",
            "sort": "asc",
            "limit": 50000,
        }
        return self.get(path, params)

    def get_ticker_details(self, ticker: str) -> dict[str, Any]:
        """Fetch company details and metadata.

        Args:
            ticker: Stock symbol (e.g., "AAPL")

        Returns:
            Dict with "results" key containing company info

        Example:
            >>> client.get_ticker_details("AAPL")
            {"results": {"ticker": "AAPL", "name": "Apple Inc.", ...}}
        """
        path = f"/v3/reference/tickers/{ticker}"
        return self.get(path)

    def __del__(self) -> None:
        """Close client on garbage collection."""
        if hasattr(self, "_client"):
            self.close()


# Module-level singleton state
class _ClientState:
    """Holds singleton client instance."""

    client: PolygonClient | None = None
    lock = threading.Lock()


def get_client() -> PolygonClient:
    """Get or create the Polygon client singleton.

    Thread-safe lazy initialization.

    Returns:
        PolygonClient instance

    Raises:
        RuntimeError: If POLYGON_API_KEY not set
    """
    if _ClientState.client is None:
        with _ClientState.lock:
            # Double-check after acquiring lock
            if _ClientState.client is None:
                _ClientState.client = PolygonClient()
    return _ClientState.client
