"""News source profiling and quality metrics API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.storage import get_storage
from app.tasks.news_profiling_tasks import profile_news_sources_task, reset_source_metrics_task

router = APIRouter(prefix="/api/news", tags=["news-profiling"])

storage = get_storage()


class SourceMetricsResponse(BaseModel):
    """Source quality metrics response."""

    vendor: str
    duplicate_rate: float
    diversity_score: float
    confidence_avg: float
    freshness_score: float
    user_useful_rate: float | None
    quality_score: float
    article_count: int
    sample_period_start: str
    calculated_at: str


class ArticleFeedbackRequest(BaseModel):
    """Request to submit article feedback."""

    article_url: str
    article_hash: str
    vendor: str
    is_useful: bool
    sentiment_override: float | None = Field(
        None, description="User-corrected sentiment (-1.0 to 1.0)"
    )


class ArticleFeedbackResponse(BaseModel):
    """Article feedback response."""

    status: str
    message: str
    vendor: str
    updated_useful_rate: float | None = None


class ProfilingTaskResponse(BaseModel):
    """Response from profiling task trigger."""

    status: str
    task_id: str | None = None
    message: str


@router.post("/profile-sources", response_model=ProfilingTaskResponse)
async def trigger_profiling(user_id: str = "default") -> ProfilingTaskResponse:
    """Trigger news source profiling task.

    This endpoint triggers an immediate profiling run for all active news sources.
    The task calculates 6 quality metrics per vendor and stores results in the database.

    Args:
        user_id: User identifier (default: "default")

    Returns:
        ProfilingTaskResponse with task ID and status
    """
    try:
        # Trigger async task
        task = profile_news_sources_task.apply_async(args=[user_id])

        return ProfilingTaskResponse(
            status="accepted",
            task_id=str(task.id),
            message="Profiling task triggered successfully. Check /api/celery/status/{task_id} for progress.",
        )
    except Exception as exc:
        return ProfilingTaskResponse(
            status="error",
            message=f"Failed to trigger profiling: {exc!s}",
        )


@router.get("/source-stats", response_model=list[SourceMetricsResponse])
async def get_all_source_stats() -> list[SourceMetricsResponse]:
    """Get latest quality metrics for all news sources.

    Returns the most recent quality metrics for each vendor, sorted by quality score descending.

    Returns:
        list[SourceMetricsResponse]: List of source metrics, one per vendor
    """
    with storage.connection() as conn:
        # Get latest metrics for each vendor
        result = conn.execute(
            """
            SELECT DISTINCT ON (vendor)
                vendor,
                duplicate_rate,
                diversity_score,
                confidence_avg,
                freshness_score,
                user_useful_rate,
                quality_score,
                article_count,
                sample_period_start,
                calculated_at
            FROM source_metrics
            ORDER BY vendor, calculated_at DESC
            """
        ).fetchall()

    metrics_list: list[SourceMetricsResponse] = []
    for row in result:
        metrics_list.append(
            SourceMetricsResponse(
                vendor=str(row[0]),
                duplicate_rate=float(row[1]),
                diversity_score=float(row[2]),
                confidence_avg=float(row[3]),
                freshness_score=float(row[4]),
                user_useful_rate=float(row[5]) if row[5] is not None else None,
                quality_score=float(row[6]),
                article_count=int(row[7]),
                sample_period_start=row[8].isoformat(),
                calculated_at=row[9].isoformat(),
            )
        )

    # Sort by quality score descending
    metrics_list.sort(key=lambda m: m.quality_score, reverse=True)

    return metrics_list


@router.get("/source-stats/{vendor}", response_model=SourceMetricsResponse | None)
async def get_vendor_stats(vendor: str) -> SourceMetricsResponse | None:
    """Get latest quality metrics for a specific vendor.

    Args:
        vendor: Vendor identifier (e.g., "polygon", "finnhub", "sec_edgar")

    Returns:
        SourceMetricsResponse: Latest metrics for the vendor, or None if not found
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT
                vendor,
                duplicate_rate,
                diversity_score,
                confidence_avg,
                freshness_score,
                user_useful_rate,
                quality_score,
                article_count,
                sample_period_start,
                calculated_at
            FROM source_metrics
            WHERE vendor = %s
            ORDER BY calculated_at DESC
            LIMIT 1
            """,
            [vendor],
        ).fetchone()

    if not result:
        return None

    return SourceMetricsResponse(
        vendor=str(result[0]),
        duplicate_rate=float(result[1]),
        diversity_score=float(result[2]),
        confidence_avg=float(result[3]),
        freshness_score=float(result[4]),
        user_useful_rate=float(result[5]) if result[5] is not None else None,
        quality_score=float(result[6]),
        article_count=int(result[7]),
        sample_period_start=result[8].isoformat(),
        calculated_at=result[9].isoformat(),
    )


@router.post("/article-feedback", response_model=ArticleFeedbackResponse)
async def submit_article_feedback(
    feedback: ArticleFeedbackRequest,
    user_id: str = "default",
) -> ArticleFeedbackResponse:
    """Submit user feedback (thumbs up/down) on a news article.

    This feedback is used to train source quality personalization.

    Args:
        feedback: Article feedback request
        user_id: User identifier (default: "default")

    Returns:
        ArticleFeedbackResponse with updated useful rate
    """
    try:
        with storage.connection() as conn:
            # Insert or update feedback
            conn.execute(
                """
                INSERT INTO user_article_feedback (
                    user_id,
                    article_url,
                    article_hash,
                    vendor,
                    is_useful,
                    sentiment_override
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, article_hash)
                DO UPDATE SET
                    is_useful = EXCLUDED.is_useful,
                    sentiment_override = EXCLUDED.sentiment_override,
                    created_at = NOW()
                """,
                [
                    user_id,
                    feedback.article_url,
                    feedback.article_hash,
                    feedback.vendor,
                    feedback.is_useful,
                    feedback.sentiment_override,
                ],
            )

            # Get updated useful rate for vendor
            result = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN is_useful THEN 1 ELSE 0 END)::float / COUNT(*)::float AS useful_rate
                FROM user_article_feedback
                WHERE vendor = %s AND user_id = %s
                """,
                [feedback.vendor, user_id],
            ).fetchone()

            conn.commit()

        useful_rate = float(result[0]) if result and result[0] is not None else None

        return ArticleFeedbackResponse(
            status="success",
            message="Feedback saved successfully",
            vendor=feedback.vendor,
            updated_useful_rate=useful_rate,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save feedback: {exc!s}") from exc


@router.get("/article-feedback/{article_hash}")
async def get_article_feedback(
    article_hash: str,
    user_id: str = "default",
) -> dict[str, Any]:
    """Get user's feedback for a specific article.

    Args:
        article_hash: Content hash of the article
        user_id: User identifier (default: "default")

    Returns:
        dict with feedback data, or {"exists": false} if no feedback
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT vendor, is_useful, created_at
            FROM user_article_feedback
            WHERE user_id = %s AND article_hash = %s
            """,
            [user_id, article_hash],
        ).fetchone()

    if not result:
        return {"exists": False}

    return {
        "exists": True,
        "vendor": str(result[0]),
        "is_useful": bool(result[1]),
        "created_at": result[2].isoformat(),
    }


@router.post("/reset-source-metrics")
async def reset_source_metrics() -> dict[str, Any]:
    """Reset all source metrics and user feedback.

    WARNING: This deletes all profiling data and user feedback.
    Use only for testing or to start fresh.

    Returns:
        dict with deletion counts
    """
    try:
        task = reset_source_metrics_task.apply_async()

        return {
            "status": "accepted",
            "task_id": str(task.id),
            "message": "Reset task triggered. All metrics and feedback will be deleted.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to reset metrics: {exc!s}") from exc
