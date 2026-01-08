"""Strategy performance storage operations.

This module handles storage and retrieval of strategy performance metrics.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from app.storage.connection import get_connection_manager
from app.utils.db_helpers import rows_to_dicts

logger = logging.getLogger(__name__)


class PerformanceStorage:
    """Database operations for strategy performance tracking."""

    def __init__(self) -> None:
        """Initialize performance storage."""
        self.conn = get_connection_manager()

    def update_live_performance(
        self,
        strategy_id: str,
        trades_count: int,
        win_rate: float,
        sharpe_ratio: float,
    ) -> None:
        """Update live performance metrics.

        Args:
            strategy_id: Strategy UUID
            trades_count: Total live trades
            win_rate: Current win rate (0-1)
            sharpe_ratio: Current Sharpe ratio
        """
        with self.conn.connection() as conn:
            conn.execute(
                """
                UPDATE strategy_definitions
                SET live_trades_count = %s,
                    live_win_rate = %s,
                    live_sharpe_ratio = %s,
                    last_used_at = NOW(),
                    live_metrics_updated_at = NOW()
                WHERE id = %s
                """,
                (trades_count, win_rate, sharpe_ratio, strategy_id),
            )
            conn.commit()

    def record_daily_performance(
        self,
        strategy_id: str,
        perf_date: date,
        trades_today: int,
        wins_today: int,
        losses_today: int,
        pnl_today: Decimal,
        trades_30d: int,
        win_rate_30d: float,
        sharpe_ratio_30d: float,
        max_drawdown_30d: float,
        status: Literal["active", "underperforming"] = "active",
        notes: str | None = None,
    ) -> None:
        """Record daily performance metrics.

        Args:
            strategy_id: Strategy UUID
            perf_date: Date of metrics
            trades_today: Trades executed today
            wins_today: Winning trades today
            losses_today: Losing trades today
            pnl_today: P&L for today
            trades_30d: Rolling 30-day trade count
            win_rate_30d: Rolling 30-day win rate
            sharpe_ratio_30d: Rolling 30-day Sharpe ratio
            max_drawdown_30d: Rolling 30-day max drawdown
            status: Performance status (default: active)
            notes: Optional notes
        """
        with self.conn.connection() as conn:
            conn.execute(
                """
                INSERT INTO strategy_performance (
                    strategy_id, date,
                    trades_today, wins_today, losses_today, pnl_today,
                    trades_30d, win_rate_30d, sharpe_ratio_30d, max_drawdown_30d,
                    status, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (strategy_id, date) DO UPDATE SET
                    trades_today = EXCLUDED.trades_today,
                    wins_today = EXCLUDED.wins_today,
                    losses_today = EXCLUDED.losses_today,
                    pnl_today = EXCLUDED.pnl_today,
                    trades_30d = EXCLUDED.trades_30d,
                    win_rate_30d = EXCLUDED.win_rate_30d,
                    sharpe_ratio_30d = EXCLUDED.sharpe_ratio_30d,
                    max_drawdown_30d = EXCLUDED.max_drawdown_30d,
                    status = EXCLUDED.status,
                    notes = EXCLUDED.notes
                """,
                (
                    strategy_id,
                    str(perf_date),
                    trades_today,
                    wins_today,
                    losses_today,
                    float(pnl_today),
                    trades_30d,
                    win_rate_30d,
                    sharpe_ratio_30d,
                    max_drawdown_30d,
                    status,
                    notes,
                ),
            )
            conn.commit()

    def get_performance_history(self, strategy_id: str, limit: int = 30) -> list[dict[str, Any]]:
        """Get performance history for a strategy.

        Args:
            strategy_id: Strategy UUID
            limit: Maximum number of records to return (default 30)

        Returns:
            List of dicts with: date, trades_30d, win_rate_30d, sharpe_ratio_30d, max_drawdown_30d, status
        """
        with self.conn.connection() as conn:
            result = conn.execute(
                """
                SELECT date, trades_30d, win_rate_30d, sharpe_ratio_30d, max_drawdown_30d, status
                FROM strategy_performance
                WHERE strategy_id = %s
                ORDER BY date DESC
                LIMIT %s
                """,
                (strategy_id, limit),
            )
            rows = result.fetchall()
            return rows_to_dicts(rows, conn)


# Singleton instance
_performance_storage_instance: PerformanceStorage | None = None


def get_performance_storage() -> PerformanceStorage:
    """Get singleton instance of performance storage."""
    global _performance_storage_instance  # noqa: PLW0603
    if _performance_storage_instance is None:
        _performance_storage_instance = PerformanceStorage()
    return _performance_storage_instance
