"""ML model management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..celery_app import celery_app
from ..logging_config import get_logger
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ml", tags=["ml"])


class TrainingTriggerResponse(BaseModel):
    """Response for training trigger."""

    success: bool
    session_id: str
    message: str


class TrainingProgressResponse(BaseModel):
    """Real-time training progress."""

    session_id: str
    status: str  # querying, labeling, training, complete, failed
    current_step: str
    progress_percent: int
    articles_found: int
    articles_labeled: int
    articles_total: int
    model_version: str | None
    accuracy: float | None
    error_message: str | None
    started_at: str
    completed_at: str | None


@router.post("/trigger-training", response_model=TrainingTriggerResponse)
async def trigger_training() -> TrainingTriggerResponse:
    """
    Manually trigger ML model training.

    Process:
    1. Queries 100 newest unlabeled articles from news_cache
    2. Labels them with Gemini (real AI review)
    3. Retrains sklearn model with accumulated data
    4. Updates production model

    Returns session_id for progress polling.
    """
    # Generate unique session ID
    session_id = str(uuid.uuid4())

    logger.info("ml_training_triggered", session_id=session_id)

    # Initialize progress tracking
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            conn.execute(
                """
                INSERT INTO ml_training_progress
                (session_id, status, current_step, progress_percent)
                VALUES (%s, %s, %s, %s)
            """,
                [session_id, "queued", "Queuing training task...", 0],
            )

            conn.commit()

    except Exception as e:
        logger.error("failed_to_create_progress", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize progress tracking: {e}"
        ) from e

    # Trigger async Celery task
    try:
        celery_app.send_task("retrain_article_quality_model_manual", args=[session_id])

        return TrainingTriggerResponse(
            success=True,
            session_id=session_id,
            message="Training started. Poll /api/ml/training-progress/{session_id} for updates.",
        )

    except Exception as e:
        logger.error("failed_to_trigger_training", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail=f"Failed to trigger training: {e}") from e


@router.get("/training-progress/{session_id}", response_model=TrainingProgressResponse)
async def get_training_progress(session_id: str) -> TrainingProgressResponse:
    """
    Get real-time progress for a training session.

    Poll this endpoint to track training progress.
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            conn.execute(
                """
                SELECT
                    session_id, status, current_step, progress_percent,
                    articles_found, articles_labeled, articles_total,
                    model_version, accuracy, error_message,
                    started_at, completed_at
                FROM ml_training_progress
                WHERE session_id = %s
            """,
                [session_id],
            )

            row = conn.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Training session not found")

            return TrainingProgressResponse(
                session_id=row[0],
                status=row[1],
                current_step=row[2],
                progress_percent=row[3],
                articles_found=row[4],
                articles_labeled=row[5],
                articles_total=row[6],
                model_version=row[7],
                accuracy=row[8],
                error_message=row[9],
                started_at=row[10].isoformat() if row[10] else "",
                completed_at=row[11].isoformat() if row[11] else None,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_fetch_progress", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch training progress: {e}"
        ) from e
