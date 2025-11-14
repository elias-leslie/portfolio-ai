"""Celery application configuration for background tasks.

This module configures Celery for asynchronous execution of
agent runs and other long-running tasks.
"""

from __future__ import annotations

import os

from celery import Celery  # type: ignore[import-untyped]  # celery doesn't ship type stubs
from celery.schedules import crontab  # type: ignore[import-untyped]
from celery.signals import (  # type: ignore[import-untyped]
    after_setup_logger,
    after_setup_task_logger,
)

from app.logging_config import SyslogPrefixFormatter, _parse_log_level

# Get Redis URL from environment or use default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Get DATABASE_URL for result backend
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai",
)

# Create Celery application with Redis broker + PostgreSQL backend
# Note: Redis is recommended for broker (fast message queue)
#       PostgreSQL is used for result backend (persistent storage)
celery_app = Celery(
    "portfolio-ai",
    broker=f"{REDIS_URL}/0",  # Redis broker (message queue)
    backend=f"db+{DATABASE_URL}",  # PostgreSQL result backend
    broker_connection_retry_on_startup=True,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_extended=True,  # Store extended task metadata (name, args, kwargs, worker)
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=540,  # 9 minute soft limit
    result_expires=60 * 60 * 24 * 30,  # Results expire after 30 days (2,592,000 seconds)
    worker_prefetch_multiplier=1,  # One task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
)

