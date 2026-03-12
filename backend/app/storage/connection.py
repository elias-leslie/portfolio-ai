"""PostgreSQL connection management with SQLAlchemy connection pooling.

This module provides connection lifecycle management for PostgreSQL storage.
Connections are pooled using SQLAlchemy QueuePool for concurrent access.
A PostgreSQL wrapper is provided to minimize code changes.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Literal

import pandas as pd
import polars as pl
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Engine

from app.config import sqlalchemy_database_url

# Import DATABASE_URL from constants (which handles dotenv loading)
from app.constants import DATABASE_URL as CONSTANTS_DATABASE_URL

from ..logging_config import get_logger

# Type alias for database values that can be returned from queries
# This is necessarily broad since PostgreSQL returns various types
DatabaseValue = str | int | float | bool | None
# Type alias for parameters that can be sent to database (includes lists for UNNEST/ANY operators)
ParameterValue = str | int | float | bool | None | date | datetime | list[str | int | float | bool | None]

logger = get_logger(__name__)

# Singleton instance
_connection_mgr: ConnectionManager | None = None


class PostgreSQLConnectionWrapper:
    """Wrapper to make psycopg connections behave like connections.

    This allows existing code using conn.execute() to work with PostgreSQL
    without modification. The wrapper translates ? placeholders
    to PostgreSQL-style %s placeholders.
    """

    def __init__(
        self,
        pg_conn: Any,
        engine: Engine | None = None,
    ) -> None:
        """Initialize wrapper around psycopg connection.

        Args:
            pg_conn: psycopg connection object (raw connection, not wrapper)
            engine: Optional SQLAlchemy engine (needed for DataFrame operations)
        """
        self._conn = pg_conn
        self._cursor = pg_conn.cursor()
        self._engine = engine

    def execute(
        self,
        query: str,
        parameters: list[ParameterValue] | tuple[ParameterValue, ...] | None = None,
    ) -> PostgreSQLConnectionWrapper:
        """Execute SQL query with PostgreSQL interface.

        Args:
            query: SQL query string (may use ? or $n placeholders)
            parameters: Optional list of parameters

        Returns:
            Self for method chaining (fetchall(), etc.)
        """
        # Convert ? placeholders to PostgreSQL %s placeholders
        if "?" in query:
            query = query.replace("?", "%s")

        # Convert PostgreSQL $1, $2, etc. placeholders to %s
        query = re.sub(r"\$\d+", "%s", query)

        if parameters:
            self._cursor.execute(query, parameters)
        else:
            self._cursor.execute(query)

        # Auto-commit DDL statements (CREATE, ALTER, DROP) for compatibility
        # auto-commits these, PostgreSQL needs explicit commit
        query_upper = query.strip().upper()
        if any(query_upper.startswith(ddl) for ddl in ["CREATE", "ALTER", "DROP"]):
            self._conn.commit()

        return self

    def fetchall(self) -> list[tuple[DatabaseValue, ...]]:
        """Fetch all results from last query."""
        result: list[tuple[DatabaseValue, ...]] = self._cursor.fetchall()
        return result

    def fetchone(self) -> tuple[DatabaseValue, ...] | None:
        """Fetch one result from last query."""
        result: tuple[DatabaseValue, ...] | None = self._cursor.fetchone()
        return result

    def _get_polars_dataframe(self) -> "pl.DataFrame":  # noqa: UP037
        """Convert query results to Polars DataFrame (compatibility).

        Returns:
            Polars DataFrame with query results.
        """
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
        return pl.DataFrame(data, strict=False)

    def pl(self) -> "pl.DataFrame":  # noqa: UP037
        """Convert query results to Polars DataFrame (compatibility).

        Returns:
            Polars DataFrame with query results.
        """
        return self._get_polars_dataframe()

    def pl_dataframe(self) -> "pl.DataFrame":  # noqa: UP037
        """Fetch results as Polars DataFrame (compatibility).

        Alias for .pl() method to match pl_dataframe() interface.

        Returns:
            Polars DataFrame with query results.
        """
        return self.pl()

    def fetchdf(self) -> "pl.DataFrame":  # noqa: UP037
        """Fetch results as Polars DataFrame (compatibility).

        Alias for .pl() method to match fetchdf() interface.

        Returns:
            Polars DataFrame with query results.
        """
        return self.pl()

    def df(self) -> pd.DataFrame:
        """Fetch results as pandas DataFrame (compatibility).

        Returns:
            pandas DataFrame with query results.
        """
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

    def insert_dataframe(
        self,
        table_name: str,
        df: pd.DataFrame | "pl.DataFrame",  # noqa: UP037
        if_exists: Literal["fail", "replace", "append"] = "append",
    ) -> int:
        """Insert pandas/polars DataFrame into table using efficient bulk insert.

        This method provides a clean alternative to variable reference
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
            Exception: If database operation fails

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
        if isinstance(df, pl.DataFrame):
            pdf = df.to_pandas()
        elif isinstance(df, pd.DataFrame):
            pdf = df
        else:
            raise TypeError(f"Expected pandas or polars DataFrame, got {type(df)}")

        if pdf.empty:
            logger.debug("empty_dataframe_skipped", table=table_name)
            return 0

        # Build INSERT statement
        columns = list(pdf.columns)
        columns_str = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

        # Convert DataFrame to list of tuples for executemany
        # Replace NaN with None for SQL NULL
        data = pdf.where(pd.notnull(pdf), None).values.tolist()

        # Execute bulk insert using raw cursor
        try:
            self._cursor.executemany(query, data)
            # Commit is handled by caller (IngestionManager) or auto-commit if not in transaction
            # But IngestionManager expects us to NOT commit if we are just part of a flow?
            # IngestionManager calls conn.commit() AFTER calling this.
            # So we just execute.
        except Exception as e:
            self._conn.rollback()
            raise e

        row_count = len(data)
        logger.debug("rows_inserted", table=table_name, count=row_count)
        return row_count

    @property
    def rowcount(self) -> int:
        """Number of rows affected by the last execute operation.

        Returns:
            Row count from the underlying cursor, or -1 if unavailable.
        """
        return self._cursor.rowcount

    @property
    def description(self) -> Any:
        """Get cursor description (column metadata).

        Returns:
            Tuple of column metadata tuples, or None if no cursor description available.
        """
        return self._cursor.description

    @property
    def raw_connection(self) -> Any:
        """Get underlying psycopg connection.

        This property exposes the raw psycopg connection for use cases that need
        direct access (e.g., passing to functions expecting a ConnectionProtocol).

        Returns:
            Raw psycopg connection object.
        """
        return self._conn


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
        # Prefer an explicit URL, then the current environment override, then the
        # import-time config snapshot. Tests rewrite PORTFOLIO_DB_URL at runtime.
        runtime_database_url = os.getenv("PORTFOLIO_DB_URL")
        url = database_url or runtime_database_url or CONSTANTS_DATABASE_URL
        if url is None:
            raise RuntimeError("DATABASE_URL must be set")
        self.database_url: str = url
        self.sqlalchemy_database_url: str = sqlalchemy_database_url(url)

        # Get pool size settings from environment or use defaults
        # Tests should use smaller values to avoid connection exhaustion
        pool_size_value = int(os.getenv("DB_POOL_SIZE", "20"))
        max_overflow_value = int(os.getenv("DB_MAX_OVERFLOW", "10"))

        # Create SQLAlchemy engine with connection pooling
        self.engine: Engine = create_engine(
            self.sqlalchemy_database_url,
            poolclass=pool.QueuePool,
            pool_size=pool_size_value,  # Max connections to keep open
            max_overflow=max_overflow_value,  # Max extra connections beyond pool_size
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=False,  # Set to True for SQL query logging
        )

        logger.info(
            f"ConnectionManager initialized with PostgreSQL (pool_size={pool_size_value}, max_overflow={max_overflow_value})"
        )

    @contextmanager
    def connection(self) -> Iterator[PostgreSQLConnectionWrapper]:
        """Context manager for PostgreSQL connections with PostgreSQL interface.

        Opens connection from pool, wraps it for compatibility, yields it
        for use, and returns it to pool on exit.

        Yields:
            PostgreSQLConnectionWrapper: Connection wrapper with methods:
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
        # Rollback any implicit transaction to start fresh and see latest committed data
        # This fixes stale reads when worker processes commit data that FastAPI doesn't see
        pg_conn.rollback()
        wrapper = PostgreSQLConnectionWrapper(pg_conn, engine=self.engine)
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
