"""Strategy storage and retrieval operations.

This module provides database operations for strategy definitions and performance tracking.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from app.storage.connection import get_connection_manager

from .models import (
    StrategyDefinition,
)

logger = logging.getLogger(__name__)


class StrategyStorage:
    """Database operations for strategy management."""

    def __init__(self) -> None:
        """Initialize strategy storage."""
        self.conn = get_connection_manager()

    def store_strategy(
        self,
        symbol: str,
        strategy_type: str,
        parameters: dict[str, Any],
        research_summary: dict[str, Any],
        generation_reasoning: str,
        backtest_metrics: list[dict[str, Any]],
        expected_sharpe: float,
        expected_win_rate: float,
        expected_max_drawdown: float,
        created_by: str,
        status: Literal["testing", "active", "archived"] = "testing",
    ) -> str:
        """Store new strategy in database.

        Args:
            symbol: Stock ticker
            strategy_type: Strategy type (momentum, value, etc.)
            parameters: StrategyParameters as dict
            research_summary: ResearchInsights as dict
            generation_reasoning: Agent's explanation
            backtest_metrics: Walk-forward validation results
            expected_sharpe: Expected Sharpe ratio
            expected_win_rate: Expected win rate
            expected_max_drawdown: Expected max drawdown
            created_by: Creator identifier (e.g., "workflow:uuid")
            status: Initial status (default: testing)

        Returns:
            Strategy ID (UUID string)
        """
        strategy_id = str(uuid.uuid4())

        # Generate name: {symbol}_{type}_{version}
        name = self._generate_strategy_name(symbol, strategy_type)

        # Get next version number
        version = self._get_next_version(symbol, name)

        # Serialize JSONB fields
        parameters_json = json.dumps(parameters)
        research_summary_json = json.dumps(research_summary)
        backtest_metrics_json = json.dumps(backtest_metrics)

        self.conn.execute_query(
            """
            INSERT INTO strategy_definitions (
                id, name, symbol, strategy_type,
                parameters, research_summary, generation_reasoning,
                backtest_metrics, expected_sharpe, expected_win_rate, expected_max_drawdown,
                created_by, version, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                strategy_id,
                name,
                symbol,
                strategy_type,
                parameters_json,
                research_summary_json,
                generation_reasoning,
                backtest_metrics_json,
                expected_sharpe,
                expected_win_rate,
                expected_max_drawdown,
                created_by,
                version,
                status,
            ),
        )

        logger.info(f"Strategy stored: {symbol} {strategy_type} v{version} (id={strategy_id})")

        return strategy_id

    def get_strategy_by_id(self, strategy_id: str) -> StrategyDefinition | None:
        """Get strategy by ID.

        Args:
            strategy_id: Strategy UUID

        Returns:
            StrategyDefinition or None if not found
        """
        rows = self.conn.execute_query(
            """
            SELECT *
            FROM strategy_definitions
            WHERE id = %s
            """,
            (strategy_id,),
        )

        if not rows:
            return None

        return self._row_to_strategy_definition(rows[0])

    def get_active_strategy(self, symbol: str) -> StrategyDefinition | None:
        """Get active strategy for symbol.

        Args:
            symbol: Stock ticker

        Returns:
            Active StrategyDefinition or None if no active strategy
        """
        rows = self.conn.execute_query(
            """
            SELECT *
            FROM strategy_definitions
            WHERE symbol = %s AND status = 'active'
            ORDER BY version DESC
            LIMIT 1
            """,
            (symbol,),
        )

        if not rows:
            return None

        return self._row_to_strategy_definition(rows[0])

    def list_strategies(
        self,
        symbol: str | None = None,
        status: Literal["testing", "active", "archived"] | None = None,
        strategy_type: str | None = None,
        limit: int = 50,
    ) -> list[StrategyDefinition]:
        """List strategies with filtering.

        Args:
            symbol: Filter by symbol (optional)
            status: Filter by status (optional)
            strategy_type: Filter by strategy type (optional)
            limit: Maximum results (default 50)

        Returns:
            List of StrategyDefinition objects
        """
        conditions = []
        params: list[Any] = []

        if symbol:
            conditions.append("symbol = %s")
            params.append(symbol)
        if status:
            conditions.append("status = %s")
            params.append(status)
        if strategy_type:
            conditions.append("strategy_type = %s")
            params.append(strategy_type)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        params.append(limit)

        rows = self.conn.execute_query(
            f"""
            SELECT *
            FROM strategy_definitions
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            tuple(params),
        )

        return [self._row_to_strategy_definition(row) for row in rows]

    def activate_strategy(self, strategy_id: str) -> None:
        """Activate strategy (sets status to 'active').

        Args:
            strategy_id: Strategy UUID
        """
        self.conn.execute_query(
            """
            UPDATE strategy_definitions
            SET status = 'active',
                activation_date = NOW()
            WHERE id = %s
            """,
            (strategy_id,),
        )

        logger.info(f"Strategy activated: {strategy_id}")

    def archive_strategy(self, strategy_id: str, reason: str) -> None:
        """Archive strategy (sets status to 'archived').

        Args:
            strategy_id: Strategy UUID
            reason: Reason for archiving
        """
        self.conn.execute_query(
            """
            UPDATE strategy_definitions
            SET status = 'archived',
                archive_date = NOW(),
                archive_reason = %s
            WHERE id = %s
            """,
            (reason, strategy_id),
        )

        logger.info(f"Strategy archived: {strategy_id} (reason: {reason})")

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
        self.conn.execute_query(
            """
            UPDATE strategy_definitions
            SET live_trades_count = %s,
                live_win_rate = %s,
                live_sharpe_ratio = %s,
                last_used_at = NOW()
            WHERE id = %s
            """,
            (trades_count, win_rate, sharpe_ratio, strategy_id),
        )

    def record_daily_performance(
        self,
        strategy_id: str,
        date: date,
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
            date: Date of metrics
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
        self.conn.execute_query(
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
                date,
                trades_today,
                wins_today,
                losses_today,
                pnl_today,
                trades_30d,
                win_rate_30d,
                sharpe_ratio_30d,
                max_drawdown_30d,
                status,
                notes,
            ),
        )

    def _generate_strategy_name(self, symbol: str, strategy_type: str) -> str:
        """Generate strategy name.

        Args:
            symbol: Stock ticker
            strategy_type: Strategy type

        Returns:
            Strategy name (e.g., "AAPL_Momentum_2024Q4")
        """
        # Get current quarter
        now = datetime.now()
        quarter = (now.month - 1) // 3 + 1
        return f"{symbol}_{strategy_type.capitalize()}_{now.year}Q{quarter}"

    def _get_next_version(self, symbol: str, name: str) -> int:
        """Get next version number for strategy.

        Args:
            symbol: Stock ticker
            name: Strategy name

        Returns:
            Next version number (1 if no existing versions)
        """
        rows = self.conn.execute_query(
            """
            SELECT MAX(version) as max_version
            FROM strategy_definitions
            WHERE symbol = %s AND name = %s
            """,
            (symbol, name),
        )

        if not rows or rows[0]["max_version"] is None:
            return 1

        return int(rows[0]["max_version"]) + 1

    def _row_to_strategy_definition(self, row: dict[str, Any]) -> StrategyDefinition:
        """Convert database row to StrategyDefinition.

        Args:
            row: Database row dict

        Returns:
            StrategyDefinition object
        """
        return StrategyDefinition(
            id=row["id"],
            name=row["name"],
            symbol=row["symbol"],
            strategy_type=row["strategy_type"],
            parameters=row["parameters"],
            research_summary=row["research_summary"],
            generation_reasoning=row["generation_reasoning"],
            backtest_metrics=row["backtest_metrics"],
            expected_sharpe=row["expected_sharpe"],
            expected_win_rate=row["expected_win_rate"],
            expected_max_drawdown=row["expected_max_drawdown"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            version=row["version"],
            status=row["status"],
            activation_date=row.get("activation_date"),
            archive_date=row.get("archive_date"),
            archive_reason=row.get("archive_reason"),
            live_trades_count=row.get("live_trades_count", 0),
            live_win_rate=row.get("live_win_rate"),
            live_sharpe_ratio=row.get("live_sharpe_ratio"),
            last_used_at=row.get("last_used_at"),
        )


# Singleton instance
_storage_instance: StrategyStorage | None = None


def get_strategy_storage() -> StrategyStorage:
    """Get singleton instance of strategy storage."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StrategyStorage()
    return _storage_instance
