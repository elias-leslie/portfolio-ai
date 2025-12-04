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
from ..sources import initialize_data_sources
from ..sources.base import DATASET_REFERENCE, DatasetRequest
from ..sources.multi_source_fetcher import MultiSourceFetcher
from ..storage import PortfolioStorage
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

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize price data fetcher.

        Args:
            storage: PortfolioStorage instance for caching and metrics
        """
        self.storage = storage
        self.cache_ttl_minutes = DEFAULT_PRICE_CACHE_TTL_MINUTES
        self._error_cache: dict[str, tuple[str, datetime]] = {}  # symbol -> (error, timestamp)
        self._error_cache_ttl_minutes = 5
        self.market_benchmark = os.getenv("PRICE_BENCHMARK_TICKER", "SPY")
        self.volatility_lookback_days = 90

        # Initialize multi-source fetcher using shared helper
        sources = initialize_data_sources()
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
        cutoff_time = datetime.now(UTC) - timedelta(minutes=self.cache_ttl_minutes)
        placeholders = ",".join(["?" for _ in symbols])

        df = self.storage.query(
            f"""
            SELECT symbol, price, beta, volatility, sector, bid, ask, bid_size, ask_size,
                   cached_at, source, error
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
            symbols=symbols,
            start=dt.date.today(),
            end=dt.date.today(),
            timezone="UTC",
        )

        df, errors_by_source = self.multi_source_fetcher.fetch_with_fallback(request, verbose=True)

        if df is not None and len(df) > 0:
            # Convert DataFrame to PriceData dict
            # Expected columns from YFinanceSource/PolygonSource reference data:
            # symbol, as_of_date, payload (JSON with price, sector, etc.), source
            for row in df.iter_rows(named=True):
                symbol = row["symbol"]
                source = row.get("source", "unknown")
                payload = row.get("payload", {})

                if isinstance(payload, str):
                    payload = json.loads(payload)

                # Extract price and metadata from payload
                price = payload.get("price", 0.0)
                sector = payload.get("sector")
                beta = payload.get("beta")
                volatility = payload.get("volatility")
                # Bid/ask data (GAP-029) - may be available from some sources
                bid = payload.get("bid")
                ask = payload.get("ask")
                bid_size = payload.get("bidSize") or payload.get("bid_size")
                ask_size = payload.get("askSize") or payload.get("ask_size")

                if price and price > 0:
                    result[symbol] = PriceData(
                        symbol=symbol,
                        price=float(price),
                        beta=float(beta) if beta else None,
                        volatility=float(volatility) if volatility else None,
                        sector=sector,
                        bid=float(bid) if bid else None,
                        ask=float(ask) if ask else None,
                        bid_size=int(bid_size) if bid_size else None,
                        ask_size=int(ask_size) if ask_size else None,
                        source=source,
                    )
                    logger.info(
                        "price_fetch_success",
                        symbol=symbol,
                        price=float(price),
                        source=source,
                        has_beta=beta is not None,
                        has_volatility=volatility is not None,
                        has_sector=sector is not None,
                    )
                else:
                    # No valid price data
                    error_msg = "No price data available"
                    result[symbol] = PriceData(
                        symbol=symbol,
                        price=0.0,
                        source=source,
                        error=error_msg,
                    )
                    logger.warning(
                        "price_fetch_no_data",
                        symbol=symbol,
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
            SELECT symbol, date, close
            FROM day_bars
            WHERE symbol IN (?, ?)
              AND date >= ?
            ORDER BY date ASC
            """,
            [symbol, self.market_benchmark, start_date.isoformat()],
        )

        if df.is_empty():
            return (None, None)

        try:
            symbol_df = (
                df.filter(pl.col("symbol") == symbol)
                .sort("date")
                .with_columns(pl.col("close").pct_change().alias("symbol_return"))
                .drop_nulls(["symbol_return"])
            )
            market_df = (
                df.filter(pl.col("symbol") == self.market_benchmark)
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
