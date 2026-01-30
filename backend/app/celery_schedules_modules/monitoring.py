"""Monitoring and lifecycle tasks for artifacts, theses, sitemap, and files."""

from typing import Any

from celery.schedules import crontab

from .constants import EXPIRY_1_HOUR, EXPIRY_10_MIN, EXPIRY_30_MIN, EXPIRY_50_MIN


def get_tasks() -> dict[str, dict[str, Any]]:
    """Monitoring and lifecycle tasks for artifacts, theses, sitemap, and files.

    Includes:
    - Artifact refresh and cleanup
    - Thesis health monitoring and processing
    - Sitemap health checks and discovery
    - File audit scanning

    Returns:
        Dict of Celery Beat task definitions for monitoring tasks
    """
    return {
        # Artifact lifecycle
        "refresh-expired-artifacts": {
            "task": "refresh_expired_artifacts",
            "schedule": crontab(hour=5, minute=33),  # Daily at 05:33 UTC (staggered)
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "cleanup-old-artifact-versions": {
            "task": "cleanup_old_versions",
            "schedule": crontab(hour=6, minute=0),  # Daily at 06:00 UTC
            "options": {"expires": EXPIRY_1_HOUR},
            "kwargs": {"max_versions": 5, "dry_run": False},
        },
        "cleanup-debug-captures": {
            "task": "cleanup_debug_captures",
            "schedule": crontab(hour=6, minute=15),  # Daily at 06:15 UTC
            "options": {"expires": EXPIRY_1_HOUR},
            "kwargs": {"max_age_days": 7, "dry_run": False},
        },
        # Thesis monitoring
        "monitor-thesis-health-daily": {
            "task": "monitor_thesis_health",
            "schedule": crontab(hour=3, minute=5),  # Daily at 03:05 UTC
            "options": {"expires": EXPIRY_30_MIN},
        },
        "process-invalidated-theses-daily": {
            "task": "process_invalidated_theses",
            "schedule": crontab(hour=3, minute=15),  # Daily at 03:15 UTC
            "options": {"expires": EXPIRY_30_MIN},
        },
        "archive-strategies-for-invalidated-theses": {
            "task": "archive_strategies_for_invalidated_theses",
            "schedule": crontab(hour=3, minute=30),  # Daily at 03:30 UTC
            "options": {"expires": EXPIRY_30_MIN},
        },
        # Sitemap health
        "check-sitemap-health-morning": {
            "task": "check_sitemap_health",
            "schedule": crontab(hour=8, minute=2),  # Daily at 08:02 UTC (staggered)
            "options": {"expires": EXPIRY_50_MIN},
        },
        "check-sitemap-health-evening": {
            "task": "check_sitemap_health",
            "schedule": crontab(hour=20, minute=0),  # Daily at 20:00 UTC
            "options": {"expires": EXPIRY_50_MIN},
        },
        "discover-sitemap-entries-daily": {
            "task": "discover_sitemap_entries",
            "schedule": crontab(hour=3, minute=33),  # Daily at 03:33 UTC (staggered)
            "options": {"expires": EXPIRY_30_MIN},
        },
        "cleanup-sitemap-history-daily": {
            "task": "cleanup_sitemap_history",
            "schedule": crontab(hour=4, minute=4),  # Daily at 04:04 UTC (staggered)
            "options": {"expires": EXPIRY_10_MIN},
        },
        # File audit
        "scan-files-daily": {
            "task": "scan_files",
            "schedule": crontab(hour=7, minute=30),  # Daily at 07:30 UTC
            "options": {"expires": EXPIRY_30_MIN},
        },
    }
