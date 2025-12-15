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
    from celery import Task

logger = get_logger(__name__)


# Helper functions (pure logic, no Celery)


def _check_disk_space_impl() -> dict[str, Any]:
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

    return {
        "partitions": partitions_info,
        "alerts": alerts,
        "alert_count": len(alerts),
        "success": True,
    }


@celery_app.task(name="rotate_logs_task", bind=True)
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
        # Backend logs directory (actual log location)
        backend_logs = Path(__file__).parent.parent.parent / "logs"
        log_dirs = [
            backend_logs,  # Primary: ~/portfolio-ai/backend/logs/
            Path("/tmp"),  # Secondary: temp logs
            Path("/var/log/portfolio-ai"),  # Legacy: system logs (if exists)
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


@celery_app.task(name="cleanup_old_logs_task", bind=True)
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

        # Backend logs directory (actual log location)
        backend_logs = Path(__file__).parent.parent.parent / "logs"
        log_dirs = [
            backend_logs,  # Primary: ~/portfolio-ai/backend/logs/
            Path("/tmp"),  # Secondary: temp logs
            Path("/var/log/portfolio-ai"),  # Legacy: system logs (if exists)
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


@celery_app.task(name="cleanup_temp_files_task", bind=True)
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
        result = _check_disk_space_impl()
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
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }


@celery_app.task(name="cleanup_old_backups_task", bind=True)
def cleanup_old_backups_task(self: Task, keep_count: int = 5) -> dict[str, int | str | float]:
    """Delete old backup files, keeping N most recent.

    Args:
        keep_count: Number of recent backups to keep (default: 5)

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("cleanup_old_backups_started", task_id=task_id, keep_count=keep_count)

    try:
        files_deleted = 0
        bytes_freed = 0

        # Backups directory
        backup_dir = Path(__file__).parent.parent.parent.parent / "backups"

        if not backup_dir.exists():
            logger.warning("backup_directory_not_found", directory=str(backup_dir))
            return {
                "task_id": task_id,
                "files_deleted": 0,
                "bytes_freed": 0,
                "message": "Backup directory not found",
                "success": True,
                "duration_seconds": 0.0,
            }

        # Find all backup files (SQL dumps)
        backup_patterns = ["*.sql", "*.sql.gz", "*.sql.bz2"]
        backup_files: list[tuple[Path, float]] = []

        for pattern in backup_patterns:
            for f in backup_dir.glob(pattern):
                if f.is_file():
                    backup_files.append((f, f.stat().st_mtime))

        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x[1], reverse=True)

        # Delete files beyond keep_count
        for file_path, _ in backup_files[keep_count:]:
            try:
                file_size = file_path.stat().st_size
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

        # Store metric in maintenance_stats
        if bytes_freed > 0:
            storage = get_connection_manager()
            with storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO maintenance_stats (metric_name, metric_value, metric_unit)
                    VALUES (%s, %s, %s)
                    """,
                    ["backup_cleanup_bytes_freed", bytes_freed, "bytes"],
                )
                conn.commit()

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result = {
            "task_id": task_id,
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": round(bytes_freed / (1024 * 1024), 2),
            "keep_count": keep_count,
            "total_backups": len(backup_files),
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("cleanup_old_backups_completed", **result)
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
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }


@celery_app.task(name="cleanup_old_models_task", bind=True)
def cleanup_old_models_task(self: Task, keep_count: int = 3) -> dict[str, int | str | float]:
    """Delete old ML model versions, keeping N most recent per model type.

    Args:
        keep_count: Number of recent versions to keep per model type (default: 3)

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("cleanup_old_models_started", task_id=task_id, keep_count=keep_count)

    try:
        files_deleted = 0
        bytes_freed = 0

        # Models directory
        models_dir = Path(__file__).parent.parent.parent / "models"

        if not models_dir.exists():
            logger.warning("models_directory_not_found", directory=str(models_dir))
            return {
                "task_id": task_id,
                "files_deleted": 0,
                "bytes_freed": 0,
                "message": "Models directory not found",
                "success": True,
                "duration_seconds": 0.0,
            }

        # Group model files by base name (e.g., article_quality_v*.joblib)
        # Pattern: {model_name}_v{date}.joblib
        import re

        model_groups: dict[str, list[tuple[Path, str]]] = {}
        model_pattern = re.compile(r"^(.+)_v(\d{8})\.joblib$")

        for f in models_dir.glob("*.joblib"):
            if f.is_symlink():
                # Skip symlinks (like article_quality_v1.joblib -> latest)
                continue
            match = model_pattern.match(f.name)
            if match:
                model_name = match.group(1)
                date_str = match.group(2)
                if model_name not in model_groups:
                    model_groups[model_name] = []
                model_groups[model_name].append((f, date_str))

        # For each model group, keep only the N most recent
        for model_name, versions in model_groups.items():
            # Sort by date (newest first)
            versions.sort(key=lambda x: x[1], reverse=True)

            # Delete versions beyond keep_count
            for file_path, date_str in versions[keep_count:]:
                try:
                    file_size = file_path.stat().st_size
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

        # Store metric in maintenance_stats
        if bytes_freed > 0:
            storage = get_connection_manager()
            with storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO maintenance_stats (metric_name, metric_value, metric_unit)
                    VALUES (%s, %s, %s)
                    """,
                    ["model_cleanup_bytes_freed", bytes_freed, "bytes"],
                )
                conn.commit()

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result = {
            "task_id": task_id,
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": round(bytes_freed / (1024 * 1024), 2),
            "keep_count": keep_count,
            "model_groups": len(model_groups),
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("cleanup_old_models_completed", **result)
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
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }


@celery_app.task(name="cleanup_solution_state_task", bind=True)
def cleanup_solution_state_task(self: Task, keep_days: int = 14) -> dict[str, int | str | float]:
    """Delete old solution_state test artifacts, keeping N days of recent data.

    Args:
        keep_days: Number of days of artifacts to keep (default: 14)

    Returns:
        Dict with task_id, directories_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("cleanup_solution_state_started", task_id=task_id, keep_days=keep_days)

    try:
        directories_deleted = 0
        bytes_freed = 0

        # Solution state directory
        solution_dir = Path(__file__).parent.parent.parent.parent / "solution_state"

        if not solution_dir.exists():
            logger.warning("solution_state_directory_not_found", directory=str(solution_dir))
            return {
                "task_id": task_id,
                "directories_deleted": 0,
                "bytes_freed": 0,
                "message": "Solution state directory not found",
                "success": True,
                "duration_seconds": 0.0,
            }

        # Calculate cutoff date
        cutoff_time = dt.datetime.now(dt.UTC) - dt.timedelta(days=keep_days)
        cutoff_timestamp = cutoff_time.timestamp()

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
                    # Calculate directory size before deletion
                    dir_size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())

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

        # Store metric in maintenance_stats
        if bytes_freed > 0:
            storage = get_connection_manager()
            with storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO maintenance_stats (metric_name, metric_value, metric_unit)
                    VALUES (%s, %s, %s)
                    """,
                    ["solution_state_cleanup_bytes_freed", bytes_freed, "bytes"],
                )
                conn.commit()

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result = {
            "task_id": task_id,
            "directories_deleted": directories_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": round(bytes_freed / (1024 * 1024), 2),
            "keep_days": keep_days,
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("cleanup_solution_state_completed", **result)
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
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }
