"""Service for inspecting Celery schedule configuration.

Provides functions to retrieve and format Celery Beat schedule information
for maintenance task monitoring.
"""

from __future__ import annotations

from celery.schedules import (
    crontab as CrontabSchedule,  # noqa: N812 - Using CamelCase for isinstance checks
)

from ..api.maintenance_types import MaintenanceScheduleResponseDict


def get_maintenance_schedule(celery_app) -> MaintenanceScheduleResponseDict:  # type: ignore[no-untyped-def]
    """Get schedule information for maintenance tasks.

    Args:
        celery_app: Celery application instance

    Returns:
        MaintenanceScheduleResponseDict with scheduled tasks and next run times

    Raises:
        Exception: If schedule retrieval fails
    """
    # Get schedule from Celery Beat
    schedule = celery_app.conf.beat_schedule

    # Filter to only maintenance tasks
    maintenance_schedule = {}
    for task_name, config in schedule.items():
        if (
            "cleanup" in task_name
            or "vacuum" in task_name
            or "check-disk" in task_name
            or "database-size" in task_name
        ):
            schedule_info = config["schedule"]

            # Format schedule information
            if isinstance(schedule_info, CrontabSchedule):
                schedule_str = f"crontab({schedule_info})"
            else:
                schedule_str = f"every {schedule_info} seconds"

            maintenance_schedule[task_name] = {
                "task": config["task"],
                "schedule": schedule_str,
                "args": config.get("args", []),
            }

    return {
        "scheduled_tasks": maintenance_schedule,
        "total_count": len(maintenance_schedule),
    }
