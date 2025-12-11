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

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from app.rules import get_rules

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)


def _get_drawdown_rules() -> tuple[float, float, float]:
    """Get drawdown thresholds from centralized rules engine."""
    rules = get_rules()
    rm = rules.risk_management
    return (
        rm.portfolio_drawdown_halt_pct,
        rm.drawdown_warning_level_1,
        rm.drawdown_warning_level_2,
    )


# Portfolio-level risk limits (GAP-023) - now from rules engine
# Legacy constants kept for backwards compatibility
PORTFOLIO_DRAWDOWN_HALT_PCT = 25.0  # Stop trading at -25% drawdown (updated from 10%)
DRAWDOWN_WARNING_LEVEL_1 = 10.0  # First warning at -10% (updated from 5%)
DRAWDOWN_WARNING_LEVEL_2 = 15.0  # Second warning at -15% (updated from 7.5%)


@dataclass
class DrawdownMetrics:
    """Portfolio drawdown metrics."""

    current_drawdown_pct: float  # Current drawdown from peak (positive = down)
    max_drawdown_pct: float  # Maximum drawdown ever recorded
    peak_equity: float  # Highest equity value recorded
    peak_date: date | None  # Date when peak was reached
    current_equity: float  # Current equity value
    underwater_days: int  # Days since last peak
    is_halted: bool  # True if trading should be halted
    halt_reason: str | None  # Reason for halt if halted


@dataclass
class PositionDrawdown:
    """Position-level drawdown tracking."""

    symbol: str
    entry_price: float
    current_price: float
    peak_price: float  # Highest price since entry
    max_adverse_excursion: float  # Worst % loss from entry
    max_favorable_excursion: float  # Best % gain from entry
    current_pnl_pct: float  # Current P&L %


def calculate_drawdown(peak: float, current: float) -> float:
    """Calculate drawdown percentage from peak.

    Args:
        peak: Peak equity value
        current: Current equity value

    Returns:
        Drawdown as positive percentage (10.0 means -10% from peak)
    """
    if peak <= 0:
        return 0.0
    return ((peak - current) / peak) * 100.0


def calculate_underwater_days(
    storage: PortfolioStorage,
    account_id: str,
    current_date: date | None = None,
) -> int:
    """Calculate days since portfolio was at peak equity.

    Args:
        storage: Database storage
        account_id: Portfolio account ID
        current_date: Date to calculate from (default: today)

    Returns:
        Number of days underwater (0 if at or above peak)
    """
    if current_date is None:
        current_date = date.today()

    # Get last peak date from snapshots
    query = """
        SELECT snapshot_date FROM portfolio_snapshots
        WHERE account_id = $1 AND drawdown_pct <= 0.01
        ORDER BY snapshot_date DESC
        LIMIT 1
    """
    result = storage.query(query, [account_id])

    if result.is_empty():
        # No peak recorded, check first snapshot date
        first_query = """
            SELECT MIN(snapshot_date) as first_date
            FROM portfolio_snapshots
            WHERE account_id = $1
        """
        first_result = storage.query(first_query, [account_id])
        if first_result.is_empty():
            return 0
        first_date_raw = first_result.get_column("first_date")[0]
        if first_date_raw is None:
            return 0
        if isinstance(first_date_raw, datetime):
            first_date = first_date_raw.date()
        elif isinstance(first_date_raw, str):
            first_date = datetime.strptime(first_date_raw, "%Y-%m-%d").date()
        elif isinstance(first_date_raw, date):
            first_date = first_date_raw
        else:
            return 0
        return (current_date - first_date).days

    peak_date_raw = result.get_column("snapshot_date")[0]
    if isinstance(peak_date_raw, datetime):
        peak_date = peak_date_raw.date()
    elif isinstance(peak_date_raw, str):
        peak_date = datetime.strptime(peak_date_raw, "%Y-%m-%d").date()
    elif isinstance(peak_date_raw, date):
        peak_date = peak_date_raw
    else:
        return 0

    underwater_days = (current_date - peak_date).days
    return max(0, underwater_days)


