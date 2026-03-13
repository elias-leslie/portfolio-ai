"""Helper utilities for temporary file and cache cleanup tasks.

Shared helper functions used by temp_cleanup.py for:
- Temporary file cleanup
- Development cache directory cleanup
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.logging_config import get_logger

from .shared_helpers import (
    build_cleanup_result,
    bytes_to_mb,
    calculate_cutoff_timestamp,
    calculate_directory_size,
    record_cleanup_metric,
)

logger = get_logger(__name__)

# Constants
SECONDS_PER_HOUR = 3600

# Temp file patterns to clean up
TEMP_FILE_PATTERNS = [
    "portfolio-ai-*",
    "tmpfile*",
    "*.tmp",
]


def cleanup_files(
    file_iterator: list[Path],
    filter_func: Any,
    dry_run: bool,
    logger_event: str,
) -> tuple[int, int, list[dict[str, Any]]]:
    """Iterate files, apply filter, and delete or track for dry run.

    Args:
        file_iterator: List of file paths to potentially delete
        filter_func: Callable(file_path, stat) -> (should_delete: bool, metadata: dict)
        dry_run: If True, only track would_delete instead of deleting
        logger_event: Event name prefix for logging

    Returns:
        Tuple of (files_deleted, bytes_freed, would_delete)
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
                would_delete.append({"file": str(file_path), "size_bytes": file_size, **metadata})
                files_deleted += 1
                bytes_freed += file_size
            else:
                file_path.unlink()
                files_deleted += 1
                bytes_freed += file_size
                logger.info("file_deleted", cleanup_type=logger_event, file=str(file_path), size_bytes=file_size)
        except Exception as file_error:
            logger.error(
                "file_deletion_failed",
                cleanup_type=logger_event,
                file=str(file_path),
                error=str(file_error),
                exc_info=True,
            )

    return files_deleted, bytes_freed, would_delete


def get_cache_targets(project_root: Path) -> list[dict[str, Any]]:
    """Return list of cache target configurations for cleanup."""
    return [
        {"name": "Python bytecode cache", "path": project_root / "backend", "pattern": "__pycache__", "recursive": True},
        {"name": "Services Python cache", "path": project_root / "services", "pattern": "__pycache__", "recursive": True},
        {"name": "Ruff cache", "path": project_root / "backend" / ".ruff_cache", "pattern": None, "recursive": False},
        {"name": "Pytest cache", "path": project_root / "backend" / ".pytest_cache", "pattern": None, "recursive": False},
        {"name": "Mypy cache", "path": project_root / "backend" / ".mypy_cache", "pattern": None, "recursive": False},
        {"name": "Root Mypy cache", "path": project_root / ".mypy_cache", "pattern": None, "recursive": False},
        {"name": "Next.js cache", "path": project_root / "frontend" / ".next" / "cache", "pattern": None, "recursive": False},
        {"name": "Claude memory backups", "path": project_root / ".claude" / "backups" / "memory", "pattern": None, "recursive": False},
    ]


def run_temp_cleanup(
    task_id: str, dry_run: bool, hours: int
) -> dict[str, Any]:
    """Execute temporary file cleanup core logic.

    Args:
        task_id: Unique task identifier
        dry_run: If True, only report what would be deleted
        hours: Delete files older than this many hours

    Returns:
        Partial result dict (without duration_seconds)
    """
    cutoff_time, cutoff_timestamp = calculate_cutoff_timestamp(hours=hours)
    temp_dir = Path("/tmp")

    all_temp_files: list[Path] = []
    for pattern in TEMP_FILE_PATTERNS:
        for temp_file in temp_dir.glob(pattern):
            if not temp_file.is_dir():
                all_temp_files.append(temp_file)

    def temp_file_filter(file_path: Path, stat: Any) -> tuple[bool, dict[str, Any]]:
        mtime = stat.st_mtime
        if mtime < cutoff_timestamp:
            age_hours = (cutoff_time.timestamp() - mtime) / SECONDS_PER_HOUR + hours
            return True, {"age_hours": round(age_hours, 1)}
        return False, {}

    files_deleted, bytes_freed, would_delete = cleanup_files(
        all_temp_files, temp_file_filter, dry_run, "temp_file"
    )
    record_cleanup_metric("temp_cleanup_bytes_freed", bytes_freed, dry_run)

    return build_cleanup_result(
        task_id=task_id,
        dry_run=dry_run,
        duration_seconds=0.0,
        task_specific_fields={
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": bytes_to_mb(bytes_freed),
            "retention_hours": hours,
        },
        would_action_list=would_delete if dry_run else None,
    )


def _process_cache_target(
    target: dict[str, Any],
    dry_run: bool,
) -> tuple[int, int, int, list[dict[str, Any]]]:
    """Process a single cache target for cleanup.

    Returns:
        Tuple of (directories_cleaned, files_deleted, bytes_freed, details)
    """
    target_name = str(target["name"])
    target_path: Path = target["path"]
    pattern: str | None = target["pattern"]
    recursive: bool = target["recursive"]

    directories_cleaned = 0
    files_deleted = 0
    bytes_freed = 0
    details: list[dict[str, Any]] = []

    if not target_path.exists():
        logger.debug("cache_target_not_found", target=target_name, path=str(target_path))
        return directories_cleaned, files_deleted, bytes_freed, details

    try:
        if recursive and pattern:
            dirs_to_clean = list(target_path.rglob(pattern))
        else:
            dirs_to_clean = [target_path] if target_path.is_dir() else []

        for cache_dir in dirs_to_clean:
            if not cache_dir.is_dir():
                continue
            dir_size, file_count = calculate_directory_size(cache_dir)
            action = "would_delete" if dry_run else "deleted"
            if not dry_run:
                shutil.rmtree(cache_dir)
                logger.info(
                    "cache_directory_cleaned",
                    name=target_name,
                    path=str(cache_dir),
                    size_bytes=dir_size,
                    file_count=file_count,
                )
            details.append(
                {"name": target_name, "path": str(cache_dir), "size_bytes": dir_size, "file_count": file_count, "action": action}
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
            exc_info=True,
        )
        details.append(
            {"name": target_name, "path": str(target_path), "action": "error", "error": str(target_error)}
        )

    return directories_cleaned, files_deleted, bytes_freed, details


def run_cache_cleanup(task_id: str, dry_run: bool) -> dict[str, Any]:
    """Execute cache directory cleanup core logic.

    Args:
        task_id: Unique task identifier
        dry_run: If True, only report what would be deleted

    Returns:
        Partial result dict (without duration_seconds)
    """
    project_root = Path(__file__).parent.parent.parent.parent.parent
    cache_targets = get_cache_targets(project_root)

    directories_cleaned = 0
    files_deleted = 0
    bytes_freed = 0
    all_details: list[dict[str, Any]] = []

    for target in cache_targets:
        d, f, b, details = _process_cache_target(target, dry_run)
        directories_cleaned += d
        files_deleted += f
        bytes_freed += b
        all_details.extend(details)

    record_cleanup_metric("cache_cleanup_bytes_freed", bytes_freed, dry_run)

    return build_cleanup_result(
        task_id=task_id,
        dry_run=dry_run,
        duration_seconds=0.0,
        task_specific_fields={
            "directories_cleaned": directories_cleaned,
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": bytes_to_mb(bytes_freed),
            "details": all_details,
        },
    )
