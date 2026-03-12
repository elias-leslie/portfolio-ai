"""Order validation logic for position limits and risk management.

Extracted from order_executor.py to improve modularity.
Handles P2 compliance checks (max position, sector exposure, trade loss limits).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.analytics.cash_manager import CashManager
from app.logging_config import get_logger
from app.rules.loader import get_rules

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

# VISION.md P2 position limits
MAX_POSITION_PCT = 0.05  # 5% of portfolio per position
MAX_SECTOR_EXPOSURE_PCT = 0.20  # 20% max exposure per sector


def get_symbol_sector(storage: PortfolioStorage, symbol: str) -> str | None:
    """Get the sector for a given symbol from price_cache.

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol

    Returns:
        Sector name or None if not found
    """
    query = """
        SELECT sector FROM price_cache
        WHERE symbol = $1 AND sector IS NOT NULL AND sector != ''
        ORDER BY cached_at DESC LIMIT 1
    """
    result = storage.query(query, [symbol])
    if result.is_empty():
        return None
    return str(result.get_column("sector")[0])


def get_sector_exposure(storage: PortfolioStorage, account_id: str, sector: str) -> float:
    """Calculate current exposure to a sector as % of portfolio value.

    Args:
        storage: PortfolioStorage instance
        account_id: Portfolio account ID
        sector: Sector name to check

    Returns:
        Sector exposure as decimal (0.15 = 15%)
    """
    cash_manager = CashManager(storage)

    # Get all positions for this account with current prices from day_bars
    positions_query = """
        SELECT pp.symbol, pp.shares,
               COALESCE(db.close, pp.cost_basis) as price
        FROM portfolio_positions pp
        LEFT JOIN LATERAL (
            SELECT close FROM day_bars
            WHERE symbol = pp.symbol
            ORDER BY date DESC LIMIT 1
        ) db ON true
        WHERE pp.account_id = $1
    """
    positions = storage.query(positions_query, [account_id])

    if positions.is_empty():
        return 0.0

    # Get total portfolio value (cash + positions)
    cash_balance = cash_manager.get_cash_balance(account_id)
    total_position_value = 0.0
    sector_value = 0.0

    for row in positions.iter_rows(named=True):
        symbol = row["symbol"]
        shares = row["shares"] or 0
        price = row["price"] or 0.0
        position_value = shares * price
        total_position_value += position_value

        # Check if this position is in the target sector
        pos_sector = get_symbol_sector(storage, symbol)
        if pos_sector and pos_sector.lower() == sector.lower():
            sector_value += position_value

    portfolio_value = cash_balance + total_position_value
    if portfolio_value <= 0:
        return 0.0

    return sector_value / portfolio_value


def validate_position_limits(
    storage: PortfolioStorage, symbol: str, amount: float, account_id: str
) -> tuple[bool, str | None]:
    """Validate position against P2 limits (5% position, 20% sector, max single trade loss).

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        amount: Dollar amount of proposed position
        account_id: Portfolio account ID

    Returns:
        Tuple of (valid, error_message)
    """
    try:
        cash_manager = CashManager(storage)

        # Get portfolio value
        cash_balance = cash_manager.get_cash_balance(account_id)

        # For paper trading, just use cash balance as portfolio value
        # Real portfolio would need to join with day_bars for current prices
        portfolio_value = cash_balance

        if portfolio_value <= 0:
            return False, "Portfolio value is zero or negative"

        # Check position size limit (5%)
        position_pct = amount / portfolio_value
        if position_pct > MAX_POSITION_PCT:
            return False, (
                f"Position size {position_pct:.1%} exceeds {MAX_POSITION_PCT:.0%} limit. "
                f"Max allowed: ${portfolio_value * MAX_POSITION_PCT:.2f}"
            )

        # Check max single trade loss limit (from rules engine)
        rules = get_rules()
        max_loss_pct = rules.risk_management.max_single_trade_loss_pct / 100.0  # Convert to decimal
        max_allowed_loss = portfolio_value * max_loss_pct

        # Potential loss = position amount (worst case: 100% loss)
        # In practice, stop-loss would limit this, but we check worst case
        potential_loss = amount

        if potential_loss > max_allowed_loss:
            return False, (
                f"Potential loss ${potential_loss:.2f} exceeds max single trade loss limit "
                f"of {rules.risk_management.max_single_trade_loss_pct:.1f}% "
                f"(${max_allowed_loss:.2f})"
            )

        # Check sector exposure limit (20%)
        sector = get_symbol_sector(storage, symbol)
        if sector:
            current_exposure = get_sector_exposure(storage, account_id, sector)
            new_exposure = current_exposure + (amount / portfolio_value)
            if new_exposure > MAX_SECTOR_EXPOSURE_PCT:
                return False, (
                    f"Sector '{sector}' exposure would be {new_exposure:.1%}, "
                    f"exceeding {MAX_SECTOR_EXPOSURE_PCT:.0%} limit"
                )

        return True, None

    except Exception as e:
        logger.error("position_limits_validation_failed", symbol=symbol, error=str(e), exc_info=True)
        return True, None  # Allow trade if validation fails (fail-open)
