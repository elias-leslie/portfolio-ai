"""Polygon API client with rate limiting and retry logic.

Adapted from market-sim for portfolio-ai.
"""

from __future__ import annotations

import threading
from typing import Any

from ..logging_config import get_logger
from .base_http_client import BaseHTTPClient

logger = get_logger(__name__)


class PolygonClient(BaseHTTPClient):
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
        timeout: float = 60.0,
    ) -> None:
        """Initialize Polygon client.

        Args:
            api_key: Polygon API key (defaults to POLYGON_API_KEY env var)
            timeout: Request timeout in seconds (default: 60)

        Raises:
            RuntimeError: If API key not provided and not in environment
        """
        super().__init__(api_key=api_key, rate_calls_per_minute=5, timeout=timeout)

    def get_api_key_env_var(self) -> str:
        """Return environment variable name for API key."""
        return "POLYGON_API_KEY"

    def get_client_name(self) -> str:
        """Return client name for logging."""
        return "polygon_client"

    def get_api_key_param_name(self) -> str:
        """Return query parameter name for API key."""
        return "apiKey"

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
