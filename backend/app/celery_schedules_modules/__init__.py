"""Celery Beat periodic task schedules.

This module contains all periodic task definitions for Celery Beat.
Schedules are organized by category in separate modules for maintainability.
"""

from typing import Any

from . import (
    agents,
    capability_scans,
    data_refresh,
    fundamentals,
    maintenance,
    market_data,
    monitoring,
    reference_data,
    static_schedule,
    strategy,
    user_configurable,
)


def get_beat_schedule() -> dict[str, dict[str, Any]]:
    """Get Celery Beat schedule configuration.

    Merges all categorized task modules into a single beat schedule.
    See individual modules for task details and documentation.

    Task Categories:
    - User-configurable: watchlist scores, news sentiment
    - Static schedule: paper trades, news profiling, ML model training
    - Data refresh: OHLCV, indicators, Fear & Greed
    - Market data: options, put/call ratios, historical data
    - Reference data: yfinance, Alpha Vantage, valuations
    - Fundamentals: earnings, financial health, risk, macro
    - Capability scans: system/feature discovery, QA
    - Agents: discovery agent, portfolio analyzer
    - Maintenance: freshness, cleanup, disk space
    - Strategy: performance, generation, signals, portfolio
    - Monitoring: artifacts, theses, sitemap, files

    Returns:
        dict: Beat schedule with all periodic tasks
    """
    return {
        **user_configurable.get_tasks(),
        **static_schedule.get_tasks(),
        **data_refresh.get_tasks(),
        **market_data.get_tasks(),
        **reference_data.get_tasks(),
        **fundamentals.get_tasks(),
        **capability_scans.get_tasks(),
        **agents.get_tasks(),
        **maintenance.get_tasks(),
        **strategy.get_tasks(),
        **monitoring.get_tasks(),
    }


__all__ = ["get_beat_schedule"]
