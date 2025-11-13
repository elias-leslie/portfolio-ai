"""CBOE options data source for put/call ratios.

Uses CBOE CDN JSON API for official put/call ratios.
Data source: https://cdn.cboe.com/data/us/options/market_statistics/daily/{date}_daily_options

This is the gold standard for market-wide options sentiment data.
"""

from __future__ import annotations

import datetime as dt
import json
import time
import urllib.request
from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger
from .source_metrics_manager import SourceMetricsManager

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)


class CBOESource:
    """CBOE options data source using CDN JSON API.

    Features:
    - Official CBOE put/call ratios (market-wide)
    - Supports TOTAL, INDEX, EQUITY, and SPX+SPXW ratios
    - Fast JSON API (no browser required)
    - Reliable date-based endpoint
    - Health monitoring via SourceMetricsManager
    """

    SOURCE_NAME = "cboe_daily_statistics"
    SOURCE_URL_TEMPLATE = (
        "https://cdn.cboe.com/data/us/options/market_statistics/daily/{date}_daily_options"
    )

    def __init__(self, storage: PortfolioStorage | None = None) -> None:
        """Initialize CBOE source.

        Args:
            storage: Optional PortfolioStorage for metrics persistence
        """
        self.last_fetch_time: dt.datetime | None = None
        self.last_fetch_data: dict[str, Any] | None = None

        # Initialize metrics tracking
        self.metrics_manager = SourceMetricsManager(storage)
        self.metrics_manager.initialize_metric(self.SOURCE_NAME)

    def fetch_put_call_ratios(self, target_date: dt.date | None = None) -> dict[str, Any]:
        """Fetch put/call ratios from CBOE JSON API.

        Args:
            target_date: Date to fetch ratios for (default: yesterday, since today's data
                        isn't available until after market close)

        Returns:
            Dict with structure:
            {
                "date": "2025-11-12",
                "total": 0.78,
                "index": 0.95,
                "equity": 0.56,
                "spx": 1.04,
                "timestamp": "2025-11-12T21:00:00+00:00"
            }

        Raises:
            RuntimeError: If API request fails or data cannot be parsed
        """
        # Default to yesterday (today's data not available until after market close)
        if target_date is None:
            target_date = dt.date.today() - dt.timedelta(days=1)

        # Build URL with date
        url = self.SOURCE_URL_TEMPLATE.format(date=target_date.strftime("%Y-%m-%d"))

        start_time = time.time()
        logger.info("cboe_fetch_started", url=url, source=self.SOURCE_NAME, date=str(target_date))

        try:
            # Fetch JSON from API
            with urllib.request.urlopen(url, timeout=30) as response:
                json_data = json.load(response)

            # Parse ratios from JSON
            data = self._parse_ratios(json_data, target_date)

            # Cache results
            self.last_fetch_time = dt.datetime.now(dt.UTC)
            self.last_fetch_data = data

            # Record success metrics
            latency_ms = int((time.time() - start_time) * 1000)
            self.metrics_manager.record_success(self.SOURCE_NAME, latency_ms)

            logger.info(
                "cboe_fetch_success",
                date=data["date"],
                total_ratio=data["total"],
                spx_ratio=data["spx"],
                latency_ms=latency_ms,
            )

            return data

        except urllib.error.URLError as e:
            # Record failure metrics
            self.metrics_manager.record_failure(self.SOURCE_NAME, e)

            logger.error(
                "cboe_fetch_failed",
                error=str(e),
                error_type=type(e).__name__,
                url=url,
            )
            raise RuntimeError(f"CBOE fetch failed: {e}") from e
        except Exception as e:
            # Record failure metrics
            self.metrics_manager.record_failure(self.SOURCE_NAME, e)

            logger.error(
                "cboe_fetch_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise RuntimeError(f"CBOE fetch failed: {e}") from e

    def _parse_ratios(self, json_data: dict[str, Any], target_date: dt.date) -> dict[str, Any]:
        """Parse put/call ratios from JSON response.

        Args:
            json_data: JSON response from CBOE API
            target_date: Date the data is for

        Returns:
            Dict with date and ratio values

        Raises:
            ValueError: If required ratios cannot be parsed
        """
        ratios_list = json_data.get("ratios", [])
        if not ratios_list:
            raise ValueError("No ratios found in JSON response")

        # Build dict for easy lookup
        ratios_dict = {ratio["name"]: float(ratio["value"]) for ratio in ratios_list}

        # Extract required ratios
        total_ratio = ratios_dict.get("TOTAL PUT/CALL RATIO")
        if total_ratio is None:
            raise ValueError("TOTAL PUT/CALL RATIO not found in response")

        index_ratio = ratios_dict.get("INDEX PUT/CALL RATIO")
        equity_ratio = ratios_dict.get("EQUITY PUT/CALL RATIO")
        spx_ratio = ratios_dict.get("SPX + SPXW PUT/CALL RATIO")

        # Set timestamp to market close (4:00 PM ET = 21:00 UTC)
        timestamp = dt.datetime.combine(target_date, dt.time(21, 0, 0), tzinfo=dt.UTC).isoformat()

        return {
            "date": target_date.isoformat(),
            "total": total_ratio,
            "index": index_ratio,
            "equity": equity_ratio,
            "spx": spx_ratio,
            "timestamp": timestamp,
        }

    def get_health_status(self) -> dict[str, Any]:
        """Get health status for monitoring.

        Returns:
            Dict with health information:
            {
                "status": "healthy" | "degraded" | "down",
                "last_fetch": "2025-11-12T21:00:00+00:00",
                "age_hours": 2.5,
                "message": "Data is fresh"
            }
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

        # CBOE updates daily, so data should be < 36 hours old
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
_cboe_source: CBOESource | None = None


def get_cboe_source(storage: PortfolioStorage | None = None) -> CBOESource:
    """Get singleton CBOE source instance.

    Args:
        storage: Optional PortfolioStorage for metrics persistence

    Returns:
        CBOESource instance with metrics tracking enabled
    """
    global _cboe_source  # noqa: PLW0603
    if _cboe_source is None:
        _cboe_source = CBOESource(storage=storage)
    return _cboe_source
