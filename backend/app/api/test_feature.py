"""API endpoint for E2E test feature validation.

Provides test status and execution history for workflow validation.
Used by FEAT-123 to validate the feature verification system itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)

router = APIRouter(prefix="/api/test", tags=["test"])


@router.get("/feature", response_model=dict[str, Any])
async def get_test_feature_status() -> dict[str, Any]:
    """Get test feature status and execution history.

    Returns:
        Test status including last run time and execution count
    """
    try:
        storage = get_storage()

        # Get verification history for FEAT-123 from feature_capabilities
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    feature_id,
                    name,
                    last_verified_at,
                    created_at,
                    acceptance_criteria
                FROM feature_capabilities
                WHERE feature_id = 'FEAT-123'
                """,
            ).fetchone()

            # Count total verification runs across all features
            run_count = conn.execute(
                """
                SELECT COUNT(*) FROM criteria_verification_runs
                """,
            ).fetchone()

        if result:
            last_verified = result[2]
            last_run_str = last_verified.isoformat() if last_verified else None
            total_runs = run_count[0] if run_count else 0
            criteria = result[4] if result[4] else []

            return {
                "status": "active",
                "feature_id": result[0],
                "feature_name": result[1],
                "last_run": last_run_str,
                "execution_count": total_runs,
                "criteria_count": len(criteria) if isinstance(criteria, list) else 0,
                "created_at": result[3].isoformat() if result[3] else None,
                "message": "E2E test feature is operational",
            }

        return {
            "status": "not_found",
            "feature_id": "FEAT-123",
            "last_run": None,
            "execution_count": 0,
            "message": "FEAT-123 not found in feature_capabilities",
        }

    except Exception as e:
        logger.exception("Failed to get test feature status", error=str(e))
        return {
            "status": "error",
            "feature_id": "FEAT-123",
            "last_run": None,
            "execution_count": 0,
            "error": str(e),
        }


@router.get("/health", response_model=dict[str, Any])
async def test_health() -> dict[str, Any]:
    """Simple health check for test endpoints.

    Returns:
        Health status with timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "test-feature-api",
    }
