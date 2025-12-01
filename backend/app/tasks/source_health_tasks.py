"""Data source health check tasks.

This module provides periodic health monitoring for all configured data sources.
Health checks test each source with a known symbol (SPY) and categorize results
as healthy, degraded, or down.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

from ..celery_app import celery_app
from ..logging_config import get_logger
from ..sources.alphavantage_source import AlphaVantageSource
from ..sources.base import DATASET_DAY, DatasetRequest
from ..sources.finnhub_source import FinnhubSource
from ..sources.fmp_source import FMPSource
from ..sources.multi_source_fetcher import MultiSourceFetcher
from ..sources.polygon_source import PolygonSource
from ..sources.twelvedata_source import TwelveDataSource
from ..sources.yfinance_source import YFinanceSource
from ..storage import PortfolioStorage

if TYPE_CHECKING:
    from celery import Task  # type: ignore[import-untyped]

logger = get_logger(__name__)


@celery_app.task(bind=True, name="check_data_source_health", max_retries=1)
def check_data_source_health(self: Task) -> dict[str, Any]:
    """Periodically test each configured data source.

    Tests each source by fetching OHLCV data for SPY (reliable test symbol).
    Categorizes sources as:
    - healthy: Returns valid data with rows
    - degraded: No error but empty data
    - down: Exception raised during fetch

    Returns:
        dict: Health status per source and summary counts
    """
    task_id = self.request.id or "unknown"
    logger.info("source_health_check_started", task_id=task_id)

    storage = PortfolioStorage()

    # Initialize all available sources (same as price_fetcher.py)
    sources = [
        YFinanceSource(),
        TwelveDataSource(),
        FMPSource(),
        PolygonSource(),
        FinnhubSource(),
        AlphaVantageSource(),
    ]

    fetcher = MultiSourceFetcher(sources, storage)
    results: dict[str, str] = {}
    errors: dict[str, str] = {}

    # Test each source individually with SPY (reliable market indicator)
    test_symbol = "SPY"
    test_date_start = dt.date.today() - dt.timedelta(days=5)
    test_date_end = dt.date.today()

    for source in fetcher.sources:
        try:
            # Create test request for day bars
            request = DatasetRequest(
                dataset=DATASET_DAY,
                profile=None,
                tickers=[test_symbol],
                start=test_date_start,
                end=test_date_end,
            )

            # Attempt fetch
            data = fetcher._fetch_from_source(source, request, {test_symbol})

            if data is not None and len(data) > 0:
                results[source.name] = "healthy"
                logger.info(
                    "source_health_check_healthy",
                    source=source.name,
                    rows=len(data),
                )
            else:
                results[source.name] = "degraded"
                logger.warning(
                    "source_health_check_degraded",
                    source=source.name,
                    reason="empty_data",
                )

        except Exception as e:
            results[source.name] = "down"
            errors[source.name] = str(e)
            logger.warning(
                "source_health_check_down",
                source=source.name,
                error=str(e),
            )

    # Calculate summary metrics
    healthy_count = sum(1 for status in results.values() if status == "healthy")
    degraded_count = sum(1 for status in results.values() if status == "degraded")
    down_count = sum(1 for status in results.values() if status == "down")

    logger.info(
        "source_health_check_completed",
        task_id=task_id,
        total_sources=len(results),
        healthy=healthy_count,
        degraded=degraded_count,
        down=down_count,
    )

    return {
        "sources": results,
        "errors": errors,
        "healthy_count": healthy_count,
        "degraded_count": degraded_count,
        "down_count": down_count,
        "total_sources": len(results),
    }
