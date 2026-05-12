"""Paper-trade execution + nightly P/L tracking for the Investment Committee.

Two surfaces:

- ``execute_from_run(run_id)``: called when the user approves a
  committee decision. Reads the committee_runs row, computes the
  share count from ``decision_pct_portfolio * portfolio_value /
  current_close``, persists a ``paper_trades`` row, marks the run
  ``approved``.

- ``update_pnl_for_open()``: invoked from the daily
  ``refresh_daily_ohlcv_wf`` after the OHLCV refresh. Walks every
  paper trade where ``closed_at IS NULL`` and updates
  ``current_price/current_pnl/last_pnl_at`` from the latest day_bars
  close.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)


@dataclass
class PaperTradeRow:
    id: str
    run_id: str
    household_id: str | None
    symbol: str
    action: str
    qty: float
    price: float
    executed_at: datetime


class PaperTradeError(RuntimeError):
    """Raised when a paper-trade execution cannot proceed."""


def execute_from_run(run_id: str) -> PaperTradeRow:
    """Create a paper_trades row from a committee_runs decision.

    Raises ``PaperTradeError`` if the run is not in a state that
    permits execution (must be 'complete'), if there is no actionable
    decision (hold), or if the current close is unavailable.
    """
    cm = get_connection_manager()
    with cm.connection() as conn:
        run_row = conn.execute(
            """
            SELECT symbol, household_id, status, decision_action,
                   decision_pct_portfolio
            FROM committee_runs
            WHERE id = %s
            """,
            (run_id,),
        ).fetchone()
        if run_row is None:
            raise PaperTradeError(f"committee_run {run_id} not found")
        symbol, household_id, status, action, pct_portfolio = run_row
        if status != "complete":
            raise PaperTradeError(
                f"committee_run {run_id} status='{status}', expected 'complete'"
            )
        if action in (None, "hold"):
            raise PaperTradeError(
                f"committee_run {run_id} decision is '{action}'; nothing to execute"
            )
        pct = float(pct_portfolio or 0.0)
        if pct <= 0:
            raise PaperTradeError(
                f"committee_run {run_id} qty_pct={pct}; nothing to execute"
            )

        # Current close from day_bars (most recent bar).
        price_row = conn.execute(
            """
            SELECT close FROM day_bars
            WHERE symbol = %s
            ORDER BY bar_date DESC
            LIMIT 1
            """,
            (str(symbol).upper(),),
        ).fetchone()
        if price_row is None or price_row[0] is None:
            raise PaperTradeError(
                f"no day_bars close available for {symbol}; cannot fill paper trade"
            )
        current_price = float(price_row[0])

        # Portfolio value: same source the trader saw — sum of
        # (shares * cost_basis). Single-household scoping handled
        # downstream when we go multi-household.
        portfolio_row = conn.execute(
            """
            SELECT COALESCE(SUM(shares * COALESCE(cost_basis, 0)), 0)
            FROM portfolio_positions
            """,
        ).fetchone()
        portfolio_value = float(portfolio_row[0]) if portfolio_row and portfolio_row[0] else 0.0
        if portfolio_value <= 0:
            raise PaperTradeError(
                "portfolio_value is zero; cannot size paper trade"
            )

        target_value = portfolio_value * pct
        qty = round(target_value / current_price)
        if qty <= 0:
            raise PaperTradeError(
                f"computed qty={qty} for {symbol} at {current_price}; nothing to execute"
            )

        paper_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO paper_trades
                (id, run_id, household_id, symbol, action, qty, price)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (paper_id, run_id, household_id, str(symbol).upper(), action, qty, current_price),
        )
        conn.execute(
            """
            UPDATE committee_runs
            SET status='approved',
                approved_at=now(),
                decision_qty=%s,
                decision_price=%s
            WHERE id=%s
            """,
            (qty, current_price, run_id),
        )
        conn.commit()

    return PaperTradeRow(
        id=paper_id,
        run_id=run_id,
        household_id=household_id,
        symbol=str(symbol).upper(),
        action=str(action),
        qty=float(qty),
        price=current_price,
        executed_at=datetime.now(tz=UTC),
    )


def update_pnl_for_open() -> dict[str, Any]:
    """For every open paper trade, recompute current_pnl from latest close.

    "Open" = ``closed_at IS NULL``. Per fold-in #5 from the subtask-1
    audit. Updates ``current_price``, ``current_pnl``, ``last_pnl_at``.

    Returns a summary dict suitable for embedding in the nightly
    workflow's result payload.
    """
    cm = get_connection_manager()
    with cm.connection() as conn:
        open_rows = conn.execute(
            """
            SELECT id, symbol, action, qty, price
            FROM paper_trades
            WHERE closed_at IS NULL
            """,
        ).fetchall()

        updated = 0
        skipped_no_price: list[str] = []
        for row in open_rows:
            paper_id, symbol, action, qty, entry_price = row
            close_row = conn.execute(
                """
                SELECT close FROM day_bars
                WHERE symbol = %s
                ORDER BY bar_date DESC
                LIMIT 1
                """,
                (str(symbol).upper(),),
            ).fetchone()
            if close_row is None or close_row[0] is None:
                skipped_no_price.append(str(symbol))
                continue
            current_price = float(close_row[0])
            sign = -1.0 if str(action) in {"sell", "trim"} else 1.0
            pnl = sign * (current_price - float(entry_price)) * float(qty)
            conn.execute(
                """
                UPDATE paper_trades
                SET current_price=%s,
                    current_pnl=%s,
                    last_pnl_at=now()
                WHERE id=%s
                """,
                (current_price, pnl, paper_id),
            )
            updated += 1
        conn.commit()

    summary = {
        "open_count": len(open_rows),
        "updated": updated,
        "skipped_no_price": skipped_no_price,
    }
    logger.info("committee_paper_trade_pnl_updated", **summary)
    return summary
