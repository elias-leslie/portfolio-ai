"""Paper trading tracker for agent idea performance.

This module provides the public API for creating and updating paper trades
to track the real-world performance of AI agent investment ideas.

The implementation is split across focused modules:
- paper_trading_orders: Order creation and management
- paper_trading_portfolio: Portfolio calculations and updates
"""

from __future__ import annotations

from app.analytics.paper_trading_orders import create_paper_trade_from_idea
from app.analytics.paper_trading_portfolio import update_all_paper_trades
from app.analytics.types import PaperTradeDict, PaperTradeStatsDict
from app.storage import PortfolioStorage


def create_paper_trade(storage: PortfolioStorage, idea_id: str) -> PaperTradeDict | None:
    """Create a paper trade entry for an agent idea.

    Extracts idea details from agent_ideas table, fetches current price,
    calculates stop-loss based on ATR, and creates idea_outcomes record.

    Args:
        storage: PortfolioStorage instance for database access
        idea_id: ID of the agent idea to track

    Returns:
        Dict with paper trade details if successful, None if failed
        - ticker: Stock ticker symbol
        - entry_price: Current market price
        - stop_loss_price: Calculated stop loss (entry - 2xATR)
        - target_price: From agent idea (if available)
        - status: 'open'

    Example:
        >>> storage = get_storage()
        >>> trade = create_paper_trade(storage, "idea-123")
        >>> print(f"Created paper trade for {trade['ticker']} at ${trade['entry_price']}")
    """
    return create_paper_trade_from_idea(storage, idea_id)


def update_paper_trades(
    storage: PortfolioStorage, max_holding_days: int = 60
) -> PaperTradeStatsDict:
    """Update all open paper trades with current prices and check for exits.

    Fetches current prices for all open trades, updates returns, and closes
    trades that hit target/stop or exceed max holding period.

    Args:
        storage: PortfolioStorage instance for database access
        max_holding_days: Maximum days to hold before auto-closing (default: 60)

    Returns:
        Dict with update statistics:
        - trades_updated: Number of trades updated
        - trades_closed: Number of trades closed
        - target_hits: Number of target price hits
        - stop_hits: Number of stop loss hits
        - expired: Number of trades closed due to time limit

    Example:
        >>> storage = get_storage()
        >>> stats = update_paper_trades(storage, max_holding_days=60)
        >>> print(f"Updated {stats['trades_updated']} trades, closed {stats['trades_closed']}")
    """
    return update_all_paper_trades(storage, max_holding_days)
