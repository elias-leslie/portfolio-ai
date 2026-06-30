"""Data source health check tasks.

This module provides periodic health monitoring for all configured data sources.
Health checks test each source with a known symbol (SPY) and categorize results
as healthy, degraded, or down.
"""

from __future__ import annotations

import datetime as dt
import time
import uuid
from typing import Any

from ..logging_config import get_logger
from ..sources._fetch_helpers import fetch_from_source
from ..sources.alphavantage_source import AlphaVantageSource
from ..sources.base import DATASET_DAY, BaseSource, DatasetRequest
from ..sources.finnhub_source import FinnhubSource
from ..sources.fmp_source import FMPSource
from ..sources.multi_source_fetcher import MultiSourceFetcher
from ..sources.polygon_source import PolygonSource
from ..sources.twelvedata_source import TwelveDataSource
from ..sources.yfinance_source import YFinanceSource
from ..storage import PortfolioStorage
from ..storage.credential_loader import load_credentials_from_database

logger = get_logger(__name__)

_TEST_SYMBOL = "SPY"
_TEST_LOOKBACK_DAYS = 5


def _build_fetcher() -> MultiSourceFetcher:
    """Instantiate all available sources and wrap them in a MultiSourceFetcher."""
    load_credentials_from_database()
    storage = PortfolioStorage()
    sources = [
        YFinanceSource(),
        TwelveDataSource(),
        FMPSource(),
        PolygonSource(),
        FinnhubSource(),
        AlphaVantageSource(),
    ]
    return MultiSourceFetcher(sources, storage)


def _make_test_request() -> DatasetRequest:
    """Build a DatasetRequest for the SPY health-check probe."""
    return DatasetRequest(
        dataset=DATASET_DAY,
        profile=None,
        symbols=[_TEST_SYMBOL],
        start=dt.date.today() - dt.timedelta(days=_TEST_LOOKBACK_DAYS),
        end=dt.date.today(),
    )


def _check_single_source(
    source: BaseSource,
    request: DatasetRequest,
    results: dict[str, str],
    errors: dict[str, str],
    metrics_manager: Any | None = None,
) -> None:
    """Probe one source and update results/errors dicts in place."""
    started_at = time.monotonic()
    try:
        data = fetch_from_source(source, request, {_TEST_SYMBOL})
        latency_ms = int((time.monotonic() - started_at) * 1000)

        if data is not None and len(data) > 0:
            results[source.name] = "healthy"
            if metrics_manager is not None:
                metrics_manager.record_success(source.name, latency_ms)
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
        if metrics_manager is not None:
            metrics_manager.record_failure(source.name, e)
        logger.warning(
            "source_health_check_down",
            source=source.name,
            error=str(e),
        )


def _summarise(
    task_id: str,
    results: dict[str, str],
    errors: dict[str, str],
) -> dict[str, object]:
    """Compute summary counts, emit a completion log, and return the result dict."""
    healthy_count = sum(1 for s in results.values() if s == "healthy")
    degraded_count = sum(1 for s in results.values() if s == "degraded")
    down_count = sum(1 for s in results.values() if s == "down")

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


def check_data_source_health() -> dict[str, object]:
    """Periodically test each configured data source.

    Tests each source by fetching OHLCV data for SPY (reliable test symbol).
    Categorizes sources as:
    - healthy: Returns valid data with rows
    - degraded: No error but empty data
    - down: Exception raised during fetch

    Returns:
        dict: Health status per source and summary counts
    """
    task_id = str(uuid.uuid4())
    logger.info("source_health_check_started", task_id=task_id)

    fetcher = _build_fetcher()
    request = _make_test_request()
    results: dict[str, str] = {}
    errors: dict[str, str] = {}

    for source in fetcher.get_sources_for_dataset(DATASET_DAY):
        _check_single_source(source, request, results, errors, fetcher.metrics_manager)

    return _summarise(task_id, results, errors)
