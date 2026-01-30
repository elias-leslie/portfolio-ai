"""Order execution engine for paper trading.

This module handles executing market orders (instant fills) for paper trading.
Phase A MVP: Simple instant fills at current price, no order states.
Phase B: Fill simulation with slippage using costs.py infrastructure.

VISION.md P2 Compliance:
- Max 5% of portfolio per position
- Max 20% exposure per sector
- Max 2% single trade loss (from rules.yaml)

GAP-023 Compliance:
- Portfolio-level trading halt at -10% drawdown

FEAT-210 Compliance:
- Track slippage (expected vs actual fill prices)
- Store slippage metrics in transactions
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

from app.analytics.cash_manager import CashManager
from app.analytics.order_calculations import (
    calculate_max_shares,
    calculate_risk_based_shares,
)
from app.analytics.order_execution_helpers import (
    execute_buy_order,
    execute_sell_order,
    log_order_transaction,
)
from app.analytics.order_validators import (
    MAX_POSITION_PCT,
    get_sector_exposure,
    get_symbol_sector,
)
from app.analytics.slippage_calculator import calculate_order_slippage
from app.analytics.transaction_logger import TransactionLogger
from app.logging_config import get_logger
from app.portfolio.price_fetcher import PriceDataFetcher

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


class OrderExecutionResult(TypedDict, total=False):
    """Result of executing a market order."""

    filled: bool
    symbol: str
    action: str
    shares: int
    price: float  # Actual fill price (after slippage)
    expected_price: float  # Price before slippage
    amount: float
    cash_before: float
    cash_after: float
    slippage_amount: float
    slippage_bps: float
    adv: float | None
    slippage_model: str
    error: str | None


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
        symbol: str,
        action: Literal["buy", "sell"],
        shares: int,
        account_id: str,
        trade_id: str | None = None,
        notes: str | None = None,
        apply_slippage: bool = True,
    ) -> OrderExecutionResult:
        """Execute a market order with fill simulation including slippage.

        Phase B: Fill simulation with slippage using costs.py infrastructure.
        Slippage model uses FIXED_PCT (5 bps) by default, or DYNAMIC if ADV available.

        Args:
            symbol: Stock symbol
            action: "buy" or "sell"
            shares: Number of shares to trade
            account_id: Portfolio account ID
            trade_id: Optional trade ID for transaction logging
            notes: Optional notes for transaction log
            apply_slippage: Whether to apply slippage (default True)

        Returns:
            Dictionary with execution results including slippage metrics
        """
        if shares <= 0:
            return {
                "filled": False,
                "error": f"Invalid shares: {shares} (must be positive)",
            }

        # Fetch current price (expected price before slippage)
        try:
            price_data_dict = self.price_fetcher.fetch_price_data([symbol])
            expected_price = price_data_dict[symbol].price
        except Exception as e:
            logger.error(f"Failed to fetch price for {symbol}: {e}")
            return {
                "filled": False,
                "error": f"Failed to fetch price for {symbol}: {e}",
            }

        # Calculate slippage using extracted module
        slippage_result = calculate_order_slippage(
            self.storage, symbol, expected_price, shares, apply_slippage
        )

        # Apply slippage to price
        # For buys: slippage increases price (we pay more)
        # For sells: slippage decreases price (we receive less)
        if action == "buy":
            fill_price = expected_price + float(slippage_result.slippage_per_share)
        else:
            fill_price = expected_price - float(slippage_result.slippage_per_share)

        # Calculate slippage amount (always positive cost)
        slippage_amount = float(slippage_result.slippage_per_share) * shares

        # Calculate order amount (based on fill price)
        amount = shares * fill_price

        # Get cash balance before transaction
        try:
            cash_before = self.cash_manager.get_cash_balance(account_id)
        except ValueError as e:
            return {"filled": False, "error": str(e)}

        # Execute order based on action
        if action == "buy":
            success, error = execute_buy_order(
                self.storage,
                symbol,
                shares,
                fill_price,
                expected_price,
                amount,
                account_id,
                cash_before,
                notes,
            )
            if not success:
                return {
                    "filled": False,
                    "symbol": symbol,
                    "action": action,
                    "shares": shares,
                    "price": fill_price,
                    "expected_price": expected_price,
                    "amount": amount,
                    "cash_before": cash_before,
                    "error": error,
                }

        elif action == "sell":
            success, error = execute_sell_order(
                self.storage, symbol, shares, fill_price, amount, account_id, notes
            )
            if not success:
                return {
                    "filled": False,
                    "symbol": symbol,
                    "action": action,
                    "error": error,
                }

        else:
            return {"filled": False, "error": f"Invalid action: {action}"}

        # Get cash balance after transaction
        cash_after = self.cash_manager.get_cash_balance(account_id)

        # Log transaction if trade_id provided (with slippage data)
        if trade_id:
            log_order_transaction(
                self.storage,
                action,
                trade_id,
                symbol,
                shares,
                fill_price,
                expected_price,
                cash_before,
                cash_after,
                slippage_result,
                slippage_amount,
                notes,
            )

        slippage_info = ""
        if slippage_result.slippage_bps > 0:
            slippage_info = (
                f" [slippage: {slippage_result.slippage_bps:.1f}bps, ${slippage_amount:.2f}]"
            )

        logger.info(
            f"Market order filled: {action.upper()} {shares} {symbol} @ ${fill_price:.2f} "
            f"(${amount:.2f}, cash: ${cash_before:.2f} → ${cash_after:.2f}){slippage_info}"
        )

        return {
            "filled": True,
            "symbol": symbol,
            "action": action,
            "shares": shares,
            "price": fill_price,
            "expected_price": expected_price,
            "amount": amount,
            "cash_before": cash_before,
            "cash_after": cash_after,
            "slippage_amount": slippage_amount,
            "slippage_bps": slippage_result.slippage_bps,
            "adv": slippage_result.adv,
            "slippage_model": slippage_result.model_used,
            "error": None,
        }

    def calculate_max_shares(
        self, symbol: str, account_id: str, max_position_pct: float = MAX_POSITION_PCT
    ) -> int:
        """Calculate maximum shares affordable (delegates to order_calculations)."""
        return calculate_max_shares(self.storage, symbol, account_id, max_position_pct)

    def get_symbol_sector(self, symbol: str) -> str | None:
        """Get sector for symbol (delegates to order_validators)."""
        return get_symbol_sector(self.storage, symbol)

    def get_sector_exposure(self, account_id: str, sector: str) -> float:
        """Calculate sector exposure (delegates to order_validators)."""
        return get_sector_exposure(self.storage, account_id, sector)

    def calculate_risk_based_shares(
        self,
        symbol: str,
        account_id: str,
        stop_loss: float | None = None,
        risk_percent: float = 0.015,
    ) -> tuple[int, dict[str, float | str | None]]:
        """Calculate risk-based position size (delegates to order_calculations)."""
        return calculate_risk_based_shares(
            self.storage, symbol, account_id, stop_loss, risk_percent
        )
