"""Read-only query operations for paper trades."""

from __future__ import annotations

from typing import Literal

from app.logging_config import get_logger
from app.models.paper_trades import (
    PaperTradeResponse,
    PaperTradesListResponse,
    PaperTradeSummaryResponse,
)
from app.storage import get_storage

from ._row_mapper import row_to_paper_trade_response

logger = get_logger(__name__)
storage = get_storage()

# SQL fragment shared by list and single-trade queries
_LIVE_PRICE_CTE = """
    WITH latest_prices AS (
        SELECT DISTINCT ON (symbol)
            symbol,
            price
        FROM price_cache
        WHERE cached_at >= NOW() - INTERVAL '1 hour'
        ORDER BY symbol, cached_at DESC
    )
"""

_LIST_TRADES_QUERY = (
    _LIVE_PRICE_CTE
    + """
    SELECT
        io.idea_id, io.agent_run_id, io.symbol, io.idea_type,
        io.shares, io.entry_price, io.entry_amount, io.entry_date,
        io.target_price, io.stop_loss_price,
        CASE WHEN io.status = 'open'
            THEN COALESCE(lp.price, io.current_price)
            ELSE io.current_price END as current_price,
        CASE WHEN io.status = 'open' AND io.entry_price > 0 THEN
            CASE WHEN io.idea_type = 'sell'
                THEN ((io.entry_price - COALESCE(lp.price, io.current_price)) / io.entry_price) * 100
                ELSE ((COALESCE(lp.price, io.current_price) - io.entry_price) / io.entry_price) * 100
            END
            ELSE io.current_return_pct END as current_return_pct,
        io.status, io.exit_price, io.exit_date, io.exit_reason,
        io.realized_return_pct,
        CASE WHEN io.status = 'open' AND io.entry_date IS NOT NULL
            THEN CURRENT_DATE - io.entry_date::date
            ELSE io.holding_days END as holding_days,
        io.max_favorable_pct, io.max_adverse_pct,
        NULL as thesis, NULL as confidence_score, NULL as risk_level,
        io.strategy_id
    FROM idea_outcomes io
    LEFT JOIN latest_prices lp ON lp.symbol = io.symbol
    {status_filter}
    ORDER BY CASE WHEN io.status = 'open' THEN 0 ELSE 1 END, io.entry_date DESC
    LIMIT ? OFFSET ?
"""
)

_SINGLE_TRADE_QUERY = (
    _LIVE_PRICE_CTE
    + """
    SELECT
        io.idea_id, io.agent_run_id, io.symbol, io.idea_type,
        io.entry_price, io.entry_date, io.target_price, io.stop_loss_price,
        CASE WHEN io.status = 'open'
            THEN COALESCE(lp.price, io.current_price)
            ELSE io.current_price END as current_price,
        CASE WHEN io.status = 'open' AND io.entry_price > 0 THEN
            CASE WHEN io.idea_type = 'sell'
                THEN ((io.entry_price - COALESCE(lp.price, io.current_price)) / io.entry_price) * 100
                ELSE ((COALESCE(lp.price, io.current_price) - io.entry_price) / io.entry_price) * 100
            END
            ELSE io.current_return_pct END as current_return_pct,
        io.status, io.exit_price, io.exit_date, io.exit_reason,
        io.realized_return_pct, io.holding_days,
        io.max_favorable_pct, io.max_adverse_pct,
        NULL as thesis, NULL as confidence_score, NULL as risk_level
    FROM idea_outcomes io
    LEFT JOIN latest_prices lp ON lp.symbol = io.symbol
    WHERE io.idea_id = ?
"""
)

_CLOSED_STATS_QUERY = """
    SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN realized_return_pct > 0 THEN 1 END) as wins,
        AVG(realized_return_pct) as avg_return,
        SUM(realized_return_pct) as total_return,
        MAX(realized_return_pct) as best_trade,
        MIN(realized_return_pct) as worst_trade
    FROM idea_outcomes
    WHERE status IN ('closed', 'target_hit', 'stop_hit', 'expired')
        AND realized_return_pct IS NOT NULL
"""

_POSITIONS_VALUE_QUERY = (
    _LIVE_PRICE_CTE
    + """
    SELECT COALESCE(SUM(
        io.shares * COALESCE(lp.price, io.current_price, io.entry_price)
    ), 0)
    FROM idea_outcomes io
    LEFT JOIN latest_prices lp ON lp.symbol = io.symbol
    WHERE io.status = 'open' AND io.shares IS NOT NULL
"""
)


def list_trades(
    status: Literal["open", "closed", "all"],
    limit: int,
    offset: int,
) -> PaperTradesListResponse:
    """Fetch paper trades with optional status filter.

    Args:
        status: Filter by 'open', 'closed', or 'all'
        limit: Maximum number of trades to return
        offset: Number of trades to skip for pagination

    Returns:
        List of paper trades with full details
    """
    status_filter = _build_status_filter(status)
    query = _LIST_TRADES_QUERY.format(status_filter=status_filter)

    with storage.connection() as conn:
        rows = conn.execute(query, (limit, offset)).fetchall()
        count_query = f"SELECT COUNT(*) FROM idea_outcomes io {status_filter}"
        total_count = conn.execute(count_query).fetchone()[0]  # type: ignore[index]

    trades = [row_to_paper_trade_response(row) for row in rows]
    logger.info("paper_trades_listed", status_filter=status, count=len(trades), total=total_count)
    return PaperTradesListResponse(
        trades=trades, total_count=int(total_count) if total_count else 0
    )


