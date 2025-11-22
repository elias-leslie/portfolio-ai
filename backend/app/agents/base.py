"""Base agent class for portfolio-ai agents.

This module provides the base Agent class that all agents inherit from.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict, cast

from anthropic import Anthropic

from ..logging_config import get_logger
from .llm_client import LLMClient
from .types import ToolInputDict

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


class ToolCallRecord(TypedDict):
    """Record of a tool call made by the agent."""

    name: str
    input: ToolInputDict
    result: object


class AgentRunResult(TypedDict, total=False):
    """Result of an agent run."""

    status: str
    response: str
    tool_calls: list[ToolCallRecord]
    iterations: int
    error: str
    run_id: str


class Agent(ABC):
    """Base class for AI agents.

    Provides common functionality for tool calling, execution tracking,
    and interaction with Claude API.
    """

    def __init__(
        self,
        storage: PortfolioStorage,
        llm_client: LLMClient | None = None,
        anthropic_client: Anthropic | None = None,
        model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        """Initialize agent.

        Args:
            storage: PortfolioStorage instance
            llm_client: LLM client (DualProviderClient for CLI providers)
            anthropic_client: Anthropic client (deprecated, for backwards compatibility)
            model: Claude model to use

        Note:
            If llm_client is provided, it takes precedence over anthropic_client.
            Tool calling currently requires anthropic_client (CLI tool support coming soon).
        """
        self.storage = storage
        self.llm_client = llm_client
        self.client = anthropic_client or Anthropic()  # Keep for tool calling support
        self.model = model
        self.agent_type = self.__class__.__name__

    @staticmethod
    def _json_serializer(value: object) -> object:
        """Serialize non-JSON-compatible values (e.g., datetime) to strings."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            return value.isoformat()
        return value

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent.

        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    def get_tools(self) -> list[dict[str, object]]:
        """Get tool definitions for this agent.

        Returns:
            List of tool definition dicts for Claude API
        """
        pass

    @abstractmethod
    def execute_tool(self, tool_name: str, tool_input: ToolInputDict) -> object:
        """Execute a tool call.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool parameters

        Returns:
            Tool execution result
        """
        pass

    def _extract_final_response(self, response: object) -> str:
        """Extract final text response from API response.

        Args:
            response: Anthropic API response

        Returns:
            Extracted text content
        """
        final_text = ""
        for block in response.content:  # type: ignore[attr-defined]
            if block.type == "text":
                final_text += block.text
        return final_text

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
        completed_at = datetime.now(UTC)
        duration_s = (completed_at - started_at).total_seconds()
        duration_ms = int(duration_s * 1000)

        logger.info(
            "agent_run_completed",
            run_id=run_id,
            agent_type=self.agent_type,
            num_tool_calls=len(tool_calls_made),
            iterations=iteration + 1,
            duration_s=round(duration_s, 2),
            status="completed",
            token_usage=token_usage,
        )

        self._record_run_complete(
            run_id,
            completed_at,
            "completed",
            len(tool_calls_made),
            duration_ms=duration_ms,
            token_usage=token_usage,
        )

        return {
            "status": "completed",
            "response": final_text,
            "tool_calls": tool_calls_made,
            "iterations": iteration + 1,
            "run_id": run_id,
        }

    def _process_tool_calls(
        self,
        response: object,
        run_id: str,
        tool_calls_made: list[ToolCallRecord],
    ) -> tuple[list[object], list[dict[str, object]]]:
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

        for block in response.content:  # type: ignore[attr-defined]
            assistant_content.append(block)

            if block.type == "tool_use":
                tool_start = datetime.now(UTC)
                tool_input = cast(ToolInputDict, block.input)

                # Execute tool
                result = self.execute_tool(block.name, tool_input)

                tool_end = datetime.now(UTC)
                duration_ms = int((tool_end - tool_start).total_seconds() * 1000)

                # Record tool call
                self._record_tool_call(run_id, block.name, tool_input, result, duration_ms)

                tool_calls_made.append({"name": block.name, "input": tool_input, "result": result})

                # Add tool result to conversation
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=self._json_serializer),
                    }
                )

        return assistant_content, tool_results

    def run(self, user_prompt: str, max_iterations: int = 10) -> AgentRunResult:
        """Run the agent with a user prompt.

        Args:
            user_prompt: User's prompt/request
            max_iterations: Maximum tool call iterations

        Returns:
            Dict with final response and metadata
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)

        # Determine provider and model
        provider = None
        model = self.model
        if self.llm_client:
            # Will be set from LLMResponse after first call
            provider = "cli"  # Placeholder, will be updated after first response
        else:
            provider = "anthropic_api"

        logger.info(
            "agent_run_started",
            run_id=run_id,
            agent_type=self.agent_type,
            provider=provider,
            model=model,
            max_iterations=max_iterations,
        )

        self._record_run_start(run_id, started_at, provider=provider, model=model)

        try:
            # Use LLM client if provided, otherwise fall back to Anthropic API
            if self.llm_client:
                return self._run_with_llm_client(run_id, started_at, user_prompt, max_iterations)
            return self._run_with_anthropic_api(run_id, started_at, user_prompt, max_iterations)

        except Exception as e:
            logger.error(f"Agent run {run_id} failed: {e}")
            self._record_run_complete(run_id, datetime.now(UTC), "error", 0, str(e))
            return {"status": "error", "error": str(e), "run_id": run_id}

    def _run_with_llm_client(
        self, run_id: str, started_at: datetime, user_prompt: str, max_iterations: int
    ) -> AgentRunResult:
        """Run agent using LLM client with JSON-based tool calling protocol.

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            user_prompt: User's prompt/request
            max_iterations: Maximum tool call iterations

        Returns:
            Agent run result dict
        """
        conversation_history: list[dict[str, object]] = []
        current_prompt = user_prompt
        tool_calls_made: list[ToolCallRecord] = []

        # Track accumulated token usage across all iterations
        total_token_usage: dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

        for iteration in range(max_iterations):
            # Generate with tools
            response = self.llm_client.generate_with_tools(  # type: ignore[union-attr]
                prompt=current_prompt,
                tools=self.get_tools(),
                system=self.get_system_prompt(),
                conversation_history=conversation_history,
                max_tokens=4096,
                temperature=1.0,
            )

            # Accumulate token usage from this iteration
            if response.usage:
                total_token_usage["input_tokens"] += response.usage.get("prompt_tokens", 0)
                total_token_usage["output_tokens"] += response.usage.get("completion_tokens", 0)
                total_token_usage["total_tokens"] += response.usage.get("total_tokens", 0)

            # Update provider/model in database on first response (get actual values from CLI)
            if iteration == 0 and response.provider and response.model:
                with self.storage.connection() as conn:
                    conn.execute(
                        "UPDATE agent_runs SET provider = ?, model = ? WHERE id = ?",
                        [response.provider, response.model, run_id],
                    )
                    conn.commit()

            if response.stop_reason == "end_turn":
                # Agent finished - provide final answer
                return self._handle_completion(
                    run_id,
                    started_at,
                    tool_calls_made,
                    iteration,
                    response.content,
                    total_token_usage,
                )

            if response.stop_reason == "tool_use":
                # Agent wants to call tools
                tool_results = []

                for tool_call in response.tool_calls:
                    tool_start = datetime.now(UTC)

                    # Execute tool
                    result = self.execute_tool(tool_call["name"], tool_call["parameters"])

                    tool_end = datetime.now(UTC)
                    duration_ms = int((tool_end - tool_start).total_seconds() * 1000)

                    # Record tool call
                    self._record_tool_call(
                        run_id, tool_call["name"], tool_call["parameters"], result, duration_ms
                    )

                    tool_calls_made.append(
                        {
                            "name": tool_call["name"],
                            "input": tool_call["parameters"],
                            "result": result,
                        }
                    )

                    tool_results.append(
                        {
                            "name": tool_call["name"],
                            "parameters": tool_call["parameters"],
                            "result": result,
                        }
                    )

                # Format tool results for next turn
                current_prompt = self._format_tool_results(tool_results)

                # Update conversation history
                conversation_history.append(
                    {
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": response.tool_calls,
                    }
                )
                conversation_history.append(
                    {
                        "role": "user",
                        "content": current_prompt,
                    }
                )

            else:
                # Unexpected stop reason
                completed_at = datetime.now(UTC)
                duration_ms = int((completed_at - started_at).total_seconds() * 1000)
                self._record_run_complete(
                    run_id,
                    completed_at,
                    "error",
                    len(tool_calls_made),
                    f"Unexpected stop reason: {response.stop_reason}",
                    duration_ms=duration_ms,
                    token_usage=total_token_usage,
                )
                return {
                    "status": "error",
                    "error": f"Unexpected stop reason: {response.stop_reason}",
                    "tool_calls": tool_calls_made,
                    "run_id": run_id,
                }

        # Max iterations reached
        completed_at = datetime.now(UTC)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        self._record_run_complete(
            run_id,
            completed_at,
            "max_iterations",
            len(tool_calls_made),
            duration_ms=duration_ms,
            token_usage=total_token_usage,
        )
        return {
            "status": "max_iterations",
            "tool_calls": tool_calls_made,
            "iterations": max_iterations,
            "run_id": run_id,
        }

    def _run_with_anthropic_api(
        self, run_id: str, started_at: datetime, user_prompt: str, max_iterations: int
    ) -> AgentRunResult:
        """Run agent using Anthropic API with native tool calling (legacy).

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            user_prompt: User's prompt/request
            max_iterations: Maximum tool call iterations

        Returns:
            Agent run result dict
        """
        messages = [{"role": "user", "content": user_prompt}]
        tool_calls_made: list[ToolCallRecord] = []

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
                    "run_id": run_id,
                }

        # Max iterations reached
        self._record_run_complete(run_id, datetime.now(UTC), "max_iterations", len(tool_calls_made))
        return {
            "status": "max_iterations",
            "tool_calls": tool_calls_made,
            "iterations": max_iterations,
            "run_id": run_id,
        }

    def _format_tool_results(self, tool_results: list[dict[str, object]]) -> str:
        """Format tool results for next conversation turn.

        Args:
            tool_results: List of tool result dicts

        Returns:
            Formatted string with tool results
        """
        parts = ["TOOL RESULTS:", "=" * 60]

        for tr in tool_results:
            parts.append(f"\nTool: {tr['name']}")
            parts.append(f"Parameters: {json.dumps(tr['parameters'])}")
            parts.append(
                f"Result:\n{json.dumps(tr['result'], indent=2, default=self._json_serializer)}"
            )
            parts.append("=" * 60)

        parts.append(
            "\nWhat would you like to do next? You can call more tools for additional data, "
            "or provide your final answer based on the information above."
        )

        return "\n".join(parts)

    def _record_run_start(
        self,
        run_id: str,
        started_at: datetime,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        """Record agent run start in database.

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            provider: LLM provider (gemini, claude, anthropic_api)
            model: Model identifier
        """
        self.storage.insert_dict(
            "agent_runs",
            {
                "id": run_id,
                "agent_type": self.agent_type,
                "started_at": started_at.isoformat() if started_at else None,
                "completed_at": None,
                "status": "running",
                "num_ideas": 0,
                "cost_usd": 0.0,
                "error_message": None,
                "metadata": None,
                "celery_task_id": None,
                "provider": provider,
                "model": model or self.model,
                "cli_command": None,
                "exit_code": None,
                "duration_ms": None,
                "token_usage": None,
                "session_id": None,
            },
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

    def _record_tool_call(
        self,
        run_id: str,
        tool_name: str,
        parameters: ToolInputDict,
        result: object,
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
                "parameters": json.dumps(parameters, default=self._json_serializer),
                "response_summary": result_summary,
                "duration_ms": duration_ms,
                "called_at": datetime.now(UTC).isoformat(),
            },
        )
