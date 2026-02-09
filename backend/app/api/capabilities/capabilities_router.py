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

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager

# analyze_capabilities removed - AI analysis migrated to [DEBT] subtasks on features
from ...tasks.capability_tasks import scan_system_capabilities
from ..types import DependenciesDict, HealthSummaryDict
from .database import (
    capability_from_row,
    get_table_name,
    insight_from_row,
    note_from_row,
    transform_db_capability,
)
from .models import CapabilitiesListResponse, CapabilityDetailResponse, ScanTriggerResponse

logger = get_logger(__name__)

router = APIRouter(prefix="")

# System tables that should NEVER be included in cleanup candidates
# These are infrastructure tables required for the system to function
SYSTEM_TABLES = {
    # Capabilities system (this feature!)
    "capability_insights",
    "capability_notes",
    "db_capabilities",
    "celery_capabilities",
    "api_capabilities",
    # Celery infrastructure
    "celery_taskmeta",
    "celery_tasksetmeta",
    # Migration tracking
    "schema_migrations",
    "alembic_version",
    # Infrastructure tables that may be empty but needed
    "source_credentials",
    "maintenance_log",
}


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
                    table = get_table_name(cap_type)
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
                    capabilities = [capability_from_row(row, columns) for row in rows]
                    # Transform db_capabilities to add age_hours field
                    capabilities = [transform_db_capability(cap) for cap in capabilities]
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

                table = get_table_name(type)
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
                count_result = conn.execute(count_query, count_params).fetchone()
                total = (
                    int(count_result[0]) if count_result and isinstance(count_result[0], int) else 0
                )

                # Execute main query
                result = conn.execute(query, params_list)
                columns = [desc[0] for desc in result.description] if result.description else []
                rows = result.fetchall()

                # Convert rows to dicts
                capabilities = [capability_from_row(row, columns) for row in rows]
                # Transform db_capabilities to add age_hours field
                capabilities = [transform_db_capability(cap) for cap in capabilities]

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
async def get_health_summary() -> HealthSummaryDict:
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
            summary: HealthSummaryDict = {
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
                # Type narrowing: ensure we have a string health_status and int count
                if isinstance(health_status_val, str) and isinstance(count, int):
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
                # Type narrowing: ensure we have a string health_status and int count
                if isinstance(health_status_val, str) and isinstance(count, int):
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
                # Type narrowing: ensure we have a string health_status and int count
                if isinstance(health_status_val, str) and isinstance(count, int):
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
        table = get_table_name(capability_type)

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

            capability = capability_from_row(row, columns)
            # Transform db_capability to add age_hours field
            capability = transform_db_capability(capability)

            # Get related insights
            insights_query = """
                SELECT * FROM capability_insights
                WHERE capability_type = %s AND capability_id = %s
                ORDER BY generated_at DESC
            """
            result = conn.execute(insights_query, [capability_type, capability_id])
            insight_columns = [desc[0] for desc in result.description] if result.description else []
            insight_rows = result.fetchall()
            insights = [insight_from_row(row, insight_columns) for row in insight_rows]

            # Get related notes
            notes_query = """
                SELECT * FROM capability_notes
                WHERE capability_type = %s AND capability_id = %s
                ORDER BY created_at DESC
            """
            result = conn.execute(notes_query, [capability_type, capability_id])
            note_columns = [desc[0] for desc in result.description] if result.description else []
            note_rows = result.fetchall()
            notes = [note_from_row(row, note_columns) for row in note_rows]

            # Extract dependencies from JSONB fields
            dependencies: DependenciesDict = {}
            if capability_type == "db":
                # No dependencies tracked for db_capabilities
                pass
            elif capability_type == "celery":
                populates_tables = capability.get("populates_tables", [])
                depends_on_tasks = capability.get("depends_on_tasks", [])
                if isinstance(populates_tables, list) and isinstance(depends_on_tasks, list):
                    dependencies["populates_tables"] = populates_tables
                    dependencies["depends_on_tasks"] = depends_on_tasks
            elif capability_type == "api":
                depends_on_tables = capability.get("depends_on_tables", [])
                if isinstance(depends_on_tables, list):
                    dependencies["depends_on_tables"] = depends_on_tables

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

    Enqueues the scan_system_capabilities task to run in the background.
    AI analysis has been migrated to [DEBT] subtasks on features.
    """
    try:
        # Trigger async scan task
        task = scan_system_capabilities()

        logger.info("capabilities_scan_triggered", task_id=task.id)

        return ScanTriggerResponse(
            task_id=task.id,
            status="queued",
            message=f"Capabilities scan queued with task ID: {task.id}",
        )

    except Exception as e:
        logger.error("scan_trigger_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger scan: {e}") from e


@router.get("/cleanup-candidates")
async def get_cleanup_candidates() -> dict[str, Any]:
    """Get all orphaned and legacy capabilities for cleanup review.

    Used by /scrub_it command to identify items that may be safe to remove.

    Returns capabilities grouped by type with health_status in ['orphaned', 'legacy'].
    Each item includes evidence of why it's a cleanup candidate.

    IMPORTANT: Items returned here have passed initial detection but still require
    verification before removal. The /scrub_it command performs additional checks.
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            candidates: dict[str, Any] = {
                "database": [],
                "celery": [],
                "api": [],
                "summary": {
                    "total_candidates": 0,
                    "by_status": {"orphaned": 0, "legacy": 0},
                },
            }

            # Query orphaned/legacy database tables (excluding system tables)
            # Build exclusion list for SQL
            system_tables_list = list(SYSTEM_TABLES)
            placeholders = ",".join(["%s"] * len(system_tables_list))

            db_query = f"""
                SELECT
                    id,
                    table_name,
                    category,
                    health_status,
                    row_count,
                    freshness_status,
                    days_since_update,
                    completeness_pct
                FROM db_capabilities
                WHERE health_status IN ('orphaned', 'legacy')
                    AND table_name NOT IN ({placeholders})
                ORDER BY health_status, table_name
            """
            result = conn.execute(db_query, tuple(system_tables_list))
            for row in result.fetchall():
                # Type annotations for row values
                row_id: Any = row[0]
                table_name: Any = row[1]
                category: Any = row[2]
                health_status: Any = row[3]
                row_count: Any = row[4]
                freshness_status: Any = row[5]
                days_since_update_raw: Any = row[6]
                completeness_pct: Any = row[7]

                # Build item with proper types
                evidence_list: list[str] = []
                days_since_update: float | None = (
                    float(days_since_update_raw) if days_since_update_raw else None
                )

                item: dict[str, Any] = {
                    "id": row_id,
                    "name": table_name,
                    "category": category,
                    "health_status": health_status,
                    "row_count": row_count,
                    "freshness_status": freshness_status,
                    "days_since_update": days_since_update,
                    "completeness_pct": completeness_pct,
                    "evidence": evidence_list,
                }

                # Build evidence list based on health status
                if health_status == "orphaned":
                    evidence_list.append("Marked as orphaned (no active usage detected)")
                if health_status == "legacy":
                    evidence_list.append("Marked as legacy (outdated or inactive)")
                if isinstance(row_count, int) and row_count == 0:
                    evidence_list.append("Table is empty (0 rows)")
                if isinstance(days_since_update, (int, float)) and days_since_update > 30:
                    evidence_list.append(f"No updates in {days_since_update:.0f} days")
                if isinstance(completeness_pct, (int, float)) and completeness_pct < 10:
                    evidence_list.append(f"Very low completeness ({completeness_pct}%)")

                candidates["database"].append(item)
                candidates["summary"]["total_candidates"] += 1
                if isinstance(health_status, str):
                    candidates["summary"]["by_status"][health_status] += 1

            # Query orphaned/legacy Celery tasks
            celery_query = """
                SELECT
                    id,
                    task_name,
                    category,
                    health_status,
                    schedule_description,
                    schedule_crontab,
                    schedule_interval_seconds,
                    success_rate_pct,
                    populates_tables
                FROM celery_capabilities
                WHERE health_status IN ('orphaned', 'legacy')
                ORDER BY health_status, task_name
            """
            result = conn.execute(celery_query)
            for row in result.fetchall():
                # Type annotations for row values
                task_id: Any = row[0]
                task_name: Any = row[1]
                task_category: Any = row[2]
                task_health_status: Any = row[3]
                schedule_desc: Any = row[4]
                schedule_crontab: Any = row[5]
                schedule_interval: Any = row[6]
                success_rate: Any = row[7]
                populates_tables_raw: Any = row[8]

                has_schedule = bool(schedule_crontab or schedule_interval)
                populates_tables_list = populates_tables_raw if populates_tables_raw else []
                evidence_list_celery: list[str] = []

                item_celery: dict[str, Any] = {
                    "id": task_id,
                    "name": task_name,
                    "category": task_category,
                    "health_status": task_health_status,
                    "schedule_description": schedule_desc,
                    "has_schedule": has_schedule,
                    "success_rate_pct": success_rate,
                    "populates_tables": populates_tables_list,
                    "evidence": evidence_list_celery,
                }

                if task_health_status == "orphaned":
                    evidence_list_celery.append("Marked as orphaned (no active usage detected)")
                if task_health_status == "legacy":
                    evidence_list_celery.append("Marked as legacy (outdated or inactive)")
                if not has_schedule:
                    evidence_list_celery.append("Not scheduled (no crontab/interval)")
                if not populates_tables_list:
                    evidence_list_celery.append("Does not populate any tables")
                if isinstance(success_rate, (int, float)) and success_rate < 50:
                    evidence_list_celery.append(f"Low success rate ({success_rate}%)")

                candidates["celery"].append(item_celery)
                candidates["summary"]["total_candidates"] += 1
                if isinstance(task_health_status, str):
                    candidates["summary"]["by_status"][task_health_status] += 1

            # Query orphaned/legacy API endpoints
            api_query = """
                SELECT
                    id,
                    endpoint_path,
                    category,
                    health_status,
                    http_method,
                    depends_on_tables
                FROM api_capabilities
                WHERE health_status IN ('orphaned', 'legacy')
                ORDER BY health_status, endpoint_path
            """
            result = conn.execute(api_query)
            for row in result.fetchall():
                # Type annotations for row values
                api_id: Any = row[0]
                endpoint_path: Any = row[1]
                api_category: Any = row[2]
                api_health_status: Any = row[3]
                http_method: Any = row[4]
                depends_on_tables_raw: Any = row[5]

                depends_on_tables_list = depends_on_tables_raw if depends_on_tables_raw else []
                evidence_list_api: list[str] = []

                item_api: dict[str, Any] = {
                    "id": api_id,
                    "name": endpoint_path,  # endpoint_path as name
                    "category": api_category,
                    "health_status": api_health_status,
                    "http_method": http_method,
                    "path": endpoint_path,  # endpoint_path
                    "depends_on_tables": depends_on_tables_list,
                    "evidence": evidence_list_api,
                }

                if api_health_status == "orphaned":
                    evidence_list_api.append("Marked as orphaned (no active usage detected)")
                if api_health_status == "legacy":
                    evidence_list_api.append("Marked as legacy (outdated or inactive)")
                if not depends_on_tables_list:
                    evidence_list_api.append("No table dependencies detected")

                candidates["api"].append(item_api)
                candidates["summary"]["total_candidates"] += 1
                if isinstance(api_health_status, str):
                    candidates["summary"]["by_status"][api_health_status] += 1

            logger.info(
                "cleanup_candidates_retrieved",
                total=candidates["summary"]["total_candidates"],
                database=len(candidates["database"]),
                celery=len(candidates["celery"]),
                api=len(candidates["api"]),
            )

            return candidates

    except Exception as e:
        logger.error("cleanup_candidates_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve cleanup candidates: {e}"
        ) from e
