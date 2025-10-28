"""Price data fetching with multi-source failover.

This module fetches price data using MultiSourceFetcher with YFinance and Polygon sources.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from datetime import datetime, timedelta

import polars as pl

from ..constants import DEFAULT_PRICE_CACHE_TTL_MINUTES
from ..logging_config import get_logger
from ..sources.base import DATASET_REFERENCE, BaseSource, DatasetRequest
from ..sources.multi_source_fetcher import MultiSourceFetcher
from ..sources.polygon_source import PolygonSource
from ..sources.yfinance_source import YFinanceSource
from ..storage import DuckDBStorage
from .models import PriceData

logger = get_logger(__name__)


class PriceDataFetcher:
    """Fetches price data with caching and multi-source failover.

    Uses MultiSourceFetcher with YFinance (priority 1) and Polygon (priority 10) sources.
    Implements 15-minute cache TTL for price data.
    """

    def __init__(self, storage: DuckDBStorage) -> None:
        """Initialize price data fetcher.

        Args:
            storage: DuckDBStorage instance for caching and metrics
        """
        self.storage = storage
        self.cache_ttl_minutes = DEFAULT_PRICE_CACHE_TTL_MINUTES
        self._error_cache: dict[str, tuple[str, datetime]] = {}  # symbol -> (error, timestamp)
        self._error_cache_ttl_minutes = 5

        # Initialize multi-source fetcher with YFinance and optionally Polygon
        sources: list[BaseSource] = [YFinanceSource()]

        # Add Polygon source only if API key is available
        polygon_api_key = os.getenv("POLYGON_API_KEY")
        if polygon_api_key:
            sources.append(PolygonSource())
            logger.info("multi_source_initialized", sources=["yfinance", "polygon"])
        else:
            logger.info(
                "multi_source_initialized",
                sources=["yfinance"],
                note="Polygon disabled (no API key)",
            )

        self.multi_source_fetcher = MultiSourceFetcher(sources, storage)

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
            [*symbols, cutoff_time],
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
        """Fetch fresh price data using MultiSourceFetcher with automatic failover.

        Args:
            symbols: List of symbols to fetch

        Returns:
            Dictionary of PriceData
        """
        result = {}

        # Use MultiSourceFetcher for automatic priority-based failover
        request = DatasetRequest(
            dataset=DATASET_REFERENCE,
            profile=None,
            tickers=symbols,
            start=dt.date.today(),
            end=dt.date.today(),
            timezone="UTC",
        )

        df, errors_by_source = self.multi_source_fetcher.fetch_with_fallback(request, verbose=True)

        if df is not None and len(df) > 0:
            # Convert DataFrame to PriceData dict
            # Expected columns from YFinanceSource/PolygonSource reference data:
            # ticker, as_of_date, payload (JSON with price, sector, etc.), source
            for row in df.iter_rows(named=True):
                ticker = row["ticker"]
                source = row.get("source", "unknown")
                payload = row.get("payload", {})

                if isinstance(payload, str):
                    payload = json.loads(payload)

                # Extract price and metadata from payload
                price = payload.get("price", 0.0)
                sector = payload.get("sector")
                beta = payload.get("beta")
                volatility = payload.get("volatility")

                if price and price > 0:
                    result[ticker] = PriceData(
                        symbol=ticker,
                        price=float(price),
                        beta=float(beta) if beta else None,
                        volatility=float(volatility) if volatility else None,
                        sector=sector,
                        source=source,
                    )
                    logger.info(
                        "price_fetch_success",
                        symbol=ticker,
                        price=float(price),
                        source=source,
                        has_beta=beta is not None,
                        has_volatility=volatility is not None,
                        has_sector=sector is not None,
                    )
                else:
                    # No valid price data
                    error_msg = "No price data available"
                    result[ticker] = PriceData(
                        symbol=ticker,
                        price=0.0,
                        source=source,
                        error=error_msg,
                    )
                    logger.warning(
                        "price_fetch_no_data",
                        symbol=ticker,
                        error=error_msg,
                        source=source,
                    )
        else:
            # All sources failed
            for symbol in symbols:
                error_details = " | ".join(
                    [f"{src}: {', '.join(errs)}" for src, errs in errors_by_source.items()]
                )
                error_msg = (
                    f"All sources failed: {error_details}"
                    if error_details
                    else "All sources failed"
                )

                result[symbol] = PriceData(
                    symbol=symbol,
                    price=0.0,
                    source="multi_source",
                    error=error_msg,
                )
                logger.warning(
                    "price_fetch_all_sources_failed",
                    symbol=symbol,
                    errors=errors_by_source,
                )

        return result

    def _cache_prices(self, price_data: dict[str, PriceData]) -> None:
        """Cache price data to database.

        Args:
            price_data: Dictionary of PriceData to cache
        """
        if not price_data:
            return

        rows = []
        for _symbol, data in price_data.items():
            rows.append(data.model_dump())

        df = pl.DataFrame(rows)
        self.storage.insert_dataframe("price_cache", df, mode="append")

        logger.info(
            "prices_cached",
            num_cached=len(rows),
            symbols=list(price_data.keys()),
        )
