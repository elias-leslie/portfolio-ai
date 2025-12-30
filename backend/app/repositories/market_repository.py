"""Repository layer for market data database operations.

Handles all database queries for market data, news sentiment, and indicators.
Extracted from market.py to reduce file size and improve separation of concerns.

Pattern: Repository handles data access, API layer handles business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

# Pseudo-symbol for market-wide events and readings
MARKET_SYMBOL = "__MARKET__"


class MarketRepository:
    """Database access layer for market data operations."""

    def __init__(self, storage: PortfolioStorage):
        """Initialize repository with storage instance.

        Args:
            storage: PortfolioStorage instance for database access
        """
        self.storage = storage

    def get_news_sentiment_hourly(self, days: int) -> list[tuple[Any, ...]]:
        """Get hourly aggregated news sentiment data.

        Args:
            days: Number of days of history to fetch

        Returns:
            List of (period, avg_score, pos_count, neg_count, total_count) tuples
        """
        with self.storage.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    DATE_TRUNC('hour', window_end) as period,
                    AVG(sentiment_score) as avg_score,
                    SUM(positive_count) as pos_count,
                    SUM(negative_count) as neg_count,
                    SUM(article_count) as total_count
                FROM news_summary_log
                WHERE symbol = MARKET_SYMBOL
                  AND window_end >= NOW() - INTERVAL '%s days'
                GROUP BY DATE_TRUNC('hour', window_end)
                ORDER BY period ASC
                """,
                [days],
            )
            return result.fetchall()

    def get_news_sentiment_daily(self, days: int) -> list[tuple[Any, ...]]:
        """Get daily aggregated news sentiment data.

        Args:
            days: Number of days of history to fetch

        Returns:
            List of (period, avg_score, pos_count, neg_count, total_count) tuples
        """
        with self.storage.connection() as conn:
            result = conn.execute(
                """
                SELECT DISTINCT ON (DATE(window_end))
                    DATE(window_end) as period,
                    sentiment_score as avg_score,
                    positive_count as pos_count,
                    negative_count as neg_count,
                    article_count as total_count
                FROM news_summary_log
                WHERE symbol = MARKET_SYMBOL
                  AND window_end >= NOW() - INTERVAL '%s days'
                ORDER BY DATE(window_end), window_end DESC
                """,
                [days],
            )
            return result.fetchall()

    def get_fear_greed_history_data(
        self, days: int
    ) -> list[tuple[Any, Any, Any, Any]]:
        """Get Fear & Greed historical data with put/call ratio.

        Args:
            days: Number of days of history to fetch

        Returns:
            List of (as_of_date, score, label, put_call_ratio) tuples
        """
        with self.storage.connection() as conn:
            result = conn.execute(
                """
                SELECT d.as_of_date, d.score, d.label, i.put_call_ratio
                FROM fear_greed_daily d
                LEFT JOIN fear_greed_inputs i ON d.as_of_date = i.as_of_date
                WHERE d.as_of_date >= CURRENT_DATE - %s
                ORDER BY d.as_of_date ASC
                """,
                [days],
            )
            return result.fetchall()

    def get_indicator_history_data(
        self, symbol: str, days: int
    ) -> list[tuple[Any, Any]]:
        """Get indicator historical data from day_bars.

        Args:
            symbol: The indicator symbol (e.g., '^GSPC', '^VIX')
            days: Number of days of history to fetch

        Returns:
            List of (date, close) tuples
        """
        with self.storage.connection() as conn:
            result = conn.execute(
                """
                SELECT date, close
                FROM day_bars
                WHERE symbol = %s AND date >= CURRENT_DATE - %s
                ORDER BY date ASC
                """,
                [symbol, days],
            )
            return result.fetchall()

    def get_market_trends_data(self, days: int) -> list[tuple[Any, Any]]:
        """Get Fear & Greed daily scores for trend charts.

        Args:
            days: Number of days of history to fetch

        Returns:
            List of (as_of_date, score) tuples in chronological order
        """
        with self.storage.connection() as conn:
            result = conn.execute(
                """
                SELECT as_of_date, score
                FROM fear_greed_daily
                ORDER BY as_of_date DESC
                LIMIT %s
                """,
                [days],
            )
            rows = result.fetchall()
        # Reverse to get chronological order (oldest first)
        return list(reversed(rows))

    def get_corporate_actions(
        self,
        action_type: str,
        symbol: str | None = None,
        limit: int = 50,
    ) -> list[tuple[Any, ...]]:
        """Get corporate actions (buybacks, dividends, splits).

        Args:
            action_type: Action type filter (buyback, dividend, split)
            symbol: Optional symbol filter
            limit: Maximum results to return

        Returns:
            List of action tuples
        """
        sql = """
            SELECT symbol, action_type, action_date, repurchase_amount,
                   shares_repurchased, dividend_amount, source, updated_at
            FROM corporate_actions
            WHERE action_type = %s
        """
        params: list[Any] = [action_type]

        if symbol:
            sql += " AND symbol = %s"
            params.append(symbol.upper())

        sql += " ORDER BY action_date DESC LIMIT %s"
        params.append(limit)

        with self.storage.connection() as conn:
            return conn.execute(sql, params).fetchall()

    def get_corporate_actions_summary(
        self, symbol: str | None = None
    ) -> list[tuple[Any, ...]]:
        """Get summary of corporate actions by symbol.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of (symbol, buyback_count, total_buybacks, latest_buyback) tuples
        """
        sql = """
            SELECT symbol,
                   COUNT(*) FILTER (WHERE action_type = 'buyback') as buyback_count,
                   SUM(repurchase_amount) FILTER (WHERE action_type = 'buyback') as total_buybacks,
                   MAX(action_date) FILTER (WHERE action_type = 'buyback') as latest_buyback
            FROM corporate_actions
        """
        params: list[Any] = []

        if symbol:
            sql += " WHERE symbol = %s"
            params.append(symbol.upper())

        sql += " GROUP BY symbol ORDER BY total_buybacks DESC NULLS LAST"

        with self.storage.connection() as conn:
            return conn.execute(sql, params).fetchall()
