"""Celery application configuration for background tasks.

This module configures Celery for asynchronous execution of
agent runs and other long-running tasks.
"""

from __future__ import annotations

import os

from celery import Celery  # type: ignore[import-untyped]  # celery doesn't ship type stubs
from celery.schedules import crontab  # type: ignore[import-untyped]

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
    result_expires=3600,  # Results expire after 1 hour
    worker_prefetch_multiplier=1,  # One task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
)

# Configure Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # Refresh watchlist scores every 1 minute during market hours (for testing)
    # Monday-Friday, 9:30 AM - 4:00 PM ET (converted to UTC)
    # Note: 9:30 AM ET = 13:30 UTC, 4:00 PM ET = 20:00 UTC
    # TODO: Make interval configurable via user preferences
    "refresh-watchlist-scores": {
        "task": "refresh_watchlist_scores",
        "schedule": crontab(
            minute="*/1",  # Every 1 minute (for testing - should be user preference)
            hour="13-20",  # 9:00 AM - 4:00 PM ET = 13:00 - 20:00 UTC (covers market hours)
            day_of_week="1-5",  # Monday-Friday
        ),
        "options": {"expires": 300},  # Task expires after 5 minutes if not picked up
    },
    # Update paper trades daily at 4:30 PM ET (market close + 30 min)
    "update-paper-trades-daily": {
        "task": "update_paper_trades_task",
        "schedule": 86400.0,  # Daily (24 hours)
        "options": {"expires": 3600},  # Task expires after 1 hour
    },
}

# Import tasks to register them with Celery
# This must come after celery_app is defined
from app.tasks import agent_tasks  # noqa: E402, F401
