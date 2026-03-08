"""Portfolio Analyzer Agent implementation.

Analyzes user's portfolio to generate personalized strategy seeds.

Section 1.1/1.3: Performance feedback and fee awareness added to prompts.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ..logging_config import get_logger
from .performance_metrics import get_full_performance_prompt_section

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.rules import get_rules

from .base import Agent, AgentRunResult
from .tools import (
    AgentTools,
    get_economic_data_tool_definition,
    get_news_tool_definition,
    get_portfolio_data_tool_definition,
    get_price_data_tool_definition,
    get_store_strategy_seed_tool_definition,
)

logger = get_logger(__name__)


class PortfolioAnalyzerAgent(Agent):
    """Portfolio Analyzer Agent - generates personalized strategy seeds.

    This agent analyzes the user's portfolio and generates seeds
    tailored to their holdings, risk profile, and market conditions.
    """

    def __init__(self, storage: PortfolioStorage, tools: AgentTools, **kwargs: object) -> None:
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
        # Get fee warning from rules
        rules = get_rules()
        fees = rules.fees
        round_trip_pct = (fees.commission_pct * 100 * 2) + (fees.slippage_bps / 100 * 2)

        fee_warning = f"""
TRADING COSTS (factor these into recommendations):
- Round-trip cost: ~{round_trip_pct:.2f}%
- Minimum profitable move: >{round_trip_pct:.1f}%
Rebalancing has costs. Only recommend changes with significant expected value.
"""

        # Get performance context
        try:
            perf_context = get_full_performance_prompt_section(self.storage, days=30)
        except Exception:
            perf_context = ""  # Don't fail if metrics unavailable

        return f"""You are a Portfolio Analyzer Agent for an investment intelligence platform.

Your role is to analyze the user's current portfolio and generate 5 personalized strategy seeds.
{perf_context}
{fee_warning}
Guidelines:
- First, fetch and analyze the user's portfolio using get_portfolio_data
- Consider their current positions, sector exposure, and concentration risk
- Check market conditions with get_news and get_economic_data
- Generate seeds that complement or hedge their portfolio
- Each seed MUST have a specific stock symbol
- Each seed should reference how it relates to their current holdings
- Assess confidence on a 1-10 scale
- Consider their portfolio's beta and volatility in recommendations

Process:
1. Use get_portfolio_data to fetch current positions and analytics
2. Use get_news to check relevant market headlines
3. Use get_economic_data to check key indicators
4. Analyze portfolio gaps, risks, and opportunities
5. Generate 5 personalized strategy seeds using store_strategy_seed

For each seed, include:
- symbol: the stock ticker
- thesis: why it fits this portfolio now
- confidence: 1-10

Generate exactly 5 strategy seeds that are specifically tailored to this portfolio, then stop."""

    def get_tools(self) -> list[dict[str, object]]:
        """Get tool definitions for Portfolio Analyzer Agent."""
        return [
            get_portfolio_data_tool_definition(),
            get_news_tool_definition(),
            get_economic_data_tool_definition(),
            get_price_data_tool_definition(),
            get_store_strategy_seed_tool_definition(),
        ]

    def execute_tool(self, tool_name: str, tool_input: dict[str, object]) -> object:  # type: ignore[override]
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
            query = str(tool_input.get("query", ""))
            max_results_raw = tool_input.get("max_results")
            max_results = int(max_results_raw) if isinstance(max_results_raw, (int, str)) else None
            return self.tools.execute_get_news(query, max_results)

        if tool_name == "get_economic_data":
            indicators_raw = tool_input.get("indicators", [])
            indicators = (
                [str(i) for i in indicators_raw] if isinstance(indicators_raw, list) else []
            )
            return self.tools.execute_get_economic_data(indicators)

        if tool_name == "get_price_data":
            symbols_raw = tool_input.get("symbols", [])
            symbols = [str(s) for s in symbols_raw] if isinstance(symbols_raw, list) else []
            return self.tools.execute_get_price_data(symbols)

        if tool_name == "store_strategy_seed":
            if not self.current_run_id:
                raise ValueError("No active run_id for storing seeds")
            symbol = str(tool_input.get("symbol", "")).strip()
            thesis = str(tool_input.get("thesis", "")).strip()
            if not symbol:
                raise ValueError("symbol is required for storing seeds")
            if not thesis:
                raise ValueError("thesis is required for storing seeds")
            confidence_raw = tool_input.get("confidence", 5)
            confidence_val = (
                float(confidence_raw) if isinstance(confidence_raw, (int, float, str)) else 5.0
            )
            return self.tools.execute_store_strategy_seed(
                agent_run_id=self.current_run_id,
                symbol=symbol,
                thesis=thesis,
                confidence=confidence_val,
            )

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
            user_prompt = "Analyze my portfolio and generate 5 personalized strategy seeds."

        # Set run_id for this execution
        self.current_run_id = str(uuid.uuid4())

        result = super().run(user_prompt, max_iterations=max_iterations)

        # Clear run_id after execution
        self.current_run_id = None

        return result
