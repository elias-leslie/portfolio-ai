"""QA system Celery tasks - daily scanning and snapshot generation.

This module provides automated QA scanning for:
- Dead code detection (unused functions/classes/imports)
- Orphan file detection (unreferenced files)
- Schema drift detection (model vs DB mismatches)
- Stale data detection (tables not updated recently)
- Code bloat detection (functions/files exceeding size limits)
- Test gap detection (untested code)

All tasks are designed to be:
- Idempotent (safe to run multiple times)
- Self-healing (detect and auto-resolve issues)
- Scheduled (run on Celery Beat schedule)
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from app.logging_config import get_logger
from app.utils.task_locks import task_lock
from app.utils.task_logging import task_logger

logger = get_logger(__name__)

# QA issue categories scanned by the system
QA_CATEGORIES = ["dead_code", "orphan_file", "schema_drift", "stale_data", "bloat", "test_gap"]


def _count_issues_by_category(issues: list[Any]) -> dict[str, int]:
    """Count issues by category using efficient Counter."""
    category_counts = Counter(issue.category for issue in issues)
    return {category: category_counts.get(category, 0) for category in QA_CATEGORIES}


def _build_success_response(
    task_id: str,
    issues: list[Any],
    snapshot_result: dict[str, Any],
) -> dict[str, Any]:
    """Build success response dictionary."""
    return {
        "status": "success",
        "task_id": task_id,
        "issues_found": len(issues),
        "issues_by_category": _count_issues_by_category(issues),
        "categories_scanned": QA_CATEGORIES,
        "snapshot": snapshot_result,
    }


def _build_error_response(task_id: str, error: Exception) -> dict[str, Any]:
    """Build error response dictionary."""
    return {
        "status": "failed",
        "task_id": task_id,
        "error": str(error),
        "error_type": type(error).__name__,
    }


def _build_skipped_response(task_id: str, reason: str) -> dict[str, Any]:
    """Build skipped response dictionary."""
    return {
        "status": "skipped",
        "reason": reason,
        "task_id": task_id,
    }


def daily_qa_scan() -> dict[str, Any]:
    """Run daily QA scan at 04:00 UTC, after capability scans.

    Workflow:
    1. Scans for all QA issue categories (dead_code, orphan_file, schema_drift, etc.)
    2. Upserts detected issues into qa_issues table
    3. Auto-resolves issues no longer detected (status: "resolved")
    4. Takes daily snapshot for trend tracking

    Returns:
        Dict with status, issues_found, categories_scanned
    """
    task_id = self.request.id or "unknown"

    with task_logger("daily_qa_scan", task_id), task_lock("daily_qa_scan", ttl=1800) as acquired:
        if not acquired:
            logger.info(
                "daily_qa_scan_skipped",
                task_id=task_id,
                reason="duplicate_task_already_running",
            )
            return _build_skipped_response(task_id, "duplicate_task_already_running")

        # Import here to avoid circular imports and ensure DB models are loaded
        try:
            from app.services.qa_scanner import QAScanner
        except ImportError:
            logger.warning(
                "daily_qa_scan_skipped",
                task_id=task_id,
                reason="qa_scanner_module_not_implemented",
            )
            return _build_skipped_response(task_id, "qa_scanner module not yet implemented")

        try:
            # Initialize scanner and run scan
            scanner = QAScanner()
            logger.info("daily_qa_scan_starting", task_id=task_id)
            issues = scanner.scan_all()

            # Upsert detected issues
            scanner.upsert_issues(issues)

            # Auto-resolve issues no longer detected
            scanner.auto_resolve_missing(issues)

            # Take daily snapshot for trend tracking
            snapshot_result = scanner.take_snapshot()

            logger.info(
                "daily_qa_scan_completed",
                task_id=task_id,
                issues_found=len(issues),
                snapshot_id=snapshot_result.get("snapshot_id"),
            )

            return _build_success_response(task_id, issues, snapshot_result)

        except Exception as e:
            logger.error(
                "daily_qa_scan_failed",
                task_id=task_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return _build_error_response(task_id, e)
