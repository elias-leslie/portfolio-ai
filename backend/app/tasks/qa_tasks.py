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

from typing import TYPE_CHECKING, Any

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.utils.task_locks import task_lock
from app.utils.task_logging import task_logger

if TYPE_CHECKING:
    from celery import Task

logger = get_logger(__name__)


@celery_app.task(bind=True, name="tasks.daily_qa_scan")
def daily_qa_scan(self: Task) -> dict[str, Any]:
    """Run daily QA scan at 04:00 UTC, after capability scans.

    Workflow:
    1. Scans for all QA issue categories (dead_code, orphan_file, schema_drift, etc.)
    2. Upserts detected issues into qa_issues table
    3. Auto-resolves issues no longer detected (status: "resolved")
    4. Takes daily snapshot for trend tracking

    Returns:
        Dict with status, issues_found, categories_scanned
    """
    task_id = self.request.id

    with task_logger("daily_qa_scan", task_id), task_lock("daily_qa_scan", ttl=1800) as acquired:
        if not acquired:
            logger.info(
                "daily_qa_scan_skipped",
                task_id=task_id,
                reason="duplicate_task_already_running",
            )
            return {
                "status": "skipped",
                "reason": "duplicate_task_already_running",
                "task_id": task_id,
            }

        try:
            # Import here to avoid circular imports and ensure DB models are loaded
            from app.services.qa_scanner import QAScanner  # noqa: PLC0415

            # Initialize scanner
            scanner = QAScanner()

            # Scan for all issue types
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

            return {
                "status": "success",
                "task_id": task_id,
                "issues_found": len(issues),
                "issues_by_category": {
                    "dead_code": len([i for i in issues if i.category == "dead_code"]),
                    "orphan_file": len([i for i in issues if i.category == "orphan_file"]),
                    "schema_drift": len([i for i in issues if i.category == "schema_drift"]),
                    "stale_data": len([i for i in issues if i.category == "stale_data"]),
                    "bloat": len([i for i in issues if i.category == "bloat"]),
                    "test_gap": len([i for i in issues if i.category == "test_gap"]),
                },
                "categories_scanned": [
                    "dead_code",
                    "orphan_file",
                    "schema_drift",
                    "stale_data",
                    "bloat",
                    "test_gap",
                ],
                "snapshot": snapshot_result,
            }

        except Exception as e:
            logger.error(
                "daily_qa_scan_failed",
                task_id=task_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return {
                "status": "failed",
                "task_id": task_id,
                "error": str(e),
                "error_type": type(e).__name__,
            }
