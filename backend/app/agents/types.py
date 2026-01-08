"""TypedDict definitions for agent types.

This module provides typed dictionaries for agent-related operations,
replacing loose dict[str, Any] with properly typed structures.
"""

from __future__ import annotations

from enum import Enum
from typing import TypedDict


class AgentRunStatus(str, Enum):
    """Status values for agent runs."""

    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    MAX_ITERATIONS = "max_iterations"


class StopReason(str, Enum):
    """Stop reason values for LLM responses."""

    END_TURN = "end_turn"
    TOOL_USE = "tool_use"


class ToolInputDict(TypedDict, total=False):
    """Standard tool input dictionary passed to agents."""

    query: str
    indicators: list[str]
    symbols: list[str]
    max_results: int
    title: str
    thesis: str
    action: str
    idea_type: str
    confidence_score: float
    risk_level: str
    symbol: str
    reason: str
    expected_return_pct: float
    time_horizon_days: int
    trade_type: str
    quantity: int
    entry_price: float
    stop_loss: float
    target_price: float
    message: str
    message_id: str


class ToolDefinitionDict(TypedDict, total=False):
    """Claude API tool definition dictionary."""

    name: str
    description: str
    input_schema: dict[str, object]


class ToolResultDict(TypedDict, total=False):
    """Standard result dictionary from tool execution."""

    status: str
    message: str
    data: object
    error: str
    errors: list[str]
    idea_id: str
    success: bool


class AgentInitKwargs(TypedDict, total=False):
    """Keyword arguments passed to agent __init__."""

    model: str
    kwargs: object


class IdeaDataDict(TypedDict, total=False):
    """Investment idea data passed to store_idea tool."""

    idea_type: str
    title: str
    thesis: str
    action: str
    confidence_score: float
    risk_level: str
    tags: list[str]
    analysis: str
