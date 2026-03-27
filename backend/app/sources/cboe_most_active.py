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

from ..constants import DEFAULT_HTTP_TIMEOUT
from ..logging_config import get_logger
from .source_metrics_manager import SourceMetricsManager

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)

# Simple sector mapping for common symbols
SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "GOOGL": "Technology", "GOOG": "Technology", "META": "Technology",
    "TSLA": "Technology", "AMD": "Technology", "INTC": "Technology", "CSCO": "Technology",
    "JPM": "Financials", "BAC": "Financials", "WFC": "Financials",
    "GS": "Financials", "MS": "Financials", "C": "Financials",
    "JNJ": "Healthcare", "UNH": "Healthcare", "PFE": "Healthcare",
    "ABBV": "Healthcare", "TMO": "Healthcare",
    "AMZN": "Consumer Discretionary", "HD": "Consumer Discretionary",
    "MCD": "Consumer Discretionary", "NKE": "Consumer Discretionary",
    "SBUX": "Consumer Discretionary",
    "WMT": "Consumer Staples", "PG": "Consumer Staples", "KO": "Consumer Staples",
    "SPY": "Indexes & ETFs", "QQQ": "Indexes & ETFs", "IWM": "Indexes & ETFs",
    "SPX": "Indexes & ETFs", "VIX": "Indexes & ETFs",
}

_DATE_FORMATS = [
    "%Y-%m-%d",   # 2025-11-15 (CBOE API format)
    "%b %d, %y",  # Nov 13, 25
    "%m/%d/%Y",   # 11/15/2025
    "%b %d %Y",   # Nov 15 2025
    "%B %d %Y",   # November 15 2025
    "%m-%d-%Y",   # 11-15-2025
]


def _parse_expiration_date(exp_str: str) -> dt.date | None:
    """Parse expiration date from various formats; returns None if unparseable."""
    if not exp_str:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(exp_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _contract_record(item: dict[str, Any], option_type: str) -> dict[str, Any]:
    return {
        "symbol": item["symbol"],
        "expiration": item["expires"],
        "strike": str(item["strike"]),
        "volume": str(item["volume"]),
        "type": option_type,
    }


class CBOEMostActiveSource:
    """CBOE Most Active Options scraper with aggregated metrics."""

    SOURCE_NAME = "cboe_most_active"
    SOURCE_URL = (
        "https://www-api.cboe.com/us/options/market_statistics/most_active/data/?mkt=cone&limit=25"
    )

    def __init__(self, storage: PortfolioStorage | None = None) -> None:
        self.last_fetch_time: dt.datetime | None = None
        self.last_fetch_data: dict[str, Any] | None = None
        self.metrics_manager = SourceMetricsManager(storage)
        self.metrics_manager.initialize_metric(self.SOURCE_NAME)

    def fetch_most_active_metrics(self) -> dict[str, Any]:
        """Fetch aggregated metrics from CBOE Most Active Options.

        Returns:
            Dict with keys: as_of_date, most_active_call_pct, near_term_pct,
            concentration_pct, sector_weights, source_timestamp

        Raises:
            RuntimeError: If scraping fails or data cannot be parsed
        """
        start_time = time.time()
        logger.info("cboe_most_active_fetch_started", url=self.SOURCE_URL, source=self.SOURCE_NAME)
        try:
            contracts = self._fetch_contracts()
            metrics = self._calculate_metrics(contracts)
            self.last_fetch_time = dt.datetime.now(dt.UTC)
            self.last_fetch_data = metrics
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
            with urllib.request.urlopen(self.SOURCE_URL, timeout=int(DEFAULT_HTTP_TIMEOUT)) as resp:
                data = json.load(resp)
        except URLError as e:
            raise RuntimeError(f"Failed to fetch from CBOE API: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from CBOE API: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to fetch contracts: {e}") from e

        all_category = next(
            (cat for cat in data.get("categories", []) if cat.get("category") == "all"),
            None,
        )
        if not all_category:
            raise RuntimeError("No 'all' category found in API response")

        contracts = [_contract_record(c, "Call") for c in all_category.get("calls", [])]
        contracts += [_contract_record(p, "Put") for p in all_category.get("puts", [])]

        if not contracts:
            raise RuntimeError("No contracts found in API response")

        logger.info("cboe_most_active_contracts_fetched", count=len(contracts))
        return contracts

    def _calculate_metrics(self, contracts: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate aggregated metrics from contracts."""
        if not contracts:
            raise ValueError("Cannot calculate metrics from empty contract list")

        total = len(contracts)
        today = dt.date.today()

        call_count = sum(1 for c in contracts if c.get("type", "").lower() == "call")
        most_active_call_pct = round((call_count / total) * 100, 2)

        near_term_count = sum(
            1
            for c in contracts
            if (exp := _parse_expiration_date(c.get("expiration", ""))) is not None
            and (exp - today).days <= 30
        )
        near_term_pct = round((near_term_count / total) * 100, 2)

        volumes = []
        for c in contracts:
            try:
                volumes.append(int(c.get("volume", "0").replace(",", "")))
            except ValueError:
                volumes.append(0)

        total_volume = sum(volumes)
        top_5_volume = sum(sorted(volumes, reverse=True)[:5])
        concentration_pct = round((top_5_volume / total_volume) * 100, 2) if total_volume > 0 else 0.0

        sector_counts: dict[str, int] = {}
        for c in contracts:
            sector = SECTOR_MAP.get(c.get("symbol", "").upper(), "Other")
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        sector_weights = {
            s: round((n / total) * 100, 2) for s, n in sector_counts.items()
        }

        return {
            "as_of_date": today.isoformat(),
            "most_active_call_pct": most_active_call_pct,
            "near_term_pct": near_term_pct,
            "concentration_pct": concentration_pct,
            "sector_weights": sector_weights,
            "source_timestamp": dt.datetime.now(dt.UTC).isoformat(),
        }

    def get_health_status(self) -> dict[str, Any]:
        """Get health status for monitoring."""
        if not self.last_fetch_time or not self.last_fetch_data:
            return {"status": "down", "last_fetch": None, "age_hours": None, "message": "No data fetched yet"}

        age_hours = (dt.datetime.now(dt.UTC) - self.last_fetch_time).total_seconds() / 3600

        if age_hours < 30:
            status, message = "healthy", "Data is fresh"
        elif age_hours < 48:
            status, message = "degraded", f"Data is {age_hours:.1f} hours old"
        else:
            status, message = "down", f"Data is stale ({age_hours:.1f} hours old)"

        return {
            "status": status,
            "last_fetch": self.last_fetch_time.isoformat(),
            "age_hours": round(age_hours, 1),
            "message": message,
        }


# Singleton instance
_cboe_most_active_source: CBOEMostActiveSource | None = None


def get_cboe_most_active_source(storage: PortfolioStorage | None = None) -> CBOEMostActiveSource:
    """Get singleton CBOE Most Active source instance."""
    global _cboe_most_active_source  # noqa: PLW0603
    if _cboe_most_active_source is None:
        _cboe_most_active_source = CBOEMostActiveSource(storage=storage)
    return _cboe_most_active_source
