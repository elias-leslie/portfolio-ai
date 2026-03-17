"""Application-wide constants for portfolio-ai.

This module centralizes magic numbers, cache sizes, limits, and default paths
to improve maintainability and reduce duplication.
"""

from __future__ import annotations

from app.config import DATABASE_URL  # re-exported for backward compatibility
from app.constants.models import (
    CLAUDE_HAIKU,
    CLAUDE_OPUS,
    CLAUDE_SONNET,
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_GEMINI_MODEL,
    GEMINI_FLASH,
    GEMINI_PRO,
)
from app.constants.services import SERVICE_PROCESS_PATTERNS
from app.constants.symbols import (
    ALL_MARKET_SYMBOLS,
    BENCHMARK_SPY,
    INDEX_DXY,
    INDEX_SP500,
    INDEX_TNX,
    INDEX_VIX,
    MARKET_INDICATORS,
    SECTOR_ETF_SYMBOLS,
    SECTOR_ETFS,
    SECTOR_LABELS,
)

# =============================================================================
# SPECIAL SYMBOLS
# =============================================================================
# Pseudo-symbol for market-wide events and readings (fear/greed history)
MARKET_SYMBOL = "__MARKET__"

# =============================================================================
# CACHE & TIMEOUTS
# =============================================================================
DEFAULT_PRICE_CACHE_TTL_MINUTES = 15

# HTTP response cache TTLs (in seconds) used by market API routers
CACHE_TTL_SHORT = 60  # 1 minute
CACHE_TTL_MEDIUM = 300  # 5 minutes
CACHE_TTL_LONG = 900  # 15 minutes

# =============================================================================
# TRUNCATION & LIMITS
# =============================================================================
ERROR_MESSAGE_TRUNCATE = 100  # Truncate error messages to prevent log bloat
RESULT_SUMMARY_LENGTH = 500  # Max chars for agent result summaries

# =============================================================================
# TIME CONSTANTS
# =============================================================================
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400

# =============================================================================
# TRADING CALENDAR
# =============================================================================
TRADING_DAYS_PER_YEAR = 252

# =============================================================================
# DATA INGESTION
# =============================================================================
# Default days of historical OHLCV data to fetch for backfill operations.
# 1300 trading days ≈ 5 years - provides enough data for:
# - 200-day moving averages and all other technical indicators
# - 1-year lookback for backtesting with sufficient warm-up period
# - Historical volatility and risk calculations
DEFAULT_BACKFILL_DAYS = 1300

# Daily refresh only fetches recent data (last 5 days) to update existing bars
DEFAULT_DAILY_REFRESH_DAYS = 5


__all__ = [
    "ALL_MARKET_SYMBOLS",
    "BENCHMARK_SPY",
    "CACHE_TTL_LONG",
    "CACHE_TTL_MEDIUM",
    "CACHE_TTL_SHORT",
    "CLAUDE_HAIKU",
    "CLAUDE_OPUS",
    "CLAUDE_SONNET",
    "DATABASE_URL",
    "DEFAULT_BACKFILL_DAYS",
    "DEFAULT_CLAUDE_MODEL",
    "DEFAULT_DAILY_REFRESH_DAYS",
    "DEFAULT_GEMINI_MODEL",
    "DEFAULT_PRICE_CACHE_TTL_MINUTES",
    "ERROR_MESSAGE_TRUNCATE",
    "GEMINI_FLASH",
    "GEMINI_PRO",
    "INDEX_DXY",
    "INDEX_SP500",
    "INDEX_TNX",
    "INDEX_VIX",
    "MARKET_INDICATORS",
    "MARKET_SYMBOL",
    "RESULT_SUMMARY_LENGTH",
    "SECONDS_PER_DAY",
    "SECONDS_PER_HOUR",
    "SECTOR_ETFS",
    "SECTOR_ETF_SYMBOLS",
    "SECTOR_LABELS",
    "SERVICE_PROCESS_PATTERNS",
    "TRADING_DAYS_PER_YEAR",
]
