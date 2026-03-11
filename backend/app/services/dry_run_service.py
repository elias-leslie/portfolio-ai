"""Service for generating comprehensive dry-run reports.

Provides functions to run all cleanup tasks in dry-run mode and aggregate
the results into comprehensive reports.
"""

from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from typing import Any

from ..logging_config import get_logger
from ..tasks.cleanup import (
    cleanup_cache_directories_task,
    cleanup_old_backups_task,
    cleanup_old_logs_task,
    cleanup_old_models_task,
    cleanup_solution_state_task,
    cleanup_temp_files_task,
    rotate_logs_task,
)
from ..tasks.maintenance_tasks import (
    cleanup_maintenance_tables_task,
    cleanup_old_agent_runs_task,
    cleanup_old_news_task,
    cleanup_old_watchlist_snapshots_task,
    cleanup_orphaned_data_task,
)
from .maintenance_types import (
    DryRunCategoryReport,
    DryRunFileInfo,
    DryRunReportResponse,
)

logger = get_logger(__name__)

DRY_RUN_TASKS: list[tuple[str, str, str, Any]] = [
    ("cleanup_old_logs_task", "logs", "Keep 7 days", cleanup_old_logs_task),
    ("cleanup_old_backups_task", "backups", "Keep 5 most recent", cleanup_old_backups_task),
    ("cleanup_old_models_task", "models", "Keep 3 versions per model", cleanup_old_models_task),
    ("cleanup_solution_state_task", "solution_state", "Keep 14 days", cleanup_solution_state_task),
    (
        "cleanup_cache_directories_task",
        "cache",
        "Safe to clear anytime",
        cleanup_cache_directories_task,
    ),
    ("cleanup_temp_files_task", "temp_files", "Keep 24 hours", cleanup_temp_files_task),
    ("rotate_logs_task", "log_rotation", "Rotate files >10MB", rotate_logs_task),
    ("cleanup_old_news_task", "news", "Keep 90 days", cleanup_old_news_task),
    ("cleanup_old_agent_runs_task", "agent_runs", "Keep 30 days", cleanup_old_agent_runs_task),
    (
        "cleanup_orphaned_data_task",
        "stale_agent_runs",
        "Mark stale runs older than 1 hour as failed",
        cleanup_orphaned_data_task,
    ),
    (
        "cleanup_old_watchlist_snapshots_task",
        "watchlist_snapshots",
        "Keep 60 days",
        cleanup_old_watchlist_snapshots_task,
    ),
    (
        "cleanup_maintenance_tables_task",
        "maintenance_tables",
        "Keep 90 days",
        cleanup_maintenance_tables_task,
    ),
]


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
        "zombie_runs_fixed",
        "deleted_count",
        "files_rotated",
        "rows_to_delete",
        "runs_to_delete",
        "zombie_runs_to_fix",
    ]

    explicit_count = next((f for f in count_fields if f in result), None)
    if explicit_count:
        return int(result.get(explicit_count, 0) or 0)

    derived_count = 0
    for key, value in result.items():
        if not isinstance(value, int):
            continue
        if key.endswith("_to_delete") or key.endswith("_deleted"):
            derived_count += value
    return derived_count


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
                    "file": item.get("file")
                    or item.get("directory")
                    or item.get("path", "unknown"),
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


def _process_future_result(
    future: Any,
    task_info: tuple[str, str, str, Any],
    categories: dict[str, DryRunCategoryReport],
    errors: list[str],
) -> None:
    """Process a completed future result and update categories/errors.

    Args:
        future: The completed future object
        task_info: Task information tuple (name, category, retention, fn)
        categories: Dictionary to store category reports
        errors: List to collect error messages
    """
    task_name, category, retention, _task_fn = task_info

    try:
        _cat_name, result, error = future.result()

        if error:
            errors.append(f"{task_name}: {error}")
            return

        categories[category] = _build_category_report(result, category, retention)

    except Exception as e:
        errors.append(f"{task_name}: {e!s}")


def generate_dry_run_report(timeout: int = 60) -> DryRunReportResponse:
    """Generate a comprehensive dry-run report for all cleanup tasks.

    This runs ALL cleanup tasks in dry-run mode and aggregates the results.

    Args:
        timeout: Max seconds to wait for each task (default: 60)

    Returns:
        DryRunReportResponse with categories and totals

    Raises:
        Exception: If report generation fails
    """
    logger.info("dry_run_report_started")

    categories: dict[str, DryRunCategoryReport] = {}
    errors: list[str] = []

    def run_task_dry_run(
        task_info: tuple[str, str, str, Any],
    ) -> tuple[str, dict[str, Any] | None, str | None]:
        """Run a single task in dry-run mode and return result."""
        _task_name, category, _retention, task_fn = task_info
        try:
            result = task_fn(dry_run=True)
            return (category, result, None)
        except Exception as e:
            return (category, None, str(e))

    # Run all tasks concurrently using thread pool
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(run_task_dry_run, task): task for task in DRY_RUN_TASKS}

        try:
            for future in as_completed(futures, timeout=timeout):
                task_info = futures[future]
                _process_future_result(future, task_info, categories, errors)
        except TimeoutError:
            logger.error("dry_run_report_timed_out", timeout_seconds=timeout)
            errors.append(f"dry_run_report timed out after {timeout} seconds")
            for future, task_info in futures.items():
                if future.done():
                    continue
                future.cancel()
                errors.append(f"{task_info[0]}: timed out")

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
    if errors:
        response["errors"] = errors

    logger.info(
        "dry_run_report_completed",
        categories=len(categories),
        total_count=total_count,
        total_mb=response["total_would_free_mb"],
    )

    return response
