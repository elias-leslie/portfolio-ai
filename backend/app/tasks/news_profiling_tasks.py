"""Tasks for news source quality profiling.

This module provides scheduled and on-demand profiling of news sources
to calculate quality metrics and track vendor performance.

Part of: News Source Quality Profiling System (Phase 1)
"""

from __future__ import annotations

import time
import uuid

from app.logging_config import get_logger
from app.storage import get_storage
from app.tasks.maintenance_logging import log_maintenance_complete, log_maintenance_start
from app.tasks.types import NewsProfilingResultDict

from ._news_profiling_helpers import (
    _delete_metrics_and_feedback,
    _get_active_vendors,
    _get_last_profiling_time,
    _get_profiling_interval_hours,
    _run_vendor_profiling,
    _should_skip_profiling,
)

logger = get_logger(__name__)


def profile_news_sources_task(
    user_id: str = "default"
) -> NewsProfilingResultDict:
    """Profile all active news sources and calculate quality metrics.

    Args:
        user_id: User identifier (default: "default")

    Returns:
        NewsProfilingResultDict: Task results with profiling summary
    """
    start_time = time.time()
    task_id = str(uuid.uuid4())
    storage = get_storage()
    log_id = log_maintenance_start("profile_news_sources_task", dry_run=False)
    try:
        interval_hours = _get_profiling_interval_hours()
        skip_result = _should_skip_profiling(interval_hours, _get_last_profiling_time())
        if skip_result:
            skip_result["task_id"] = task_id
            log_maintenance_complete(log_id, "profile_news_sources_task", True, dict(skip_result))
            return skip_result

        logger.info("profiling_news_sources_started", task_id=task_id, user_id=user_id, interval_hours=interval_hours)

        vendors = _get_active_vendors()
        if not vendors:
            logger.warning("no_active_vendors_found", task_id=task_id)
            result = NewsProfilingResultDict(
                status="completed", task_id=task_id, vendors_profiled=0,
                duration_seconds=round(time.time() - start_time, 2),
            )
            log_maintenance_complete(log_id, "profile_news_sources_task", True, dict(result))
            return result

        logger.info("active_vendors_found", task_id=task_id, num_vendors=len(vendors), vendors=vendors)
        result = _run_vendor_profiling(storage, vendors, task_id, user_id, start_time)
        log_maintenance_complete(log_id, "profile_news_sources_task", True, dict(result))
        return result
    except Exception as exc:
        duration = round(time.time() - start_time, 2)
        logger.error("profiling_news_sources_failed", task_id=task_id, user_id=user_id,
                     error=str(exc), duration_seconds=duration, exc_info=True)
        error_result = NewsProfilingResultDict(
            status="error", task_id=task_id, errors=[str(exc)], duration_seconds=duration,
        )
        log_maintenance_complete(log_id, "profile_news_sources_task", False, dict(error_result), str(exc))
        return error_result


def reset_source_metrics_task() -> NewsProfilingResultDict:
    """Reset all source metrics and user feedback.

    This task:
    1. Deletes all source_metrics records
    2. Deletes all user_article_feedback records
    3. Allows fresh profiling start

    Returns:
        NewsProfilingResultDict: Task results with deletion counts
    """
    start_time = time.time()
    task_id = str(uuid.uuid4())
    storage = get_storage()
    log_id = log_maintenance_start("reset_source_metrics_task", dry_run=False)

    try:
        metrics_deleted, feedback_deleted = _delete_metrics_and_feedback(storage)
        logger.info("source_metrics_reset_completed", task_id=task_id,
                    metrics_deleted=metrics_deleted, feedback_deleted=feedback_deleted)
        result = NewsProfilingResultDict(
            status="completed", task_id=task_id,
            metrics_deleted=metrics_deleted, feedback_deleted=feedback_deleted,
            duration_seconds=round(time.time() - start_time, 2),
        )
        log_maintenance_complete(log_id, "reset_source_metrics_task", True, dict(result))
        return result
    except Exception as exc:
        duration = round(time.time() - start_time, 2)
        logger.error("source_metrics_reset_failed", task_id=task_id,
                     error=str(exc), duration_seconds=duration, exc_info=True)
        result = NewsProfilingResultDict(
            status="error", task_id=task_id, errors=[str(exc)], duration_seconds=duration,
        )
        log_maintenance_complete(log_id, "reset_source_metrics_task", False, dict(result), str(exc))
        return result
