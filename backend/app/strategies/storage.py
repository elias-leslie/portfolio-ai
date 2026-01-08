"""Strategy storage and retrieval operations.

This module provides database operations for strategy definitions and performance tracking.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from app.storage.connection import get_connection_manager
from app.utils.db_helpers import generate_uuid, rows_to_dicts
from app.utils.json_helpers import json_serializer

from .models import (
    StrategyDefinition,
)
from .strategy_performance import get_performance_storage
from .strategy_queries import get_strategy_queries
from .strategy_seeds import get_seed_storage
from .strategy_signals import get_signal_storage
from .strategy_trades import get_trade_storage

logger = logging.getLogger(__name__)


# Strategy definitions table columns (matches CREATE TABLE order in migration 047)
STRATEGY_COLUMNS = """
    id, name, symbol, strategy_type,
    parameters, research_summary, generation_reasoning,
    backtest_metrics, expected_sharpe, expected_win_rate, expected_max_drawdown,
    created_by, created_at, version,
    status, activation_date, archive_date, archive_reason,
    live_trades_count, live_win_rate, live_sharpe_ratio, last_used_at
""".strip()


class StrategyStorage:
    """Database operations for strategy management."""

    # Strategy performance thresholds
    UNDERPERFORMING_SHARPE_THRESHOLD = 0.5
    DEFAULT_PERFORMANCE_THRESHOLD = 0.9
    PERFORMANCE_WINDOW_DAYS = 30

    def __init__(self) -> None:
        """Initialize strategy storage."""
        self.conn = get_connection_manager()
        self._seed_storage = get_seed_storage()
        self._performance_storage = get_performance_storage()
        self._signal_storage = get_signal_storage()
        self._queries = get_strategy_queries()
        self._trade_storage = get_trade_storage()

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
            symbol: Stock symbol
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
        strategy_id = generate_uuid()

        # Generate name: {symbol}_{type}_{version}
        name = self._generate_strategy_name(symbol, strategy_type)

        # Get next version number
        version = self._get_next_version(symbol, name)

        # Serialize JSONB fields (handle Decimal types)
        parameters_json = json.dumps(parameters, default=json_serializer)
        research_summary_json = json.dumps(research_summary, default=json_serializer)
        backtest_metrics_json = json.dumps(backtest_metrics, default=json_serializer)

        with self.conn.connection() as conn:
            self._ensure_symbol_exists(conn, symbol)
            conn.execute(
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
            conn.commit()

        logger.info(f"Strategy stored: {symbol} {strategy_type} v{version} (id={strategy_id})")

        return strategy_id

    def get_strategy_by_id(self, strategy_id: str) -> StrategyDefinition | None:
        """Get strategy by ID.

        Args:
            strategy_id: Strategy UUID

        Returns:
            StrategyDefinition or None if not found
        """
        with self.conn.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT {STRATEGY_COLUMNS}
                FROM strategy_definitions
                WHERE id = %s
                """,
                (strategy_id,),
            ).fetchall()

            if not rows:
                return None

            result = rows_to_dicts(rows, conn)

        return self._row_to_strategy_definition(result[0])

    def get_active_strategy(self, symbol: str) -> StrategyDefinition | None:
        """Get active strategy for symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Active StrategyDefinition or None if no active strategy
        """
        with self.conn.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT {STRATEGY_COLUMNS}
                FROM strategy_definitions
                WHERE symbol = %s AND status = 'active'
                ORDER BY version DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchall()

            if not rows:
                return None

            result = rows_to_dicts(rows, conn)

        return self._row_to_strategy_definition(result[0])

    def get_top_watchlist_symbols(
        self,
        limit: int = 20,
        require_score: bool = False,
    ) -> list[str]:
        """Get top watchlist symbols ordered by overall score.

        Args:
            limit: Maximum number of symbols to return
            require_score: If True, only return symbols with non-null scores

        Returns:
            List of symbol strings
        """
        score_condition = "WHERE overall_score IS NOT NULL" if require_score else ""

        with self.conn.connection() as conn:
            rows = conn.execute(
                f"""
                WITH latest_scores AS (
                    SELECT DISTINCT ON (wi.symbol)
                        wi.symbol,
                        ws.overall_score
                    FROM watchlist_items wi
                    LEFT JOIN watchlist_snapshots_v ws ON wi.id = ws.item_id
                    ORDER BY wi.symbol, ws.fetched_at DESC
                )
                SELECT symbol
                FROM latest_scores
                {score_condition}
                ORDER BY overall_score DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            ).fetchall()

        return [str(row[0]) for row in rows]

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

        with self.conn.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT {STRATEGY_COLUMNS}
                FROM strategy_definitions
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                tuple(params),
            ).fetchall()

            result = rows_to_dicts(rows, conn)

        return [self._row_to_strategy_definition(row) for row in result]

    def activate_strategy(self, strategy_id: str) -> None:
        """Activate strategy (sets status to 'active').

        Args:
            strategy_id: Strategy UUID
        """
        with self.conn.connection() as conn:
            conn.execute(
                """
                UPDATE strategy_definitions
                SET status = 'active',
                    activation_date = NOW()
                WHERE id = %s
                """,
                (strategy_id,),
            )
            conn.commit()

        logger.info(f"Strategy activated: {strategy_id}")

    def archive_strategy(self, strategy_id: str, reason: str) -> None:
        """Archive strategy (sets status to 'archived').

        Args:
            strategy_id: Strategy UUID
            reason: Reason for archiving
        """
        with self.conn.connection() as conn:
            conn.execute(
                """
                UPDATE strategy_definitions
                SET status = 'archived',
                    archive_date = NOW(),
                    archive_reason = %s
                WHERE id = %s
                """,
                (reason, strategy_id),
            )
            conn.commit()

        logger.info(f"Strategy archived: {strategy_id} (reason: {reason})")

    def update_live_performance(
        self,
        strategy_id: str,
        trades_count: int,
        win_rate: float,
        sharpe_ratio: float,
    ) -> None:
        """Update live performance metrics. Delegates to PerformanceStorage."""
        return self._performance_storage.update_live_performance(
            strategy_id, trades_count, win_rate, sharpe_ratio
        )

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
        """Record daily performance metrics. Delegates to PerformanceStorage."""
        return self._performance_storage.record_daily_performance(
            strategy_id,
            perf_date,
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
        )

    def _ensure_symbol_exists(self, conn: Any, symbol: str) -> None:
        """Ensure symbol exists in symbols table.

        Args:
            conn: Database connection
            symbol: Stock symbol to check/insert
        """
        conn.execute(
            """
            INSERT INTO symbols (symbol, security_type, created_at)
            VALUES (%s, 'equity', NOW())
            ON CONFLICT (symbol) DO NOTHING
            """,
            (symbol,),
        )

    def _generate_strategy_name(self, symbol: str, strategy_type: str) -> str:
        """Generate strategy name.

        Args:
            symbol: Stock symbol
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
            symbol: Stock symbol
            name: Strategy name

        Returns:
            Next version number (1 if no existing versions)
        """
        with self.conn.connection() as conn:
            rows = conn.execute(
                """
                SELECT MAX(version) as max_version
                FROM strategy_definitions
                WHERE symbol = %s AND name = %s
                """,
                (symbol, name),
            ).fetchall()

        if not rows or rows[0][0] is None:
            return 1

        return int(rows[0][0]) + 1

    def _row_to_strategy_definition(self, row: dict[str, Any]) -> StrategyDefinition:
        """Convert database row to StrategyDefinition.

        Args:
            row: Database row dict

        Returns:
            StrategyDefinition object
        """
        # Convert UUID to string, keep Decimal for Pydantic
        return StrategyDefinition(
            id=str(row["id"]),  # UUID → string
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

    def get_symbols_needing_strategies(self, max_symbols: int) -> list[tuple[Any, ...]]:
        """Get symbols that need strategy generation. Delegates to StrategyQueries."""
        return self._queries.get_symbols_needing_strategies(max_symbols)

    def get_underperforming_strategies(
        self, performance_threshold: float | None = None, limit: int = 5
    ) -> list[tuple[Any, ...]]:
        """Get active strategies with performance below threshold. Delegates to StrategyQueries."""
        return self._queries.get_underperforming_strategies(performance_threshold, limit)

    def get_strategy_trades(
        self,
        strategy_id: str,
        cutoff_date: date,
    ) -> list[tuple[Any, Any]]:
        """Get trades for a strategy since cutoff date. Delegates to TradeStorage."""
        return self._trade_storage.get_strategy_trades(strategy_id, cutoff_date)

    def get_strategy_seed(self, seed_id: str) -> tuple[str, float] | None:
        """Get strategy seed details. Delegates to SeedStorage."""
        return self._seed_storage.get_strategy_seed(seed_id)

    def get_seed_by_strategy_id(self, strategy_id: str) -> dict[str, Any] | None:
        """Get seed info for a strategy. Delegates to SeedStorage."""
        return self._seed_storage.get_seed_by_strategy_id(strategy_id)

    def get_backtest_runs(self, strategy_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Get backtest runs for a strategy. Delegates to TradeStorage."""
        return self._trade_storage.get_backtest_runs(strategy_id, limit)

    def get_strategy_signals(self, strategy_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent signals for a strategy. Delegates to SignalStorage."""
        return self._signal_storage.get_strategy_signals(strategy_id, limit)

    def get_symbol_trades(self, symbol: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent trades for a symbol. Delegates to TradeStorage."""
        return self._trade_storage.get_symbol_trades(symbol, limit)

    def link_strategy_to_seed(
        self,
        strategy_id: str,
        seed_id: str,
        seed_thesis: str,
        seed_confidence: float,
    ) -> None:
        """Link a generated strategy back to its seed. Delegates to SeedStorage."""
        return self._seed_storage.link_strategy_to_seed(
            strategy_id, seed_id, seed_thesis, seed_confidence
        )

    def reject_seed(self, seed_id: str) -> None:
        """Mark a seed as rejected. Delegates to SeedStorage."""
        return self._seed_storage.reject_seed(seed_id)

    def list_seeds(
        self,
        status: str | None = None,
        symbol: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[Any, ...]], int]:
        """List strategy seeds with optional filtering. Delegates to SeedStorage."""
        return self._seed_storage.list_seeds(status, symbol, limit, offset)

    def get_seed_by_id(self, seed_id: str) -> tuple[Any, ...] | None:
        """Get a specific strategy seed by ID. Delegates to SeedStorage."""
        return self._seed_storage.get_seed_by_id(seed_id)

    def get_performance_history(self, strategy_id: str, limit: int = 30) -> list[dict[str, Any]]:
        """Get performance history for a strategy. Delegates to PerformanceStorage."""
        return self._performance_storage.get_performance_history(strategy_id, limit)

    def store_signal(self, signal_data: dict[str, Any]) -> str | None:
        """Store a generated signal in the database. Delegates to SignalStorage."""
        return self._signal_storage.store_signal(signal_data)


# Singleton instance
_storage_instance: StrategyStorage | None = None


def get_strategy_storage() -> StrategyStorage:
    """Get singleton instance of strategy storage."""
    global _storage_instance  # noqa: PLW0603
    if _storage_instance is None:
        _storage_instance = StrategyStorage()
    return _storage_instance
