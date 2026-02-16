"""ML model management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..hatchet_app import get_admin_client
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

    try:
        admin = get_admin_client()
        admin.run_workflow(
            "portfolio-ml-train-manual",
            {"session_id": session_id},
        )

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
                session_id=str(row[0]),
                status=str(row[1]),
                current_step=str(row[2]),
                progress_percent=int(row[3]) if row[3] is not None else 0,
                articles_found=int(row[4]) if row[4] is not None else 0,
                articles_labeled=int(row[5]) if row[5] is not None else 0,
                articles_total=int(row[6]) if row[6] is not None else 0,
                model_version=str(row[7]) if row[7] is not None else None,
                accuracy=float(row[8]) if row[8] is not None else None,
                error_message=str(row[9]) if row[9] is not None else None,
                started_at=row[10].isoformat() if isinstance(row[10], datetime) else "",
                completed_at=row[11].isoformat() if isinstance(row[11], datetime) else None,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_fetch_progress", error=str(e), session_id=session_id)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch training progress: {e}"
        ) from e
