"""Helper utilities for log file rotation and cleanup tasks.

Shared helper functions used by log_cleanup.py for:
- Log file rotation (when files exceed size threshold)
- Old log file deletion (based on retention period)
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from app.logging_config import get_logger
from app.tasks.cleanup.shared_helpers import (
    build_cleanup_result,
    bytes_to_mb,
    calculate_cutoff_timestamp,
    record_cleanup_metric,
)
from app.tasks.cleanup.temp_cleanup_helpers import cleanup_files

logger = get_logger(__name__)

# Constants
LOG_ROTATION_SIZE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10MB
SECONDS_PER_DAY = 86400


def get_log_directories() -> list[Path]:
    """Get list of log directories to check for cleanup operations."""
    backend_logs = Path(__file__).parent.parent.parent.parent / "logs"
    return [
        backend_logs,  # Primary: ~/portfolio-ai/backend/logs/
        Path("/tmp/portfolio-ai-logs"),  # Secondary: temp logs (restricted subdirectory)
        Path("/var/log/portfolio-ai"),  # Legacy: system logs (if exists)
    ]


def _rotate_single_log(log_file: Path, dry_run: bool) -> tuple[bool, dict[str, Any]]:
    """Rotate a single log file if it exceeds the size threshold.

    Returns:
        Tuple of (was_rotated, metadata_dict)
    """
    file_size = log_file.stat().st_size
    if file_size <= LOG_ROTATION_SIZE_THRESHOLD_BYTES:
        return False, {}

    if dry_run:
        return True, {"size_bytes": file_size, "size_mb": bytes_to_mb(file_size)}

    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    rotated_name = log_file.with_suffix(f".log.{timestamp}")
    log_file.rename(rotated_name)
    logger.info("log_file_rotated", file=str(log_file), new_name=str(rotated_name))
    return True, {}


def _rotate_log_file(
    log_file: Path,
    dry_run: bool,
    files_rotated: int,
    would_rotate: list[dict[str, Any]],
) -> int:
    """Attempt to rotate a single log file; return updated files_rotated count."""
    try:
        rotated, metadata = _rotate_single_log(log_file, dry_run)
    except Exception as file_error:
        logger.error(
            "log_rotation_failed",
            file=str(log_file),
            error=str(file_error),
            exc_info=True,
        )
        return files_rotated

    if not rotated:
        return files_rotated

    files_rotated += 1
    if dry_run:
        would_rotate.append({"file": str(log_file), **metadata})
    return files_rotated


def run_log_rotation(task_id: str, dry_run: bool) -> dict[str, Any]:
    """Execute log rotation core logic.

    Args:
        task_id: Unique task identifier
        dry_run: If True, only report what would be rotated

    Returns:
        Partial result dict (without duration_seconds)
    """
    files_rotated = 0
    would_rotate: list[dict[str, Any]] = []

    for log_dir in get_log_directories():
        if not log_dir.exists():
            logger.warning("log_directory_not_found", directory=str(log_dir))
            continue

        for log_file in log_dir.glob("*.log"):
            files_rotated = _rotate_log_file(log_file, dry_run, files_rotated, would_rotate)

    return build_cleanup_result(
        task_id=task_id,
        dry_run=dry_run,
        duration_seconds=0.0,
        task_specific_fields={"files_rotated": files_rotated},
        would_action_list=would_rotate if dry_run else None,
    )


def run_old_logs_cleanup(task_id: str, dry_run: bool, days: int) -> dict[str, Any]:
    """Execute old log file cleanup core logic.

    Args:
        task_id: Unique task identifier
        dry_run: If True, only report what would be deleted
        days: Delete logs older than this many days. Must be >= 1.

    Raises:
        ValueError: If days is <= 0.

    Returns:
        Partial result dict (without duration_seconds)
    """
    if days <= 0:
        raise ValueError(f"retention_days must be >= 1, got {days}")

    cutoff_time, cutoff_timestamp = calculate_cutoff_timestamp(days=days)

    all_log_files: list[Path] = []
    for log_dir in get_log_directories():
        if not log_dir.exists():
            logger.warning("log_directory_not_found", directory=str(log_dir))
            continue
        all_log_files.extend(log_dir.glob("*.log.*"))

    def log_file_filter(file_path: Path, stat: Any) -> tuple[bool, dict[str, Any]]:
        mtime = stat.st_mtime
        if mtime < cutoff_timestamp:
            age_days = (cutoff_time.timestamp() - mtime) / SECONDS_PER_DAY + days
            return True, {"age_days": round(age_days, 1)}
        return False, {}

    files_deleted, bytes_freed, would_delete = cleanup_files(
        all_log_files, log_file_filter, dry_run, "log_file"
    )
    record_cleanup_metric("log_cleanup_bytes_freed", bytes_freed, dry_run)

    return build_cleanup_result(
        task_id=task_id,
        dry_run=dry_run,
        duration_seconds=0.0,
        task_specific_fields={
            "files_deleted": files_deleted,
            "bytes_freed": bytes_freed,
            "bytes_freed_mb": bytes_to_mb(bytes_freed),
            "retention_days": days,
        },
        would_action_list=would_delete if dry_run else None,
    )
