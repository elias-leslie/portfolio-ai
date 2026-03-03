"""Price data fetching with multi-source failover.

This module fetches price data using MultiSourceFetcher with YFinance and Polygon sources.
"""

from __future__ import annotations

import datetime as dt
import os

from ..constants import DEFAULT_PRICE_CACHE_TTL_MINUTES
from ..logging_config import get_logger
from ..sources import initialize_data_sources
from ..sources.base import DATASET_REFERENCE, DatasetRequest
from ..sources.multi_source_fetcher import MultiSourceFetcher
from ..storage import PortfolioStorage
from ._payload_parser import build_all_sources_failed_entry, parse_payload_row
from ._price_cache import cache_prices, get_cached_prices
from ._risk_metrics import compute_local_risk_metrics
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
        self._error_cache: dict[str, tuple[str, dt.datetime]] = {}
        self._error_cache_ttl_minutes = 5
        self.market_benchmark = os.getenv("PRICE_BENCHMARK_TICKER", "SPY")
        self.volatility_lookback_days = 90

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

        cached_data = get_cached_prices(symbols, self.storage, self.cache_ttl_minutes)
        result.update(cached_data)

        missing_symbols = [s for s in symbols if s not in result]
        if missing_symbols:
            fresh_data = self._fetch_fresh_prices(missing_symbols)
            result.update(fresh_data)
            valid_data = {k: v for k, v in fresh_data.items() if v.price > 0 and not v.error}
            if valid_data:
                cache_prices(valid_data, self.storage)

        return result

    def _fetch_fresh_prices(self, symbols: list[str]) -> dict[str, PriceData]:
        """Fetch fresh price data using MultiSourceFetcher with automatic failover.

        Args:
            symbols: List of symbols to fetch

        Returns:
            Dictionary of PriceData
        """
        request = DatasetRequest(
            dataset=DATASET_REFERENCE,
            profile=None,
            symbols=symbols,
            start=dt.date.today(),
            end=dt.date.today(),
            timezone="UTC",
        )

        df, errors_by_source = self.multi_source_fetcher.fetch_with_fallback(request, verbose=True)

        result: dict[str, PriceData] = {}

        if df is not None and len(df) > 0:
            for row in df.iter_rows(named=True):
                parsed = parse_payload_row(row)
                result[parsed.symbol] = parsed

        # Handle symbols not in results (partial or complete failure)
        for symbol in symbols:
            if symbol not in result:
                result[symbol] = build_all_sources_failed_entry(symbol, errors_by_source)

        # Augment missing beta/volatility from local historical data
        for symbol, data in result.items():
            if data.price and (data.beta is None or data.volatility is None):
                beta, volatility = self._compute_local_risk_metrics(symbol)
                if beta is not None:
                    data.beta = beta
                if volatility is not None:
                    data.volatility = volatility

        return result

    def _compute_local_risk_metrics(self, symbol: str) -> tuple[float | None, float | None]:
        """Compute beta and volatility from local historical data."""
        return compute_local_risk_metrics(
            symbol,
            self.storage,
            market_benchmark=self.market_benchmark,
            volatility_lookback_days=self.volatility_lookback_days,
        )
