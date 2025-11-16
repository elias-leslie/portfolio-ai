"""Celery tasks for system capability scanning and AI analysis.

These tasks run on schedule to auto-discover system capabilities and
generate AI-powered insights about data quality and gaps.
"""

from __future__ import annotations

import time
from typing import Any

from ..celery_app import celery_app
from ..logging_config import get_logger
from ..services.ai_analyzer import CapabilityAnalyzer
from ..services.capability_scanner import APIScanner, CeleryScanner, DatabaseScanner
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)


@celery_app.task(name="scan_system_capabilities")  # type: ignore[misc]
def scan_system_capabilities() -> dict[str, Any]:
    """Scan system capabilities (database tables, Celery tasks, API endpoints).

    Runs automatically on schedule (daily at 03:00 UTC) to discover and update
    capability metadata for monitoring and AI analysis.

    Returns:
        Dict with scan results:
            - status: "success" or "error"
            - db_tables_scanned: int
            - celery_tasks_scanned: int
            - api_endpoints_scanned: int
            - total_capabilities: int
            - scan_duration_seconds: float
            - error: str | None
    """
    start_time = time.time()

    logger.info("capability_scan_started")

    try:
        # Get connection manager
        conn_mgr = get_connection_manager()

        # Scan database tables
        logger.info("scanning_database_capabilities")
        db_scanner = DatabaseScanner(conn_mgr)
        db_caps = db_scanner.scan()
        db_saved = db_scanner.save_capabilities(db_caps)
        logger.info("database_scan_saved", count=db_saved)

        # Scan Celery tasks
        logger.info("scanning_celery_capabilities")
        celery_scanner = CeleryScanner(conn_mgr)
        celery_caps = celery_scanner.scan()
        celery_saved = celery_scanner.save_capabilities(celery_caps)
        logger.info("celery_scan_saved", count=celery_saved)

        # Scan API endpoints
        logger.info("scanning_api_capabilities")
        api_scanner = APIScanner(conn_mgr)
        api_caps = api_scanner.scan()
        api_saved = api_scanner.save_capabilities(api_caps)
        logger.info("api_scan_saved", count=api_saved)

        # Calculate duration
        duration = time.time() - start_time

        result = {
            "status": "success",
            "db_tables_scanned": len(db_caps),
            "celery_tasks_scanned": len(celery_caps),
            "api_endpoints_scanned": len(api_caps),
            "total_capabilities": len(db_caps) + len(celery_caps) + len(api_caps),
            "scan_duration_seconds": round(duration, 2),
            "error": None,
        }

        logger.info(
            "capability_scan_complete",
            db_tables=len(db_caps),
            celery_tasks=len(celery_caps),
            api_endpoints=len(api_caps),
            duration_seconds=round(duration, 2),
        )

        return result

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "capability_scan_failed",
            error=str(e),
            duration_seconds=round(duration, 2),
        )

        return {
            "status": "error",
            "db_tables_scanned": 0,
            "celery_tasks_scanned": 0,
            "api_endpoints_scanned": 0,
            "total_capabilities": 0,
            "scan_duration_seconds": round(duration, 2),
            "error": str(e),
        }


@celery_app.task(name="analyze_capabilities")  # type: ignore[misc]
def analyze_capabilities() -> dict[str, Any]:
    """Run AI analysis on system capabilities to identify issues and gaps.

    Runs automatically on schedule (daily at 03:15 UTC, 15 min after scan)
    to generate insights about data quality, freshness, and missing capabilities.

    Uses Claude Code CLI (zero API cost) for analysis. No ANTHROPIC_API_KEY required.
    Claude CLI is auto-detected from PATH or CLAUDE_CLI_PATH environment variable.

    Typical execution time: 2-5 minutes (CLI subprocess overhead ~200ms + analysis time)

    Returns:
        Dict with analysis results:
            - status: "success" or "error"
            - insights_generated: int
            - insights_saved: int
            - analysis_duration_seconds: float
            - error: str | None
    """
    start_time = time.time()

    logger.info("ai_capability_analysis_started")

    try:
        # Get connection manager
        conn_mgr = get_connection_manager()

        # Initialize analyzer
        analyzer = CapabilityAnalyzer(conn_mgr)

        # Run analysis
        insights = analyzer.analyze()

        # Calculate duration
        duration = time.time() - start_time

        result = {
            "status": "success",
            "insights_generated": len(insights),
            "insights_saved": len(insights),
            "analysis_duration_seconds": round(duration, 2),
            "error": None,
        }

        logger.info(
            "ai_capability_analysis_complete",
            insights_generated=len(insights),
            duration_seconds=round(duration, 2),
        )

        return result

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "ai_capability_analysis_failed",
            error=str(e),
            duration_seconds=round(duration, 2),
        )

        return {
            "status": "error",
            "insights_generated": 0,
            "insights_saved": 0,
            "analysis_duration_seconds": round(duration, 2),
            "error": str(e),
        }
