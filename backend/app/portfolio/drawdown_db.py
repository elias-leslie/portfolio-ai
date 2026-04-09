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
    cash_query = """
        SELECT cash_balance FROM portfolio_accounts
        WHERE id = $1
    """
    cash_result = storage.query(cash_query, [account_id])
    if cash_result.is_empty():
        return 0.0
    cash = float(cash_result.get_column("cash_balance")[0] or 0)

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


def _parse_date_value(value: date | datetime | str | None) -> date | None:
    """Parse a date value from various types returned by database queries.

    Args:
        value: Raw date value from DB (date, datetime, str, or None)

    Returns:
        Parsed date or None if value is None or unrecognized
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    if isinstance(value, date):
        return value
    return None


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
        current_equity = get_portfolio_equity(storage, account_id)
        return (current_equity, date.today())

    peak_equity = float(result.get_column("equity")[0] or 0)
    peak_date = _parse_date_value(result.get_column("snapshot_date")[0])

    return (peak_equity, peak_date)


def _get_first_snapshot_days(
    storage: PortfolioStorage,
    account_id: str,
    current_date: date,
) -> int:
    """Calculate days since first snapshot when no peak is found.

    Args:
        storage: Database storage
        account_id: Portfolio account ID
        current_date: Date to calculate from

    Returns:
        Days since first snapshot, or 0 if no snapshots exist
    """
    first_query = """
        SELECT MIN(snapshot_date) as first_date
        FROM portfolio_snapshots
        WHERE account_id = $1
    """
    first_result = storage.query(first_query, [account_id])
    if first_result.is_empty():
        return 0

    first_date = _parse_date_value(first_result.get_column("first_date")[0])
    if first_date is None:
        return 0

    return (current_date - first_date).days


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

    query = """
        SELECT snapshot_date FROM portfolio_snapshots
        WHERE account_id = $1 AND drawdown_pct <= 0.01
        ORDER BY snapshot_date DESC
        LIMIT 1
    """
    result = storage.query(query, [account_id])

    if result.is_empty():
        return _get_first_snapshot_days(storage, account_id, current_date)

    peak_date = _parse_date_value(result.get_column("snapshot_date")[0])
    if peak_date is None:
        return 0

    return max(0, (current_date - peak_date).days)


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
    with storage.connection() as conn:
        rows = conn.execute(query, [account_id, days]).fetchall()

    if not rows:
        return []

    return [
        _format_history_row(
            {
                "snapshot_date": snapshot_date,
                "equity": equity,
                "drawdown_pct": drawdown_pct,
                "peak_equity": peak_equity,
            }
        )
        for snapshot_date, equity, drawdown_pct, peak_equity in rows
    ]


def _format_history_row(row: dict[str, object]) -> dict[str, float | str]:
    """Format a single snapshot row for history output.

    Args:
        row: Named row from portfolio_snapshots query

    Returns:
        Dict with date string, equity, drawdown_pct, peak_equity
    """
    snapshot_date_val = row["snapshot_date"]
    if isinstance(snapshot_date_val, datetime):
        snapshot_date_str = str(snapshot_date_val.date())
    else:
        snapshot_date_str = str(snapshot_date_val)

    return {
        "date": snapshot_date_str,
        "equity": float(row["equity"]),
        "drawdown_pct": float(row["drawdown_pct"]),
        "peak_equity": float(row["peak_equity"]),
    }


def _get_snapshot_cash(
    storage: PortfolioStorage,
    account_id: str,
) -> float | None:
    """Fetch cash balance for snapshot, validating account exists.

    Args:
        storage: Database storage
        account_id: Portfolio account ID

    Returns:
        Cash balance or None if account not found
    """
    cash_query = """
        SELECT COALESCE(cash_balance, 0) as cash FROM portfolio_accounts
        WHERE id = $1
    """
    cash_result = storage.query(cash_query, [account_id])
    if cash_result.is_empty():
        return None
    return float(cash_result.get_column("cash")[0] or 0)


def _resolve_snapshot_values(
    storage: PortfolioStorage,
    account_id: str,
    current_equity: float | None,
    peak_equity: float | None,
    drawdown_pct: float | None,
) -> tuple[float, float, float]:
    """Resolve snapshot values, computing any that are not provided.

    Args:
        storage: Database storage
        account_id: Portfolio account ID
        current_equity: Precalculated current equity (optional)
        peak_equity: Precalculated peak equity (optional)
        drawdown_pct: Precalculated drawdown (optional)

    Returns:
        Tuple of (current_equity, peak_equity, drawdown_pct)
    """
    if current_equity is None:
        current_equity = get_portfolio_equity(storage, account_id)

    if peak_equity is None or drawdown_pct is None:
        peak_equity_calc, _ = get_peak_equity(storage, account_id)
        peak_equity = max(peak_equity_calc, current_equity)
        drawdown_pct = calculate_drawdown(peak_equity, current_equity)

    return (current_equity, peak_equity, drawdown_pct)


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
    All equity/drawdown values are optional and computed if omitted.
    """
    if snapshot_date is None:
        snapshot_date = date.today()

    cash = _get_snapshot_cash(storage, account_id)
    if cash is None:
        logger.warning("portfolio_snapshot_skipped_no_account", account_id=account_id)
        return

    current_equity, peak_equity, drawdown_pct = _resolve_snapshot_values(
        storage, account_id, current_equity, peak_equity, drawdown_pct
    )
    position_value = current_equity - cash

    _upsert_snapshot(
        storage,
        account_id,
        snapshot_date,
        current_equity,
        cash,
        position_value,
        peak_equity,
        drawdown_pct,
    )

    logger.info(
        "portfolio_snapshot_saved",
        account_id=account_id,
        date=str(snapshot_date),
        equity=f"{current_equity:.2f}",
        drawdown_pct=f"{drawdown_pct:.2f}",
    )


def _upsert_snapshot(
    storage: PortfolioStorage,
    account_id: str,
    snapshot_date: date,
    current_equity: float,
    cash: float,
    position_value: float,
    peak_equity: float,
    drawdown_pct: float,
) -> None:
    """Execute the upsert SQL for a portfolio snapshot.

    Args:
        storage: Database storage
        account_id: Portfolio account ID
        snapshot_date: Date of snapshot
        current_equity: Total equity value
        cash: Cash balance
        position_value: Value of positions
        peak_equity: Peak equity for drawdown calculation
        drawdown_pct: Drawdown percentage
    """
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
