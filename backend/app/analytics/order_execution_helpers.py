"""Helper functions for order execution.

Extracted from order_executor.py to improve modularity.
Handles buy/sell validation and transaction logging.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from app.analytics.cash_manager import CashManager
from app.analytics.order_validators import validate_position_limits
from app.analytics.slippage_calculator import SlippageResult
from app.analytics.transaction_logger import TransactionLogger
from app.logging_config import get_logger
from app.portfolio.drawdown import check_portfolio_drawdown_halt

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


def execute_buy_order(
    storage: PortfolioStorage,
    symbol: str,
    shares: int,
    fill_price: float,
    expected_price: float,
    amount: float,
    account_id: str,
    cash_before: float,
    notes: str | None,
) -> tuple[bool, str | None]:
    """Execute a buy order with all validations.

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        shares: Number of shares
        fill_price: Fill price after slippage
        expected_price: Price before slippage
        amount: Total order amount
        account_id: Portfolio account ID
        cash_before: Cash balance before transaction
        notes: Optional notes

    Returns:
        Tuple of (success, error_message)
    """
    cash_manager = CashManager(storage)

    # GAP-023: Check portfolio drawdown halt (no new buys at -10% drawdown)
    can_trade, halt_reason = check_portfolio_drawdown_halt(storage, account_id)
    if not can_trade:
        return False, halt_reason or "Trading halted due to portfolio drawdown"

    # Check sufficient cash
    if not cash_manager.check_sufficient_cash(account_id, amount):
        return (
            False,
            f"Insufficient cash: need ${amount:.2f}, have ${cash_before:.2f}",
        )

    # P2: Check position size and sector exposure limits
    valid, limit_error = validate_position_limits(storage, symbol, amount, account_id)
    if not valid:
        logger.warning(f"Position limits exceeded for {symbol}: {limit_error}")
        return False, limit_error

    # Deduct cash
    reason = notes or f"Buy {shares} shares of {symbol} @ ${fill_price:.2f}"
    success = cash_manager.deduct_cash(account_id, amount, reason)

    if not success:
        return False, "Failed to deduct cash"

    return True, None


def execute_sell_order(
    storage: PortfolioStorage,
    symbol: str,
    shares: int,
    fill_price: float,
    amount: float,
    account_id: str,
    notes: str | None,
) -> tuple[bool, str | None]:
    """Execute a sell order.

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        shares: Number of shares
        fill_price: Fill price after slippage
        amount: Total order amount
        account_id: Portfolio account ID
        notes: Optional notes

    Returns:
        Tuple of (success, error_message)
    """
    cash_manager = CashManager(storage)

    # Add cash
    reason = notes or f"Sell {shares} shares of {symbol} @ ${fill_price:.2f}"
    success = cash_manager.add_cash(account_id, amount, reason)

    if not success:
        return False, "Failed to add cash"

    return True, None


def log_order_transaction(
    storage: PortfolioStorage,
    action: Literal["buy", "sell"],
    trade_id: str,
    symbol: str,
    shares: int,
    fill_price: float,
    expected_price: float,
    cash_before: float,
    cash_after: float,
    slippage_result: SlippageResult,
    slippage_amount: float,
    notes: str | None = None,
) -> None:
    """Log order transaction to database.

    Args:
        storage: PortfolioStorage instance
        action: Buy or sell
        trade_id: Trade ID
        symbol: Stock symbol
        shares: Number of shares
        fill_price: Fill price after slippage
        expected_price: Price before slippage
        cash_before: Cash balance before
        cash_after: Cash balance after
        slippage_result: Slippage calculation result
        slippage_amount: Total slippage cost
        notes: Optional notes
    """
    transaction_logger = TransactionLogger(storage)

    if action == "buy":
        transaction_logger.log_entry(
            trade_id=trade_id,
            symbol=symbol,
            shares=shares,
            price=fill_price,
            cash_before=cash_before,
            cash_after=cash_after,
            notes=notes,
            expected_price=expected_price,
            slippage_amount=slippage_amount,
            slippage_bps=slippage_result.slippage_bps,
            adv=slippage_result.adv,
            slippage_model=slippage_result.model_used,
        )
    else:  # sell
        # Calculate P&L (requires entry price from trade record)
        pnl = 0.0  # Will be calculated by caller with entry price
        transaction_logger.log_exit(
            trade_id=trade_id,
            symbol=symbol,
            shares=shares,
            price=fill_price,
            cash_before=cash_before,
            cash_after=cash_after,
            pnl=pnl,
            notes=notes,
            expected_price=expected_price,
            slippage_amount=slippage_amount,
            slippage_bps=slippage_result.slippage_bps,
            adv=slippage_result.adv,
            slippage_model=slippage_result.model_used,
        )