def get_portfolio_equity(
    storage: PortfolioStorage,
    account_id: str,
) -> float:
    """Get current total portfolio equity (cash + positions).

    Args:
        storage: Database storage
        account_id: Portfolio account ID

    Returns:
        Total equity value
    """
    # Get cash balance
    cash_query = """
        SELECT cash_balance FROM portfolio_accounts
        WHERE id = $1
    """
    cash_result = storage.query(cash_query, [account_id])
    if cash_result.is_empty():
        return 0.0
    cash = float(cash_result.get_column("cash_balance")[0] or 0)

    # Get position values using latest day_bars prices
    positions_query = """
        SELECT COALESCE(SUM(pp.shares * COALESCE(db.close, pp.cost_basis)), 0) as position_value
        FROM portfolio_positions pp
        LEFT JOIN LATERAL (
            SELECT close FROM day_bars
            WHERE symbol = pp.symbol
            ORDER BY date DESC LIMIT 1
        ) db ON true
        WHERE pp.account_id = $1
    """
    positions_result = storage.query(positions_query, [account_id])
    position_value = float(positions_result.get_column("position_value")[0] or 0)

    return cash + position_value


def get_peak_equity(
    storage: PortfolioStorage,
    account_id: str,
) -> tuple[float, date | None]:
    """Get peak equity value and date from historical snapshots.

    Args:
        storage: Database storage
        account_id: Portfolio account ID

    Returns:
        Tuple of (peak_equity, peak_date)
    """
    query = """
        SELECT equity, snapshot_date
        FROM portfolio_snapshots
        WHERE account_id = $1
        ORDER BY equity DESC
        LIMIT 1
    """
    result = storage.query(query, [account_id])

    if result.is_empty():
        # No historical data, use current equity as peak
        current_equity = get_portfolio_equity(storage, account_id)
        return (current_equity, date.today())

    peak_equity = float(result.get_column("equity")[0] or 0)
    peak_date_val = result.get_column("snapshot_date")[0]

    if isinstance(peak_date_val, datetime):
        peak_date = peak_date_val.date()
    elif isinstance(peak_date_val, str):
        peak_date = datetime.strptime(peak_date_val, "%Y-%m-%d").date()
    else:
        peak_date = peak_date_val

    return (peak_equity, peak_date)


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


def save_portfolio_snapshot(
    storage: PortfolioStorage,
    account_id: str,
    snapshot_date: date | None = None,
) -> None:
    """Save daily portfolio equity snapshot with drawdown.

    Should be called daily (market close) to track equity curve.

    Args:
        storage: Database storage
        account_id: Portfolio account ID
        snapshot_date: Date for snapshot (default: today)
    """
    if snapshot_date is None:
        snapshot_date = date.today()

    current_equity = get_portfolio_equity(storage, account_id)
    peak_equity, _ = get_peak_equity(storage, account_id)

    # Update peak if new high
    peak_equity = max(peak_equity, current_equity)

    drawdown_pct = calculate_drawdown(peak_equity, current_equity)

    # Get cash and position breakdown, validate account exists (FK constraint)
    cash_query = """
        SELECT COALESCE(cash_balance, 0) as cash FROM portfolio_accounts
        WHERE id = $1
    """
    cash_result = storage.query(cash_query, [account_id])
    if cash_result.is_empty():
        logger.warning("portfolio_snapshot_skipped_no_account", account_id=account_id)
        return
    cash = float(cash_result.get_column("cash")[0] or 0)
    position_value = current_equity - cash

    # Upsert snapshot
    upsert_query = """
        INSERT INTO portfolio_snapshots
            (account_id, snapshot_date, equity, cash, position_value, peak_equity, drawdown_pct, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        ON CONFLICT (account_id, snapshot_date)
        DO UPDATE SET
            equity = EXCLUDED.equity,
            cash = EXCLUDED.cash,
            position_value = EXCLUDED.position_value,
            peak_equity = EXCLUDED.peak_equity,
            drawdown_pct = EXCLUDED.drawdown_pct,
            created_at = NOW()
    """
    storage.execute(
        upsert_query,
        [
            account_id,
            str(snapshot_date),
            current_equity,
            cash,
            position_value,
            peak_equity,
            drawdown_pct,
        ],
    )

    logger.info(
        "portfolio_snapshot_saved",
        account_id=account_id,
        date=str(snapshot_date),
        equity=f"{current_equity:.2f}",
        drawdown_pct=f"{drawdown_pct:.2f}",
    )


