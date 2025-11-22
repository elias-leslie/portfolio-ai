"""Market data pipeline tasks.

This package contains Celery tasks for maintaining market data:
- historical_ohlcv_pipeline: Maintains 252 days of historical OHLCV data
- options_pipeline: Fetches put/call ratios and options activity metrics
- fear_greed_pipeline: Populates fear & greed indicator inputs
"""

from __future__ import annotations

from app.tasks.market_data.fear_greed_pipeline import populate_fear_greed_inputs
from app.tasks.market_data.historical_ohlcv_pipeline import maintain_historical_market_data
from app.tasks.market_data.options_pipeline import (
    fetch_options_activity_metrics,
    fetch_putcall_ratio,
)

__all__ = [
    "fetch_options_activity_metrics",
    "fetch_putcall_ratio",
    "maintain_historical_market_data",
    "populate_fear_greed_inputs",
]
