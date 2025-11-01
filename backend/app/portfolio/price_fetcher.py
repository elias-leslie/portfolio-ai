"""Price data fetching with multi-source failover.

This module fetches price data using MultiSourceFetcher with YFinance and Polygon sources.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from datetime import UTC, datetime, timedelta
from math import sqrt

import numpy as np
import polars as pl

from ..constants import DEFAULT_PRICE_CACHE_TTL_MINUTES
from ..logging_config import get_logger
from ..sources.alphavantage_source import AlphaVantageSource
from ..sources.base import DATASET_REFERENCE, BaseSource, DatasetRequest
from ..sources.finnhub_source import FinnhubSource
from ..sources.fmp_source import FMPSource
from ..sources.multi_source_fetcher import MultiSourceFetcher
from ..sources.polygon_source import PolygonSource
from ..sources.twelvedata_source import TwelveDataSource
from ..sources.yfinance_source import YFinanceSource
from ..storage import DuckDBStorage
from .models import PriceData

logger = get_logger(__name__)


class PriceDataFetcher:
    """Fetches price data with caching and multi-source failover.

    Uses MultiSourceFetcher with up to 6 sources in priority order:
    1. YFinance (no API key needed)
    2. TwelveData
    3. FMP
    4. Polygon
    5. Finnhub
    6. AlphaVantage

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
        self.market_benchmark = os.getenv("PRICE_BENCHMARK_TICKER", "SPY")
        self.volatility_lookback_days = 90

        # Initialize multi-source fetcher with all available sources
        sources: list[BaseSource] = [YFinanceSource()]  # Priority 1, no key needed
        source_names = ["yfinance"]
        skipped_sources = []

        # Add TwelveData (Priority 2)
        if self._has_api_key("TWELVEDATA_API_KEY"):
            sources.append(TwelveDataSource())
            source_names.append("twelvedata")
        else:
            skipped_sources.append("twelvedata")

        # Add FMP (Priority 3)
        if self._has_api_key("FMP_API_KEY"):
            sources.append(FMPSource())
            source_names.append("fmp")
        else:
            skipped_sources.append("fmp")

        # Add Polygon (Priority 4)
        if self._has_api_key("POLYGON_API_KEY"):
            sources.append(PolygonSource())
            source_names.append("polygon")
        else:
            skipped_sources.append("polygon")

        # Add Finnhub (Priority 5)
        if self._has_api_key("FINNHUB_API_KEY"):
            sources.append(FinnhubSource())
            source_names.append("finnhub")
        else:
            skipped_sources.append("finnhub")

        # Add AlphaVantage (Priority 6)
        if self._has_api_key("ALPHAVANTAGE_API_KEY"):
            sources.append(AlphaVantageSource())
            source_names.append("alphavantage")
        else:
            skipped_sources.append("alphavantage")

        logger.info(
            "sources_initialized",
            count=len(sources),
            active_sources=source_names,
            skipped_sources=skipped_sources,
        )

        self.multi_source_fetcher = MultiSourceFetcher(sources, storage)

    def _has_api_key(self, key_name: str) -> bool:
        """Check if an API key is available in environment.

        Args:
            key_name: Name of the environment variable

        Returns:
            True if key exists and is non-empty, False otherwise
        """
        key_value = os.getenv(key_name)
        return bool(key_value and key_value.strip())

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
        cutoff_time = datetime.now(UTC) - timedelta(minutes=self.cache_ttl_minutes)
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

        # Augment metrics for any symbols missing beta or volatility
        for symbol, data in result.items():
            if data.price and (data.beta is None or data.volatility is None):
                beta, volatility = self._compute_local_risk_metrics(symbol)
                if beta is not None:
                    data.beta = beta
                if volatility is not None:
                    data.volatility = volatility

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

    def _compute_local_risk_metrics(self, symbol: str) -> tuple[float | None, float | None]:
        """Compute beta and volatility from local historical data."""
        start_date = datetime.now(UTC).date() - timedelta(days=self.volatility_lookback_days * 2)
        df = self.storage.query(
            """
            SELECT ticker, date, close
            FROM day_bars
            WHERE ticker IN (?, ?)
              AND date >= ?
            ORDER BY date ASC
            """,
            [symbol, self.market_benchmark, start_date],
        )

        if df.is_empty():
            return (None, None)

        try:
            symbol_df = (
                df.filter(pl.col("ticker") == symbol)
                .sort("date")
                .with_columns(pl.col("close").pct_change().alias("symbol_return"))
                .drop_nulls(["symbol_return"])
            )
            market_df = (
                df.filter(pl.col("ticker") == self.market_benchmark)
                .sort("date")
                .with_columns(pl.col("close").pct_change().alias("market_return"))
                .drop_nulls(["market_return"])
            )
        except pl.exceptions.ComputeError:
            return (None, None)

        if symbol_df.is_empty() or market_df.is_empty():
            return (None, None)

        joined = symbol_df.join(market_df, on="date", how="inner")
        if joined.height < 5:
            return (None, None)

        symbol_returns = joined["symbol_return"].to_numpy()
        market_returns = joined["market_return"].to_numpy()

        # Filter non-finite values
        mask = np.isfinite(symbol_returns) & np.isfinite(market_returns)
        symbol_returns = symbol_returns[mask]
        market_returns = market_returns[mask]

        if symbol_returns.size < 5 or market_returns.size < 5:
            return (None, None)

        # Volatility: annualized standard deviation of daily returns
        symbol_std = np.std(symbol_returns, ddof=1)
        volatility = float(symbol_std * sqrt(252))

        market_variance = float(np.var(market_returns, ddof=1))
        if market_variance == 0 or np.isnan(market_variance):
            beta = None
        else:
            covariance = float(np.cov(symbol_returns, market_returns, ddof=1)[0, 1])
            beta = covariance / market_variance

        return (beta, volatility)
