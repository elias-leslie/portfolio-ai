"""LLM client flow orchestration for agents.

This module handles the main LLM client conversation loop,
including initialization, response handling, and dispatch.
Extracted from base.py for single responsibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .response_processing import extract_output_tokens
from .types import StopReason

if TYPE_CHECKING:
    from ..storage.facade import PortfolioStorage
    from .base import AgentRunResult, ToolCallRecord
    from .llm_client import LLMClient, LLMResponse

# Agent constants
MAX_LLM_TOKENS = 4096


class LLMFlowMixin:
    """Mixin providing LLM client flow methods for agents.

    Requires various methods from other mixins and the agent class.
    """

    storage: PortfolioStorage
    llm_client: LLMClient | None
    agent_type: str

    def get_system_prompt(self) -> str:
        """Get system prompt (implemented by concrete agent)."""
        raise NotImplementedError

    def get_tools(self) -> list[dict[str, object]]:
        """Get tool definitions (implemented by concrete agent)."""
        raise NotImplementedError

    def _store_conversation_message(
        self,
        run_id: str,
        role: str,
        content: str,
        token_count: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Store conversation message (implemented by AgentPersistenceMixin)."""
        raise NotImplementedError

    def _handle_completion(
        self,
        run_id: str,
        started_at: datetime,
        tool_calls_made: list[ToolCallRecord],
        iteration: int,
        final_text: str,
        token_usage: dict[str, int] | None = None,
    ) -> AgentRunResult:
        """Handle completion (implemented by CompletionHandlerMixin)."""
        raise NotImplementedError

    def _handle_unexpected_stop_reason(
        self,
        run_id: str,
        started_at: datetime,
        stop_reason: str | None,
        tool_calls_made: list[ToolCallRecord],
        token_usage: dict[str, int] | None = None,
    ) -> AgentRunResult:
        """Handle unexpected stop (implemented by CompletionHandlerMixin)."""
        raise NotImplementedError

    def _handle_max_iterations(
        self,
        run_id: str,
        started_at: datetime,
        max_iterations: int,
        tool_calls_made: list[ToolCallRecord],
        token_usage: dict[str, int] | None = None,
    ) -> AgentRunResult:
        """Handle max iterations (implemented by CompletionHandlerMixin)."""
        raise NotImplementedError

    def _process_tool_calls_llm(
        self,
        run_id: str,
        tool_calls: list[dict[str, object]],
        tool_calls_made: list[ToolCallRecord],
    ) -> list[dict[str, object]]:
        """Process tool calls (implemented by ToolExecutorMixin)."""
        raise NotImplementedError

    def _format_tool_results(self, tool_results: list[dict[str, object]]) -> str:
        """Format tool results (implemented by ToolFormattingMixin)."""
        raise NotImplementedError

    def _accumulate_token_usage(
        self, response: LLMResponse, total_token_usage: dict[str, int]
    ) -> None:
        """Accumulate token usage (implemented by ResponseProcessingMixin)."""
        raise NotImplementedError

    def _update_provider_metadata(self, response: LLMResponse, run_id: str) -> None:
        """Update provider metadata in database from LLM response.

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
        output_tokens = extract_output_tokens(response)
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

    def _dispatch_llm_stop_reason(
        self,
        run_id: str,
        started_at: datetime,
        response: LLMResponse,
        tool_calls_made: list[ToolCallRecord],
        conversation_history: list[dict[str, object]],
        iteration: int,
        total_token_usage: dict[str, int],
    ) -> AgentRunResult | str:
        """Dispatch LLM response based on stop reason.

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            response: LLM response to dispatch
            tool_calls_made: List of tool calls made
            conversation_history: Conversation history (modified if tool_use)
            iteration: Current iteration number
            total_token_usage: Accumulated token usage

        Returns:
            AgentRunResult if done (end_turn or error), or str prompt if continuing
        """
        if response.stop_reason == StopReason.END_TURN.value:
            return self._handle_llm_end_turn_response(
                run_id, started_at, response, tool_calls_made, iteration, total_token_usage
            )

        if response.stop_reason == StopReason.TOOL_USE.value:
            return self._handle_llm_tool_use_response(
                run_id, response, tool_calls_made, conversation_history
            )

        # Unexpected stop reason
        return self._handle_unexpected_stop_reason(
            run_id, started_at, response.stop_reason, tool_calls_made, total_token_usage
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
        output_tokens = extract_output_tokens(response)
        self._store_conversation_message(
            run_id,
            "assistant",
            response.content,
            token_count=output_tokens,
            metadata={"has_tool_calls": True},
        )

        # Process tool calls and format results for next turn
        tool_results = self._process_tool_calls_llm(run_id, response.tool_calls, tool_calls_made)
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
            response = self.llm_client.generate_with_tools(
                prompt=current_prompt,
                tools=self.get_tools(),
                system=self.get_system_prompt(),
                conversation_history=conversation_history,
                temperature=1.0,
                purpose=f"agent:{self.agent_type}",
            )

            # Accumulate token usage from this iteration
            self._accumulate_token_usage(response, total_token_usage)

            # Update provider/model in database on first response
            if iteration == 0:
                self._update_provider_metadata(response, run_id)

            # Dispatch based on stop reason
            result = self._dispatch_llm_stop_reason(
                run_id,
                started_at,
                response,
                tool_calls_made,
                conversation_history,
                iteration,
                total_token_usage,
            )

            # If result is a string, it's the next prompt; continue the loop
            if isinstance(result, str):
                current_prompt = result
            else:
                # Otherwise it's a final AgentRunResult
                return result

        # Max iterations reached
        return self._handle_max_iterations(
            run_id, started_at, max_iterations, tool_calls_made, total_token_usage
        )
