"""PostgreSQL query operations for portfolio data retrieval.

This module provides preset query methods and raw SQL execution capabilities.
Implementation details are delegated to focused sub-modules:
- _queries_snapshot: snapshot upsert helpers
- _queries_research: market/research data queries
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import polars as pl

from ..logging_config import get_logger
from ._queries_research import (
    get_bar_count,
    get_current_price,
    get_fear_greed_latest,
    get_news_data,
    get_ohlcv_data,
    get_spy_and_vix_data,
    get_symbol_sector,
)
from ._queries_snapshot import do_upsert_watchlist_snapshot
from .types import ParameterValue

if TYPE_CHECKING:
    from .connection import ConnectionManager

logger = get_logger(__name__)


class _ResearchQueryMixin:
    """Mixin providing market/research data query methods."""

    def query(self, sql: str, params: list[ParameterValue] | None = None) -> pl.DataFrame:
        """Provided by QueryManager; declared here for type checking."""
        raise NotImplementedError

    def get_news_data(self, symbol: str, start_date: str, end_date: str) -> pl.DataFrame:
        """Fetch news articles from the cache."""
        return get_news_data(self.query, symbol, start_date, end_date)

    def get_ohlcv_data(self, symbol: str, limit: int = 60) -> pl.DataFrame:
        """Fetch OHLCV data for trend analysis."""
        return get_ohlcv_data(self.query, symbol, limit)

    def get_current_price(self, symbol: str) -> float | None:
        """Get current price for a symbol."""
        return get_current_price(self.query, symbol)

    def get_bar_count(self, symbol: str) -> int:
        """Get total bar count for a symbol."""
        return get_bar_count(self.query, symbol)

    def get_fear_greed_latest(self) -> dict[str, int]:
        """Get latest Fear & Greed data."""
        return get_fear_greed_latest(self.query)

    def get_spy_and_vix_data(self) -> dict[str, float]:
        """Get latest SPY and VIX prices."""
        return get_spy_and_vix_data(self.query)

    def get_symbol_sector(self, symbol: str) -> str:
        """Get sector for a symbol from watchlist metadata."""
        return get_symbol_sector(self.query, symbol)


class QueryManager(_ResearchQueryMixin):
    """Manages query operations for PostgreSQL storage.

    Provides preset query methods for common use cases and raw SQL execution.
    Research/market data queries are provided via _ResearchQueryMixin.
    """

    def __init__(self, connection_mgr: ConnectionManager) -> None:
        self.connection_mgr = connection_mgr

    def query(self, sql: str, params: list[ParameterValue] | None = None) -> pl.DataFrame:
        """Execute a SQL query and return results as a Polars DataFrame."""
        with self.connection_mgr.connection() as conn:
            if params:
                result = conn.execute(sql, params).fetchdf()
            else:
                result = conn.execute(sql).fetchdf()
            return result

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
            FROM watchlist_snapshots_v
            WHERE item_id = ?
        """
        params: list[ParameterValue] = [item_id]

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
        **kwargs: object,
    ) -> None:
        """Insert or update a watchlist snapshot record.

        Delegates to do_upsert_watchlist_snapshot in _queries_snapshot.
        See that function for the full parameter list.
        """
        do_upsert_watchlist_snapshot(
            self.connection_mgr, item_id, fetched_at, **kwargs
        )
