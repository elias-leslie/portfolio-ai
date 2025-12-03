"""Celery tasks for technical indicators and market sentiment.

This package provides tasks for:
- Technical indicator calculations (RSI, MACD, SMA, EMA, etc.)
- Fear & Greed Index calculation

All tasks are re-exported here for Celery registration via celery_app.py.
"""

from __future__ import annotations

# Import Celery tasks for registration
from app.tasks.indicators.fear_greed import calculate_fear_greed
from app.tasks.indicators.technical import (
    backfill_technical_indicators,
    update_technical_indicators,
)

# Re-export all tasks for Celery to discover
__all__ = [
    "backfill_technical_indicators",
    "calculate_fear_greed",
    "update_technical_indicators",
]
