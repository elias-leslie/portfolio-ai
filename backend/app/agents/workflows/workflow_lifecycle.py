"""Workflow lifecycle management for multi-agent workflows."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.logging_config import get_logger

logger = get_logger(__name__)

_ALLOWED_UPDATE_COLUMNS = {
    "status",
    "current_step",
    "started_at",
    "completed_at",
    "error",
    "last_updated_at",
}


def _pg_array(items: list[str]) -> str:
    """Format a Python list as a PostgreSQL text-array literal."""
    return "{" + ",".join(items) + "}" if items else "{}"


def _build_shared_context(config: dict[str, object] | None) -> dict[str, object]:
    return {
        "config": config or {},
        "started_at": datetime.now(UTC).isoformat(),
        "agents": {},
        "votes": {},
        "messages": [],
    }


def _row_to_status_dict(result: object) -> dict[str, object]:
    """Convert a single-row query result to a workflow status dict."""
    cols = [
        "id", "workflow_type", "status", "current_step", "agents_involved",
        "shared_context", "result", "error", "created_at", "started_at",
        "completed_at", "last_updated_at", "max_duration_seconds",
        "retry_count", "max_retries", "triggered_by", "priority",
    ]
    row = {col: result.get_column(col)[0] for col in cols}
    row["workflow_id"] = row.pop("id")
    return row


def _build_set_clause(updates: dict[str, object]) -> tuple[str, list[object]]:
    """Build a parameterised SET clause, returning (clause, values)."""
    parts: list[str] = []
    values: list[object] = []
    for i, (key, value) in enumerate(updates.items(), start=1):
        if key not in _ALLOWED_UPDATE_COLUMNS:
            raise ValueError(f"Invalid column name: {key}")
        parts.append(f"{key} = ${i}")
        values.append(value)
    return ", ".join(parts), values


def _attempt_retry(
    storage: PortfolioStorage, workflow_id: str, error: str
) -> dict[str, object] | None:
    """Try to queue a retry. Returns a result dict on success, None otherwise."""
    result = storage.query(
        "SELECT retry_count, max_retries FROM agent_workflows WHERE id = $1",
        [workflow_id],
    )
    if result.is_empty():
        return None

    retry_count = result.get_column("retry_count")[0]
    max_retries = result.get_column("max_retries")[0]
    if retry_count >= max_retries:
        return None

    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE agent_workflows
            SET status = 'pending', retry_count = retry_count + 1,
                error = $1, last_updated_at = $2
            WHERE id = $3
            """,
            [error, datetime.now(UTC), workflow_id],
        )
        conn.commit()

    logger.info(
        "workflow_retry_queued",
        workflow_id=workflow_id,
        retry_count=retry_count + 1,
        max_retries=max_retries,
    )
    return {
        "status": "retry_queued",
        "workflow_id": workflow_id,
        "retry_count": retry_count + 1,
        "max_retries": max_retries,
    }


