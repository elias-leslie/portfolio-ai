"""Base agent class for portfolio-ai agents.

This module provides the base Agent class that all agents inherit from.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from anthropic import Anthropic

from ..logging_config import get_logger

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


class Agent(ABC):
    """Base class for AI agents.

    Provides common functionality for tool calling, execution tracking,
    and interaction with Claude API.
    """

    def __init__(
        self,
        storage: PortfolioStorage,
        anthropic_client: Anthropic | None = None,
        model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        """Initialize agent.

        Args:
            storage: PortfolioStorage instance
            anthropic_client: Anthropic client (or create new one)
            model: Claude model to use
        """
        self.storage = storage
        self.client = anthropic_client or Anthropic()
        self.model = model
        self.agent_type = self.__class__.__name__

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent.

        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    def get_tools(self) -> list[dict[str, Any]]:
        """Get tool definitions for this agent.

        Returns:
            List of tool definition dicts for Claude API
        """
        pass

    @abstractmethod
    def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        """Execute a tool call.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool parameters

        Returns:
            Tool execution result
        """
        pass

    def _extract_final_response(self, response: Any) -> str:
        """Extract final text response from API response.

        Args:
            response: Anthropic API response

        Returns:
            Extracted text content
        """
        final_text = ""
        for block in response.content:
            if block.type == "text":
                final_text += block.text
        return final_text

    def _handle_completion(
        self,
        run_id: str,
        started_at: datetime,
        tool_calls_made: list[dict[str, Any]],
        iteration: int,
        final_text: str,
    ) -> dict[str, Any]:
        """Handle successful agent run completion.

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            tool_calls_made: List of tool calls made
            iteration: Current iteration number
            final_text: Final response text

        Returns:
            Completion result dict
        """
        completed_at = datetime.now(UTC)
        duration_s = (completed_at - started_at).total_seconds()

        logger.info(
            "agent_run_completed",
            run_id=run_id,
            agent_type=self.agent_type,
            num_tool_calls=len(tool_calls_made),
            iterations=iteration + 1,
            duration_s=round(duration_s, 2),
            status="completed",
        )

        self._record_run_complete(
            run_id, completed_at, "completed", len(tool_calls_made)
        )

        return {
            "status": "completed",
            "response": final_text,
            "tool_calls": tool_calls_made,
            "iterations": iteration + 1,
        }

    def _process_tool_calls(
        self,
        response: Any,
        run_id: str,
        tool_calls_made: list[dict[str, Any]],
    ) -> tuple[list[Any], list[dict[str, Any]]]:
        """Process tool calls from API response.

        Args:
            response: Anthropic API response with tool_use blocks
            run_id: Unique run identifier
            tool_calls_made: List to append tool calls to (modified in place)

        Returns:
            Tuple of (assistant_content, tool_results) for next message
        """
        assistant_content = []
        tool_results = []

        for block in response.content:
            assistant_content.append(block)

            if block.type == "tool_use":
                tool_start = datetime.now(UTC)
                tool_input = cast(dict[str, Any], block.input)

                # Execute tool
                result = self.execute_tool(block.name, tool_input)

                tool_end = datetime.now(UTC)
                duration_ms = int((tool_end - tool_start).total_seconds() * 1000)

                # Record tool call
                self._record_tool_call(
                    run_id, block.name, tool_input, result, duration_ms
                )

                tool_calls_made.append(
                    {"name": block.name, "input": tool_input, "result": result}
                )

                # Add tool result to conversation
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    }
                )

        return assistant_content, tool_results

    def run(self, user_prompt: str, max_iterations: int = 10) -> dict[str, Any]:
        """Run the agent with a user prompt.

        Args:
            user_prompt: User's prompt/request
            max_iterations: Maximum tool call iterations

        Returns:
            Dict with final response and metadata
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)

        logger.info(
            "agent_run_started",
            run_id=run_id,
            agent_type=self.agent_type,
            model=self.model,
            max_iterations=max_iterations,
        )

        self._record_run_start(run_id, started_at)

        try:
            messages = [{"role": "user", "content": user_prompt}]
            tool_calls_made: list[dict[str, Any]] = []

            for iteration in range(max_iterations):
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=self.get_system_prompt(),
                    tools=self.get_tools(),  # type: ignore[arg-type]
                    messages=messages,  # type: ignore[arg-type]
                )

                if response.stop_reason == "end_turn":
                    final_text = self._extract_final_response(response)
                    return self._handle_completion(
                        run_id, started_at, tool_calls_made, iteration, final_text
                    )

                if response.stop_reason == "tool_use":
                    assistant_content, tool_results = self._process_tool_calls(
                        response, run_id, tool_calls_made
                    )

                    # Continue conversation with tool results
                    messages.append({"role": "assistant", "content": assistant_content})  # type: ignore[dict-item]
                    messages.append({"role": "user", "content": tool_results})  # type: ignore[dict-item]

                else:
                    # Unexpected stop reason
                    self._record_run_complete(
                        run_id,
                        datetime.now(UTC),
                        "error",
                        len(tool_calls_made),
                        f"Unexpected stop reason: {response.stop_reason}",
                    )
                    return {
                        "status": "error",
                        "error": f"Unexpected stop reason: {response.stop_reason}",
                        "tool_calls": tool_calls_made,
                    }

            # Max iterations reached
            self._record_run_complete(
                run_id, datetime.now(UTC), "max_iterations", len(tool_calls_made)
            )
            return {
                "status": "max_iterations",
                "tool_calls": tool_calls_made,
                "iterations": max_iterations,
            }

        except Exception as e:
            logger.error(f"Agent run {run_id} failed: {e}")
            self._record_run_complete(run_id, datetime.now(UTC), "error", 0, str(e))
            return {"status": "error", "error": str(e)}

    def _record_run_start(self, run_id: str, started_at: datetime) -> None:
        """Record agent run start in database."""
        self.storage.insert_dict(
            "agent_runs",
            {
                "id": run_id,
                "agent_type": self.agent_type,
                "started_at": started_at,
                "completed_at": None,
                "status": "running",
                "num_ideas": 0,
                "cost_usd": 0.0,
                "error_message": None,
                "metadata": None,
                "celery_task_id": None,
            },
        )

    def _record_run_complete(
        self,
        run_id: str,
        completed_at: datetime,
        status: str,
        num_ideas: int,
        error_message: str | None = None,
    ) -> None:
        """Record agent run completion in database."""
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE agent_runs
                SET completed_at = ?,
                    status = ?,
                    num_ideas = ?,
                    error_message = ?
                WHERE id = ?
                """,
                [completed_at, status, num_ideas, error_message, run_id],
            )
            conn.commit()  # Commit the update

    def _record_tool_call(
        self,
        run_id: str,
        tool_name: str,
        parameters: dict[str, Any],
        result: Any,
        duration_ms: int,
    ) -> None:
        """Record tool call in database."""
        tool_call_id = str(uuid.uuid4())

        # Summarize result
        result_summary = str(result)[:500]

        self.storage.insert_dict(
            "agent_tool_calls",
            {
                "id": tool_call_id,
                "agent_run_id": run_id,
                "tool_name": tool_name,
                "parameters": json.dumps(parameters),
                "response_summary": result_summary,
                "duration_ms": duration_ms,
                "called_at": datetime.now(UTC),
            },
        )
