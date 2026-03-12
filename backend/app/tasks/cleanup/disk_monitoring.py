"""Disk space monitoring tasks.

This module provides automated disk space monitoring tasks for:
- Disk space usage alerts (when usage exceeds threshold)

All tasks are designed to be:
- Idempotent (safe to run multiple times)
- Non-destructive (read-only monitoring)
- Scheduled via Hatchet cron workflows
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

import yaml

from app.logging_config import get_logger
from app.tasks.maintenance_logging import (
    log_maintenance_complete,
    log_maintenance_start,
    record_maintenance_metric,
)
from app.utils.task_helpers import build_error_result, calculate_duration

logger = get_logger(__name__)

_DEFAULT_DISK_ALERT_THRESHOLD_PERCENT = 85


def _bytes_to_mb(bytes_value: int) -> float:
    """Convert bytes to megabytes, rounded to 2 decimal places."""
    return round(bytes_value / (1024 * 1024), 2)


def _load_disk_alert_threshold() -> int:
    """Load the disk alert threshold from maintenance config."""
    config_path = Path(__file__).parent.parent.parent / "config" / "maintenance_config.yaml"
    if not config_path.exists():
        return _DEFAULT_DISK_ALERT_THRESHOLD_PERCENT

    try:
        with config_path.open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file) or {}
    except Exception as exc:
        logger.warning("disk_threshold_load_failed", error=str(exc), path=str(config_path))
        return _DEFAULT_DISK_ALERT_THRESHOLD_PERCENT

    threshold = config.get("monitoring", {}).get("disk_space_alert_threshold")
    if isinstance(threshold, int) and 0 <= threshold <= 100:
        return threshold
    return _DEFAULT_DISK_ALERT_THRESHOLD_PERCENT


def check_disk_space_impl(alert_threshold_percent: int) -> dict[str, Any]:
    """Check disk space usage and alert if it exceeds the configured threshold.

    Returns:
        Dict with partitions, alerts
    """
    partitions_info = []
    alerts = []

    # Check key partitions
    paths_to_check = [
        ("/", "root"),
        ("/tmp", "tmp"),
        ("/var/log", "var_log"),
    ]

    for path, name in paths_to_check:
        if not Path(path).exists():
            continue

        try:
            stat = shutil.disk_usage(path)
            used_percentage = (stat.used / stat.total) * 100

            partition_info = {
                "path": path,
                "name": name,
                "total_bytes": stat.total,
                "used_bytes": stat.used,
                "free_bytes": stat.free,
                "used_percentage": round(used_percentage, 2),
            }
            partitions_info.append(partition_info)

            if used_percentage > alert_threshold_percent:
                alert = {
                    "partition": path,
                    "used_percentage": round(used_percentage, 2),
                    "free_mb": _bytes_to_mb(stat.free),
                    "threshold_percent": alert_threshold_percent,
                }
                alerts.append(alert)
                logger.warning("disk_space_alert", **alert)

            # Store metric in maintenance_stats
            record_maintenance_metric(
                f"disk_space_used_percentage_{name}",
                used_percentage,
                "percentage",
                json.dumps({"partition": path, "threshold_percent": alert_threshold_percent}),
            )

        except Exception as partition_error:
            logger.error(
                "disk_space_check_failed",
                partition=path,
                error=str(partition_error),
            )

    return {
        "partitions": partitions_info,
        "alerts": alerts,
        "alert_count": len(alerts),
        "alert_threshold_percent": alert_threshold_percent,
        "success": True,
    }


def check_disk_space_task(
    ) -> dict[str, int | str | float | list[dict[str, Any]]]:
    """Check disk space usage and alert if >85%.

    Returns:
        Dict with task_id, partitions, alerts, duration_seconds
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("check_disk_space_task", dry_run=False)
    alert_threshold_percent = _load_disk_alert_threshold()

    logger.info(
        "check_disk_space_started",
        task_id=task_id,
        alert_threshold_percent=alert_threshold_percent,
    )

    try:
        result = check_disk_space_impl(alert_threshold_percent)
        duration = calculate_duration(start_time)

        result_dict: dict[str, int | str | float | list[dict[str, Any]]] = {
            "task_id": task_id,
            **result,
            "duration_seconds": round(duration, 2),
        }

        logger.info("check_disk_space_completed", **result_dict)
        log_maintenance_complete(log_id, "check_disk_space_task", True, result_dict)
        return result_dict

    except Exception as e:
        duration = calculate_duration(start_time)
        logger.error(
            "check_disk_space_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = build_error_result(task_id, e, duration)
        log_maintenance_complete(log_id, "check_disk_space_task", False, error_result, str(e))
        return error_result
