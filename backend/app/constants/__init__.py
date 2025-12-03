"""
Application-wide constants for portfolio-ai.

This module centralizes magic numbers, cache sizes, limits, and default paths
to improve maintainability and reduce duplication.
"""

import os
from pathlib import Path

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
# FILE PATHS & DATABASE
# =============================================================================
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai",
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
    "DEFAULT_BACKUP_DIR",
    "DEFAULT_CONFIG_DIR",
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
]
