"""Agent tools orchestrator - unified interface for all tool execution.

This module provides a unified AgentTools class that delegates to specialized
tool executors. It also re-exports tool definitions for backward compatibility.

Architecture:
- Tool definitions: See tool_definitions.py
- Data tools: See tool_executors_data.py
- Trading tools: See tool_executors_trading.py
- Collaboration tools: See tool_executors_collaboration.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.portfolio.analytics import PortfolioAnalytics
    from app.portfolio.manager import PortfolioManager
    from app.portfolio.price_fetcher import PriceDataFetcher
    from app.services import NewsService
    from app.sources.fred import FREDSource
    from app.storage.facade import PortfolioStorage

# Import all tool definitions for re-export
from .tool_definitions import (
    get_add_symbol_tool_definition,
    get_economic_data_tool_definition,
    get_news_tool_definition,
    get_portfolio_data_tool_definition,
    get_price_data_tool_definition,
    get_query_memory_tool_definition,
    get_remove_symbol_tool_definition,
    get_send_message_tool_definition,
    get_store_strategy_seed_tool_definition,
    get_vote_decision_tool_definition,
    get_wait_response_tool_definition,
)

# Import specialized tool executors
from .tool_executors_collaboration import CollaborationTools
from .tool_executors_data import DataTools
from .tool_executors_trading import TradingTools

# Re-export everything for backward compatibility
__all__ = [
    "AgentTools",
    "get_add_symbol_tool_definition",
    "get_economic_data_tool_definition",
    "get_news_tool_definition",
    "get_portfolio_data_tool_definition",
    "get_price_data_tool_definition",
    "get_query_memory_tool_definition",
    "get_remove_symbol_tool_definition",
    "get_send_message_tool_definition",
    "get_store_strategy_seed_tool_definition",
    "get_vote_decision_tool_definition",
    "get_wait_response_tool_definition",
]


class AgentTools:
    """Unified interface for all agent tools.

    Delegates execution to specialized tool executors while maintaining
    a unified API for backward compatibility.
    """

    def __init__(
        self,
        storage: PortfolioStorage,
        news_service: NewsService,
        fred_source: FREDSource,
        price_fetcher: PriceDataFetcher,
        portfolio_mgr: PortfolioManager,
        analytics: PortfolioAnalytics,
    ) -> None:
        """Initialize agent tools orchestrator.

        Args:
            storage: PortfolioStorage instance
            news_service: NewsService instance
            fred_source: FREDSource instance
            price_fetcher: PriceDataFetcher instance
            portfolio_mgr: PortfolioManager instance
            analytics: PortfolioAnalytics instance
        """
        # Store dependencies for direct access
        self.storage = storage

        # Initialize specialized executors
        self.data = DataTools(
            storage=storage,
            news_service=news_service,
            fred_source=fred_source,
            portfolio_mgr=portfolio_mgr,
            analytics=analytics,
            price_fetcher=price_fetcher,
        )
        self.trading = TradingTools(storage=storage)
        self.collaboration = CollaborationTools(storage=storage)

    # Data tools - delegate to DataTools
    def execute_get_news(self, query: str, max_results: int | None = None) -> dict[str, object]:
        """Execute get_news tool."""
        return self.data.execute_get_news(query, max_results)

    def execute_get_economic_data(self, indicators: list[str]) -> dict[str, object]:
        """Execute get_economic_data tool."""
        return self.data.execute_get_economic_data(indicators)

    def execute_get_portfolio_data(self) -> dict[str, object]:
        """Execute get_portfolio_data tool."""
        return self.data.execute_get_portfolio_data()

    def execute_get_price_data(self, symbols: list[str]) -> dict[str, object]:
        """Execute get_price_data tool."""
        return self.data.execute_get_price_data(symbols)

    # Trading tools - delegate to TradingTools
    def execute_store_strategy_seed(
        self,
        agent_run_id: str,
        symbol: str,
        thesis: str,
        confidence: float,
        source_data: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Execute store_strategy_seed tool."""
        return self.trading.execute_store_strategy_seed(
            agent_run_id, symbol, thesis, confidence, source_data
        )

    def execute_add_symbol(
        self,
        agent_run_id: str,
        symbol: str,
        reason: str,
        expected_return_pct: float,
        time_horizon_days: int,
    ) -> dict[str, object]:
        """Execute add_symbol tool."""
        return self.trading.execute_add_symbol(
            agent_run_id, symbol, reason, expected_return_pct, time_horizon_days
        )

    def execute_remove_symbol(
        self, agent_run_id: str, symbol: str, reason: str
    ) -> dict[str, object]:
        """Execute remove_symbol tool."""
        return self.trading.execute_remove_symbol(agent_run_id, symbol, reason)

    # Collaboration tools - delegate to CollaborationTools
    def execute_send_message_to_agent(
        self,
        agent_run_id: str,
        agent_type: str,
        message_type: str,
        message: str,
        data: dict[str, object] | None = None,
        priority: int = 5,
    ) -> dict[str, object]:
        """Execute send_message_to_agent tool."""
        return self.collaboration.execute_send_message_to_agent(
            agent_run_id, agent_type, message_type, message, data, priority
        )

    def execute_query_agent_memory(self, workflow_id: str, key: str) -> dict[str, object]:
        """Execute query_agent_memory tool."""
        return self.collaboration.execute_query_agent_memory(workflow_id, key)

    def execute_vote_on_decision(
        self,
        agent_run_id: str,
        workflow_id: str,
        decision_id: str,
        vote: str,
        reasoning: str,
        confidence: float | None = None,
    ) -> dict[str, object]:
        """Execute vote_on_decision tool."""
        return self.collaboration.execute_vote_on_decision(
            agent_run_id, workflow_id, decision_id, vote, reasoning, confidence
        )

    def execute_wait_for_agent_response(
        self, message_id: str, timeout_seconds: int = 300
    ) -> dict[str, object]:
        """Execute wait_for_agent_response tool."""
        return self.collaboration.execute_wait_for_agent_response(message_id, timeout_seconds)
