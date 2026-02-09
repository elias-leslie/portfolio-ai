"""Celery tasks for acceptance criteria verification.

DEPRECATED: These tasks will be removed when SummitFlow has task infrastructure.
Features/verification are now managed by SummitFlow (port 8001).

This module provides scheduled and on-demand verification tasks:
- verify_all_acceptance_criteria: DISABLED (SummitFlow manages verification)
- verify_feature_criteria: DISABLED (SummitFlow manages verification)
- verify_criteria_batch: DISABLED (SummitFlow manages verification)
"""

from __future__ import annotations

from typing import Any

from ..logging_config import get_logger

logger = get_logger(__name__)


def verify_all_acceptance_criteria(
    type_filter: str | None = None, limit: int | None = None
) -> dict[str, Any]:
    """DISABLED: Verification is now managed by SummitFlow.

    This task is a no-op until SummitFlow has its own task infrastructure.
    See: portfolio-ai-4tg (SummitFlow: Add Celery task infrastructure)
    """
    logger.info(
        "verify_all_acceptance_criteria_skipped",
        reason="Migrated to SummitFlow - awaiting Celery integration",
        type_filter=type_filter,
        limit=limit,
    )
    return {
        "status": "skipped",
        "reason": "Verification now managed by SummitFlow",
    }


def verify_feature_criteria(feature_id: str) -> dict[str, Any]:
    """DISABLED: Verification is now managed by SummitFlow.

    This task is a no-op until SummitFlow has its own task infrastructure.
    See: portfolio-ai-4tg (SummitFlow: Add Celery task infrastructure)
    """
    logger.info(
        "verify_feature_criteria_skipped",
        reason="Migrated to SummitFlow - awaiting Celery integration",
        feature_id=feature_id,
    )
    return {
        "status": "skipped",
        "reason": "Verification now managed by SummitFlow",
        "feature_id": feature_id,
    }


def verify_criteria_batch(feature_ids: list[str]) -> dict[str, Any]:
    """DISABLED: Verification is now managed by SummitFlow.

    This task is a no-op until SummitFlow has its own task infrastructure.
    See: portfolio-ai-4tg (SummitFlow: Add Celery task infrastructure)
    """
    logger.info(
        "verify_criteria_batch_skipped",
        reason="Migrated to SummitFlow - awaiting Celery integration",
        feature_count=len(feature_ids),
    )
    return {
        "status": "skipped",
        "reason": "Verification now managed by SummitFlow",
        "feature_count": len(feature_ids),
    }
