"""ML model metrics and status endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/status", tags=["status", "ml"])


class MLModelMetrics(BaseModel):
    """ML model training metrics."""

    model_name: str
    model_version: str
    trained_at: str
    training_samples: int
    test_samples: int
    accuracy: float
    precision_score: float
    recall_score: float
    f1_score: float
    useful_count: int
    not_useful_count: int


class MLModelStatusResponse(BaseModel):
    """ML model status for status page."""

    current_model: MLModelMetrics | None
    previous_model: MLModelMetrics | None
    total_training_samples: int
    models_trained: int
    next_training: str  # Estimated next training time


@router.get("/ml-model-metrics", response_model=MLModelStatusResponse)
async def get_ml_model_metrics() -> MLModelStatusResponse:
    """
    Get ML model training metrics for status page.

    Returns current and previous model metrics, total samples, and next training time.
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Get latest 2 models
            conn.execute(
                """
                SELECT
                    model_name, model_version, trained_at,
                    training_samples, test_samples,
                    accuracy, precision_score, recall_score, f1_score,
                    useful_count, not_useful_count
                FROM ml_model_metrics
                WHERE model_name = %s
                ORDER BY trained_at DESC
                LIMIT 2
            """,
                ["article_quality"],
            )

            models = conn.fetchall()

            current_model = None
            previous_model = None

            if len(models) >= 1:
                row = models[0]
                current_model = MLModelMetrics(
                    model_name=row[0],
                    model_version=row[1],
                    trained_at=row[2].isoformat(),
                    training_samples=row[3],
                    test_samples=row[4],
                    accuracy=row[5],
                    precision_score=row[6],
                    recall_score=row[7],
                    f1_score=row[8],
                    useful_count=row[9],
                    not_useful_count=row[10],
                )

            if len(models) >= 2:
                row = models[1]
                previous_model = MLModelMetrics(
                    model_name=row[0],
                    model_version=row[1],
                    trained_at=row[2].isoformat(),
                    training_samples=row[3],
                    test_samples=row[4],
                    accuracy=row[5],
                    precision_score=row[6],
                    recall_score=row[7],
                    f1_score=row[8],
                    useful_count=row[9],
                    not_useful_count=row[10],
                )

            # Count total models trained
            conn.execute(
                "SELECT COUNT(*) FROM ml_model_metrics WHERE model_name = %s",
                ["article_quality"],
            )
            count_row = conn.fetchone()
            models_trained = count_row[0] if count_row else 0

            # Total training samples (from current model)
            total_samples = (
                current_model.training_samples + current_model.test_samples if current_model else 0
            )

            # Next training: Daily at ~02:00 UTC (after OHLCV refresh)
            now = datetime.now(UTC)
            tomorrow_2am = (now + timedelta(days=1)).replace(
                hour=2, minute=0, second=0, microsecond=0
            )
            next_training = tomorrow_2am.isoformat()

            return MLModelStatusResponse(
                current_model=current_model,
                previous_model=previous_model,
                total_training_samples=total_samples,
                models_trained=models_trained,
                next_training=next_training,
            )

    except Exception as e:
        logger.error("failed_to_fetch_ml_metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch ML model metrics: {e}") from e
