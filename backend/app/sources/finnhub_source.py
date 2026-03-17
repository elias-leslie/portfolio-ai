"""Finnhub API source adapter with rate limiting.

Implements BaseSource interface for Finnhub API with support for
daily OHLCV data and company profile information.

Rate limits:
- Free tier: 60 API calls per minute
"""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
from collections.abc import Iterable
from typing import Any

import polars as pl

from ..constants import DEFAULT_HTTP_TIMEOUT
from ..logging_config import get_logger
from .base import BaseSource, DatasetRequest, standardize_dates
from .base_http_client import BaseHTTPClient

logger = get_logger(__name__)


class FinnhubClient(BaseHTTPClient):
    """Synchronous Finnhub REST API client with rate limiting.

    Features:
    - Thread-safe rate limiting (60 requests/min)
    - Automatic retries with exponential backoff
    - Request tracking for performance monitoring
    """

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(
        self,
        api_key: str | None = None,
        rate_calls_per_minute: int | None = 60,
        timeout: float = DEFAULT_HTTP_TIMEOUT,
    ) -> None:
        """Initialize Finnhub client.

        Args:
            api_key: Finnhub API key (defaults to FINNHUB_API_KEY env var)
            rate_calls_per_minute: Maximum requests per minute (default: 60, None = no limit)
            timeout: Request timeout in seconds (default: 30)

        Raises:
            RuntimeError: If API key not provided and not in environment
        """
        super().__init__(
            api_key=api_key, rate_calls_per_minute=rate_calls_per_minute, timeout=timeout
        )

    def get_api_key_env_var(self) -> str:
        """Return environment variable name for API key."""
        return "FINNHUB_API_KEY"

    def get_client_name(self) -> str:
        """Return client name for logging."""
        return "finnhub_client"

    def get_api_key_param_name(self) -> str:
        """Return query parameter name for API key."""
        return "token"

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Execute GET request.

        Args:
            path: API path
            params: Query parameters

        Returns:
            Parsed JSON response (dict or list)
        """
        return self.request(path, params, method="GET")

    def get_candles(
        self,
        symbol: str,
        resolution: str = "D",
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
    ) -> dict[str, Any]:
        """Fetch historical candles (OHLCV) for a symbol.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            resolution: Time resolution (D = daily)
            from_timestamp: Start timestamp (Unix seconds)
            to_timestamp: End timestamp (Unix seconds)

        Returns:
            Dict with "c", "h", "l", "o", "t", "v" keys for close, high, low, open, time, volume

        Example:
            >>> client.get_candles("AAPL", "D", 1704067200, 1706745600)
            {"c": [184.35, ...], "h": [186.5, ...], "l": [183.8, ...], ...}
        """
        params: dict[str, Any] = {
            "symbol": symbol,
            "resolution": resolution,
        }
        if from_timestamp:
            params["from"] = from_timestamp
        if to_timestamp:
            params["to"] = to_timestamp

        result: dict[str, Any] = self.get("/stock/candle", params)
        return result

    def get_company_profile(self, symbol: str) -> dict[str, Any]:
        """Fetch company profile and metadata.

        Args:
            symbol: Stock symbol (e.g., "AAPL")

        Returns:
            Dict with company profile information

        Example:
            >>> client.get_company_profile("AAPL")
            {"name": "Apple Inc", "symbol": "AAPL", "country": "US", ...}
        """
        params = {"symbol": symbol}
        result: dict[str, object] = self.get("/stock/profile2", params)
        return result


# Module-level singleton state
class _ClientState:
    """Holds singleton client instance."""

    client: FinnhubClient | None = None
    lock = threading.Lock()


def get_client() -> FinnhubClient:
    """Get or create the Finnhub client singleton.

    Thread-safe lazy initialization.

    Returns:
        FinnhubClient instance

    Raises:
        RuntimeError: If FINNHUB_API_KEY not set
    """
    if _ClientState.client is None:
        with _ClientState.lock:
            # Double-check after acquiring lock
            if _ClientState.client is None:
                _ClientState.client = FinnhubClient()
    return _ClientState.client


class FinnhubSource(BaseSource):
    """Finnhub source adapter implementing BaseSource interface.

    Priority: 10 (same as Polygon - medium priority)
    Rate limits: 60 calls/min
    """

    name = "finnhub"
    priority = 10  # Same as Polygon - medium priority
    supports_day = True
    supports_reference = True
    supports_news = True

    def __init__(self) -> None:
        """Initialize Finnhub source."""
        self.client = get_client()
        logger.info("finnhub_source_initialized")

    def is_enabled(self) -> bool:
        """Check if Finnhub API key is configured."""
        return os.getenv("FINNHUB_API_KEY") is not None

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        """Fetch daily OHLCV bars from Finnhub.

        Args:
            request: DatasetRequest with symbols, start, end dates

        Returns:
            Polars DataFrame with OHLCV data, or None if fetch fails
        """
        frames: list[pl.DataFrame] = []

        # Convert dates to date objects
        start_date, end_date = standardize_dates(request)

        # Convert to Unix timestamps
        from_ts = int(dt.datetime.combine(start_date, dt.time.min).timestamp())
        to_ts = int(dt.datetime.combine(end_date, dt.time.max).timestamp())

        logger.info(
            "finnhub_fetch_day_bars_start",
            num_symbols=len(list(request.symbols)),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        for symbol in request.symbols:
            try:
                # Fetch candle data
                response = self.client.get_candles(
                    symbol=symbol,
                    resolution="D",
                    from_timestamp=from_ts,
                    to_timestamp=to_ts,
                )

                # Check for error response
                if response.get("s") == "no_data":
                    logger.debug("finnhub_no_data", symbol=symbol)
                    continue

                # Extract OHLCV arrays
                closes = response.get("c", [])
                highs = response.get("h", [])
                lows = response.get("l", [])
                opens = response.get("o", [])
                timestamps = response.get("t", [])
                volumes = response.get("v", [])

                if not closes or len(closes) == 0:
                    logger.debug("finnhub_empty_data", symbol=symbol)
                    continue

                # Parse OHLCV data
                records = []
                for i, (ts, o, h, lo, c, v) in enumerate(
                    zip(timestamps, opens, highs, lows, closes, volumes, strict=False)
                ):
                    try:
                        bar_date = dt.datetime.fromtimestamp(ts, tz=dt.UTC).date()
                        records.append(
                            {
                                "date": bar_date,
                                "symbol": symbol,
                                "open": float(o),
                                "high": float(h),
                                "low": float(lo),
                                "close": float(c),
                                "volume": int(v),
                                "vwap": None,  # Finnhub doesn't provide VWAP
                                "source": "finnhub",
                            }
                        )
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            "finnhub_bar_parse_error",
                            symbol=symbol,
                            index=i,
                            error=str(e),
                        )
                        continue

                if not records:
                    logger.debug("finnhub_no_valid_bars", symbol=symbol)
                    continue

                # Create DataFrame
                df = pl.DataFrame(records)

                # Add ingest_run_id if provided
                if request.ingest_run_id:
                    df = df.with_columns(pl.lit(request.ingest_run_id).alias("ingest_run_id"))

                frames.append(df)

                logger.debug(
                    "finnhub_fetch_success",
                    symbol=symbol,
                    rows=len(df),
                )

            except Exception as e:
                logger.warning(
                    "finnhub_fetch_error",
                    symbol=symbol,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Continue to next symbol
                continue

        if not frames:
            logger.warning("finnhub_no_data_fetched")
            return None

        # Combine all symbols
        combined = pl.concat(frames, how="vertical_relaxed")

        logger.info(
            "finnhub_fetch_day_bars_complete",
            total_rows=len(combined),
            unique_symbols=combined["symbol"].n_unique(),
        )

        return combined

    def fetch_reference_payload(
        self, symbols: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Fetch company profile data from Finnhub.

        Args:
            symbols: List of symbols
            as_of: As-of date for reference data

        Returns:
            Polars DataFrame with reference data, or None if fetch fails
        """
        records = []

        logger.info(
            "finnhub_fetch_reference_start",
            num_symbols=len(list(symbols)),
            as_of_date=as_of.isoformat(),
        )

        for symbol in symbols:
            try:
                response = self.client.get_company_profile(symbol)

                # Check for empty response
                if not response or not response.get("name"):
                    logger.debug("finnhub_no_reference_data", symbol=symbol)
                    continue

                # Store profile as JSON string
                payload_json = json.dumps(response)

                records.append(
                    {
                        "symbol": symbol,
                        "as_of_date": as_of,
                        "payload": payload_json,
                        "source": "finnhub",
                    }
                )

                logger.debug("finnhub_reference_fetched", symbol=symbol)

            except Exception as e:
                logger.warning(
                    "finnhub_reference_error",
                    symbol=symbol,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                continue

        if not records:
            logger.warning("finnhub_no_reference_data_fetched")
            return None

        logger.info(
            "finnhub_reference_complete",
            num_symbols=len(records),
        )

        return pl.DataFrame(records)

    def fetch_news_payload(
        self, symbols: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles from Finnhub company-news and general news endpoints."""
        records: list[dict[str, Any]] = []
        start_date = start.astimezone(dt.UTC).date().isoformat()
        end_date = end.astimezone(dt.UTC).date().isoformat()

        symbol_list = list(symbols) or ["__MARKET__"]

        for symbol in symbol_list:
            is_market = symbol in (None, "__MARKET__")
            try:
                if is_market:
                    response = self.client.get("/news", {"category": "general"})
                else:
                    response = self.client.get(
                        "/company-news",
                        {"symbol": symbol, "from": start_date, "to": end_date},
                    )
            except Exception as exc:
                logger.warning(
                    "finnhub_news_error",
                    symbol="__MARKET__" if is_market else symbol,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                continue

            items = response if isinstance(response, list) else []
            if not items:
                logger.debug(
                    "finnhub_news_empty",
                    symbol="__MARKET__" if is_market else symbol,
                )
                continue

            for item in items:
                headline = item.get("headline") or item.get("title")
                if not headline:
                    continue

                published_at = None
                published_raw = item.get("datetime") or item.get("published_at")
                if isinstance(published_raw, (int, float)):
                    published_at = dt.datetime.fromtimestamp(float(published_raw), tz=dt.UTC)
                elif isinstance(published_raw, str):
                    try:
                        published_at = dt.datetime.fromisoformat(
                            published_raw.replace("Z", "+00:00")
                        )
                    except ValueError:
                        published_at = None

                records.append(
                    {
                        "symbol": "__MARKET__" if is_market else symbol,
                        "headline": headline,
                        "url": item.get("url"),
                        "summary": item.get("summary"),
                        "news_source_name": item.get("source"),
                        "author": item.get("author"),
                        "image_url": item.get("image"),
                        "published_at": published_at,
                        "raw_payload": json.dumps(item),
                        "source": "finnhub",
                    }
                )

            logger.debug(
                "finnhub_news_fetched",
                symbol="__MARKET__" if is_market else symbol,
                articles=len(items),
            )

        if not records:
            logger.info("finnhub_news_no_articles", symbols=list(symbol_list))
            return None

        return pl.DataFrame(records)