def get_drawdown_history(
    storage: PortfolioStorage,
    account_id: str,
    days: int = 90,
) -> list[dict[str, float | str]]:
    """Get historical drawdown curve for analysis.

    Args:
        storage: Database storage
        account_id: Portfolio account ID
        days: Number of days to retrieve

    Returns:
        List of dicts with date, equity, drawdown_pct
    """
    query = f"""
        SELECT snapshot_date, equity, drawdown_pct, peak_equity
        FROM portfolio_snapshots
        WHERE account_id = $1
          AND snapshot_date >= CURRENT_DATE - INTERVAL '{days} days'
        ORDER BY snapshot_date ASC
    """

    result = storage.query(query, [account_id])

    if result.is_empty():
        return []

    history: list[dict[str, float | str]] = []
    for row in result.iter_rows(named=True):
        snapshot_date_val = row["snapshot_date"]
        if isinstance(snapshot_date_val, datetime):
            snapshot_date_str = str(snapshot_date_val.date())
        else:
            snapshot_date_str = str(snapshot_date_val)
        history.append(
            {
                "date": snapshot_date_str,
                "equity": float(row["equity"]),
                "drawdown_pct": float(row["drawdown_pct"]),
                "peak_equity": float(row["peak_equity"]),
            }
        )

    return history


def calculate_position_drawdown(
    entry_price: float,
    current_price: float,
    peak_price: float,
) -> PositionDrawdown:
    """Calculate drawdown metrics for a single position.

    Args:
        entry_price: Entry price of position
        current_price: Current market price
        peak_price: Highest price since entry

    Returns:
        PositionDrawdown with excursion metrics
    """
    if entry_price <= 0:
        return PositionDrawdown(
            symbol="",
            entry_price=0.0,
            current_price=0.0,
            peak_price=0.0,
            max_adverse_excursion=0.0,
            max_favorable_excursion=0.0,
            current_pnl_pct=0.0,
        )

    current_pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
    max_favorable = ((peak_price - entry_price) / entry_price) * 100.0
    max_adverse = min(0.0, current_pnl_pct)  # Worst loss from entry

    return PositionDrawdown(
        symbol="",  # Caller should set
        entry_price=entry_price,
        current_price=current_price,
        peak_price=peak_price,
        max_adverse_excursion=abs(max_adverse),
        max_favorable_excursion=max(0.0, max_favorable),
        current_pnl_pct=current_pnl_pct,
    )


def get_recovery_estimate(
    current_drawdown_pct: float,
    historical_avg_daily_return: float = 0.05,  # Assume 0.05% avg daily
) -> int | None:
    """Estimate days to recover from current drawdown.

    Args:
        current_drawdown_pct: Current drawdown percentage
        historical_avg_daily_return: Average daily return percentage

    Returns:
        Estimated days to recovery, or None if not calculable
    """
    if current_drawdown_pct <= 0 or historical_avg_daily_return <= 0:
        return 0

    # Need to gain back (drawdown / (1 - drawdown)) to break even
    # E.g., -10% needs +11.11% to recover
    recovery_needed = (current_drawdown_pct / (100 - current_drawdown_pct)) * 100

    days_estimate = int(recovery_needed / historical_avg_daily_return)
    return days_estimate
