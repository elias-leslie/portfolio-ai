"""
Database storage operations for backtest framework.

CRUD operations for:
- backtest_runs: Create, read, update, list
- backtest_trades: Create, read by run_id
- backtest_equity: Create, read by run_id

Follows existing storage patterns from watchlist/portfolio modules.
"""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal

from app.backtest.models import BacktestEquity, BacktestRun, BacktestTrade
from app.storage.connection import ConnectionManager

logger = logging.getLogger(__name__)


def create_backtest_run(
    storage: ConnectionManager,
    strategy_name: str,
    symbol: str,
    start_date: date,
    end_date: date,
    initial_capital: Decimal,
) -> str:
    """Create new backtest run record.

    Args:
        storage: Database connection manager
        strategy_name: Strategy identifier (e.g., "signal_classifier")
        symbol: Stock symbol
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Starting capital

    Returns:
        Backtest run ID (UUID string)
    """
    run_id = str(uuid.uuid4())

    query = """
        INSERT INTO backtest_runs (
            id, strategy_name, symbol, start_date, end_date,
            initial_capital, status, created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
    """

    params = (
        run_id,
        strategy_name,
        symbol,
        start_date,
        end_date,
        initial_capital,
        "pending",
        datetime.now(),
    )

    storage.execute_write_query(query, params)  # type: ignore[attr-defined]

    logger.info(f"Created backtest run: {run_id} | {symbol} | {start_date} to {end_date}")

    return run_id


