"""System Capabilities API endpoints.

This module provides REST API endpoints to expose system capability data:
- Database table capabilities (db_capabilities)
- Celery task capabilities (celery_capabilities)
- API endpoint capabilities (api_capabilities)
- AI-generated insights (capability_insights)
- Human annotations (capability_notes)
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager
from ..tasks.capability_tasks import scan_system_capabilities

logger = get_logger(__name__)

router = APIRouter(prefix="/api/capabilities", tags=["capabilities"])


# Request/Response Models
class InsightReviewRequest(BaseModel):
    """Request to review/update an insight status."""

    status: Literal["confirmed", "dismissed", "in_progress", "fixed"]
    status_reason: str = ""
    reviewed_by: str = "human"


class NoteCreateRequest(BaseModel):
    """Request to create a new capability note."""

    capability_type: Literal["db", "celery", "api"]
    capability_id: int | None = None
    insight_id: int | None = None
    note_type: Literal["observation", "recommendation", "question", "decision", "reference"]
    note: str


class ScanTriggerResponse(BaseModel):
    """Response for manual scan trigger."""

    task_id: str
    status: str = "queued"
    message: str


class CapabilitiesListResponse(BaseModel):
    """Response for paginated capabilities list."""

    total: int
    capabilities: list[dict[str, Any]]


class CapabilityDetailResponse(BaseModel):
    """Response for single capability with related data."""

    capability: dict[str, Any]
    insights: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: dict[str, Any] = Field(default_factory=dict)


class InsightsListResponse(BaseModel):
    """Response for paginated insights list."""

    total: int
    insights: list[dict[str, Any]]


class NotesListResponse(BaseModel):
    """Response for notes list."""

    notes: list[dict[str, Any]]


class NoteCreateResponse(BaseModel):
    """Response for note creation."""

    id: int
    message: str


# Helper functions
def _dict_from_row(row: tuple[Any, ...], columns: list[str]) -> dict[str, Any]:
    """Convert database row tuple to dict."""
    return dict(zip(columns, row, strict=True))


def _transform_db_capability(cap: dict[str, Any]) -> dict[str, Any]:
    """Transform db_capability to add computed fields expected by frontend.

    Adds age_hours field by converting days_since_update to hours.
    Frontend expects age_hours (number | null) but DB stores days_since_update (integer | null).
    """
    if cap.get("capability_type") == "db":
        # Convert days_since_update to age_hours for frontend compatibility
        days = cap.get("days_since_update")
        cap["age_hours"] = days * 24 if days is not None else None

        # Add missing fields with defaults if needed
        cap.setdefault("source", None)
        cap.setdefault("description", "")

    return cap


def _get_table_name(capability_type: str) -> str:
    """Get database table name for capability type."""
    mapping = {
        "db": "db_capabilities",
        "celery": "celery_capabilities",
        "api": "api_capabilities",
    }
    if capability_type not in mapping:
        raise ValueError(f"Invalid capability type: {capability_type}")
    return mapping[capability_type]


# Endpoints
@router.get("", response_model=CapabilitiesListResponse)
async def get_capabilities(
    type: str = Query("all", description="Filter by type: db, celery, api, or all"),
    category: str | None = Query(None, description="Filter by category"),
    status: str | None = Query(None, description="Filter by status (db only)"),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results offset"),
) -> CapabilitiesListResponse:
    """Get paginated list of system capabilities.

    Returns capabilities from one or all capability tables with join counts
    for insights and notes.

    Query params:
        - type: Filter by capability type (db|celery|api|all)
        - category: Filter by category
        - status: Filter by status (freshness_status for db_capabilities)
        - limit: Results per page (default 50, max 200)
        - offset: Results offset for pagination
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Build queries based on type
            if type == "all":
                # Query all three tables separately and combine results
                all_capabilities = []
                total = 0

                for cap_type in ["db", "celery", "api"]:
                    table = _get_table_name(cap_type)
                    query_params: list[Any] = [cap_type, cap_type]

                    query = f"""
                        SELECT
                            '{cap_type}' as capability_type,
                            c.*,
                            COALESCE(insights.count, 0) as insights_count,
                            COALESCE(notes.count, 0) as notes_count
                        FROM {table} c
                        LEFT JOIN (
                            SELECT capability_id, COUNT(*) as count
                            FROM capability_insights
                            WHERE capability_type = %s
                            GROUP BY capability_id
                        ) insights ON c.id = insights.capability_id
                        LEFT JOIN (
                            SELECT capability_id, COUNT(*) as count
                            FROM capability_notes
                            WHERE capability_type = %s
                            GROUP BY capability_id
                        ) notes ON c.id = notes.capability_id
                    """

                    where_clauses = []
                    if category:
                        where_clauses.append("c.category = %s")
                        query_params.append(category)

                    if where_clauses:
                        query += " WHERE " + " AND ".join(where_clauses)

                    query += " ORDER BY c.id"

                    # Execute query
                    result = conn.execute(query, query_params)
                    columns = [desc[0] for desc in result.description] if result.description else []
                    rows = result.fetchall()

                    # Convert to dicts and add to combined list
                    capabilities = [_dict_from_row(row, columns) for row in rows]
                    # Transform db_capabilities to add age_hours field
                    capabilities = [_transform_db_capability(cap) for cap in capabilities]
                    all_capabilities.extend(capabilities)
                    total += len(capabilities)

                # Apply pagination to combined results
                capabilities = all_capabilities[offset : offset + limit]
                rows = []  # Set empty for later check
                columns = []  # Set empty for later check

            else:
                # Single table query
                if type not in ["db", "celery", "api"]:
                    raise HTTPException(status_code=400, detail=f"Invalid type: {type}")

                table = _get_table_name(type)
                params_list: list[Any] = [type, type]

                query = f"""
                    SELECT
                        '{type}' as capability_type,
                        c.*,
                        COALESCE(insights.count, 0) as insights_count,
                        COALESCE(notes.count, 0) as notes_count
                    FROM {table} c
                    LEFT JOIN (
                        SELECT capability_id, COUNT(*) as count
                        FROM capability_insights
                        WHERE capability_type = %s
                        GROUP BY capability_id
                    ) insights ON c.id = insights.capability_id
                    LEFT JOIN (
                        SELECT capability_id, COUNT(*) as count
                        FROM capability_notes
                        WHERE capability_type = %s
                        GROUP BY capability_id
                    ) notes ON c.id = notes.capability_id
                """

                where_clauses = []
                if category:
                    where_clauses.append("c.category = %s")
                    params_list.append(category)
                if status and type == "db":
                    where_clauses.append("c.freshness_status = %s")
                    params_list.append(status)

                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)

                query += " ORDER BY c.id LIMIT %s OFFSET %s"
                params_list.extend([limit, offset])

                # Count query
                count_query = f"SELECT COUNT(*) FROM {table} c"
                count_params = []
                if where_clauses:
                    count_query += " WHERE " + " AND ".join(where_clauses)
                    count_params = params_list[2:-2]  # Skip type params and limit/offset

                # Execute count
                result = conn.execute(count_query, count_params).fetchone()
                total = result[0] if result else 0

                # Execute main query
                result = conn.execute(query, params_list)
                columns = [desc[0] for desc in result.description] if result.description else []
                rows = result.fetchall()

                # Convert rows to dicts
                capabilities = [_dict_from_row(row, columns) for row in rows]
                # Transform db_capabilities to add age_hours field
                capabilities = [_transform_db_capability(cap) for cap in capabilities]

            logger.info(
                "capabilities_list_retrieved",
                type=type,
                category=category,
                status=status,
                total=total,
                returned=len(capabilities),
                limit=limit,
                offset=offset,
            )

            return CapabilitiesListResponse(total=total, capabilities=capabilities)

    except Exception as e:
        logger.error("capabilities_list_error", error=str(e), type=type)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve capabilities: {e}") from e


