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


def start_workflow(
    storage: PortfolioStorage,
    workflow_type: str,
    config: dict[str, object] | None = None,
    agents_involved: list[str] | None = None,
    triggered_by: str | None = None,
    priority: int = 5,
    max_duration_seconds: int = 3600,
) -> dict[str, object]:
    """Start a new multi-agent workflow.

    Args:
        storage: PortfolioStorage instance for database access
        workflow_type: Type of workflow (e.g., 'daily_gap_analysis', 'paper_trade_validation')
        config: Optional configuration for workflow
        agents_involved: List of agent types participating (e.g., ['gemini', 'claude'])
        triggered_by: Who/what triggered this workflow
        priority: Priority 1-10 (1=urgent, 10=low, default=5)
        max_duration_seconds: Maximum workflow runtime in seconds (default 3600)

    Returns:
        Result dictionary with workflow_id and status
    """
    try:
        workflow_id = str(uuid.uuid4())

        # Build shared context
        shared_context: dict[str, object] = {
            "config": config or {},
            "started_at": datetime.now(UTC).isoformat(),
            "agents": {},  # Will store agent-specific state
            "votes": {},  # Will store consensus votes
            "messages": [],  # Will store workflow messages
        }

        # Insert workflow record using direct SQL to avoid numpy array conversion
        agents_list = agents_involved if agents_involved else []

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
                    "{" + ",".join(agents_list) + "}" if agents_list else "{}",
                    json.dumps(shared_context),
                    triggered_by,
                    priority,
                    max_duration_seconds,
                    datetime.now(UTC),
                    datetime.now(UTC),
                ],
            )
            conn.commit()

        logger.info(
            f"Started workflow {workflow_id} ({workflow_type}) "
            f"with agents: {agents_involved or 'none'}"
        )

        return {
            "status": "started",
            "workflow_id": workflow_id,
            "workflow_type": workflow_type,
            "agents_involved": agents_involved or [],
        }

    except Exception as e:
        logger.error(f"Failed to start workflow: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


def update_workflow_status(
    storage: PortfolioStorage,
    workflow_id: str,
    status: Literal["pending", "running", "blocked", "complete", "failed"],
    current_step: str | None = None,
    error: str | None = None,
) -> None:
    """Update workflow status and current step.

    Args:
        storage: PortfolioStorage instance for database access
        workflow_id: ID of the workflow
        status: New status
        current_step: Optional current step description
        error: Optional error message (required if status='failed')
    """
    updates: dict[str, object] = {
        "status": status,
        "last_updated_at": datetime.now(UTC),
    }

    if current_step:
        updates["current_step"] = current_step

    if status in ("running", "blocked", "complete", "failed"):
        # Set started_at if not already set
        result = storage.query(
            "SELECT started_at FROM agent_workflows WHERE id = $1", [workflow_id]
        )
        if not result.is_empty() and result.get_column("started_at")[0] is None:
            updates["started_at"] = datetime.now(UTC)

    if status in ("complete", "failed"):
        updates["completed_at"] = datetime.now(UTC)

    if status == "failed" and error:
        updates["error"] = error

    # Build SET clause
    # Validate column names against whitelist to prevent SQL injection
    allowed_columns = {
        "status",
        "current_step",
        "started_at",
        "completed_at",
        "error",
        "last_updated_at",
    }
    set_parts = []
    values = []
    for i, (key, value) in enumerate(updates.items(), start=1):
        if key not in allowed_columns:
            raise ValueError(f"Invalid column name: {key}")
        set_parts.append(f"{key} = ${i}")
        values.append(value)

    values.append(workflow_id)
    set_clause = ", ".join(set_parts)

    with storage.connection() as conn:
        conn.execute(
            f"UPDATE agent_workflows SET {set_clause} WHERE id = ${len(values)}",
            [str(v) for v in values],
        )
        conn.commit()

    logger.info(f"Workflow {workflow_id} status updated to {status}")


def complete_workflow(
    storage: PortfolioStorage, workflow_id: str, result: dict[str, object]
) -> dict[str, object]:
    """Mark a workflow as complete with final result.

    Args:
        storage: PortfolioStorage instance for database access
        workflow_id: ID of the workflow
        result: Final workflow result

    Returns:
        Status dictionary
    """
    try:
        with storage.connection() as conn:
            conn.execute(
                """
                UPDATE agent_workflows
                SET status = 'complete', result = %s, completed_at = %s, last_updated_at = %s
                WHERE id = %s
                """,
                [json.dumps(result), datetime.now(UTC), datetime.now(UTC), workflow_id],
            )
            conn.commit()

        logger.info(f"Workflow {workflow_id} completed successfully")

        return {
            "status": "completed",
            "workflow_id": workflow_id,
            "result": result,
        }

    except Exception as e:
        logger.error(f"Failed to complete workflow: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


def fail_workflow(
    storage: PortfolioStorage, workflow_id: str, error: str, retry: bool = False
) -> dict[str, object]:
    """Mark a workflow as failed.

    Args:
        storage: PortfolioStorage instance for database access
        workflow_id: ID of the workflow
        error: Error message
        retry: Whether to retry the workflow

    Returns:
        Status dictionary
    """
    try:
        if retry:
            # Increment retry count
            result = storage.query(
                "SELECT retry_count, max_retries FROM agent_workflows WHERE id = $1",
                [workflow_id],
            )

            if not result.is_empty():
                retry_count = result.get_column("retry_count")[0]
                max_retries = result.get_column("max_retries")[0]

                if retry_count < max_retries:
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
                        f"Workflow {workflow_id} queued for retry ({retry_count + 1}/{max_retries})"
                    )

                    return {
                        "status": "retry_queued",
                        "workflow_id": workflow_id,
                        "retry_count": retry_count + 1,
                        "max_retries": max_retries,
                    }

        # Mark as failed (no retry or max retries exceeded)
        with storage.connection() as conn:
            conn.execute(
                """
                UPDATE agent_workflows
                SET status = 'failed', error = $1, completed_at = $2, last_updated_at = $2
                WHERE id = $3
                """,
                [error, datetime.now(UTC), workflow_id],
            )

        logger.error(f"Workflow {workflow_id} failed: {error}")

        return {
            "status": "failed",
            "workflow_id": workflow_id,
            "error": error,
        }

    except Exception as e:
        logger.error(f"Failed to mark workflow as failed: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


def get_workflow_status(storage: PortfolioStorage, workflow_id: str) -> dict[str, object] | None:
    """Get current status of a workflow.

    Args:
        storage: PortfolioStorage instance for database access
        workflow_id: ID of the workflow

    Returns:
        Workflow status dictionary or None if not found
    """
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

        return {
            "workflow_id": result.get_column("id")[0],
            "workflow_type": result.get_column("workflow_type")[0],
            "status": result.get_column("status")[0],
            "current_step": result.get_column("current_step")[0],
            "agents_involved": result.get_column("agents_involved")[0],
            "shared_context": result.get_column("shared_context")[0],
            "result": result.get_column("result")[0],
            "error": result.get_column("error")[0],
            "created_at": result.get_column("created_at")[0],
            "started_at": result.get_column("started_at")[0],
            "completed_at": result.get_column("completed_at")[0],
            "last_updated_at": result.get_column("last_updated_at")[0],
            "max_duration_seconds": result.get_column("max_duration_seconds")[0],
            "retry_count": result.get_column("retry_count")[0],
            "max_retries": result.get_column("max_retries")[0],
            "triggered_by": result.get_column("triggered_by")[0],
            "priority": result.get_column("priority")[0],
        }

    except Exception as e:
        logger.error(f"Failed to get workflow status: {e}")
        return None
