"""CBOE Most Active Options data source.

Scrapes CBOE Most Active Options page for market positioning intelligence.
Data source: https://www.cboe.com/us/options/market_statistics/most_active/

Provides aggregated daily metrics (not raw contract data):
- Sentiment: % of calls vs puts
- Time horizon: % near-term vs far-term
- Concentration: % in top 5 vs all top 25
- Sector distribution: % by sector
"""

from __future__ import annotations

import datetime as dt
import json
import time
import urllib.request
from typing import TYPE_CHECKING, Any
from urllib.error import URLError

from ..logging_config import get_logger
from .source_metrics_manager import SourceMetricsManager

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)

# Simple sector mapping for common symbols
# Expanded mapping can be added as needed
SECTOR_MAP = {
    # Technology
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "GOOGL": "Technology",
    "GOOG": "Technology",
    "META": "Technology",
    "TSLA": "Technology",
    "AMD": "Technology",
    "INTC": "Technology",
    "CSCO": "Technology",
    # Financials
    "JPM": "Financials",
    "BAC": "Financials",
    "WFC": "Financials",
    "GS": "Financials",
    "MS": "Financials",
    "C": "Financials",
    # Healthcare
    "JNJ": "Healthcare",
    "UNH": "Healthcare",
    "PFE": "Healthcare",
    "ABBV": "Healthcare",
    "TMO": "Healthcare",
    # Consumer
    "AMZN": "Consumer Discretionary",
    "HD": "Consumer Discretionary",
    "MCD": "Consumer Discretionary",
    "NKE": "Consumer Discretionary",
    "SBUX": "Consumer Discretionary",
    "WMT": "Consumer Staples",
    "PG": "Consumer Staples",
    "KO": "Consumer Staples",
    # Indexes & ETFs
    "SPY": "Indexes & ETFs",
    "QQQ": "Indexes & ETFs",
    "IWM": "Indexes & ETFs",
    "SPX": "Indexes & ETFs",
    "VIX": "Indexes & ETFs",
}


