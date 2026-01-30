"""Schedule parsing utilities for Celery scanner."""

from __future__ import annotations

from typing import Any


def parse_schedule(
    schedule_obj: Any,
) -> tuple[str, str | None, int | None]:
    """Parse Celery schedule object into human-readable format.

    Args:
        schedule_obj: Celery schedule object (crontab or interval)

    Returns:
        Tuple of (description, crontab_string, interval_seconds)
    """
    from celery.schedules import crontab  # noqa: PLC0415

    schedule_str = str(schedule_obj)

    # Try to parse crontab
    if isinstance(schedule_obj, crontab):
        # Human-readable description
        hour = schedule_obj._orig_hour if hasattr(schedule_obj, "_orig_hour") else "*"
        minute = schedule_obj._orig_minute if hasattr(schedule_obj, "_orig_minute") else "*"

        if hour != "*" and minute != "*":
            description = f"Daily at {hour:02d}:{minute:02d} UTC"
            crontab_str = f"{minute} {hour} * * *"
        else:
            description = f"Crontab: {schedule_str}"
            crontab_str = schedule_str

        # Estimate interval in seconds for daily tasks
        interval_seconds = 86400 if hour != "*" else None

    elif isinstance(schedule_obj, (int, float)):
        # Interval in seconds
        interval_seconds = int(schedule_obj)

        if interval_seconds < 60:
            description = f"Every {interval_seconds} seconds"
        elif interval_seconds < 3600:
            description = f"Every {interval_seconds // 60} minutes"
        elif interval_seconds < 86400:
            description = f"Every {interval_seconds // 3600} hours"
        else:
            description = f"Every {interval_seconds // 86400} days"

        crontab_str = None

    else:
        # Unknown schedule type
        description = f"Schedule: {schedule_str}"
        crontab_str = None
        interval_seconds = None

    return description, crontab_str, interval_seconds
