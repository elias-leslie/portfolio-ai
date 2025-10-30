"""PostgreSQL connection management with SQLAlchemy connection pooling.

This module provides connection lifecycle management for PostgreSQL storage.
Connections are pooled using SQLAlchemy QueuePool for concurrent access.
A DuckDB-compatible wrapper is provided to minimize code changes.
"""

from __future__ import annotations

import logging
import os
import re
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

    def __init__(self, pg_conn: Any, engine: Any = None) -> None:
        """Initialize wrapper around psycopg2 connection.

        Args:
            pg_conn: psycopg2 connection object
            engine: Optional SQLAlchemy engine (needed for DataFrame operations)
        """
        self._conn = pg_conn
        self._cursor = pg_conn.cursor()
        self._engine = engine

    def execute(self, query: str, parameters: list[Any] | None = None) -> Any:
        """Execute SQL query with DuckDB-compatible interface.

        Args:
            query: SQL query string (may use ? or $n placeholders)
            parameters: Optional list of parameters

        Returns:
            Self for method chaining (fetchall(), etc.)
        """
        # Convert DuckDB ? placeholders to PostgreSQL %s placeholders
        if "?" in query:
            query = query.replace("?", "%s")

        # Convert PostgreSQL $1, $2, etc. placeholders to %s
        query = re.sub(r"\$\d+", "%s", query)

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

    def fetchdf(self) -> Any:
        """Fetch results as Polars DataFrame (DuckDB compatibility).

        Alias for .pl() method to match DuckDB's fetchdf() interface.

        Returns:
            Polars DataFrame with query results.
        """
        return self.pl()

    def df(self) -> Any:
        """Fetch results as pandas DataFrame (DuckDB compatibility).

        Returns:
            pandas DataFrame with query results.
        """
        try:
            import pandas as pd  # noqa: PLC0415  # type: ignore[import-untyped]

            # Get column names from cursor description
            if self._cursor.description is None:
                # No results to convert
                return pd.DataFrame()

            columns = [desc[0] for desc in self._cursor.description]
            rows = self._cursor.fetchall()

            # Create pandas DataFrame
            if not rows:
                return pd.DataFrame(columns=columns)

            return pd.DataFrame(rows, columns=columns)
        except ImportError as e:
            raise ImportError("pandas is required for .df() method") from e

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

    def insert_dataframe(self, table_name: str, df: Any, if_exists: str = "append") -> int:
        """Insert pandas/polars DataFrame into table using efficient bulk insert.

        This method provides a clean alternative to DuckDB's variable reference
        feature (SELECT * FROM pandas_df), which doesn't exist in PostgreSQL.

        Args:
            table_name: Target table name
            df: pandas or polars DataFrame to insert
            if_exists: 'append' (default), 'replace', or 'fail'
                - 'append': Insert data, table must exist
                - 'replace': Drop table and recreate (WARNING: destructive)
                - 'fail': Raise error if table exists

        Returns:
            Number of rows inserted

        Raises:
            ValueError: If table_name contains SQL injection characters
            ImportError: If pandas not installed
            psycopg2.Error: If database operation fails

        Example:
            >>> with mgr.connection() as conn:
            ...     df = pl.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
            ...     rows = conn.insert_dataframe("my_table", df)
            ...     print(f"Inserted {rows} rows")

        Note:
            Uses pandas.DataFrame.to_sql() with method='multi' for
            optimized batch insertion (100-1000x faster than row-by-row).
        """
        import pandas as pd  # noqa: PLC0415

        # Validate table name (prevent SQL injection)
        if not table_name.replace("_", "").isalnum():
            raise ValueError(f"Invalid table name: {table_name}")

        # Convert polars to pandas if needed
        if hasattr(df, "to_pandas"):
            pdf = df.to_pandas()
        elif isinstance(df, pd.DataFrame):
            pdf = df
        else:
            raise TypeError(f"Expected pandas or polars DataFrame, got {type(df)}")

        if pdf.empty:
            logger.debug(f"Skipping empty DataFrame for table {table_name}")
            return 0

        # Use pandas to_sql with SQLAlchemy connection for efficient bulk insert
        # pandas requires a proper SQLAlchemy connection in a transaction context
        if self._engine is None:
            raise RuntimeError(
                "SQLAlchemy engine not available. "
                "DataFrame operations require the engine to be passed to wrapper."
            )

        # pandas to_sql needs to run in its own transaction
        # Use the engine directly (not the wrapped connection) to avoid conflicts
        with self._engine.connect() as sql_conn, sql_conn.begin():
            pdf.to_sql(
                name=table_name,
                con=sql_conn,
                if_exists=if_exists,
                index=False,
                method="multi",  # Batch inserts (much faster than default)
            )

        row_count = len(pdf)
        logger.debug(f"Inserted {row_count} rows into {table_name}")
        return row_count

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
        self.database_url: str = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai",
        )  # type: ignore[assignment]

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
            PostgreSQLDuckDBWrapper: Connection wrapper with methods:
                - execute(query, params) → self
                - fetchall() → list[tuple]
                - fetchone() → tuple | None
                - fetchdf() → polars.DataFrame
                - pl() → polars.DataFrame
                - insert_dataframe(table, df) → int
                - commit(), rollback(), close()

        Example:
            >>> mgr = ConnectionManager()
            >>> with mgr.connection() as conn:
            ...     result = conn.execute("SELECT * FROM portfolio_accounts").fetchall()
            ...     # connection automatically returned to pool after block
        """
        logger.debug("Getting connection from PostgreSQL pool")
        pg_conn = self.engine.raw_connection()
        wrapper = PostgreSQLDuckDBWrapper(pg_conn, engine=self.engine)
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
