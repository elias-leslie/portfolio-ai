"""Celery tasks for news source quality profiling.

This module provides scheduled and on-demand profiling of news sources
to calculate quality metrics and track vendor performance.

Part of: News Source Quality Profiling System (Phase 1)
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from app.logging_config import get_logger
from app.services.news_quality_metrics import (
    QualityWeights,
    calculate_all_metrics,
    load_quality_weights_from_preferences,
)
from app.storage import get_storage
from app.storage.facade import PortfolioStorage
from app.tasks.types import NewsProfilingResultDict

logger = get_logger(__name__)


def _get_profiling_interval_hours() -> int:
    """Get profiling interval from user preferences.

    Returns:
        int: Hours between profiling runs (default: 12)
    """
    storage = get_storage()
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT news_profiling_interval_hours
            FROM user_preferences
            WHERE id = %s
            """,
            ["default"],
        ).fetchone()

    if not result or result[0] is None:
        return 12  # Default

    return int(result[0])


def _get_last_profiling_time() -> datetime | None:
    """Get timestamp of last profiling run.

    Returns:
        datetime | None: Last profiling time, or None if never run
    """
    storage = get_storage()
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT MAX(calculated_at)
            FROM source_metrics
            """
        ).fetchone()

    if not result or result[0] is None:
        return None

    ts = result[0]
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=UTC)

    return None


def _get_active_vendors() -> list[str]:
    """Get list of active news vendors from news_cache.

    Returns:
        list[str]: List of vendor names that have articles in cache
    """
    storage = get_storage()
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT DISTINCT raw_payload->'raw'->>'vendor' AS vendor
            FROM news_cache
            WHERE raw_payload->'raw'->>'vendor' IS NOT NULL
            ORDER BY vendor
            """
        ).fetchall()

    vendors = [str(row[0]).strip() for row in result if row[0]]
    return [v for v in vendors if v and v not in {"null", "unknown"}]


def _should_skip_profiling(
    interval_hours: int, last_profiling: datetime | None
) -> NewsProfilingResultDict | None:
    """Check if profiling should be skipped due to interval.

    Args:
        interval_hours: Required interval between profiling runs
        last_profiling: Timestamp of last profiling, or None

    Returns:
        None if should proceed, or NewsProfilingResultDict with skip reason if should skip
    """
    if not last_profiling:
        return None

    now = datetime.now(UTC)
    elapsed = (now - last_profiling).total_seconds() / 3600.0
    if elapsed < interval_hours:
        logger.info(
            "profiling_skipped_too_soon",
            elapsed_hours=round(elapsed, 2),
            interval_hours=interval_hours,
            next_run_in=round(interval_hours - elapsed, 2),
        )
        return NewsProfilingResultDict(
            status="skipped",
            reason="interval_not_elapsed",
            elapsed_hours=round(elapsed, 2),
            interval_hours=interval_hours,
        )

    return None


def _calculate_vendor_metrics(
    storage: PortfolioStorage,
    vendor: str,
    window_start: datetime,
    window_end: datetime,
    weights: QualityWeights,
    user_id: str,
) -> dict[str, Any]:
    """Calculate all quality metrics for a single vendor.

    Args:
        storage: Storage instance
        vendor: Vendor name
        window_start: Start of analysis window
        window_end: End of analysis window
        weights: Quality metric weights
        user_id: User identifier

    Returns:
        Dict with metrics (duplicate_rate, diversity_score, etc.)
    """
    metrics = calculate_all_metrics(
        storage=storage,
        vendor=vendor,
        window_start=window_start,
        window_end=window_end,
        weights=weights,
        user_id=user_id,
    )

    return {
        "duplicate_rate": metrics.duplicate_rate,
        "diversity_score": metrics.diversity_score,
        "confidence_avg": metrics.confidence_avg,
        "freshness_score": metrics.freshness_score,
        "user_useful_rate": metrics.user_useful_rate,
        "quality_score": metrics.quality_score,
        "article_count": metrics.article_count,
        "sample_period_start": metrics.sample_period_start,
        "calculated_at": metrics.calculated_at,
    }