class CBOEMostActiveSource:
    """CBOE Most Active Options scraper with aggregated metrics.

    Features:
    - Scrapes top 25 most active option contracts
    - Calculates sentiment (call/put mix)
    - Identifies time horizon (near vs far-term)
    - Measures concentration (focused vs dispersed)
    - Maps sector distribution
    - Health monitoring via SourceMetricsManager
    """

    SOURCE_NAME = "cboe_most_active"
    SOURCE_URL = (
        "https://www-api.cboe.com/us/options/market_statistics/most_active/data/?mkt=cone&limit=25"
    )

    def __init__(self, storage: PortfolioStorage | None = None) -> None:
        """Initialize CBOE Most Active source.

        Args:
            storage: Optional PortfolioStorage for metrics persistence
        """
        self.last_fetch_time: dt.datetime | None = None
        self.last_fetch_data: dict[str, Any] | None = None

        # Initialize metrics tracking
        self.metrics_manager = SourceMetricsManager(storage)
        self.metrics_manager.initialize_metric(self.SOURCE_NAME)

    def fetch_most_active_metrics(self) -> dict[str, Any]:
        """Fetch aggregated metrics from CBOE Most Active Options.

        Returns:
            Dict with structure:
            {
                "as_of_date": "2025-11-13",
                "most_active_call_pct": 32.0,  # % calls
                "near_term_pct": 68.0,  # % expiring ≤30 days
                "concentration_pct": 88.5,  # % volume in top 5
                "sector_weights": {"Technology": 45.2, ...},
                "source_timestamp": "2025-11-13T21:15:00+00:00"
            }

        Raises:
            RuntimeError: If scraping fails or data cannot be parsed
        """
        start_time = time.time()
        logger.info("cboe_most_active_fetch_started", url=self.SOURCE_URL, source=self.SOURCE_NAME)

        try:
            # Use Playwright to render page and extract table data
            contracts = self._fetch_contracts()

            # Calculate aggregated metrics
            metrics = self._calculate_metrics(contracts)

            # Cache results
            self.last_fetch_time = dt.datetime.now(dt.UTC)
            self.last_fetch_data = metrics

            # Record success metrics
            latency_ms = int((time.time() - start_time) * 1000)
            self.metrics_manager.record_success(self.SOURCE_NAME, latency_ms)

            logger.info(
                "cboe_most_active_fetch_success",
                date=metrics["as_of_date"],
                call_pct=metrics["most_active_call_pct"],
                near_term_pct=metrics["near_term_pct"],
                concentration_pct=metrics["concentration_pct"],
                latency_ms=latency_ms,
            )

            return metrics

        except Exception as e:
            # Record failure metrics
            self.metrics_manager.record_failure(self.SOURCE_NAME, e)

            logger.error(
                "cboe_most_active_fetch_failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise RuntimeError(f"CBOE Most Active fetch failed: {e}") from e

    def _fetch_contracts(self) -> list[dict[str, Any]]:
        """Fetch contract data from CBOE JSON API.

        Returns:
            List of contracts with keys: symbol, strike, expiration, type, volume

        Raises:
            RuntimeError: If API request fails
        """
        try:
            # Fetch JSON from API
            with urllib.request.urlopen(self.SOURCE_URL, timeout=30) as response:
                data = json.load(response)

            # Extract contracts from "all" category (All Options section)
            all_category = next(
                (cat for cat in data.get("categories", []) if cat.get("category") == "all"),
                None,
            )

            if not all_category:
                raise RuntimeError("No 'all' category found in API response")

            # Combine calls and puts into single list
            contracts = []

            # Add calls
            for call in all_category.get("calls", []):
                contracts.append(
                    {
                        "symbol": call["symbol"],
                        "expiration": call["expires"],  # Already ISO format (YYYY-MM-DD)
                        "strike": str(call["strike"]),
                        "volume": str(call["volume"]),
                        "type": "Call",
                    }
                )

            # Add puts
            for put in all_category.get("puts", []):
                contracts.append(
                    {
                        "symbol": put["symbol"],
                        "expiration": put["expires"],  # Already ISO format (YYYY-MM-DD)
                        "strike": str(put["strike"]),
                        "volume": str(put["volume"]),
                        "type": "Put",
                    }
                )

            if not contracts:
                raise RuntimeError("No contracts found in API response")

            logger.info("cboe_most_active_contracts_fetched", count=len(contracts))
            return contracts

        except URLError as e:
            raise RuntimeError(f"Failed to fetch from CBOE API: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from CBOE API: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to fetch contracts: {e}") from e

    def _calculate_metrics(self, contracts: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate aggregated metrics from contracts.

        Args:
            contracts: List of contract dicts

        Returns:
            Dict with aggregated metrics
        """
        if not contracts:
            raise ValueError("Cannot calculate metrics from empty contract list")

        total_contracts = len(contracts)
        today = dt.date.today()

        # 1. most_active_call_pct: % of contracts that are calls
        call_count = sum(1 for c in contracts if c.get("type", "").lower() == "call")
        most_active_call_pct = round((call_count / total_contracts) * 100, 2)

        # 2. near_term_pct: % expiring within 30 days
        near_term_count = 0
        for c in contracts:
            exp_str = c.get("expiration", "")
            try:
                # Parse various date formats (e.g., "11/15/2025", "Nov 15 2025")
                exp_date = self._parse_expiration_date(exp_str)
                if exp_date:
                    days_to_exp = (exp_date - today).days
                    if days_to_exp <= 30:
                        near_term_count += 1
            except Exception:
                continue  # Skip unparseable dates

        near_term_pct = round((near_term_count / total_contracts) * 100, 2)

        # 3. concentration_pct: % of volume in top 5 vs all
        volumes = []
        for c in contracts:
            vol_str = c.get("volume", "0").replace(",", "")
            try:
                volumes.append(int(vol_str))
            except ValueError:
                volumes.append(0)

        total_volume = sum(volumes)
        top_5_volume = sum(sorted(volumes, reverse=True)[:5])
        concentration_pct = (
            round((top_5_volume / total_volume) * 100, 2) if total_volume > 0 else 0.0
        )

        # 4. sector_weights: % distribution by sector
        sector_counts: dict[str, int] = {}
        for c in contracts:
            symbol = c.get("symbol", "").upper()
            sector = SECTOR_MAP.get(symbol, "Other")
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        sector_weights = {
            sector: round((count / total_contracts) * 100, 2)
            for sector, count in sector_counts.items()
        }

        return {
            "as_of_date": today.isoformat(),
            "most_active_call_pct": most_active_call_pct,
            "near_term_pct": near_term_pct,
            "concentration_pct": concentration_pct,
            "sector_weights": sector_weights,
            "source_timestamp": dt.datetime.now(dt.UTC).isoformat(),
        }

    def _parse_expiration_date(self, exp_str: str) -> dt.date | None:
        """Parse expiration date from various formats.

        Args:
            exp_str: Expiration date string

        Returns:
            Parsed date or None if unparseable
        """
        if not exp_str:
            return None

        # Try common formats
        formats = [
            "%Y-%m-%d",  # 2025-11-15 (CBOE API format - try first)
            "%b %d, %y",  # Nov 13, 25 (old scraper format)
            "%m/%d/%Y",  # 11/15/2025
            "%b %d %Y",  # Nov 15 2025
            "%B %d %Y",  # November 15 2025
            "%m-%d-%Y",  # 11-15-2025
        ]

        for fmt in formats:
            try:
                return dt.datetime.strptime(exp_str.strip(), fmt).date()
            except ValueError:
                continue

        return None

    def get_health_status(self) -> dict[str, Any]:
        """Get health status for monitoring.

        Returns:
            Dict with health information
        """
        if not self.last_fetch_time or not self.last_fetch_data:
            return {
                "status": "down",
                "last_fetch": None,
                "age_hours": None,
                "message": "No data fetched yet",
            }

        now = dt.datetime.now(dt.UTC)
        age_hours = (now - self.last_fetch_time).total_seconds() / 3600

        # Most Active updates continuously, but we fetch daily
        if age_hours < 30:
            status = "healthy"
            message = "Data is fresh"
        elif age_hours < 48:
            status = "degraded"
            message = f"Data is {age_hours:.1f} hours old"
        else:
            status = "down"
            message = f"Data is stale ({age_hours:.1f} hours old)"

        return {
            "status": status,
            "last_fetch": self.last_fetch_time.isoformat(),
            "age_hours": round(age_hours, 1),
            "message": message,
        }


# Singleton instance
_cboe_most_active_source: CBOEMostActiveSource | None = None


def get_cboe_most_active_source(storage: PortfolioStorage | None = None) -> CBOEMostActiveSource:
    """Get singleton CBOE Most Active source instance.

    Args:
        storage: Optional PortfolioStorage for metrics persistence

    Returns:
        CBOEMostActiveSource instance with metrics tracking enabled
    """
    global _cboe_most_active_source  # noqa: PLW0603
    if _cboe_most_active_source is None:
        _cboe_most_active_source = CBOEMostActiveSource(storage=storage)
    return _cboe_most_active_source
