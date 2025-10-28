"""Price data fetching with multi-source failover.

This module fetches price data using yfinance as primary and Polygon as backup.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from http.client import RemoteDisconnected
from json import JSONDecodeError
from urllib.error import HTTPError, URLError

import polars as pl
import yfinance as yf
from requests.exceptions import ConnectionError, ReadTimeout, Timeout
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..constants import DEFAULT_PRICE_CACHE_TTL_MINUTES
from ..logging_config import get_logger
from ..storage import DuckDBStorage
from .models import PriceData

logger = get_logger(__name__)


class PriceDataFetcher:
    """Fetches price data with caching and multi-source failover.

    Uses yfinance as primary source and Polygon as backup.
    Implements 15-minute cache TTL.
    """

    def __init__(self, storage: DuckDBStorage) -> None:
        """Initialize price data fetcher.

        Args:
            storage: DuckDBStorage instance for caching
        """
        self.storage = storage
        self.cache_ttl_minutes = DEFAULT_PRICE_CACHE_TTL_MINUTES
        self.polygon_api_key = os.getenv("POLYGON_API_KEY")
        self._error_cache: dict[str, tuple[str, datetime]] = {}  # symbol -> (error, timestamp)
        self._error_cache_ttl_minutes = 5

    def fetch_price_data(self, symbols: list[str]) -> dict[str, PriceData]:
        """Fetch price data for multiple symbols with caching.

        Args:
            symbols: List of stock symbols

        Returns:
            Dictionary mapping symbol to PriceData
        """
        result: dict[str, PriceData] = {}

        # Check cache first
        cached_data = self._get_cached_prices(symbols)
        result.update(cached_data)

        # Fetch missing symbols
        missing_symbols = [s for s in symbols if s not in result]

        if missing_symbols:
            fresh_data = self._fetch_fresh_prices(missing_symbols)
            result.update(fresh_data)

            # Cache the fresh data
            self._cache_prices(fresh_data)

        return result

    def _get_cached_prices(self, symbols: list[str]) -> dict[str, PriceData]:
        """Get cached prices that are still valid.

        Args:
            symbols: List of symbols to check

        Returns:
            Dictionary of cached PriceData
        """
        if not symbols:
            return {}

        # Query cache for recent prices
        cutoff_time = datetime.now() - timedelta(minutes=self.cache_ttl_minutes)
        placeholders = ",".join(["?" for _ in symbols])

        df = self.storage.query(
            f"""
            SELECT symbol, price, beta, volatility, sector, cached_at, source, error
            FROM price_cache
            WHERE symbol IN ({placeholders})
              AND cached_at >= ?
            ORDER BY symbol, cached_at DESC
            """,
            symbols + [cutoff_time],
        )

        if df.is_empty():
            return {}

        # Get most recent entry per symbol
        df = df.group_by("symbol").agg(pl.all().first())

        result = {}
        for row in df.iter_rows(named=True):
            result[row["symbol"]] = PriceData(**row)

        logger.info(
            "cache_hit",
            num_cached=len(result),
            symbols=list(result.keys()),
            cache_hit=True,
        )
        return result

    def _fetch_fresh_prices(self, symbols: list[str]) -> dict[str, PriceData]:
        """Fetch fresh price data from yfinance (primary) or Polygon (backup).

        Args:
            symbols: List of symbols to fetch

        Returns:
            Dictionary of PriceData
        """
        result = {}

        # Try yfinance first
        yfinance_data = self._fetch_from_yfinance(symbols)
        result.update(yfinance_data)

        # Fallback to Polygon for failed symbols
        failed_symbols = [s for s in symbols if s not in result]
        if failed_symbols and self.polygon_api_key:
            logger.info(
                "polygon_failover",
                num_failed=len(failed_symbols),
                symbols=failed_symbols,
                source="polygon",
            )
            polygon_data = self._fetch_from_polygon(failed_symbols)
            result.update(polygon_data)
        elif failed_symbols:
            logger.warning(
                "no_polygon_api_key",
                num_failed=len(failed_symbols),
                symbols=failed_symbols,
            )

        return result

    def _fetch_from_yfinance(self, symbols: list[str]) -> dict[str, PriceData]:
        """Fetch price data from yfinance.

        Args:
            symbols: List of symbols

        Returns:
            Dictionary of PriceData
        """
        result = {}

        for symbol in symbols:
            # Check error cache first to avoid retry storms
            if symbol in self._error_cache:
                cached_error, cached_at = self._error_cache[symbol]
                if datetime.now() - cached_at < timedelta(minutes=self._error_cache_ttl_minutes):
                    logger.debug(
                        "error_cache_hit",
                        symbol=symbol,
                        error=cached_error,
                        cached_at=cached_at.isoformat(),
                    )
                    result[symbol] = PriceData(
                        symbol=symbol,
                        price=0.0,
                        source="yfinance",
                        error=cached_error,
                    )
                    continue
                else:
                    # Error cache expired, remove it
                    del self._error_cache[symbol]

            # Try to fetch with retry logic
            price_data = self._fetch_single_symbol_with_retry(symbol)
            if price_data:
                result[symbol] = price_data

        return result

    @retry(
        retry=retry_if_exception_type((Timeout, ReadTimeout, ConnectionError, RemoteDisconnected)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _fetch_single_symbol_with_retry(self, symbol: str) -> PriceData | None:
        """Fetch a single symbol with retry logic for transient errors.

        Args:
            symbol: Stock symbol to fetch

        Returns:
            PriceData if successful, None otherwise
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Get current price
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if not price:
                error_msg = "No price data available"
                logger.warning(
                    "price_fetch_no_data",
                    symbol=symbol,
                    error=error_msg,
                    source="yfinance",
                )
                # Cache this error (permanent - don't retry)
                self._error_cache[symbol] = (error_msg, datetime.now())
                return PriceData(
                    symbol=symbol,
                    price=0.0,
                    source="yfinance",
                    error=error_msg,
                )

            # Get beta (market risk)
            beta = info.get("beta")

            # Get volatility (approximate from 52-week range if available)
            volatility = None
            if "fiftyTwoWeekHigh" in info and "fiftyTwoWeekLow" in info:
                high = info["fiftyTwoWeekHigh"]
                low = info["fiftyTwoWeekLow"]
                if high and low and high > 0:
                    volatility = (high - low) / high

            # Get sector
            sector = info.get("sector")

            price_data = PriceData(
                symbol=symbol,
                price=float(price),
                beta=float(beta) if beta else None,
                volatility=float(volatility) if volatility else None,
                sector=sector,
                source="yfinance",
            )

            logger.info(
                "price_fetch_success",
                symbol=symbol,
                price=float(price),
                source="yfinance",
                has_beta=beta is not None,
                has_volatility=volatility is not None,
                has_sector=sector is not None,
            )
            return price_data

        except HTTPError as e:
            # HTTP errors - check status code
            status_code = getattr(e, "code", None)
            if status_code == 404:
                error_msg = f"Symbol not found (404)"
                logger.warning(
                    "price_fetch_http_error",
                    symbol=symbol,
                    error=error_msg,
                    status_code=404,
                    source="yfinance",
                )
                # Cache this error (permanent - invalid symbol)
                self._error_cache[symbol] = (error_msg, datetime.now())
                return PriceData(
                    symbol=symbol,
                    price=0.0,
                    source="yfinance",
                    error=error_msg,
                )
            elif status_code == 429:
                error_msg = f"Rate limit exceeded (429)"
                logger.warning(
                    "price_fetch_rate_limit",
                    symbol=symbol,
                    error=error_msg,
                    status_code=429,
                    source="yfinance",
                    will_retry=True,
                )
                # Don't cache - let retry logic handle it
                raise  # Retry on rate limits
            else:
                error_msg = f"HTTP error {status_code}"
                logger.warning(
                    "price_fetch_http_error",
                    symbol=symbol,
                    error=error_msg,
                    status_code=status_code,
                    source="yfinance",
                )
                self._error_cache[symbol] = (error_msg, datetime.now())
                return PriceData(
                    symbol=symbol,
                    price=0.0,
                    source="yfinance",
                    error=error_msg,
                )

        except (Timeout, ReadTimeout, ConnectionError, RemoteDisconnected) as e:
            # Transient network errors - retry
            error_msg = f"Network error: {type(e).__name__}"
            logger.warning(
                "price_fetch_network_error",
                symbol=symbol,
                error=error_msg,
                error_type=type(e).__name__,
                source="yfinance",
                will_retry=True,
            )
            raise  # Retry these errors

        except JSONDecodeError as e:
            # Malformed response
            error_msg = "Invalid JSON response"
            logger.warning(
                "price_fetch_json_error",
                symbol=symbol,
                error=error_msg,
                source="yfinance",
            )
            self._error_cache[symbol] = (error_msg, datetime.now())
            return PriceData(
                symbol=symbol,
                price=0.0,
                source="yfinance",
                error=error_msg,
            )

        except KeyError as e:
            # Missing expected field
            error_msg = f"Missing field: {e}"
            logger.warning(
                "price_fetch_key_error",
                symbol=symbol,
                error=error_msg,
                missing_field=str(e),
                source="yfinance",
            )
            self._error_cache[symbol] = (error_msg, datetime.now())
            return PriceData(
                symbol=symbol,
                price=0.0,
                source="yfinance",
                error=error_msg,
            )

        except Exception as e:
            # Catch-all for unexpected errors
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            logger.error(
                "price_fetch_unexpected_error",
                symbol=symbol,
                error=error_msg,
                error_type=type(e).__name__,
                source="yfinance",
            )
            self._error_cache[symbol] = (error_msg, datetime.now())
            return PriceData(
                symbol=symbol,
                price=0.0,
                source="yfinance",
                error=error_msg,
            )

    def _fetch_from_polygon(self, symbols: list[str]) -> dict[str, PriceData]:
        """Fetch price data from Polygon API.

        Args:
            symbols: List of symbols

        Returns:
            Dictionary of PriceData
        """
        # Placeholder for Polygon implementation
        # Will be implemented when Polygon integration is needed
        logger.info(
            "polygon_not_implemented",
            symbols=symbols,
            num_symbols=len(symbols),
            source="polygon",
        )
        return {}

    def _cache_prices(self, price_data: dict[str, PriceData]) -> None:
        """Cache price data to database.

        Args:
            price_data: Dictionary of PriceData to cache
        """
        if not price_data:
            return

        rows = []
        for symbol, data in price_data.items():
            rows.append(data.model_dump())

        df = pl.DataFrame(rows)
        self.storage.insert_dataframe("price_cache", df, mode="append")

        logger.info(
            "prices_cached",
            num_cached=len(rows),
            symbols=list(price_data.keys()),
        )
