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
from app.utils.json_helpers import json_serializer

from .models import (
    StrategyDefinition,
)

logger = logging.getLogger(__name__)


class StrategyStorage:
    """Database operations for strategy management."""

    # Strategy performance thresholds
    UNDERPERFORMING_SHARPE_THRESHOLD = 0.5
    DEFAULT_PERFORMANCE_THRESHOLD = 0.9
    PERFORMANCE_WINDOW_DAYS = 30

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
        strategy_id = str(uuid.uuid4())

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
                """
                SELECT *
                FROM strategy_definitions
                WHERE id = %s
                """,
                (strategy_id,),
            ).fetchall()

        if not rows:
            return None

        return self._row_to_strategy_definition(self._convert_row(rows[0]))

    def get_active_strategy(self, symbol: str) -> StrategyDefinition | None:
        """Get active strategy for symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Active StrategyDefinition or None if no active strategy
        """
        with self.conn.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM strategy_definitions
                WHERE symbol = %s AND status = 'active'
                ORDER BY version DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchall()

        if not rows:
            return None

        return self._row_to_strategy_definition(self._convert_row(rows[0]))

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
                SELECT *
                FROM strategy_definitions
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                tuple(params),
            ).fetchall()

        return [self._row_to_strategy_definition(self._convert_row(row)) for row in rows]

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
                    str(date),
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

    def _convert_row(self, row: tuple[Any, ...]) -> dict[str, Any]:
        """Convert database row tuple to dictionary.

        Args:
            row: Database row tuple from fetchall()

        Returns:
            Dictionary with column names as keys

        Note: Column order must match the CREATE TABLE order in migration 047:
            id, name, symbol, strategy_type,
            parameters, research_summary, generation_reasoning,
            backtest_metrics, expected_sharpe, expected_win_rate, expected_max_drawdown,
            created_by, created_at, version,
            status, activation_date, archive_date, archive_reason,
            live_trades_count, live_win_rate, live_sharpe_ratio, last_used_at
        """
        column_names = [
            "id",
            "name",
            "symbol",
            "strategy_type",
            "parameters",
            "research_summary",
            "generation_reasoning",
            "backtest_metrics",
            "expected_sharpe",
            "expected_win_rate",
            "expected_max_drawdown",
            "created_by",
            "created_at",  # Fixed order: created_at before version per schema
            "version",
            "status",
            "activation_date",
            "archive_date",
            "archive_reason",
            "live_trades_count",
            "live_win_rate",
            "live_sharpe_ratio",
            "last_used_at",
        ]
        return dict(zip(column_names, row, strict=False))

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
        """Get symbols that need strategy generation.

        Includes:
        1. Top watchlist symbols without active strategy
        2. Symbols with underperforming strategies (30-day Sharpe < threshold)

        Args:
            max_symbols: Maximum number of symbols to return

        Returns:
            List of (symbol, overall_score, reason) tuples
        """
        with self.conn.connection() as conn:
            return conn.execute(
                f"""
                WITH latest_scores AS (
                    SELECT DISTINCT ON (wi.symbol)
                        wi.symbol,
                        ws.overall_score
                    FROM watchlist_items wi
                    LEFT JOIN watchlist_snapshots_v ws ON wi.id = ws.item_id
                    ORDER BY wi.symbol, ws.fetched_at DESC
                ),
                active_strategies AS (
                    SELECT symbol, id, expected_sharpe
                    FROM strategy_definitions
                    WHERE status = 'active'
                ),
                underperforming AS (
                    SELECT DISTINCT sd.symbol
                    FROM strategy_definitions sd
                    JOIN strategy_performance sp ON sd.id = sp.strategy_id
                    WHERE sd.status = 'active'
                      AND sp.date >= CURRENT_DATE - INTERVAL '{self.PERFORMANCE_WINDOW_DAYS} days'
                    GROUP BY sd.symbol
                    HAVING AVG(sp.sharpe_ratio_30d) < {self.UNDERPERFORMING_SHARPE_THRESHOLD}
                )
                SELECT ls.symbol, ls.overall_score,
                       CASE
                           WHEN acts.id IS NULL THEN 'no_strategy'
                           WHEN under.symbol IS NOT NULL THEN 'underperforming'
                           ELSE 'active'
                       END as reason
                FROM latest_scores ls
                LEFT JOIN active_strategies acts ON ls.symbol = acts.symbol
                LEFT JOIN underperforming under ON ls.symbol = under.symbol
                WHERE acts.id IS NULL OR under.symbol IS NOT NULL
                ORDER BY ls.overall_score DESC NULLS LAST
                LIMIT %s
                """,
                (max_symbols * 2,),  # Fetch extra in case some fail
            ).fetchall()

    def get_underperforming_strategies(
        self, performance_threshold: float | None = None, limit: int = 5
    ) -> list[tuple[Any, ...]]:
        """Get active strategies with performance below threshold.

        Args:
            performance_threshold: Min ratio of actual/expected Sharpe (default uses DEFAULT_PERFORMANCE_THRESHOLD)
            limit: Maximum number of strategies to return

        Returns:
            List of (id, symbol, name, expected_sharpe, actual_sharpe, performance_ratio) tuples
        """
        threshold = performance_threshold if performance_threshold is not None else self.DEFAULT_PERFORMANCE_THRESHOLD
        with self.conn.connection() as conn:
            return conn.execute(
                f"""
                SELECT DISTINCT sd.id, sd.symbol, sd.name,
                       sd.expected_sharpe,
                       AVG(sp.sharpe_ratio_30d) as actual_sharpe,
                       AVG(sp.sharpe_ratio_30d) / NULLIF(sd.expected_sharpe, 0) as performance_ratio
                FROM strategy_definitions sd
                JOIN strategy_performance sp ON sd.id = sp.strategy_id
                WHERE sd.status = 'active'
                  AND sp.date >= CURRENT_DATE - INTERVAL '{self.PERFORMANCE_WINDOW_DAYS} days'
                  AND sd.expected_sharpe > 0
                GROUP BY sd.id, sd.symbol, sd.name, sd.expected_sharpe
                HAVING AVG(sp.sharpe_ratio_30d) / NULLIF(sd.expected_sharpe, 0) < %s
                ORDER BY performance_ratio ASC
                LIMIT %s
                """,
                (threshold, limit),
            ).fetchall()

    def get_strategy_trades(
        self,
        strategy_id: str,
        cutoff_date: date,
    ) -> list[tuple[date, Decimal]]:
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
                [cutoff_date, strategy_id],
            )
            return [(row[0], row[1]) for row in result.fetchall()]

    def get_strategy_seed(self, seed_id: str) -> tuple[str, float] | None:
        """Get strategy seed details.

        Args:
            seed_id: Seed UUID

        Returns:
            Tuple of (thesis, confidence) or None if not found
        """
        with self.conn.connection() as conn:
            row = conn.execute(
                "SELECT thesis, confidence FROM strategy_seeds WHERE id = %s",
                [seed_id],
            ).fetchone()

            if not row:
                return None

            thesis = str(row[0]) if row[0] else ""
            confidence = float(row[1]) if row[1] is not None else 0.0
            return (thesis, confidence)

    def link_strategy_to_seed(
        self,
        strategy_id: str,
        seed_id: str,
        seed_thesis: str,
        seed_confidence: float,
    ) -> None:
        """Link a generated strategy back to its seed.

        Updates strategy_definitions with seed info and marks seed as converted.

        Args:
            strategy_id: Strategy UUID
            seed_id: Seed UUID
            seed_thesis: Seed thesis text
            seed_confidence: Seed confidence score
        """
        with self.conn.connection() as conn:
            # Update strategy with seed info
            conn.execute(
                """
                UPDATE strategy_definitions
                SET seed_id = %s, seed_thesis = %s, seed_confidence = %s
                WHERE id = %s
                """,
                [seed_id, seed_thesis, seed_confidence, strategy_id],
            )

            # Mark seed as converted
            conn.execute(
                """
                UPDATE strategy_seeds
                SET status = 'converted', strategy_id = %s, processed_at = NOW()
                WHERE id = %s
                """,
                [strategy_id, seed_id],
            )
            conn.commit()

    def reject_seed(self, seed_id: str) -> None:
        """Mark a seed as rejected.

        Args:
            seed_id: Seed UUID
        """
        with self.conn.connection() as conn:
            conn.execute(
                """
                UPDATE strategy_seeds
                SET status = 'rejected', processed_at = NOW()
                WHERE id = %s
                """,
                [seed_id],
            )
            conn.commit()


# Singleton instance
_storage_instance: StrategyStorage | None = None


def get_strategy_storage() -> StrategyStorage:
    """Get singleton instance of strategy storage."""
    global _storage_instance  # noqa: PLW0603
    if _storage_instance is None:
        _storage_instance = StrategyStorage()
    return _storage_instance
