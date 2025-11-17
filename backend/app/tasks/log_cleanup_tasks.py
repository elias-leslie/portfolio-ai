"""Celery tasks for log and temporary file cleanup operations.

This module provides automated cleanup tasks for:
- Log file rotation and cleanup
- Temporary file cleanup
- Disk space monitoring

All tasks are designed to be:
- Idempotent (safe to run multiple times)
- Non-destructive (respect retention periods)
- Scheduled (run on Celery Beat schedule)
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

if TYPE_CHECKING:
    from celery import Task  # type: ignore[import-untyped]

logger = get_logger(__name__)


@celery_app.task(name="rotate_logs_task", bind=True)  # type: ignore[misc]
def rotate_logs_task(self: Task) -> dict[str, int | str | float]:
    """Rotate logs in /tmp and /var/log/portfolio-ai directories.

    Returns:
        Dict with task_id, files_rotated, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("rotate_logs_started", task_id=task_id)

    try:
        files_rotated = 0
        log_dirs = [
            Path("/tmp"),
            Path("/var/log/portfolio-ai"),
        ]

        for log_dir in log_dirs:
            if not log_dir.exists():
                logger.warning("log_directory_not_found", directory=str(log_dir))
                continue

            # Find .log files
            log_files = list(log_dir.glob("*.log"))

            for log_file in log_files:
                try:
                    # Check if file size > 10MB
                    if log_file.stat().st_size > 10 * 1024 * 1024:
                        # Rotate: rename to .log.1, .log.2, etc.
                        timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
                        rotated_name = log_file.with_suffix(f".log.{timestamp}")
                        log_file.rename(rotated_name)
                        files_rotated += 1
                        logger.info(
                            "log_file_rotated",
                            file=str(log_file),
                            new_name=str(rotated_name),
                        )
                except Exception as file_error:
                    logger.error(
                        "log_rotation_failed",
                        file=str(log_file),
                        error=str(file_error),
                    )

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result = {
            "task_id": task_id,
            "files_rotated": files_rotated,
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("rotate_logs_completed", **result)
        return result

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "rotate_logs_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }


@celery_app.task(name="cleanup_old_logs_task", bind=True)  # type: ignore[misc]
def cleanup_old_logs_task(self: Task, days: int = 7) -> dict[str, int | str | float]:
    """Delete log files older than specified days.

    Args:
        days: Delete logs older than N days (default: 7)

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("cleanup_old_logs_started", task_id=task_id, days=days)

    try:
        files_deleted = 0
        bytes_freed = 0
        cutoff_time = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
        cutoff_timestamp = cutoff_time.timestamp()

        log_dirs = [
            Path("/tmp"),
            Path("/var/log/portfolio-ai"),
        ]

        for log_dir in log_dirs:
            if not log_dir.exists():
                logger.warning("log_directory_not_found", directory=str(log_dir))
                continue

            # Find all rotated log files (.log.TIMESTAMP, .log.1, .log.2, etc.)
            log_files = list(log_dir.glob("*.log.*"))

            for log_file in log_files:
                try:
                    # Check file modification time
                    mtime = log_file.stat().st_mtime
                    if mtime < cutoff_timestamp:
                        file_size = log_file.stat().st_size
                        log_file.unlink()
                        files_deleted += 1
                        bytes_freed += file_size
                        logger.info(
                            "log_file_deleted",
                            file=str(log_file),
                            size_bytes=file_size,
                        )
                except Exception as file_error:
                    logger.error(
                        "log_deletion_failed",
                        file=str(log_file),
                        error=str(file_error),
                    )

        # Store metric in maintenance_stats
        if bytes_freed > 0:
            storage = get_connection_manager()
            with storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO maintenance_stats (metric_name, metric_value, metric_unit)
                    VALUES (%s, %s, %s)
                    """,
                    ["log_cleanup_bytes_freed", bytes_freed, "bytes"],
                )
                conn.commit()

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result = {
            "task_id": task_id,
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": round(bytes_freed / (1024 * 1024), 2),
            "retention_days": days,
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("cleanup_old_logs_completed", **result)
        return result

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "cleanup_old_logs_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }


@celery_app.task(name="cleanup_temp_files_task", bind=True)  # type: ignore[misc]
def cleanup_temp_files_task(self: Task, hours: int = 24) -> dict[str, int | str | float]:
    """Delete temporary files older than specified hours.

    Args:
        hours: Delete temp files older than N hours (default: 24)

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("cleanup_temp_files_started", task_id=task_id, hours=hours)

    try:
        files_deleted = 0
        bytes_freed = 0
        cutoff_time = dt.datetime.now(dt.UTC) - dt.timedelta(hours=hours)
        cutoff_timestamp = cutoff_time.timestamp()

        temp_dir = Path("/tmp")

        # Patterns for temp files to clean up
        temp_patterns = [
            "portfolio-ai-*",
            "celery-*",
            "tmpfile*",
            "*.tmp",
        ]

        for pattern in temp_patterns:
            temp_files = list(temp_dir.glob(pattern))

            for temp_file in temp_files:
                try:
                    # Skip directories for now
                    if temp_file.is_dir():
                        continue

                    # Check file modification time
                    mtime = temp_file.stat().st_mtime
                    if mtime < cutoff_timestamp:
                        file_size = temp_file.stat().st_size
                        temp_file.unlink()
                        files_deleted += 1
                        bytes_freed += file_size
                except Exception as file_error:
                    logger.error(
                        "temp_file_deletion_failed",
                        file=str(temp_file),
                        error=str(file_error),
                    )

        # Store metric in maintenance_stats
        if bytes_freed > 0:
            storage = get_connection_manager()
            with storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO maintenance_stats (metric_name, metric_value, metric_unit)
                    VALUES (%s, %s, %s)
                    """,
                    ["temp_cleanup_bytes_freed", bytes_freed, "bytes"],
                )
                conn.commit()

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result = {
            "task_id": task_id,
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": round(bytes_freed / (1024 * 1024), 2),
            "retention_hours": hours,
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("cleanup_temp_files_completed", **result)
        return result

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "cleanup_temp_files_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }


@celery_app.task(name="check_disk_space_task", bind=True)  # type: ignore[misc]
def check_disk_space_task(self: Task) -> dict[str, int | str | float | list[dict[str, Any]]]:
    """Check disk space usage and alert if >85%.

    Returns:
        Dict with task_id, partitions, alerts, duration_seconds
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("check_disk_space_started", task_id=task_id)

    try:
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

                # Alert if usage > 85%
                if used_percentage > 85:
                    alert = {
                        "partition": path,
                        "used_percentage": round(used_percentage, 2),
                        "free_mb": round(stat.free / (1024 * 1024), 2),
                    }
                    alerts.append(alert)
                    logger.warning("disk_space_alert", **alert)

                # Store metric in maintenance_stats
                storage = get_connection_manager()
                with storage.connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO maintenance_stats (metric_name, metric_value, metric_unit, metadata)
                        VALUES (%s, %s, %s, %s)
                        """,
                        [
                            f"disk_space_used_percentage_{name}",
                            used_percentage,
                            "percentage",
                            f'{{"partition": "{path}"}}',
                        ],
                    )
                    conn.commit()

            except Exception as partition_error:
                logger.error(
                    "disk_space_check_failed",
                    partition=path,
                    error=str(partition_error),
                )

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result_dict: dict[str, int | str | float | list[dict[str, Any]]] = {
            "task_id": task_id,
            "partitions": partitions_info,
            "alerts": alerts,
            "alert_count": len(alerts),
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("check_disk_space_completed", **result_dict)
        return result_dict

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "check_disk_space_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }
