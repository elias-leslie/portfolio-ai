"""Tool result formatting utilities for agents.

This module handles formatting tool results for conversation turns
and building tool result dictionaries. Extracted from base.py.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..utils.json_helpers import json_serializer

if TYPE_CHECKING:
    from .base import ToolExecutionResult
    from .types import ToolInputDict


def format_tool_results(tool_results: list[dict[str, object]]) -> str:
    """Format tool results for next conversation turn.

    Args:
        tool_results: List of tool result dicts with name, parameters, result

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


def build_tool_result_dict(
    tool_name: str, tool_params: ToolInputDict, exec_result: ToolExecutionResult
) -> dict[str, object]:
    """Build a tool result dict for the results list.

    Args:
        tool_name: Name of the tool
        tool_params: Tool parameters
        exec_result: Tool execution result with result and duration_ms

    Returns:
        Dict with name, parameters, and result
    """
    return {
        "name": tool_name,
        "parameters": tool_params,
        "result": exec_result["result"],
    }


class ToolFormattingMixin:
    """Mixin providing tool formatting methods for agents."""

    def _format_tool_results(self, tool_results: list[dict[str, object]]) -> str:
        """Format tool results for next conversation turn."""
        return format_tool_results(tool_results)

    def _build_tool_result_dict(
        self, tool_name: str, tool_params: ToolInputDict, exec_result: ToolExecutionResult
    ) -> dict[str, object]:
        """Build a tool result dict for the results list."""
        return build_tool_result_dict(tool_name, tool_params, exec_result)
