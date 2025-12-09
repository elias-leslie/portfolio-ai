"""Workflow Graph API - React Flow visualization for scheduled tasks.

This module transforms celery_capabilities data into React Flow compatible
graph format for workflow visualization.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..logging_config import get_logger
from ..services.celery_inspector import get_unified_task_list
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# Pydantic models for response
class NodeData(BaseModel):
    """Data payload for a workflow node."""

    label: str
    schedule: str
    category: str
    status: Literal["idle", "running", "completed", "failed", "pending"]
    lastRun: str | None  # noqa: N815 - camelCase for frontend API
    nextRun: str | None  # noqa: N815 - camelCase for frontend API
    successRate: float  # noqa: N815 - camelCase for frontend API
    avgDuration: float  # noqa: N815 - camelCase for frontend API (milliseconds)
    populatesTables: list[str]  # noqa: N815 - camelCase for frontend API


class WorkflowNode(BaseModel):
    """A node in the workflow graph."""

    id: str
    type: Literal["task", "workflow", "agent"]
    data: NodeData
    position: dict[str, float]


class WorkflowEdge(BaseModel):
    """An edge connecting two nodes."""

    id: str
    source: str
    target: str
    type: Literal["dependency", "data-flow"]
    animated: bool = False


class WorkflowGraphResponse(BaseModel):
    """Response model for workflow graph endpoint."""

    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    categories: list[str]
    lastUpdated: str  # noqa: N815 - camelCase for frontend API


def _humanize_schedule(task_name: str, cron_expr: str | None) -> str:
    """Convert cron expression or task name to human-readable schedule."""
    # Try to get from common patterns
    if cron_expr:
        # Simple parsing for common cron patterns
        parts = cron_expr.split()
        if len(parts) >= 5:
            minute, hour = parts[0], parts[1]
            if minute.isdigit() and hour.isdigit():
                return f"{hour.zfill(2)}:{minute.zfill(2)} UTC"
            if minute == "*/5":
                return "Every 5 min"
            if minute == "*/15":
                return "Every 15 min"
            if minute == "*/30":
                return "Every 30 min"
            if hour == "*" and minute.isdigit():
                return f"Hourly at :{minute.zfill(2)}"
    return "Scheduled"


def _task_name_to_label(task_name: str) -> str:
    """Convert task name to human-readable label."""
    # Remove common prefixes
    name = task_name
    for prefix in ["tasks.", "app.tasks.", "celery_"]:
        if name.startswith(prefix):
            name = name[len(prefix) :]

    # Convert kebab-case or snake_case to Title Case
    name = name.replace("-", " ").replace("_", " ")
    return name.title()


@router.get("/graph", response_model=WorkflowGraphResponse)
async def get_workflow_graph(
    category: str | None = Query(None, description="Comma-separated categories to filter"),
    include_inactive: bool = Query(False, description="Include tasks with 0% success rate"),
) -> WorkflowGraphResponse:
    """Get workflow graph in React Flow format.

    Transforms celery_capabilities into nodes and edges for visualization.
    Overlays current task status from live Celery inspection.
    """
    conn_mgr = get_connection_manager()
    nodes: list[WorkflowNode] = []
    edges: list[WorkflowEdge] = []
    all_categories: set[str] = set()

    # Parse category filter
    category_filter: set[str] | None = None
    if category:
        category_filter = {c.strip().lower() for c in category.split(",")}

    # Get live task status
    active_tasks: dict[str, str] = {}
    pending_tasks: set[str] = set()
    try:
        unified_tasks = get_unified_task_list(status="all", limit=100)
        for task in unified_tasks:
            task_name = task.get("name", "")
            status = task.get("status", "").upper()
            if status == "ACTIVE":
                active_tasks[task_name] = "running"
            elif status == "PENDING":
                pending_tasks.add(task_name)
    except Exception as e:
        logger.warning("failed_to_get_live_tasks", error=str(e))

    with conn_mgr.connection() as conn:
        # Query celery_capabilities for tasks with dependencies
        query = """
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
                schedule_description
            FROM celery_capabilities
            WHERE 1=1
        """
        params: list[Any] = []

        if not include_inactive:
            query += " AND (success_rate_pct > 0 OR last_run_at IS NOT NULL)"

        if category_filter:
            query += " AND LOWER(category) = ANY(%s)"
            params.append(list(category_filter))

        query += " ORDER BY category, task_name"

        result = conn.execute(query, params)
        rows = result.fetchall()

        # Build nodes
        task_ids: set[str] = set()
        for row in rows:
            task_name = row[0]
            task_category = row[1] or "uncategorized"
            depends_on = row[2] or []
            populates = row[3] or []
            last_run = row[4]
            next_run = row[5]
            success_rate = row[6] or 0.0
            avg_duration = row[7] or 0.0
            cron_schedule = row[8]
            schedule_description = row[9]

            # Parse JSON fields if needed
            if isinstance(depends_on, str):
                try:
                    depends_on = json.loads(depends_on)
                except json.JSONDecodeError:
                    depends_on = []
            if isinstance(populates, str):
                try:
                    populates = json.loads(populates)
                except json.JSONDecodeError:
                    populates = []

            task_ids.add(task_name)
            all_categories.add(task_category)

            # Determine status
            status: Literal["idle", "running", "completed", "failed", "pending"] = "idle"
            if task_name in active_tasks:
                status = "running"
            elif task_name in pending_tasks:
                status = "pending"
            elif last_run and isinstance(last_run, datetime):
                # Check if recently completed (within last hour)
                age = (datetime.now(UTC) - last_run.replace(tzinfo=UTC)).total_seconds()
                if age < 3600:
                    status = "completed"

            node = WorkflowNode(
                id=task_name,
                type="task",
                data=NodeData(
                    label=_task_name_to_label(task_name),
                    schedule=schedule_description or _humanize_schedule(task_name, cron_schedule),
                    category=task_category,
                    status=status,
                    lastRun=last_run.isoformat() if last_run else None,
                    nextRun=next_run.isoformat() if next_run else None,
                    successRate=float(success_rate),
                    avgDuration=float(avg_duration),
                    populatesTables=populates if isinstance(populates, list) else [],
                ),
                position={"x": 0, "y": 0},  # Dagre will calculate on frontend
            )
            nodes.append(node)

            # Build edges from dependencies
            if depends_on:
                for dep in depends_on:
                    # Only create edge if dependency exists in our node set
                    # (will be validated after all nodes are created)
                    edge = WorkflowEdge(
                        id=f"e-{dep}-{task_name}",
                        source=dep,
                        target=task_name,
                        type="dependency",
                        animated=dep in active_tasks,
                    )
                    edges.append(edge)

        # Filter edges to only include those where both source and target exist
        edges = [e for e in edges if e.source in task_ids and e.target in task_ids]

    return WorkflowGraphResponse(
        nodes=nodes,
        edges=edges,
        categories=sorted(all_categories),
        lastUpdated=datetime.now(UTC).isoformat(),
    )