def update_backtest_status(
    storage: ConnectionManager,
    run_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update backtest run status.

    Args:
        storage: Database connection manager
        run_id: Backtest run ID
        status: New status ("pending", "running", "completed", "failed")
        error_message: Error message if status is "failed"
    """
    query = """
        UPDATE backtest_runs
        SET status = $1,
            error_message = $2,
            completed_at = CASE WHEN $1 IN ('completed', 'failed') THEN $3 ELSE completed_at END
        WHERE id = $4
    """

    params = (status, error_message, datetime.now(), run_id)
    storage.execute_write_query(query, params)  # type: ignore[attr-defined]

    logger.debug(f"Updated backtest {run_id} status: {status}")


def update_backtest_result(
    storage: ConnectionManager,
    run_id: str,
    final_equity: Decimal,
    total_return_pct: Decimal,
    sharpe_ratio: Decimal,
    max_drawdown_pct: Decimal,
    win_rate: Decimal,
    num_trades: int,
    profit_factor: Decimal,
) -> None:
    """Update backtest run with final performance metrics.

    Args:
        storage: Database connection manager
        run_id: Backtest run ID
        final_equity: Final portfolio value
        total_return_pct: Total return percentage
        sharpe_ratio: Annualized Sharpe ratio
        max_drawdown_pct: Maximum drawdown percentage
        win_rate: Win rate percentage
        num_trades: Total number of trades
        profit_factor: Profit factor (wins/losses)
    """
    query = """
        UPDATE backtest_runs
        SET final_equity = $1,
            total_return_pct = $2,
            sharpe_ratio = $3,
            max_drawdown_pct = $4,
            win_rate = $5,
            num_trades = $6,
            profit_factor = $7,
            status = $8,
            completed_at = $9
        WHERE id = $10
    """

    params = (
        final_equity,
        total_return_pct,
        sharpe_ratio,
        max_drawdown_pct,
        win_rate,
        num_trades,
        profit_factor,
        "completed",
        datetime.now(),
        run_id,
    )

    storage.execute_write_query(query, params)  # type: ignore[attr-defined]

    logger.info(
        f"Backtest {run_id} complete: Return: {total_return_pct:.2f}% | "
        f"Sharpe: {sharpe_ratio:.2f} | Trades: {num_trades}"
    )


def save_backtest_trade(
    storage: ConnectionManager,
    trade: BacktestTrade,
) -> str:
    """Save backtest trade record.

    Args:
        storage: Database connection manager
        trade: BacktestTrade model

    Returns:
        Trade ID (UUID string)
    """
    trade_id = str(uuid.uuid4())

    query = """
        INSERT INTO backtest_trades (
            id, run_id, symbol, entry_date, entry_price,
            exit_date, exit_price, shares, pnl, pnl_pct,
            exit_reason, max_favorable_pct, max_adverse_pct, created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        RETURNING id
    """

    params = (
        trade_id,
        trade.run_id,
        trade.symbol,
        trade.entry_date,
        trade.entry_price,
        trade.exit_date,
        trade.exit_price,
        trade.shares,
        trade.pnl,
        trade.pnl_pct,
        trade.exit_reason,
        trade.max_favorable_pct,
        trade.max_adverse_pct,
        datetime.now(),
    )

    storage.execute_write_query(query, params)  # type: ignore[attr-defined]

    return trade_id


def save_equity_snapshot(
    storage: ConnectionManager,
    snapshot: BacktestEquity,
) -> str:
    """Save daily equity curve snapshot.

    Args:
        storage: Database connection manager
        snapshot: BacktestEquity model

    Returns:
        Snapshot ID (UUID string)
    """
    snapshot_id = str(uuid.uuid4())

    query = """
        INSERT INTO backtest_equity (
            id, run_id, date, equity, cash, position_value, drawdown_pct, created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (run_id, date) DO UPDATE SET
            equity = EXCLUDED.equity,
            cash = EXCLUDED.cash,
            position_value = EXCLUDED.position_value,
            drawdown_pct = EXCLUDED.drawdown_pct
        RETURNING id
    """

    params = (
        snapshot_id,
        snapshot.run_id,
        snapshot.date,
        snapshot.equity,
        snapshot.cash,
        snapshot.position_value,
        snapshot.drawdown_pct,
        datetime.now(),
    )

    storage.execute_write_query(query, params)  # type: ignore[attr-defined]

    return snapshot_id


def get_backtest_run(storage: ConnectionManager, run_id: str) -> BacktestRun | None:
    """Fetch backtest run by ID.

    Args:
        storage: Database connection manager
        run_id: Backtest run ID

    Returns:
        BacktestRun model or None if not found
    """
    query = """
        SELECT *
        FROM backtest_runs
        WHERE id = $1
    """

    result = storage.execute_read_query(query, (run_id,))  # type: ignore[attr-defined]

    if not result:
        return None

    row = result[0]
    return BacktestRun(**row)


def get_backtest_trades(storage: ConnectionManager, run_id: str) -> list[BacktestTrade]:
    """Fetch all trades for backtest run.

    Args:
        storage: Database connection manager
        run_id: Backtest run ID

    Returns:
        List of BacktestTrade models (ordered by entry date)
    """
    query = """
        SELECT *
        FROM backtest_trades
        WHERE run_id = $1
        ORDER BY entry_date ASC
    """

    result = storage.execute_read_query(query, (run_id,))  # type: ignore[attr-defined]

    return [BacktestTrade(**row) for row in result]


def get_backtest_equity_curve(storage: ConnectionManager, run_id: str) -> list[BacktestEquity]:
    """Fetch equity curve for backtest run.

    Args:
        storage: Database connection manager
        run_id: Backtest run ID

    Returns:
        List of BacktestEquity models (ordered by date)
    """
    query = """
        SELECT *
        FROM backtest_equity
        WHERE run_id = $1
        ORDER BY date ASC
    """

    result = storage.execute_read_query(query, (run_id,))  # type: ignore[attr-defined]

    return [BacktestEquity(**row) for row in result]


def list_backtest_runs(
    storage: ConnectionManager,
    limit: int = 50,
    offset: int = 0,
    symbol: str | None = None,
    status: str | None = None,
) -> list[BacktestRun]:
    """List backtest runs with optional filtering.

    Args:
        storage: Database connection manager
        limit: Maximum number of runs to return
        offset: Pagination offset
        symbol: Filter by symbol (optional)
        status: Filter by status (optional)

    Returns:
        List of BacktestRun models (ordered by created_at DESC)
    """
    where_clauses = []
    params: list[str | int] = []
    param_idx = 1

    if symbol:
        where_clauses.append(f"symbol = ${param_idx}")
        params.append(symbol)
        param_idx += 1

    if status:
        where_clauses.append(f"status = ${param_idx}")
        params.append(status)
        param_idx += 1

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = f"""
        SELECT *
        FROM backtest_runs
        {where_sql}
        ORDER BY created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
    """

    params.extend([limit, offset])

    result = storage.execute_read_query(query, tuple(params))  # type: ignore[attr-defined]

    return [BacktestRun(**row) for row in result]


def delete_backtest_run(storage: ConnectionManager, run_id: str) -> bool:
    """Delete backtest run and all associated trades/equity snapshots.

    Args:
        storage: Database connection manager
        run_id: Backtest run ID

    Returns:
        True if deleted, False if run not found
    """
    # Cascade delete handles trades and equity snapshots automatically
    query = """
        DELETE FROM backtest_runs
        WHERE id = $1
        RETURNING id
    """

    result = storage.execute_write_query(query, (run_id,))  # type: ignore[attr-defined]

    if result and len(result) > 0:
        logger.info(f"Deleted backtest run: {run_id}")
        return True

    return False
