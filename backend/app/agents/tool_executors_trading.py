"""Trading tool executors for agent trading operations.

This module provides execution logic for trading tools:
- store_idea: Store investment ideas
- add_symbol: Add symbols to watchlist
- remove_symbol: Remove symbols from watchlist
- create_paper_trade: Create paper trades
- run_backtest: Execute backtests for strategy validation

Section 1.2: Confidence → Leverage enforcement added.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.agents.trading.backtest import execute_run_backtest
from app.agents.trading.ideas import execute_store_idea, execute_store_strategy_seed
from app.agents.trading.paper_trading import execute_create_paper_trade
from app.agents.trading.watchlist import execute_add_symbol, execute_remove_symbol


class TradingTools:
    """Trading tool executors for agents."""

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize trading tools.

        Args:
            storage: PortfolioStorage instance
        """
        self.storage = storage

    def execute_store_idea(self, agent_run_id: str, **idea_data: object) -> dict[str, object]:
        """Execute store_idea tool and automatically create a paper trade.

        Args:
            agent_run_id: ID of the agent run
            **idea_data: Idea data fields

        Returns:
            Result dictionary with idea ID and status
        """
        return execute_store_idea(self.storage, agent_run_id, **idea_data)

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

    def execute_create_paper_trade(
        self,
        agent_run_id: str,
        symbol: str,
        action: str,
        thesis: str,
        target_price: float | None = None,
        stop_loss_pct: float | None = None,
        confidence_score: float = 0.7,
    ) -> dict[str, object]:
        """Execute create_paper_trade tool for autonomous paper trading.

        Creates a paper trade with automatic cash management and position sizing.
        Position size is now confidence-adjusted (Section 1.2):
        - Low confidence (0-0.4): 1.25-2.5% position
        - Medium confidence (0.4-0.6): 5% position (base)
        - High confidence (0.6-0.8): 7.5% position
        - Very high confidence (0.8-1.0): 10% position

        Args:
            agent_run_id: ID of the agent run
            symbol: Stock symbol
            action: 'buy' or 'sell'
            thesis: Investment thesis
            target_price: Optional target exit price
            stop_loss_pct: Optional stop loss percentage
            confidence_score: Confidence score (0.0-1.0) for position sizing

        Returns:
            Result dictionary with trade details or error
        """
        return execute_create_paper_trade(
            self.storage,
            agent_run_id,
            symbol,
            action,
            thesis,
            target_price,
            stop_loss_pct,
            confidence_score,
        )

    def execute_run_backtest(
        self,
        agent_run_id: str,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        strategy_name: str = "signal_classifier",
        min_signal_strength: int = 7,
        max_holding_days: int = 60,
        position_sizing_method: str = "fixed_dollars",
        position_size_value: float = 10000.0,
    ) -> dict[str, object]:
        """Execute run_backtest tool for strategy validation.

        Runs backtest synchronously and waits for completion (agents need results
        to make decisions). Runs task and blocks until done.

        Args:
            agent_run_id: ID of the agent run
            symbol: Stock symbol
            start_date: Backtest start date (ISO format: YYYY-MM-DD)
            end_date: Backtest end date (ISO format: YYYY-MM-DD)
            initial_capital: Starting capital (default: 100000.0)
            strategy_name: Strategy to use (default: 'signal_classifier')
            min_signal_strength: Minimum signal strength (1-10, default: 7)
            max_holding_days: Maximum holding period (default: 60)
            position_sizing_method: 'fixed_dollars' or 'fixed_shares' (default: 'fixed_dollars')
            position_size_value: Position size in dollars or shares (default: 10000.0)

        Returns:
            Result dictionary with backtest metrics or error
        """
        return execute_run_backtest(
            self.storage,
            agent_run_id,
            symbol,
            start_date,
            end_date,
            initial_capital,
            strategy_name,
            min_signal_strength,
            max_holding_days,
            position_sizing_method,
            position_size_value,
        )


__all__ = ["TradingTools"]
