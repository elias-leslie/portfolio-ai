"""User-configurable backend refresh tasks."""

from typing import Any

from celery.schedules import crontab

from .constants import EXPIRY_2_MIN, EXPIRY_50_MIN, POLL_INTERVAL_60_SEC


def get_tasks() -> dict[str, dict[str, Any]]:
    """User-configurable backend refresh tasks.

    These tasks poll frequently (60s) but honor user preference intervals.
    Task logic checks: last_refresh_time + user_interval < now → execute

    Returns:
        Dict of Celery Beat task definitions for user-configurable refreshes
    """
    return {
        "refresh-watchlist-scores": {
            "task": "refresh_watchlist_scores",
            "schedule": POLL_INTERVAL_60_SEC,
            "args": ["default"],  # account_id
            "options": {"expires": EXPIRY_2_MIN},
            # Notes:
            # - Task checks: watchlist_refresh_override → default_refresh_minutes → 15 min
            # - Skips execution if not enough time elapsed since last refresh
            # - Runs 24/7 to capture after-hours and weekend data
            # - Issue #4 fix: Uses Redis cache for watchlist symbols (60s TTL)
        },
        # Future: Portfolio analytics refresh
        # Note: Commented example for future implementation
        "refresh-news-sentiment": {
            "task": "refresh_news_sentiment",
            "schedule": crontab(minute=25),  # Hourly at :25 (was 30min, caused CPU spikes)
            "args": ["default"],
            "options": {"expires": EXPIRY_50_MIN},  # 50 min expiry for hourly schedule
            # Notes:
            # - Changed from 30min to hourly to reduce CPU load (task takes 4-5 min)
            # - Runs at :25 to avoid collision with other hourly tasks
            # - Task checks: news_refresh_override → default_refresh_minutes → 15 min
            # - Uses optimized JOIN query from Issue #5 fix
        },
    }
