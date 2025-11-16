"""Capabilities router - main capabilities endpoints.

This module provides REST API endpoints for core system capability data:
- GET / - List all capabilities (with filtering/pagination)
- GET /health/summary - Health status summary across all capability types
- GET /{type}/{id} - Get detailed capability view with insights/notes
- POST /scan - Trigger manual capabilities scan
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager
from ...tasks.capability_tasks import scan_system_capabilities

logger = get_logger(__name__)

router = APIRouter()


# Request/Response Models
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
@router.get("/", response_model=CapabilitiesListResponse)
async def get_capabilities(
    type: str = Query("all", description="Filter by type: db, celery, api, or all"),
    category: str | None = Query(None, description="Filter by category"),
    status: str | None = Query(None, description="Filter by status (db only)"),
    health_status: str | None = Query(
        None, description="Filter by health: active, orphaned, legacy, suspect"
    ),
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
        - health_status: Filter by health (active|orphaned|legacy|suspect)
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
                    if health_status:
                        where_clauses.append("c.health_status = %s")
                        query_params.append(health_status)

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
                if health_status:
                    where_clauses.append("c.health_status = %s")
                    params_list.append(health_status)

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
                health_status=health_status,
                total=total,
                returned=len(capabilities),
                limit=limit,
                offset=offset,
            )

            return CapabilitiesListResponse(total=total, capabilities=capabilities)

    except Exception as e:
        logger.error("capabilities_list_error", error=str(e), type=type)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve capabilities: {e}") from e


@router.get("/health/summary")
async def get_health_summary() -> dict[str, Any]:
    """Get health status summary across all capability types.

    Returns counts of capabilities grouped by type and health status.

    Example response:
    {
        "total": 71,
        "by_type": {
            "database": {"active": 35, "orphaned": 3, "legacy": 2, "suspect": 2},
            "celery": {"active": 11, "orphaned": 1, "legacy": 0, "suspect": 1},
            "api": {"active": 14, "orphaned": 1, "legacy": 0, "suspect": 1}
        },
        "by_status": {
            "active": 60,
            "orphaned": 5,
            "legacy": 2,
            "suspect": 4
        }
    }
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Query health counts from all three tables
            summary: dict[str, Any] = {
                "total": 0,
                "by_type": {
                    "database": {"active": 0, "orphaned": 0, "legacy": 0, "suspect": 0},
                    "celery": {"active": 0, "orphaned": 0, "legacy": 0, "suspect": 0},
                    "api": {"active": 0, "orphaned": 0, "legacy": 0, "suspect": 0},
                },
                "by_status": {"active": 0, "orphaned": 0, "legacy": 0, "suspect": 0},
            }

            # Query db_capabilities
            db_query = """
                SELECT health_status, COUNT(*) as count
                FROM db_capabilities
                WHERE health_status IS NOT NULL
                GROUP BY health_status
            """
            result = conn.execute(db_query)
            for row in result.fetchall():
                health_status_val, count = row
                summary["by_type"]["database"][health_status_val] = count
                summary["by_status"][health_status_val] += count
                summary["total"] += count

            # Query celery_capabilities
            celery_query = """
                SELECT health_status, COUNT(*) as count
                FROM celery_capabilities
                WHERE health_status IS NOT NULL
                GROUP BY health_status
            """
            result = conn.execute(celery_query)
            for row in result.fetchall():
                health_status_val, count = row
                summary["by_type"]["celery"][health_status_val] = count
                summary["by_status"][health_status_val] += count
                summary["total"] += count

            # Query api_capabilities
            api_query = """
                SELECT health_status, COUNT(*) as count
                FROM api_capabilities
                WHERE health_status IS NOT NULL
                GROUP BY health_status
            """
            result = conn.execute(api_query)
            for row in result.fetchall():
                health_status_val, count = row
                summary["by_type"]["api"][health_status_val] = count
                summary["by_status"][health_status_val] += count
                summary["total"] += count

            logger.info(
                "health_summary_retrieved",
                total=summary["total"],
                active=summary["by_status"]["active"],
                orphaned=summary["by_status"]["orphaned"],
                legacy=summary["by_status"]["legacy"],
                suspect=summary["by_status"]["suspect"],
            )

            return summary

    except Exception as e:
        logger.error("health_summary_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve health summary: {e}"
        ) from e


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
