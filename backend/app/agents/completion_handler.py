"""Completion handling for agent runs.

This module handles agent run completion, including success, error,
and max iterations scenarios. Extracted from base.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ..logging_config import get_logger
from ..utils.formatters import calculate_duration_ms
from .types import AgentRunStatus

if TYPE_CHECKING:
    from .base import AgentRunResult, ToolCallRecord

logger = get_logger(__name__)


def get_completion_metadata(started_at: datetime) -> tuple[datetime, int]:
    """Calculate completion time and duration.

    Args:
        started_at: When the operation started

    Returns:
        Tuple of (completed_at, duration_ms)
    """
    completed_at = datetime.now(UTC)
    duration_ms = calculate_duration_ms(started_at, completed_at)
    return completed_at, duration_ms


class CompletionHandlerMixin:
    """Mixin providing completion handling methods for agents.

    Requires _record_run_complete method from AgentPersistenceMixin.
    """

    agent_type: str

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
        """Record agent run completion (implemented by AgentPersistenceMixin)."""
        raise NotImplementedError

    def _log_completion(
        self,
        run_id: str,
        tool_calls_made: list[ToolCallRecord],
        iteration: int,
        duration_ms: int,
        token_usage: dict[str, int] | None,
    ) -> None:
        """Log agent run completion.

        Args:
            run_id: Unique run identifier
            tool_calls_made: List of tool calls made
            iteration: Current iteration number
            duration_ms: Execution duration in milliseconds
            token_usage: Token usage stats from LLM response
        """
        logger.info(
            "agent_run_completed",
            run_id=run_id,
            agent_type=self.agent_type,
            num_tool_calls=len(tool_calls_made),
            iterations=iteration + 1,
            duration_s=round(duration_ms / 1000.0, 2),
            status=AgentRunStatus.COMPLETED.value,
            token_usage=token_usage,
        )

    def _handle_completion(
        self,
        run_id: str,
        started_at: datetime,
        tool_calls_made: list[ToolCallRecord],
        iteration: int,
        final_text: str,
        token_usage: dict[str, int] | None = None,
    ) -> AgentRunResult:
        """Handle successful agent run completion.

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            tool_calls_made: List of tool calls made
            iteration: Current iteration number
            final_text: Final response text
            token_usage: Token usage stats from LLM response

        Returns:
            Completion result dict
        """
        completed_at, duration_ms = get_completion_metadata(started_at)

        self._log_completion(run_id, tool_calls_made, iteration, duration_ms, token_usage)

        self._record_run_complete(
            run_id,
            completed_at,
            AgentRunStatus.COMPLETED.value,
            len(tool_calls_made),
            duration_ms=duration_ms,
            token_usage=token_usage,
        )

        return {
            "status": AgentRunStatus.COMPLETED.value,
            "response": final_text,
            "tool_calls": tool_calls_made,
            "iterations": iteration + 1,
            "run_id": run_id,
        }

    def _handle_unexpected_stop_reason(
        self,
        run_id: str,
        started_at: datetime,
        stop_reason: str | None,
        tool_calls_made: list[ToolCallRecord],
        token_usage: dict[str, int] | None = None,
    ) -> AgentRunResult:
        """Handle unexpected stop reason in agent execution.

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            stop_reason: The unexpected stop reason from the LLM
            tool_calls_made: List of tool calls made during the run
            token_usage: Optional token usage stats

        Returns:
            AgentRunResult with error status
        """
        completed_at, duration_ms = get_completion_metadata(started_at)
        error_msg = f"Unexpected stop reason: {stop_reason}"

        self._record_run_complete(
            run_id,
            completed_at,
            AgentRunStatus.ERROR.value,
            len(tool_calls_made),
            error_msg,
            duration_ms=duration_ms,
            token_usage=token_usage,
        )

        return {
            "status": AgentRunStatus.ERROR.value,
            "error": error_msg,
            "tool_calls": tool_calls_made,
            "run_id": run_id,
        }

    def _handle_max_iterations(
        self,
        run_id: str,
        started_at: datetime,
        max_iterations: int,
        tool_calls_made: list[ToolCallRecord],
        token_usage: dict[str, int] | None = None,
    ) -> AgentRunResult:
        """Handle max iterations reached in agent execution.

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            max_iterations: The maximum iterations limit
            tool_calls_made: List of tool calls made during the run
            token_usage: Optional token usage stats

        Returns:
            AgentRunResult with max_iterations status
        """
        completed_at, duration_ms = get_completion_metadata(started_at)

        self._record_run_complete(
            run_id,
            completed_at,
            AgentRunStatus.MAX_ITERATIONS.value,
            len(tool_calls_made),
            duration_ms=duration_ms,
            token_usage=token_usage,
        )

        return {
            "status": AgentRunStatus.MAX_ITERATIONS.value,
            "tool_calls": tool_calls_made,
            "iterations": max_iterations,
            "run_id": run_id,
        }
