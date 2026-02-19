"""Workflow Graph API - React Flow visualization for scheduled tasks.

This module transforms task capabilities data into React Flow compatible
graph format for workflow visualization.

Phase 1.5 adds intelligent dependency inference from table relationships.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..logging_config import get_logger
from ..services.hatchet_inspector import get_unified_task_list
from ..storage.connection import get_connection_manager
from .workflow_graph_helpers import (
    _infer_dependencies,
    build_explicit_edges,
    build_inferred_edges,
    build_node,
    parse_row_to_task_data,
)
from .workflow_graph_models import (
    DependencyOverrideRequest,
    DependencyOverrideResponse,
    NodeData,
    WorkflowEdge,
    WorkflowGraphResponse,
    WorkflowNode,
)

# Re-export models so existing importers can still reach them from this module
__all__ = [
    "DependencyOverrideRequest",
    "DependencyOverrideResponse",
    "NodeData",
    "WorkflowEdge",
    "WorkflowGraphResponse",
    "WorkflowNode",
    "router",
]

logger = get_logger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

_CAPABILITIES_QUERY = """
    SELECT
        task_name,
        category,
        depends_on_tasks,
        populates_tables,
        last_run_at,
        next_run_at,
        success_rate_pct,
        avg_duration_ms,
        schedule_crontab,
        schedule_description,
        reads_from_tables,
        dependency_overrides,
        schedule_interval_seconds
    FROM celery_capabilities
    WHERE 1=1
"""


def _get_live_task_status() -> tuple[dict[str, str], set[str]]:
    """Fetch live task statuses from Hatchet; returns (active_tasks, pending_tasks)."""
    active_tasks: dict[str, str] = {}
    pending_tasks: set[str] = set()
    try:
        unified_tasks = get_unified_task_list(status="all", limit=100)
        for task in unified_tasks:
            live_task_name = task.get("name", "")
            status = task.get("status", "").upper()
            if status == "ACTIVE":
                active_tasks[live_task_name] = "running"
            elif status == "PENDING":
                pending_tasks.add(live_task_name)
    except Exception as e:
        logger.warning("failed_to_get_live_tasks", error=str(e))
    return active_tasks, pending_tasks


def _build_query_and_params(
    include_inactive: bool,
    category_filter: set[str] | None,
) -> tuple[str, list[Any]]:
    """Build the SQL query and parameter list based on filters."""
    query = _CAPABILITIES_QUERY
    params: list[Any] = []
    if not include_inactive:
        query += " AND (success_rate_pct > 0 OR last_run_at IS NOT NULL)"
    if category_filter:
        query += " AND LOWER(category) = ANY(%s)"
        params.append(list(category_filter))
    query += " ORDER BY category, task_name"
    return query, params


def _process_rows(
    rows: list[Any],
    active_tasks: dict[str, str],
    pending_tasks: set[str],
) -> tuple[list[WorkflowNode], list[WorkflowEdge], list[dict[str, Any]], set[str], set[str]]:
    """Process DB rows into nodes, explicit edges, task data, IDs, and categories."""
    nodes: list[WorkflowNode] = []
    edges: list[WorkflowEdge] = []
    tasks_data: list[dict[str, Any]] = []
    task_ids: set[str] = set()
    all_categories: set[str] = set()

    for row in rows:
        task_name = str(row[0])
        task_category = str(row[1]) if row[1] else "uncategorized"

        task_data = parse_row_to_task_data(row)
        tasks_data.append(task_data)
        task_ids.add(task_name)
        all_categories.add(task_category)

        nodes.append(build_node(row, task_data, active_tasks, pending_tasks))
        edges.extend(build_explicit_edges(row, task_name, active_tasks))

    return nodes, edges, tasks_data, task_ids, all_categories


@router.get("/graph", response_model=WorkflowGraphResponse)
async def get_workflow_graph(
    category: str | None = Query(None, description="Comma-separated categories to filter"),
    include_inactive: bool = Query(False, description="Include tasks with 0% success rate"),
) -> WorkflowGraphResponse:
    """Get workflow graph in React Flow format.

    Transforms task capabilities into nodes and edges for visualization.
    Overlays current task status from live Hatchet inspection.
    """
    conn_mgr = get_connection_manager()
    category_filter: set[str] | None = None
    if category:
        category_filter = {c.strip().lower() for c in category.split(",")}

    active_tasks, pending_tasks = _get_live_task_status()

    with conn_mgr.connection() as conn:
        query, params = _build_query_and_params(include_inactive, category_filter)
        result = conn.execute(query, params)
        rows = result.fetchall()

        nodes, edges, tasks_data, task_ids, all_categories = _process_rows(
            rows, active_tasks, pending_tasks
        )

        inferred_deps = _infer_dependencies(tasks_data)
        inferred_edges = build_inferred_edges(inferred_deps, tasks_data, edges, active_tasks)
        edges.extend(inferred_edges)

        edges = [e for e in edges if e.source in task_ids and e.target in task_ids]

    return WorkflowGraphResponse(
        nodes=nodes,
        edges=edges,
        categories=sorted(all_categories),
        lastUpdated=datetime.now(UTC).isoformat(),
    )


def _merge_overrides(
    existing: dict[str, Any],
    overrides: DependencyOverrideRequest,
) -> dict[str, Any]:
    """Merge incoming override request with existing overrides."""
    existing_add = set(existing.get("add", []))
    existing_remove = set(existing.get("remove", []))

    existing_add.update(overrides.add)
    existing_remove.update(overrides.remove)

    conflicts = existing_add & existing_remove
    existing_add -= conflicts
    existing_remove -= conflicts

    return {
        "add": sorted(existing_add),
        "remove": sorted(existing_remove),
        "reason": overrides.reason,
    }


def _fetch_existing_overrides(conn: Any, task_name: str) -> dict[str, Any]:
    """Fetch and parse existing dependency_overrides for a task; raises 404 if not found."""
    check = conn.execute(
        "SELECT dependency_overrides FROM celery_capabilities WHERE task_name = %s",
        [task_name],
    )
    row = check.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Task {task_name} not found")

    raw: Any = row[0] or {}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


@router.patch("/tasks/{task_name}/dependencies", response_model=DependencyOverrideResponse)
async def update_task_dependencies(
    task_name: str,
    overrides: DependencyOverrideRequest,
) -> DependencyOverrideResponse:
    """Update dependency overrides for a task.

    Used by /audit_it to auto-correct dependency issues, or manually to fix
    incorrectly inferred dependencies.
    """
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        existing = _fetch_existing_overrides(conn, task_name)
        new_overrides = _merge_overrides(existing, overrides)

        conn.execute(
            """
            UPDATE celery_capabilities
            SET dependency_overrides = %s::jsonb,
                updated_at = NOW()
            WHERE task_name = %s
            """,
            [json.dumps(new_overrides), task_name],
        )
        conn.raw_connection.commit()

        logger.info(
            "dependency_overrides_updated",
            task_name=task_name,
            add_count=len(new_overrides["add"]),
            remove_count=len(new_overrides["remove"]),
        )

    return DependencyOverrideResponse(
        status="updated",
        task_name=task_name,
        overrides=new_overrides,
    )
