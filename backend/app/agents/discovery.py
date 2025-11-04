"""Discovery Agent implementation.

Scans market news and economic data to generate general investment ideas.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from .base import Agent
from .tools import (
    AgentTools,
    get_economic_data_tool_definition,
    get_news_tool_definition,
    get_store_idea_tool_definition,
)

logger = get_logger(__name__)


class DiscoveryAgent(Agent):
    """Discovery Agent - generates general market investment ideas.

    This agent scans news and economic indicators to identify
    broad market opportunities without reference to user's portfolio.
    """

    def __init__(self, storage: PortfolioStorage, tools: AgentTools, **kwargs: Any) -> None:
        """Initialize Discovery Agent.

        Args:
            storage: PortfolioStorage instance
            tools: AgentTools instance
            **kwargs: Additional arguments for base Agent
        """
        super().__init__(storage, **kwargs)
        self.tools = tools
        self.current_run_id: str | None = None

    def get_system_prompt(self) -> str:
        """Get system prompt for Discovery Agent."""
        return """You are a Discovery Agent for an investment intelligence platform.

Your role is to scan market news and economic indicators to identify 5 high-quality general investment ideas.

Guidelines:
- Generate ideas that would be interesting to active investors
- Consider both long and short opportunities
- Look for themes in news and economic data
- Each idea should be actionable and specific
- Assess confidence (0-100) and risk level (low/medium/high) for each idea
- Provide clear thesis and specific action for each idea

Process:
1. Use get_news to fetch recent market headlines
2. Use get_economic_data to check key indicators (VIX, rates, etc.)
3. Analyze the data to identify 5 distinct investment opportunities
4. For each idea, use store_idea to save it with full details

Generate exactly 5 ideas, then stop."""

    def get_tools(self) -> list[dict[str, Any]]:
        """Get tool definitions for Discovery Agent."""
        return [
            get_news_tool_definition(),
            get_economic_data_tool_definition(),
            get_store_idea_tool_definition(),
        ]

    def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        """Execute a tool call.

        Args:
            tool_name: Name of the tool
            tool_input: Tool parameters

        Returns:
            Tool execution result
        """
        if tool_name == "get_news":
            return self.tools.execute_get_news(**tool_input)

        if tool_name == "get_economic_data":
            return self.tools.execute_get_economic_data(**tool_input)

        if tool_name == "store_idea":
            if not self.current_run_id:
                raise ValueError("No active run_id for storing ideas")
            return self.tools.execute_store_idea(self.current_run_id, **tool_input)

        raise ValueError(f"Unknown tool: {tool_name}")

    def run(self, user_prompt: str = "", max_iterations: int = 10) -> dict[str, Any]:
        """Run Discovery Agent with default prompt.

        Args:
            user_prompt: Optional custom prompt (defaults to market analysis)
            max_iterations: Maximum number of iterations (default: 10)

        Returns:
            dict containing status, response, and metadata
        """
        if not user_prompt:
            user_prompt = "Analyze current market conditions and generate 5 investment ideas."

        # Set run_id for this execution
        self.current_run_id = str(uuid.uuid4())

        result = super().run(user_prompt, max_iterations=max_iterations)

        # Clear run_id after execution
        self.current_run_id = None

        return result
