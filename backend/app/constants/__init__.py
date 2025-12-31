"""
Application-wide constants for portfolio-ai.

This module centralizes magic numbers, cache sizes, limits, and default paths
to improve maintainability and reduce duplication.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment from ~/.env.local
_env_file = Path.home() / ".env.local"
if _env_file.exists():
    load_dotenv(_env_file)

from app.constants.services import (  # noqa: E402
    SERVICE_PROCESS_PATTERNS,
    SERVICE_UNIT_MAPPING,
    VALID_SERVICES,
)
from app.constants.symbols import (  # noqa: E402
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
# FILE PATHS & DATABASE
# =============================================================================
DATABASE_URL = os.environ.get("PORTFOLIO_DB_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "PORTFOLIO_DB_URL environment variable is required. "
        "Create ~/.env.local with PORTFOLIO_DB_URL=postgresql://..."
    )

DEFAULT_DB_PATH = Path("data/portfolio-ai.db")
DEFAULT_CONFIG_DIR = Path("config")
DEFAULT_PORTFOLIO_CONFIG_DIR = Path("config/portfolio")
DEFAULT_LOG_DIR = Path("logs")
DEFAULT_BACKUP_DIR = Path("data/backups")

# =============================================================================
# API LIMITS & BATCH SIZES
# =============================================================================
DEFAULT_API_TIMEOUT_SECONDS = 15
MAX_API_RETRY_ATTEMPTS = 3

# =============================================================================
# DATABASE QUERY LIMITS
# =============================================================================
DEFAULT_QUERY_LIMIT = 100
MAX_QUERY_LIMIT = 10000

# =============================================================================
# CACHE & TIMEOUTS
# =============================================================================
DEFAULT_PRICE_CACHE_TTL_MINUTES = 15
DEFAULT_AGENT_TIMEOUT_MINUTES = 10
DEFAULT_AGENT_COST_LIMIT_USD = 0.50

# =============================================================================
# PORTFOLIO ANALYTICS
# =============================================================================
PERCENTAGE_DECIMAL_PLACES = 2
PRICE_DECIMAL_PLACES = 2
DEFAULT_RISK_FREE_RATE = 0.04

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

# =============================================================================
# ENVIRONMENT VARIABLE NAMES
# =============================================================================
ENV_DB_PATH = "DB_PATH"
ENV_POLYGON_API_KEY = "POLYGON_API_KEY"
ENV_FRED_API_KEY = "FRED_API_KEY"
ENV_ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
ENV_PRICE_CACHE_TTL = "PRICE_CACHE_TTL_MINUTES"

__all__ = [
    "ALL_MARKET_SYMBOLS",
    "BENCHMARK_SPY",
    "DATABASE_URL",
    "DEFAULT_AGENT_COST_LIMIT_USD",
    "DEFAULT_AGENT_TIMEOUT_MINUTES",
    "DEFAULT_API_TIMEOUT_SECONDS",
    "DEFAULT_BACKFILL_DAYS",
    "DEFAULT_BACKUP_DIR",
    "DEFAULT_CONFIG_DIR",
    "DEFAULT_DAILY_REFRESH_DAYS",
    "DEFAULT_DB_PATH",
    "DEFAULT_LOG_DIR",
    "DEFAULT_PORTFOLIO_CONFIG_DIR",
    "DEFAULT_PRICE_CACHE_TTL_MINUTES",
    "DEFAULT_QUERY_LIMIT",
    "DEFAULT_RISK_FREE_RATE",
    "ENV_ANTHROPIC_API_KEY",
    "ENV_DB_PATH",
    "ENV_FRED_API_KEY",
    "ENV_POLYGON_API_KEY",
    "ENV_PRICE_CACHE_TTL",
    "INDEX_DXY",
    "INDEX_SP500",
    "INDEX_TNX",
    "INDEX_VIX",
    "MARKET_INDICATORS",
    "MAX_API_RETRY_ATTEMPTS",
    "MAX_QUERY_LIMIT",
    "PERCENTAGE_DECIMAL_PLACES",
    "PRICE_DECIMAL_PLACES",
    "SECTOR_ETFS",
    "SECTOR_ETF_SYMBOLS",
    "SECTOR_LABELS",
    "SERVICE_PROCESS_PATTERNS",
    "SERVICE_UNIT_MAPPING",
    "VALID_SERVICES",
]
