"""
Application-wide constants for portfolio-ai.

This module centralizes magic numbers, cache sizes, limits, and default paths
to improve maintainability and reduce duplication.
"""

# =============================================================================
# FILE PATHS & DATABASE
# =============================================================================
# PostgreSQL database connection URL
import os
from pathlib import Path

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai",
)

DEFAULT_DB_PATH = Path("data/portfolio-ai.db")

# Default config directory
DEFAULT_CONFIG_DIR = Path("config")

# Default portfolio config directory
DEFAULT_PORTFOLIO_CONFIG_DIR = Path("config/portfolio")

# Default log directory
DEFAULT_LOG_DIR = Path("logs")

# Default backup directory
DEFAULT_BACKUP_DIR = Path("data/backups")

# =============================================================================
# API LIMITS & BATCH SIZES
# =============================================================================

# Default API request timeout (seconds)
DEFAULT_API_TIMEOUT_SECONDS = 15

# Maximum retry attempts for API calls
MAX_API_RETRY_ATTEMPTS = 3

# =============================================================================
# DATABASE QUERY LIMITS
# =============================================================================

# Default limit for query results
DEFAULT_QUERY_LIMIT = 100

# Maximum allowed query limit (safety cap)
MAX_QUERY_LIMIT = 10000

# =============================================================================
# CACHE & TIMEOUTS
# =============================================================================

# Cache max age for price data (minutes)
DEFAULT_PRICE_CACHE_TTL_MINUTES = 15

# Agent run timeout (minutes)
DEFAULT_AGENT_TIMEOUT_MINUTES = 10

# Agent cost limit per run (USD)
DEFAULT_AGENT_COST_LIMIT_USD = 0.50

# =============================================================================
# PORTFOLIO ANALYTICS
# =============================================================================

# Number of decimal places for percentage display
PERCENTAGE_DECIMAL_PLACES = 2

# Number of decimal places for price display
PRICE_DECIMAL_PLACES = 2

# Default risk-free rate for analytics (annual %)
DEFAULT_RISK_FREE_RATE = 0.04

# =============================================================================
# ENVIRONMENT VARIABLE NAMES
# =============================================================================

ENV_DB_PATH = "DB_PATH"
ENV_POLYGON_API_KEY = "POLYGON_API_KEY"
ENV_FRED_API_KEY = "FRED_API_KEY"
ENV_ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
ENV_PRICE_CACHE_TTL = "PRICE_CACHE_TTL_MINUTES"
