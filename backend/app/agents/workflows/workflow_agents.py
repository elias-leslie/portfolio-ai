"""Agent coordination and task assignment for multi-agent workflows."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.logging_config import get_logger

logger = get_logger(__name__)


def assign_task_to_agent(
    storage: PortfolioStorage,
    workflow_id: str,
    agent_type: str,
    task: str,
    context: dict[str, object] | None = None,
) -> dict[str, object]:
    """Assign a task to a specific agent in a workflow.

    Args:
        storage: PortfolioStorage instance for database access
        workflow_id: ID of the workflow
        agent_type: Type of agent to assign task to
        task: Task description
        context: Optional task-specific context

    Returns:
        Result dictionary with assignment status
    """
    try:
        # Get current shared context
        result = storage.query(
            "SELECT shared_context FROM agent_workflows WHERE id = $1",
            [workflow_id],
        )

        if result.is_empty():
            return {
                "status": "error",
                "error": f"Workflow {workflow_id} not found",
            }

        shared_context = result.get_column("shared_context")[0]

        # Add task assignment to agent's state
        if agent_type not in shared_context["agents"]:
            shared_context["agents"][agent_type] = {
                "tasks": [],
                "outputs": [],
                "status": "pending",
            }

        task_assignment = {
            "task": task,
            "context": context or {},
            "assigned_at": datetime.now(UTC).isoformat(),
            "status": "pending",
        }
        shared_context["agents"][agent_type]["tasks"].append(task_assignment)

        # Update workflow (JSON-serialize shared_context)
        with storage.connection() as conn:
            conn.execute(
                "UPDATE agent_workflows SET shared_context = %s, last_updated_at = %s WHERE id = %s",
                [json.dumps(shared_context), datetime.now(UTC), workflow_id],
            )
            conn.commit()

        logger.info("task_assigned", agent_type=agent_type, workflow_id=workflow_id, task_preview=task[:100])

        return {
            "status": "assigned",
            "workflow_id": workflow_id,
            "agent_type": agent_type,
            "task": task,
        }

    except Exception as e:
        logger.error("task_assignment_failed", error=str(e))
        return {
            "status": "error",
            "error": str(e),
        }


def record_agent_output(
    storage: PortfolioStorage,
    workflow_id: str,
    agent_type: str,
    output: dict[str, object],
    confidence: float = 1.0,
) -> None:
    """Record output from an agent in a workflow.

    Args:
        storage: PortfolioStorage instance for database access
        workflow_id: ID of the workflow
        agent_type: Type of agent
        output: Agent's output data
        confidence: Confidence level 0-1
    """
    try:
        # Get current shared context
        result = storage.query(
            "SELECT shared_context FROM agent_workflows WHERE id = $1",
            [workflow_id],
        )

        if result.is_empty():
            logger.error("workflow_not_found", workflow_id=workflow_id)
            return

        shared_context = result.get_column("shared_context")[0]

        # Initialize agent state if needed
        if agent_type not in shared_context["agents"]:
            shared_context["agents"][agent_type] = {
                "tasks": [],
                "outputs": [],
                "status": "pending",
            }

        # Record output
        output_record = {
            "output": output,
            "confidence": confidence,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        shared_context["agents"][agent_type]["outputs"].append(output_record)
        shared_context["agents"][agent_type]["status"] = "completed"

        # Update workflow (JSON-serialize shared_context)
        with storage.connection() as conn:
            conn.execute(
                "UPDATE agent_workflows SET shared_context = %s, last_updated_at = %s WHERE id = %s",
                [json.dumps(shared_context), datetime.now(UTC), workflow_id],
            )
            conn.commit()

        logger.info("agent_output_recorded", agent_type=agent_type, workflow_id=workflow_id)

    except Exception as e:
        logger.error("agent_output_recording_failed", error=str(e))


def collect_agent_outputs(storage: PortfolioStorage, workflow_id: str) -> dict[str, object]:
    """Collect all agent outputs from a workflow.

    Args:
        storage: PortfolioStorage instance for database access
        workflow_id: ID of the workflow

    Returns:
        Dictionary mapping agent_type to list of outputs
    """
    try:
        result = storage.query(
            "SELECT shared_context FROM agent_workflows WHERE id = $1",
            [workflow_id],
        )

        if result.is_empty():
            return {}

        shared_context = result.get_column("shared_context")[0]
        agents_data = shared_context.get("agents", {})

        # Extract outputs from each agent
        collected: dict[str, object] = {}
        for agent_type, agent_state in agents_data.items():
            collected[agent_type] = agent_state.get("outputs", [])

        return collected

    except Exception as e:
        logger.error("agent_output_collection_failed", error=str(e))
        return {}
