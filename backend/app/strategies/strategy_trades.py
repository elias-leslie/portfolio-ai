"""Strategy trade and backtest storage operations.

This module handles storage and retrieval of strategy trades and backtests.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.utils.db_helpers import rows_to_dicts

logger = get_logger(__name__)


class TradeStorage:
    """Database operations for strategy trades and backtests."""

    def __init__(self) -> None:
        """Initialize trade storage."""
        self.conn = get_connection_manager()

    def get_strategy_trades(
        self,
        strategy_id: str,
        cutoff_date: date,
    ) -> list[tuple[Any, Any]]:
        """Get trades for a strategy since cutoff date.

        Args:
            strategy_id: Strategy UUID
            cutoff_date: Earliest date to include

        Returns:
            List of (trade_date, pnl) tuples
        """
        with self.conn.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    o.created_at::DATE as trade_date,
                    o.realized_pnl as pnl
                FROM idea_outcomes o
                WHERE o.realized_pnl IS NOT NULL
                  AND o.created_at >= %s
                  AND o.strategy_id = %s
                ORDER BY o.created_at
                """,
                [str(cutoff_date), strategy_id],
            )
            return [(row[0], row[1]) for row in result.fetchall()]

    def get_symbol_trades(self, symbol: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent trades for a symbol.

        Args:
            symbol: Stock symbol
            limit: Maximum number of trades to return

        Returns:
            List of trade dicts
        """
        with self.conn.connection() as conn:
            result = conn.execute(
                """
                SELECT io.idea_id, io.symbol, io.entry_price, io.exit_price,
                       io.current_return_pct, io.status, io.entry_date
                FROM idea_outcomes io
                WHERE io.symbol = %s
                ORDER BY io.entry_date DESC
                LIMIT %s
                """,
                [symbol, limit],
            )
            rows = result.fetchall()
            trades_raw = rows_to_dicts(rows, conn)

        trades = []
        for row in trades_raw:
            trades.append(
                {
                    "id": str(row["idea_id"]),
                    "symbol": str(row["symbol"]),
                    "entry_price": float(row["entry_price"])
                    if row["entry_price"] is not None
                    else None,
                    "exit_price": float(row["exit_price"])
                    if row["exit_price"] is not None
                    else None,
                    "return_pct": float(row["current_return_pct"])
                    if row["current_return_pct"] is not None
                    else None,
                    "status": str(row["status"]),
                    "entry_date": row["entry_date"],
                }
            )
        return trades

    def get_backtest_runs(self, strategy_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Get backtest runs for a strategy.

        Args:
            strategy_id: Strategy UUID
            limit: Maximum number of runs to return

        Returns:
            List of backtest run dicts
        """
        with self.conn.connection() as conn:
            result = conn.execute(
                """
                SELECT id, start_date, end_date, sharpe_ratio, total_return_pct,
                       max_drawdown_pct, win_rate, num_trades, status, created_at
                FROM backtest_runs
                WHERE strategy_definition_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                [strategy_id, limit],
            )
            rows = result.fetchall()
            backtests_raw = rows_to_dicts(rows, conn)

        backtests = []
        for row in backtests_raw:
            backtests.append(
                {
                    "id": str(row["id"]),
                    "start_date": row["start_date"],
                    "end_date": row["end_date"],
                    "sharpe_ratio": float(row["sharpe_ratio"])
                    if row["sharpe_ratio"] is not None
                    else None,
                    "total_return_pct": float(row["total_return_pct"])
                    if row["total_return_pct"] is not None
                    else None,
                    "max_drawdown_pct": float(row["max_drawdown_pct"])
                    if row["max_drawdown_pct"] is not None
                    else None,
                    "win_rate": float(row["win_rate"]) if row["win_rate"] is not None else None,
                    "num_trades": int(row["num_trades"]) if row["num_trades"] else 0,
                    "status": str(row["status"]),
                    "created_at": row["created_at"],
                }
            )
        return backtests


# Singleton instance
_trade_storage_instance: TradeStorage | None = None


def get_trade_storage() -> TradeStorage:
    """Get singleton instance of trade storage."""
    global _trade_storage_instance  # noqa: PLW0603
    if _trade_storage_instance is None:
        _trade_storage_instance = TradeStorage()
    return _trade_storage_instance
