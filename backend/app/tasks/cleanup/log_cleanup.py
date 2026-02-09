"""Log file rotation and cleanup tasks.

This module provides automated log cleanup tasks for:
- Log file rotation (when files exceed size threshold)
- Old log file deletion (based on retention period)

All tasks are designed to be:
- Idempotent (safe to run multiple times)
- Non-destructive (respect retention periods)
- Scheduled via Hatchet cron workflows
"""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path
from typing import Any

from app.logging_config import get_logger
from app.tasks.maintenance_logging import (
    log_maintenance_complete,
    log_maintenance_start,
)
from app.utils.task_helpers import build_error_result, calculate_duration

logger = get_logger(__name__)

# Constants
LOG_ROTATION_SIZE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10MB
SECONDS_PER_DAY = 86400


# Helper functions (pure logic, no Celery)


def _bytes_to_mb(bytes_value: int) -> float:
    """Convert bytes to megabytes, rounded to 2 decimal places."""
    return round(bytes_value / (1024 * 1024), 2)


def _get_log_directories() -> list[Path]:
    """Get list of log directories to check for cleanup operations.

    Returns:
        List of Path objects for log directories (backend logs, /tmp, legacy /var/log)
    """
    backend_logs = Path(__file__).parent.parent.parent.parent / "logs"
    return [
        backend_logs,  # Primary: ~/portfolio-ai/backend/logs/
        Path("/tmp"),  # Secondary: temp logs
        Path("/var/log/portfolio-ai"),  # Legacy: system logs (if exists)
    ]


