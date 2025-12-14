"""Celery task for file audit scanning."""

from __future__ import annotations

from typing import Any

from ..celery_app import celery_app
from ..logging_config import get_logger
from ..services.file_scanner import FileScanner

logger = get_logger(__name__)


@celery_app.task(name="scan_files")
def scan_files() -> dict[str, Any]:
    """Scan codebase and update file audit table.

    Can be triggered manually via API or scheduled.

    Returns:
        Summary dict with scan statistics.
    """
    logger.info("file_scan_task_started")

    try:
        scanner = FileScanner()
        result = scanner.scan()
        logger.info("file_scan_task_completed", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("file_scan_task_failed", error=str(e), error_type=type(e).__name__)
        return {"status": "error", "error": str(e)}