def _process_all_vendors(
    storage: PortfolioStorage,
    vendors: list[str],
    window_start: datetime,
    window_end: datetime,
    weights: QualityWeights,
    user_id: str,
) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    """Calculate metrics for all vendors, return results and errors.

    Args:
        storage: Storage instance
        vendors: List of vendor names
        window_start: Start of analysis window
        window_end: End of analysis window
        weights: Quality metric weights
        user_id: User identifier

    Returns:
        (metrics_results, errors) where metrics_results is list of (vendor, metrics_dict)
    """
    metrics_results: list[tuple[str, dict[str, Any]]] = []
    errors: list[str] = []

    for vendor in vendors:
        try:
            logger.debug("calculating_metrics_for_vendor", vendor=vendor)
            metrics_dict = _calculate_vendor_metrics(
                storage, vendor, window_start, window_end, weights, user_id
            )
            metrics_results.append((vendor, metrics_dict))
            logger.info(
                "vendor_metrics_calculated",
                vendor=vendor,
                quality_score=round(metrics_dict["quality_score"], 3),
                article_count=metrics_dict["article_count"],
            )
        except Exception as exc:
            error_msg = f"{vendor}: {exc!s}"
            errors.append(error_msg)
            logger.error(
                "vendor_metrics_calculation_failed",
                vendor=vendor,
                error=str(exc),
            )

    return metrics_results, errors


def _store_metrics(metrics: list[tuple[str, dict[str, Any]]]) -> None:
    """Store calculated metrics in database.

    Args:
        metrics: List of (vendor, metrics_dict) tuples
    """
    storage = get_storage()
    with storage.connection() as conn:
        for vendor, metric_dict in metrics:
            conn.execute(
                """
                INSERT INTO source_metrics (
                    vendor,
                    duplicate_rate,
                    diversity_score,
                    confidence_avg,
                    freshness_score,
                    user_useful_rate,
                    quality_score,
                    article_count,
                    sample_period_start,
                    calculated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    vendor,
                    metric_dict["duplicate_rate"],
                    metric_dict["diversity_score"],
                    metric_dict["confidence_avg"],
                    metric_dict["freshness_score"],
                    metric_dict["user_useful_rate"],
                    metric_dict["quality_score"],
                    metric_dict["article_count"],
                    metric_dict["sample_period_start"],
                    metric_dict["calculated_at"],
                ],
            )
        conn.commit()


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
    storage = get_storage()

    # Check if profiling is needed
    interval_hours = _get_profiling_interval_hours()
    last_profiling = _get_last_profiling_time()

    skip_result = _should_skip_profiling(interval_hours, last_profiling)
    if skip_result:
        return skip_result

    logger.info("profiling_news_sources_started", user_id=user_id, interval_hours=interval_hours)

    # Get active vendors
    vendors = _get_active_vendors()
    if not vendors:
        logger.warning("no_active_vendors_found")
        return NewsProfilingResultDict(
            status="completed",
            vendors_profiled=0,
            duration_seconds=round(time.time() - start_time, 2),
        )

    logger.info("active_vendors_found", num_vendors=len(vendors), vendors=vendors)
    weights = load_quality_weights_from_preferences(storage, user_id)

    # Calculate metrics for all vendors (last 24 hours)
    now = datetime.now(UTC)
    window_start, window_end = now - timedelta(hours=24), now
    metrics_results, errors = _process_all_vendors(
        storage, vendors, window_start, window_end, weights, user_id
    )

    # Store metrics
    if metrics_results:
        try:
            _store_metrics(metrics_results)
            logger.info("metrics_stored_successfully", num_vendors=len(metrics_results))
        except Exception as exc:
            logger.error("metrics_storage_failed", error=str(exc))
            errors.append(f"Storage failed: {exc!s}")

    duration = round(time.time() - start_time, 2)
    num_profiled = len(metrics_results)

    result: NewsProfilingResultDict = {
        "status": "completed",
        "vendors_profiled": num_profiled,
        "total_vendors": len(vendors),
        "errors": errors,
        "duration_seconds": duration,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
    }

    logger.info(
        "profiling_news_sources_completed",
        vendors_profiled=num_profiled,
        total_vendors=len(vendors),
        errors_count=len(errors),
        duration_seconds=duration,
    )
    return result


def reset_source_metrics_task() -> NewsProfilingResultDict:
    """Reset all source metrics and user feedback.

    This task:
    1. Deletes all source_metrics records
    2. Deletes all user_article_feedback records
    3. Allows fresh profiling start

    Returns:
        NewsProfilingResultDict: Task results with deletion counts
    """
    storage = get_storage()

    with storage.connection() as conn:
        # Delete source metrics
        conn.execute("DELETE FROM source_metrics")
        metrics_deleted = conn._cursor.rowcount  # type: ignore[attr-defined]

        # Delete user feedback
        conn.execute("DELETE FROM user_article_feedback")
        feedback_deleted = conn._cursor.rowcount  # type: ignore[attr-defined]

        conn.commit()

    logger.info(
        "source_metrics_reset_completed",
        metrics_deleted=metrics_deleted,
        feedback_deleted=feedback_deleted,
    )

    return NewsProfilingResultDict(
        status="completed",
        metrics_deleted=metrics_deleted,
        feedback_deleted=feedback_deleted,
    )
