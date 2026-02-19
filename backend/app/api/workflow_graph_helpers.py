"""Helper functions for the Workflow Graph API.

Includes schedule parsing, label formatting, and dependency inference.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from .workflow_graph_models import NodeData, WorkflowEdge, WorkflowNode


def _humanize_schedule(task_name: str, cron_expr: str | None) -> str:
    """Convert cron expression or task name to human-readable schedule."""
    if cron_expr:
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
    name = task_name
    for prefix in ["tasks.", "app.tasks.", "celery_"]:
        if name.startswith(prefix):
            name = name[len(prefix):]
    name = name.replace("-", " ").replace("_", " ")
    return name.title()


def _parse_schedule_time(crontab: str | None, interval_seconds: int | None) -> int | None:
    """Convert schedule to minutes-from-midnight for timing comparison.

    Returns None for interval-based schedules (can't determine fixed order).
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


def _parse_json_field(value: Any, default: Any) -> Any:
    """Parse a field that may be a JSON string or already parsed."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value if value is not None else default


def _infer_dependencies(
    tasks: list[dict[str, Any]],
) -> list[tuple[str, str, str]]:
    """Infer task dependencies from table relationships and timing.

    Rules:
    1. If Task B reads_from table X AND Task A populates table X
       AND Task A scheduled before Task B -> A->B edge
    2. Apply dependency_overrides (add/remove)
    """
    edges: list[tuple[str, str, str]] = []
    writers = _build_writers_map(tasks)
    edges = _find_read_write_deps(tasks, writers)
    edges.extend(_collect_manual_overrides(tasks))
    return _deduplicate_edges(edges)


def _build_writers_map(tasks: list[dict[str, Any]]) -> dict[str, list[tuple[str, int | None]]]:
    """Build lookup map: table -> [(task_name, schedule_time)]."""
    writers: dict[str, list[tuple[str, int | None]]] = {}
    for task in tasks:
        task_name = task.get("task_name", "")
        populates = _parse_json_field(task.get("populates_tables"), [])
        schedule_time = _parse_schedule_time(
            task.get("schedule_crontab"),
            task.get("schedule_interval_seconds"),
        )
        for table in populates:
            writers.setdefault(table, []).append((task_name, schedule_time))
    return writers


def _find_read_write_deps(
    tasks: list[dict[str, Any]],
    writers: dict[str, list[tuple[str, int | None]]],
) -> list[tuple[str, str, str]]:
    """Find dependencies based on read/write table relationships."""
    edges: list[tuple[str, str, str]] = []
    for task in tasks:
        task_name = task.get("task_name", "")
        reads = _parse_json_field(task.get("reads_from_tables"), [])
        task_time = _parse_schedule_time(
            task.get("schedule_crontab"),
            task.get("schedule_interval_seconds"),
        )
        for table in reads:
            for writer_name, writer_time in writers.get(table, []):
                if writer_name == task_name:
                    continue
                if (writer_time is not None and task_time is not None and writer_time < task_time) or (writer_time is None and task_time is None):
                    edges.append((writer_name, task_name, f"writes->reads: {table}"))
    return edges


def _collect_manual_overrides(tasks: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """Collect manually specified dependency additions from overrides."""
    edges: list[tuple[str, str, str]] = []
    for task in tasks:
        task_name = task.get("task_name", "")
        overrides = _parse_json_field(task.get("dependency_overrides"), {})
        reason = overrides.get("reason", "manual override")
        for dep in overrides.get("add", []):
            edges.append((dep, task_name, f"manual: {reason}"))
    return edges


def _deduplicate_edges(edges: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Remove duplicate (source, target) pairs from edge list."""
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str, str]] = []
    for source, target, reason in edges:
        key = (source, target)
        if key not in seen:
            seen.add(key)
            unique.append((source, target, reason))
    return unique


