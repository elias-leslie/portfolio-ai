"""PostgreSQL connection wrapper providing a unified query interface.

Contains the PostgreSQLConnectionWrapper class which wraps a raw psycopg
connection and provides fetchall/fetchone/DataFrame result methods.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

import pandas as pd
import polars as pl
from sqlalchemy.engine import Engine

from ..logging_config import get_logger

# Type alias for database values that can be returned from queries
# This is necessarily broad since PostgreSQL returns various types
DatabaseValue = str | int | float | bool | None
# Type alias for parameters that can be sent to database (includes lists for UNNEST/ANY operators)
ParameterValue = str | int | float | bool | None | date | datetime | list[str | int | float | bool | None]

logger = get_logger(__name__)


def _db_scalar(value: Any) -> Any:
    """Convert dataframe missing-value sentinels to DB nulls."""
    if isinstance(value, (dict, list, tuple, set)):
        return value
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        return value
    return value


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

    def _get_polars_dataframe(self) -> pl.DataFrame:
        """Convert query results to Polars DataFrame (compatibility)."""
        if self._cursor.description is None:
            return pl.DataFrame()

        columns = [desc[0] for desc in self._cursor.description]
        rows = self._cursor.fetchall()

        if not rows:
            return pl.DataFrame({col: [] for col in columns})

        data = {col: [row[i] for row in rows] for i, col in enumerate(columns)}
        return pl.DataFrame(data, strict=False)

    def pl(self) -> pl.DataFrame:
        """Convert query results to Polars DataFrame (compatibility)."""
        return self._get_polars_dataframe()

    def pl_dataframe(self) -> pl.DataFrame:
        """Fetch results as Polars DataFrame. Alias for .pl()."""
        return self.pl()

    def fetchdf(self) -> pl.DataFrame:
        """Fetch results as Polars DataFrame. Alias for .pl()."""
        return self.pl()

    def df(self) -> pd.DataFrame:
        """Fetch results as pandas DataFrame."""
        if self._cursor.description is None:
            return pd.DataFrame()

        columns = [desc[0] for desc in self._cursor.description]
        rows = self._cursor.fetchall()

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
        df: pd.DataFrame | pl.DataFrame,
        if_exists: Literal["fail", "replace", "append"] = "append",
    ) -> int:
        """Insert pandas/polars DataFrame into table using efficient bulk insert.

        Args:
            table_name: Target table name
            df: pandas or polars DataFrame to insert
            if_exists: 'append' (default), 'replace', or 'fail'

        Returns:
            Number of rows inserted

        Raises:
            ValueError: If table_name contains SQL injection characters
            TypeError: If df is not a supported DataFrame type
        """
        import pandas as pd  # noqa: PLC0415

        if not table_name.replace("_", "").isalnum():
            raise ValueError(f"Invalid table name: {table_name}")

        if isinstance(df, pl.DataFrame):
            if df.is_empty():
                logger.debug("empty_dataframe_skipped", table=table_name)
                return 0
            columns = list(df.columns)
            raw_rows = df.iter_rows()
        elif isinstance(df, pd.DataFrame):
            if df.empty:
                logger.debug("empty_dataframe_skipped", table=table_name)
                return 0
            columns = list(df.columns)
            raw_rows = df.itertuples(index=False, name=None)
        else:
            raise TypeError(f"Expected pandas or polars DataFrame, got {type(df)}")

        if not columns:
            logger.debug("empty_dataframe_skipped", table=table_name)
            return 0

        columns_str = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

        data = [[_db_scalar(value) for value in row] for row in raw_rows]

        try:
            self._cursor.executemany(query, data)
        except Exception as e:
            self._conn.rollback()
            raise e

        row_count = len(data)
        logger.debug("rows_inserted", table=table_name, count=row_count)
        return row_count

    @property
    def rowcount(self) -> int:
        """Number of rows affected by the last execute operation."""
        return self._cursor.rowcount

    @property
    def description(self) -> Any:
        """Get cursor description (column metadata)."""
        return self._cursor.description

    @property
    def raw_connection(self) -> Any:
        """Get underlying psycopg connection."""
        return self._conn
