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
from ..utils.market_hours import get_market_status
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

    def fetch_price_data(
        self,
        symbols: list[str],
        *,
        force_refresh: bool = False,
        max_age_minutes: int | None = None,
    ) -> dict[str, PriceData]:
        """Fetch price data for multiple symbols with caching.

        Args:
            symbols: List of stock symbols
            force_refresh: When True, skip the cache and fetch fresh vendor data.
            max_age_minutes: Optional age cutoff for cache hits. Defaults to
                the market-session-aware TTL.

        Returns:
            Dictionary mapping symbol to PriceData
        """
        unique_symbols = self._normalize_symbols(symbols)
        if not unique_symbols:
            return {}

        result: dict[str, PriceData] = {}

        if not force_refresh:
            cache_ttl_minutes = (
                self._cache_ttl_minutes() if max_age_minutes is None else max_age_minutes
            )
            cached_data = get_cached_prices(
                unique_symbols, self.storage, cache_ttl_minutes
            )
            result.update(cached_data)

        missing_symbols = [s for s in unique_symbols if s not in result]
        if missing_symbols:
            fresh_data = self._fetch_fresh_prices(missing_symbols)
            result.update(fresh_data)
            valid_data = {k: v for k, v in fresh_data.items() if v.price > 0 and not v.error}
            if valid_data:
                cache_prices(valid_data, self.storage)

        return result

    def fetch_cached_price_data(
        self,
        symbols: list[str],
        *,
        max_age_minutes: int | None = 24 * 60,
    ) -> dict[str, PriceData]:
        """Return cached prices only.

        Read APIs use this to keep page loads bounded. Background refresh jobs
        own external quote fetching; if cache is empty, callers surface missing
        or stale data instead of blocking on vendor fallbacks.
        """
        return get_cached_prices(self._normalize_symbols(symbols), self.storage, max_age_minutes)

    def _get_cached_prices(
        self,
        symbols: list[str],
        cache_ttl_minutes: int | None = None,
    ) -> dict[str, PriceData]:
        """Compatibility wrapper for older tests and local callers."""
        ttl = self._cache_ttl_minutes() if cache_ttl_minutes is None else cache_ttl_minutes
        return get_cached_prices(self._normalize_symbols(symbols), self.storage, ttl)

    def _cache_prices(self, price_data: dict[str, PriceData]) -> None:
        """Compatibility wrapper for older tests and local callers."""
        cache_prices(price_data, self.storage)

    @staticmethod
    def _normalize_symbols(symbols: list[str]) -> list[str]:
        """Normalize symbols once at the quote boundary."""
        return list(
            dict.fromkeys(
                str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()
            )
        )

    def _cache_ttl_minutes(self) -> int:
        market_status = get_market_status()
        if market_status == "open":
            return 2
        if market_status in {"pre_market", "after_hours"}:
            return 5
        return max(self.cache_ttl_minutes, 30)

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
