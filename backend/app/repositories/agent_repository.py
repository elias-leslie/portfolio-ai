"""Repository layer for agent run database operations.

Handles all database queries for agent runs, tool calls, and conversation messages.
Extracted from agents/base.py to separate data access from agent logic.

Pattern: Repository handles data access, Agent class handles orchestration.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.agents.types import AgentRunStatus
from app.utils.json_helpers import json_serializer

if TYPE_CHECKING:
    from app.agents.types import ToolInputDict
    from app.storage import PortfolioStorage

# Constants for result truncation
RESULT_SUMMARY_LENGTH = 500  # Max chars for result summary


class AgentRunRepository:
    """Database access layer for agent run operations."""

    def __init__(self, storage: PortfolioStorage):
        """Initialize repository with storage instance.

        Args:
            storage: PortfolioStorage instance for database access
        """
        self.storage = storage
        self._message_sequence: dict[str, int] = {}  # Tracks message sequence per run_id

    def create_run(
        self,
        run_id: str,
        agent_type: str,
        model: str,
        started_at: datetime,
        provider: str | None = None,
        run_type: str = "automated",
        parent_run_id: str | None = None,
        workflow_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Record agent run start in database.

        Args:
            run_id: Unique run identifier
            agent_type: Agent class name
            model: Model identifier
            started_at: Run start timestamp
            provider: LLM provider (gemini, claude, anthropic_api)
            run_type: Type of run (automated, user_chat, cross_validation)
            parent_run_id: Parent run ID for linked runs (e.g., follow-up discussions)
            workflow_id: Associated workflow ID
            user_id: User ID for multi-user support
        """
        self.storage.insert_dict(
            "agent_runs",
            {
                "id": run_id,
                "agent_type": agent_type,
                "started_at": started_at.isoformat() if started_at else None,
                "completed_at": None,
                "status": AgentRunStatus.RUNNING.value,
                "num_ideas": 0,
                "cost_usd": 0.0,
                "error_message": None,
                "metadata": None,
                "celery_task_id": None,
                "provider": provider,
                "model": model,
                "cli_command": None,
                "exit_code": None,
                "duration_ms": None,
                "token_usage": None,
                "session_id": None,
                "run_type": run_type,
                "parent_run_id": parent_run_id,
                "workflow_id": workflow_id,
                "user_id": user_id,
            },
        )
        # Track message sequence for this run
        self._message_sequence[run_id] = 0

    def complete_run(
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
            token_usage: Token usage stats {input_tokens, output_tokens, total_tokens}
            exit_code: CLI process exit code (if applicable)
        """
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE agent_runs
                SET completed_at = ?,
                    status = ?,
                    num_ideas = ?,
                    error_message = ?,
                    duration_ms = ?,
                    token_usage = ?,
                    exit_code = ?
                WHERE id = ?
                """,
                [
                    completed_at,
                    status,
                    num_ideas,
                    error_message,
                    duration_ms,
                    json.dumps(token_usage) if token_usage else None,
                    exit_code or 0,
                    run_id,
                ],
            )
            conn.commit()  # Commit the update

    def record_tool_call(
        self,
        run_id: str,
        tool_name: str,
        parameters: ToolInputDict,
        result: object,
        duration_ms: int,
    ) -> None:
        """Record tool call in database.

        Args:
            run_id: Agent run ID
            tool_name: Name of the tool that was called
            parameters: Tool input parameters
            result: Tool execution result
            duration_ms: Execution duration in milliseconds
        """
        tool_call_id = str(uuid.uuid4())

        # Summarize result
        result_summary = str(result)[:RESULT_SUMMARY_LENGTH]

        self.storage.insert_dict(
            "agent_tool_calls",
            {
                "id": tool_call_id,
                "agent_run_id": run_id,
                "tool_name": tool_name,
                "parameters": json.dumps(parameters, default=json_serializer),
                "response_summary": result_summary,
                "duration_ms": duration_ms,
                "called_at": datetime.now(UTC).isoformat(),
            },
        )

    def store_message(
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
            metadata: Optional metadata (e.g., tool name, tool_use_id)
        """
        # Get and increment sequence number (initialized in create_run)
        sequence_num = self._message_sequence[run_id]
        self._message_sequence[run_id] = sequence_num + 1

        self.storage.insert_dict(
            "agent_conversation_messages",
            {
                "agent_run_id": run_id,
                "sequence_num": sequence_num,
                "role": role,
                "content": content,
                "token_count": token_count,
                "metadata": json.dumps(metadata) if metadata else None,
            },
        )