# Configure Celery Beat schedule for periodic tasks
# ==============================================
#
# REFRESH ARCHITECTURE:
# ---------------------
# Backend refresh (expensive API calls): Controlled by user preferences
#   - Global default: default_refresh_minutes (15 min default)
#   - Per-feature overrides: watchlist_refresh_override, portfolio_refresh_override, news_refresh_override
#   - Tasks check preference hierarchy: override → default → hardcoded fallback
#
# Frontend polling (cheap DB reads): Fixed at 30 seconds for responsiveness
#   - Controlled by frontend_poll_interval in user_preferences (default: 30s)
#   - Independent of backend refresh schedule
#
# PERIODIC TASK TYPES:
# --------------------
# 1. User-Configurable Backend Refresh (respects preferences)
#    - Watchlist scores: polls every 60s, honors user's refresh_interval
#    - Portfolio analytics: (future) polls every 60s, honors user's refresh_interval
#    - News sentiment: (future) polls every 60s, honors user's refresh_interval
#
# 2. Static Schedules (not configurable)
#    - Paper trades update: Daily at 4:30 PM ET (market close + 30 min)
#    - Data cleanup: (future) Weekly on Sunday 2:00 AM
#
# DESIGN RATIONALE:
# -----------------
# - Beat polls frequently (60s) to ensure responsiveness
# - Task logic skips execution if not enough time elapsed since last refresh
# - This ensures user preferences are honored while maintaining prompt execution
# - Example: If user sets watchlist to 5 min, Beat checks every 60s but only
#   executes refresh when 5 min have passed since last actual refresh
#
# See: docs/REFRESH_ARCHITECTURE.md for complete documentation
#
celery_app.conf.beat_schedule = {
    # ============================================================================
    # USER-CONFIGURABLE BACKEND REFRESH TASKS
    # ============================================================================
    # These tasks poll frequently (60s) but honor user preference intervals
    # Task logic checks: last_refresh_time + user_interval < now → execute
    # ============================================================================
    "refresh-watchlist-scores": {
        "task": "refresh_watchlist_scores",
        "schedule": 60.0,  # Poll every 60 seconds (Beat check interval)
        "args": ["default"],  # account_id
        "options": {"expires": 120},  # Task expires after 2 minutes if not picked up
        # Notes:
        # - Task checks: watchlist_refresh_override → default_refresh_minutes → 15 min
        # - Skips execution if not enough time elapsed since last refresh
        # - Runs 24/7 to capture after-hours and weekend data
        # - Issue #4 fix: Uses Redis cache for watchlist symbols (60s TTL)
    },
    # Future: Portfolio analytics refresh
    # Note: Commented example for future implementation
    # "refresh-portfolio-analytics": {
    #     "task": "refresh_portfolio_analytics",  # noqa: ERA001
    #     "schedule": 60.0,  # Poll every 60 seconds  # noqa: ERA001
    #     "args": ["default"],  # noqa: ERA001
    #     "options": {"expires": 120},  # noqa: ERA001
    #     # Task checks: portfolio_refresh_override → default_refresh_minutes → 15 min
    # },
    "refresh-news-sentiment": {
        "task": "refresh_news_sentiment",
        "schedule": 65.0,  # Poll every 65 seconds (5s offset from watchlist)
        "args": ["default"],
        "options": {"expires": 120},
        # Notes:
        # - Task checks: news_refresh_override → default_refresh_minutes → 15 min
        # - 5-second offset reduces contention with watchlist refresh
        # - Still allows concurrent execution when both tasks need to run
        # - Uses optimized JOIN query from Issue #5 fix
    },
    # ============================================================================
    # STATIC SCHEDULE TASKS (NOT CONFIGURABLE)
    # ============================================================================
    # These tasks run on fixed schedules regardless of user preferences
    # ============================================================================
    "update-paper-trades-daily": {
        "task": "update_paper_trades_task",
        "schedule": 86400.0,  # Daily (24 hours)
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at 4:30 PM ET (market close + 30 min)
        # - Not configurable by user (business logic requirement)
    },
    "profile-news-sources": {
        "task": "profile_news_sources",
        "schedule": 43200.0,  # Every 12 hours (configurable via user preferences)
        "args": ["default"],  # user_id
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Task checks: news_profiling_interval_hours preference (default 12h)
        # - Calculates 6 quality metrics per vendor (duplicate, diversity, confidence, freshness, user_feedback, quality)
        # - Stores results in source_metrics table
        # - Skips execution if not enough time elapsed since last profiling
    },
    "refresh-daily-ohlcv": {
        "task": "refresh_daily_ohlcv",
        "schedule": 86400.0,  # Daily (24 hours)
        "args": [
            [
                "SPY",  # S&P 500 (market regime indicators)
                # Market indicators for Market Conditions card
                "^GSPC",  # S&P 500 Index
                "^VIX",  # Volatility Index
                "^TNX",  # 10-Year Treasury Note Yield
                "DX-Y.NYB",  # US Dollar Index
                # Sector ETFs for Market Conditions sector breakdown
                "XLK",  # Technology
                "XLF",  # Financials
                "XLE",  # Energy
                "XLV",  # Healthcare
                "XLY",  # Consumer Discretionary
                "XLP",  # Consumer Staples
                "XLI",  # Industrials
                "XLU",  # Utilities
                "XLRE",  # Real Estate
                "XLB",  # Materials
                "XLC",  # Communication Services
            ]
        ],
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at ~02:00 UTC
        # - Ensures SPY + market indicators + sector ETFs fresh for market intelligence
        # - Fetches last 5 days to account for holidays/weekends
    },
    "retrain-article-quality-model": {
        "task": "retrain_article_quality_model",
        "schedule": 86400.0,  # Daily (24 hours)
        "options": {"expires": 7200},  # Task expires after 2 hours
        # Notes:
        # - Queries 100 newest unlabeled articles from news_cache
        # - Labels them with Gemini for quality assessment
        # - Retrains sklearn model with accumulated training data
        # - Updates production model if accuracy improves
        # - Stores metrics in ml_model_metrics table
        # - Runs daily to keep model fresh with evolving news patterns
    },
    "update-technical-indicators-daily": {
        "task": "update_technical_indicators",
        "schedule": 86400.0,  # Daily (24 hours)
        "args": [["SPY"]],  # Update SPY indicators
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at ~02:30 UTC (after OHLCV refresh)
        # - Calculates RSI, SMA_200, and other technical indicators
        # - Must run after refresh-daily-ohlcv completes
    },
    "populate-fear-greed-inputs-daily": {
        "task": "populate_fear_greed_inputs",
        "schedule": 86400.0,  # Daily (24 hours)
        "args": [7],  # Update last 7 days
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at ~02:45 UTC (after indicators update at 02:30)
        # - Replaces manual update_fear_greed_inputs.py script
        # - Fetches SPY OHLCV and calculates SMA_200, RSI_14
        # - Fetches VIX if available, uses estimate if missing
        # - Populates fear_greed_inputs table (SPY, VIX, RSI data)
        # - Automatically triggers calculate_fear_greed after completion
        # - Idempotent: Safe to run multiple times
        # - Self-healing: Backfills missing dates within 7-day window
    },
    "calculate-fear-greed-daily": {
        "task": "calculate_fear_greed",
        "schedule": 86400.0,  # Daily (24 hours)
        "args": [None],  # Calculate for latest available date
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at ~03:00 UTC (after populate-fear-greed-inputs completes)
        # - Calculates Fear & Greed Index from inputs table
        # - Uses 252-day rolling window for percentile rankings
        # - Must run after populate-fear-greed-inputs-daily completes
        # - NOTE: Also triggered automatically by populate_fear_greed_inputs task
    },
    "maintain-historical-market-data": {
        "task": "maintain_historical_market_data",
        "schedule": 86400.0,  # Daily (24 hours)
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at ~04:00 UTC (after Fear & Greed calculation)
        # - Maintains 252 trading days for all market indicators and sectors
        # - Idempotent: Checks if data exists, backfills if needed, adds new day if current
        # - Self-healing: Automatically fixes missing or stale data
        # - Symbols: ^GSPC, ^VIX, ^TNX, DX-Y.NYB (indicators)
        # - Symbols: XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLU, XLRE, XLB, XLC (sectors)
        # - NO MANUAL BACKFILLING NEEDED - task handles all data maintenance
    },
    "fetch-putcall-ratio-daily": {
        "task": "fetch_putcall_ratio",
        "schedule": 86400.0,  # Daily (24 hours)
        "args": [None],  # Fetch for today
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at ~04:30 UTC (after market data maintenance)
        # - Fetches SPX options data from yfinance
        # - Calculates total put/call ratio (put OI / call OI)
        # - Stores in fear_greed_inputs.put_call_ratio column
        # - Market sentiment: >1.0 = Bearish, 0.7-1.0 = Neutral, <0.7 = Bullish
    },
    "refresh-yfinance-reference": {
        "task": "refresh_yfinance_reference_data",
        "schedule": crontab(hour=4, minute=0),  # Daily at 04:00 UTC
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at 04:00 UTC
        # - Fetches reference data (including valuation metrics) from yfinance
        # - Updates reference_cache table for all watchlist symbols
        # - Includes P/E, P/B, P/S, PEG, dividend yield, payout ratio
        # - Also fetches bonus metrics: EPS, margins, growth rates, ratios
    },
    "parse-valuation-metrics": {
        "task": "parse_valuation_metrics",
        "schedule": crontab(hour=4, minute=30),  # Daily at 04:30 UTC (after fetch)
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at 04:30 UTC (30 minutes after yfinance reference fetch)
        # - Extracts valuation metrics from JSON payloads in reference_cache
        # - Populates structured columns: pe_ratio_trailing, pe_ratio_forward, etc.
        # - Idempotent: Safe to run multiple times
    },
    "refresh-alphavantage-reference-backup": {
        "task": "refresh_alphavantage_reference_backup",
        "schedule": crontab(hour=4, minute=45),  # Daily at 04:45 UTC (after yfinance + parsing)
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at 04:45 UTC (after yfinance refresh at 04:00 and parsing at 04:30)
        # - Fetches Alpha Vantage OVERVIEW data as backup for symbols with missing/stale yfinance data
        # - Only processes symbols where yfinance data is missing or >7 days old
        # - Rate limited: 500 calls/day, 5 calls/min (free tier)
        # - Provides 15/16 valuation metrics (missing only payout_ratio, but calculated if possible)
        # - Idempotent: Safe to run multiple times
        # - Self-healing: Automatically fills gaps in valuation data coverage
    },
    "fetch-options-activity-daily": {
        "task": "fetch_options_activity_metrics",
        "schedule": crontab(hour=21, minute=15),  # Daily at 21:15 UTC (4:15 PM ET)
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at 21:15 UTC (4:15 PM ET, after market close at 4:00 PM)
        # - Scrapes CBOE Most Active Options page
        # - Calculates aggregated metrics:
        #   * Call/put sentiment (% calls in top 25)
        #   * Time horizon (% near-term ≤30 days)
        #   * Concentration (% volume in top 5)
        #   * Sector distribution
        # - Stores in options_market_metrics table
        # - Used for market positioning intelligence
    },
    "scan-system-capabilities": {
        "task": "scan_system_capabilities",
        "schedule": crontab(hour=3, minute=0),  # Daily at 03:00 UTC
        "options": {"expires": 1800},  # Task expires after 30 minutes
        # Notes:
        # - Runs daily at 03:00 UTC (after data refresh tasks complete)
        # - Auto-discovers all system capabilities:
        #   * Database tables (row counts, completeness, freshness)
        #   * Celery scheduled tasks (schedules, success rates)
        #   * API endpoints (paths, dependencies)
        # - Stores results in capability registry tables:
        #   * db_capabilities
        #   * celery_capabilities
        #   * api_capabilities
        # - Enables AI-powered monitoring and gap detection
        # - Critical for preventing AI agents from breaking features
    },
    "analyze-capabilities": {
        "task": "analyze_capabilities",
        "schedule": crontab(hour=3, minute=15),  # Daily at 03:15 UTC (15 min after scan)
        "options": {"expires": 1800},  # Task expires after 30 minutes
        # Notes:
        # - Runs daily at 03:15 UTC (15 minutes after capability scan)
        # - Uses Claude AI to analyze capability data and identify:
        #   * Data quality issues (stale, incomplete, missing fields)
        #   * Missing capabilities (gaps in data sources, missing tasks)
        #   * Broken dependencies (tasks failing, endpoints broken)
        # - Stores insights in capability_insights table
        # - Filters insights by confidence threshold (default: 0.70)
        # - Provides actionable suggestions with file paths
        # - Critical for proactive monitoring before AI agents break things
    },
    # Future: Data cleanup task
    # Note: Commented example for future implementation
    # "cleanup-old-data": {
    #     "task": "cleanup_old_data",  # noqa: ERA001
    #     "schedule": 604800.0,  # Weekly (7 days)  # noqa: ERA001
    #     "options": {"expires": 3600},  # noqa: ERA001
    #     # Runs Sunday 2:00 AM - not configurable
    # },
}

