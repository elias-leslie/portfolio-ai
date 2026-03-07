"""Trading tool executors for agent trading operations.

This module provides execution logic for trading tools:
- store_strategy_seed: Store investment strategy seeds
- add_symbol: Add symbols to watchlist
- remove_symbol: Remove symbols from watchlist

Section 1.2: Confidence → Leverage enforcement added.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.agents.trading.ideas import execute_store_strategy_seed
from app.agents.trading.watchlist import execute_add_symbol, execute_remove_symbol


class TradingTools:
    """Trading tool executors for agents."""

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize trading tools.

        Args:
            storage: PortfolioStorage instance
        """
        self.storage = storage

    def execute_store_strategy_seed(
        self,
        agent_run_id: str,
        symbol: str,
        thesis: str,
        confidence: float,
        source_data: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Execute store_strategy_seed tool to create a strategy seed.

        Seeds are AI-generated investment ideas with required symbol. High-confidence
        seeds (>=7) automatically trigger strategy_research_workflow.

        Args:
            agent_run_id: ID of the agent run
            symbol: Stock symbol (REQUIRED - fixes broken Ideas system)
            thesis: Investment thesis explaining the opportunity
            confidence: Confidence score (1-10 scale)
            source_data: Optional context data (news, economic indicators)

        Returns:
            Result dictionary with seed ID, status, and workflow trigger info
        """
        return execute_store_strategy_seed(
            self.storage, agent_run_id, symbol, thesis, confidence, source_data
        )

    def execute_add_symbol(
        self,
        agent_run_id: str,
        symbol: str,
        reason: str,
        expected_return_pct: float,
        time_horizon_days: int,
    ) -> dict[str, object]:
        """Execute add_symbol tool to autonomously add symbols to watchlist.

        Args:
            agent_run_id: ID of the agent run (for ownership tracking)
            symbol: Stock symbol
            reason: Why adding this symbol
            expected_return_pct: Expected return percentage
            time_horizon_days: Time horizon in days

        Returns:
            Result dictionary with status and details
        """
        return execute_add_symbol(
            self.storage, agent_run_id, symbol, reason, expected_return_pct, time_horizon_days
        )

    def execute_remove_symbol(
        self, agent_run_id: str, symbol: str, reason: str
    ) -> dict[str, object]:
        """Execute remove_symbol tool with ownership validation.

        Agents can ONLY remove symbols they added. This prevents agents from
        removing user-added symbols or symbols added by other agents.

        Args:
            agent_run_id: ID of the agent run
            symbol: Stock symbol to remove
            reason: Why removing this symbol

        Returns:
            Result dictionary with status and details
        """
        return execute_remove_symbol(self.storage, agent_run_id, symbol, reason)

__all__ = ["TradingTools"]
