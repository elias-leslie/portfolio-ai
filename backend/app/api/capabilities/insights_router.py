"""Insights router - capability insights endpoints.

This module provides REST API endpoints for capability insights:
- GET /insights - List all insights (with filtering/pagination)
- POST /insights/{id}/review - Review/update insight status
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager
from .database import insight_from_row
from .models import (
    InsightCreateRequest,
    InsightCreateResponse,
    InsightReviewRequest,
    InsightsListResponse,
)

logger = get_logger(__name__)

router = APIRouter()


# Endpoints
@router.post("/insights", response_model=InsightCreateResponse)
async def create_insight(insight: InsightCreateRequest) -> InsightCreateResponse:
    """Create a new capability insight.

    Used by /scrub_it and other tools to record findings about capabilities
    that need attention (broken dependencies, missing data, etc.).

    Body:
        - capability_type: db, celery, or api
        - capability_id: ID of the related capability (optional)
        - table_name: Table name for quick reference (optional)
        - insight_type: broken_dependency, missing_data, data_quality, etc.
        - severity: low, medium, high, critical
        - finding: Concise description of the issue
        - expected_behavior: What should happen (optional)
        - actual_behavior: What's actually happening (optional)
        - impact: Why this matters (optional)
        - suggested_fix: Specific action to take (optional)
        - reference_data: Related files, tables, URLs (optional)
        - ai_model: AI model that generated this insight (optional)
        - ai_confidence: Confidence level 0.0-1.0 (optional)
    """
    import json

    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Validate capability exists if capability_id provided
            if insight.capability_id is not None:
                table_map = {
                    "db": "db_capabilities",
                    "celery": "celery_capabilities",
                    "api": "api_capabilities",
                }
                cap_table = table_map.get(insight.capability_type)
                if cap_table:
                    check_query = f"SELECT id FROM {cap_table} WHERE id = %s"
                    result = conn.execute(check_query, [insight.capability_id]).fetchone()
                    if not result:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Capability not found: {insight.capability_type}/{insight.capability_id}",
                        )

            # Insert insight
            insert_query = """
                INSERT INTO capability_insights (
                    capability_type,
                    capability_id,
                    table_name,
                    insight_type,
                    severity,
                    finding,
                    expected_behavior,
                    actual_behavior,
                    impact,
                    suggested_fix,
                    reference_data,
                    ai_model,
                    ai_confidence,
                    status,
                    generated_at,
                    created_at,
                    updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'pending', NOW(), NOW(), NOW()
                )
                RETURNING id
            """
            result = conn.execute(
                insert_query,
                [
                    insight.capability_type,
                    insight.capability_id,
                    insight.table_name,
                    insight.insight_type,
                    insight.severity,
                    insight.finding,
                    insight.expected_behavior,
                    insight.actual_behavior,
                    insight.impact,
                    insight.suggested_fix,
                    json.dumps(insight.reference_data) if insight.reference_data else None,
                    insight.ai_model,
                    insight.ai_confidence,
                ],
            ).fetchone()
            conn.commit()

            if not result or result[0] is None:
                raise HTTPException(
                    status_code=500, detail="Failed to create insight: no ID returned"
                )

            insight_id = int(result[0])

            logger.info(
                "insight_created",
                insight_id=insight_id,
                capability_type=insight.capability_type,
                capability_id=insight.capability_id,
                insight_type=insight.insight_type,
                severity=insight.severity,
            )

            return InsightCreateResponse(
                id=insight_id,
                message=f"Insight created successfully with ID {insight_id}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("insight_create_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create insight: {e}") from e


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
            count_result = conn.execute(count_query, params).fetchone()
            total: int = int(count_result[0]) if count_result and count_result[0] else 0

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

            result_rows = conn.execute(query, params)
            rows = result_rows.fetchall()
            columns = (
                [desc[0] for desc in result_rows.description] if result_rows.description else []
            )
            insights = [insight_from_row(row, columns) for row in rows]

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
