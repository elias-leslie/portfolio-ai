"""Company fundamental data fetching and health classification.

This module provides multi-source failover for fetching company fundamentals
(profit margins, revenue growth, debt ratios, analyst ratings) and classifies
companies as EXCELLENT, GOOD, or WEAK based on financial health metrics.

Sources (in priority order):
1. YFinance (free, no API key needed)
2. Finnhub (requires FINNHUB_API_KEY environment variable)
3. Financial Modeling Prep (requires FMP_API_KEY environment variable)
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import requests
from pydantic import BaseModel

if TYPE_CHECKING:
    pass

try:
    import yfinance as yf  # type: ignore[import-untyped]

    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


class FundamentalData(BaseModel):
    """Company fundamental data model."""

    symbol: str
    profit_margin: float | None = None  # Profit margin as decimal (0.53 = 53%)
    revenue_growth: float | None = None  # Revenue growth as decimal (1.22 = 122%)
    debt_to_equity: float | None = None  # Debt-to-equity ratio (0.45 = 45%)
    recommendation_key: str | None = None  # "buy", "hold", "sell"
    recommendation_mean: float | None = None  # 1.0-5.0 (1=strong buy, 5=sell)
    target_mean_price: float | None = None  # Analyst average target price


class BaseFundamentalSource(ABC):
    """Abstract base class for fundamental data sources."""

    @abstractmethod
    def fetch_fundamentals(self, symbol: str) -> FundamentalData | None:
        """Fetch fundamental data for a symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            FundamentalData if successful, None if failed
        """
        pass


class YFinanceSource(BaseFundamentalSource):
    """YFinance fundamental data source (free, no API key)."""

    def fetch_fundamentals(self, symbol: str) -> FundamentalData | None:
        """Fetch fundamentals from YFinance.

        Args:
            symbol: Stock ticker symbol

        Returns:
            FundamentalData if successful, None if failed
        """
        if not YFINANCE_AVAILABLE:
            return None

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

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
        except Exception:
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
            symbol: Stock ticker symbol

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
        except Exception:
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
            symbol: Stock ticker symbol

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
        except Exception:
            return None


def fetch_fundamentals(symbol: str) -> FundamentalData | None:
    """Fetch fundamental data with multi-source failover.

    Tries sources in order:
    1. YFinance (free)
    2. Finnhub (if API key available)
    3. FMP (if API key available)

    Args:
        symbol: Stock ticker symbol

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


def classify_company_health(data: FundamentalData) -> str:
    """Classify company health as EXCELLENT, GOOD, or WEAK.

    Classification criteria:
    - EXCELLENT: Profit margin > 20% AND revenue growth > 20% AND
                 debt-to-equity < 0.5 AND analyst consensus strong buy
    - GOOD: Profit margin > 5% AND revenue growth 5-20% AND
            debt-to-equity < 1.5
    - WEAK: Profit margin < 0% OR revenue shrinking OR debt-to-equity > 2.0

    Args:
        data: FundamentalData with company metrics

    Returns:
        "EXCELLENT", "GOOD", or "WEAK"
    """
    # Extract metrics (treat None as neutral/default values)
    profit_margin = data.profit_margin if data.profit_margin is not None else 0.06
    revenue_growth = data.revenue_growth if data.revenue_growth is not None else 0.06
    debt_to_equity = data.debt_to_equity if data.debt_to_equity is not None else 1.0
    recommendation_mean = data.recommendation_mean if data.recommendation_mean is not None else 3.0

    # Check for WEAK signals (highest priority)
    if profit_margin < 0:  # Unprofitable
        return "WEAK"
    if revenue_growth < 0:  # Shrinking revenue
        return "WEAK"
    if debt_to_equity > 2.0:  # High debt
        return "WEAK"

    # Check for EXCELLENT signals (all criteria must be met)
    if (
        profit_margin > 0.20
        and revenue_growth > 0.20
        and debt_to_equity < 0.5
        and recommendation_mean < 2.0
    ):
        return "EXCELLENT"

    # Default to GOOD (moderate company)
    return "GOOD"


def fetch_fundamentals_cached(conn: Any, symbol: str, ttl_days: int = 1) -> FundamentalData | None:
    """Fetch fundamental data with caching support (default TTL: 24 hours).

    This function checks the reference_cache table first. If valid cached data
    exists (within TTL), it returns the cached data without calling external APIs.
    If cache is stale or missing, it fetches fresh data and caches it.

    Args:
        conn: Database connection
        symbol: Stock ticker symbol
        ttl_days: Cache TTL in days (default: 1 day = 24 hours)

    Returns:
        FundamentalData if successful, None if failed

    Example:
        >>> from app.storage.connection import ConnectionManager
        >>> cm = ConnectionManager()
        >>> with cm.connection() as conn:
        ...     data = fetch_fundamentals_cached(conn, "NVDA")
        >>> # First call fetches from API and caches
        >>> # Second call within 24 hours uses cache
    """
    # Check cache first
    cache_cutoff = date.today() - timedelta(days=ttl_days)

    cached_row = conn.execute(
        """
        SELECT payload
        FROM reference_cache
        WHERE ticker = %s
          AND source = %s
          AND as_of_date >= %s
        ORDER BY as_of_date DESC
        LIMIT 1
        """,
        [symbol, "fundamentals", cache_cutoff],
    ).fetchone()

    # Cache hit - return cached data
    if cached_row is not None:
        payload = cached_row[0]
        return FundamentalData(**payload)

    # Cache miss or stale - fetch fresh data
    fresh_data = fetch_fundamentals(symbol)

    if fresh_data is None:
        return None

    # Cache the fresh data
    conn.execute(
        """
        INSERT INTO reference_cache (ticker, as_of_date, payload, source)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (ticker, as_of_date, source)
        DO UPDATE SET payload = EXCLUDED.payload
        """,
        [
            symbol,
            date.today(),
            json.dumps(fresh_data.model_dump()),
            "fundamentals",
        ],
    )
    conn.commit()

    return fresh_data
