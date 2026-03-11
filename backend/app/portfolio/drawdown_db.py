"""Database query functions for drawdown tracking.

This module contains all database-dependent functions for retrieving
equity, peak values, and underwater days calculations.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from ..logging_config import get_logger
from .drawdown_calc import calculate_drawdown

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)


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
    query = """
        SELECT snapshot_date, equity, drawdown_pct, peak_equity
        FROM portfolio_snapshots
        WHERE account_id = $1
          AND snapshot_date >= CURRENT_DATE - make_interval(days => $2)
        ORDER BY snapshot_date ASC
    """

    result = storage.query(query, [account_id, days])

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


def save_portfolio_snapshot(
    storage: PortfolioStorage,
    account_id: str,
    snapshot_date: date | None = None,
    current_equity: float | None = None,
    peak_equity: float | None = None,
    drawdown_pct: float | None = None,
) -> None:
    """Save daily portfolio equity snapshot with drawdown.

    Should be called daily (market close) to track equity curve.

    Args:
        storage: Database storage
        account_id: Portfolio account ID
        snapshot_date: Date for snapshot (default: today)
        current_equity: Precalculated current equity (optional)
        peak_equity: Precalculated peak equity (optional)
        drawdown_pct: Precalculated drawdown (optional)
    """
    if snapshot_date is None:
        snapshot_date = date.today()

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

    # Use precalculated values if provided
    if current_equity is None:
        current_equity = get_portfolio_equity(storage, account_id)

    position_value = current_equity - cash

    if peak_equity is None or drawdown_pct is None:
        peak_equity_calc, _ = get_peak_equity(storage, account_id)
        peak_equity = max(peak_equity_calc, current_equity)
        drawdown_pct = calculate_drawdown(peak_equity, current_equity)

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
