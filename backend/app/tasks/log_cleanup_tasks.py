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
from app.tasks.maintenance_logging import (
    log_maintenance_complete,
    log_maintenance_start,
    record_maintenance_metric,
)

if TYPE_CHECKING:
    from celery import Task

logger = get_logger(__name__)

# Constants
LOG_ROTATION_SIZE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10MB
DISK_ALERT_THRESHOLD_PERCENT = 85
SECONDS_PER_DAY = 86400
SECONDS_PER_HOUR = 3600

# Helper functions (pure logic, no Celery)


def _bytes_to_mb(bytes_value: int) -> float:
    """Convert bytes to megabytes, rounded to 2 decimal places."""
    return round(bytes_value / (1024 * 1024), 2)


def _get_log_directories() -> list[Path]:
    """Get list of log directories to check for cleanup operations.

    Returns:
        List of Path objects for log directories (backend logs, /tmp, legacy /var/log)
    """
    backend_logs = Path(__file__).parent.parent.parent / "logs"
    return [
        backend_logs,  # Primary: ~/portfolio-ai/backend/logs/
        Path("/tmp"),  # Secondary: temp logs
        Path("/var/log/portfolio-ai"),  # Legacy: system logs (if exists)
    ]


def _build_error_result(
    task_id: str,
    error: Exception,
    duration_seconds: float,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """Build standardized error result dict for cleanup tasks."""
    result: dict[str, Any] = {
        "task_id": task_id,
        "error": str(error),
        "success": False,
        "duration_seconds": round(duration_seconds, 2),
    }
    if dry_run is not None:
        result["dry_run"] = dry_run
    return result


def _build_cleanup_result(
    task_id: str,
    dry_run: bool,
    duration_seconds: float,
    task_specific_fields: dict[str, Any],
    would_action_list: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build standardized success result dict for cleanup tasks.

    Args:
        task_id: The Celery task ID
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


def _calculate_directory_size(directory: Path) -> tuple[int, int]:
    """Calculate total size and file count of a directory.

    Args:
        directory: Path to the directory to measure

    Returns:
        Tuple of (total_bytes, file_count)
    """
    total_bytes = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
    file_count = sum(1 for f in directory.rglob("*") if f.is_file())
    return total_bytes, file_count


def _handle_missing_directory(
    task_id: str,
    dry_run: bool,
    directory_path: Path,
    task_name: str,
    log_id: int,
) -> dict[str, Any] | None:
    """Handle missing directory for cleanup tasks.

    Args:
        task_id: The Celery task ID
        dry_run: Whether this was a dry run
        directory_path: Path to the directory to check
        task_name: Name of the task (for logging)
        log_id: Maintenance log ID

    Returns:
        Early result dict if directory doesn't exist, None otherwise
    """
    if not directory_path.exists():
        logger.warning(f"{task_name}_directory_not_found", directory=str(directory_path))
        early_result = {
            "task_id": task_id,
            "dry_run": dry_run,
            "files_deleted": 0,
            "bytes_freed": 0,
            "message": f"{task_name.replace('_', ' ').title()} directory not found",
            "success": True,
            "duration_seconds": 0.0,
        }
        log_maintenance_complete(log_id, task_name, True, early_result)
        return early_result
    return None


def _get_cache_targets(project_root: Path) -> list[dict[str, Any]]:
    """Get list of cache targets for cleanup operations.

    Args:
        project_root: Root path of the project

    Returns:
        List of cache target configurations with name, path, pattern, and recursive flags
    """
    return [
        # Python caches (recursive __pycache__ cleanup)
        {
            "name": "Python bytecode cache",
            "path": project_root / "backend",
            "pattern": "__pycache__",
            "recursive": True,
        },
        {
            "name": "Services Python cache",
            "path": project_root / "services",
            "pattern": "__pycache__",
            "recursive": True,
        },
        # Linter/test caches (single directories)
        {
            "name": "Ruff cache",
            "path": project_root / "backend" / ".ruff_cache",
            "pattern": None,
            "recursive": False,
        },
        {
            "name": "Pytest cache",
            "path": project_root / "backend" / ".pytest_cache",
            "pattern": None,
            "recursive": False,
        },
        {
            "name": "Mypy cache",
            "path": project_root / "backend" / ".mypy_cache",
            "pattern": None,
            "recursive": False,
        },
        # Frontend cache (only .next/cache, not server)
        {
            "name": "Next.js cache",
            "path": project_root / "frontend" / ".next" / "cache",
            "pattern": None,
            "recursive": False,
        },
        # Claude transient memory
        {
            "name": "Claude memory backups",
            "path": project_root / ".claude" / "backups" / "memory",
            "pattern": None,
            "recursive": False,
        },
    ]


def check_disk_space_impl() -> dict[str, Any]:
    """Check disk space usage and alert if >85%.

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

            # Alert if usage > 85%
            if used_percentage > DISK_ALERT_THRESHOLD_PERCENT:
                alert = {
                    "partition": path,
                    "used_percentage": round(used_percentage, 2),
                    "free_mb": _bytes_to_mb(stat.free),
                }
                alerts.append(alert)
                logger.warning("disk_space_alert", **alert)

            # Store metric in maintenance_stats
            record_maintenance_metric(
                f"disk_space_used_percentage_{name}",
                used_percentage,
                "percentage",
                f'{{"partition": "{path}"}}',
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
        "success": True,
    }


@celery_app.task(name="rotate_logs_task", bind=True)
def rotate_logs_task(self: Task, dry_run: bool = False) -> dict[str, int | str | float | bool]:
    """Rotate logs in /tmp and /var/log/portfolio-ai directories.

    Args:
        dry_run: If True, only report what would be rotated

    Returns:
        Dict with task_id, files_rotated, duration_seconds, success status
    """
    task_id = self.request.id
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

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result: dict[str, Any] = {
            "task_id": task_id,
            "dry_run": dry_run,
            "files_rotated": files_rotated,
            "duration_seconds": round(duration, 2),
            "success": True,
        }
        if dry_run and would_rotate:
            result["would_rotate"] = would_rotate

        logger.info(
            "rotate_logs_completed", **{k: v for k, v in result.items() if k != "would_rotate"}
        )
        log_maintenance_complete(log_id, "rotate_logs_task", True, result)
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
        error_result = _build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(log_id, "rotate_logs_task", False, error_result, str(e))
        return error_result


@celery_app.task(name="cleanup_old_logs_task", bind=True)
def cleanup_old_logs_task(self: Task, days: int = 7, dry_run: bool = False) -> dict[str, Any]:
    """Delete log files older than specified days.

    Args:
        days: Delete logs older than N days (default: 7)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_old_logs_task", dry_run)

    logger.info("cleanup_old_logs_started", task_id=task_id, days=days, dry_run=dry_run)

    try:
        files_deleted = 0
        bytes_freed = 0
        would_delete: list[dict[str, Any]] = []
        cutoff_time, cutoff_timestamp = _calculate_cutoff_timestamp(days=days)

        log_dirs = _get_log_directories()

        for log_dir in log_dirs:
            if not log_dir.exists():
                logger.warning("log_directory_not_found", directory=str(log_dir))
                continue

            # Find all rotated log files (.log.TIMESTAMP, .log.1, .log.2, etc.)
            log_files = list(log_dir.glob("*.log.*"))

            for log_file in log_files:
                try:
                    # Check file modification time
                    stat = log_file.stat()
                    mtime = stat.st_mtime
                    if mtime < cutoff_timestamp:
                        file_size = stat.st_size
                        age_days = (cutoff_time.timestamp() - mtime) / SECONDS_PER_DAY + days

                        if dry_run:
                            would_delete.append(
                                {
                                    "file": str(log_file),
                                    "size_bytes": file_size,
                                    "age_days": round(age_days, 1),
                                }
                            )
                            files_deleted += 1
                            bytes_freed += file_size
                        else:
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

        # Store metric in maintenance_stats (only if not dry run)
        if bytes_freed > 0 and not dry_run:
            record_maintenance_metric("log_cleanup_bytes_freed", bytes_freed, "bytes")

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

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
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "cleanup_old_logs_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = _build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(log_id, "cleanup_old_logs_task", False, error_result, str(e))
        return error_result


@celery_app.task(name="cleanup_temp_files_task", bind=True)
def cleanup_temp_files_task(self: Task, hours: int = 24, dry_run: bool = False) -> dict[str, Any]:
    """Delete temporary files older than specified hours.

    Args:
        hours: Delete temp files older than N hours (default: 24)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_temp_files_task", dry_run)

    logger.info("cleanup_temp_files_started", task_id=task_id, hours=hours, dry_run=dry_run)

    try:
        files_deleted = 0
        bytes_freed = 0
        would_delete: list[dict[str, Any]] = []
        cutoff_time, cutoff_timestamp = _calculate_cutoff_timestamp(hours=hours)

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
                    stat = temp_file.stat()
                    mtime = stat.st_mtime
                    if mtime < cutoff_timestamp:
                        file_size = stat.st_size
                        age_hours = (cutoff_time.timestamp() - mtime) / SECONDS_PER_HOUR + hours

                        if dry_run:
                            would_delete.append(
                                {
                                    "file": str(temp_file),
                                    "size_bytes": file_size,
                                    "age_hours": round(age_hours, 1),
                                }
                            )
                            files_deleted += 1
                            bytes_freed += file_size
                        else:
                            temp_file.unlink()
                            files_deleted += 1
                            bytes_freed += file_size
                except Exception as file_error:
                    logger.error(
                        "temp_file_deletion_failed",
                        file=str(temp_file),
                        error=str(file_error),
                    )

        # Store metric in maintenance_stats (only if not dry run)
        if bytes_freed > 0 and not dry_run:
            record_maintenance_metric("temp_cleanup_bytes_freed", bytes_freed, "bytes")

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result: dict[str, Any] = {
            "task_id": task_id,
            "dry_run": dry_run,
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": _bytes_to_mb(bytes_freed),
            "retention_hours": hours,
            "duration_seconds": round(duration, 2),
            "success": True,
        }
        if dry_run and would_delete:
            result["would_delete"] = would_delete

        logger.info(
            "cleanup_temp_files_completed",
            **{k: v for k, v in result.items() if k != "would_delete"},
        )
        log_maintenance_complete(log_id, "cleanup_temp_files_task", True, result)
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
        error_result = _build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(log_id, "cleanup_temp_files_task", False, error_result, str(e))
        return error_result


@celery_app.task(name="check_disk_space_task", bind=True)
def check_disk_space_task(self: Task) -> dict[str, int | str | float | list[dict[str, Any]]]:
    """Check disk space usage and alert if >85%.

    Returns:
        Dict with task_id, partitions, alerts, duration_seconds
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("check_disk_space_started", task_id=task_id)

    try:
        result = check_disk_space_impl()
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result_dict: dict[str, int | str | float | list[dict[str, Any]]] = {
            "task_id": task_id,
            **result,
            "duration_seconds": round(duration, 2),
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
        return _build_error_result(task_id, e, duration)


@celery_app.task(name="cleanup_old_backups_task", bind=True)
def cleanup_old_backups_task(
    self: Task, keep_count: int = 5, dry_run: bool = False
) -> dict[str, Any]:
    """Delete old backup files, keeping N most recent.

    Args:
        keep_count: Number of recent backups to keep (default: 5)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_old_backups_task", dry_run)

    logger.info(
        "cleanup_old_backups_started", task_id=task_id, keep_count=keep_count, dry_run=dry_run
    )

    try:
        files_deleted = 0
        bytes_freed = 0
        would_delete: list[dict[str, Any]] = []

        # Backups directory
        backup_dir = Path(__file__).parent.parent.parent.parent / "backups"

        # Check if directory exists
        early_exit = _handle_missing_directory(
            task_id, dry_run, backup_dir, "cleanup_old_backups_task", log_id
        )
        if early_exit:
            return early_exit

        # Find all backup files (SQL dumps)
        backup_patterns = ["*.sql", "*.sql.gz", "*.sql.bz2"]
        backup_files: list[tuple[Path, float, int]] = []

        for pattern in backup_patterns:
            for f in backup_dir.glob(pattern):
                if f.is_file():
                    stat = f.stat()
                    backup_files.append((f, stat.st_mtime, stat.st_size))

        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x[1], reverse=True)

        # Delete files beyond keep_count
        now = dt.datetime.now(dt.UTC).timestamp()
        for file_path, mtime, file_size in backup_files[keep_count:]:
            try:
                age_days = (now - mtime) / SECONDS_PER_DAY

                if dry_run:
                    would_delete.append(
                        {
                            "file": str(file_path),
                            "size_bytes": file_size,
                            "age_days": round(age_days, 1),
                        }
                    )
                    files_deleted += 1
                    bytes_freed += file_size
                else:
                    file_path.unlink()
                    files_deleted += 1
                    bytes_freed += file_size
                    logger.info(
                        "backup_file_deleted",
                        file=str(file_path),
                        size_bytes=file_size,
                    )
            except Exception as file_error:
                logger.error(
                    "backup_deletion_failed",
                    file=str(file_path),
                    error=str(file_error),
                )

        # Store metric in maintenance_stats (only if not dry run)
        if bytes_freed > 0 and not dry_run:
            record_maintenance_metric("backup_cleanup_bytes_freed", bytes_freed, "bytes")

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result: dict[str, Any] = {
            "task_id": task_id,
            "dry_run": dry_run,
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": _bytes_to_mb(bytes_freed),
            "keep_count": keep_count,
            "total_backups": len(backup_files),
            "duration_seconds": round(duration, 2),
            "success": True,
        }
        if dry_run and would_delete:
            result["would_delete"] = would_delete

        logger.info(
            "cleanup_old_backups_completed",
            **{k: v for k, v in result.items() if k != "would_delete"},
        )
        log_maintenance_complete(log_id, "cleanup_old_backups_task", True, result)
        return result

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "cleanup_old_backups_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = _build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(log_id, "cleanup_old_backups_task", False, error_result, str(e))
        return error_result


@celery_app.task(name="cleanup_old_models_task", bind=True)
def cleanup_old_models_task(
    self: Task, keep_count: int = 3, dry_run: bool = False
) -> dict[str, Any]:
    """Delete old ML model versions, keeping N most recent per model type.

    Args:
        keep_count: Number of recent versions to keep per model type (default: 3)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_old_models_task", dry_run)

    logger.info(
        "cleanup_old_models_started", task_id=task_id, keep_count=keep_count, dry_run=dry_run
    )

    try:
        files_deleted = 0
        bytes_freed = 0
        would_delete: list[dict[str, Any]] = []

        # Models directory
        models_dir = Path(__file__).parent.parent.parent / "models"

        if not models_dir.exists():
            logger.warning("models_directory_not_found", directory=str(models_dir))
            early_result = {
                "task_id": task_id,
                "dry_run": dry_run,
                "files_deleted": 0,
                "bytes_freed": 0,
                "message": "Models directory not found",
                "success": True,
                "duration_seconds": 0.0,
            }
            log_maintenance_complete(log_id, "cleanup_old_models_task", True, early_result)
            return early_result

        # Group model files by base name (e.g., article_quality_v*.joblib)
        # Pattern: {model_name}_v{date}.joblib
        import re

        model_groups: dict[str, list[tuple[Path, str, int]]] = {}
        model_pattern = re.compile(r"^(.+)_v(\d{8})\.joblib$")

        for f in models_dir.glob("*.joblib"):
            if f.is_symlink():
                # Skip symlinks (like article_quality_v1.joblib -> latest)
                continue
            match = model_pattern.match(f.name)
            if match:
                model_name = match.group(1)
                date_str = match.group(2)
                file_size = f.stat().st_size
                if model_name not in model_groups:
                    model_groups[model_name] = []
                model_groups[model_name].append((f, date_str, file_size))

        # For each model group, keep only the N most recent
        for model_name, versions in model_groups.items():
            # Sort by date (newest first)
            versions.sort(key=lambda x: x[1], reverse=True)

            # Delete versions beyond keep_count
            for file_path, date_str, file_size in versions[keep_count:]:
                try:
                    if dry_run:
                        would_delete.append(
                            {
                                "file": str(file_path),
                                "model_name": model_name,
                                "version_date": date_str,
                                "size_bytes": file_size,
                            }
                        )
                        files_deleted += 1
                        bytes_freed += file_size
                    else:
                        file_path.unlink()
                        files_deleted += 1
                        bytes_freed += file_size
                        logger.info(
                            "model_file_deleted",
                            file=str(file_path),
                            model_name=model_name,
                            version_date=date_str,
                            size_bytes=file_size,
                        )
                except Exception as file_error:
                    logger.error(
                        "model_deletion_failed",
                        file=str(file_path),
                        error=str(file_error),
                    )

        # Store metric in maintenance_stats (only if not dry run)
        if bytes_freed > 0 and not dry_run:
            record_maintenance_metric("model_cleanup_bytes_freed", bytes_freed, "bytes")

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result: dict[str, Any] = {
            "task_id": task_id,
            "dry_run": dry_run,
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": _bytes_to_mb(bytes_freed),
            "keep_count": keep_count,
            "model_groups": len(model_groups),
            "duration_seconds": round(duration, 2),
            "success": True,
        }
        if dry_run and would_delete:
            result["would_delete"] = would_delete

        logger.info(
            "cleanup_old_models_completed",
            **{k: v for k, v in result.items() if k != "would_delete"},
        )
        log_maintenance_complete(log_id, "cleanup_old_models_task", True, result)
        return result

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "cleanup_old_models_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = _build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(log_id, "cleanup_old_models_task", False, error_result, str(e))
        return error_result


@celery_app.task(name="cleanup_solution_state_task", bind=True)
def cleanup_solution_state_task(
    self: Task, keep_days: int = 14, dry_run: bool = False
) -> dict[str, Any]:
    """Delete old solution_state test artifacts, keeping N days of recent data.

    Args:
        keep_days: Number of days of artifacts to keep (default: 14)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, directories_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_solution_state_task", dry_run)

    logger.info(
        "cleanup_solution_state_started", task_id=task_id, keep_days=keep_days, dry_run=dry_run
    )

    try:
        directories_deleted = 0
        bytes_freed = 0
        would_delete: list[dict[str, Any]] = []

        # Solution state directory
        solution_dir = Path(__file__).parent.parent.parent.parent / "solution_state"

        if not solution_dir.exists():
            logger.warning("solution_state_directory_not_found", directory=str(solution_dir))
            early_result = {
                "task_id": task_id,
                "dry_run": dry_run,
                "directories_deleted": 0,
                "bytes_freed": 0,
                "message": "Solution state directory not found",
                "success": True,
                "duration_seconds": 0.0,
            }
            log_maintenance_complete(log_id, "cleanup_solution_state_task", True, early_result)
            return early_result

        # Calculate cutoff date
        _cutoff_time, cutoff_timestamp = _calculate_cutoff_timestamp(days=keep_days)
        now = dt.datetime.now(dt.UTC).timestamp()

        # Find directories that look like timestamps (YYYYMMDD-HHMMSS format)
        import re

        timestamp_pattern = re.compile(r"^\d{8}-\d{6}$")

        for entry in solution_dir.iterdir():
            if not entry.is_dir():
                continue

            if not timestamp_pattern.match(entry.name):
                continue

            try:
                # Check directory modification time
                mtime = entry.stat().st_mtime
                if mtime < cutoff_timestamp:
                    # Calculate directory size
                    dir_size, _file_count = _calculate_directory_size(entry)
                    age_days = (now - mtime) / SECONDS_PER_DAY

                    if dry_run:
                        would_delete.append(
                            {
                                "directory": str(entry),
                                "size_bytes": dir_size,
                                "age_days": round(age_days, 1),
                            }
                        )
                        directories_deleted += 1
                        bytes_freed += dir_size
                    else:
                        # Delete directory recursively
                        shutil.rmtree(entry)
                        directories_deleted += 1
                        bytes_freed += dir_size
                        logger.info(
                            "solution_state_deleted",
                            directory=str(entry),
                            size_bytes=dir_size,
                        )
            except Exception as dir_error:
                logger.error(
                    "solution_state_deletion_failed",
                    directory=str(entry),
                    error=str(dir_error),
                )

        # Store metric in maintenance_stats (only if not dry run)
        if bytes_freed > 0 and not dry_run:
            record_maintenance_metric("solution_state_cleanup_bytes_freed", bytes_freed, "bytes")

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result: dict[str, Any] = {
            "task_id": task_id,
            "dry_run": dry_run,
            "directories_deleted": directories_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": _bytes_to_mb(bytes_freed),
            "keep_days": keep_days,
            "duration_seconds": round(duration, 2),
            "success": True,
        }
        if dry_run and would_delete:
            result["would_delete"] = would_delete

        logger.info(
            "cleanup_solution_state_completed",
            **{k: v for k, v in result.items() if k != "would_delete"},
        )
        log_maintenance_complete(log_id, "cleanup_solution_state_task", True, result)
        return result

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "cleanup_solution_state_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = _build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(log_id, "cleanup_solution_state_task", False, error_result, str(e))
        return error_result


@celery_app.task(name="cleanup_cache_directories_task", bind=True)
def cleanup_cache_directories_task(self: Task, dry_run: bool = False) -> dict[str, Any]:
    """Clean up development cache directories to free disk space.

    This is an OPTIONAL manual task - not scheduled by default.
    Safe to run anytime as caches regenerate automatically.

    Targets:
    - backend/__pycache__ (recursive)
    - backend/.ruff_cache
    - backend/.pytest_cache
    - backend/.mypy_cache
    - frontend/.next/cache (NOT .next/server)
    - .claude/backups/memory (Claude transient memory)
    - services/*/__pycache__ (recursive)

    Args:
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with directories_cleaned, files_deleted, bytes_freed, duration_seconds
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_cache_directories_task", dry_run)

    logger.info("cleanup_cache_directories_started", task_id=task_id, dry_run=dry_run)

    try:
        directories_cleaned = 0
        files_deleted = 0
        bytes_freed = 0
        details: list[dict[str, Any]] = []

        # Project root
        project_root = Path(__file__).parent.parent.parent.parent

        # Get cache targets with their cleanup strategy
        cache_targets = _get_cache_targets(project_root)

        for target in cache_targets:
            target_name = str(target["name"])
            target_path: Path = target["path"]  # type: ignore[assignment]
            pattern: str | None = target["pattern"]  # type: ignore[assignment]
            recursive: bool = target["recursive"]  # type: ignore[assignment]

            if not target_path.exists():
                logger.debug("cache_target_not_found", target=target_name, path=str(target_path))
                continue

            try:
                if recursive and pattern:
                    # Find all matching directories recursively
                    dirs_to_clean = list(target_path.rglob(pattern))
                else:
                    # Single directory
                    dirs_to_clean = [target_path] if target_path.is_dir() else []

                for cache_dir in dirs_to_clean:
                    if not cache_dir.is_dir():
                        continue

                    # Calculate size before deletion
                    dir_size, file_count = _calculate_directory_size(cache_dir)

                    if dry_run:
                        details.append(
                            {
                                "name": target_name,
                                "path": str(cache_dir),
                                "size_bytes": dir_size,
                                "file_count": file_count,
                                "action": "would_delete",
                            }
                        )
                    else:
                        # Delete directory
                        shutil.rmtree(cache_dir)
                        details.append(
                            {
                                "name": target_name,
                                "path": str(cache_dir),
                                "size_bytes": dir_size,
                                "file_count": file_count,
                                "action": "deleted",
                            }
                        )
                        logger.info(
                            "cache_directory_cleaned",
                            name=target_name,
                            path=str(cache_dir),
                            size_bytes=dir_size,
                            file_count=file_count,
                        )

                    directories_cleaned += 1
                    files_deleted += file_count
                    bytes_freed += dir_size

            except Exception as target_error:
                logger.error(
                    "cache_cleanup_target_failed",
                    target=target_name,
                    path=str(target_path),
                    error=str(target_error),
                )
                details.append(
                    {
                        "name": target_name,
                        "path": str(target_path),
                        "action": "error",
                        "error": str(target_error),
                    }
                )

        # Store metric in maintenance_stats (only if not dry run)
        if bytes_freed > 0 and not dry_run:
            record_maintenance_metric("cache_cleanup_bytes_freed", bytes_freed, "bytes")

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result: dict[str, Any] = {
            "task_id": task_id,
            "dry_run": dry_run,
            "directories_cleaned": directories_cleaned,
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": _bytes_to_mb(bytes_freed),
            "details": details,
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info(
            "cleanup_cache_directories_completed",
            **{k: v for k, v in result.items() if k != "details"},
        )
        log_maintenance_complete(log_id, "cleanup_cache_directories_task", True, result)
        return result

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "cleanup_cache_directories_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = _build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(
            log_id, "cleanup_cache_directories_task", False, error_result, str(e)
        )
        return error_result
