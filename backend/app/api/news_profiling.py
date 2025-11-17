"""News source profiling and quality metrics API."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.storage import get_storage
from app.tasks.news_profiling_tasks import profile_news_sources_task, reset_source_metrics_task

from .types import ResetSourceMetricsDict

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
        vendor_val = row[0]
        duplicate_rate_val = row[1]
        diversity_score_val = row[2]
        confidence_avg_val = row[3]
        freshness_score_val = row[4]
        user_useful_rate_val = row[5]
        quality_score_val = row[6]
        article_count_val = row[7]
        sample_period_start_val = row[8]
        calculated_at_val = row[9]

        # Type narrowing for database values
        if not isinstance(duplicate_rate_val, (int, float)):
            duplicate_rate_val = 0.0
        if not isinstance(diversity_score_val, (int, float)):
            diversity_score_val = 0.0
        if not isinstance(confidence_avg_val, (int, float)):
            confidence_avg_val = 0.0
        if not isinstance(freshness_score_val, (int, float)):
            freshness_score_val = 0.0
        if not isinstance(quality_score_val, (int, float)):
            quality_score_val = 0.0
        if not isinstance(article_count_val, int):
            article_count_val = 0
        if not isinstance(user_useful_rate_val, (int, float)) and user_useful_rate_val is not None:
            user_useful_rate_val = None

        # Ensure datetime objects have isoformat
        if isinstance(sample_period_start_val, datetime):
            sample_period_start_str = sample_period_start_val.isoformat()
        else:
            sample_period_start_str = str(sample_period_start_val)

        if isinstance(calculated_at_val, datetime):
            calculated_at_str = calculated_at_val.isoformat()
        else:
            calculated_at_str = str(calculated_at_val)

        metrics_list.append(
            SourceMetricsResponse(
                vendor=str(vendor_val),
                duplicate_rate=float(duplicate_rate_val),
                diversity_score=float(diversity_score_val),
                confidence_avg=float(confidence_avg_val),
                freshness_score=float(freshness_score_val),
                user_useful_rate=float(user_useful_rate_val)
                if user_useful_rate_val is not None
                else None,
                quality_score=float(quality_score_val),
                article_count=int(article_count_val),
                sample_period_start=sample_period_start_str,
                calculated_at=calculated_at_str,
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

    # Type narrowing for database result
    vendor_val = result[0]
    duplicate_rate_val = result[1]
    diversity_score_val = result[2]
    confidence_avg_val = result[3]
    freshness_score_val = result[4]
    user_useful_rate_val = result[5]
    quality_score_val = result[6]
    article_count_val = result[7]
    sample_period_start_val = result[8]
    calculated_at_val = result[9]

    # Ensure numeric types
    if not isinstance(duplicate_rate_val, (int, float)):
        duplicate_rate_val = 0.0
    if not isinstance(diversity_score_val, (int, float)):
        diversity_score_val = 0.0
    if not isinstance(confidence_avg_val, (int, float)):
        confidence_avg_val = 0.0
    if not isinstance(freshness_score_val, (int, float)):
        freshness_score_val = 0.0
    if not isinstance(quality_score_val, (int, float)):
        quality_score_val = 0.0
    if not isinstance(article_count_val, int):
        article_count_val = 0
    if not isinstance(user_useful_rate_val, (int, float)) and user_useful_rate_val is not None:
        user_useful_rate_val = None

    # Ensure datetime objects have isoformat
    if isinstance(sample_period_start_val, datetime):
        sample_period_start_str = sample_period_start_val.isoformat()
    else:
        sample_period_start_str = str(sample_period_start_val)

    if isinstance(calculated_at_val, datetime):
        calculated_at_str = calculated_at_val.isoformat()
    else:
        calculated_at_str = str(calculated_at_val)

    return SourceMetricsResponse(
        vendor=str(vendor_val),
        duplicate_rate=float(duplicate_rate_val),
        diversity_score=float(diversity_score_val),
        confidence_avg=float(confidence_avg_val),
        freshness_score=float(freshness_score_val),
        user_useful_rate=float(user_useful_rate_val) if user_useful_rate_val is not None else None,
        quality_score=float(quality_score_val),
        article_count=int(article_count_val),
        sample_period_start=sample_period_start_str,
        calculated_at=calculated_at_str,
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
) -> dict[str, bool | str]:
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

    # Type narrowing for database result
    vendor_val = result[0]
    is_useful_val = result[1]
    created_at_val = result[2]

    # Ensure datetime object has isoformat
    if isinstance(created_at_val, datetime):
        created_at_str = created_at_val.isoformat()
    else:
        created_at_str = str(created_at_val)

    return {
        "exists": True,
        "vendor": str(vendor_val),
        "is_useful": bool(is_useful_val),
        "created_at": created_at_str,
    }


@router.post("/reset-source-metrics")
async def reset_source_metrics() -> ResetSourceMetricsDict:
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
