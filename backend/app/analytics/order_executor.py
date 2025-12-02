"""Order execution engine for paper trading.

This module handles executing market orders (instant fills) for paper trading.
Phase A MVP: Simple instant fills at current price, no order states.
Phase B: Advanced order types (limit, stop), fill simulation with slippage.

VISION.md P2 Compliance:
- Max 5% of portfolio per position
- Max 20% exposure per sector

GAP-023 Compliance:
- Portfolio-level trading halt at -10% drawdown
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

from app.analytics.cash_manager import CashManager
from app.analytics.transaction_logger import TransactionLogger
from app.logging_config import get_logger
from app.portfolio.drawdown import check_portfolio_drawdown_halt
from app.portfolio.price_fetcher import PriceDataFetcher

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

# VISION.md P2 position limits
MAX_POSITION_PCT = 0.05  # 5% of portfolio per position
MAX_SECTOR_EXPOSURE_PCT = 0.20  # 20% max exposure per sector


class OrderExecutionResult(TypedDict, total=False):
    """Result of executing a market order."""

    filled: bool
    ticker: str
    action: str
    shares: int
    price: float
    amount: float
    cash_before: float
    cash_after: float
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
        ticker: str,
        action: Literal["buy", "sell"],
        shares: int,
        account_id: str,
        trade_id: str | None = None,
        notes: str | None = None,
    ) -> OrderExecutionResult:
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
            # GAP-023: Check portfolio drawdown halt (no new buys at -10% drawdown)
            can_trade, halt_reason = check_portfolio_drawdown_halt(self.storage, account_id)
            if not can_trade:
                return {
                    "filled": False,
                    "ticker": ticker,
                    "action": action,
                    "shares": shares,
                    "price": current_price,
                    "amount": amount,
                    "cash_before": cash_before,
                    "error": halt_reason or "Trading halted due to portfolio drawdown",
                }

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

            # P2: Check position size and sector exposure limits
            valid, limit_error = self.validate_position_limits(ticker, amount, account_id)
            if not valid:
                logger.warning(f"Position limits exceeded for {ticker}: {limit_error}")
                return {
                    "filled": False,
                    "ticker": ticker,
                    "action": action,
                    "shares": shares,
                    "price": current_price,
                    "amount": amount,
                    "cash_before": cash_before,
                    "error": limit_error,
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
        self, ticker: str, account_id: str, max_position_pct: float = MAX_POSITION_PCT
    ) -> int:
        """Calculate maximum shares affordable for a position.

        Uses simple equal-weight position sizing (5% of account by default per P2).

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

    def get_ticker_sector(self, ticker: str) -> str | None:
        """Get the sector for a given ticker from price_cache.

        Args:
            ticker: Stock symbol

        Returns:
            Sector name or None if not found
        """
        query = """
            SELECT sector FROM price_cache
            WHERE ticker = $1 AND sector IS NOT NULL AND sector != ''
            ORDER BY cached_at DESC LIMIT 1
        """
        result = self.storage.query(query, [ticker])
        if result.is_empty():
            return None
        return str(result.get_column("sector")[0])

    def get_sector_exposure(self, account_id: str, sector: str) -> float:
        """Calculate current exposure to a sector as % of portfolio value.

        Args:
            account_id: Portfolio account ID
            sector: Sector name to check

        Returns:
            Sector exposure as decimal (0.15 = 15%)
        """
        # Get all positions for this account
        positions_query = """
            SELECT pp.ticker, pp.shares, pp.current_price
            FROM portfolio_positions pp
            JOIN portfolio_accounts pa ON pp.account_id = pa.id
            WHERE pa.id = $1
        """
        positions = self.storage.query(positions_query, [account_id])

        if positions.is_empty():
            return 0.0

        # Get total portfolio value (cash + positions)
        cash_balance = self.cash_manager.get_cash_balance(account_id)
        total_position_value = 0.0
        sector_value = 0.0

        for row in positions.iter_rows(named=True):
            ticker = row["ticker"]
            shares = row["shares"] or 0
            price = row["current_price"] or 0.0
            position_value = shares * price
            total_position_value += position_value

            # Check if this position is in the target sector
            pos_sector = self.get_ticker_sector(ticker)
            if pos_sector and pos_sector.lower() == sector.lower():
                sector_value += position_value

        portfolio_value = cash_balance + total_position_value
        if portfolio_value <= 0:
            return 0.0

        return sector_value / portfolio_value

    def validate_position_limits(
        self, ticker: str, amount: float, account_id: str
    ) -> tuple[bool, str | None]:
        """Validate position against P2 limits (5% position, 20% sector).

        Args:
            ticker: Stock symbol
            amount: Dollar amount of proposed position
            account_id: Portfolio account ID

        Returns:
            Tuple of (valid, error_message)
        """
        try:
            # Get portfolio value
            cash_balance = self.cash_manager.get_cash_balance(account_id)

            # Calculate total portfolio value including positions
            positions_query = """
                SELECT COALESCE(SUM(shares * current_price), 0) as position_value
                FROM portfolio_positions
                WHERE account_id = $1
            """
            result = self.storage.query(positions_query, [account_id])
            position_value = float(result.get_column("position_value")[0] or 0)
            portfolio_value = cash_balance + position_value

            if portfolio_value <= 0:
                return False, "Portfolio value is zero or negative"

            # Check position size limit (5%)
            position_pct = amount / portfolio_value
            if position_pct > MAX_POSITION_PCT:
                return False, (
                    f"Position size {position_pct:.1%} exceeds {MAX_POSITION_PCT:.0%} limit. "
                    f"Max allowed: ${portfolio_value * MAX_POSITION_PCT:.2f}"
                )

            # Check sector exposure limit (20%)
            sector = self.get_ticker_sector(ticker)
            if sector:
                current_exposure = self.get_sector_exposure(account_id, sector)
                new_exposure = current_exposure + (amount / portfolio_value)
                if new_exposure > MAX_SECTOR_EXPOSURE_PCT:
                    return False, (
                        f"Sector '{sector}' exposure would be {new_exposure:.1%}, "
                        f"exceeding {MAX_SECTOR_EXPOSURE_PCT:.0%} limit"
                    )

            return True, None

        except Exception as e:
            logger.error(f"Failed to validate position limits for {ticker}: {e}")
            return True, None  # Allow trade if validation fails (fail-open)
