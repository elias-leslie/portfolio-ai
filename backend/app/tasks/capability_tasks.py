"""Celery tasks for system capability scanning.

These tasks run on schedule to auto-discover system capabilities.
AI analysis (analyze_capabilities) has been removed - tech debt is now
tracked as [DEBT] subtasks on features.
"""

from __future__ import annotations

import time

from ..celery_app import celery_app
from ..logging_config import get_logger
from ..services.capability_scanner import (
    APIScanner,
    CeleryScanner,
    DatabaseScanner,
    FeatureScanner,
)
from ..storage.connection import get_connection_manager
from .types import CapabilityResultDict

logger = get_logger(__name__)


@celery_app.task(name="scan_system_capabilities")  # type: ignore[misc]
def scan_system_capabilities() -> CapabilityResultDict:
    """Scan system capabilities (database tables, Celery tasks, API endpoints).

    Runs automatically on schedule (daily at 03:00 UTC) to discover and update
    capability metadata for monitoring and AI analysis.

    Returns:
        CapabilityResultDict with scan results:
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

        # Scan features (validates task file linkage and completion)
        logger.info("scanning_feature_capabilities")
        feature_scanner = FeatureScanner(conn_mgr)
        feature_caps = feature_scanner.scan()
        logger.info("feature_scan_complete", count=len(feature_caps))

        # Calculate duration
        duration = time.time() - start_time

        result: CapabilityResultDict = {
            "status": "success",
            "db_tables_scanned": len(db_caps),
            "celery_tasks_scanned": len(celery_caps),
            "api_endpoints_scanned": len(api_caps),
            "features_scanned": len(feature_caps),
            "total_capabilities": len(db_caps)
            + len(celery_caps)
            + len(api_caps)
            + len(feature_caps),
            "scan_duration_seconds": round(duration, 2),
        }

        logger.info(
            "capability_scan_complete",
            db_tables=len(db_caps),
            celery_tasks=len(celery_caps),
            api_endpoints=len(api_caps),
            features=len(feature_caps),
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

        return CapabilityResultDict(
            status="error",
            db_tables_scanned=0,
            celery_tasks_scanned=0,
            api_endpoints_scanned=0,
            total_capabilities=0,
            scan_duration_seconds=round(duration, 2),
            error=str(e),
        )


# analyze_capabilities task removed - tech debt is now tracked as [DEBT] subtasks on features
# See tasks/tasks-tech-debt-to-feature-subtasks-migration.md


@celery_app.task(name="scan_feature_capabilities")  # type: ignore[misc]
def scan_feature_capabilities() -> CapabilityResultDict:
    """Scan and validate features in feature_capabilities table.

    This task validates existing features by:
    - Checking task_file exists
    - Parsing task_section completion from markdown
    - Updating health_status based on verification state
    - Detecting inconsistencies (passes=True but tasks incomplete)

    Returns:
        CapabilityResultDict with scan results:
            - status: "success" or "error"
            - features_scanned: int
            - needs_review_count: int
            - scan_duration_seconds: float
            - error: str | None
    """
    start_time = time.time()

    logger.info("feature_capability_scan_started")

    try:
        # Get connection manager
        conn_mgr = get_connection_manager()

        # Initialize scanner
        scanner = FeatureScanner(conn_mgr)

        # Run scan
        features = scanner.scan()

        # Count features needing review
        needs_review_count = sum(1 for f in features if f.get("needs_review", False))

        # Get summary
        summary = scanner.get_summary()

        # Calculate duration
        duration = time.time() - start_time

        result: CapabilityResultDict = {
            "status": "success",
            "features_scanned": len(features),
            "needs_review_count": needs_review_count,
            "total_features": summary["total"],
            "passes_breakdown": summary["passes_breakdown"],
            "scan_duration_seconds": round(duration, 2),
        }

        logger.info(
            "feature_capability_scan_complete",
            features_scanned=len(features),
            needs_review=needs_review_count,
            duration_seconds=round(duration, 2),
        )

        return result

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "feature_capability_scan_failed",
            error=str(e),
            duration_seconds=round(duration, 2),
        )

        return CapabilityResultDict(
            status="error",
            features_scanned=0,
            needs_review_count=0,
            scan_duration_seconds=round(duration, 2),
            error=str(e),
        )
