"""FRED macroeconomic data source for agents.

Simplified FRED API integration for fetching economic indicators.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FREDSource:
    """Fetch macroeconomic indicators from the FRED API."""

    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    # Key economic indicators
    INDICATORS = {
        "VIX": "VIXCLS",  # Volatility Index
        "DXY": "DTWEXBGS",  # US Dollar Index
        "TNX": "GS10",  # 10-Year Treasury Rate
        "FEDFUNDS": "FEDFUNDS",  # Fed Funds Rate
        "CPI_YOY": "CPIAUCSL",  # Consumer Price Index
        "UNEMPLOYMENT": "UNRATE",  # Unemployment Rate
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

    def fetch_latest(self, indicator: str) -> dict[str, Any] | None:
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
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            if "observations" in data and data["observations"]:
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

    def fetch_multiple(self, indicators: list[str]) -> dict[str, dict[str, Any]]:
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
