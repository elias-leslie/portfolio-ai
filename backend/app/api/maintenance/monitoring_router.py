"""Maintenance monitoring and statistics router.

This module provides REST API endpoints for monitoring system resources,
database size, maintenance statistics, and scheduled task information.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, TypedDict, cast

from celery.schedules import (
    crontab as CrontabSchedule,  # noqa: N812 - Using CamelCase for isinstance checks
)
from fastapi import APIRouter, HTTPException

from ...celery_app import celery_app
from ...logging_config import get_logger
from ...services.maintenance_tracker import (
    get_all_metrics_summary,
    get_cleanup_trends,
)
from ...tasks.log_cleanup_tasks import _check_disk_space_impl
from ...tasks.maintenance_tasks import _get_database_size_impl
from ..maintenance_types import (
    DatabaseSizeResponseDict,
    DiskSpaceResponseDict,
    MaintenanceScheduleResponseDict,
)


class FileCleanupInfo(TypedDict):
    """Info about a file cleanup category."""

    path: str
    size_mb: float
    file_count: int
    retention_policy: str
    schedule: str


class FileCleanupStatusResponse(TypedDict):
    """Response for file cleanup status endpoint."""

    logs: FileCleanupInfo
    backups: FileCleanupInfo
    models: FileCleanupInfo
    solution_state: FileCleanupInfo
    total_size_mb: float


class DryRunFileInfo(TypedDict):
    """Info about files that would be deleted in a dry run."""

    file: str
    size_bytes: int
    age_days: float
    reason: str


class DryRunCategoryReport(TypedDict):
    """Dry run report for a single category."""

    category: str
    would_delete_count: int
    would_free_bytes: int
    would_free_mb: float
    files: list[DryRunFileInfo]
    retention_policy: str


class DryRunReportResponse(TypedDict):
    """Full dry run report response."""

    generated_at: str
    categories: dict[str, DryRunCategoryReport]
    total_would_delete: int
    total_would_free_mb: float

logger = get_logger(__name__)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


# API Endpoints


@router.get("/disk-space")
async def get_disk_space() -> DiskSpaceResponseDict:
    """Get current disk space usage for all monitored partitions.

    Returns:
        Dict with partition information and alerts

    Raises:
        HTTPException: If disk space check fails
    """
    try:
        # Call implementation directly (no Celery, immediate response)
        result = _check_disk_space_impl()
        return cast(DiskSpaceResponseDict, result)

    except Exception as e:
        logger.error(
            "get_disk_space_failed",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get disk space: {e!s}",
        ) from e


@router.get("/database-size")
async def get_database_size() -> DatabaseSizeResponseDict:
    """Get current database size and table sizes.

    Returns:
        Dict with database size and top tables

    Raises:
        HTTPException: If database size check fails
    """
    try:
        # Call implementation directly (no Celery, immediate response)
        result = _get_database_size_impl()
        return cast(DatabaseSizeResponseDict, result)

    except Exception as e:
        logger.error(
            "get_database_size_failed",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get database size: {e!s}",
        ) from e


@router.get("/stats")
async def get_maintenance_stats(
    metric_name: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    """Get maintenance statistics and trends.

    Args:
        metric_name: Specific metric to retrieve (None = all metrics summary)
        days: Number of days of history for trends (default: 30)

    Returns:
        Dict with metric values over time or summary of all metrics

    Raises:
        HTTPException: If stats retrieval fails
    """
    try:
        if metric_name:
            # Get trend data for specific metric
            trends = get_cleanup_trends(metric_name, days)
            return {
                "metric_name": metric_name,
                "days": days,
                "data_points": len(trends),
                "trends": trends,
            }
        # Get summary of all metrics
        summary = get_all_metrics_summary()
        return {
            "summary": summary,
            "metric_count": len(summary),
        }

    except Exception as e:
        logger.error(
            "get_maintenance_stats_failed",
            metric_name=metric_name,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get maintenance stats: {e!s}",
        ) from e


@router.get("/schedule")
async def get_maintenance_schedule() -> MaintenanceScheduleResponseDict:
    """Get schedule information for all maintenance tasks.

    Returns:
        Dict with scheduled tasks and their next run times

    Raises:
        HTTPException: If schedule retrieval fails
    """
    try:
        # Get schedule from Celery Beat
        schedule = celery_app.conf.beat_schedule

        # Filter to only maintenance tasks
        maintenance_schedule = {}
        for task_name, config in schedule.items():
            if (
                "cleanup" in task_name
                or "vacuum" in task_name
                or "check-disk" in task_name
                or "database-size" in task_name
            ):
                schedule_info = config["schedule"]

                # Format schedule information
                if isinstance(schedule_info, CrontabSchedule):
                    schedule_str = f"crontab({schedule_info})"
                else:
                    schedule_str = f"every {schedule_info} seconds"

                maintenance_schedule[task_name] = {
                    "task": config["task"],
                    "schedule": schedule_str,
                    "args": config.get("args", []),
                }

        return {
            "scheduled_tasks": maintenance_schedule,
            "total_count": len(maintenance_schedule),
        }

    except Exception as e:
        logger.error(
            "get_maintenance_schedule_failed",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get maintenance schedule: {e!s}",
        ) from e


def _calculate_dir_size(path: Path, pattern: str = "*") -> tuple[float, int]:
    """Calculate directory size and file count.

    Args:
        path: Directory path
        pattern: Glob pattern for files to count

    Returns:
        Tuple of (size_mb, file_count)
    """
    if not path.exists():
        return 0.0, 0

    total_bytes = 0
    file_count = 0

    for f in path.glob(pattern):
        if f.is_file() and not f.is_symlink():
            total_bytes += f.stat().st_size
            file_count += 1

    return round(total_bytes / (1024 * 1024), 2), file_count


@router.get("/file-cleanup-status")
async def get_file_cleanup_status() -> FileCleanupStatusResponse:
    """Get sizes and retention info for file cleanup directories.

    Returns:
        Dict with file cleanup status for logs, backups, models, solution_state

    Raises:
        HTTPException: If status retrieval fails
    """
    try:
        # Base paths
        project_root = Path(__file__).parent.parent.parent.parent.parent
        backend_root = Path(__file__).parent.parent.parent.parent

        # Logs directory
        logs_path = backend_root / "logs"
        logs_size, logs_count = _calculate_dir_size(logs_path, "*.log*")

        # Backups directory
        backups_path = project_root / "backups"
        backups_sql_size, backups_sql_count = _calculate_dir_size(backups_path, "*.sql")
        backups_gz_size, backups_gz_count = _calculate_dir_size(backups_path, "*.sql.gz")
        backups_size = round(backups_sql_size + backups_gz_size, 2)
        backups_count = backups_sql_count + backups_gz_count

        # Models directory
        models_path = backend_root / "models"
        models_size, models_count = _calculate_dir_size(models_path, "*.joblib")

        # Solution state directory
        solution_path = project_root / "solution_state"
        solution_size = 0.0
        solution_count = 0
        if solution_path.exists():
            timestamp_pattern = re.compile(r"^\d{8}-\d{6}$")
            for entry in solution_path.iterdir():
                if entry.is_dir() and timestamp_pattern.match(entry.name):
                    for f in entry.rglob("*"):
                        if f.is_file():
                            solution_size += f.stat().st_size / (1024 * 1024)
                            solution_count += 1
            solution_size = round(solution_size, 2)

        total_size = round(logs_size + backups_size + models_size + solution_size, 2)

        return {
            "logs": {
                "path": str(logs_path),
                "size_mb": logs_size,
                "file_count": logs_count,
                "retention_policy": "Keep 7 days",
                "schedule": "Daily 02:00 UTC",
            },
            "backups": {
                "path": str(backups_path),
                "size_mb": backups_size,
                "file_count": backups_count,
                "retention_policy": "Keep 5 most recent",
                "schedule": "Weekly Sunday 04:45 UTC",
            },
            "models": {
                "path": str(models_path),
                "size_mb": models_size,
                "file_count": models_count,
                "retention_policy": "Keep 3 versions per model",
                "schedule": "Weekly Sunday 05:00 UTC",
            },
            "solution_state": {
                "path": str(solution_path),
                "size_mb": solution_size,
                "file_count": solution_count,
                "retention_policy": "Keep 14 days",
                "schedule": "Weekly Sunday 05:15 UTC",
            },
            "total_size_mb": total_size,
        }

    except Exception as e:
        logger.error(
            "get_file_cleanup_status_failed",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get file cleanup status: {e!s}",
        ) from e


class CacheDirectoryInfo(TypedDict):
    """Info about a cache directory."""

    name: str
    path: str
    size_mb: float
    file_count: int
    description: str


class CacheStatusResponse(TypedDict):
    """Response for cache status endpoint."""

    directories: list[CacheDirectoryInfo]
    total_size_mb: float
    total_file_count: int


def _get_cache_dir_info(path: Path, name: str, description: str) -> CacheDirectoryInfo:
    """Get info about a cache directory, handling recursive patterns."""
    if not path.exists():
        return {
            "name": name,
            "path": str(path),
            "size_mb": 0.0,
            "file_count": 0,
            "description": description,
        }

    total_bytes = 0
    file_count = 0

    for f in path.rglob("*"):
        if f.is_file() and not f.is_symlink():
            try:
                total_bytes += f.stat().st_size
                file_count += 1
            except (OSError, FileNotFoundError):
                pass  # Skip files we can't access

    return {
        "name": name,
        "path": str(path),
        "size_mb": round(total_bytes / (1024 * 1024), 2),
        "file_count": file_count,
        "description": description,
    }


def _count_pycache_recursive(base_path: Path) -> tuple[float, int]:
    """Count all __pycache__ dirs under a path."""
    total_bytes = 0
    file_count = 0

    if not base_path.exists():
        return 0.0, 0

    for pycache_dir in base_path.rglob("__pycache__"):
        if pycache_dir.is_dir():
            for f in pycache_dir.iterdir():
                if f.is_file():
                    try:
                        total_bytes += f.stat().st_size
                        file_count += 1
                    except (OSError, FileNotFoundError):
                        pass

    return round(total_bytes / (1024 * 1024), 2), file_count


@router.get("/cache-status")
async def get_cache_status() -> CacheStatusResponse:
    """Get sizes for all cache directories that can be cleaned.

    These caches regenerate automatically and are safe to delete.

    Returns:
        Dict with cache directory info and totals

    Raises:
        HTTPException: If status retrieval fails
    """
    try:
        project_root = Path(__file__).parent.parent.parent.parent.parent
        backend_root = Path(__file__).parent.parent.parent.parent

        directories: list[CacheDirectoryInfo] = []

        # Python __pycache__ (backend)
        backend_pycache_size, backend_pycache_count = _count_pycache_recursive(backend_root)
        directories.append({
            "name": "Python Bytecode (backend)",
            "path": str(backend_root / "__pycache__"),
            "size_mb": backend_pycache_size,
            "file_count": backend_pycache_count,
            "description": "Compiled Python files, regenerate on import",
        })

        # Python __pycache__ (services)
        services_path = project_root / "services"
        services_pycache_size, services_pycache_count = _count_pycache_recursive(services_path)
        directories.append({
            "name": "Python Bytecode (services)",
            "path": str(services_path / "__pycache__"),
            "size_mb": services_pycache_size,
            "file_count": services_pycache_count,
            "description": "Compiled Python files, regenerate on import",
        })

        # Ruff cache
        ruff_path = backend_root / ".ruff_cache"
        directories.append(_get_cache_dir_info(
            ruff_path, "Ruff Linter Cache", "Ruff analysis cache, regenerates on lint"
        ))

        # Pytest cache
        pytest_path = backend_root / ".pytest_cache"
        directories.append(_get_cache_dir_info(
            pytest_path, "Pytest Cache", "Test execution cache, regenerates on test run"
        ))

        # Mypy cache
        mypy_path = backend_root / ".mypy_cache"
        directories.append(_get_cache_dir_info(
            mypy_path, "Mypy Cache", "Type check cache, regenerates on mypy run"
        ))

        # Next.js cache (only .next/cache, not server)
        nextjs_cache_path = project_root / "frontend" / ".next" / "cache"
        directories.append(_get_cache_dir_info(
            nextjs_cache_path, "Next.js Build Cache", "Webpack/build cache, regenerates on build"
        ))

        # Claude memory backups
        claude_memory_path = project_root / ".claude" / "backups" / "memory"
        directories.append(_get_cache_dir_info(
            claude_memory_path, "Claude Memory Backups", "Transient Claude memory, not essential"
        ))

        # Calculate totals
        total_size = sum(d["size_mb"] for d in directories)
        total_count = sum(d["file_count"] for d in directories)

        return {
            "directories": directories,
            "total_size_mb": round(total_size, 2),
            "total_file_count": total_count,
        }

    except Exception as e:
        logger.error(
            "get_cache_status_failed",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cache status: {e!s}",
        ) from e
