"""Insights router - capability insights endpoints.

This module provides REST API endpoints for capability insights:
- GET /insights - List all insights (with filtering/pagination)
- POST /insights/{id}/review - Review/update insight status
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager
from ..types import InsightDict

logger = get_logger(__name__)

router = APIRouter()


# Request/Response Models
class InsightReviewRequest(BaseModel):
    """Request to review/update an insight status."""

    status: Literal["confirmed", "dismissed", "in_progress", "fixed"]
    status_reason: str = ""
    reviewed_by: str = "human"


class InsightsListResponse(BaseModel):
    """Response for paginated insights list."""

    total: int
    insights: list[InsightDict]


# Helper functions
def _dict_from_row(row: tuple[Any, ...], columns: list[str]) -> InsightDict:
    """Convert database row tuple to dict."""
    result: InsightDict = {}
    for key, value in zip(columns, row, strict=True):
        result[key] = value  # type: ignore
    return result


# Endpoints
@router.get("/insights", response_model=InsightsListResponse)
async def get_insights(
    status: str | None = Query(None, description="Filter by status"),
    severity: str | None = Query(None, description="Filter by severity"),
    type: str | None = Query(None, description="Filter by insight_type"),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results offset"),
) -> InsightsListResponse:
    """Get paginated list of capability insights with related capability info.

    Query params:
        - status: Filter by status (pending, confirmed, dismissed, in_progress, fixed)
        - severity: Filter by severity (low, medium, high, critical)
        - type: Filter by insight_type
        - limit: Results per page (default 50, max 200)
        - offset: Results offset for pagination
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Build WHERE clause
            where_clauses = []
            params: list[Any] = []

            if status:
                where_clauses.append("i.status = %s")
                params.append(status)
            if severity:
                where_clauses.append("i.severity = %s")
                params.append(severity)
            if type:
                where_clauses.append("i.insight_type = %s")
                params.append(type)

            where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            # Count query
            count_query = f"SELECT COUNT(*) FROM capability_insights i{where_sql}"
            result = conn.execute(count_query, params).fetchone()
            total = result[0] if result else 0

            # Main query with capability info
            query = f"""
                SELECT
                    i.*,
                    i.table_name as related_table
                FROM capability_insights i
                {where_sql}
                ORDER BY i.generated_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])

            result = conn.execute(query, params)
            columns = [desc[0] for desc in result.description] if result.description else []
            rows = result.fetchall()
            insights = [_dict_from_row(row, columns) for row in rows]

            logger.info(
                "insights_list_retrieved",
                status=status,
                severity=severity,
                type=type,
                total=total,
                returned=len(insights),
            )

            return InsightsListResponse(total=total, insights=insights)

    except Exception as e:
        logger.error("insights_list_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve insights: {e}") from e


@router.post("/insights/{insight_id}/review")
async def review_insight(
    insight_id: int,
    review: InsightReviewRequest,
) -> dict[str, str | int]:
    """Update the review status of an insight.

    Path params:
        - insight_id: ID of the insight to review

    Body:
        - status: New status (confirmed, dismissed, in_progress, fixed)
        - status_reason: Reason for status change
        - reviewed_by: Reviewer identifier (default: "human")
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Check if insight exists
            check_query = "SELECT id FROM capability_insights WHERE id = %s"
            result = conn.execute(check_query, [insight_id]).fetchone()

            if not result:
                raise HTTPException(status_code=404, detail=f"Insight not found: {insight_id}")

            # Update insight
            update_query = """
                UPDATE capability_insights
                SET
                    status = %s,
                    status_reason = %s,
                    reviewed_by = %s,
                    reviewed_at = NOW(),
                    fixed_at = CASE WHEN %s = 'fixed' THEN NOW() ELSE fixed_at END,
                    updated_at = NOW()
                WHERE id = %s
            """
            conn.execute(
                update_query,
                [
                    review.status,
                    review.status_reason,
                    review.reviewed_by,
                    review.status,
                    insight_id,
                ],
            )
            conn.commit()

            logger.info(
                "insight_reviewed",
                insight_id=insight_id,
                status=review.status,
                reviewed_by=review.reviewed_by,
            )

            return {
                "id": insight_id,
                "status": review.status,
                "reviewed_by": review.reviewed_by,
                "message": f"Insight {insight_id} updated to {review.status}",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("insight_review_error", error=str(e), insight_id=insight_id)
        raise HTTPException(status_code=500, detail=f"Failed to review insight: {e}") from e
