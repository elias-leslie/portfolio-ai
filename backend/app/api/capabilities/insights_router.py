"""Insights router - capability insights CRUD endpoints.

This module provides REST API endpoints for capability insights:
- POST /insights - Create a new insight
- GET /insights - List insights (with filtering)
- GET /insights/{id} - Get single insight detail
- PATCH /insights/{id}/review - Update insight review status
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager
from .database import get_table_name, insight_from_row
from .models import (
    InsightCreateRequest,
    InsightCreateResponse,
    InsightReviewRequest,
    InsightsListResponse,
)

logger = get_logger(__name__)

router = APIRouter()


@router.post("/insights", response_model=InsightCreateResponse)
async def create_insight(insight: InsightCreateRequest) -> InsightCreateResponse:
    """Create a new capability insight.

    Body:
        - capability_type: Type of capability (db, celery, api)
        - capability_id: ID of the capability (optional)
        - table_name: Table name for quick reference (optional)
        - insight_type: Type of insight (see InsightCreateRequest for options)
        - severity: Severity level (low, medium, high, critical)
        - finding: Concise description of the finding
        - expected_behavior: What should happen (optional)
        - actual_behavior: What's actually happening (optional)
        - impact: Why this matters (optional)
        - suggested_fix: Specific action to take (optional)
        - reference_data: Related files, tables, etc. (optional)
        - ai_model: AI model that generated insight (optional)
        - ai_confidence: AI confidence 0.0-1.0 (optional)
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Validate capability exists if capability_id provided
            if insight.capability_id:
                table = get_table_name(insight.capability_type)
                check_query = f"SELECT id FROM {table} WHERE id = %s"
                result = conn.execute(check_query, [insight.capability_id]).fetchone()
                if not result:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Capability not found: {insight.capability_type}/{insight.capability_id}",
                    )

            # Insert insight
            insert_query = """
                INSERT INTO capability_insights (
                    capability_type, capability_id, table_name,
                    insight_type, severity, finding,
                    expected_behavior, actual_behavior, impact, suggested_fix,
                    reference_data, ai_model, ai_confidence,
                    status, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
                RETURNING id
            """
            insert_result = conn.execute(
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
            )
            insight_id_row = insert_result.fetchone()
            insight_id = int(insight_id_row[0]) if insight_id_row and insight_id_row[0] else 0
            conn.commit()

            logger.info(
                "insight_created",
                insight_id=insight_id,
                capability_type=insight.capability_type,
                capability_id=insight.capability_id,
                insight_type=insight.insight_type,
                severity=insight.severity,
            )

            return InsightCreateResponse(id=insight_id, message="Insight created successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("insight_create_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create insight: {e}") from e


@router.get("/insights", response_model=InsightsListResponse)
async def get_insights(
    capability_type: str | None = Query(None, description="Filter by capability type"),
    capability_id: int | None = Query(None, description="Filter by capability ID"),
    insight_type: str | None = Query(None, description="Filter by insight type"),
    severity: str | None = Query(None, description="Filter by severity"),
    status: str | None = Query(None, description="Filter by status (pending, confirmed, dismissed, fixed)"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> InsightsListResponse:
    """Get insights filtered by various criteria.

    Query params:
        - capability_type: Filter by capability type (db, celery, api)
        - capability_id: Filter by capability ID
        - insight_type: Filter by insight type
        - severity: Filter by severity (low, medium, high, critical)
        - status: Filter by status (pending, confirmed, dismissed, fixed)
        - limit: Max results (default 100, max 500)
        - offset: Offset for pagination
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Build WHERE clause
            where_clauses = []
            params: list[Any] = []

            if capability_type:
                where_clauses.append("capability_type = %s")
                params.append(capability_type)
            if capability_id is not None:
                where_clauses.append("capability_id = %s")
                params.append(capability_id)
            if insight_type:
                where_clauses.append("insight_type = %s")
                params.append(insight_type)
            if severity:
                where_clauses.append("severity = %s")
                params.append(severity)
            if status:
                where_clauses.append("status = %s")
                params.append(status)

            where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            # Get total count matching filter
            count_query = f"SELECT COUNT(*) FROM capability_insights {where_sql}"
            count_result = conn.execute(count_query, params).fetchone()
            total = int(count_result[0]) if count_result else 0

            # Get global counts for progress display
            pending_result = conn.execute(
                "SELECT COUNT(*) FROM capability_insights WHERE status = 'pending'"
            ).fetchone()
            pending_count = int(pending_result[0]) if pending_result else 0

            fixed_result = conn.execute(
                "SELECT COUNT(*) FROM capability_insights WHERE status = 'fixed'"
            ).fetchone()
            fixed_count = int(fixed_result[0]) if fixed_result else 0

            # Query insights with pagination
            query = f"""
                SELECT * FROM capability_insights
                {where_sql}
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                        ELSE 5
                    END,
                    created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])

            result_rows = conn.execute(query, params)
            columns = (
                [desc[0] for desc in result_rows.description] if result_rows.description else []
            )
            rows = result_rows.fetchall()
            insights = [insight_from_row(row, columns) for row in rows]

            logger.info(
                "insights_retrieved",
                capability_type=capability_type,
                insight_type=insight_type,
                severity=severity,
                status=status,
                count=len(insights),
                total=total,
            )

            return InsightsListResponse(
                total=total,
                pending_count=pending_count,
                fixed_count=fixed_count,
                insights=insights,
            )

    except Exception as e:
        logger.error("insights_list_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve insights: {e}") from e


@router.get("/insights/{insight_id}")
async def get_insight(insight_id: int) -> dict[str, Any]:
    """Get a single insight by ID.

    Path params:
        - insight_id: ID of the insight
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            query = "SELECT * FROM capability_insights WHERE id = %s"
            result_rows = conn.execute(query, [insight_id])
            columns = (
                [desc[0] for desc in result_rows.description] if result_rows.description else []
            )
            row = result_rows.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"Insight not found: {insight_id}")

            insight = insight_from_row(row, columns)
            return {"insight": insight}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("insight_get_error", insight_id=insight_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve insight: {e}") from e


@router.patch("/insights/{insight_id}/review")
async def review_insight(insight_id: int, review: InsightReviewRequest) -> dict[str, str]:
    """Update the review status of an insight.

    Path params:
        - insight_id: ID of the insight

    Body:
        - status: New review status (pending, confirmed, dismissed, fixed)
        - status_reason: Reason for status change (optional)
        - reviewed_by: Reviewer identifier (default "human")
    """
    conn_mgr = get_connection_manager()

    valid_statuses = ["pending", "confirmed", "dismissed", "fixed"]
    if review.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid review status: {review.status}. Must be one of {valid_statuses}",
        )

    try:
        with conn_mgr.connection() as conn:
            # Check insight exists
            check_query = "SELECT id FROM capability_insights WHERE id = %s"
            result = conn.execute(check_query, [insight_id]).fetchone()
            if not result:
                raise HTTPException(status_code=404, detail=f"Insight not found: {insight_id}")

            # Update status
            update_query = """
                UPDATE capability_insights
                SET status = %s,
                    status_reason = %s,
                    reviewed_by = %s,
                    reviewed_at = NOW()
                WHERE id = %s
            """
            conn.execute(
                update_query,
                [review.status, review.status_reason, review.reviewed_by, insight_id],
            )
            conn.commit()

            logger.info(
                "insight_reviewed",
                insight_id=insight_id,
                status=review.status,
                reviewed_by=review.reviewed_by,
            )

            return {"message": f"Insight {insight_id} updated to {review.status}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("insight_review_error", insight_id=insight_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to review insight: {e}") from e


@router.delete("/insights/{insight_id}")
async def delete_insight(insight_id: int) -> dict[str, str]:
    """Delete an insight by ID.

    Path params:
        - insight_id: ID of the insight
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Check insight exists
            check_query = "SELECT id FROM capability_insights WHERE id = %s"
            result = conn.execute(check_query, [insight_id]).fetchone()
            if not result:
                raise HTTPException(status_code=404, detail=f"Insight not found: {insight_id}")

            # Delete insight
            delete_query = "DELETE FROM capability_insights WHERE id = %s"
            conn.execute(delete_query, [insight_id])
            conn.commit()

            logger.info("insight_deleted", insight_id=insight_id)

            return {"message": f"Insight {insight_id} deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("insight_delete_error", insight_id=insight_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete insight: {e}") from e
