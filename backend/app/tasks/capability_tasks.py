"""Tasks for system capability scanning.

These tasks run on schedule to auto-discover system capabilities.
AI analysis (analyze_capabilities) has been removed - tech debt is now
tracked as [DEBT] subtasks on features.
"""

from __future__ import annotations

import time

from ..logging_config import get_logger
from ..services.capability_scanner import (
    APIScanner,
    DatabaseScanner,
    FeatureScanner,
)
from ..storage.connection import get_connection_manager
from .types import CapabilityResultDict

logger = get_logger(__name__)


def scan_system_capabilities() -> CapabilityResultDict:
    """Scan system capabilities (database tables, API endpoints).

    Runs automatically on schedule (daily at 03:00 UTC) to discover and update
    capability metadata for monitoring.

    Returns:
        CapabilityResultDict with scan results
    """
    start_time = time.time()

    logger.info("capability_scan_started")

    try:
        conn_mgr = get_connection_manager()

        # Scan database tables
        logger.info("scanning_database_capabilities")
        db_scanner = DatabaseScanner(conn_mgr)
        db_caps = db_scanner.scan()
        db_saved = db_scanner.save_capabilities(db_caps)
        logger.info("database_scan_saved", count=db_saved)

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

        duration = time.time() - start_time

        result: CapabilityResultDict = {
            "status": "success",
            "db_tables_scanned": len(db_caps),
            "celery_tasks_scanned": 0,
            "api_endpoints_scanned": len(api_caps),
            "features_scanned": len(feature_caps),
            "total_capabilities": len(db_caps) + len(api_caps) + len(feature_caps),
            "scan_duration_seconds": round(duration, 2),
        }

        logger.info(
            "capability_scan_complete",
            db_tables=len(db_caps),
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


def scan_feature_capabilities() -> CapabilityResultDict:
    """Scan and validate features in feature_capabilities table.

    This task validates existing features by:
    - Checking task_file exists
    - Parsing task_section completion from markdown
    - Updating health_status based on verification state
    - Detecting inconsistencies (passes=True but tasks incomplete)

    Returns:
        CapabilityResultDict with scan results
    """
    start_time = time.time()

    logger.info("feature_capability_scan_started")

    try:
        conn_mgr = get_connection_manager()
        scanner = FeatureScanner(conn_mgr)
        features = scanner.scan()
        needs_review_count = sum(1 for f in features if f.get("needs_review", False))
        summary = scanner.get_summary()

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
