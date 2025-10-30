"""PostgreSQL connection management with SQLAlchemy connection pooling.

This module provides connection lifecycle management for PostgreSQL storage.
Connections are pooled using SQLAlchemy QueuePool for concurrent access.
A DuckDB-compatible wrapper is provided to minimize code changes.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine, pool  # type: ignore[import-not-found]
from sqlalchemy.engine import Engine  # type: ignore[import-not-found]

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Singleton instance
_connection_mgr: ConnectionManager | None = None


class PostgreSQLDuckDBWrapper:
    """Wrapper to make psycopg2 connections behave like DuckDB connections.

    This allows existing code using conn.execute() to work with PostgreSQL
    without modification. The wrapper translates DuckDB-style ? placeholders
    to PostgreSQL-style %s placeholders.
    """

    def __init__(self, pg_conn: Any) -> None:
        """Initialize wrapper around psycopg2 connection.

        Args:
            pg_conn: psycopg2 connection object
        """
        self._conn = pg_conn
        self._cursor = pg_conn.cursor()

    def execute(self, query: str, parameters: list[Any] | None = None) -> Any:
        """Execute SQL query with DuckDB-compatible interface.

        Args:
            query: SQL query string (may use ? placeholders)
            parameters: Optional list of parameters

        Returns:
            Self for method chaining (fetchall(), etc.)
        """
        # Convert DuckDB ? placeholders to PostgreSQL %s placeholders
        if "?" in query:
            query = query.replace("?", "%s")

        if parameters:
            self._cursor.execute(query, parameters)
        else:
            self._cursor.execute(query)

        # Auto-commit DDL statements (CREATE, ALTER, DROP) for DuckDB compatibility
        # DuckDB auto-commits these, PostgreSQL needs explicit commit
        query_upper = query.strip().upper()
        if any(query_upper.startswith(ddl) for ddl in ["CREATE", "ALTER", "DROP"]):
            self._conn.commit()

        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Fetch all results from last query."""
        return self._cursor.fetchall()  # type: ignore[no-any-return]

    def fetchone(self) -> tuple[Any, ...] | None:
        """Fetch one result from last query."""
        return self._cursor.fetchone()  # type: ignore[no-any-return]

    def pl(self) -> Any:
        """Convert query results to Polars DataFrame (DuckDB compatibility).

        Returns:
            Polars DataFrame with query results.
        """
        try:
            import polars as pl  # noqa: PLC0415

            # Get column names from cursor description
            if self._cursor.description is None:
                # No results to convert
                return pl.DataFrame()

            columns = [desc[0] for desc in self._cursor.description]
            rows = self._cursor.fetchall()

            # Create Polars DataFrame
            if not rows:
                return pl.DataFrame({col: [] for col in columns})

            # Convert to dict format for Polars
            data = {col: [row[i] for row in rows] for i, col in enumerate(columns)}
            return pl.DataFrame(data)
        except ImportError as e:
            raise ImportError("Polars is required for .pl() method") from e

    def commit(self) -> None:
        """Commit current transaction."""
        self._conn.commit()

    def rollback(self) -> None:
        """Rollback current transaction."""
        self._conn.rollback()

    def close(self) -> None:
        """Close cursor and connection."""
        self._cursor.close()
        self._conn.close()

    @property
    def description(self) -> Any:
        """Get cursor description (column metadata)."""
        return self._cursor.description


class ConnectionManager:
    """Manages PostgreSQL database connections with SQLAlchemy pooling.

    Provides context manager for connection lifecycle and connection pooling
    for concurrent access with multiple workers.

    Example:
        >>> mgr = get_connection_manager()
        >>> with mgr.connection() as conn:
        ...     result = conn.execute("SELECT * FROM my_table").fetchall()
    """

    def __init__(self, database_url: str | None = None) -> None:
        """Initialize connection manager with SQLAlchemy engine.

        Args:
            database_url: PostgreSQL connection string. If None, reads from
                DATABASE_URL environment variable.

        Example:
            >>> mgr = ConnectionManager("postgresql://user:pass@localhost:5432/db")
            >>> mgr = ConnectionManager()  # Uses DATABASE_URL env var
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai",
        )

        # Create SQLAlchemy engine with connection pooling
        self.engine: Engine = create_engine(
            self.database_url,
            poolclass=pool.QueuePool,
            pool_size=20,  # Max connections to keep open
            max_overflow=10,  # Max extra connections beyond pool_size
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=False,  # Set to True for SQL query logging
        )

        logger.info("ConnectionManager initialized with PostgreSQL (pool_size=20, max_overflow=10)")

    @contextmanager
    def connection(self) -> Iterator[PostgreSQLDuckDBWrapper]:
        """Context manager for PostgreSQL connections with DuckDB-compatible interface.

        Opens connection from pool, wraps it for DuckDB compatibility, yields it
        for use, and returns it to pool on exit.

        Yields:
            PostgreSQLDuckDBWrapper: DuckDB-compatible connection wrapper.

        Example:
            >>> mgr = ConnectionManager()
            >>> with mgr.connection() as conn:
            ...     result = conn.execute("SELECT * FROM portfolio_accounts").fetchall()
            ...     # connection automatically returned to pool after block
        """
        logger.debug("Getting connection from PostgreSQL pool")
        pg_conn = self.engine.raw_connection()
        wrapper = PostgreSQLDuckDBWrapper(pg_conn)
        try:
            yield wrapper
        finally:
            wrapper.close()  # Returns connection to pool
            logger.debug("Connection returned to pool")


def get_connection_manager(database_url: str | None = None) -> ConnectionManager:
    """Get or create singleton ConnectionManager instance.

    Args:
        database_url: Optional PostgreSQL connection string. Only used on first call.

    Returns:
        ConnectionManager instance (singleton).

    Example:
        >>> mgr = get_connection_manager()  # Creates singleton
        >>> mgr2 = get_connection_manager()  # Returns same instance
        >>> assert mgr is mgr2
    """
    global _connection_mgr  # noqa: PLW0603
    if _connection_mgr is None:
        _connection_mgr = ConnectionManager(database_url=database_url)
        logger.info("Created new ConnectionManager singleton")
    return _connection_mgr
