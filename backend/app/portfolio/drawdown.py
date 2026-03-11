"""Portfolio drawdown tracking and risk management.

This module implements GAP-023: Real-time drawdown tracking with portfolio-level
stop at -25% to prevent catastrophic losses.

Features:
- Real-time drawdown calculation from peak equity
- Max drawdown tracking per position and portfolio
- Portfolio-level trading halt at -25% drawdown
- Drawdown recovery tracking (underwater days)
- Historical drawdown curve for analysis

Note: Thresholds are now loaded from centralized rules engine (v1.0.0).
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from ..logging_config import get_logger
from .drawdown_calc import (
    calculate_drawdown,
    calculate_position_drawdown,
    get_recovery_estimate,
)
from .drawdown_db import (
    calculate_underwater_days,
    get_drawdown_history,
    get_peak_equity,
    get_portfolio_equity,
    save_portfolio_snapshot,
)
from .drawdown_models import DrawdownMetrics, PositionDrawdown

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)


# Portfolio-level risk limits (GAP-023)
PORTFOLIO_DRAWDOWN_HALT_PCT = 25.0  # Stop trading at -25% drawdown
DRAWDOWN_WARNING_LEVEL_1 = 10.0  # First warning at -10%
DRAWDOWN_WARNING_LEVEL_2 = 15.0  # Second warning at -15%


def calculate_drawdown_metrics(
    storage: PortfolioStorage,
    account_id: str,
) -> DrawdownMetrics:
    """Calculate comprehensive drawdown metrics for a portfolio.

    Args:
        storage: Database storage
        account_id: Portfolio account ID

    Returns:
        DrawdownMetrics with current status
    """
    current_equity = get_portfolio_equity(storage, account_id)
    peak_equity, peak_date = get_peak_equity(storage, account_id)

    # Ensure peak is at least current (no negative drawdown from initial state)
    if current_equity > peak_equity:
        peak_equity = current_equity
        peak_date = date.today()

    current_drawdown = calculate_drawdown(peak_equity, current_equity)
    underwater_days = calculate_underwater_days(storage, account_id)

    # Get historical max drawdown
    max_drawdown_query = """
        SELECT COALESCE(MAX(drawdown_pct), 0) as max_dd
        FROM portfolio_snapshots
        WHERE account_id = $1
    """
    max_dd_result = storage.query(max_drawdown_query, [account_id])
    max_drawdown = float(max_dd_result.get_column("max_dd")[0] or 0)

    # Use current if higher than historical
    max_drawdown = max(max_drawdown, current_drawdown)

    # Check if trading should be halted
    is_halted = current_drawdown >= PORTFOLIO_DRAWDOWN_HALT_PCT
    halt_reason = None
    if is_halted:
        halt_reason = (
            f"Portfolio drawdown of {current_drawdown:.1f}% exceeds "
            f"{PORTFOLIO_DRAWDOWN_HALT_PCT:.0f}% limit. Trading halted."
        )

    return DrawdownMetrics(
        current_drawdown_pct=current_drawdown,
        max_drawdown_pct=max_drawdown,
        peak_equity=peak_equity,
        peak_date=peak_date,
        current_equity=current_equity,
        underwater_days=underwater_days,
        is_halted=is_halted,
        halt_reason=halt_reason,
    )


def check_portfolio_drawdown_halt(
    storage: PortfolioStorage,
    account_id: str,
) -> tuple[bool, str | None]:
    """Check if portfolio drawdown exceeds halt threshold.

    This should be called before executing any new trades.

    Args:
        storage: Database storage
        account_id: Portfolio account ID

    Returns:
        Tuple of (can_trade, halt_reason)
        can_trade is False if drawdown exceeds -10%
    """
    metrics = calculate_drawdown_metrics(storage, account_id)

    if metrics.is_halted:
        logger.warning(
            "portfolio_drawdown_halt",
            account_id=account_id,
            drawdown_pct=f"{metrics.current_drawdown_pct:.2f}",
            peak_equity=f"{metrics.peak_equity:.2f}",
            current_equity=f"{metrics.current_equity:.2f}",
        )
        return (False, metrics.halt_reason)

    # Log warnings at intermediate levels
    if metrics.current_drawdown_pct >= DRAWDOWN_WARNING_LEVEL_2:
        logger.warning(
            "portfolio_drawdown_warning_level_2",
            account_id=account_id,
            drawdown_pct=f"{metrics.current_drawdown_pct:.2f}",
        )
    elif metrics.current_drawdown_pct >= DRAWDOWN_WARNING_LEVEL_1:
        logger.info(
            "portfolio_drawdown_warning_level_1",
            account_id=account_id,
            drawdown_pct=f"{metrics.current_drawdown_pct:.2f}",
        )

    return (True, None)


# Re-export all public APIs to maintain backwards compatibility
__all__ = [
    "DRAWDOWN_WARNING_LEVEL_1",
    "DRAWDOWN_WARNING_LEVEL_2",
    "PORTFOLIO_DRAWDOWN_HALT_PCT",
    "DrawdownMetrics",
    "PositionDrawdown",
    "calculate_drawdown",
    "calculate_drawdown_metrics",
    "calculate_position_drawdown",
    "calculate_underwater_days",
    "check_portfolio_drawdown_halt",
    "get_drawdown_history",
    "get_peak_equity",
    "get_portfolio_equity",
    "get_recovery_estimate",
    "save_portfolio_snapshot",
]
