"""Celery tasks for artifact cleanup operations.

This module provides automated cleanup tasks for:
- Old backup files (SQL dumps)
- Old ML model versions
- Old solution state test artifacts

All tasks are designed to be:
- Idempotent (safe to run multiple times)
- Non-destructive (respect retention periods)
- Scheduled (run on Celery Beat schedule)
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.logging_config import get_logger
from app.tasks.maintenance_logging import (
import uuid
    log_maintenance_complete,
    log_maintenance_start,
    record_maintenance_metric,
)
from app.utils.task_helpers import build_error_result, calculate_duration

logger = get_logger(__name__)

# Constants
SECONDS_PER_DAY = 86400


# Helper functions


def _bytes_to_mb(bytes_value: int) -> float:
    """Convert bytes to megabytes, rounded to 2 decimal places."""
    return round(bytes_value / (1024 * 1024), 2)


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


def _record_cleanup_metric(metric_name: str, bytes_freed: int, dry_run: bool) -> None:
    """Record cleanup metric in maintenance_stats if bytes were freed and not a dry run.

    Args:
        metric_name: Name of the metric to record
        bytes_freed: Number of bytes freed by the cleanup operation
        dry_run: Whether this was a dry run
    """
    if bytes_freed > 0 and not dry_run:
        record_maintenance_metric(metric_name, bytes_freed, "bytes")


def _handle_missing_directory(
    task_id: str,
    dry_run: bool,
    directory_path: Path,
    task_name: str,
    log_id: int,
    counter_field_name: str = "files_deleted",
) -> dict[str, Any] | None:
    """Handle missing directory for cleanup tasks.

    Args:
        task_id: The Celery task ID
        dry_run: Whether this was a dry run
        directory_path: Path to the directory to check
        task_name: Name of the task (for logging)
        log_id: Maintenance log ID
        counter_field_name: Name of the counter field (default 'files_deleted')

    Returns:
        Early result dict if directory doesn't exist, None otherwise
    """
    if not directory_path.exists():
        logger.warning(f"{task_name}_directory_not_found", directory=str(directory_path))
        early_result = {
            "task_id": task_id,
            "dry_run": dry_run,
            counter_field_name: 0,
            "bytes_freed": 0,
            "message": f"{task_name.replace('_', ' ').title()} directory not found",
            "success": True,
            "duration_seconds": 0.0,
        }
        log_maintenance_complete(log_id, task_name, True, early_result)
        return early_result
    return None


def _group_model_files_by_name(
    models_dir: Path,
) -> dict[str, list[tuple[Path, str, int]]]:
    """Group model files by base name, extracting version dates.

    Expects files matching pattern: {model_name}_v{date}.joblib (e.g., article_quality_v20250101.joblib)

    Args:
        models_dir: Path to the models directory

    Returns:
        Dict mapping model_name -> list of (Path, date_str, file_size) tuples
    """
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

    return model_groups


def _get_old_model_versions(
    model_groups: dict[str, list[tuple[Path, str, int]]],
    keep_count: int,
) -> list[tuple[Path, str, str, int]]:
    """Extract old model versions to delete from grouped models.

    Sorts each group by date (newest first) and returns all versions beyond keep_count.

    Args:
        model_groups: Dict mapping model_name -> list of (Path, date_str, file_size) tuples
        keep_count: Number of recent versions to keep per model type

    Returns:
        List of (file_path, model_name, date_str, file_size) tuples for deletion
    """
    old_versions: list[tuple[Path, str, str, int]] = []

    for model_name, versions in model_groups.items():
        # Sort by date (newest first)
        versions.sort(key=lambda x: x[1], reverse=True)

        # Collect versions beyond keep_count
        for file_path, date_str, file_size in versions[keep_count:]:
            old_versions.append((file_path, model_name, date_str, file_size))

    return old_versions


def cleanup_old_backups_task(
    self: Task[..., Any], keep_count: int = 5, dry_run: bool = False
) -> dict[str, Any]:
    """Delete old backup files, keeping N most recent.

    Args:
        keep_count: Number of recent backups to keep (default: 5)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())
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
        backup_dir = Path(__file__).parent.parent.parent.parent.parent / "backups"

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
        _record_cleanup_metric("backup_cleanup_bytes_freed", bytes_freed, dry_run)

        duration = calculate_duration(start_time)

        result = _build_cleanup_result(
            task_id=task_id,
            dry_run=dry_run,
            duration_seconds=duration,
            task_specific_fields={
                "files_deleted": files_deleted,
                "bytes_freed": bytes_freed,
                "bytes_freed_mb": _bytes_to_mb(bytes_freed),
                "keep_count": keep_count,
                "total_backups": len(backup_files),
            },
            would_action_list=would_delete if dry_run else None,
        )

        logger.info(
            "cleanup_old_backups_completed",
            **{k: v for k, v in result.items() if k != "would_action_list"},
        )
        log_maintenance_complete(log_id, "cleanup_old_backups_task", True, result)
        return result

    except Exception as e:
        duration = calculate_duration(start_time)
        logger.error(
            "cleanup_old_backups_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(log_id, "cleanup_old_backups_task", False, error_result, str(e))
        return error_result


def cleanup_old_models_task(
    self: Task[..., Any], keep_count: int = 3, dry_run: bool = False
) -> dict[str, Any]:
    """Delete old ML model versions, keeping N most recent per model type.

    Args:
        keep_count: Number of recent versions to keep per model type (default: 3)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())
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
        models_dir = Path(__file__).parent.parent.parent.parent / "models"

        early_result = _handle_missing_directory(
            task_id, dry_run, models_dir, "cleanup_old_models_task", log_id
        )
        if early_result:
            return early_result

        # Group model files by base name and extract old versions
        model_groups = _group_model_files_by_name(models_dir)
        old_versions = _get_old_model_versions(model_groups, keep_count)

        # Delete old versions
        for file_path, model_name, date_str, file_size in old_versions:
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
        _record_cleanup_metric("model_cleanup_bytes_freed", bytes_freed, dry_run)

        duration = calculate_duration(start_time)

        result = _build_cleanup_result(
            task_id=task_id,
            dry_run=dry_run,
            duration_seconds=duration,
            task_specific_fields={
                "files_deleted": files_deleted,
                "bytes_freed": bytes_freed,
                "bytes_freed_mb": _bytes_to_mb(bytes_freed),
                "keep_count": keep_count,
                "model_groups": len(model_groups),
            },
            would_action_list=would_delete if dry_run else None,
        )

        logger.info(
            "cleanup_old_models_completed",
            **{k: v for k, v in result.items() if k != "would_action_list"},
        )
        log_maintenance_complete(log_id, "cleanup_old_models_task", True, result)
        return result

    except Exception as e:
        duration = calculate_duration(start_time)
        logger.error(
            "cleanup_old_models_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(log_id, "cleanup_old_models_task", False, error_result, str(e))
        return error_result


def cleanup_solution_state_task(
    self: Task[..., Any], keep_days: int = 14, dry_run: bool = False
) -> dict[str, Any]:
    """Delete old solution_state test artifacts, keeping N days of recent data.

    Args:
        keep_days: Number of days of artifacts to keep (default: 14)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, directories_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())
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
        solution_dir = Path(__file__).parent.parent.parent.parent.parent / "solution_state"

        early_result = _handle_missing_directory(
            task_id,
            dry_run,
            solution_dir,
            "cleanup_solution_state_task",
            log_id,
            counter_field_name="directories_deleted",
        )
        if early_result:
            return early_result

        # Calculate cutoff date
        _cutoff_time, cutoff_timestamp = _calculate_cutoff_timestamp(days=keep_days)
        now = dt.datetime.now(dt.UTC).timestamp()

        # Find directories that look like timestamps (YYYYMMDD-HHMMSS format)
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
        _record_cleanup_metric("solution_state_cleanup_bytes_freed", bytes_freed, dry_run)

        duration = calculate_duration(start_time)

        result = _build_cleanup_result(
            task_id=task_id,
            dry_run=dry_run,
            duration_seconds=duration,
            task_specific_fields={
                "directories_deleted": directories_deleted,
                "bytes_freed": bytes_freed,
                "bytes_freed_mb": _bytes_to_mb(bytes_freed),
                "keep_days": keep_days,
            },
            would_action_list=would_delete if dry_run else None,
        )

        logger.info(
            "cleanup_solution_state_completed",
            **{k: v for k, v in result.items() if k != "would_action_list"},
        )
        log_maintenance_complete(log_id, "cleanup_solution_state_task", True, result)
        return result

    except Exception as e:
        duration = calculate_duration(start_time)
        logger.error(
            "cleanup_solution_state_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(log_id, "cleanup_solution_state_task", False, error_result, str(e))
        return error_result
