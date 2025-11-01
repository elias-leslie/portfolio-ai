"""PostgreSQL query operations for portfolio data retrieval.

This module provides preset query methods and raw SQL execution capabilities.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

import polars as pl

from ..logging_config import get_logger

if TYPE_CHECKING:
    from .connection import ConnectionManager

logger = get_logger(__name__)


class QueryManager:
    """Manages query operations for PostgreSQL storage.

    Provides preset query methods for common use cases and raw SQL execution.
    """

    def __init__(self, connection_mgr: ConnectionManager) -> None:
        """Initialize query manager.

        Args:
            connection_mgr: ConnectionManager instance for database access.
        """
        self.connection_mgr = connection_mgr

    def query(self, sql: str, params: list[Any] | None = None) -> pl.DataFrame:
        """Execute a SQL query and return results as a Polars DataFrame.

        Args:
            sql: SQL query string
            params: Optional list of parameter values for parameterized queries

        Returns:
            Polars DataFrame with query results
        """
        with self.connection_mgr.connection() as conn:
            if params:
                result = conn.execute(sql, params).fetchdf()
            else:
                result = conn.execute(sql).fetchdf()
            # fetchdf() already returns polars DataFrame, no conversion needed
            return result  # type: ignore[no-any-return]

    def get_watchlist_items_by_account(self, account_id: str) -> pl.DataFrame:
        """Return watchlist items for a given account ordered by symbol."""
        sql = """
            SELECT
                id,
                account_id,
                symbol,
                metadata,
                note,
                created_at,
                updated_at
            FROM watchlist_items
            WHERE account_id = ?
            ORDER BY symbol
        """
        return self.query(sql, [account_id])

    def get_watchlist_snapshot_history(
        self,
        item_id: str,
        *,
        limit: int = 100,
        start_at: datetime | None = None,
    ) -> pl.DataFrame:
        """Return historical snapshots for a watchlist item."""
        sql = """
            SELECT
                item_id,
                fetched_at,
                price,
                change_pct,
                beta,
                volatility,
                news_score,
                technical_score,
                fundamental_score,
                ai_score,
                ai_confidence,
                sector_score,
                competitor_score,
                overall_score,
                raw_metrics
            FROM watchlist_snapshots
            WHERE item_id = ?
        """
        params: list[Any] = [item_id]

        if start_at is not None:
            sql += " AND fetched_at >= ?"
            params.append(start_at)

        sql += " ORDER BY fetched_at DESC LIMIT ?"
        params.append(limit)

        return self.query(sql, params)

    def upsert_watchlist_snapshot(
        self,
        item_id: str,
        fetched_at: datetime,
        *,
        price: float | None = None,
        change_pct: float | None = None,
        beta: float | None = None,
        volatility: float | None = None,
        news_score: float | None = None,
        technical_score: float | None = None,
        fundamental_score: float | None = None,
        ai_score: float | None = None,
        ai_confidence: float | None = None,
        sector_score: float | None = None,
        competitor_score: float | None = None,
        overall_score: float | None = None,
        is_stale: bool = False,
        raw_metrics: dict[str, Any] | None = None,
    ) -> None:
        """Insert or update a watchlist snapshot record."""
        raw_metrics_json = json.dumps(raw_metrics) if raw_metrics is not None else None

        sql = """
            INSERT INTO watchlist_snapshots (
                item_id,
                fetched_at,
                price,
                change_pct,
                beta,
                volatility,
                news_score,
                technical_score,
                fundamental_score,
                ai_score,
                ai_confidence,
                sector_score,
                competitor_score,
                overall_score,
                is_stale,
                raw_metrics
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (item_id, fetched_at) DO UPDATE SET
                price = EXCLUDED.price,
                change_pct = EXCLUDED.change_pct,
                beta = EXCLUDED.beta,
                volatility = EXCLUDED.volatility,
                news_score = EXCLUDED.news_score,
                technical_score = EXCLUDED.technical_score,
                fundamental_score = EXCLUDED.fundamental_score,
                ai_score = EXCLUDED.ai_score,
                ai_confidence = EXCLUDED.ai_confidence,
                sector_score = EXCLUDED.sector_score,
                competitor_score = EXCLUDED.competitor_score,
                overall_score = EXCLUDED.overall_score,
                is_stale = EXCLUDED.is_stale,
                raw_metrics = EXCLUDED.raw_metrics
        """

        params = [
            item_id,
            fetched_at,
            price,
            change_pct,
            beta,
            volatility,
            news_score,
            technical_score,
            fundamental_score,
            ai_score,
            ai_confidence,
            sector_score,
            competitor_score,
            overall_score,
            is_stale,
            raw_metrics_json,
        ]

        with self.connection_mgr.connection() as conn:
            conn.execute(sql, params)
            conn.commit()  # Commit the upsert
