"""Anthropic API flow orchestration for agents.

This module handles the Anthropic API conversation loop (legacy path).
Extracted from base.py for single responsibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from anthropic import Anthropic

from .response_processing import extract_final_response
from .types import StopReason

if TYPE_CHECKING:
    from .base import AgentRunResult, ToolCallRecord

# Agent constants
MAX_LLM_TOKENS = 4096


class AnthropicFlowMixin:
    """Mixin providing Anthropic API flow methods for agents.

    Requires various methods from other mixins and the agent class.
    """

    client: Anthropic
    model: str

    def get_system_prompt(self) -> str:
        """Get system prompt (implemented by concrete agent)."""
        raise NotImplementedError

    def get_tools(self) -> list[dict[str, object]]:
        """Get tool definitions (implemented by concrete agent)."""
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

    def _process_tool_calls_anthropic(
        self,
        response: object,
        run_id: str,
        tool_calls_made: list[ToolCallRecord],
    ) -> tuple[list[object], list[dict[str, object]]]:
        """Process tool calls (implemented by ToolExecutorMixin)."""
        raise NotImplementedError

    def _dispatch_anthropic_stop_reason(
        self,
        run_id: str,
        started_at: datetime,
        response: object,
        tool_calls_made: list[ToolCallRecord],
        messages: list[dict[str, object]],
        iteration: int,
    ) -> AgentRunResult | None:
        """Dispatch Anthropic API response based on stop reason.

        Args:
            run_id: Unique run identifier
            started_at: Run start timestamp
            response: Anthropic API response
            tool_calls_made: List of tool calls made
            messages: Conversation messages (modified if tool_use)
            iteration: Current iteration number

        Returns:
            AgentRunResult if done (end_turn or error), or None if continuing
        """
        if response.stop_reason == StopReason.END_TURN.value:  # type: ignore[attr-defined]
            final_text = extract_final_response(response)
            return self._handle_completion(
                run_id, started_at, tool_calls_made, iteration, final_text
            )

        if response.stop_reason == StopReason.TOOL_USE.value:  # type: ignore[attr-defined]
            assistant_content, tool_results = self._process_tool_calls_anthropic(
                response, run_id, tool_calls_made
            )
            # Continue conversation with tool results
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
            return None  # Continue loop

        # Unexpected stop reason
        return self._handle_unexpected_stop_reason(
            run_id,
            started_at,
            response.stop_reason,  # type: ignore[attr-defined]
            tool_calls_made,
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
        messages: list[dict[str, object]] = [{"role": "user", "content": user_prompt}]
        tool_calls_made: list[ToolCallRecord] = []

        for iteration in range(max_iterations):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_LLM_TOKENS,
                system=self.get_system_prompt(),
                tools=self.get_tools(),  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )

            result = self._dispatch_anthropic_stop_reason(
                run_id, started_at, response, tool_calls_made, messages, iteration
            )

            if result is not None:
                return result

        # Max iterations reached
        return self._handle_max_iterations(run_id, started_at, max_iterations, tool_calls_made)
