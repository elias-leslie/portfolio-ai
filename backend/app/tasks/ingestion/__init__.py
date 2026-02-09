"""Data ingestion tasks package.

This package contains background tasks for ingesting market data from external sources.
All tasks are re-exported here for backward compatibility.

Modules:
    - price_ingestion: OHLCV price data tasks
    - analytics_ingestion: Covariance and earnings data tasks
    - fundamental_ingestion: Fundamental data and macro indicators
"""

from __future__ import annotations

# Re-export all tasks
from .analytics_ingestion import update_earnings_surprises, update_portfolio_covariance
from .fundamental_ingestion import ingest_fundamental_data, ingest_macro_indicators
from .price_ingestion import (
    ingest_historical_ohlcv,
    refresh_daily_ohlcv,
    refresh_watchlist_ohlcv,
)

__all__ = [
    "ingest_fundamental_data",
    "ingest_historical_ohlcv",
    "ingest_macro_indicators",
    "refresh_daily_ohlcv",
    "refresh_watchlist_ohlcv",
    "update_earnings_surprises",
    "update_portfolio_covariance",
]