# Import tasks to register them with Celery
# This must come after celery_app is defined
from app.tasks import (  # noqa: E402, F401
    agent_tasks,
    capability_tasks,
    data_ingestion_tasks,
    indicator_tasks,
    market_data_tasks,
    ml_training_tasks,
    news_tasks,
    reference_tasks,
    watchlist_tasks,
)


# Configure Celery logging to use syslog prefixes for journald
@after_setup_logger.connect
def setup_celery_logger(logger, *args, **kwargs):  # type: ignore[no-untyped-def]
    """Configure Celery logger to use syslog prefixes for proper journald PRIORITY.

    This signal handler is called after Celery sets up its logger. We replace
    the formatter with our SyslogPrefixFormatter so that log entries have
    correct syslog priority prefixes that systemd parses into the PRIORITY field.
    """
    log_level = _parse_log_level(os.getenv("LOG_LEVEL"))

    # Update all handlers to use syslog formatter
    for handler in logger.handlers:
        handler.setLevel(log_level)
        handler.setFormatter(
            SyslogPrefixFormatter("[%(asctime)s: %(levelname)s/%(processName)s] %(message)s")
        )


@after_setup_task_logger.connect
def setup_celery_task_logger(logger, *args, **kwargs):  # type: ignore[no-untyped-def]
    """Configure Celery task logger to use syslog prefixes for proper journald PRIORITY.

    This signal handler is called after Celery sets up task loggers. We replace
    the formatter with our SyslogPrefixFormatter so that log entries have
    correct syslog priority prefixes that systemd parses into the PRIORITY field.
    """
    log_level = _parse_log_level(os.getenv("LOG_LEVEL"))

    # Update all handlers to use syslog formatter
    for handler in logger.handlers:
        handler.setLevel(log_level)
        handler.setFormatter(
            SyslogPrefixFormatter("[%(asctime)s: %(levelname)s/%(processName)s] %(message)s")
        )
