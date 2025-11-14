"""Order execution engine for paper trading.

This module handles executing market orders (instant fills) for paper trading.
Phase A MVP: Simple instant fills at current price, no order states.
Phase B: Advanced order types (limit, stop), fill simulation with slippage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from app.analytics.cash_manager import CashManager
from app.analytics.transaction_logger import TransactionLogger
from app.logging_config import get_logger
from app.portfolio.price_fetcher import PriceDataFetcher

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


class OrderExecutor:
    """Executes paper trading orders with cash management and transaction logging."""

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize order executor.

        Args:
            storage: PortfolioStorage instance for database operations
        """
        self.storage = storage
        self.cash_manager = CashManager(storage)
        self.transaction_logger = TransactionLogger(storage)
        self.price_fetcher = PriceDataFetcher(storage)

    def execute_market_order(  # noqa: PLR0911
        self,
        ticker: str,
        action: Literal["buy", "sell"],
        shares: int,
        account_id: str,
        trade_id: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Execute a market order with instant fill at current price.

        Phase A: Simple instant fills, no slippage.
        Phase B: Add fill simulation with slippage and spread.

        Args:
            ticker: Stock symbol
            action: "buy" or "sell"
            shares: Number of shares to trade
            account_id: Portfolio account ID
            trade_id: Optional trade ID for transaction logging
            notes: Optional notes for transaction log

        Returns:
            Dictionary with execution results:
                {
                    "filled": bool,
                    "ticker": str,
                    "action": str,
                    "shares": int,
                    "price": float,
                    "amount": float,
                    "cash_before": float,
                    "cash_after": float,
                    "error": str | None
                }
        """
        if shares <= 0:
            return {
                "filled": False,
                "error": f"Invalid shares: {shares} (must be positive)",
            }

        # Fetch current price
        try:
            price_data_dict = self.price_fetcher.fetch_price_data([ticker])
            current_price = price_data_dict[ticker].price
        except Exception as e:
            logger.error(f"Failed to fetch price for {ticker}: {e}")
            return {
                "filled": False,
                "error": f"Failed to fetch price for {ticker}: {e}",
            }

        # Calculate order amount
        amount = shares * current_price

        # Get cash balance before transaction
        try:
            cash_before = self.cash_manager.get_cash_balance(account_id)
        except ValueError as e:
            return {"filled": False, "error": str(e)}

        # Execute order based on action
        if action == "buy":
            # Check sufficient cash
            if not self.cash_manager.check_sufficient_cash(account_id, amount):
                return {
                    "filled": False,
                    "ticker": ticker,
                    "action": action,
                    "shares": shares,
                    "price": current_price,
                    "amount": amount,
                    "cash_before": cash_before,
                    "error": f"Insufficient cash: need ${amount:.2f}, have ${cash_before:.2f}",
                }

            # Deduct cash
            reason = notes or f"Buy {shares} shares of {ticker} @ ${current_price:.2f}"
            success = self.cash_manager.deduct_cash(account_id, amount, reason)

            if not success:
                return {
                    "filled": False,
                    "ticker": ticker,
                    "action": action,
                    "error": "Failed to deduct cash",
                }

        elif action == "sell":
            # Add cash
            reason = notes or f"Sell {shares} shares of {ticker} @ ${current_price:.2f}"
            success = self.cash_manager.add_cash(account_id, amount, reason)

            if not success:
                return {
                    "filled": False,
                    "ticker": ticker,
                    "action": action,
                    "error": "Failed to add cash",
                }

        else:
            return {"filled": False, "error": f"Invalid action: {action}"}

        # Get cash balance after transaction
        cash_after = self.cash_manager.get_cash_balance(account_id)

        # Log transaction if trade_id provided
        if trade_id:
            if action == "buy":
                self.transaction_logger.log_entry(
                    trade_id=trade_id,
                    ticker=ticker,
                    shares=shares,
                    price=current_price,
                    cash_before=cash_before,
                    cash_after=cash_after,
                    notes=notes,
                )
            else:  # sell
                # Calculate P&L (requires entry price from trade record)
                pnl = 0.0  # Will be calculated by caller with entry price
                self.transaction_logger.log_exit(
                    trade_id=trade_id,
                    ticker=ticker,
                    shares=shares,
                    price=current_price,
                    cash_before=cash_before,
                    cash_after=cash_after,
                    pnl=pnl,
                    notes=notes,
                )

        logger.info(
            f"Market order filled: {action.upper()} {shares} {ticker} @ ${current_price:.2f} "
            f"(${amount:.2f}, cash: ${cash_before:.2f} → ${cash_after:.2f})"
        )

        return {
            "filled": True,
            "ticker": ticker,
            "action": action,
            "shares": shares,
            "price": current_price,
            "amount": amount,
            "cash_before": cash_before,
            "cash_after": cash_after,
            "error": None,
        }

    def calculate_max_shares(
        self, ticker: str, account_id: str, max_position_pct: float = 0.05
    ) -> int:
        """Calculate maximum shares affordable for a position.

        Uses simple equal-weight position sizing (5% of account by default).

        Args:
            ticker: Stock symbol
            account_id: Portfolio account ID
            max_position_pct: Maximum position size as % of account (default 5%)

        Returns:
            Maximum number of shares affordable
        """
        try:
            # Get current cash balance
            cash_balance = self.cash_manager.get_cash_balance(account_id)

            # Calculate position size
            max_position_amount = cash_balance * max_position_pct

            # Get current price
            price_data_dict = self.price_fetcher.fetch_price_data([ticker])
            current_price = price_data_dict[ticker].price

            # Calculate max shares
            max_shares = int(max_position_amount / current_price)

            return max_shares

        except Exception as e:
            logger.error(f"Failed to calculate max shares for {ticker}: {e}")
            return 0
