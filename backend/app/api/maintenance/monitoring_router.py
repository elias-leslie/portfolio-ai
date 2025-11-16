"""Maintenance monitoring and statistics router.

This module provides REST API endpoints for monitoring system resources,
database size, maintenance statistics, and scheduled task information.
"""

from __future__ import annotations

from typing import Any

from celery.schedules import (  # type: ignore[import-untyped]
    crontab as CrontabSchedule,  # noqa: N812 - Using CamelCase for isinstance checks
)
from fastapi import APIRouter, HTTPException

from ...celery_app import celery_app
from ...logging_config import get_logger
from ...services.maintenance_tracker import (
    get_all_metrics_summary,
    get_cleanup_trends,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


# API Endpoints


@router.get("/disk-space")
async def get_disk_space() -> dict[str, Any]:
    """Get current disk space usage for all monitored partitions.

    Returns:
        Dict with partition information and alerts

    Raises:
        HTTPException: If disk space check fails
    """
    try:
        # Trigger disk space check task and wait for result
        task = celery_app.send_task("check_disk_space_task")
        result: dict[str, Any] = task.get(timeout=10)  # Wait up to 10 seconds

        return result

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
async def get_database_size() -> dict[str, Any]:
    """Get current database size and table sizes.

    Returns:
        Dict with database size and top tables

    Raises:
        HTTPException: If database size check fails
    """
    try:
        # Trigger database size task and wait for result
        task = celery_app.send_task("get_database_size_task")
        result: dict[str, Any] = task.get(timeout=10)  # Wait up to 10 seconds

        return result

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
async def get_maintenance_schedule() -> dict[str, Any]:
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