@router.get("/{capability_type}/{capability_id}", response_model=CapabilityDetailResponse)
async def get_capability_detail(
    capability_type: Literal["db", "celery", "api"],
    capability_id: int,
) -> CapabilityDetailResponse:
    """Get detailed view of a single capability with related insights, notes, and dependencies.

    Path params:
        - capability_type: Type of capability (db|celery|api)
        - capability_id: Unique ID of the capability

    Returns:
        - capability: Full capability record
        - insights: All related insights
        - notes: All related notes
        - dependencies: Extracted from JSONB fields (populates_tables, depends_on_tables, etc.)
    """
    conn_mgr = get_connection_manager()

    try:
        table = _get_table_name(capability_type)

        with conn_mgr.connection() as conn:
            # Get main capability record
            query = f"SELECT * FROM {table} WHERE id = %s"
            result = conn.execute(query, [capability_id])
            columns = [desc[0] for desc in result.description] if result.description else []
            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Capability not found: {capability_type}/{capability_id}",
                )

            capability = _dict_from_row(row, columns)
            # Transform db_capability to add age_hours field
            capability = _transform_db_capability(capability)

            # Get related insights
            insights_query = """
                SELECT * FROM capability_insights
                WHERE capability_type = %s AND capability_id = %s
                ORDER BY generated_at DESC
            """
            result = conn.execute(insights_query, [capability_type, capability_id])
            insight_columns = [desc[0] for desc in result.description] if result.description else []
            insight_rows = result.fetchall()
            insights = [_dict_from_row(row, insight_columns) for row in insight_rows]

            # Get related notes
            notes_query = """
                SELECT * FROM capability_notes
                WHERE capability_type = %s AND capability_id = %s
                ORDER BY created_at DESC
            """
            result = conn.execute(notes_query, [capability_type, capability_id])
            note_columns = [desc[0] for desc in result.description] if result.description else []
            note_rows = result.fetchall()
            notes = [_dict_from_row(row, note_columns) for row in note_rows]

            # Extract dependencies from JSONB fields
            dependencies: dict[str, Any] = {}
            if capability_type == "db":
                # No dependencies tracked for db_capabilities
                pass
            elif capability_type == "celery":
                dependencies["populates_tables"] = capability.get("populates_tables", [])
                dependencies["depends_on_tasks"] = capability.get("depends_on_tasks", [])
            elif capability_type == "api":
                dependencies["depends_on_tables"] = capability.get("depends_on_tables", [])

            logger.info(
                "capability_detail_retrieved",
                capability_type=capability_type,
                capability_id=capability_id,
                insights_count=len(insights),
                notes_count=len(notes),
            )

            return CapabilityDetailResponse(
                capability=capability,
                insights=insights,
                notes=notes,
                dependencies=dependencies,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "capability_detail_error",
            error=str(e),
            capability_type=capability_type,
            capability_id=capability_id,
        )
        raise HTTPException(status_code=500, detail=f"Failed to retrieve capability: {e}") from e


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
) -> dict[str, Any]:
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


