"""Celery application configuration for background tasks.

This module configures Celery for asynchronous execution of
agent runs and other long-running tasks.
"""

from __future__ import annotations

import os

from celery import Celery  # type: ignore[import-untyped]  # celery doesn't ship type stubs

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
        "schedule": 60.0,
        "args": ["default"],
        "options": {"expires": 120},
        # Task checks: news_refresh_override → default_refresh_minutes → 15 min
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
    "refresh-daily-ohlcv": {
        "task": "refresh_daily_ohlcv",
        "schedule": 86400.0,  # Daily (24 hours)
        "args": [["SPY"]],  # Refresh SPY by default
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at ~02:00 UTC (before Fear & Greed computation)
        # - Ensures SPY data is fresh for market regime indicators
        # - Fetches last 5 days to account for holidays/weekends
    },
    "update-technical-indicators-daily": {
        "task": "update_technical_indicators",
        "schedule": 86400.0,  # Daily (24 hours)
        "args": [["SPY"]],  # Update SPY indicators
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at ~02:30 UTC (after OHLCV refresh, before Fear & Greed)
        # - Calculates RSI, SMA_200, and other indicators needed for Fear & Greed
        # - Must run after refresh-daily-ohlcv completes
    },
    "compute-fear-greed-daily": {
        "task": "compute_fear_greed_daily",
        "schedule": 86400.0,  # Daily (24 hours)
        "options": {"expires": 3600},  # Task expires after 1 hour
        # Notes:
        # - Runs daily at 03:30 UTC (after market close + data availability)
        # - Depends on refresh-daily-ohlcv completing first
        # - Not configurable by user (business logic requirement)
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
    data_ingestion_tasks,
    fear_greed_tasks,
    indicator_tasks,
    news_tasks,
    watchlist_tasks,
)
