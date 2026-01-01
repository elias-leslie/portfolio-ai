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
from ..utils.formatters import calculate_duration_ms
from ..utils.json_helpers import json_serializer
from .llm_client import LLMClient
from .types import AgentRunStatus, StopReason, ToolInputDict

# Agent constants
MAX_LLM_TOKENS = 4096  # Max tokens for LLM response
TOOL_RESULT_TRUNCATE = 10000  # Max chars to store for tool results
RESULT_SUMMARY_LENGTH = 500  # Max chars for result summary

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

    from .llm_client import LLMResponse

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


class ToolExecutionResult(TypedDict):
    """Result of executing and recording a tool call."""

    result: object
    duration_ms: int


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
        model: str = "claude-sonnet-4-5",
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
        self._message_sequence: dict[str, int] = {}  # Tracks message sequence per run_id

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

    def _extract_output_tokens(self, response: LLMResponse) -> int | None:
        """Extract completion tokens from LLM response.

        Args:
            response: LLM response with usage info

        Returns:
            Completion token count, or None if unavailable
        """
        return response.usage.get("completion_tokens") if response.usage else None

    def _accumulate_token_usage(
        self, response: LLMResponse, total_token_usage: dict[str, int]
    ) -> None:
        """Accumulate token usage from an LLM response.

        Args:
            response: LLM response with usage info
            total_token_usage: Dict to accumulate usage into (modified in place)
        """
        if response.usage:
            total_token_usage["input_tokens"] += response.usage.get("prompt_tokens", 0)
            total_token_usage["output_tokens"] += response.usage.get("completion_tokens", 0)
            total_token_usage["total_tokens"] += response.usage.get("total_tokens", 0)

    def _update_provider_metadata(self, response: LLMResponse, run_id: str) -> None:
        """Update provider and model metadata in database from LLM response.

        Called on first iteration to get actual values from CLI.

        Args:
            response: LLM response with provider/model info
            run_id: Agent run ID to update
        """
        if response.provider and response.model:
            with self.storage.connection() as conn:
                conn.execute(
                    "UPDATE agent_runs SET provider = ?, model = ? WHERE id = ?",
                    [response.provider, response.model, run_id],
                )
                conn.commit()

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
        duration_ms = calculate_duration_ms(started_at, completed_at)
        duration_s = duration_ms / 1000.0

        logger.info(
            "agent_run_completed",
            run_id=run_id,
            agent_type=self.agent_type,
            num_tool_calls=len(tool_calls_made),
            iterations=iteration + 1,
            duration_s=round(duration_s, 2),
            status=AgentRunStatus.COMPLETED.value,
            token_usage=token_usage,
        )

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

    def _execute_and_record_tool(
        self,
        run_id: str,
        tool_name: str,
        tool_params: ToolInputDict,
        tool_calls_made: list[ToolCallRecord],
    ) -> ToolExecutionResult:
        """Execute a tool and record the call in the database.

        This is the core tool execution logic shared by both Anthropic API
        and LLM client processing paths.

        Args:
            run_id: Unique run identifier
            tool_name: Name of the tool to execute
            tool_params: Parameters to pass to the tool
            tool_calls_made: List to append tool call record to (modified in place)

        Returns:
            ToolExecutionResult with result and duration_ms
        """
        tool_start = datetime.now(UTC)

        # Execute the tool
        result = self.execute_tool(tool_name, tool_params)

        tool_end = datetime.now(UTC)
        duration_ms = calculate_duration_ms(tool_start, tool_end)

        # Record in database
        self._record_tool_call(run_id, tool_name, tool_params, result, duration_ms)

        # Append to accumulated records
        tool_calls_made.append(
            {
                "name": tool_name,
                "input": tool_params,
                "result": result,
            }
        )

        return {"result": result, "duration_ms": duration_ms}

    def _handle_unexpected_stop_reason(
        self,
        run_id: str,
        started_at: datetime,
        stop_reason: str | None,
        tool_calls_made: list[ToolCallRecord],
        token_usage: dict[str, int] | None = None,
    ) -> AgentRunResult:
        """Handle unexpected stop reason in agent execution.

        Consolidates error handling for both LLM client and Anthropic API paths.

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            stop_reason: The unexpected stop reason from the LLM
            tool_calls_made: List of tool calls made during the run
            token_usage: Optional token usage stats

        Returns:
            AgentRunResult with error status
        """
        completed_at = datetime.now(UTC)
        duration_ms = calculate_duration_ms(started_at, completed_at)
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

        Consolidates max iterations handling for both LLM client and Anthropic API paths.

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            max_iterations: The maximum iterations limit
            tool_calls_made: List of tool calls made during the run
            token_usage: Optional token usage stats

        Returns:
            AgentRunResult with max_iterations status
        """
        completed_at = datetime.now(UTC)
        duration_ms = calculate_duration_ms(started_at, completed_at)

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

    def _process_tool_calls_anthropic(
        self,
        response: object,
        run_id: str,
        tool_calls_made: list[ToolCallRecord],
    ) -> tuple[list[object], list[dict[str, object]]]:
        """Process tool calls from Anthropic API response.

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
                tool_input = cast(ToolInputDict, block.input)

                # Execute and record using shared helper
                exec_result = self._execute_and_record_tool(
                    run_id, block.name, tool_input, tool_calls_made
                )

                # Add tool result to conversation (Anthropic format)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(exec_result["result"], default=json_serializer),
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
            self._record_run_complete(
                run_id, datetime.now(UTC), AgentRunStatus.ERROR.value, 0, str(e)
            )
            return {"status": AgentRunStatus.ERROR.value, "error": str(e), "run_id": run_id}

    def _initialize_llm_conversation(
        self, run_id: str, user_prompt: str
    ) -> tuple[list[dict[str, object]], str, list[ToolCallRecord], dict[str, int]]:
        """Initialize LLM conversation state and store initial messages.

        Args:
            run_id: Unique run identifier
            user_prompt: User's prompt/request

        Returns:
            Tuple of (conversation_history, current_prompt, tool_calls_made, total_token_usage)
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

        # Store system prompt
        self._store_conversation_message(run_id, "system", self.get_system_prompt())

        # Store initial user message
        self._store_conversation_message(run_id, "user", user_prompt)

        return conversation_history, current_prompt, tool_calls_made, total_token_usage

    def _handle_llm_end_turn_response(
        self,
        run_id: str,
        started_at: datetime,
        response: LLMResponse,
        tool_calls_made: list[ToolCallRecord],
        iteration: int,
        total_token_usage: dict[str, int],
    ) -> AgentRunResult:
        """Handle end_turn response from LLM client.

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            response: LLM response with end_turn stop reason
            tool_calls_made: List of tool calls made during the run
            iteration: Current iteration number
            total_token_usage: Accumulated token usage

        Returns:
            Agent run result dict
        """
        # Store assistant's final response
        output_tokens = self._extract_output_tokens(response)
        self._store_conversation_message(
            run_id, "assistant", response.content, token_count=output_tokens
        )
        # Agent finished - provide final answer
        return self._handle_completion(
            run_id,
            started_at,
            tool_calls_made,
            iteration,
            response.content,
            total_token_usage,
        )

    def _handle_llm_tool_use_response(
        self,
        run_id: str,
        response: LLMResponse,
        tool_calls_made: list[ToolCallRecord],
        conversation_history: list[dict[str, object]],
    ) -> str:
        """Handle tool_use response from LLM client.

        Args:
            run_id: Unique run identifier
            response: LLM response with tool_use stop reason
            tool_calls_made: List of tool calls made (modified in place)
            conversation_history: Conversation history (modified in place)

        Returns:
            Formatted tool results as prompt for next turn
        """
        # Store assistant's response with tool calls
        output_tokens = self._extract_output_tokens(response)
        self._store_conversation_message(
            run_id,
            "assistant",
            response.content,
            token_count=output_tokens,
            metadata={"has_tool_calls": True},
        )

        # Process tool calls and format results for next turn
        tool_results = self._process_tool_calls_llm(
            run_id, response.tool_calls, tool_calls_made
        )
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

        return current_prompt

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
        # Initialize conversation state
        conversation_history, current_prompt, tool_calls_made, total_token_usage = (
            self._initialize_llm_conversation(run_id, user_prompt)
        )

        for iteration in range(max_iterations):
            # Generate with tools
            response = self.llm_client.generate_with_tools(  # type: ignore[union-attr]
                prompt=current_prompt,
                tools=self.get_tools(),
                system=self.get_system_prompt(),
                conversation_history=conversation_history,
                max_tokens=MAX_LLM_TOKENS,
                temperature=1.0,
            )

            # Accumulate token usage from this iteration
            self._accumulate_token_usage(response, total_token_usage)

            # Update provider/model in database on first response (get actual values from CLI)
            if iteration == 0:
                self._update_provider_metadata(response, run_id)

            if response.stop_reason == "end_turn":
                return self._handle_llm_end_turn_response(
                    run_id, started_at, response, tool_calls_made, iteration, total_token_usage
                )

            if response.stop_reason == "tool_use":
                current_prompt = self._handle_llm_tool_use_response(
                    run_id, response, tool_calls_made, conversation_history
                )

            else:
                # Unexpected stop reason
                return self._handle_unexpected_stop_reason(
                    run_id, started_at, response.stop_reason, tool_calls_made, total_token_usage
                )

        # Max iterations reached
        return self._handle_max_iterations(
            run_id, started_at, max_iterations, tool_calls_made, total_token_usage
        )

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
                max_tokens=MAX_LLM_TOKENS,
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
                assistant_content, tool_results = self._process_tool_calls_anthropic(
                    response, run_id, tool_calls_made
                )

                # Continue conversation with tool results
                messages.append({"role": "assistant", "content": assistant_content})  # type: ignore[dict-item]
                messages.append({"role": "user", "content": tool_results})  # type: ignore[dict-item]

            else:
                # Unexpected stop reason
                return self._handle_unexpected_stop_reason(
                    run_id, started_at, response.stop_reason, tool_calls_made
                )

        # Max iterations reached
        return self._handle_max_iterations(run_id, started_at, max_iterations, tool_calls_made)

    def _process_tool_calls_llm(
        self,
        run_id: str,
        tool_calls: list[dict[str, object]],
        tool_calls_made: list[ToolCallRecord],
    ) -> list[dict[str, object]]:
        """Process a batch of tool calls from LLM client and return results.

        Executes each tool call, stores conversation messages, records in database,
        and returns formatted results for the next conversation turn.

        Args:
            run_id: Current agent run ID
            tool_calls: List of tool call dicts from LLM response
            tool_calls_made: Accumulated list to append tool records to

        Returns:
            List of tool result dicts for _format_tool_results
        """
        tool_results: list[dict[str, object]] = []

        for tool_call in tool_calls:
            tool_name = str(tool_call["name"])
            tool_params = cast(ToolInputDict, tool_call["parameters"])

            # Store tool call message (before execution)
            self._store_conversation_message(
                run_id,
                "tool_call",
                json.dumps(
                    {"name": tool_name, "parameters": tool_params},
                    default=json_serializer,
                ),
                metadata={"tool_name": tool_name},
            )

            # Execute and record using shared helper
            exec_result = self._execute_and_record_tool(
                run_id, tool_name, tool_params, tool_calls_made
            )

            # Store tool result message (truncate long results)
            result_str = json.dumps(exec_result["result"], default=json_serializer)
            self._store_conversation_message(
                run_id,
                "tool_result",
                result_str[:TOOL_RESULT_TRUNCATE],
                metadata={"tool_name": tool_name, "duration_ms": exec_result["duration_ms"]},
            )

            tool_results.append(
                {
                    "name": tool_name,
                    "parameters": tool_params,
                    "result": exec_result["result"],
                }
            )

        return tool_results

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
            parts.append(f"Result:\n{json.dumps(tr['result'], indent=2, default=json_serializer)}")
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
            parent_run_id: Parent run ID for linked runs (e.g., follow-up discussions)
            workflow_id: Associated workflow ID
            user_id: User ID for multi-user support
        """
        self.storage.insert_dict(
            "agent_runs",
            {
                "id": run_id,
                "agent_type": self.agent_type,
                "started_at": started_at.isoformat() if started_at else None,
                "completed_at": None,
                "status": AgentRunStatus.RUNNING.value,
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
                "run_type": run_type,
                "parent_run_id": parent_run_id,
                "workflow_id": workflow_id,
                "user_id": user_id,
            },
        )
        # Track message sequence for this run
        self._message_sequence[run_id] = 0

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
            metadata: Optional metadata (e.g., tool name, tool_use_id)
        """
        # Get and increment sequence number (initialized in _record_run_start)
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
