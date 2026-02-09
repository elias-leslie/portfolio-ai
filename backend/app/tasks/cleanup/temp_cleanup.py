"""Temporary file and cache cleanup tasks.

This module provides automated cleanup tasks for:
- Temporary files in /tmp
- Development cache directories (optional manual task)

All tasks are designed to be:
- Idempotent (safe to run multiple times)
- Non-destructive (respect retention periods)
- Scheduled or manually triggered
"""

from __future__ import annotations

import datetime as dt
import shutil
import uuid
from pathlib import Path
from typing import Any

from app.logging_config import get_logger
from app.tasks.maintenance_logging import (
    log_maintenance_complete,
    log_maintenance_start,
    record_maintenance_metric,
)
from app.utils.task_helpers import build_error_result, calculate_duration

logger = get_logger(__name__)

# Constants
SECONDS_PER_HOUR = 3600


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


def cleanup_temp_files_task(
    hours: int = 24, dry_run: bool = False
) -> dict[str, Any]:
    """Delete temporary files older than specified hours.

    Args:
        hours: Delete temp files older than N hours (default: 24)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_temp_files_task", dry_run)

    logger.info("cleanup_temp_files_started", task_id=task_id, hours=hours, dry_run=dry_run)

    try:
        cutoff_time, cutoff_timestamp = _calculate_cutoff_timestamp(hours=hours)

        temp_dir = Path("/tmp")

        # Patterns for temp files to clean up
        temp_patterns = [
            "portfolio-ai-*",
            "celery-*",
            "tmpfile*",
            "*.tmp",
        ]

        # Collect all temp files matching patterns
        all_temp_files: list[Path] = []
        for pattern in temp_patterns:
            for temp_file in temp_dir.glob(pattern):
                # Skip directories
                if not temp_file.is_dir():
                    all_temp_files.append(temp_file)

        # Define filter function for temp files
        def temp_file_filter(file_path: Path, stat: Any) -> tuple[bool, dict[str, Any]]:
            mtime = stat.st_mtime
            if mtime < cutoff_timestamp:
                age_hours = (cutoff_time.timestamp() - mtime) / SECONDS_PER_HOUR + hours
                return True, {"age_hours": round(age_hours, 1)}
            return False, {}

        # Use helper to perform cleanup
        files_deleted, bytes_freed, would_delete = _cleanup_files(
            all_temp_files, temp_file_filter, dry_run, "temp_file"
        )

        # Store metric in maintenance_stats (only if not dry run)
        _record_cleanup_metric("temp_cleanup_bytes_freed", bytes_freed, dry_run)

        duration = calculate_duration(start_time)

        result = _build_cleanup_result(
            task_id=task_id,
            dry_run=dry_run,
            duration_seconds=duration,
            task_specific_fields={
                "files_deleted": files_deleted,
                "bytes_freed": bytes_freed,
                "bytes_freed_mb": _bytes_to_mb(bytes_freed),
                "retention_hours": hours,
            },
            would_action_list=would_delete if dry_run else None,
        )

        logger.info(
            "cleanup_temp_files_completed",
            **{k: v for k, v in result.items() if k != "would_action_list"},
        )
        log_maintenance_complete(log_id, "cleanup_temp_files_task", True, result)
        return result

    except Exception as e:
        duration = calculate_duration(start_time)
        logger.error(
            "cleanup_temp_files_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(log_id, "cleanup_temp_files_task", False, error_result, str(e))
        return error_result


def cleanup_cache_directories_task(dry_run: bool = False) -> dict[str, Any]:
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
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_cache_directories_task", dry_run)

    logger.info("cleanup_cache_directories_started", task_id=task_id, dry_run=dry_run)

    try:
        directories_cleaned = 0
        files_deleted = 0
        bytes_freed = 0
        details: list[dict[str, Any]] = []

        # Project root
        project_root = Path(__file__).parent.parent.parent.parent.parent

        # Get cache targets with their cleanup strategy
        cache_targets = _get_cache_targets(project_root)

        for target in cache_targets:
            target_name = str(target["name"])
            target_path: Path = target["path"]
            pattern: str | None = target["pattern"]
            recursive: bool = target["recursive"]

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
        _record_cleanup_metric("cache_cleanup_bytes_freed", bytes_freed, dry_run)

        duration = calculate_duration(start_time)

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
        duration = calculate_duration(start_time)
        logger.error(
            "cleanup_cache_directories_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        error_result = build_error_result(task_id, e, duration, dry_run=dry_run)
        log_maintenance_complete(
            log_id, "cleanup_cache_directories_task", False, error_result, str(e)
        )
        return error_result
