"""Fundamental data source implementations with multi-source failover.

This module provides multiple data sources for fetching company fundamentals:
1. YFinance (free, no API key needed)
2. Finnhub (requires FINNHUB_API_KEY environment variable)
3. Financial Modeling Prep (requires FMP_API_KEY environment variable)

Sources are tried in priority order with automatic failover.
"""

from __future__ import annotations

import os

import requests

from app.logging_config import get_logger
from app.watchlist.fundamentals_models import BaseFundamentalSource, FundamentalData

logger = get_logger(__name__)

try:
    import yfinance as yf

    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


class YFinanceSource(BaseFundamentalSource):
    """YFinance fundamental data source (free, no API key)."""

    def fetch_fundamentals(self, symbol: str) -> FundamentalData | None:
        """Fetch fundamentals from YFinance.

        Args:
            symbol: Stock symbol

        Returns:
            FundamentalData if successful, None if failed
        """
        if not YFINANCE_AVAILABLE:
            return None

        try:
            yf_obj = yf.Ticker(symbol)
            info = yf_obj.info

            # Extract and convert fields
            profit_margin = info.get("profitMargins")
            revenue_growth = info.get("revenueGrowth")

            # Convert debt-to-equity from percentage to decimal
            debt_to_equity_pct = info.get("debtToEquity")
            debt_to_equity = debt_to_equity_pct / 100.0 if debt_to_equity_pct is not None else None

            recommendation_key = info.get("recommendationKey")
            recommendation_mean = info.get("recommendationMean")
            target_mean_price = info.get("targetMeanPrice")

            return FundamentalData(
                symbol=symbol,
                profit_margin=profit_margin,
                revenue_growth=revenue_growth,
                debt_to_equity=debt_to_equity,
                recommendation_key=recommendation_key,
                recommendation_mean=recommendation_mean,
                target_mean_price=target_mean_price,
            )
        except Exception as e:
            logger.debug("yfinance_fundamentals_failed", symbol=symbol, error=str(e))
            return None


class FinnhubSource(BaseFundamentalSource):
    """Finnhub fundamental data source (requires API key)."""

    def __init__(self, api_key: str) -> None:
        """Initialize Finnhub source.

        Args:
            api_key: Finnhub API key
        """
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"

    def fetch_fundamentals(self, symbol: str) -> FundamentalData | None:
        """Fetch fundamentals from Finnhub.

        Args:
            symbol: Stock symbol

        Returns:
            FundamentalData if successful, None if failed
        """
        try:
            url = f"{self.base_url}/stock/metric"
            params = {"symbol": symbol, "metric": "all", "token": self.api_key}

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            metric = data.get("metric", {})

            # Extract and convert fields (Finnhub returns percentages)
            # Use TTM (trailing twelve months) fields for most current data
            profit_margin_pct = metric.get("netProfitMarginTTM") or metric.get(
                "netProfitMarginAnnual"
            )
            profit_margin = profit_margin_pct / 100.0 if profit_margin_pct is not None else None

            # Use 3-year growth as proxy for recent growth rate
            revenue_growth_pct = metric.get("revenueGrowth3Y") or metric.get("revenueGrowth5Y")
            revenue_growth = revenue_growth_pct / 100.0 if revenue_growth_pct is not None else None

            # Use long-term debt to equity ratio
            debt_to_equity = metric.get("longTermDebt/equityAnnual") or metric.get(
                "longTermDebt/equityQuarterly"
            )

            return FundamentalData(
                symbol=symbol,
                profit_margin=profit_margin,
                revenue_growth=revenue_growth,
                debt_to_equity=debt_to_equity,
            )
        except Exception as e:
            logger.debug("finnhub_fundamentals_failed", symbol=symbol, error=str(e))
            return None


class FMPSource(BaseFundamentalSource):
    """Financial Modeling Prep fundamental data source (requires API key)."""

    def __init__(self, api_key: str) -> None:
        """Initialize FMP source.

        Args:
            api_key: FMP API key
        """
        self.api_key = api_key
        self.base_url = "https://financialmodelingprep.com/api/v3"

    def fetch_fundamentals(self, symbol: str) -> FundamentalData | None:
        """Fetch fundamentals from FMP.

        Args:
            symbol: Stock symbol

        Returns:
            FundamentalData if successful, None if failed
        """
        try:
            url = f"{self.base_url}/ratios/{symbol}"
            params = {"apikey": self.api_key}

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # FMP returns array, take most recent (first item)
            if not data or len(data) == 0:
                return None

            ratios = data[0]

            # Extract fields (FMP returns decimals, not percentages)
            profit_margin = ratios.get("netProfitMargin")
            revenue_growth = ratios.get("revenueGrowth")
            debt_to_equity = ratios.get("debtEquityRatio")

            return FundamentalData(
                symbol=symbol,
                profit_margin=profit_margin,
                revenue_growth=revenue_growth,
                debt_to_equity=debt_to_equity,
            )
        except Exception as e:
            logger.debug("fmp_fundamentals_failed", symbol=symbol, error=str(e))
            return None


def fetch_fundamentals(symbol: str) -> FundamentalData | None:
    """Fetch fundamental data with multi-source failover.

    Tries sources in order:
    1. YFinance (free)
    2. Finnhub (if API key available)
    3. FMP (if API key available)

    Args:
        symbol: Stock symbol

    Returns:
        FundamentalData if any source succeeds, None if all fail
    """
    # Try YFinance first (free, no API key)
    yfinance_source = YFinanceSource()
    result = yfinance_source.fetch_fundamentals(symbol)
    if result is not None:
        return result

    # Try Finnhub if API key available
    finnhub_key = os.environ.get("FINNHUB_API_KEY")
    if finnhub_key:
        finnhub_source = FinnhubSource(api_key=finnhub_key)
        result = finnhub_source.fetch_fundamentals(symbol)
        if result is not None:
            return result

    # Try FMP if API key available
    fmp_key = os.environ.get("FMP_API_KEY")
    if fmp_key:
        fmp_source = FMPSource(api_key=fmp_key)
        result = fmp_source.fetch_fundamentals(symbol)
        if result is not None:
            return result

    # All sources failed
    return None
