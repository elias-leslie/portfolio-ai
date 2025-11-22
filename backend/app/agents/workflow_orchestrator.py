"""Multi-agent workflow orchestrator for autonomous trading intelligence."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.logging_config import get_logger

logger = get_logger(__name__)


class WorkflowOrchestrator:
    """Orchestrate multi-agent workflows for collaborative tasks."""

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize workflow orchestrator.

        Args:
            storage: PortfolioStorage instance for database access
        """
        self.storage = storage

    def start_workflow(
        self,
        workflow_type: str,
        config: dict[str, object] | None = None,
        agents_involved: list[str] | None = None,
        triggered_by: str | None = None,
        priority: int = 5,
        max_duration_seconds: int = 3600,
    ) -> dict[str, object]:
        """Start a new multi-agent workflow.

        Args:
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

            with self.storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO agent_workflows (
                        id, workflow_type, status, current_step, agents_involved,
                        shared_context, triggered_by, priority, max_duration_seconds,
                        created_at, last_updated_at
                    ) VALUES ($1, $2, $3, $4, $5::TEXT[], $6::JSONB, $7, $8, $9, $10, $11)
                    """,
                    [
                        workflow_id,
                        workflow_type,
                        "pending",
                        "initializing",
                        "{" + ",".join(agents_list) + "}"
                        if agents_list
                        else "{}",  # PostgreSQL array literal format
                        json.dumps(shared_context),
                        triggered_by,
                        priority,
                        max_duration_seconds,
                        datetime.now(UTC),
                        datetime.now(UTC),
                    ],
                )
                conn.commit()  # Explicitly commit the transaction

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
        self,
        workflow_id: str,
        status: Literal["pending", "running", "blocked", "complete", "failed"],
        current_step: str | None = None,
        error: str | None = None,
    ) -> None:
        """Update workflow status and current step.

        Args:
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
            result = self.storage.query(
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
            set_parts.append(f"{key} = ${i}")  # validated: column from whitelist
            values.append(value)

        values.append(workflow_id)  # WHERE clause
        set_clause = ", ".join(set_parts)

        with self.storage.connection() as conn:
            conn.execute(
                f"UPDATE agent_workflows SET {set_clause} WHERE id = ${len(values)}",  # validated: columns from whitelist
                [str(v) for v in values],
            )
            conn.commit()

        logger.info(f"Workflow {workflow_id} status updated to {status}")

    def assign_task_to_agent(
        self,
        workflow_id: str,
        agent_type: str,
        task: str,
        context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Assign a task to a specific agent in a workflow.

        Args:
            workflow_id: ID of the workflow
            agent_type: Type of agent to assign task to
            task: Task description
            context: Optional task-specific context

        Returns:
            Result dictionary with assignment status
        """
        try:
            # Get current shared context
            result = self.storage.query(
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
            with self.storage.connection() as conn:
                conn.execute(
                    "UPDATE agent_workflows SET shared_context = $1::JSONB, last_updated_at = $2 WHERE id = $3",
                    [json.dumps(shared_context), datetime.now(UTC), workflow_id],
                )
                conn.commit()

            logger.info(f"Assigned task to {agent_type} in workflow {workflow_id}: {task[:100]}")

            return {
                "status": "assigned",
                "workflow_id": workflow_id,
                "agent_type": agent_type,
                "task": task,
            }

        except Exception as e:
            logger.error(f"Failed to assign task: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    def record_agent_output(
        self,
        workflow_id: str,
        agent_type: str,
        output: dict[str, object],
        confidence: float = 1.0,
    ) -> None:
        """Record output from an agent in a workflow.

        Args:
            workflow_id: ID of the workflow
            agent_type: Type of agent
            output: Agent's output data
            confidence: Confidence level 0-1
        """
        try:
            # Get current shared context
            result = self.storage.query(
                "SELECT shared_context FROM agent_workflows WHERE id = $1",
                [workflow_id],
            )

            if result.is_empty():
                logger.error(f"Workflow {workflow_id} not found")
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
            with self.storage.connection() as conn:
                conn.execute(
                    "UPDATE agent_workflows SET shared_context = $1::JSONB, last_updated_at = $2 WHERE id = $3",
                    [json.dumps(shared_context), datetime.now(UTC), workflow_id],
                )
                conn.commit()

            logger.info(f"Recorded output from {agent_type} in workflow {workflow_id}")

        except Exception as e:
            logger.error(f"Failed to record agent output: {e}")

    def collect_agent_outputs(self, workflow_id: str) -> dict[str, object]:
        """Collect all agent outputs from a workflow.

        Args:
            workflow_id: ID of the workflow

        Returns:
            Dictionary mapping agent_type to list of outputs
        """
        try:
            result = self.storage.query(
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
            logger.error(f"Failed to collect agent outputs: {e}")
            return {}

    def resolve_conflicts(  # noqa: PLR0911
        self,
        workflow_id: str,
        conflicting_outputs: dict[str, object],
        method: Literal["voting", "majority", "confidence", "first"] = "confidence",
    ) -> dict[str, object]:
        """Resolve conflicts between agent outputs using specified method.

        Args:
            workflow_id: ID of the workflow
            conflicting_outputs: Dictionary mapping agent_type to output
            method: Resolution method:
                - 'voting': Use explicit votes from agents
                - 'majority': Simple majority of agent outputs
                - 'confidence': Weighted by confidence scores
                - 'first': Use first agent's output (fallback)

        Returns:
            Resolved output with metadata about resolution
        """
        try:
            if not conflicting_outputs:
                return {
                    "status": "error",
                    "error": "No outputs to resolve",
                }

            if len(conflicting_outputs) == 1:
                # No conflict, return single output
                agent_type = next(iter(conflicting_outputs.keys()))
                return {
                    "status": "resolved",
                    "method": "single_agent",
                    "result": conflicting_outputs[agent_type],
                    "resolved_by": agent_type,
                }

            # Get workflow context for votes and confidence
            result = self.storage.query(
                "SELECT shared_context FROM agent_workflows WHERE id = $1",
                [workflow_id],
            )

            if result.is_empty():
                logger.warning(f"Workflow {workflow_id} not found, using first output as fallback")
                first_agent = next(iter(conflicting_outputs.keys()))
                return {
                    "status": "resolved",
                    "method": "fallback_first",
                    "result": conflicting_outputs[first_agent],
                    "resolved_by": first_agent,
                }

            shared_context = result.get_column("shared_context")[0]

            if method == "confidence":
                # Use confidence-weighted resolution
                max_confidence = 0.0
                best_agent = None
                best_output = None

                for agent_type, _outputs in conflicting_outputs.items():
                    if agent_type in shared_context.get("agents", {}):
                        agent_outputs = shared_context["agents"][agent_type].get("outputs", [])
                        if agent_outputs:
                            latest = agent_outputs[-1]
                            confidence = latest.get("confidence", 0.0)
                            if confidence > max_confidence:
                                max_confidence = confidence
                                best_agent = agent_type
                                best_output = latest.get("output")

                if best_output is not None:
                    return {
                        "status": "resolved",
                        "method": "confidence",
                        "result": best_output,
                        "resolved_by": best_agent,
                        "confidence": max_confidence,
                    }

            elif method == "voting":
                # Use explicit votes
                votes = shared_context.get("votes", {})
                if votes:
                    # Count votes (simplified - assumes single decision)
                    vote_counts: dict[str, int] = {}
                    for _decision_id, decision_votes in votes.items():
                        for vote_record in decision_votes:
                            vote_val = vote_record.get("vote")
                            vote_counts[vote_val] = vote_counts.get(vote_val, 0) + 1

                    # Get majority vote
                    if vote_counts:
                        majority_vote = max(vote_counts, key=vote_counts.get)  # type: ignore
                        return {
                            "status": "resolved",
                            "method": "voting",
                            "result": majority_vote,
                            "vote_counts": vote_counts,
                        }

            elif method == "majority":
                # Simple majority - count identical outputs
                output_counts: dict[str, int] = {}
                output_map: dict[str, object] = {}

                for _agent_type, output in conflicting_outputs.items():
                    output_str = str(output)  # Simple comparison
                    output_counts[output_str] = output_counts.get(output_str, 0) + 1
                    output_map[output_str] = output

                majority_output_str = max(output_counts, key=output_counts.get)  # type: ignore
                return {
                    "status": "resolved",
                    "method": "majority",
                    "result": output_map[majority_output_str],
                    "count": output_counts[majority_output_str],
                    "total": len(conflicting_outputs),
                }

            # Fallback: Use first agent's output
            first_agent = next(iter(conflicting_outputs.keys()))
            logger.warning(
                f"Using fallback resolution for workflow {workflow_id}: first agent ({first_agent})"
            )

            return {
                "status": "resolved",
                "method": "fallback_first",
                "result": conflicting_outputs[first_agent],
                "resolved_by": first_agent,
            }

        except Exception as e:
            logger.error(f"Failed to resolve conflicts: {e}")
            # Ultimate fallback
            if conflicting_outputs:
                first_agent = next(iter(conflicting_outputs.keys()))
                return {
                    "status": "error_fallback",
                    "method": "error_first",
                    "result": conflicting_outputs[first_agent],
                    "resolved_by": first_agent,
                    "error": str(e),
                }
            return {
                "status": "error",
                "error": str(e),
            }

    def get_workflow_status(self, workflow_id: str) -> dict[str, object] | None:
        """Get current status of a workflow.

        Args:
            workflow_id: ID of the workflow

        Returns:
            Workflow status dictionary or None if not found
        """
        try:
            result = self.storage.query(
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

    def complete_workflow(self, workflow_id: str, result: dict[str, object]) -> dict[str, object]:
        """Mark a workflow as complete with final result.

        Args:
            workflow_id: ID of the workflow
            result: Final workflow result

        Returns:
            Status dictionary
        """
        try:
            with self.storage.connection() as conn:
                conn.execute(
                    """
                    UPDATE agent_workflows
                    SET status = 'complete', result = $1::JSONB, completed_at = $2, last_updated_at = $2
                    WHERE id = $3
                    """,
                    [json.dumps(result), datetime.now(UTC), workflow_id],
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

    def fail_workflow(self, workflow_id: str, error: str, retry: bool = False) -> dict[str, object]:
        """Mark a workflow as failed.

        Args:
            workflow_id: ID of the workflow
            error: Error message
            retry: Whether to retry the workflow

        Returns:
            Status dictionary
        """
        try:
            if retry:
                # Increment retry count
                result = self.storage.query(
                    "SELECT retry_count, max_retries FROM agent_workflows WHERE id = $1",
                    [workflow_id],
                )

                if not result.is_empty():
                    retry_count = result.get_column("retry_count")[0]
                    max_retries = result.get_column("max_retries")[0]

                    if retry_count < max_retries:
                        with self.storage.connection() as conn:
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
            with self.storage.connection() as conn:
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
