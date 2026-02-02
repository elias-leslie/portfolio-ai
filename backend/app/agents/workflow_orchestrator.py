"""Multi-agent workflow orchestrator for autonomous trading intelligence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.agents.workflows import workflow_agents, workflow_consensus, workflow_lifecycle


class WorkflowOrchestrator:
    """Orchestrate multi-agent workflows for collaborative tasks.

    This class acts as a facade, delegating to specialized modules:
    - workflow_lifecycle: Start, complete, fail workflows
    - workflow_agents: Agent task assignment and output recording
    - workflow_consensus: Conflict resolution
    """

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
        return workflow_lifecycle.start_workflow(
            self.storage,
            workflow_type,
            config,
            agents_involved,
            triggered_by,
            priority,
            max_duration_seconds,
        )

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
        workflow_lifecycle.update_workflow_status(
            self.storage, workflow_id, status, current_step, error
        )

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
        return workflow_agents.assign_task_to_agent(
            self.storage, workflow_id, agent_type, task, context
        )

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
        workflow_agents.record_agent_output(
            self.storage, workflow_id, agent_type, output, confidence
        )

    def collect_agent_outputs(self, workflow_id: str) -> dict[str, object]:
        """Collect all agent outputs from a workflow.

        Args:
            workflow_id: ID of the workflow

        Returns:
            Dictionary mapping agent_type to list of outputs
        """
        return workflow_agents.collect_agent_outputs(self.storage, workflow_id)

    def resolve_conflicts(
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
        return workflow_consensus.resolve_conflicts(
            self.storage, workflow_id, conflicting_outputs, method
        )

    def get_workflow_status(self, workflow_id: str) -> dict[str, object] | None:
        """Get current status of a workflow.

        Args:
            workflow_id: ID of the workflow

        Returns:
            Workflow status dictionary or None if not found
        """
        return workflow_lifecycle.get_workflow_status(self.storage, workflow_id)

    def complete_workflow(self, workflow_id: str, result: dict[str, object]) -> dict[str, object]:
        """Mark a workflow as complete with final result.

        Args:
            workflow_id: ID of the workflow
            result: Final workflow result

        Returns:
            Status dictionary
        """
        return workflow_lifecycle.complete_workflow(self.storage, workflow_id, result)

    def fail_workflow(self, workflow_id: str, error: str, retry: bool = False) -> dict[str, object]:
        """Mark a workflow as failed.

        Args:
            workflow_id: ID of the workflow
            error: Error message
            retry: Whether to retry the workflow

        Returns:
            Status dictionary
        """
        return workflow_lifecycle.fail_workflow(self.storage, workflow_id, error, retry)
