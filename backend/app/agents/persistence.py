"""Agent persistence layer for database recording.

This module handles all database operations for agent runs, tool calls,
and conversation messages. Extracted from base.py for single responsibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..repositories import AgentRunRepository
    from .types import ToolInputDict


class AgentPersistenceMixin:
    """Mixin providing database persistence methods for agents.

    All methods delegate to the AgentRunRepository for actual DB operations.
    """

    repository: AgentRunRepository
    agent_type: str
    model: str

    def _record_run_start(
        self,
        run_id: str,
        started_at: datetime,
        provider: str | None = None,
        model: str | None = None,
        run_type: str = "automated",
        parent_run_id: str | None = None,
        workflow_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Record agent run start in database.

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            provider: LLM provider (gemini, claude, anthropic_api)
            model: Model identifier
            run_type: Type of run (automated, user_chat, cross_validation)
            parent_run_id: Parent run ID for linked runs
            workflow_id: Associated workflow ID
            user_id: User ID for multi-user support
        """
        self.repository.create_run(
            run_id=run_id,
            agent_type=self.agent_type,
            model=model or self.model,
            started_at=started_at,
            provider=provider,
            run_type=run_type,
            parent_run_id=parent_run_id,
            workflow_id=workflow_id,
            user_id=user_id,
        )

    def _record_run_complete(
        self,
        run_id: str,
        completed_at: datetime,
        status: str,
        num_ideas: int,
        error_message: str | None = None,
        duration_ms: int | None = None,
        token_usage: dict[str, int] | None = None,
        exit_code: int | None = None,
    ) -> None:
        """Record agent run completion in database.

        Args:
            run_id: Unique run identifier
            completed_at: Run completion timestamp
            status: Final status (completed, error, max_iterations)
            num_ideas: Number of ideas generated
            error_message: Error message if failed
            duration_ms: Execution duration in milliseconds
            token_usage: Token usage stats
            exit_code: CLI process exit code
        """
        self.repository.complete_run(
            run_id=run_id,
            completed_at=completed_at,
            status=status,
            num_ideas=num_ideas,
            error_message=error_message,
            duration_ms=duration_ms,
            token_usage=token_usage,
            exit_code=exit_code,
        )

    def _record_tool_call(
        self,
        run_id: str,
        tool_name: str,
        parameters: ToolInputDict,
        result: object,
        duration_ms: int,
    ) -> None:
        """Record tool call in database."""
        self.repository.record_tool_call(
            run_id=run_id,
            tool_name=tool_name,
            parameters=parameters,
            result=result,
            duration_ms=duration_ms,
        )

    def _store_conversation_message(
        self,
        run_id: str,
        role: str,
        content: str,
        token_count: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Store a conversation message for the agent run.

        Args:
            run_id: Agent run ID
            role: Message role (user, assistant, system, tool_call, tool_result)
            content: Message content
            token_count: Optional token count for this message
            metadata: Optional metadata
        """
        self.repository.store_message(
            run_id=run_id,
            role=role,
            content=content,
            token_count=token_count,
            metadata=metadata,
        )
