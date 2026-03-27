"""News source profiling and quality metrics API."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from functools import lru_cache
from typing import Any, TypedDict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.storage import get_storage
from app.tasks.news_profiling_tasks import profile_news_sources_task, reset_source_metrics_task

router = APIRouter(prefix="/api/news", tags=["news-profiling"])


class ResetSourceMetricsDict(TypedDict):
    """Response payload from reset-source-metrics endpoint."""

    status: str
    task_id: str
    message: str


@lru_cache(maxsize=1)
def _storage():
    return get_storage()


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


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_SOURCE_METRICS_COLUMNS = (
    "vendor, duplicate_rate, diversity_score, confidence_avg, freshness_score, "
    "user_useful_rate, quality_score, article_count, sample_period_start, calculated_at"
)


def _to_iso_str(value: Any) -> str:
    """Return ISO-format string for datetime values, str() for everything else."""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _row_to_source_metrics(row: Sequence[Any]) -> SourceMetricsResponse:
    """Convert a raw DB row (10 columns) into a SourceMetricsResponse."""
    vendor, dup, div, conf, fresh, useful, quality, count, period_start, calc_at = row

    # Coerce numeric columns to expected types
    if not isinstance(dup, (int, float)):
        dup = 0.0
    if not isinstance(div, (int, float)):
        div = 0.0
    if not isinstance(conf, (int, float)):
        conf = 0.0
    if not isinstance(fresh, (int, float)):
        fresh = 0.0
    if not isinstance(quality, (int, float)):
        quality = 0.0
    if not isinstance(count, int):
        count = 0
    if not isinstance(useful, (int, float)) and useful is not None:
        useful = None

    return SourceMetricsResponse(
        vendor=str(vendor),
        duplicate_rate=float(dup),
        diversity_score=float(div),
        confidence_avg=float(conf),
        freshness_score=float(fresh),
        user_useful_rate=float(useful) if useful is not None else None,
        quality_score=float(quality),
        article_count=int(count),
        sample_period_start=_to_iso_str(period_start),
        calculated_at=_to_iso_str(calc_at),
    )


def _insert_or_update_feedback(conn: Any, user_id: str, feedback: ArticleFeedbackRequest) -> None:
    """Upsert a user feedback row."""
    conn.execute(
        """
        INSERT INTO user_article_feedback (
            user_id, article_url, article_hash, vendor, is_useful, sentiment_override
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


def _fetch_vendor_useful_rate(conn: Any, vendor: str, user_id: str) -> float | None:
    """Return the fraction of useful articles for a vendor/user combination."""
    result = conn.execute(
        """
        SELECT SUM(CASE WHEN is_useful THEN 1 ELSE 0 END)::float / COUNT(*)::float AS useful_rate
        FROM user_article_feedback
        WHERE vendor = %s AND user_id = %s
        """,
        [vendor, user_id],
    ).fetchone()
    return float(result[0]) if result and result[0] is not None else None


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


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
        result = await run_in_threadpool(profile_news_sources_task, user_id)

        return ProfilingTaskResponse(
            status=str(result.get("status", "completed")),
            task_id=str(result.get("task_id")) if result.get("task_id") else None,
            message="Profiling task completed successfully."
            if result.get("status") != "error"
            else "Profiling task failed.",
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
    with _storage().connection() as conn:
        rows = conn.execute(
            f"""
            SELECT DISTINCT ON (vendor) {_SOURCE_METRICS_COLUMNS}
            FROM source_metrics
            ORDER BY vendor, calculated_at DESC
            """
        ).fetchall()

    metrics_list = [_row_to_source_metrics(row) for row in rows]
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
    with _storage().connection() as conn:
        row = conn.execute(
            f"""
            SELECT {_SOURCE_METRICS_COLUMNS}
            FROM source_metrics
            WHERE vendor = %s
            ORDER BY calculated_at DESC
            LIMIT 1
            """,
            [vendor],
        ).fetchone()

    return _row_to_source_metrics(row) if row else None


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
        with _storage().connection() as conn:
            _insert_or_update_feedback(conn, user_id, feedback)
            useful_rate = _fetch_vendor_useful_rate(conn, feedback.vendor, user_id)
            conn.commit()

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
    with _storage().connection() as conn:
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
        "created_at": _to_iso_str(result[2]),
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
        result = await run_in_threadpool(reset_source_metrics_task)

        response: ResetSourceMetricsDict = {
            "status": str(result.get("status", "completed")),
            "task_id": str(result.get("task_id", "")),
            "message": "Reset task completed. All metrics and feedback have been deleted."
            if result.get("status") != "error"
            else "Reset task failed.",
        }
        return response
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to reset metrics: {exc!s}") from exc
