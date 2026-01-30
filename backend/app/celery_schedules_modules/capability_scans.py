"""QA scanning and capability discovery tasks."""

from typing import Any

from celery.schedules import crontab

from .constants import EXPIRY_1_HOUR, EXPIRY_2_HOURS, EXPIRY_30_MIN


def get_tasks() -> dict[str, dict[str, Any]]:
    """QA scanning and capability discovery tasks."""
    return {
        "scan-system-capabilities": {
            "task": "scan_system_capabilities",
            "schedule": crontab(hour=3, minute=0),
            "options": {"expires": EXPIRY_30_MIN},
        },
        "scan-feature-capabilities": {
            "task": "scan_feature_capabilities",
            "schedule": crontab(hour=3, minute=5),
            "options": {"expires": EXPIRY_30_MIN},
        },
        "daily-qa-scan": {
            "task": "tasks.daily_qa_scan",
            "schedule": crontab(hour=4, minute=30),
            "options": {"expires": EXPIRY_1_HOUR},
        },
        "verify-acceptance-criteria": {
            "task": "verify_all_acceptance_criteria",
            "schedule": crontab(hour=5, minute=20, day_of_week=0),
            "options": {"expires": EXPIRY_2_HOURS},
        },
    }