def _build_cleanup_result(
    task_id: str,
    dry_run: bool,
    duration_seconds: float,
    task_specific_fields: dict[str, Any],
    would_action_list: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build standardized success result dict for cleanup tasks.

    Args:
        task_id: The task ID
        dry_run: Whether this was a dry run
        duration_seconds: Task execution duration in seconds
        task_specific_fields: Task-specific fields to merge (e.g., files_deleted, bytes_freed)
        would_action_list: Optional list of actions that would be taken in dry run mode

    Returns:
        Standardized result dict with task_id, dry_run, duration_seconds, success=True,
        and all task-specific fields merged in
    """
    result: dict[str, Any] = {
        "task_id": task_id,
        "dry_run": dry_run,
        "duration_seconds": round(duration_seconds, 2),
        "success": True,
        **task_specific_fields,
    }
    if would_action_list and len(would_action_list) > 0:
        result["would_action_list"] = would_action_list
    return result


def _calculate_cutoff_timestamp(
    days: int | None = None,
    hours: int | None = None,
) -> tuple[dt.datetime, float]:
    """Calculate cutoff datetime and timestamp for cleanup operations.

    Args:
        days: Number of days for retention period
        hours: Number of hours for retention period (alternative to days)

    Returns:
        Tuple of (cutoff_datetime, cutoff_timestamp)
    """
    if hours is not None:
        cutoff_time = dt.datetime.now(dt.UTC) - dt.timedelta(hours=hours)
    elif days is not None:
        cutoff_time = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    else:
        # Default to 30 days
        cutoff_time = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)
    return cutoff_time, cutoff_time.timestamp()


def _record_cleanup_metric(metric_name: str, bytes_freed: int, dry_run: bool) -> None:
    """Record cleanup metric in maintenance_stats if bytes were freed and not a dry run.

    Args:
        metric_name: Name of the metric to record
        bytes_freed: Number of bytes freed by the cleanup operation
        dry_run: Whether this was a dry run
    """
    from app.tasks.maintenance_logging import record_maintenance_metric

    if bytes_freed > 0 and not dry_run:
        record_maintenance_metric(metric_name, bytes_freed, "bytes")


def _cleanup_files(
    file_iterator: list[Path],
    filter_func: Any,
    dry_run: bool,
    logger_event: str,
) -> tuple[int, int, list[dict[str, Any]]]:
    """Generic file cleanup helper that encapsulates file iteration, deletion, and tracking.

    Iterates through files, applies filter function to each, and either tracks deletions
    (dry_run) or performs actual deletion and logs the action.

    Args:
        file_iterator: Iterator yielding file paths to potentially delete
        filter_func: Callable that takes (file_path, stat_result) and returns
                     (should_delete: bool, metadata: dict[str, Any]) or (False, {}) if should skip
        dry_run: If True, only track would_delete instead of actually deleting
        logger_event: Event name for logging success/error messages

    Returns:
        Tuple of (files_deleted: int, bytes_freed: int, would_delete: list[dict])
    """
    files_deleted = 0
    bytes_freed = 0
    would_delete: list[dict[str, Any]] = []

    for file_path in file_iterator:
        try:
            stat = file_path.stat()
            should_delete, metadata = filter_func(file_path, stat)

            if not should_delete:
                continue

            file_size = stat.st_size

            if dry_run:
                would_delete.append(
                    {
                        "file": str(file_path),
                        "size_bytes": file_size,
                        **metadata,
                    }
                )
                files_deleted += 1
                bytes_freed += file_size
            else:
                file_path.unlink()
                files_deleted += 1
                bytes_freed += file_size
                logger.info(
                    f"{logger_event}_deleted",
                    file=str(file_path),
                    size_bytes=file_size,
                )

        except Exception as file_error:
            logger.error(
                f"{logger_event}_deletion_failed",
                file=str(file_path),
                error=str(file_error),
            )

    return files_deleted, bytes_freed, would_delete


def rotate_logs_task(
    dry_run: bool = False
) -> dict[str, int | str | float | bool]:
    """Rotate logs in /tmp and /var/log/portfolio-ai directories.

    Args:
        dry_run: If True, only report what would be rotated

    Returns:
        Dict with task_id, files_rotated, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("rotate_logs_task", dry_run)

    logger.info("rotate_logs_started", task_id=task_id, dry_run=dry_run)

    try:
        files_rotated = 0
        would_rotate: list[dict[str, Any]] = []
        log_dirs = _get_log_directories()

        for log_dir in log_dirs:
            if not log_dir.exists():
                logger.warning("log_directory_not_found", directory=str(log_dir))
                continue

            # Find .log files
            log_files = list(log_dir.glob("*.log"))

            for log_file in log_files:
                try:
                    file_size = log_file.stat().st_size
                    # Check if file size > 10MB
                    if file_size > LOG_ROTATION_SIZE_THRESHOLD_BYTES:
                        if dry_run:
                            would_rotate.append(
                                {
                                    "file": str(log_file),
                                    "size_bytes": file_size,
                                    "size_mb": _bytes_to_mb(file_size),
                                }
                            )
                            files_rotated += 1
                        else:
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

        duration = calculate_duration(start_time)

        result = _build_cleanup_result(
            task_id=task_id,
            dry_run=dry_run,
            duration_seconds=duration,
            task_specific_fields={
                "files_rotated": files_rotated,
            },
            would_action_list=would_rotate if dry_run else None,
        )

        logger.info(
            "rotate_logs_completed", **{k: v for k, v in result.items() if k != "would_action_list"}
        )
        log_maintenance_complete(log_id, "rotate_logs_task", True, result)
        return result

    except Exception as e:
        duration = calculate_duration(start_time)
        logger.error(
            "rotate_logs_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(log_id, "rotate_logs_task", False, error_result, str(e))
        return error_result


def cleanup_old_logs_task(
    days: int = 7, dry_run: bool = False
) -> dict[str, Any]:
    """Delete log files older than specified days.

    Args:
        days: Delete logs older than N days (default: 7)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_old_logs_task", dry_run)

    logger.info("cleanup_old_logs_started", task_id=task_id, days=days, dry_run=dry_run)

    try:
        cutoff_time, cutoff_timestamp = _calculate_cutoff_timestamp(days=days)

        log_dirs = _get_log_directories()

        # Collect all log files from all directories
        all_log_files: list[Path] = []
        for log_dir in log_dirs:
            if not log_dir.exists():
                logger.warning("log_directory_not_found", directory=str(log_dir))
                continue
            # Find all rotated log files (.log.TIMESTAMP, .log.1, .log.2, etc.)
            all_log_files.extend(log_dir.glob("*.log.*"))

        # Define filter function for log files
        def log_file_filter(file_path: Path, stat: Any) -> tuple[bool, dict[str, Any]]:
            mtime = stat.st_mtime
            if mtime < cutoff_timestamp:
                age_days = (cutoff_time.timestamp() - mtime) / SECONDS_PER_DAY + days
                return True, {"age_days": round(age_days, 1)}
            return False, {}

        # Use helper to perform cleanup
        files_deleted, bytes_freed, would_delete = _cleanup_files(
            all_log_files, log_file_filter, dry_run, "log_file"
        )

        # Store metric in maintenance_stats (only if not dry run)
        _record_cleanup_metric("log_cleanup_bytes_freed", bytes_freed, dry_run)

        duration = calculate_duration(start_time)

        result = _build_cleanup_result(
            task_id=task_id,
            dry_run=dry_run,
            duration_seconds=duration,
            task_specific_fields={
                "files_deleted": files_deleted,
                "bytes_freed": bytes_freed,
                "bytes_freed_mb": _bytes_to_mb(bytes_freed),
                "retention_days": days,
            },
            would_action_list=would_delete if dry_run else None,
        )

        logger.info(
            "cleanup_old_logs_completed",
            **{k: v for k, v in result.items() if k != "would_action_list"},
        )
        log_maintenance_complete(log_id, "cleanup_old_logs_task", True, result)
        return result

    except Exception as e:
        duration = calculate_duration(start_time)
        logger.error(
            "cleanup_old_logs_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(log_id, "cleanup_old_logs_task", False, error_result, str(e))
        return error_result
