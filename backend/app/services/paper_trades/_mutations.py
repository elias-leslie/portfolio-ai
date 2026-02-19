"""Write/mutation operations for paper trades (close, reset, settings)."""

from __future__ import annotations

from datetime import date

from app.analytics.cash_manager import CashManager
from app.logging_config import get_logger
from app.models.paper_trades import (
    CloseTradeResponse,
    ResetAccountResponse,
    UpdateSettingsResponse,
)
from app.storage import get_storage

logger = get_logger(__name__)
storage = get_storage()


def close_trade(
    trade_id: str,
    exit_price: float | None,
    exit_reason: str,
) -> CloseTradeResponse:
    """Manually close an open paper trade.

    Args:
        trade_id: The idea_id of the paper trade to close
        exit_price: Optional exit price (uses current_price if not provided)
        exit_reason: Reason for closing

    Returns:
        Result of close operation with realized P&L

    Raises:
        ValueError: If trade not found, already closed, or missing price data
    """
    with storage.connection() as conn:
        trade_row = conn.execute(
            """
            WITH latest_prices AS (
                SELECT DISTINCT ON (symbol)
                    symbol,
                    price
                FROM price_cache
                WHERE cached_at >= NOW() - INTERVAL '1 hour'
                ORDER BY symbol, cached_at DESC
            )
            SELECT
                io.symbol,
                io.entry_price,
                COALESCE(lp.price, io.current_price) as current_price,
                io.status,
                io.shares
            FROM idea_outcomes io
            LEFT JOIN latest_prices lp ON lp.symbol = io.symbol
            WHERE io.idea_id = ?
            """,
            [trade_id],
        ).fetchone()

        if not trade_row:
            raise ValueError(f"Paper trade {trade_id} not found")

        symbol, entry_price, current_price, status, shares = trade_row

        if status != "open":
            raise ValueError(f"Trade is already {status}, cannot close")

        final_exit_price = exit_price if exit_price is not None else current_price

        if final_exit_price is None or entry_price is None:
            raise ValueError("Cannot close trade: missing price data")

        realized_return_pct = (
            (float(final_exit_price) - float(entry_price)) / float(entry_price)
        ) * 100

        exit_date = date.today().isoformat()
        conn.execute(
            """
            UPDATE idea_outcomes
            SET
                status = 'closed',
                exit_price = ?,
                exit_date = ?,
                exit_reason = ?,
                realized_return_pct = ?
            WHERE idea_id = ?
            """,
            [final_exit_price, exit_date, exit_reason, realized_return_pct, trade_id],
        )
        conn.commit()

    if shares is not None and (isinstance(shares, (int, float)) and shares > 0):
        exit_amount = float(shares) * float(final_exit_price)
        cash_manager = CashManager(storage)
        cash_manager.add_cash(
            "paper_trading",
            exit_amount,
            f"Sell {shares} {symbol} @ ${final_exit_price:.2f}",
        )

    logger.info(
        "paper_trade_closed",
        trade_id=trade_id,
        symbol=symbol,
        exit_price=final_exit_price,
        realized_return_pct=realized_return_pct,
    )

    return CloseTradeResponse(
        status="closed",
        trade_id=trade_id,
        symbol=str(symbol),
        exit_price=float(final_exit_price),
        exit_date=str(exit_date),
        realized_return_pct=float(realized_return_pct),
        message=f"Successfully closed {symbol} trade with {realized_return_pct:+.2f}% return",
    )


def reset_account(
    new_starting_balance: float | None,
    close_open_trades: bool,
) -> ResetAccountResponse:
    """Reset the paper trading account to starting balance.

    Args:
        new_starting_balance: Optional new starting balance
        close_open_trades: Whether to close open trades

    Returns:
        Result of reset operation

    Raises:
        ValueError: If account not found or data corrupted
    """
    with storage.connection() as conn:
        account_row = conn.execute(
            "SELECT cash_balance, initial_cash FROM portfolio_accounts WHERE id = 'paper_trading'"
        ).fetchone()

        if not account_row:
            raise ValueError("Paper trading account not found")

        if account_row[0] is None or account_row[1] is None:
            raise ValueError("Account balance data is corrupted (NULL values)")

        previous_balance = float(account_row[0])
        current_initial = float(account_row[1])
        trades_closed = _close_open_trades_if_requested(conn, close_open_trades)

        new_balance = new_starting_balance or current_initial

        conn.execute(
            """
            UPDATE portfolio_accounts
            SET
                cash_balance = ?,
                initial_cash = ?,
                updated_at = NOW()
            WHERE id = 'paper_trading'
            """,
            [new_balance, new_balance],
        )
        conn.commit()

    logger.info(
        "paper_account_reset",
        previous_balance=previous_balance,
        new_balance=new_balance,
        trades_closed=trades_closed,
    )

    return ResetAccountResponse(
        status="reset",
        previous_balance=previous_balance,
        new_balance=new_balance,
        trades_closed=trades_closed,
        message=f"Account reset to ${new_balance:,.2f}. {trades_closed} trades closed.",
    )


def update_settings(starting_balance: float) -> UpdateSettingsResponse:
    """Update paper trading account settings.

    Args:
        starting_balance: New starting balance amount

    Returns:
        Updated settings

    Raises:
        ValueError: If account not found or data corrupted
    """
    with storage.connection() as conn:
        account_row = conn.execute(
            "SELECT cash_balance FROM portfolio_accounts WHERE id = 'paper_trading'"
        ).fetchone()

        if not account_row:
            raise ValueError("Paper trading account not found")

        if account_row[0] is None:
            raise ValueError("Account balance data is corrupted (NULL value)")

        current_cash = float(account_row[0])

        conn.execute(
            """
            UPDATE portfolio_accounts
            SET
                initial_cash = ?,
                updated_at = NOW()
            WHERE id = 'paper_trading'
            """,
            [starting_balance],
        )
        conn.commit()

    logger.info("paper_settings_updated", starting_balance=starting_balance)

    return UpdateSettingsResponse(
        status="updated",
        starting_balance=starting_balance,
        cash_balance=current_cash,
        message=f"Starting balance updated to ${starting_balance:,.2f}",
    )


def _close_open_trades_if_requested(conn: object, close_open_trades: bool) -> int:
    """Close all open trades if requested, returning count closed.

    Args:
        conn: Database connection
        close_open_trades: Whether to perform the close

    Returns:
        Number of trades closed
    """
    if not close_open_trades:
        return 0

    count_row = conn.execute(  # type: ignore[union-attr]
        "SELECT COUNT(*) FROM idea_outcomes WHERE status = 'open'"
    ).fetchone()
    trades_closed = int(count_row[0]) if count_row and count_row[0] is not None else 0

    if trades_closed == 0:
        return 0

    exit_date = date.today().isoformat()
    conn.execute(  # type: ignore[union-attr]
        """
        UPDATE idea_outcomes
        SET
            status = 'closed',
            exit_price = COALESCE(current_price, entry_price),
            exit_date = ?,
            exit_reason = 'account_reset',
            realized_return_pct = CASE
                WHEN entry_price > 0 THEN
                    ((COALESCE(current_price, entry_price) - entry_price) / entry_price) * 100
                ELSE 0
            END
        WHERE status = 'open'
        """,
        [exit_date],
    )
    return trades_closed
