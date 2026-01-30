"""Automated maintenance tasks for system health."""

from typing import Any

from celery.schedules import crontab

from .constants import (
    CLEANUP_AGENT_RUNS_RETENTION_DAYS,
    CLEANUP_BACKUPS_KEEP_COUNT,
    CLEANUP_LOGS_RETENTION_DAYS,
    CLEANUP_MODELS_KEEP_COUNT,
    CLEANUP_NEWS_RETENTION_DAYS,
    CLEANUP_SOLUTION_STATE_RETENTION_DAYS,
    CLEANUP_TEMP_FILES_RETENTION_HOURS,
    EXPIRY_1_HOUR,
    EXPIRY_2_HOURS,
    EXPIRY_10_MIN,
)


def get_tasks() -> dict[str, dict[str, Any]]:
    """Automated maintenance tasks for system health.

    These tasks maintain system health through automated cleanup and monitoring.
    Includes log cleanup, temp file cleanup, database vacuum, news cleanup,
    agent run cleanup, orphaned data cleanup, backup cleanup, model cleanup,
    solution state cleanup, disk space checks, data source health, and database size tracking.

    Returns:
        Dict of Celery Beat task definitions for maintenance tasks
    """
    return {
        "maintain-data-freshness": {
            "task": "maintain_data_freshness",
            "schedule": crontab(hour="*/2"),  # Every 2 hours
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "check-all-data-freshness": {
            "task": "check_all_data_freshness",
            "schedule": crontab(minute=0, hour="*/2"),  # Every 2 hours
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-old-logs-daily": {
            "task": "cleanup_old_logs_task",
            "schedule": crontab(hour=2, minute=0),  # Daily at 02:00 UTC
            "args": [CLEANUP_LOGS_RETENTION_DAYS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-temp-files-daily": {
            "task": "cleanup_temp_files_task",
            "schedule": crontab(hour=2, minute=15),  # Daily at 02:15 UTC
            "args": [CLEANUP_TEMP_FILES_RETENTION_HOURS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "vacuum-database-weekly": {
            "task": "vacuum_database_task",
            "schedule": crontab(day_of_week=0, hour=3, minute=30),  # Sunday 03:30 UTC
            "args": [None],
            "options": {"expires": EXPIRY_2_HOURS},
        },
        "cleanup-old-news-weekly": {
            "task": "cleanup_old_news_task",
            "schedule": crontab(day_of_week=0, hour=4, minute=0),  # Sunday 04:00 UTC
            "args": [CLEANUP_NEWS_RETENTION_DAYS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-old-agent-runs-weekly": {
            "task": "cleanup_old_agent_runs_task",
            "schedule": crontab(day_of_week=0, hour=4, minute=15),  # Sunday 04:15 UTC
            "args": [CLEANUP_AGENT_RUNS_RETENTION_DAYS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-orphaned-data-weekly": {
            "task": "cleanup_orphaned_data_task",
            "schedule": crontab(day_of_week=0, hour=4, minute=30),  # Sunday 04:30 UTC
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-old-backups-weekly": {
            "task": "cleanup_old_backups_task",
            "schedule": crontab(day_of_week=0, hour=4, minute=45),  # Sunday 04:45 UTC
            "args": [CLEANUP_BACKUPS_KEEP_COUNT],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-old-models-weekly": {
            "task": "cleanup_old_models_task",
            "schedule": crontab(day_of_week=0, hour=5, minute=5),  # Sunday 05:05 UTC
            "args": [CLEANUP_MODELS_KEEP_COUNT],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-solution-state-weekly": {
            "task": "cleanup_solution_state_task",
            "schedule": crontab(day_of_week=0, hour=5, minute=25),  # Sunday 05:25 UTC
            "args": [CLEANUP_SOLUTION_STATE_RETENTION_DAYS],
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "check-disk-space-periodic": {
            "task": "check_disk_space_task",
            "schedule": crontab(hour="*/6"),  # Every 6 hours
            "options": {"expires": EXPIRY_10_MIN},
        },
        "check-data-source-health-periodic": {
            "task": "check_data_source_health",
            "schedule": crontab(minute=30, hour="*/6"),  # Every 6 hours at :30
            "options": {"expires": EXPIRY_10_MIN},
        },
        "get-database-size-daily": {
            "task": "get_database_size_task",
            "schedule": crontab(hour=5, minute=36),  # Daily at 05:36 UTC (staggered)
            "options": {"expires": EXPIRY_10_MIN},
        },
        "refresh-sec-cik-cache-weekly": {
            "task": "refresh_sec_cik_cache",
            "schedule": crontab(
                hour=6, minute=5, day_of_week=0
            ),  # Weekly on Sunday at 06:05 UTC (staggered)
            "options": {"expires": EXPIRY_1_HOUR},
        },
    }
