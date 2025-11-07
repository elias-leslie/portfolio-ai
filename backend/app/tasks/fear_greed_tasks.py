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

    Self-healing: Automatically triggers backfill if insufficient historical data.

    Returns:
        Dict with computation result
    """
    try:
        target_date = date.today()
        logger.info("fear_greed_task_start", date=target_date)

        storage = get_storage()

        # Check if we have sufficient historical data for accurate percentiles
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT COUNT(*)
                FROM fear_greed_inputs
                WHERE vix_close IS NOT NULL AND hy_spread IS NOT NULL
                """
            )
            historical_count = result.fetchone()[0]

        # If less than 100 days of historical data, trigger backfill first
        # (252 days ideal, but 100 days minimum for somewhat meaningful percentiles)
        if historical_count < 100:
            logger.warning(
                "insufficient_historical_data",
                current_count=historical_count,
                required_minimum=100,
                triggering_backfill=True
            )

            # Import here to avoid circular dependency
            from ..tasks.data_ingestion_tasks import backfill_fred_indicators

            # Trigger backfill task (waits for completion)
            logger.info("triggering_backfill_task", days=252)
            backfill_result = backfill_fred_indicators.delay(days=252).get(timeout=300)
            logger.info(
                "backfill_completed",
                rows_inserted=backfill_result.get("rows_inserted", 0),
                vix_rows=backfill_result.get("vix_rows", 0),
                hy_spread_rows=backfill_result.get("hy_spread_rows", 0)
            )

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
