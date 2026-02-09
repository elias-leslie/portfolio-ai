"""Hatchet workflow run inspection service.

Provides functions to inspect Hatchet workflow runs, replacing
the old celery_inspector.py. Uses the Hatchet REST API to query
workflow run statuses.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from app.logging_config import get_logger

logger = get_logger(__name__)


def _get_hatchet_client() -> Any:
    """Get the Hatchet client instance."""
    from app.hatchet_app import get_hatchet

    return get_hatchet()


def _format_run(run: Any) -> dict[str, Any]:
    """Convert a Hatchet workflow run to a normalized dict."""
    # Extract fields safely
    run_id = getattr(run, "workflow_run_id", None) or getattr(run, "id", "unknown")
    name = getattr(run, "workflow_name", None) or getattr(run, "display_name", "unknown")
    status = getattr(run, "status", "UNKNOWN")
    started_at = getattr(run, "started_at", None) or getattr(run, "created_at", None)
    finished_at = getattr(run, "finished_at", None)

    duration = None
    if started_at and finished_at:
        try:
            if isinstance(started_at, str):
                started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            if isinstance(finished_at, str):
                finished_at = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
            duration = (finished_at - started_at).total_seconds()
        except (ValueError, TypeError):
            pass
    elif started_at and status == "RUNNING":
        try:
            if isinstance(started_at, str):
                started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            duration = (datetime.now(UTC) - started_at).total_seconds()
        except (ValueError, TypeError):
            pass

    started_str = None
    if started_at:
        started_str = started_at.isoformat() if isinstance(started_at, datetime) else str(started_at)

    finished_str = None
    if finished_at:
        finished_str = (
            finished_at.isoformat() if isinstance(finished_at, datetime) else str(finished_at)
        )

    # Extract input/output if available
    input_data = getattr(run, "input", None)
    output_data = getattr(run, "output", None)

    return {
        "id": str(run_id),
        "name": str(name),
        "status": str(status),
        "started_at": started_str,
        "duration": duration,
        "date_done": finished_str,
        "worker": "portfolio-worker",
        "args": json.dumps(input_data) if input_data else None,
        "kwargs": None,
        "result": json.dumps(output_data) if output_data else None,
        "traceback": getattr(run, "error", None),
    }


def _list_runs(statuses: list[str], limit: int = 50) -> list[dict[str, Any]]:
    """List workflow runs by status using the Hatchet REST API."""
    try:
        hatchet = _get_hatchet_client()
        runs = hatchet.rest.workflow_run_list(statuses=statuses, limit=limit)

        if not runs:
            return []

        # Handle both list and paginated response objects
        run_list = runs if isinstance(runs, list) else getattr(runs, "rows", [])
        return [_format_run(run) for run in run_list]
    except Exception as e:
        logger.warning("hatchet_list_runs_failed", error=str(e), statuses=statuses)
        return []


def get_active_tasks() -> list[dict[str, Any]]:
    """Get currently running workflow runs."""
    return _list_runs(["RUNNING"])


def get_pending_tasks() -> list[dict[str, Any]]:
    """Get queued/pending workflow runs."""
    return _list_runs(["PENDING", "QUEUED"])


def get_recent_completed(limit: int = 50) -> list[dict[str, Any]]:
    """Get recently succeeded workflow runs."""
    return _list_runs(["SUCCEEDED"], limit=limit)


def get_recent_failed(limit: int = 50) -> list[dict[str, Any]]:
    """Get recently failed workflow runs."""
    return _list_runs(["FAILED"], limit=limit)


def get_queue_depth() -> int:
    """Get total count of pending workflow runs."""
    pending = get_pending_tasks()
    return len(pending)


def get_unified_task_list(
    status: Literal["all", "active", "pending", "completed", "failed"] = "all",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get unified task list from Hatchet with optional filtering."""
    tasks: list[dict[str, Any]] = []

    if status in ("all", "active"):
        tasks.extend(get_active_tasks())

    if status in ("all", "pending"):
        tasks.extend(get_pending_tasks())

    if status in ("all", "completed"):
        tasks.extend(get_recent_completed(limit=limit))

    if status in ("all", "failed"):
        tasks.extend(get_recent_failed(limit=limit))

    return tasks
