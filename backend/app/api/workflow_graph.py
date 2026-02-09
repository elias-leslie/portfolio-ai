"""Workflow Graph API - React Flow visualization for scheduled tasks.

This module transforms celery_capabilities data into React Flow compatible
graph format for workflow visualization.

Phase 1.5 adds intelligent dependency inference from table relationships.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..logging_config import get_logger
from ..services.hatchet_inspector import get_unified_task_list
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


def _parse_schedule_time(crontab: str | None, interval_seconds: int | None) -> int | None:
    """Convert schedule to minutes-from-midnight for timing comparison.

    Returns None for interval-based schedules (can't determine fixed order).

    Args:
        crontab: Crontab string (e.g., "30 2 * * *")
        interval_seconds: Interval in seconds

    Returns:
        Minutes from midnight, or None if not determinable
    """
    if crontab:
        parts = crontab.split()
        if len(parts) >= 2:
            try:
                minute = int(parts[0]) if parts[0] != "*" else 0
                hour = int(parts[1]) if parts[1] != "*" else 0
                return hour * 60 + minute
            except ValueError:
                pass
    return None


def _infer_dependencies(
    tasks: list[dict[str, Any]],
) -> list[tuple[str, str, str]]:
    """Infer task dependencies from table relationships and timing.

    Rules:
    1. If Task B reads_from table X AND Task A populates table X
       AND Task A scheduled before Task B → A→B edge
    2. Apply dependency_overrides (add/remove)

    Args:
        tasks: List of task dicts with populates_tables, reads_from_tables, etc.

    Returns:
        List of (source_task, target_task, reason) tuples
    """
    edges: list[tuple[str, str, str]] = []

    # Build lookup map: table -> [(task_name, schedule_time)]
    writers: dict[str, list[tuple[str, int | None]]] = {}
    for task in tasks:
        task_name = task.get("task_name", "")
        populates = task.get("populates_tables") or []
        if isinstance(populates, str):
            try:
                populates = json.loads(populates)
            except json.JSONDecodeError:
                populates = []

        schedule_time = _parse_schedule_time(
            task.get("schedule_crontab"),
            task.get("schedule_interval_seconds"),
        )

        for table in populates:
            if table not in writers:
                writers[table] = []
            writers[table].append((task_name, schedule_time))

    # Find dependencies based on reads
    for task in tasks:
        task_name = task.get("task_name", "")
        reads = task.get("reads_from_tables") or []
        if isinstance(reads, str):
            try:
                reads = json.loads(reads)
            except json.JSONDecodeError:
                reads = []

        task_time = _parse_schedule_time(
            task.get("schedule_crontab"),
            task.get("schedule_interval_seconds"),
        )

        for table in reads:
            if table in writers:
                for writer_name, writer_time in writers[table]:
                    # Skip self-references
                    if writer_name == task_name:
                        continue
                    # Check timing (writer should run before reader)
                    if writer_time is not None and task_time is not None:
                        if writer_time < task_time:
                            edges.append(
                                (
                                    writer_name,
                                    task_name,
                                    f"writes→reads: {table}",
                                )
                            )
                    elif writer_time is None and task_time is None:
                        # Both interval-based, include edge without timing check
                        edges.append(
                            (
                                writer_name,
                                task_name,
                                f"writes→reads: {table}",
                            )
                        )

        # Apply manual overrides (add)
        overrides = task.get("dependency_overrides") or {}
        if isinstance(overrides, str):
            try:
                overrides = json.loads(overrides)
            except json.JSONDecodeError:
                overrides = {}

        for dep in overrides.get("add", []):
            reason = overrides.get("reason", "manual override")
            edges.append((dep, task_name, f"manual: {reason}"))

    # Deduplicate
    seen: set[tuple[str, str]] = set()
    unique_edges: list[tuple[str, str, str]] = []
    for source, target, reason in edges:
        key = (source, target)
        if key not in seen:
            seen.add(key)
            unique_edges.append((source, target, reason))

    return unique_edges


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
            live_task_name = task.get("name", "")
            status = task.get("status", "").upper()
            if status == "ACTIVE":
                active_tasks[live_task_name] = "running"
            elif status == "PENDING":
                pending_tasks.add(live_task_name)
    except Exception as e:
        logger.warning("failed_to_get_live_tasks", error=str(e))

    with conn_mgr.connection() as conn:
        # Query celery_capabilities for tasks with dependencies
        # Phase 1.5: Now includes reads_from_tables and dependency_overrides
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
                schedule_description,
                reads_from_tables,
                dependency_overrides,
                schedule_interval_seconds
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

        # Convert rows to list of dicts for dependency inference
        tasks_data: list[dict[str, Any]] = []

        # Build nodes
        task_ids: set[str] = set()
        for row in rows:
            task_name: str = str(row[0])
            task_category: str = str(row[1]) if row[1] else "uncategorized"
            depends_on: Any = row[2] or []
            populates: Any = row[3] or []
            last_run = row[4]
            next_run = row[5]
            success_rate = row[6] or 0.0
            avg_duration = row[7] or 0.0
            cron_schedule: str | None = str(row[8]) if row[8] else None
            schedule_description: str | None = str(row[9]) if row[9] else None
            reads_from: Any = row[10] or []
            dep_overrides: Any = row[11] or {}
            interval_seconds = row[12]

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
            if isinstance(reads_from, str):
                try:
                    reads_from = json.loads(reads_from)
                except json.JSONDecodeError:
                    reads_from = []
            if isinstance(dep_overrides, str):
                try:
                    dep_overrides = json.loads(dep_overrides)
                except json.JSONDecodeError:
                    dep_overrides = {}

            if isinstance(task_name, str):
                task_ids.add(task_name)
            if isinstance(task_category, str):
                all_categories.add(task_category)

            # Store for dependency inference
            tasks_data.append(
                {
                    "task_name": task_name,
                    "populates_tables": populates,
                    "reads_from_tables": reads_from,
                    "dependency_overrides": dep_overrides,
                    "schedule_crontab": cron_schedule,
                    "schedule_interval_seconds": interval_seconds,
                }
            )

            # Determine status
            node_status: Literal["idle", "running", "completed", "failed", "pending"] = "idle"
            if task_name in active_tasks:
                node_status = "running"
            elif task_name in pending_tasks:
                node_status = "pending"
            elif last_run and isinstance(last_run, datetime):
                # Check if recently completed (within last hour)
                age = (datetime.now(UTC) - last_run.replace(tzinfo=UTC)).total_seconds()
                if age < 3600:
                    node_status = "completed"

            # Convert schedule and category to strings
            schedule_str: str = (
                str(schedule_description)
                if schedule_description
                else _humanize_schedule(task_name, cron_schedule)
            )
            category_str: str = str(task_category)

            # Handle datetime fields
            last_run_str: str | None = None
            if last_run and isinstance(last_run, datetime):
                last_run_str = last_run.isoformat()

            next_run_str: str | None = None
            if next_run and isinstance(next_run, datetime):
                next_run_str = next_run.isoformat()

            node = WorkflowNode(
                id=task_name,
                type="task",
                data=NodeData(
                    label=_task_name_to_label(task_name),
                    schedule=schedule_str,
                    category=category_str,
                    status=node_status,
                    lastRun=last_run_str,
                    nextRun=next_run_str,
                    successRate=float(success_rate),
                    avgDuration=float(avg_duration),
                    populatesTables=populates if isinstance(populates, list) else [],
                ),
                position={"x": 0, "y": 0},  # Dagre will calculate on frontend
            )
            nodes.append(node)

            # Build edges from explicit dependencies (depends_on_tasks field)
            if depends_on and isinstance(depends_on, list):
                for dep in depends_on:
                    edge = WorkflowEdge(
                        id=f"e-explicit-{dep}-{task_name}",
                        source=dep,
                        target=task_name,
                        type="dependency",
                        animated=dep in active_tasks,
                    )
                    edges.append(edge)

        # Phase 1.5: Infer dependencies from table relationships
        inferred_deps = _infer_dependencies(tasks_data)
        for source, target, _reason in inferred_deps:
            # Check if edge should be removed by override
            target_task = next((t for t in tasks_data if t["task_name"] == target), None)
            if target_task:
                removes = target_task.get("dependency_overrides", {}).get("remove", [])
                if source in removes:
                    continue  # Skip this edge

            # Only add if not already present (from explicit deps)
            edge_id = f"e-inferred-{source}-{target}"
            if not any(e.source == source and e.target == target for e in edges):
                edge = WorkflowEdge(
                    id=edge_id,
                    source=source,
                    target=target,
                    type="data-flow",  # Inferred edges are data-flow type
                    animated=source in active_tasks,
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


# Phase 1.5: Dependency override models and endpoint
class DependencyOverrideRequest(BaseModel):
    """Request model for updating task dependency overrides."""

    add: list[str] = []
    remove: list[str] = []
    reason: str


class DependencyOverrideResponse(BaseModel):
    """Response model for dependency override updates."""

    status: str
    task_name: str
    overrides: dict[str, Any]


@router.patch("/tasks/{task_name}/dependencies", response_model=DependencyOverrideResponse)
async def update_task_dependencies(
    task_name: str,
    overrides: DependencyOverrideRequest,
) -> DependencyOverrideResponse:
    """Update dependency overrides for a task.

    Used by /audit_it to auto-correct dependency issues, or manually to fix
    incorrectly inferred dependencies.

    Args:
        task_name: The task name (beat schedule key)
        overrides: Dependencies to add/remove and reason

    Returns:
        Updated override state
    """
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        # First check if task exists
        check = conn.execute(
            "SELECT dependency_overrides FROM celery_capabilities WHERE task_name = %s",
            [task_name],
        )
        row = check.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Task {task_name} not found")

        # Merge with existing overrides
        raw_existing: Any = row[0] or {}
        existing: dict[str, Any] = {}
        if isinstance(raw_existing, str):
            try:
                existing = json.loads(raw_existing)
            except json.JSONDecodeError:
                existing = {}
        elif isinstance(raw_existing, dict):
            existing = raw_existing

        # Merge add/remove lists
        existing_add = set(existing.get("add", []))
        existing_remove = set(existing.get("remove", []))

        existing_add.update(overrides.add)
        existing_remove.update(overrides.remove)

        # Remove any that are in both lists (cancel out)
        conflicts = existing_add & existing_remove
        existing_add -= conflicts
        existing_remove -= conflicts

        new_overrides = {
            "add": sorted(existing_add),
            "remove": sorted(existing_remove),
            "reason": overrides.reason,
        }

        # Update database
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
