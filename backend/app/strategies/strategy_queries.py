"""Strategy query and analysis operations.

This module handles complex queries for identifying symbols needing strategies
and strategies that are underperforming.
"""

from __future__ import annotations

from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)


# Strategy performance thresholds
UNDERPERFORMING_SHARPE_THRESHOLD = 0.5
DEFAULT_PERFORMANCE_THRESHOLD = 0.9
PERFORMANCE_WINDOW_DAYS = 30


class StrategyQueries:
    """Database queries for strategy analysis."""

    def __init__(self) -> None:
        """Initialize strategy queries."""
        self.conn = get_connection_manager()

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
                """
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
                      AND sp.date >= CURRENT_DATE - INTERVAL '%s days'
                    GROUP BY sd.symbol
                    HAVING AVG(sp.sharpe_ratio_30d) < %s
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
                (
                    PERFORMANCE_WINDOW_DAYS,
                    UNDERPERFORMING_SHARPE_THRESHOLD,
                    max_symbols * 2,
                ),  # Fetch extra in case some fail
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
        threshold = (
            performance_threshold
            if performance_threshold is not None
            else DEFAULT_PERFORMANCE_THRESHOLD
        )
        with self.conn.connection() as conn:
            return conn.execute(
                """
                SELECT DISTINCT sd.id, sd.symbol, sd.name,
                       sd.expected_sharpe,
                       AVG(sp.sharpe_ratio_30d) as actual_sharpe,
                       AVG(sp.sharpe_ratio_30d) / NULLIF(sd.expected_sharpe, 0) as performance_ratio
                FROM strategy_definitions sd
                JOIN strategy_performance sp ON sd.id = sp.strategy_id
                WHERE sd.status = 'active'
                  AND sp.date >= CURRENT_DATE - INTERVAL '%s days'
                  AND sd.expected_sharpe > 0
                GROUP BY sd.id, sd.symbol, sd.name, sd.expected_sharpe
                HAVING AVG(sp.sharpe_ratio_30d) / NULLIF(sd.expected_sharpe, 0) < %s
                ORDER BY performance_ratio ASC
                LIMIT %s
                """,
                (PERFORMANCE_WINDOW_DAYS, threshold, limit),
            ).fetchall()


# Singleton instance
_queries_instance: StrategyQueries | None = None


def get_strategy_queries() -> StrategyQueries:
    """Get singleton instance of strategy queries."""
    global _queries_instance  # noqa: PLW0603
    if _queries_instance is None:
        _queries_instance = StrategyQueries()
    return _queries_instance
