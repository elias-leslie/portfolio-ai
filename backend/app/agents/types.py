"""TypedDict definitions for agent types.

This module provides typed dictionaries for agent-related operations,
replacing loose dict[str, Any] with properly typed structures.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TypedDict


class AgentRunStatus(StrEnum):
    """Status values for agent runs."""

    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    MAX_ITERATIONS = "max_iterations"


class StopReason(StrEnum):
    """Stop reason values for LLM responses."""

    END_TURN = "end_turn"
    TOOL_USE = "tool_use"


class ToolInputDict(TypedDict, total=False):
    """Standard tool input dictionary passed to agents."""

    query: str
    indicators: list[str]
    symbols: list[str]
    max_results: int
    thesis: str
    confidence: float
    symbol: str
    reason: str
    expected_return_pct: float
    time_horizon_days: int
    workflow_id: str
    key: str
    agent_type: str
    message_type: str
    message: str
    message_id: str
    data: dict[str, object]
    priority: int
    decision_id: str
    vote: str
    reasoning: str
    timeout_seconds: int


class ToolResultDict(TypedDict, total=False):
    """Standard result dictionary from tool execution."""

    status: str
    message: str
    data: object
    error: str
    errors: list[str]
    seed_id: str
    success: bool


