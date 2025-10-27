"""DuckDB query operations for portfolio data retrieval.

This module provides preset query methods and raw SQL execution capabilities.
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


class QueryManager:
    """Manages query operations for DuckDB storage.

    Provides preset query methods for common use cases and raw SQL execution.
    """

    def __init__(self, connection_mgr) -> None:
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
            return pl.from_pandas(result)
