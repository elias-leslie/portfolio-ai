"""Portfolio Analyzer Agent implementation.

Analyzes user's portfolio to generate personalized investment ideas.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from .base import Agent, AgentRunResult
from .tools import (
    AgentTools,
    get_economic_data_tool_definition,
    get_news_tool_definition,
    get_portfolio_data_tool_definition,
    get_price_data_tool_definition,
    get_store_idea_tool_definition,
)

logger = get_logger(__name__)


class PortfolioAnalyzerAgent(Agent):
    """Portfolio Analyzer Agent - generates personalized investment ideas.

    This agent analyzes the user's portfolio and generates ideas
    tailored to their holdings, risk profile, and market conditions.
    """

    def __init__(self, storage: PortfolioStorage, tools: AgentTools, **kwargs: Any) -> None:
        """Initialize Portfolio Analyzer Agent.

        Args:
            storage: PortfolioStorage instance
            tools: AgentTools instance
            **kwargs: Additional arguments for base Agent
        """
        super().__init__(storage, **kwargs)
        self.tools = tools
        self.current_run_id: str | None = None

    def get_system_prompt(self) -> str:
        """Get system prompt for Portfolio Analyzer Agent."""
        return """You are a Portfolio Analyzer Agent for an investment intelligence platform.

Your role is to analyze the user's current portfolio and generate 5 personalized investment ideas.

Guidelines:
- First, fetch and analyze the user's portfolio using get_portfolio_data
- Consider their current positions, sector exposure, and concentration risk
- Check market conditions with get_news and get_economic_data
- Generate ideas that complement or hedge their portfolio
- Each idea should reference how it relates to their current holdings
- Assess confidence (0-100) and risk level (low/medium/high)
- Consider their portfolio's beta and volatility in recommendations

Process:
1. Use get_portfolio_data to fetch current positions and analytics
2. Use get_news to check relevant market headlines
3. Use get_economic_data to check key indicators
4. Analyze portfolio gaps, risks, and opportunities
5. Generate 5 personalized ideas using store_idea

Generate exactly 5 ideas that are specifically tailored to this portfolio, then stop."""

    def get_tools(self) -> list[dict[str, Any]]:
        """Get tool definitions for Portfolio Analyzer Agent."""
        return [
            get_portfolio_data_tool_definition(),
            get_news_tool_definition(),
            get_economic_data_tool_definition(),
            get_price_data_tool_definition(),
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
        if tool_name == "get_portfolio_data":
            return self.tools.execute_get_portfolio_data()

        if tool_name == "get_news":
            return self.tools.execute_get_news(**tool_input)

        if tool_name == "get_economic_data":
            return self.tools.execute_get_economic_data(**tool_input)

        if tool_name == "get_price_data":
            return self.tools.execute_get_price_data(**tool_input)

        if tool_name == "store_idea":
            if not self.current_run_id:
                raise ValueError("No active run_id for storing ideas")
            return self.tools.execute_store_idea(self.current_run_id, **tool_input)

        raise ValueError(f"Unknown tool: {tool_name}")

    def run(self, user_prompt: str = "", max_iterations: int = 10) -> AgentRunResult:
        """Run Portfolio Analyzer Agent with default prompt.

        Args:
            user_prompt: Optional custom prompt (defaults to portfolio analysis)
            max_iterations: Maximum number of iterations (default: 10)

        Returns:
            dict containing status, response, and metadata
        """
        if not user_prompt:
            user_prompt = "Analyze my portfolio and generate 5 personalized investment ideas."

        # Set run_id for this execution
        self.current_run_id = str(uuid.uuid4())

        result = super().run(user_prompt, max_iterations=max_iterations)

        # Clear run_id after execution
        self.current_run_id = None

        return result