def get_trade_summary() -> PaperTradeSummaryResponse:
    """Get summary statistics for paper trading performance.

    Returns:
        Summary with win rate, average return, total P&L, etc.
    """
    with storage.connection() as conn:
        counts = _fetch_status_counts(conn)
        stats_row = conn.execute(_CLOSED_STATS_QUERY).fetchone()
        account_row = conn.execute(
            "SELECT cash_balance, initial_cash FROM portfolio_accounts WHERE id = 'paper_trading'"
        ).fetchone()
        positions_row = conn.execute(_POSITIONS_VALUE_QUERY).fetchone()

    return _build_summary_response(counts, stats_row, account_row, positions_row)


def get_single_trade(trade_id: str) -> PaperTradeResponse | None:
    """Get detailed information for a single paper trade.

    Args:
        trade_id: The idea_id of the paper trade

    Returns:
        Trade details or None if not found
    """
    with storage.connection() as conn:
        row = conn.execute(_SINGLE_TRADE_QUERY, [trade_id]).fetchone()

    if not row:
        return None

    trade = PaperTradeResponse(
        idea_id=str(row[0]) if row[0] else "",
        agent_run_id=str(row[1]) if row[1] else "",
        symbol=str(row[2]) if row[2] else "",
        idea_type=str(row[3]) if row[3] in ["buy", "sell"] else "buy",  # type: ignore[arg-type]
        entry_price=float(row[4]) if row[4] is not None else None,
        entry_date=str(row[5]) if row[5] else None,
        target_price=float(row[6]) if row[6] is not None else None,
        stop_loss_price=float(row[7]) if row[7] is not None else None,
        current_price=float(row[8]) if row[8] is not None else None,
        current_return_pct=float(row[9]) if row[9] is not None else None,
        status=str(row[10]) if row[10] else "",
        exit_price=float(row[11]) if row[11] is not None else None,
        exit_date=str(row[12]) if row[12] else None,
        exit_reason=str(row[13]) if row[13] else None,
        realized_return_pct=float(row[14]) if row[14] is not None else None,
        holding_days=int(row[15]) if row[15] is not None else None,
        max_favorable_pct=float(row[16]) if row[16] is not None else None,
        max_adverse_pct=float(row[17]) if row[17] is not None else None,
        thesis=str(row[18]) if row[18] else None,
        confidence_score=float(row[19]) if row[19] is not None else None,
        risk_level=str(row[20]) if row[20] else None,
    )

    logger.info("paper_trade_retrieved", trade_id=trade_id, symbol=trade.symbol)
    return trade


def _build_status_filter(status: Literal["open", "closed", "all"]) -> str:
    """Return SQL WHERE clause for the given status filter."""
    if status == "open":
        return "WHERE io.status = 'open'"
    if status == "closed":
        return "WHERE io.status IN ('closed', 'target_hit', 'stop_hit', 'expired')"
    return ""


def _fetch_status_counts(conn: object) -> tuple[int, int]:
    """Return (open_count, closed_count) from the DB."""
    open_count = conn.execute(  # type: ignore[union-attr]
        "SELECT COUNT(*) FROM idea_outcomes WHERE status = 'open'"
    ).fetchone()[0]
    closed_count = conn.execute(  # type: ignore[union-attr]
        "SELECT COUNT(*) FROM idea_outcomes WHERE status IN ('closed', 'target_hit', 'stop_hit', 'expired')"
    ).fetchone()[0]
    return int(open_count) if open_count else 0, int(closed_count) if closed_count else 0


def _build_summary_response(
    counts: tuple[int, int],
    stats_row: object,
    account_row: object,
    positions_row: object,
) -> PaperTradeSummaryResponse:
    """Assemble PaperTradeSummaryResponse from raw DB result rows."""
    open_count, closed_count = counts

    total_closed = int(stats_row[0]) if stats_row[0] else 0  # type: ignore[index]
    wins = int(stats_row[1]) if stats_row[1] else 0  # type: ignore[index]
    avg_return = float(stats_row[2]) if stats_row[2] else 0.0  # type: ignore[index]
    best_trade = float(stats_row[4]) if stats_row[4] is not None else None  # type: ignore[index]
    worst_trade = float(stats_row[5]) if stats_row[5] is not None else None  # type: ignore[index]
    win_rate = (float(wins) / float(total_closed) * 100.0) if total_closed > 0 else 0.0

    cash_balance = float(account_row[0]) if account_row and account_row[0] is not None else None  # type: ignore[index]
    starting_balance = float(account_row[1]) if account_row and account_row[1] is not None else None  # type: ignore[index]
    positions_value = float(positions_row[0]) if positions_row and positions_row[0] is not None else 0.0  # type: ignore[index]

    total_portfolio_value = (cash_balance or 0.0) + positions_value if cash_balance is not None else None
    actual_pnl_pct = 0.0
    if starting_balance and starting_balance > 0 and total_portfolio_value is not None:
        actual_pnl_pct = ((total_portfolio_value - starting_balance) / starting_balance) * 100

    logger.info(
        "paper_trade_summary_retrieved",
        open=open_count,
        closed=closed_count,
        win_rate=win_rate,
        cash_balance=cash_balance,
    )

    return PaperTradeSummaryResponse(
        total_open=open_count,
        total_closed=closed_count,
        win_rate=float(win_rate),
        avg_return_pct=float(avg_return),
        total_pnl_pct=actual_pnl_pct,
        best_trade_pct=float(best_trade) if best_trade is not None else None,
        worst_trade_pct=float(worst_trade) if worst_trade is not None else None,
        cash_balance=cash_balance,
        starting_balance=starting_balance,
        positions_value=positions_value,
        total_portfolio_value=total_portfolio_value,
    )
