"""FRED macroeconomic data source for agents.

Simplified FRED API integration for fetching economic indicators.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import ClassVar

import httpx

from ..logging_config import get_logger
from .types import FREDDataDict

logger = get_logger(__name__)


class FREDSource:
    """Fetch macroeconomic indicators from the FRED API."""

    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    # Key economic indicators
    INDICATORS: ClassVar[dict[str, str]] = {
        # Volatility & Risk
        "VIX": "VIXCLS",  # Volatility Index
        "HY_SPREAD": "BAMLH0A0HYM2",  # High-Yield Corporate Bond OAS (basis points)
        # Currency
        "DXY": "DTWEXBGS",  # US Dollar Index
        # Treasury Yields (GAP-034: Yield Curve)
        "YIELD_3M": "DTB3",  # 3-Month T-Bill
        "YIELD_2Y": "DGS2",  # 2-Year Treasury
        "YIELD_5Y": "DGS5",  # 5-Year Treasury
        "YIELD_10Y": "DGS10",  # 10-Year Treasury
        "YIELD_30Y": "DGS30",  # 30-Year Treasury
        "TNX": "GS10",  # 10-Year Treasury (legacy alias)
        # Fed Policy (GAP-036)
        "FEDFUNDS": "FEDFUNDS",  # Fed Funds Rate
        "EFFR": "EFFR",  # Effective Fed Funds Rate (daily)
        # Inflation (GAP-035)
        "CPI": "CPIAUCSL",  # Consumer Price Index (monthly)
        "CPI_YOY": "CPIAUCSL",  # Alias for CPI
        "PCE": "PCEPI",  # Personal Consumption Expenditures
        "CORE_CPI": "CPILFESL",  # Core CPI (ex food & energy)
        "BREAKEVEN_5Y": "T5YIE",  # 5-Year Breakeven Inflation
        "BREAKEVEN_10Y": "T10YIE",  # 10-Year Breakeven Inflation
        # Employment
        "UNEMPLOYMENT": "UNRATE",  # Unemployment Rate
        "NONFARM_PAYROLLS": "PAYEMS",  # Total Nonfarm Payrolls
        # GDP & Growth
        "GDP": "GDP",  # Gross Domestic Product
        "REAL_GDP": "GDPC1",  # Real GDP
    }

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize FRED source.

        Args:
            api_key: FRED API key (or read from FRED_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        self.timeout = 15.0

    def is_enabled(self) -> bool:
        """Check if FRED API key is available."""
        return bool(self.api_key)

    def fetch_latest(self, indicator: str) -> FREDDataDict | None:
        """Fetch latest value for an indicator.

        Args:
            indicator: Indicator name (e.g., "VIX", "TNX")

        Returns:
            Dict with date and value, or None if failed
        """
        if not self.api_key:
            logger.warning("FRED API key not set")
            return None

        series_id = self.INDICATORS.get(indicator)
        if not series_id:
            logger.warning(f"Unknown indicator: {indicator}")
            return None

        try:
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 1,
            }

            response = httpx.get(
                self.BASE_URL,
                params=params,  # type: ignore[arg-type]  # httpx params typing - dict[str, object] is valid at runtime
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            if data.get("observations"):
                obs = data["observations"][0]
                return {
                    "indicator": indicator,
                    "series_id": series_id,
                    "date": obs.get("date"),
                    "value": float(obs.get("value", 0)),
                }

            return None

        except Exception as e:
            logger.error(f"Failed to fetch {indicator} from FRED: {e}")
            return None

    def fetch_multiple(self, indicators: list[str]) -> dict[str, FREDDataDict]:
        """Fetch latest values for multiple indicators.

        Args:
            indicators: List of indicator names

        Returns:
            Dict mapping indicator name to data dict
        """
        result = {}
        for indicator in indicators:
            data = self.fetch_latest(indicator)
            if data:
                result[indicator] = data

        return result

    def fetch_series(
        self,
        indicator: str,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
    ) -> list[tuple[date, float]]:
        """Fetch time series data for an indicator over a date range.

        Args:
            indicator: Indicator name (e.g., "HY_SPREAD", "VIX")
            start_date: Start date (inclusive), defaults to all available
            end_date: End date (inclusive), defaults to latest

        Returns:
            List of (date, value) tuples, sorted by date ascending.
            Missing values (FRED returns ".") are filtered out.
        """
        if not self.api_key:
            logger.warning("FRED API key not set")
            return []

        series_id = self.INDICATORS.get(indicator)
        if not series_id:
            logger.warning(f"Unknown indicator: {indicator}")
            return []

        try:
            params: dict[str, str | int] = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "asc",
            }

            # Add date filters if provided
            if start_date:
                if isinstance(start_date, str):
                    params["observation_start"] = start_date
                else:
                    params["observation_start"] = start_date.strftime("%Y-%m-%d")

            if end_date:
                if isinstance(end_date, str):
                    params["observation_end"] = end_date
                else:
                    params["observation_end"] = end_date.strftime("%Y-%m-%d")

            response = httpx.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            results = []

            if observations := data.get("observations"):
                for obs in observations:
                    # Skip missing values (FRED returns "." for missing data)
                    value_str = obs.get("value", "")
                    if value_str == "." or not value_str:
                        continue

                    try:
                        obs_date = datetime.strptime(obs["date"], "%Y-%m-%d").date()
                        value = float(value_str)
                        results.append((obs_date, value))
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Skipping invalid observation: {obs}, error: {e}")
                        continue

            logger.info(f"Fetched {len(results)} observations for {indicator} (series {series_id})")
            return results

        except Exception as e:
            logger.error(f"Failed to fetch {indicator} series from FRED: {e}")
            return []

    def get_latest_value(self, indicator: str) -> tuple[date, float] | None:
        """Get the most recent value for an indicator.

        Args:
            indicator: Indicator name (e.g., "HY_SPREAD", "VIX")

        Returns:
            Tuple of (date, value) or None if unavailable
        """
        data = self.fetch_latest(indicator)
        if not data:
            return None

        try:
            obs_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
            value = float(data["value"])
            return (obs_date, value)
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to parse latest value for {indicator}: {e}")
            return None

    def fetch_yield_curve(self, as_of_date: date | None = None) -> dict[str, float | None]:
        """Fetch complete yield curve data.

        Args:
            as_of_date: Date to fetch (default: latest available)

        Returns:
            Dict with yields and spreads
        """
        yields = {}
        indicators = ["YIELD_3M", "YIELD_2Y", "YIELD_5Y", "YIELD_10Y", "YIELD_30Y"]

        for indicator in indicators:
            data = self.fetch_latest(indicator)
            if data:
                yields[indicator.lower()] = data["value"]
            else:
                yields[indicator.lower()] = None

        # Calculate spreads
        y10 = yields.get("yield_10y")
        y2 = yields.get("yield_2y")
        y3m = yields.get("yield_3m")

        yields["spread_10y_2y"] = (y10 - y2) if y10 and y2 else None
        yields["spread_10y_3m"] = (y10 - y3m) if y10 and y3m else None
        yields["is_inverted"] = yields["spread_10y_2y"] < 0 if yields["spread_10y_2y"] else None

        return yields

    def fetch_inflation_data(self) -> dict[str, float | None]:
        """Fetch inflation-related indicators.

        Returns:
            Dict with CPI, PCE, breakeven rates
        """
        indicators = ["CPI", "CORE_CPI", "PCE", "BREAKEVEN_5Y", "BREAKEVEN_10Y"]
        result = {}

        for indicator in indicators:
            data = self.fetch_latest(indicator)
            if data:
                result[indicator.lower()] = data["value"]
            else:
                result[indicator.lower()] = None

        return result

    def fetch_fed_funds_data(self) -> dict[str, float | None]:
        """Fetch Fed funds rate data.

        Returns:
            Dict with fed funds rate and effective rate
        """
        result = {}

        for indicator in ["FEDFUNDS", "EFFR"]:
            data = self.fetch_latest(indicator)
            if data:
                result[indicator.lower()] = data["value"]
            else:
                result[indicator.lower()] = None

        return result
