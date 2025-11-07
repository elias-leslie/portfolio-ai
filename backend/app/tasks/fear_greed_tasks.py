"""Celery tasks for Fear & Greed Index computation."""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog

from ..celery_app import celery_app
from ..market.fear_greed_service import FearGreedService
from ..storage import get_storage

logger = structlog.get_logger(__name__)


@celery_app.task(name="compute_fear_greed_daily", bind=True, max_retries=3)  # type: ignore[misc]
def compute_fear_greed_daily(self: Any) -> dict[str, str | float]:
    """Compute Fear & Greed Index for current date.

    Scheduled to run daily at 03:30 UTC (after market close + data availability).

    Returns:
        Dict with computation result
    """
    try:
        target_date = date.today()
        logger.info("fear_greed_task_start", date=target_date)

        storage = get_storage()
        service = FearGreedService(storage)

        result = service.compute_for_date(target_date)

        logger.info(
            "fear_greed_task_complete",
            date=target_date,
            score=result["score"],
            label=result["label"],
        )

        return {
            "status": "success",
            "date": str(target_date),
            "score": result["score"],
            "label": result["label"],
        }

    except Exception as e:
        logger.error("fear_greed_task_failed", error=str(e), exc_info=True)

        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2**self.request.retries)) from e