def parse_row_to_task_data(row: tuple) -> dict[str, Any]:
    """Parse a database row into a task data dict for dependency inference."""
    cron_schedule: str | None = str(row[8]) if row[8] else None
    interval_seconds = row[12]
    return {
        "task_name": str(row[0]),
        "populates_tables": _parse_json_field(row[3] or [], []),
        "reads_from_tables": _parse_json_field(row[10] or [], []),
        "dependency_overrides": _parse_json_field(row[11] or {}, {}),
        "schedule_crontab": cron_schedule,
        "schedule_interval_seconds": interval_seconds,
    }


def determine_node_status(
    task_name: str,
    last_run: Any,
    active_tasks: dict[str, str],
    pending_tasks: set[str],
) -> Literal["idle", "running", "completed", "failed", "pending"]:
    """Determine the current status of a node."""
    if task_name in active_tasks:
        return "running"
    if task_name in pending_tasks:
        return "pending"
    if last_run and isinstance(last_run, datetime):
        age = (datetime.now(UTC) - last_run.replace(tzinfo=UTC)).total_seconds()
        if age < 3600:
            return "completed"
    return "idle"


def build_node(
    row: tuple,
    task_data: dict[str, Any],
    active_tasks: dict[str, str],
    pending_tasks: set[str],
) -> WorkflowNode:
    """Build a WorkflowNode from a database row."""
    task_name: str = str(row[0])
    task_category: str = str(row[1]) if row[1] else "uncategorized"
    populates = task_data["populates_tables"]
    last_run = row[4]
    next_run = row[5]
    success_rate = row[6] or 0.0
    avg_duration = row[7] or 0.0
    cron_schedule: str | None = str(row[8]) if row[8] else None
    schedule_description: str | None = str(row[9]) if row[9] else None

    node_status = determine_node_status(task_name, last_run, active_tasks, pending_tasks)

    schedule_str = (
        str(schedule_description)
        if schedule_description
        else _humanize_schedule(task_name, cron_schedule)
    )

    last_run_str: str | None = last_run.isoformat() if last_run and isinstance(last_run, datetime) else None
    next_run_str: str | None = next_run.isoformat() if next_run and isinstance(next_run, datetime) else None

    return WorkflowNode(
        id=task_name,
        type="task",
        data=NodeData(
            label=_task_name_to_label(task_name),
            schedule=schedule_str,
            category=task_category,
            status=node_status,
            lastRun=last_run_str,
            nextRun=next_run_str,
            successRate=float(success_rate),
            avgDuration=float(avg_duration),
            populatesTables=populates if isinstance(populates, list) else [],
        ),
        position={"x": 0, "y": 0},
    )


def build_explicit_edges(
    row: tuple,
    task_name: str,
    active_tasks: dict[str, str],
) -> list[WorkflowEdge]:
    """Build edges from the explicit depends_on_tasks field."""
    depends_on = _parse_json_field(row[2] or [], [])
    edges: list[WorkflowEdge] = []
    if depends_on and isinstance(depends_on, list):
        for dep in depends_on:
            edges.append(WorkflowEdge(
                id=f"e-explicit-{dep}-{task_name}",
                source=dep,
                target=task_name,
                type="dependency",
                animated=dep in active_tasks,
            ))
    return edges


def build_inferred_edges(
    inferred_deps: list[tuple[str, str, str]],
    tasks_data: list[dict[str, Any]],
    existing_edges: list[WorkflowEdge],
    active_tasks: dict[str, str],
) -> list[WorkflowEdge]:
    """Build inferred dependency edges, respecting overrides and deduplication."""
    new_edges: list[WorkflowEdge] = []
    for source, target, _reason in inferred_deps:
        target_task = next((t for t in tasks_data if t["task_name"] == target), None)
        if target_task:
            removes = target_task.get("dependency_overrides", {}).get("remove", [])
            if source in removes:
                continue
        if not any(e.source == source and e.target == target for e in existing_edges):
            new_edges.append(WorkflowEdge(
                id=f"e-inferred-{source}-{target}",
                source=source,
                target=target,
                type="data-flow",
                animated=source in active_tasks,
            ))
    return new_edges
