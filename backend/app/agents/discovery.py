"""Discovery Agent implementation.

Scans market news and economic data to generate general investment ideas.

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
    get_store_strategy_seed_tool_definition,
)

logger = get_logger(__name__)


class DiscoveryAgent(Agent):
    """Discovery Agent - generates general market investment ideas.

    This agent scans news and economic indicators to identify
    broad market opportunities without reference to user's portfolio.
    """

    def __init__(self, storage: PortfolioStorage, tools: AgentTools, **kwargs: object) -> None:
        """Initialize Discovery Agent.

        Args:
            storage: PortfolioStorage instance
            tools: AgentTools instance
            **kwargs: Additional arguments for base Agent
        """
        super().__init__(storage, **kwargs)  # type: ignore[arg-type]
        self.tools = tools
        self.current_run_id: str | None = None

    def get_system_prompt(self) -> str:
        """Get system prompt for Discovery Agent."""
        # Get fee warning from rules
        rules = get_rules()
        fees = rules.fees
        round_trip_pct = (fees.commission_pct * 100 * 2) + (fees.slippage_bps / 100 * 2)

        fee_warning = f"""
TRADING COSTS (factor these into idea quality):
- Round-trip cost: ~{round_trip_pct:.2f}%
- Minimum profitable move: >{round_trip_pct:.1f}%
Focus on high-conviction opportunities that justify trading costs.
"""

        # Get performance context
        try:
            perf_context = get_full_performance_prompt_section(self.storage, days=30)
        except Exception:
            perf_context = ""  # Don't fail if metrics unavailable

        return f"""You are a Discovery Agent for an investment intelligence platform.

Your role is to scan market news and economic indicators to identify 5 high-quality strategy seeds.
{perf_context}
{fee_warning}
Guidelines:
- Generate seeds that would be interesting to active investors
- Consider both long and short opportunities
- Look for themes in news and economic data
- Each seed MUST have a specific stock symbol (e.g., AAPL, NVDA, MSFT)
- Assess confidence (1-10) - seeds with confidence >= 7 auto-trigger strategy backtesting
- Provide clear thesis explaining why this opportunity exists

Process:
1. Use get_news to fetch recent market headlines
2. Use get_economic_data to check key indicators (VIX, rates, etc.)
3. Analyze the data to identify 5 distinct investment opportunities
4. For each opportunity, use store_strategy_seed with:
   - symbol: The specific stock ticker (REQUIRED)
   - thesis: Your investment thesis
   - confidence: Score 1-10 (>=7 triggers automatic strategy workflow)

Generate exactly 5 strategy seeds with specific symbols, then stop."""

    def get_tools(self) -> list[dict[str, object]]:
        """Get tool definitions for Discovery Agent."""
        return [
            get_news_tool_definition(),
            get_economic_data_tool_definition(),
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

        if tool_name == "store_strategy_seed":
            if not self.current_run_id:
                raise ValueError("No active run_id for storing seeds")
            confidence_raw = tool_input.get("confidence", 5)
            confidence_val = (
                float(confidence_raw) if isinstance(confidence_raw, (int, float, str)) else 5.0
            )
            return self.tools.execute_store_strategy_seed(
                agent_run_id=self.current_run_id,
                symbol=str(tool_input.get("symbol", "")),
                thesis=str(tool_input.get("thesis", "")),
                confidence=confidence_val,
            )

        # Legacy support for store_idea (deprecated)
        if tool_name == "store_idea":
            if not self.current_run_id:
                raise ValueError("No active run_id for storing ideas")
            return self.tools.execute_store_idea(self.current_run_id, **tool_input)

        raise ValueError(f"Unknown tool: {tool_name}")

    def run(self, user_prompt: str = "", max_iterations: int = 10) -> AgentRunResult:
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
