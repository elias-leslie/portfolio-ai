"""
Database storage operations for backtest framework.

CRUD operations for:
- backtest_runs: Create, read, update, list
- backtest_trades: Create, read by run_id
- backtest_equity: Create, read by run_id

Follows existing storage patterns from watchlist/portfolio modules.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.backtest.models import BacktestEquity, BacktestRun, BacktestTrade
from app.logging_config import get_logger
from app.storage.connection import ConnectionManager

logger = get_logger(__name__)


def create_backtest_run(
    storage: ConnectionManager | Any,  # Accept PortfolioStorage or ConnectionManager
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """

    params = (
        run_id,
        strategy_name,
        symbol,
        start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date),
        end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date),
        float(initial_capital),
        "pending",
        datetime.now(UTC),
    )

    with storage.connection() as conn:
        conn.execute(query, params)
        conn.commit()

    logger.info("backtest_run_created", run_id=run_id, symbol=symbol, start_date=str(start_date), end_date=str(end_date))

    return run_id


def update_backtest_status(
    storage: ConnectionManager | Any,  # Accept PortfolioStorage or ConnectionManager
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
        SET status = %s,
            error_message = %s,
            completed_at = CASE WHEN %s IN ('completed', 'failed') THEN %s ELSE completed_at END
        WHERE id = %s
    """

    params = (status, error_message, status, datetime.now(UTC), run_id)
    with storage.connection() as conn:
        conn.execute(query, params)
        conn.commit()

    logger.debug("backtest_status_updated", run_id=run_id, status=status)


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
    # Benchmark comparison fields (Section 0.1)
    buy_hold_return: Decimal | None = None,
    excess_return: Decimal | None = None,
    beats_buy_hold: bool | None = None,
    alpha: Decimal | None = None,
    information_ratio: Decimal | None = None,
    beta: Decimal | None = None,
    benchmark_symbol: str = "SPY",
) -> None:
    """Update backtest run with final performance metrics and benchmark comparison.

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
        buy_hold_return: Buy-and-hold return for benchmark over same period
        excess_return: Strategy return minus buy-hold return
        beats_buy_hold: Whether strategy outperformed buy-and-hold
        alpha: Jensen's alpha (risk-adjusted excess return)
        information_ratio: Excess return per unit tracking error
        beta: Strategy beta vs benchmark
        benchmark_symbol: Benchmark symbol used (default SPY)
    """
    query = """
        UPDATE backtest_runs
        SET final_equity = %s,
            total_return_pct = %s,
            sharpe_ratio = %s,
            max_drawdown_pct = %s,
            win_rate = %s,
            num_trades = %s,
            profit_factor = %s,
            buy_hold_return = %s,
            excess_return = %s,
            beats_buy_hold = %s,
            alpha = %s,
            information_ratio = %s,
            beta = %s,
            benchmark_symbol = %s,
            status = %s,
            completed_at = %s
        WHERE id = %s
    """

    params = (
        float(final_equity),
        float(total_return_pct),
        float(sharpe_ratio),
        float(max_drawdown_pct),
        float(win_rate),
        num_trades,
        float(profit_factor),
        float(buy_hold_return) if buy_hold_return is not None else None,
        float(excess_return) if excess_return is not None else None,
        beats_buy_hold,
        float(alpha) if alpha is not None else None,
        float(information_ratio) if information_ratio is not None else None,
        float(beta) if beta is not None else None,
        benchmark_symbol,
        "completed",
        datetime.now(UTC),
        run_id,
    )

    with storage.connection() as conn:
        conn.execute(query, params)
        conn.commit()

    excess_str = f" | Excess: {excess_return:.2f}%" if excess_return is not None else ""
    logger.info(
        f"Backtest {run_id} complete: Return: {total_return_pct:.2f}%{excess_str} | "
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """

    params = (
        trade_id,
        trade.run_id,
        trade.symbol,
        trade.entry_date.isoformat()
        if hasattr(trade.entry_date, "isoformat")
        else str(trade.entry_date),
        float(trade.entry_price),
        trade.exit_date.isoformat()
        if trade.exit_date and hasattr(trade.exit_date, "isoformat")
        else (str(trade.exit_date) if trade.exit_date else None),
        float(trade.exit_price) if trade.exit_price is not None else None,
        trade.shares,
        float(trade.pnl) if trade.pnl is not None else None,
        float(trade.pnl_pct) if trade.pnl_pct is not None else None,
        trade.exit_reason,
        float(trade.max_favorable_pct) if trade.max_favorable_pct is not None else None,
        float(trade.max_adverse_pct) if trade.max_adverse_pct is not None else None,
        datetime.now(UTC),
    )

    with storage.connection() as conn:
        # Ensure symbol exists in symbols table (FK constraint)
        conn.execute(
            """
            INSERT INTO symbols (symbol, security_type, created_at)
            VALUES (%s, 'equity', NOW())
            ON CONFLICT (symbol) DO NOTHING
            """,
            (trade.symbol,),
        )
        conn.execute(query, params)
        conn.commit()

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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
        snapshot.date.isoformat() if hasattr(snapshot.date, "isoformat") else str(snapshot.date),
        float(snapshot.equity),
        float(snapshot.cash),
        float(snapshot.position_value),
        float(snapshot.drawdown_pct),
        datetime.now(UTC),
    )

    with storage.connection() as conn:
        conn.execute(query, params)
        conn.commit()

    return snapshot_id


