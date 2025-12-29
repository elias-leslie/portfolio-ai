"""Repository layer for market data database operations.

Handles all database queries for market data, news sentiment, and indicators.
Extracted from market.py to reduce file size and improve separation of concerns.

Pattern: Repository handles data access, API layer handles business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

    def get_news_sentiment_hourly(self, days: int) -> list[tuple]:
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

    def get_news_sentiment_daily(self, days: int) -> list[tuple]:
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
