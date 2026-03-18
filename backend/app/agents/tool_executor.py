"""Tool execution logic for agents.

This module handles tool call execution, recording, and result formatting.
Extracted from base.py for single responsibility.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from ..utils.formatters import calculate_duration_ms
from ..utils.json_helpers import json_serializer
from .tool_formatting import build_tool_result_dict
from .types import ToolInputDict

if TYPE_CHECKING:
    from ..storage.facade import PortfolioStorage
    from .base import ToolCallRecord, ToolExecutionResult

# Constant for truncating tool results in storage
TOOL_RESULT_TRUNCATE = 10000


class ToolExecutorMixin:
    """Mixin providing tool execution methods for agents.

    Requires execute_tool method from the agent class.
    Requires _record_tool_call and _store_conversation_message from persistence.
    """

    storage: PortfolioStorage

    def execute_tool(self, tool_name: str, tool_input: ToolInputDict) -> object:
        """Execute a tool call (implemented by concrete agent)."""
        raise NotImplementedError

    def _record_tool_call(
        self,
        run_id: str,
        tool_name: str,
        parameters: ToolInputDict,
        result: object,
        duration_ms: int,
    ) -> None:
        """Record tool call in database (implemented by AgentPersistenceMixin)."""
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

    def _store_tool_call_message(
        self, run_id: str, tool_name: str, tool_params: ToolInputDict
    ) -> None:
        """Store a tool call message in conversation history.

        Args:
            run_id: Current agent run ID
            tool_name: Name of the tool being called
            tool_params: Tool parameters
        """
        self._store_conversation_message(
            run_id,
            "tool_call",
            json.dumps(
                {"name": tool_name, "parameters": tool_params},
                default=json_serializer,
            ),
            metadata={"tool_name": tool_name},
        )

    def _store_tool_result_message(
        self, run_id: str, tool_name: str, exec_result: ToolExecutionResult
    ) -> None:
        """Store a tool result message in conversation history.

        Args:
            run_id: Current agent run ID
            tool_name: Name of the tool
            exec_result: Tool execution result with result and duration_ms
        """
        result_str = json.dumps(exec_result["result"], default=json_serializer)
        self._store_conversation_message(
            run_id,
            "tool_result",
            result_str[:TOOL_RESULT_TRUNCATE],
            metadata={"tool_name": tool_name, "duration_ms": exec_result["duration_ms"]},
        )

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

        for block in response.content:
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
            self._store_tool_call_message(run_id, tool_name, tool_params)

            # Execute and record using shared helper
            exec_result = self._execute_and_record_tool(
                run_id, tool_name, tool_params, tool_calls_made
            )

            # Store tool result message
            self._store_tool_result_message(run_id, tool_name, exec_result)

            # Build result dict
            tool_results.append(build_tool_result_dict(tool_name, tool_params, exec_result))

        return tool_results
