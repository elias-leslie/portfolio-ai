"""Service for generating comprehensive dry-run reports.

Provides functions to run all cleanup tasks in dry-run mode and aggregate
the results into comprehensive reports.
"""

from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ..api.maintenance.monitoring_types import (
    DryRunCategoryReport,
    DryRunFileInfo,
    DryRunReportResponse,
)
from ..logging_config import get_logger

logger = get_logger(__name__)


def _extract_count_from_result(result: dict[str, Any]) -> int:
    """Extract count field from cleanup task result.

    Different tasks use different field names for counts.

    Args:
        result: Task result dict

    Returns:
        Count of items to delete/clean
    """
    count_fields = [
        "files_deleted",
        "directories_deleted",
        "directories_cleaned",
        "rows_deleted",
        "runs_deleted",
        "deleted_count",
        "files_rotated",
        "rows_to_delete",
        "runs_to_delete",
        "orphaned_insights_to_delete",
    ]

    count_field = next((f for f in count_fields if f in result), None)
    return result.get(count_field, 0) if count_field else 0


def _extract_bytes_from_result(result: dict[str, Any]) -> int:
    """Extract bytes freed field from cleanup task result.

    Args:
        result: Task result dict

    Returns:
        Bytes to be freed
    """
    bytes_fields = ["bytes_freed", "deleted_size_bytes"]
    bytes_field = next((f for f in bytes_fields if f in result), None)
    return result.get(bytes_field, 0) if bytes_field else 0


def _extract_files_from_result(result: dict[str, Any]) -> list[DryRunFileInfo]:
    """Extract file list from cleanup task result.

    Args:
        result: Task result dict

    Returns:
        List of file info dicts (limited to 50 items)
    """
    files: list[DryRunFileInfo] = []
    would_items = (
        result.get("would_delete") or result.get("would_rotate") or result.get("details") or []
    )

    for item in would_items[:50]:  # Limit to 50 items
        if isinstance(item, dict):
            files.append(
                {
                    "file": item.get("file") or item.get("directory") or item.get("path", "unknown"),
                    "size_bytes": item.get("size_bytes", 0),
                    "age_days": item.get("age_days", 0.0) or item.get("age_hours", 0.0) / 24.0,
                    "reason": item.get("reason") or item.get("action") or "age/count exceeded",
                }
            )

    return files


def _build_category_report(
    result: dict[str, Any] | None, category: str, retention: str
) -> DryRunCategoryReport:
    """Build a category report from task result.

    Args:
        result: Task result dict or None
        category: Category name
        retention: Retention policy description

    Returns:
        DryRunCategoryReport dict
    """
    if not result or not result.get("success"):
        return {
            "category": category,
            "would_delete_count": 0,
            "would_free_bytes": 0,
            "would_free_mb": 0.0,
            "files": [],
            "retention_policy": retention,
        }

    count = _extract_count_from_result(result)
    bytes_freed = _extract_bytes_from_result(result)
    files = _extract_files_from_result(result)

    return {
        "category": category,
        "would_delete_count": count,
        "would_free_bytes": bytes_freed,
        "would_free_mb": round(bytes_freed / (1024 * 1024), 2),
        "files": files,
        "retention_policy": retention,
    }


def generate_dry_run_report(celery_app, timeout: int = 60) -> DryRunReportResponse:  # type: ignore[no-untyped-def]
    """Generate a comprehensive dry-run report for all cleanup tasks.

    This runs ALL cleanup tasks in dry-run mode and aggregates the results.

    Args:
        celery_app: Celery application instance
        timeout: Max seconds to wait for each task (default: 60)

    Returns:
        DryRunReportResponse with categories and totals

    Raises:
        Exception: If report generation fails
    """
    logger.info("dry_run_report_started")

    # Define all cleanup tasks with their categories
    cleanup_tasks = [
        # File cleanup tasks
        ("cleanup_old_logs_task", "logs", "Keep 7 days"),
        ("cleanup_old_backups_task", "backups", "Keep 5 most recent"),
        ("cleanup_old_models_task", "models", "Keep 3 versions per model"),
        ("cleanup_solution_state_task", "solution_state", "Keep 14 days"),
        ("cleanup_cache_directories_task", "cache", "Safe to clear anytime"),
        ("cleanup_temp_files_task", "temp_files", "Keep 24 hours"),
        ("rotate_logs_task", "log_rotation", "Rotate files >10MB"),
        # Artifact cleanup tasks
        ("cleanup_old_versions", "artifact_versions", "Keep 5 per criterion"),
        ("cleanup_debug_captures", "debug_captures", "Keep 7 days"),
        # Database cleanup tasks
        ("cleanup_old_news_task", "news", "Keep 90 days"),
        ("cleanup_old_agent_runs_task", "agent_runs", "Keep 30 days"),
        ("cleanup_orphaned_data_task", "orphaned_data", "N/A"),
    ]

    categories: dict[str, DryRunCategoryReport] = {}
    errors: list[str] = []

    def run_task_dry_run(
        task_info: tuple[str, str, str],
    ) -> tuple[str, dict[str, Any] | None, str | None]:
        """Run a single task in dry-run mode and return result."""
        task_name, category, _retention = task_info
        try:
            task = celery_app.send_task(task_name, kwargs={"dry_run": True})
            result = task.get(timeout=timeout)
            return (category, result, None)
        except Exception as e:
            return (category, None, str(e))

    # Run all tasks concurrently using thread pool
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(run_task_dry_run, task): task for task in cleanup_tasks}

        for future in as_completed(futures):
            task_info = futures[future]
            task_name, category, retention = task_info

            try:
                _cat_name, result, error = future.result()

                if error:
                    errors.append(f"{task_name}: {error}")
                    continue

                categories[category] = _build_category_report(result, category, retention)

            except Exception as e:
                errors.append(f"{task_name}: {e!s}")

    # Calculate totals
    total_count = sum(cat["would_delete_count"] for cat in categories.values())
    total_bytes = sum(cat["would_free_bytes"] for cat in categories.values())

    # Log errors if any
    if errors:
        logger.warning("dry_run_report_errors", errors=errors)

    response: DryRunReportResponse = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "categories": categories,
        "total_would_delete": total_count,
        "total_would_free_mb": round(total_bytes / (1024 * 1024), 2),
    }

    logger.info(
        "dry_run_report_completed",
        categories=len(categories),
        total_count=total_count,
        total_mb=response["total_would_free_mb"],
    )

    return response
