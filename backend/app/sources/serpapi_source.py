"""SerpAPI source adapter for Google Finance and Google Trends data.

Provides access to:
- Google Finance: Quote data, financials, price info
- Google Trends: Search volume interest over time (sentiment proxy)

Rate limits:
- Free tier: 100 searches/month
- Paid: $50/month for 5000 searches
"""

from __future__ import annotations

import datetime as dt
import os
import threading
from typing import Any

import polars as pl

from ..logging_config import get_logger
from .base_http_client import BaseHTTPClient

logger = get_logger(__name__)


# Exchange mappings for Google Finance query format
EXCHANGE_MAPPINGS = {
    "NYSE": "NYSE",
    "NASDAQ": "NASDAQ",
    "AMEX": "AMEX",
    "NYQ": "NYSE",
    "NMS": "NASDAQ",
    "NGM": "NASDAQ",
}


class SerpAPIClient(BaseHTTPClient):
    """Synchronous SerpAPI REST client with rate limiting.

    Features:
    - Thread-safe rate limiting
    - Automatic retries with exponential backoff
    - Support for Google Finance and Google Trends engines
    """

    BASE_URL = "https://serpapi.com"

    def __init__(
        self,
        api_key: str | None = None,
        rate_calls_per_minute: int | None = 10,  # Conservative for free tier
        timeout: float = 30.0,
    ) -> None:
        """Initialize SerpAPI client.

        Args:
            api_key: SerpAPI key (defaults to SERPAPI_API_KEY env var)
            rate_calls_per_minute: Max requests per minute (default: 10)
            timeout: Request timeout in seconds (default: 30)

        Raises:
            RuntimeError: If API key not provided and not in environment
        """
        super().__init__(
            api_key=api_key, rate_calls_per_minute=rate_calls_per_minute, timeout=timeout
        )

    def get_api_key_env_var(self) -> str:
        """Return environment variable name for API key."""
        return "SERPAPI_API_KEY"

    def get_client_name(self) -> str:
        """Return client name for logging."""
        return "serpapi_client"

    def get_api_key_param_name(self) -> str:
        """Return query parameter name for API key."""
        return "api_key"

    def get_google_finance(self, symbol: str, exchange: str | None = None) -> dict[str, Any]:
        """Fetch Google Finance data for a stock symbol.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            exchange: Exchange name (e.g., "NASDAQ"). Auto-detected if not provided.

        Returns:
            Dict with Google Finance data including summary, financials, news

        Example:
            >>> client.get_google_finance("AAPL", "NASDAQ")
            {"summary": {"price": 150.0, ...}, "financials": {...}, ...}
        """
        # Format query as SYMBOL:EXCHANGE
        exchange_code = EXCHANGE_MAPPINGS.get(exchange or "", exchange or "NASDAQ")
        query = f"{symbol}:{exchange_code}"

        params = {
            "engine": "google_finance",
            "q": query,
        }

        result: dict[str, Any] = self.request("/search", params, method="GET")
        return result

    def get_google_trends(
        self,
        query: str,
        date_range: str = "today 3-m",
        geo: str = "US",
    ) -> dict[str, Any]:
        """Fetch Google Trends interest over time data.

        Args:
            query: Search term (e.g., "AAPL stock", "Tesla")
            date_range: Time range (default: "today 3-m" for last 3 months)
                Options: "now 1-H", "now 4-H", "now 1-d", "now 7-d",
                        "today 1-m", "today 3-m", "today 12-m", "today 5-y"
            geo: Geographic region (default: "US")

        Returns:
            Dict with interest_over_time, related_topics, related_queries

        Example:
            >>> client.get_google_trends("AAPL stock")
            {"interest_over_time": {"timeline_data": [...]}, ...}
        """
        params = {
            "engine": "google_trends",
            "q": query,
            "date": date_range,
            "geo": geo,
            "data_type": "TIMESERIES",
        }

        result: dict[str, Any] = self.request("/search", params, method="GET")
        return result


# Module-level singleton state
class _ClientState:
    """Holds singleton client instance."""

    client: SerpAPIClient | None = None
    lock = threading.Lock()


def get_client() -> SerpAPIClient:
    """Get or create the SerpAPI client singleton.

    Thread-safe lazy initialization.

    Returns:
        SerpAPIClient instance

    Raises:
        RuntimeError: If SERPAPI_API_KEY not set
    """
    if _ClientState.client is None:
        with _ClientState.lock:
            if _ClientState.client is None:
                _ClientState.client = SerpAPIClient()
    return _ClientState.client


def is_serpapi_enabled() -> bool:
    """Check if SerpAPI is configured (API key present)."""
    return os.getenv("SERPAPI_API_KEY") is not None


