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
from collections.abc import Iterable
from contextlib import suppress
from typing import Any

import polars as pl

from ..logging_config import get_logger
from .base import BaseSource, DatasetRequest, standardize_dates
from .base_http_client import BaseHTTPClient

logger = get_logger(__name__)


class FMPClient(BaseHTTPClient):
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
        rate_calls_per_day: int | None = 250,
        timeout: float = 30.0,
    ) -> None:
        """Initialize FMP client.

        Args:
            api_key: FMP API key (defaults to FMP_API_KEY env var)
            rate_calls_per_day: Maximum requests per day (default: 250, None = no limit)
            timeout: Request timeout in seconds (default: 30)

        Raises:
            RuntimeError: If API key not provided and not in environment
        """
        super().__init__(api_key=api_key, rate_calls_per_day=rate_calls_per_day, timeout=timeout)

    def get_api_key_env_var(self) -> str:
        """Return environment variable name for API key."""
        return "FMP_API_KEY"

    def get_client_name(self) -> str:
        """Return client name for logging."""
        return "fmp_client"

    def get_api_key_param_name(self) -> str:
        """Return query parameter name for API key."""
        return "apikey"

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Execute GET request.

        Args:
            path: API path
            params: Query parameters

        Returns:
            Parsed JSON response (dict or list)
        """
        return self.request(path, params, method="GET")

    def get_historical_price(
        self,
        symbol: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, Any]:
        """Fetch historical daily OHLCV bars for a symbol.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            from_date: Start date (YYYY-MM-DD format, optional)
            to_date: End date (YYYY-MM-DD format, optional)

        Returns:
            Dict with "historical" key containing list of OHLCV dicts

        Example:
            >>> client.get_historical_price("AAPL", "2024-01-01", "2024-01-31")
            {"symbol": "AAPL", "historical": [{"date": "2024-01-31", "open": 184.35, ...}]}
        """
        path = f"/historical-price-full/{symbol}"
        params: dict[str, Any] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        result: dict[str, Any] = self.get(path, params)
        return result

    def get_profile(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch company profile and metadata.

        Args:
            symbol: Stock symbol (e.g., "AAPL")

        Returns:
            List with single dict containing company profile

        Example:
            >>> client.get_profile("AAPL")
            [{"symbol": "AAPL", "companyName": "Apple Inc", "sector": "Technology", ...}]
        """
        path = f"/profile/{symbol}"
        result: list[dict[str, Any]] = self.get(path)
        return result


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
            request: DatasetRequest with symbols, start, end dates

        Returns:
            Polars DataFrame with OHLCV data, or None if fetch fails
        """
        frames: list[pl.DataFrame] = []

        # Convert dates to date objects
        start_date, end_date = standardize_dates(request)

        logger.info(
            "fmp_fetch_day_bars_start",
            num_symbols=len(list(request.symbols)),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        for symbol in request.symbols:
            try:
                # Fetch historical data
                response = self.client.get_historical_price(
                    symbol=symbol,
                    from_date=start_date.isoformat(),
                    to_date=end_date.isoformat(),
                )

                # Check for error response
                if "Error Message" in response:
                    error_msg = response.get("Error Message", "Unknown error")
                    logger.warning(
                        "fmp_api_error",
                        symbol=symbol,
                        error=error_msg,
                    )
                    continue

                # Extract historical data
                historical = response.get("historical", [])
                if not historical:
                    logger.debug("fmp_no_data", symbol=symbol)
                    continue

                # Parse OHLCV data
                records = []
                for bar in historical:
                    try:
                        records.append(
                            {
                                "date": dt.date.fromisoformat(bar["date"]),
                                "symbol": symbol,
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
                            symbol=symbol,
                            bar=bar,
                            error=str(e),
                        )
                        continue

                if not records:
                    logger.debug("fmp_no_valid_bars", symbol=symbol)
                    continue

                # Create DataFrame
                df = pl.DataFrame(records)

                # Add ingest_run_id if provided
                if request.ingest_run_id:
                    df = df.with_columns(pl.lit(request.ingest_run_id).alias("ingest_run_id"))

                frames.append(df)

                logger.debug(
                    "fmp_fetch_success",
                    symbol=symbol,
                    rows=len(df),
                )

            except Exception as e:
                logger.warning(
                    "fmp_fetch_error",
                    symbol=symbol,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Continue to next symbol
                continue

        if not frames:
            logger.warning("fmp_no_data_fetched")
            return None

        # Combine all symbols
        combined = pl.concat(frames, how="vertical_relaxed")

        logger.info(
            "fmp_fetch_day_bars_complete",
            total_rows=len(combined),
            unique_symbols=combined["symbol"].n_unique(),
        )

        return combined

    def fetch_reference_payload(
        self, symbols: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Fetch company profile data from FMP.

        Args:
            symbols: List of symbols
            as_of: As-of date for reference data

        Returns:
            Polars DataFrame with reference data, or None if fetch fails
        """
        records = []

        logger.info(
            "fmp_fetch_reference_start",
            num_symbols=len(list(symbols)),
            as_of_date=as_of.isoformat(),
        )

        for symbol in symbols:
            try:
                response = self.client.get_profile(symbol)

                # Check for empty response
                if not response:
                    logger.warning(
                        "fmp_profile_api_error",
                        symbol=symbol,
                        error="No data",
                    )
                    continue

                # FMP returns a list with single profile dict
                profile = response[0]

                # Store profile as JSON string
                payload_json = json.dumps(profile)

                records.append(
                    {
                        "symbol": symbol,
                        "as_of_date": as_of,
                        "payload": payload_json,
                        "source": "fmp",
                    }
                )

                logger.debug("fmp_reference_fetched", symbol=symbol)

            except Exception as e:
                logger.warning(
                    "fmp_reference_error",
                    symbol=symbol,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                continue

        if not records:
            logger.warning("fmp_no_reference_data_fetched")
            return None

        logger.info(
            "fmp_reference_complete",
            num_symbols=len(records),
        )

        return pl.DataFrame(records)

    def fetch_news_payload(
        self, symbols: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles from FMP stock news endpoint."""
        records: list[dict[str, Any]] = []
        start_date = start.astimezone(dt.UTC).date().isoformat()
        end_date = end.astimezone(dt.UTC).date().isoformat()

        symbol_list = list(symbols) or ["__MARKET__"]
        for symbol in symbol_list:
            is_market = symbol in (None, "__MARKET__")
            params: dict[str, Any] = {
                "from": start_date,
                "to": end_date,
                "limit": 50,
            }
            if not is_market:
                params["symbols"] = symbol

            try:
                response = self.client.get("/stock_news", params)
            except Exception as exc:
                logger.warning(
                    "fmp_news_error",
                    symbol="__MARKET__" if is_market else symbol,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                continue

            items = response if isinstance(response, list) else []
            if not items:
                logger.debug(
                    "fmp_news_empty",
                    symbol="__MARKET__" if is_market else symbol,
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
                        "symbol": "__MARKET__" if is_market else (item.get("symbol") or symbol),
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
                symbol="__MARKET__" if is_market else symbol,
                articles=len(items),
            )

        if not records:
            logger.info("fmp_news_no_articles", symbols=list(symbol_list))
            return None

        return pl.DataFrame(records)
