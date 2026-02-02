"""Strategy storage and retrieval operations.

This module provides database operations for strategy definitions and performance tracking.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from app.storage.connection import get_connection_manager
from app.utils.db_helpers import rows_to_dicts

from .models import StrategyDefinition
from .storage_converters import row_to_strategy_definition
from .storage_delegator import StrategyStorageDelegator
from .storage_helpers import (
    ensure_symbol_exists,
    generate_strategy_id,
    generate_strategy_name,
    get_next_version,
    serialize_strategy_fields,
)

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


class StrategyStorage(StrategyStorageDelegator):
    """Database operations for strategy management."""

    # Strategy performance thresholds
    UNDERPERFORMING_SHARPE_THRESHOLD = 0.5
    DEFAULT_PERFORMANCE_THRESHOLD = 0.9
    PERFORMANCE_WINDOW_DAYS = 30

    def __init__(self) -> None:
        """Initialize strategy storage."""
        super().__init__()
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
        """Store new strategy in database. Returns strategy ID (UUID string)."""
        strategy_id = generate_strategy_id()
        name = generate_strategy_name(symbol, strategy_type)
        version = get_next_version(self.conn, symbol, name)

        # Serialize JSONB fields
        parameters_json, research_summary_json, backtest_metrics_json = serialize_strategy_fields(
            parameters, research_summary, backtest_metrics
        )

        with self.conn.connection() as conn:
            ensure_symbol_exists(conn, symbol)
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
        """Get strategy by ID."""
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

        return row_to_strategy_definition(result[0])

    def get_active_strategy(self, symbol: str) -> StrategyDefinition | None:
        """Get active strategy for symbol."""
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

        return row_to_strategy_definition(result[0])

    def get_top_watchlist_symbols(self, limit: int = 20, require_score: bool = False) -> list[str]:
        """Get top watchlist symbols ordered by overall score."""
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
        """List strategies with optional filtering."""
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

        return [row_to_strategy_definition(row) for row in result]

    def activate_strategy(self, strategy_id: str) -> None:
        """Activate strategy (sets status to 'active')."""
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
        """Archive strategy (sets status to 'archived')."""
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


# Singleton instance
_storage_instance: StrategyStorage | None = None


def get_strategy_storage() -> StrategyStorage:
    """Get singleton instance of strategy storage."""
    global _storage_instance  # noqa: PLW0603
    if _storage_instance is None:
        _storage_instance = StrategyStorage()
    return _storage_instance
