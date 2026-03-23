"""Order calculation utilities for position sizing.

Extracted from order_executor.py to improve modularity.
Handles max shares calculation and risk-based position sizing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.analytics.cash_manager import CashManager
from app.analytics.order_validators import MAX_POSITION_PCT
from app.logging_config import get_logger
from app.portfolio.price_fetcher import PriceDataFetcher

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


def calculate_max_shares(
    storage: PortfolioStorage,
    symbol: str,
    account_id: str,
    max_position_pct: float = MAX_POSITION_PCT,
) -> int:
    """Calculate maximum shares affordable for a position.

    Uses simple equal-weight position sizing (5% of account by default per P2).

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        account_id: Portfolio account ID
        max_position_pct: Maximum position size as % of account (default 5%)

    Returns:
        Maximum number of shares affordable
    """
    try:
        cash_manager = CashManager(storage)
        price_fetcher = PriceDataFetcher(storage)

        # Get current cash balance
        cash_balance = cash_manager.get_cash_balance(account_id)

        # Calculate position size
        max_position_amount = cash_balance * max_position_pct

        # Get current price
        price_data_dict = price_fetcher.fetch_price_data([symbol])
        current_price = price_data_dict[symbol].price

        # Calculate max shares
        max_shares = int(max_position_amount / current_price)

        return max_shares

    except Exception as e:
        logger.error("max_shares_calc_failed", symbol=symbol, error=str(e), exc_info=True)
        return 0


def calculate_risk_based_shares(
    storage: PortfolioStorage,
    symbol: str,
    account_id: str,
    stop_loss: float | None = None,
    risk_percent: float = 0.015,
) -> tuple[int, dict[str, float | str | None]]:
    """Calculate position size using risk-based sizing (GAP-043).

    Integrates with position_sizing module for proper risk management.
    Formula: shares = (risk_percent * equity) / (entry_price - stop_loss)

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        account_id: Portfolio account ID
        stop_loss: Stop-loss price. If None, calculates ATR-based stop.
        risk_percent: Risk per trade as fraction (0.015 = 1.5%)

    Returns:
        Tuple of (shares, details dict)
    """
    from app.analytics.trade_calculations import calculate_stop_loss  # noqa: PLC0415

    default_risk_pct = 0.015  # 1.5% per trade

    cash_manager = CashManager(storage)
    price_fetcher = PriceDataFetcher(storage)

    details: dict[str, float | str | None] = {
        "symbol": symbol,
        "account_id": account_id,
        "equity": None,
        "entry_price": None,
        "stop_loss": None,
        "stop_distance_pct": None,
        "risk_percent": risk_percent or default_risk_pct,
        "shares": 0,
        "position_value": None,
        "error": None,
    }

    try:
        # Get current price (entry price)
        price_data_dict = price_fetcher.fetch_price_data([symbol])
        entry_price = price_data_dict[symbol].price
        details["entry_price"] = entry_price

        # Get portfolio equity
        cash_balance = cash_manager.get_cash_balance(account_id)
        # For paper trading, just use cash as equity
        # Real portfolio would need to join with day_bars for current prices
        equity = cash_balance
        details["equity"] = equity

        # Get or calculate stop loss
        if stop_loss is None:
            stop_loss = calculate_stop_loss(storage, symbol, entry_price)
            if stop_loss is None:
                details["error"] = "Cannot calculate ATR-based stop loss"
                return 0, details

        details["stop_loss"] = stop_loss

        # Calculate stop distance as percentage
        if stop_loss and entry_price > stop_loss:
            details["stop_distance_pct"] = (entry_price - stop_loss) / entry_price

        # Risk-based position sizing: shares = (risk_pct * equity) / risk_per_share
        effective_risk = risk_percent or default_risk_pct
        risk_amount = effective_risk * equity
        risk_per_share = entry_price - stop_loss
        if risk_per_share <= 0:
            details["error"] = "Stop loss must be below entry price"
            return 0, details

        shares = int(risk_amount / risk_per_share)
        position_value = shares * entry_price

        details["risk_amount"] = risk_amount
        details["risk_per_share"] = risk_per_share
        details["shares"] = float(shares)
        details["position_value"] = position_value
        details["position_percent"] = position_value / equity if equity > 0 else None

        return shares, details

    except Exception as e:
        logger.error("risk_shares_calc_failed", symbol=symbol, error=str(e), exc_info=True)
        details["error"] = str(e)
        return 0, details
