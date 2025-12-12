"""Celery tasks for acceptance criteria verification.

This module provides scheduled and on-demand verification tasks:
- verify_all_acceptance_criteria: Daily scheduled verification
- verify_feature_criteria: Verify a single feature's criteria
- verify_criteria_batch: Verify multiple features
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from celery import Task

from ..celery_app import celery_app
from ..logging_config import get_logger
from ..services.criteria_verifier import CriteriaVerifier
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)


@celery_app.task(bind=True, name="verify_all_acceptance_criteria")
def verify_all_acceptance_criteria(
    self: Task, type_filter: str | None = None, limit: int | None = None
) -> dict[str, Any]:
    """Verify all auto-verifiable acceptance criteria.

    Scheduled to run daily at 05:00 UTC after data refresh.
    Can also be triggered on-demand via API.

    Args:
        type_filter: Optional type filter (api, test, ui)
        limit: Optional limit on number of criteria to verify

    Returns:
        Summary dict with verification results
    """
    logger.info(
        "starting_scheduled_verification",
        type_filter=type_filter,
        limit=limit,
    )

    try:
        # Run async verification in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            verifier = CriteriaVerifier()
            result = loop.run_until_complete(
                verifier.verify_all_automatable(type_filter=type_filter, limit=limit)
            )
        finally:
            loop.close()

        # Record verification run in history
        _record_verification_run(result)

        logger.info("scheduled_verification_complete", **result)
        return result

    except Exception as e:
        logger.error("scheduled_verification_failed", error=str(e))
        return {"error": str(e), "status": "failed"}


@celery_app.task(bind=True, name="verify_feature_criteria")
def verify_feature_criteria(self: Task, feature_id: str) -> dict[str, Any]:
    """Verify all criteria for a single feature.

    Args:
        feature_id: The feature ID (e.g., FEAT-001)

    Returns:
        Dict with feature_id and list of criterion results
    """
    logger.info("verifying_feature_criteria", feature_id=feature_id)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            verifier = CriteriaVerifier()
            results = loop.run_until_complete(verifier.verify_feature(feature_id))
        finally:
            loop.close()

        # Count results
        passed = sum(1 for r in results if r.get("passed") is True)
        failed = sum(1 for r in results if r.get("passed") is False)

        summary = {
            "feature_id": feature_id,
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "criteria": results,
        }

        logger.info(
            "feature_criteria_verified",
            feature_id=feature_id,
            total=len(results),
            passed=passed,
            failed=failed,
        )
        return summary

    except Exception as e:
        logger.error(
            "feature_criteria_verification_failed",
            feature_id=feature_id,
            error=str(e),
        )
        return {"feature_id": feature_id, "error": str(e), "status": "failed"}


@celery_app.task(bind=True, name="verify_criteria_batch")
def verify_criteria_batch(self: Task, feature_ids: list[str]) -> dict[str, Any]:
    """Verify criteria for multiple features.

    Args:
        feature_ids: List of feature IDs to verify

    Returns:
        Dict with per-feature results and summary
    """
    logger.info("verifying_criteria_batch", feature_count=len(feature_ids))

    results = {}
    total_passed = 0
    total_failed = 0

    for feature_id in feature_ids:
        result = verify_feature_criteria(feature_id)
        results[feature_id] = result
        if "passed" in result:
            total_passed += result["passed"]
            total_failed += result["failed"]

    summary = {
        "features_verified": len(feature_ids),
        "total_passed": total_passed,
        "total_failed": total_failed,
        "results": results,
    }

    logger.info(
        "criteria_batch_verified",
        features=len(feature_ids),
        passed=total_passed,
        failed=total_failed,
    )
    return summary


def _record_verification_run(result: dict[str, Any]) -> None:
    """Record verification run in history table."""
    try:
        conn_mgr = get_connection_manager()
        with conn_mgr.connection() as conn:
            # Check if table exists first
            exists_result = conn.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'criteria_verification_runs'
                )
                """
            ).fetchone()

            if exists_result is None:
                logger.error("table_existence_check_failed")
                return

            exists = exists_result[0]

            if not exists:
                # Create table if it doesn't exist
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS criteria_verification_runs (
                        id SERIAL PRIMARY KEY,
                        run_at TIMESTAMPTZ DEFAULT NOW(),
                        total_criteria INT,
                        passed INT,
                        failed INT,
                        errors INT,
                        type_filter TEXT,
                        duration_seconds FLOAT
                    )
                    """
                )

            # Insert run record
            conn.execute(
                """
                INSERT INTO criteria_verification_runs
                    (run_at, total_criteria, passed, failed, errors, type_filter, duration_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    datetime.now(UTC),
                    result.get("total_verified", 0),
                    result.get("passed", 0),
                    result.get("failed", 0),
                    result.get("errors", 0),
                    result.get("type_filter"),
                    result.get("duration_seconds", 0),
                ),
            )
            conn.commit()

    except Exception as e:
        logger.error("record_verification_run_failed", error=str(e))