@router.post("/notes", response_model=NoteCreateResponse)
async def create_note(note: NoteCreateRequest) -> NoteCreateResponse:
    """Create a new capability note.

    Body:
        - capability_type: Type of capability (db, celery, api)
        - capability_id: ID of the capability (optional)
        - insight_id: ID of related insight (optional)
        - note_type: Type of note (observation, recommendation, question, decision, reference)
        - note: Note content
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Validate capability exists if capability_id provided
            if note.capability_id:
                table = _get_table_name(note.capability_type)
                check_query = f"SELECT id FROM {table} WHERE id = %s"
                result = conn.execute(check_query, [note.capability_id]).fetchone()
                if not result:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Capability not found: {note.capability_type}/{note.capability_id}",
                    )

            # Validate insight exists if insight_id provided
            if note.insight_id:
                check_query = "SELECT id FROM capability_insights WHERE id = %s"
                result = conn.execute(check_query, [note.insight_id]).fetchone()
                if not result:
                    raise HTTPException(
                        status_code=404, detail=f"Insight not found: {note.insight_id}"
                    )

            # Insert note
            insert_query = """
                INSERT INTO capability_notes
                    (capability_type, capability_id, insight_id, note_type, note, created_by)
                VALUES (%s, %s, %s, %s, %s, 'human')
                RETURNING id
            """
            result = conn.execute(
                insert_query,
                [
                    note.capability_type,
                    note.capability_id,
                    note.insight_id,
                    note.note_type,
                    note.note,
                ],
            )
            note_id = result.fetchone()[0]
            conn.commit()

            logger.info(
                "note_created",
                note_id=note_id,
                capability_type=note.capability_type,
                capability_id=note.capability_id,
                insight_id=note.insight_id,
                note_type=note.note_type,
            )

            return NoteCreateResponse(id=note_id, message=f"Note {note_id} created successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("note_create_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create note: {e}") from e


@router.get("/notes", response_model=NotesListResponse)
async def get_notes(
    capability_type: str | None = Query(None, description="Filter by capability type"),
    capability_id: int | None = Query(None, description="Filter by capability ID"),
    insight_id: int | None = Query(None, description="Filter by insight ID"),
) -> NotesListResponse:
    """Get notes filtered by capability or insight.

    Query params:
        - capability_type: Filter by capability type (db, celery, api)
        - capability_id: Filter by capability ID
        - insight_id: Filter by insight ID
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
            if insight_id is not None:
                where_clauses.append("insight_id = %s")
                params.append(insight_id)

            where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            # Query notes
            query = f"""
                SELECT * FROM capability_notes
                {where_sql}
                ORDER BY created_at DESC
            """

            result = conn.execute(query, params)
            columns = [desc[0] for desc in result.description] if result.description else []
            rows = result.fetchall()
            notes = [_dict_from_row(row, columns) for row in rows]

            logger.info(
                "notes_retrieved",
                capability_type=capability_type,
                capability_id=capability_id,
                insight_id=insight_id,
                count=len(notes),
            )

            return NotesListResponse(notes=notes)

    except Exception as e:
        logger.error("notes_list_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve notes: {e}") from e


@router.post("/scan", response_model=ScanTriggerResponse)
async def trigger_scan() -> ScanTriggerResponse:
    """Trigger a manual system capabilities scan.

    Enqueues the scan_system_capabilities Celery task and returns the task ID.
    The scan will run asynchronously in the background.
    """
    try:
        # Trigger async task
        task = scan_system_capabilities.delay()

        logger.info("capabilities_scan_triggered", task_id=task.id)

        return ScanTriggerResponse(
            task_id=task.id,
            status="queued",
            message=f"Capabilities scan queued with task ID: {task.id}",
        )

    except Exception as e:
        logger.error("scan_trigger_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger scan: {e}") from e