def fetch_google_finance_quote(symbol: str, exchange: str | None = None) -> dict[str, Any] | None:
    """Fetch Google Finance quote data for a symbol.

    Args:
        symbol: Stock symbol
        exchange: Optional exchange code

    Returns:
        Dict with quote data or None if not available
    """
    if not is_serpapi_enabled():
        logger.debug("serpapi_not_configured")
        return None

    try:
        client = get_client()
        response = client.get_google_finance(symbol, exchange)

        # Extract summary/quote data
        summary = response.get("summary", {})
        financials = response.get("financials", {})
        graph = response.get("graph", [])

        if not summary:
            logger.debug("serpapi_no_summary", symbol=symbol)
            return None

        result = {
            "symbol": symbol,
            "source": "serpapi_google_finance",
            "price": summary.get("price"),
            "currency": summary.get("currency"),
            "change": summary.get("price_movement", {}).get("value"),
            "change_percent": summary.get("price_movement", {}).get("percentage"),
            "market_cap": financials.get("market_cap"),
            "pe_ratio": financials.get("pe_ratio"),
            "dividend_yield": financials.get("dividend_yield"),
            "52_week_high": financials.get("52_week_high"),
            "52_week_low": financials.get("52_week_low"),
            "graph_data": graph,
            "raw_response": response,
            "fetched_at": dt.datetime.now(tz=dt.UTC).isoformat(),
        }

        logger.info("serpapi_finance_fetched", symbol=symbol)
        return result

    except Exception as e:
        logger.warning(
            "serpapi_finance_error",
            symbol=symbol,
            error=str(e),
            error_type=type(e).__name__,
        )
        return None


def fetch_google_trends(
    query: str,
    date_range: str = "today 3-m",
    geo: str = "US",
) -> dict[str, Any] | None:
    """Fetch Google Trends interest data for a search term.

    Args:
        query: Search term (e.g., "AAPL stock")
        date_range: Time range (default: last 3 months)
        geo: Geographic region (default: US)

    Returns:
        Dict with trends data or None if not available
    """
    if not is_serpapi_enabled():
        logger.debug("serpapi_not_configured")
        return None

    try:
        client = get_client()
        response = client.get_google_trends(query, date_range, geo)

        interest_over_time = response.get("interest_over_time", {})
        timeline_data = interest_over_time.get("timeline_data", [])

        if not timeline_data:
            logger.debug("serpapi_no_trends_data", query=query)
            return None

        # Parse timeline data into structured format
        data_points = []
        for point in timeline_data:
            date_str = point.get("date", "")
            values = point.get("values", [])
            if values:
                # Get the first value (primary query)
                extracted_value = values[0].get("extracted_value", 0)
                data_points.append({"date": date_str, "interest": extracted_value})

        result = {
            "query": query,
            "source": "serpapi_google_trends",
            "geo": geo,
            "date_range": date_range,
            "data_points": data_points,
            "average_interest": sum(p["interest"] for p in data_points) / len(data_points)
            if data_points
            else 0,
            "max_interest": max((p["interest"] for p in data_points), default=0),
            "related_topics": response.get("related_topics", {}),
            "related_queries": response.get("related_queries", {}),
            "raw_response": response,
            "fetched_at": dt.datetime.now(tz=dt.UTC).isoformat(),
        }

        logger.info("serpapi_trends_fetched", query=query, data_points=len(data_points))
        return result

    except Exception as e:
        logger.warning(
            "serpapi_trends_error",
            query=query,
            error=str(e),
            error_type=type(e).__name__,
        )
        return None


def fetch_stock_trends(symbol: str, date_range: str = "today 3-m") -> dict[str, Any] | None:
    """Fetch Google Trends data specifically for a stock symbol.

    Convenience function that searches for "{symbol} stock".

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        date_range: Time range (default: last 3 months)

    Returns:
        Dict with trends data or None if not available
    """
    query = f"{symbol} stock"
    result = fetch_google_trends(query, date_range)
    if result:
        result["symbol"] = symbol
    return result


def get_trends_dataframe(symbols: list[str], date_range: str = "today 3-m") -> pl.DataFrame | None:
    """Fetch Google Trends data for multiple symbols and return as DataFrame.

    Args:
        symbols: List of stock symbols
        date_range: Time range for trends data

    Returns:
        Polars DataFrame with trends data or None if no data
    """
    if not is_serpapi_enabled():
        return None

    records = []
    for symbol in symbols:
        trends = fetch_stock_trends(symbol, date_range)
        if trends:
            records.append(
                {
                    "symbol": symbol,
                    "average_interest": trends.get("average_interest", 0),
                    "max_interest": trends.get("max_interest", 0),
                    "data_points_count": len(trends.get("data_points", [])),
                    "fetched_at": trends.get("fetched_at"),
                }
            )

    if not records:
        return None

    return pl.DataFrame(records)
