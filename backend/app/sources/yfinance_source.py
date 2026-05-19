"""YFinance data source adapter.

Implements BaseSource interface for yfinance library with support for
daily OHLCV data and company reference information.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Any

import polars as pl

from .base import BaseSource, DatasetRequest
from .yfinance_fetchers import (
    fetch_all_fundamental_data,
    fetch_cash_flow_data,
    fetch_day_bars,
    fetch_insider_transactions,
    fetch_institutional_holders,
    fetch_news_payload,
    fetch_quarterly_fundamentals,
    fetch_reference_payload,
    fetch_sector_history,
    fetch_short_interest,
)


class YFinanceSource(BaseSource):
    """YFinance data source adapter.

    Free tier with no API key required.
    Note: yfinance has quirks - delays of 0.5-2s between requests recommended.
    """

    name = "yfinance"
    priority = 1  # Highest priority (free, no rate limits for basic usage)
    supports_day = True
    supports_reference = True
    supports_news = True

    MARKET_SYMBOL = "^GSPC"

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        """Fetch daily OHLCV bars from yfinance.

        Args:
            request: DatasetRequest with symbols, start, end dates

        Returns:
            Polars DataFrame with OHLCV data, or None if fetch fails
        """
        return fetch_day_bars(request)

    def fetch_reference_payload(
        self, symbols: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Fetch company reference data from yfinance.

        Args:
            symbols: Iterable of stock symbols
            as_of: Date for reference data

        Returns:
            Polars DataFrame with reference data, or None if fetch fails
        """
        return fetch_reference_payload(symbols, as_of)

    def fetch_news_payload(
        self, symbols: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles using yfinance's symbol news feed.

        Args:
            symbols: Iterable of stock symbols
            start: Start datetime for news
            end: End datetime for news

        Returns:
            Polars DataFrame with news articles, or None if fetch fails
        """
        return fetch_news_payload(symbols, start, end)

    # ============================================
    # GAP-004: Cash Flow Metrics
    # ============================================
    def fetch_cash_flow_data(self, symbol: str) -> dict[str, Any] | None:
        """Fetch cash flow statement data for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with cash flow metrics, or None if failed
        """
        return fetch_cash_flow_data(symbol)

    # ============================================
    # GAP-006: Insider Transactions
    # ============================================
    def fetch_insider_transactions(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch insider transactions for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            List of insider transaction dicts
        """
        return fetch_insider_transactions(symbol)

    # ============================================
    # GAP-007: Institutional Holdings
    # ============================================
    def fetch_institutional_holders(
        self, symbol: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Fetch institutional holders for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Tuple of (list of holder dicts, summary dict)
        """
        return fetch_institutional_holders(symbol)

    # ============================================
    # GAP-011: Short Interest
    # ============================================
    def fetch_short_interest(self, symbol: str) -> dict[str, Any] | None:
        """Fetch short interest data for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with short interest metrics, or None if failed
        """
        return fetch_short_interest(symbol)

    # ============================================
    # Combined fundamental data fetch
    # ============================================
    def fetch_all_fundamental_data(self, symbol: str) -> dict[str, Any]:
        """Fetch all fundamental data for a symbol in one call.

        Combines cash flow, insider, institutional, and short data.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with all fundamental data
        """
        return fetch_all_fundamental_data(symbol)

    def fetch_quarterly_fundamentals(self, symbol: str) -> dict[str, Any] | None:
        """Pull 4-8 quarters of income/balance/cashflow + derived ratios.

        Used by the L3 fan-out fetcher on each Tier-1 survivor. Separate
        from ``fetch_all_fundamental_data`` because it returns the
        spec field bundle (margins, ROE/ROIC, D/E, YoY growth) rather
        than a per-table aggregation tuned for the weekly cron.
        """
        return fetch_quarterly_fundamentals(symbol)

    def fetch_sector_history(
        self,
        symbol: str,
        start_date: dt.date,
        end_date: dt.date,
    ) -> list[tuple[dt.date, float]]:
        """Fetch historical close prices for a sector ETF.

        Args:
            symbol: Sector ETF symbol (e.g., "XLK", "XLF")
            start_date: Start date for history
            end_date: End date for history

        Returns:
            List of (date, close_price) tuples, empty if no data available
        """
        return fetch_sector_history(symbol, start_date, end_date)