def _mark_failed(storage: PortfolioStorage, workflow_id: str, error: str) -> None:
    """Unconditionally mark *workflow_id* as failed in the database."""
    now = datetime.now(UTC)
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE agent_workflows
            SET status = 'failed', error = $1, completed_at = $2, last_updated_at = $3
            WHERE id = $4
            """,
            [error, now, now, workflow_id],
        )
        conn.commit()


def _insert_workflow(
    storage: PortfolioStorage,
    workflow_id: str,
    workflow_type: str,
    agents_list: list[str],
    config: dict[str, object] | None,
    triggered_by: str | None,
    priority: int,
    max_duration_seconds: int,
    now: datetime,
) -> None:
    """Insert a new workflow row into the database."""
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO agent_workflows (
                id, workflow_type, status, current_step, agents_involved,
                shared_context, triggered_by, priority, max_duration_seconds,
                created_at, last_updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                workflow_id,
                workflow_type,
                "pending",
                "initializing",
                _pg_array(agents_list),
                json.dumps(_build_shared_context(config)),
                triggered_by,
                priority,
                max_duration_seconds,
                now,
                now,
            ],
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_workflow(
    storage: PortfolioStorage,
    workflow_type: str,
    config: dict[str, object] | None = None,
    agents_involved: list[str] | None = None,
    triggered_by: str | None = None,
    priority: int = 5,
    max_duration_seconds: int = 3600,
) -> dict[str, object]:
    """Start a new multi-agent workflow and return a status dict."""
    try:
        workflow_id = str(uuid.uuid4())
        agents_list = agents_involved or []
        now = datetime.now(UTC)

        _insert_workflow(
            storage, workflow_id, workflow_type, agents_list,
            config, triggered_by, priority, max_duration_seconds, now,
        )

        logger.info(
            "workflow_started",
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            agents_involved=agents_list,
        )
        return {
            "status": "started",
            "workflow_id": workflow_id,
            "workflow_type": workflow_type,
            "agents_involved": agents_list,
        }

    except Exception as e:
        logger.error("workflow_start_failed", error=str(e), exc_info=True)
        return {"status": "error", "error": str(e)}


def update_workflow_status(
    storage: PortfolioStorage,
    workflow_id: str,
    status: Literal["pending", "running", "blocked", "complete", "failed"],
    current_step: str | None = None,
    error: str | None = None,
) -> None:
    """Update workflow status and current step."""
    updates: dict[str, object] = {
        "status": status,
        "last_updated_at": datetime.now(UTC),
    }

    if current_step:
        updates["current_step"] = current_step

    if status in ("running", "blocked", "complete", "failed"):
        row = storage.query(
            "SELECT started_at FROM agent_workflows WHERE id = $1", [workflow_id]
        )
        if not row.is_empty() and row.get_column("started_at")[0] is None:
            updates["started_at"] = datetime.now(UTC)

    if status in ("complete", "failed"):
        updates["completed_at"] = datetime.now(UTC)

    if status == "failed" and error:
        updates["error"] = error

    set_clause, values = _build_set_clause(updates)
    values.append(workflow_id)

    with storage.connection() as conn:
        conn.execute(
            f"UPDATE agent_workflows SET {set_clause} WHERE id = ${len(values)}",
            [str(v) for v in values],
        )
        conn.commit()

    logger.info("workflow_status_updated", workflow_id=workflow_id, status=status)


def complete_workflow(
    storage: PortfolioStorage, workflow_id: str, result: dict[str, object]
) -> dict[str, object]:
    """Mark a workflow as complete with final result."""
    try:
        now = datetime.now(UTC)
        with storage.connection() as conn:
            conn.execute(
                """
                UPDATE agent_workflows
                SET status = 'complete', result = %s, completed_at = %s, last_updated_at = %s
                WHERE id = %s
                """,
                [json.dumps(result), now, now, workflow_id],
            )
            conn.commit()

        logger.info("workflow_completed", workflow_id=workflow_id)
        return {"status": "completed", "workflow_id": workflow_id, "result": result}

    except Exception as e:
        logger.error("workflow_completion_failed", error=str(e), exc_info=True)
        return {"status": "error", "error": str(e)}


def fail_workflow(
    storage: PortfolioStorage, workflow_id: str, error: str, retry: bool = False
) -> dict[str, object]:
    """Mark a workflow as failed, optionally queuing a retry."""
    try:
        if retry:
            retry_result = _attempt_retry(storage, workflow_id, error)
            if retry_result is not None:
                return retry_result

        _mark_failed(storage, workflow_id, error)
        logger.error("workflow_failed", workflow_id=workflow_id, error=error)
        return {"status": "failed", "workflow_id": workflow_id, "error": error}

    except Exception as e:
        logger.error("workflow_fail_marking_failed", error=str(e), exc_info=True)
        return {"status": "error", "error": str(e)}


def get_workflow_status(storage: PortfolioStorage, workflow_id: str) -> dict[str, object] | None:
    """Get current status of a workflow, or None if not found."""
    try:
        result = storage.query(
            """
            SELECT id, workflow_type, status, current_step, agents_involved,
                   shared_context, result, error, created_at, started_at,
                   completed_at, last_updated_at, max_duration_seconds,
                   retry_count, max_retries, triggered_by, priority
            FROM agent_workflows
            WHERE id = $1
            """,
            [workflow_id],
        )
        if result.is_empty():
            return None
        return _row_to_status_dict(result)

    except Exception as e:
        logger.error("workflow_status_fetch_failed", error=str(e), exc_info=True)
        return None
