"""Base HTTP client with rate limiting and retry logic.

Provides common HTTP client functionality for all API sources including:
- Automatic retries with exponential backoff
- Thread-safe rate limiting (per-minute and/or per-day)
- Request tracking and logging

This eliminates 1,469 lines of duplicate code across 5 API clients.
"""

from __future__ import annotations

import os
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ..constants import DEFAULT_HTTP_TIMEOUT
from ..logging_config import get_logger

logger = get_logger(__name__)


def should_retry_http_exception(exc: BaseException) -> bool:
    """Determine if exception should trigger a retry.

    Retries on:
    - 429 (rate limit)
    - 500, 502, 503, 504 (server errors)
    - Network errors (timeout, connection errors)

    Args:
        exc: Exception to evaluate

    Returns:
        True if exception should trigger a retry, False otherwise
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else None
        return status in {429, 500, 502, 503, 504}
    return isinstance(exc, httpx.RequestError)


class RateLimiter:
    """Thread-safe rate limiter using sliding window algorithm.

    Supports per-minute AND/OR per-day limits. Can enforce both simultaneously.
    """

    def __init__(
        self,
        calls_per_minute: int | None = None,
        calls_per_day: int | None = None,
    ) -> None:
        """Initialize rate limiter.

        Args:
            calls_per_minute: Maximum requests per minute (None = no minute limit)
            calls_per_day: Maximum requests per day (None = no day limit)

        Raises:
            ValueError: If both limits are None
        """
        if calls_per_minute is None and calls_per_day is None:
            raise ValueError("At least one of calls_per_minute or calls_per_day must be set")

        self._calls_per_minute = calls_per_minute
        self._calls_per_day = calls_per_day
        self._lock = threading.Lock()

        # Track requests in last minute (if minute limit set)
        if calls_per_minute:
            self._minute_requests: deque[float] = deque(maxlen=calls_per_minute)
        else:
            self._minute_requests = deque()

        # Track requests in last 24 hours (if day limit set)
        if calls_per_day:
            self._day_requests: deque[float] = deque(maxlen=calls_per_day)
        else:
            self._day_requests = deque()

    def throttle(self, source_name: str) -> None:
        """Enforce rate limits. Blocks or raises error if limit exceeded.

        Args:
            source_name: Client name for logging

        Raises:
            RuntimeError: If daily limit exceeded (doesn't block 24h in practice)
        """
        with self._lock:
            now = time.monotonic()

            # Check per-minute limit
            if self._calls_per_minute is not None:
                self._enforce_limit(
                    source_name=source_name,
                    requests=self._minute_requests,
                    limit=self._calls_per_minute,
                    window_seconds=60.0,
                    window_name="minute",
                    now=now,
                )

            # Check per-day limit
            if self._calls_per_day is not None:
                self._enforce_limit(
                    source_name=source_name,
                    requests=self._day_requests,
                    limit=self._calls_per_day,
                    window_seconds=86400.0,  # 24 hours
                    window_name="day",
                    now=now,
                )

    def _enforce_limit(
        self,
        source_name: str,
        requests: deque[float],
        limit: int,
        window_seconds: float,
        window_name: str,
        now: float,
    ) -> None:
        """Enforce a single rate limit (minute or day).

        Args:
            source_name: Client name for logging
            requests: Deque of request timestamps
            limit: Maximum requests in window
            window_seconds: Window size in seconds (60 or 86400)
            window_name: "minute" or "day" for logging
            now: Current time (monotonic)

        Raises:
            RuntimeError: If limit exceeded and window is "day" (doesn't block 24h)
        """
        # Remove requests older than window
        cutoff_time = now - window_seconds
        while requests and requests[0] < cutoff_time:
            requests.popleft()

        # If we've hit the limit, wait (minute) or raise (day)
        if len(requests) >= limit:
            oldest = requests[0]
            wait_for = window_seconds - (now - oldest)
            if wait_for > 0:
                if window_name == "minute":
                    # For per-minute limits, actually wait
                    logger.debug(
                        f"{source_name}_rate_limit_wait",
                        wait_seconds=wait_for,
                        limit=f"{limit}/{window_name}",
                    )
                    time.sleep(wait_for)
                    now = time.monotonic()
                else:
                    # For per-day limits, raise error (don't block 24h)
                    logger.warning(
                        f"{source_name}_rate_limit_hit",
                        wait_seconds=wait_for,
                        limit=f"{limit}/{window_name}",
                    )
                    # Use "daily" for user-facing error message
                    window_display = "daily" if window_name == "day" else window_name
                    raise RuntimeError(
                        f"{source_name} {window_display} rate limit ({limit} calls) exceeded. "
                        f"Reset in {wait_for:.0f} seconds"
                    )

        # Record this request
        requests.append(now)


class BaseHTTPClient(ABC):
    """Abstract base class for HTTP API clients with rate limiting and retries.

    Provides:
    - Thread-safe rate limiting (per-minute and/or per-day)
    - Automatic retries with exponential backoff
    - Request tracking and logging
    - Standardized error handling

    Subclasses must implement:
    - get_api_key_env_var(): Return env var name for API key
    - get_client_name(): Return client name for logging
    - get_api_key_param_name(): Return query param name for API key
    - BASE_URL (class attribute): API base URL
    """

    BASE_URL: str  # Must be set by subclass

    def __init__(
        self,
        api_key: str | None = None,
        rate_calls_per_minute: int | None = None,
        rate_calls_per_day: int | None = None,
        timeout: float = DEFAULT_HTTP_TIMEOUT,
    ) -> None:
        """Initialize HTTP client.

        Args:
            api_key: API key (defaults to env var from get_api_key_env_var())
            rate_calls_per_minute: Maximum requests per minute (None = no limit)
            rate_calls_per_day: Maximum requests per day (None = no limit)
            timeout: Request timeout in seconds (default: 30)

        Raises:
            RuntimeError: If API key not provided and not in environment
        """
        # Get API key from parameter or environment
        env_var = self.get_api_key_env_var()
        self.api_key = api_key or os.getenv(env_var)
        if not self.api_key:
            raise RuntimeError(f"{env_var} is not set")

        # Initialize HTTP client
        self._client = httpx.Client(timeout=timeout)

        # Initialize rate limiter
        self._rate_limiter = RateLimiter(
            calls_per_minute=rate_calls_per_minute,
            calls_per_day=rate_calls_per_day,
        )

        # Track request count for monitoring
        self.request_count = 0

        # Log initialization
        client_name = self.get_client_name()
        rate_info = []
        if rate_calls_per_minute:
            rate_info.append(f"{rate_calls_per_minute}/min")
        if rate_calls_per_day:
            rate_info.append(f"{rate_calls_per_day}/day")

        logger.info(
            f"{client_name}_initialized",
            rate_limit=" + ".join(rate_info) if rate_info else "none",
            timeout=timeout,
        )

    @abstractmethod
    def get_api_key_env_var(self) -> str:
        """Return environment variable name for API key.

        Returns:
            Environment variable name (e.g., "FMP_API_KEY")
        """
        pass

    @abstractmethod
    def get_client_name(self) -> str:
        """Return client name for logging.

        Returns:
            Client name (e.g., "fmp_client")
        """
        pass

    @abstractmethod
    def get_api_key_param_name(self) -> str:
        """Return query parameter name for API key.

        Returns:
            Parameter name (e.g., "apikey" for FMP, "token" for Finnhub)
        """
        pass

    def close(self) -> None:
        """Close HTTP client and release resources."""
        self._client.close()
        client_name = self.get_client_name()
        logger.debug("http_client_closed", client=client_name, request_count=self.request_count)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, max=30),
        retry=retry_if_exception(should_retry_http_exception),
        reraise=True,
    )
    def request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        method: str = "GET",
    ) -> Any:
        """Execute HTTP request with rate limiting and retries.

        Args:
            endpoint: API endpoint path (e.g., "/historical-price-full/AAPL")
            params: Query parameters (API key will be added automatically)
            method: HTTP method (default: GET)

        Returns:
            Parsed JSON response (can be dict or list)

        Raises:
            HTTPStatusError: On HTTP errors after retries exhausted
            RequestError: On network errors after retries exhausted
        """
        # Enforce rate limit
        client_name = self.get_client_name()
        self._rate_limiter.throttle(client_name)

        # Build query parameters and add API key
        query = dict(params or {})
        api_key_param = self.get_api_key_param_name()
        query[api_key_param] = self.api_key

        # Make request
        start_time = time.time()
        url = f"{self.BASE_URL}{endpoint}"
        response = self._client.request(method.upper(), url, params=query)
        duration_ms = int((time.time() - start_time) * 1000)

        # Check for HTTP errors
        response.raise_for_status()
        self.request_count += 1

        # Log success
        logger.info(
            f"{client_name}_request_success",
            method=method.upper(),
            endpoint=endpoint,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_count=self.request_count,
        )

        return response.json()

    def __del__(self) -> None:
        """Close client on garbage collection."""
        if hasattr(self, "_client"):
            self.close()
