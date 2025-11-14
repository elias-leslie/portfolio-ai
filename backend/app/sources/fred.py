"""FRED macroeconomic data source for agents.

Simplified FRED API integration for fetching economic indicators.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, ClassVar

import httpx

from ..logging_config import get_logger

logger = get_logger(__name__)


class FREDSource:
    """Fetch macroeconomic indicators from the FRED API."""

    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    # Key economic indicators
    INDICATORS: ClassVar[dict[str, str]] = {
        "VIX": "VIXCLS",  # Volatility Index
        "DXY": "DTWEXBGS",  # US Dollar Index
        "TNX": "GS10",  # 10-Year Treasury Rate
        "FEDFUNDS": "FEDFUNDS",  # Fed Funds Rate
        "CPI_YOY": "CPIAUCSL",  # Consumer Price Index
        "UNEMPLOYMENT": "UNRATE",  # Unemployment Rate
        "HY_SPREAD": "BAMLH0A0HYM2",  # High-Yield Corporate Bond OAS (basis points)
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
