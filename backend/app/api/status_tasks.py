"""Celery task management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..hatchet_app import get_hatchet
from ..logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/status", tags=["status", "tasks"])


class WatchlistRefreshResponse(BaseModel):
    """Response for watchlist refresh operation."""

    success: bool
    task_id: str
    message: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


@router.post("/watchlist/refresh", response_model=WatchlistRefreshResponse)
def refresh_watchlist() -> WatchlistRefreshResponse:
    """Trigger manual watchlist refresh (Celery task).

    Returns:
        WatchlistRefreshResponse: Result with task ID
    """
    logger.info("refresh_watchlist_request")

    try:
        hatchet = get_hatchet()
        workflow_run = hatchet.admin.run_workflow("portfolio-refresh-watchlist-scores", {})

        logger.info("refresh_watchlist_triggered", task_id=workflow_run.workflow_run_id)
        return WatchlistRefreshResponse(
            success=True,
            task_id=workflow_run.workflow_run_id,
            message=f"Watchlist refresh task triggered (ID: {workflow_run.workflow_run_id})",
        )

    except Exception as e:
        logger.error("refresh_watchlist_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Error triggering watchlist refresh: {e!s}"
        ) from e