def get_backtest_run(
    storage: ConnectionManager | Any, run_id: str
) -> BacktestRun | None:  # Accept PortfolioStorage
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
        WHERE id = %s
    """

    with storage.connection() as conn:
        df = conn.execute(query, (run_id,)).pl()

    if df.is_empty():
        return None

    # Convert Polars DataFrame row to dict and create model
    row_dict = df.to_dicts()[0]
    # Convert UUID objects to strings
    if "id" in row_dict and hasattr(row_dict["id"], "hex"):
        row_dict["id"] = str(row_dict["id"])
    return BacktestRun(**row_dict)


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
        WHERE run_id = %s
        ORDER BY entry_date ASC
    """

    with storage.connection() as conn:
        df = conn.execute(query, (run_id,)).pl()

    trades = []
    for row in df.to_dicts():
        # Convert UUID objects to strings
        if "id" in row and hasattr(row["id"], "hex"):
            row["id"] = str(row["id"])
        if "run_id" in row and hasattr(row["run_id"], "hex"):
            row["run_id"] = str(row["run_id"])
        trades.append(BacktestTrade(**row))
    return trades


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
        WHERE run_id = %s
        ORDER BY date ASC
    """

    with storage.connection() as conn:
        df = conn.execute(query, (run_id,)).pl()

    equities = []
    for row in df.to_dicts():
        # Convert UUID objects to strings
        if "id" in row and hasattr(row["id"], "hex"):
            row["id"] = str(row["id"])
        if "run_id" in row and hasattr(row["run_id"], "hex"):
            row["run_id"] = str(row["run_id"])
        equities.append(BacktestEquity(**row))
    return equities


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

    if symbol:
        where_clauses.append("symbol = %s")
        params.append(symbol)

    if status:
        where_clauses.append("status = %s")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    query = f"""
        SELECT *
        FROM backtest_runs
        {where_sql}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """

    params.extend([limit, offset])

    with storage.connection() as conn:
        df = conn.execute(query, tuple(params)).pl()

    runs = []
    for row in df.to_dicts():
        # Convert UUID objects to strings
        if "id" in row and hasattr(row["id"], "hex"):
            row["id"] = str(row["id"])
        runs.append(BacktestRun(**row))
    return runs


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
        WHERE id = %s
        RETURNING id
    """

    with storage.connection() as conn:
        df = conn.execute(query, (run_id,)).pl()
        conn.commit()

    if not df.is_empty():
        logger.info("backtest_run_deleted", run_id=run_id)
        return True

    return False
