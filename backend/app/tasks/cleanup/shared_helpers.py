"""Shared helper utilities for cleanup tasks.

Common functions used by both artifact_cleanup_helpers.py and
temp_cleanup_helpers.py to avoid duplication.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from app.logging_config import get_logger
from app.tasks.maintenance_logging import record_maintenance_metric

logger = get_logger(__name__)

# Type aliases
_DryRunEntry = dict[str, int | float | str]
_CleanupVal = int | float | str | bool | list[_DryRunEntry]
CleanupResult = dict[str, _CleanupVal]


def bytes_to_mb(bytes_value: int) -> float:
    """Convert bytes to megabytes, rounded to 2 decimal places."""
    return round(bytes_value / (1024 * 1024), 2)


def build_cleanup_result(
    task_id: str,
    dry_run: bool,
    duration_seconds: float,
    task_specific_fields: dict[str, Any],
    would_action_list: list[dict[str, Any]] | None = None,
) -> CleanupResult:
    """Build standardized success result dict for cleanup tasks."""
    result: CleanupResult = {
        "task_id": task_id,
        "dry_run": dry_run,
        "duration_seconds": round(duration_seconds, 2),
        "success": True,
        **task_specific_fields,
    }
    if would_action_list:
        result["would_action_list"] = would_action_list
    return result


def calculate_cutoff_timestamp(
    days: int | None = None, hours: int | None = None
) -> tuple[dt.datetime, float]:
    """Calculate cutoff datetime and timestamp for cleanup operations."""
    if hours is not None:
        cutoff_time = dt.datetime.now(dt.UTC) - dt.timedelta(hours=hours)
    elif days is not None:
        cutoff_time = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    else:
        cutoff_time = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)
    return cutoff_time, cutoff_time.timestamp()


def calculate_directory_size(directory: Path) -> tuple[int, int]:
    """Return (total_bytes, file_count) for a directory."""
    files = [f for f in directory.rglob("*") if f.is_file()]
    return sum(f.stat().st_size for f in files), len(files)


def record_cleanup_metric(metric_name: str, bytes_freed: int, dry_run: bool) -> None:
    """Record cleanup metric if bytes were freed and not a dry run."""
    if bytes_freed > 0 and not dry_run:
        record_maintenance_metric(metric_name, bytes_freed, "bytes")
