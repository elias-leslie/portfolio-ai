"""Shared constants for Celery Beat schedules."""

from app.constants import ALL_MARKET_SYMBOLS

# Schedule intervals (seconds)
POLL_INTERVAL_60_SEC: float = 60.0  # Standard polling interval for user-configurable tasks
POLL_INTERVAL_30_MIN: float = 1800.0  # 30 minutes - reduced polling for API-heavy tasks
POLL_INTERVAL_12_HOURS: float = 43200.0  # 12 hours - for daily-ish tasks

# Task expiry times (seconds)
EXPIRY_2_MIN: int = 120  # Quick tasks that should be dropped if delayed
EXPIRY_10_MIN: int = 600  # 10-minute expiry for quick monitoring tasks
EXPIRY_28_MIN: int = 1700  # Slightly less than 30-min schedule
EXPIRY_30_MIN: int = 1800  # 30-minute expiry for moderate tasks
EXPIRY_50_MIN: int = 3000  # 50-minute expiry for longer tasks
EXPIRY_1_HOUR: int = 3600  # Longer-running tasks
EXPIRY_2_HOURS: int = 7200  # 2-hour expiry for daily cleanup tasks

# Fear & Greed lookback period (days)
FEAR_GREED_LOOKBACK_DAYS: int = 7

# Cleanup task retention periods
CLEANUP_LOGS_RETENTION_DAYS = 7
CLEANUP_TEMP_FILES_RETENTION_HOURS = 24
CLEANUP_NEWS_RETENTION_DAYS = 90
CLEANUP_AGENT_RUNS_RETENTION_DAYS = 30
CLEANUP_BACKUPS_KEEP_COUNT = 5
CLEANUP_MODELS_KEEP_COUNT = 3
CLEANUP_SOLUTION_STATE_RETENTION_DAYS = 14

__all__ = [
    "ALL_MARKET_SYMBOLS",
    "CLEANUP_AGENT_RUNS_RETENTION_DAYS",
    "CLEANUP_BACKUPS_KEEP_COUNT",
    "CLEANUP_LOGS_RETENTION_DAYS",
    "CLEANUP_MODELS_KEEP_COUNT",
    "CLEANUP_NEWS_RETENTION_DAYS",
    "CLEANUP_SOLUTION_STATE_RETENTION_DAYS",
    "CLEANUP_TEMP_FILES_RETENTION_HOURS",
    "EXPIRY_1_HOUR",
    "EXPIRY_2_HOURS",
    "EXPIRY_2_MIN",
    "EXPIRY_10_MIN",
    "EXPIRY_28_MIN",
    "EXPIRY_30_MIN",
    "EXPIRY_50_MIN",
    "FEAR_GREED_LOOKBACK_DAYS",
    "POLL_INTERVAL_12_HOURS",
    "POLL_INTERVAL_30_MIN",
    "POLL_INTERVAL_60_SEC",
]
