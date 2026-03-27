"""Private helpers for news_profiling_tasks.py.

Extracted to keep the main task module concise.
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
    """Calculate all quality metrics for a single vendor."""
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
            errors.append(f"{vendor}: {exc!s}")
            logger.error(
                "vendor_metrics_calculation_failed",
                vendor=vendor,
                error=str(exc),
                exc_info=True,
            )

    return metrics_results, errors


def _store_metrics(metrics: list[tuple[str, dict[str, Any]]]) -> None:
    """Store calculated metrics in database."""
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


def _store_metrics_with_error_handling(
    metrics_results: list[tuple[str, dict[str, Any]]],
    errors: list[str],
    task_id: str,
) -> None:
    """Store metrics and append storage errors to errors list."""
    if not metrics_results:
        return
    try:
        _store_metrics(metrics_results)
        logger.info("metrics_stored_successfully", task_id=task_id, num_vendors=len(metrics_results))
    except Exception as exc:
        logger.error("metrics_storage_failed", task_id=task_id, error=str(exc), exc_info=True)
        errors.append(f"Storage failed: {exc!s}")


def _delete_metrics_and_feedback(storage: PortfolioStorage) -> tuple[int, int]:
    """Delete all source_metrics and user_article_feedback rows.

    Returns:
        (metrics_deleted, feedback_deleted) row counts
    """
    with storage.connection() as conn:
        conn.execute("DELETE FROM source_metrics")
        metrics_deleted = conn.rowcount
        conn.execute("DELETE FROM user_article_feedback")
        feedback_deleted = conn.rowcount
        conn.commit()
    return metrics_deleted, feedback_deleted


def _run_vendor_profiling(
    storage: PortfolioStorage,
    vendors: list[str],
    task_id: str,
    user_id: str,
    start_time: float,
) -> NewsProfilingResultDict:
    """Process all vendors and return a completed result dict."""
    weights = load_quality_weights_from_preferences(storage, user_id)
    now = datetime.now(UTC)
    window_start, window_end = now - timedelta(hours=24), now
    metrics_results, errors = _process_all_vendors(
        storage, vendors, window_start, window_end, weights, user_id
    )

    _store_metrics_with_error_handling(metrics_results, errors, task_id)

    duration = round(time.time() - start_time, 2)
    result = NewsProfilingResultDict(
        status="completed",
        task_id=task_id,
        vendors_profiled=len(metrics_results),
        total_vendors=len(vendors),
        errors=errors,
        duration_seconds=duration,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
    )
    logger.info(
        "profiling_news_sources_completed",
        task_id=task_id,
        vendors_profiled=len(metrics_results),
        total_vendors=len(vendors),
        errors_count=len(errors),
        duration_seconds=duration,
    )
    return result
