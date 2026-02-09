"""Maintenance monitoring and statistics router.

This module provides REST API endpoints for monitoring system resources,
database size, maintenance statistics, and scheduled task information.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, HTTPException

from ...logging_config import get_logger
from ...services.dry_run_service import generate_dry_run_report
from ...services.file_monitoring_service import (
    get_cache_status as get_cache_status_service,
)
from ...services.file_monitoring_service import (
    get_file_cleanup_status as get_file_cleanup_status_service,
)
from ...services.maintenance_tracker import (
    get_all_metrics_summary,
    get_cleanup_trends,
)
from ...tasks.cleanup.disk_monitoring import check_disk_space_impl
from ...tasks.maintenance_operations import get_database_size
from ..maintenance_types import (
    DatabaseSizeResponseDict,
    DiskSpaceResponseDict,
    MaintenanceScheduleResponseDict,
)
from .monitoring_types import (
    CacheStatusResponse,
    DryRunReportResponse,
    FileCleanupStatusResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


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
        result = check_disk_space_impl()
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
async def get_database_size_endpoint() -> DatabaseSizeResponseDict:
    """Get current database size and table sizes.

    Returns:
        Dict with database size and top tables

    Raises:
        HTTPException: If database size check fails
    """
    try:
        # Call implementation directly (no Celery, immediate response)
        result = get_database_size()
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
        scheduled_tasks = {
            "vacuum-database": {"task": "portfolio-vacuum-db", "schedule": "crontab(0 2 * * 0)"},
            "cleanup-old-news": {"task": "portfolio-cleanup-old-news", "schedule": "crontab(0 3 * * *)"},
            "cleanup-agent-runs": {"task": "portfolio-cleanup-agent-runs", "schedule": "crontab(30 3 * * *)"},
            "cleanup-orphaned": {"task": "portfolio-cleanup-orphaned-data", "schedule": "crontab(0 4 * * 0)"},
            "cleanup-logs": {"task": "portfolio-cleanup-logs", "schedule": "crontab(0 2 * * *)"},
            "cleanup-temp": {"task": "portfolio-cleanup-temp", "schedule": "crontab(30 2 * * *)"},
            "cleanup-backups": {"task": "portfolio-cleanup-backups", "schedule": "crontab(0 1 * * 0)"},
            "cleanup-models": {"task": "portfolio-cleanup-models", "schedule": "crontab(30 1 * * 0)"},
            "cleanup-solution-state": {"task": "portfolio-cleanup-solution-state", "schedule": "crontab(0 5 * * *)"},
            "check-disk": {"task": "portfolio-check-disk", "schedule": "crontab(*/30 * * * *)"},
            "rotate-logs": {"task": "portfolio-rotate-logs", "schedule": "crontab(0 0 * * *)"},
        }
        return {
            "scheduled_tasks": scheduled_tasks,
            "total_count": len(scheduled_tasks),
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


@router.get("/file-cleanup-status")
async def get_file_cleanup_status() -> FileCleanupStatusResponse:
    """Get sizes and retention info for file cleanup directories.

    Returns:
        Dict with file cleanup status for logs, backups, models, solution_state

    Raises:
        HTTPException: If status retrieval fails
    """
    try:
        return get_file_cleanup_status_service()

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
        return get_cache_status_service()

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


@router.post("/dry-run-report")
async def get_dry_run_report(timeout: int = 60) -> DryRunReportResponse:
    """Generate a comprehensive dry-run report for all cleanup tasks.

    This endpoint runs ALL cleanup tasks in dry-run mode and aggregates
    the results into a comprehensive report showing what WOULD be cleaned.

    Args:
        timeout: Max seconds to wait for each task (default: 60)

    Returns:
        DryRunReportResponse with categories and totals

    Raises:
        HTTPException: If report generation fails
    """
    try:
        return generate_dry_run_report(timeout)

    except Exception as e:
        logger.error(
            "dry_run_report_failed",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate dry-run report: {e!s}",
        ) from e
