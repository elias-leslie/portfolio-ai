"""Helper utilities for artifact cleanup tasks.

Shared helper functions used by artifact_cleanup.py for:
- Backup file cleanup
- ML model version cleanup
- Solution state artifact cleanup
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path

from app.logging_config import get_logger
from app.tasks.maintenance_logging import (
    log_maintenance_complete,
    record_maintenance_metric,
)

logger = get_logger(__name__)

# Constants
SECONDS_PER_DAY = 86400


def bytes_to_mb(bytes_value: int) -> float:
    """Convert bytes to megabytes, rounded to 2 decimal places."""
    return round(bytes_value / (1024 * 1024), 2)


def build_cleanup_result(
    task_id: str,
    dry_run: bool,
    duration_seconds: float,
    task_specific_fields: dict[str, int | float | str | bool | list[dict[str, int | float | str]]],
    would_action_list: list[dict[str, int | float | str]] | None = None,
) -> dict[str, int | float | str | bool | list[dict[str, int | float | str]]]:
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
    result: dict[str, int | float | str | bool | list[dict[str, int | float | str]]] = {
        "task_id": task_id,
        "dry_run": dry_run,
        "duration_seconds": round(duration_seconds, 2),
        "success": True,
        **task_specific_fields,
    }
    if would_action_list and len(would_action_list) > 0:
        result["would_action_list"] = would_action_list
    return result


def calculate_cutoff_timestamp(
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
        cutoff_time = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)
    return cutoff_time, cutoff_time.timestamp()


def calculate_directory_size(directory: Path) -> tuple[int, int]:
    """Calculate total size and file count of a directory.

    Args:
        directory: Path to the directory to measure

    Returns:
        Tuple of (total_bytes, file_count)
    """
    total_bytes = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
    file_count = sum(1 for f in directory.rglob("*") if f.is_file())
    return total_bytes, file_count


def record_cleanup_metric(metric_name: str, bytes_freed: int, dry_run: bool) -> None:
    """Record cleanup metric in maintenance_stats if bytes were freed and not a dry run.

    Args:
        metric_name: Name of the metric to record
        bytes_freed: Number of bytes freed by the cleanup operation
        dry_run: Whether this was a dry run
    """
    if bytes_freed > 0 and not dry_run:
        record_maintenance_metric(metric_name, bytes_freed, "bytes")


def handle_missing_directory(
    task_id: str,
    dry_run: bool,
    directory_path: Path,
    task_name: str,
    log_id: int,
    counter_field_name: str = "files_deleted",
) -> dict[str, int | float | str | bool | list[dict[str, int | float | str]]] | None:
    """Handle missing directory for cleanup tasks.

    Args:
        task_id: The task ID
        dry_run: Whether this was a dry run
        directory_path: Path to the directory to check
        task_name: Name of the task (for logging)
        log_id: Maintenance log ID
        counter_field_name: Name of the counter field (default 'files_deleted')

    Returns:
        Early result dict if directory doesn't exist, None otherwise
    """
    if directory_path.exists():
        return None
    logger.warning(f"{task_name}_directory_not_found", directory=str(directory_path))
    early_result: dict[str, int | float | str | bool | list[dict[str, int | float | str]]] = {
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


def group_model_files_by_name(
    models_dir: Path,
) -> dict[str, list[tuple[Path, str, int]]]:
    """Group model files by base name, extracting version dates.

    Expects files matching pattern: {model_name}_v{date}.joblib

    Args:
        models_dir: Path to the models directory

    Returns:
        Dict mapping model_name -> list of (Path, date_str, file_size) tuples
    """
    model_groups: dict[str, list[tuple[Path, str, int]]] = {}
    model_pattern = re.compile(r"^(.+)_v(\d{8})\.joblib$")

    for f in models_dir.glob("*.joblib"):
        if f.is_symlink():
            continue
        match = model_pattern.match(f.name)
        if not match:
            continue
        model_name = match.group(1)
        date_str = match.group(2)
        file_size = f.stat().st_size
        if model_name not in model_groups:
            model_groups[model_name] = []
        model_groups[model_name].append((f, date_str, file_size))

    return model_groups


def get_old_model_versions(
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
        versions.sort(key=lambda x: x[1], reverse=True)
        for file_path, date_str, file_size in versions[keep_count:]:
            old_versions.append((file_path, model_name, date_str, file_size))

    return old_versions


def process_backup_file(
    file_path: Path,
    mtime: float,
    file_size: int,
    dry_run: bool,
    now: float,
    would_delete: list[dict[str, int | float | str]],
) -> tuple[int, int]:
    """Process a single backup file for deletion.

    Args:
        file_path: Path to the backup file
        mtime: File modification time as a timestamp
        file_size: File size in bytes
        dry_run: Whether this is a dry run
        now: Current timestamp
        would_delete: List to append dry-run entries to

    Returns:
        Tuple of (files_deleted_delta, bytes_freed_delta)
    """
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
        else:
            file_path.unlink()
            logger.info(
                "backup_file_deleted",
                file=str(file_path),
                size_bytes=file_size,
            )
        return 1, file_size
    except Exception as file_error:
        logger.error(
            "backup_deletion_failed",
            file=str(file_path),
            error=str(file_error),
        )
        return 0, 0


def process_model_file(
    file_path: Path,
    model_name: str,
    date_str: str,
    file_size: int,
    dry_run: bool,
    would_delete: list[dict[str, int | float | str]],
) -> tuple[int, int]:
    """Process a single model file for deletion.

    Args:
        file_path: Path to the model file
        model_name: Base model name
        date_str: Model version date string
        file_size: File size in bytes
        dry_run: Whether this is a dry run
        would_delete: List to append dry-run entries to

    Returns:
        Tuple of (files_deleted_delta, bytes_freed_delta)
    """
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
        else:
            file_path.unlink()
            logger.info(
                "model_file_deleted",
                file=str(file_path),
                model_name=model_name,
                version_date=date_str,
                size_bytes=file_size,
            )
        return 1, file_size
    except Exception as file_error:
        logger.error(
            "model_deletion_failed",
            file=str(file_path),
            error=str(file_error),
        )
        return 0, 0


def process_solution_state_entry(
    entry: Path,
    cutoff_timestamp: float,
    now: float,
    dry_run: bool,
    would_delete: list[dict[str, int | float | str]],
) -> tuple[int, int]:
    """Process a single solution state directory for deletion.

    Args:
        entry: Path to the directory entry
        cutoff_timestamp: Cutoff time as a timestamp
        now: Current timestamp
        dry_run: Whether this is a dry run
        would_delete: List to append dry-run entries to

    Returns:
        Tuple of (directories_deleted_delta, bytes_freed_delta)
    """
    try:
        mtime = entry.stat().st_mtime
        if mtime >= cutoff_timestamp:
            return 0, 0
        dir_size, _file_count = calculate_directory_size(entry)
        age_days = (now - mtime) / SECONDS_PER_DAY
        if dry_run:
            would_delete.append(
                {
                    "directory": str(entry),
                    "size_bytes": dir_size,
                    "age_days": round(age_days, 1),
                }
            )
        else:
            shutil.rmtree(entry)
            logger.info(
                "solution_state_deleted",
                directory=str(entry),
                size_bytes=dir_size,
            )
        return 1, dir_size
    except Exception as dir_error:
        logger.error(
            "solution_state_deletion_failed",
            directory=str(entry),
            error=str(dir_error),
        )
        return 0, 0


def collect_backup_files(backup_dir: Path) -> list[tuple[Path, float, int]]:
    """Collect and sort backup files by modification time (newest first).

    Args:
        backup_dir: Path to the backups directory

    Returns:
        List of (file_path, mtime, file_size) tuples sorted newest first
    """
    backup_patterns = ["*.sql", "*.sql.gz", "*.sql.bz2"]
    backup_files: list[tuple[Path, float, int]] = []
    for pattern in backup_patterns:
        for f in backup_dir.glob(pattern):
            if f.is_file():
                stat = f.stat()
                backup_files.append((f, stat.st_mtime, stat.st_size))
    backup_files.sort(key=lambda x: x[1], reverse=True)
    return backup_files


def delete_old_backups(
    backup_files: list[tuple[Path, float, int]],
    keep_count: int,
    dry_run: bool,
) -> tuple[int, int, list[dict[str, int | float | str]]]:
    """Delete backup files beyond keep_count.

    Args:
        backup_files: Sorted list of (file_path, mtime, file_size) tuples
        keep_count: Number of files to keep
        dry_run: Whether this is a dry run

    Returns:
        Tuple of (files_deleted, bytes_freed, would_delete)
    """
    files_deleted = 0
    bytes_freed = 0
    would_delete: list[dict[str, int | float | str]] = []
    now = dt.datetime.now(dt.UTC).timestamp()
    for file_path, mtime, file_size in backup_files[keep_count:]:
        deleted, freed = process_backup_file(
            file_path, mtime, file_size, dry_run, now, would_delete
        )
        files_deleted += deleted
        bytes_freed += freed
    return files_deleted, bytes_freed, would_delete


def delete_old_model_versions(
    old_versions: list[tuple[Path, str, str, int]],
    dry_run: bool,
) -> tuple[int, int, list[dict[str, int | float | str]]]:
    """Delete old model version files.

    Args:
        old_versions: List of (file_path, model_name, date_str, file_size) tuples
        dry_run: Whether this is a dry run

    Returns:
        Tuple of (files_deleted, bytes_freed, would_delete)
    """
    files_deleted = 0
    bytes_freed = 0
    would_delete: list[dict[str, int | float | str]] = []
    for file_path, model_name, date_str, file_size in old_versions:
        deleted, freed = process_model_file(
            file_path, model_name, date_str, file_size, dry_run, would_delete
        )
        files_deleted += deleted
        bytes_freed += freed
    return files_deleted, bytes_freed, would_delete


def delete_old_solution_state_dirs(
    solution_dir: Path,
    cutoff_timestamp: float,
    dry_run: bool,
) -> tuple[int, int, list[dict[str, int | float | str]]]:
    """Delete solution state directories older than the cutoff timestamp.

    Args:
        solution_dir: Path to the solution state directory
        cutoff_timestamp: Cutoff time as a timestamp; dirs older than this are deleted
        dry_run: Whether this is a dry run

    Returns:
        Tuple of (directories_deleted, bytes_freed, would_delete)
    """
    directories_deleted = 0
    bytes_freed = 0
    would_delete: list[dict[str, int | float | str]] = []
    now = dt.datetime.now(dt.UTC).timestamp()
    timestamp_pattern = re.compile(r"^\d{8}-\d{6}$")

    for entry in solution_dir.iterdir():
        if not entry.is_dir() or not timestamp_pattern.match(entry.name):
            continue
        deleted, freed = process_solution_state_entry(
            entry, cutoff_timestamp, now, dry_run, would_delete
        )
        directories_deleted += deleted
        bytes_freed += freed
    return directories_deleted, bytes_freed, would_delete


def run_backups_cleanup(
    task_id: str,
    dry_run: bool,
    keep_count: int,
    log_id: int,
) -> dict[str, int | float | str | bool | list[dict[str, int | float | str]]]:
    """Execute backup cleanup core logic (directory scan, delete, build result).

    Args:
        task_id: The task ID
        dry_run: Whether this is a dry run
        keep_count: Number of recent backups to keep
        log_id: Maintenance log ID

    Returns:
        Standardized result dict
    """
    from pathlib import Path as _Path
    backup_dir = _Path(__file__).parent.parent.parent.parent.parent / "backups"
    early_exit = handle_missing_directory(
        task_id, dry_run, backup_dir, "cleanup_old_backups_task", log_id
    )
    if early_exit:
        return early_exit

    backup_files = collect_backup_files(backup_dir)
    files_deleted, bytes_freed, would_delete = delete_old_backups(
        backup_files, keep_count, dry_run
    )
    record_cleanup_metric("backup_cleanup_bytes_freed", bytes_freed, dry_run)
    return build_cleanup_result(
        task_id=task_id,
        dry_run=dry_run,
        duration_seconds=0.0,
        task_specific_fields={
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": bytes_to_mb(bytes_freed),
            "keep_count": keep_count,
            "total_backups": len(backup_files),
        },
        would_action_list=would_delete if dry_run else None,
    )


def run_models_cleanup(
    task_id: str,
    dry_run: bool,
    keep_count: int,
    log_id: int,
) -> dict[str, int | float | str | bool | list[dict[str, int | float | str]]]:
    """Execute model cleanup core logic (directory scan, delete, build result).

    Args:
        task_id: The task ID
        dry_run: Whether this is a dry run
        keep_count: Number of recent model versions to keep per model type
        log_id: Maintenance log ID

    Returns:
        Standardized result dict
    """
    from pathlib import Path as _Path
    models_dir = _Path(__file__).parent.parent.parent.parent / "models"
    early_result = handle_missing_directory(
        task_id, dry_run, models_dir, "cleanup_old_models_task", log_id
    )
    if early_result:
        return early_result

    model_groups = group_model_files_by_name(models_dir)
    old_versions = get_old_model_versions(model_groups, keep_count)
    files_deleted, bytes_freed, would_delete = delete_old_model_versions(old_versions, dry_run)
    record_cleanup_metric("model_cleanup_bytes_freed", bytes_freed, dry_run)
    return build_cleanup_result(
        task_id=task_id,
        dry_run=dry_run,
        duration_seconds=0.0,
        task_specific_fields={
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": bytes_to_mb(bytes_freed),
            "keep_count": keep_count,
            "model_groups": len(model_groups),
        },
        would_action_list=would_delete if dry_run else None,
    )


def run_solution_state_cleanup(
    task_id: str,
    dry_run: bool,
    keep_days: int,
    log_id: int,
) -> dict[str, int | float | str | bool | list[dict[str, int | float | str]]]:
    """Execute solution state cleanup core logic (directory scan, delete, build result).

    Args:
        task_id: The task ID
        dry_run: Whether this is a dry run
        keep_days: Number of days of artifacts to keep
        log_id: Maintenance log ID

    Returns:
        Standardized result dict
    """
    from pathlib import Path as _Path
    solution_dir = _Path(__file__).parent.parent.parent.parent.parent / "solution_state"
    early_result = handle_missing_directory(
        task_id,
        dry_run,
        solution_dir,
        "cleanup_solution_state_task",
        log_id,
        counter_field_name="directories_deleted",
    )
    if early_result:
        return early_result

    _cutoff_time, cutoff_timestamp = calculate_cutoff_timestamp(days=keep_days)
    directories_deleted, bytes_freed, would_delete = delete_old_solution_state_dirs(
        solution_dir, cutoff_timestamp, dry_run
    )
    record_cleanup_metric("solution_state_cleanup_bytes_freed", bytes_freed, dry_run)
    return build_cleanup_result(
        task_id=task_id,
        dry_run=dry_run,
        duration_seconds=0.0,
        task_specific_fields={
            "directories_deleted": directories_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": bytes_to_mb(bytes_freed),
            "keep_days": keep_days,
        },
        would_action_list=would_delete if dry_run else None,
    )
