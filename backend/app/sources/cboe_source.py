"""CBOE options data source for put/call ratios.

Scrapes CBOE Daily Market Statistics page for official put/call ratios.
Data source: https://www.cboe.com/us/options/market_statistics/daily/

This is the gold standard for market-wide options sentiment data.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger
from .source_metrics_manager import SourceMetricsManager

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)


class CBOESource:
    """CBOE options data source using Playwright for page rendering.

    Features:
    - Official CBOE put/call ratios (market-wide)
    - Supports TOTAL, INDEX, EQUITY, and SPX+SPXW ratios
    - Robust scraping with retry logic
    - Minimal dependencies (uses existing Playwright)
    - Health monitoring via SourceMetricsManager
    """

    SOURCE_NAME = "cboe_daily_statistics"
    SOURCE_URL = "https://www.cboe.com/us/options/market_statistics/daily/"

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

    def fetch_put_call_ratios(self) -> dict[str, Any]:
        """Fetch put/call ratios from CBOE daily statistics page.

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
            RuntimeError: If scraping fails or data cannot be parsed
        """
        start_time = time.time()
        logger.info("cboe_fetch_started", url=self.SOURCE_URL, source=self.SOURCE_NAME)

        try:
            # Use Playwright to render page and extract text
            # This is the most reliable method for JavaScript-rendered pages
            page_text = self._fetch_page_text()

            # Parse ratios from text
            data = self._parse_ratios(page_text)

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

        except Exception as e:
            # Record failure metrics
            self.metrics_manager.record_failure(self.SOURCE_NAME, e)

            logger.error(
                "cboe_fetch_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise RuntimeError(f"CBOE fetch failed: {e}") from e

    def _fetch_page_text(self) -> str:
        """Fetch page content using Playwright execute.js script.

        Returns:
            Page text content

        Raises:
            RuntimeError: If Playwright execution fails
        """
        # Use existing browser-automation script
        script_path = (
            "/home/kasadis/portfolio-ai/.claude/skills/browser-automation/scripts/execute.js"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_file = f.name

        try:
            # Execute JavaScript to get page text
            # Ensure Playwright finds browsers in user's home directory
            env = os.environ.copy()
            env["HOME"] = "/home/kasadis"  # Ensure correct home for Playwright
            subprocess.run(
                [
                    "node",
                    script_path,
                    self.SOURCE_URL,
                    "document.body.innerText",
                    output_file,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
                env=env,
            )

            # Read result from JSON file
            with Path(output_file).open() as f:
                data = json.load(f)
                page_text: str = data.get("result", "")

            if not page_text:
                raise RuntimeError("Empty page text returned")

            return page_text

        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Playwright timeout after 30s: {e}") from e
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Playwright execution failed: {e.stderr}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to fetch page text: {e}") from e
        finally:
            # Clean up temp file
            with contextlib.suppress(Exception):
                Path(output_file).unlink()

    def _parse_ratios(self, page_text: str) -> dict[str, Any]:
        """Parse put/call ratios from page text.

        Args:
            page_text: Raw page text from CBOE website

        Returns:
            Dict with date and ratio values

        Raises:
            ValueError: If required ratios cannot be parsed
        """
        # Extract date (e.g., "Nov 12, 2025")
        date_match = re.search(r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})", page_text)
        if not date_match:
            raise ValueError("Could not find date in page text")

        date_str = date_match.group(1)
        # Convert to ISO format
        date_obj = dt.datetime.strptime(date_str, "%b %d, %Y").date()

        # Extract TOTAL PUT/CALL RATIO
        total_match = re.search(r"TOTAL PUT/CALL RATIO\s+([0-9.]+)", page_text, re.IGNORECASE)
        if not total_match:
            raise ValueError("Could not find TOTAL PUT/CALL RATIO")
        total_ratio = float(total_match.group(1))

        # Extract INDEX PUT/CALL RATIO
        index_match = re.search(r"INDEX PUT/CALL RATIO\s+([0-9.]+)", page_text, re.IGNORECASE)
        index_ratio = float(index_match.group(1)) if index_match else None

        # Extract EQUITY PUT/CALL RATIO
        equity_match = re.search(r"EQUITY PUT/CALL RATIO\s+([0-9.]+)", page_text, re.IGNORECASE)
        equity_ratio = float(equity_match.group(1)) if equity_match else None

        # Extract SPX + SPXW PUT/CALL RATIO (most relevant for S&P 500 sentiment)
        spx_match = re.search(r"SPX \+ SPXW PUT/CALL RATIO\s+([0-9.]+)", page_text, re.IGNORECASE)
        spx_ratio = float(spx_match.group(1)) if spx_match else None

        # Set timestamp to market close (4:00 PM ET = 21:00 UTC)
        timestamp = dt.datetime.combine(date_obj, dt.time(21, 0, 0), tzinfo=dt.UTC).isoformat()

        return {
            "date": date_obj.isoformat(),
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
