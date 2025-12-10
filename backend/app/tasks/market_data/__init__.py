"""Market data pipeline tasks.

This package contains Celery tasks for maintaining market data:
- historical_ohlcv_pipeline: Maintains 1260 days (5 years) of historical OHLCV data
- options_pipeline: Fetches put/call ratios and options activity metrics
- fear_greed_pipeline: Populates fear & greed indicator inputs
- corporate_actions_pipeline: Fetches buybacks, dividends, splits
"""

from __future__ import annotations

from app.tasks.market_data.corporate_actions_pipeline import fetch_corporate_actions
from app.tasks.market_data.fear_greed_pipeline import populate_fear_greed_inputs
from app.tasks.market_data.historical_ohlcv_pipeline import maintain_historical_market_data
from app.tasks.market_data.options_pipeline import (
    fetch_options_activity_metrics,
    fetch_putcall_ratio,
)

__all__ = [
    "fetch_corporate_actions",
    "fetch_options_activity_metrics",
    "fetch_putcall_ratio",
    "maintain_historical_market_data",
    "populate_fear_greed_inputs",
]
