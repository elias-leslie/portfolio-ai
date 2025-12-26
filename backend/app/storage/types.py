"""Type definitions for storage layer.

This module provides Protocol definitions for database connections and storage
interfaces, enabling proper type checking and IDE autocomplete while maintaining
duck typing compatibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import polars as pl

# Type alias for database values that can be returned from queries
DatabaseValue = str | int | float | bool | None
# Type alias for parameters that can be sent to database (includes lists for UNNEST/ANY operators)
ParameterValue = str | int | float | bool | None | datetime | list[str | int | float | bool | None]


class DatabaseConnection(Protocol):
    """Protocol for database connection objects.

    This protocol defines the interface for database connections used throughout
    the application. It enables type checking and IDE support while maintaining
    compatibility with different connection implementations (psycopg3, PostgreSQL, etc.).

    Methods:
        execute: Execute a SQL query with optional parameters (accepts list or tuple)
        fetchall: Fetch all results from last query
        fetchone: Fetch one result from last query
        fetchdf: Fetch query results as a DataFrame
        pl: Return a Polars-compatible interface
        commit: Commit the current transaction
        rollback: Rollback the current transaction
        close: Close the connection
    """

    def execute(
        self,
        query: str,
        parameters: list[ParameterValue] | tuple[ParameterValue, ...] | None = None,
    ) -> DatabaseConnection:
        """Execute a SQL query with optional parameters.

        Args:
            query: SQL query string
            parameters: Optional list or tuple of query parameters

        Returns:
            Self for method chaining
        """
        ...

    def fetchall(self) -> list[tuple[DatabaseValue, ...]]:
        """Fetch all results from last query.

        Returns:
            List of result rows as tuples
        """
        ...

    def fetchone(self) -> tuple[DatabaseValue, ...] | None:
        """Fetch one result from last query.

        Returns:
            Single result row as tuple, or None if no results
        """
        ...

    def fetchdf(self) -> pl.DataFrame:
        """Fetch query results as a Polars DataFrame.

        Returns:
            Polars DataFrame containing query results
        """
        ...

    def pl(self) -> pl.DataFrame:
        """Return results as a Polars DataFrame.

        Returns:
            Polars DataFrame interface
        """
        ...

    def commit(self) -> None:
        """Commit the current transaction.

        Persists all changes made since the last commit or rollback.
        """
        ...

    def rollback(self) -> None:
        """Rollback the current transaction.

        Undoes all changes made since the last commit.
        """
        ...

    def close(self) -> None:
        """Close the connection.

        Releases the connection back to the pool or closes it.
        """
        ...

    @property
    def raw_connection(self) -> Any:
        """Get underlying raw database connection.

        Returns:
            Raw connection object for cases needing direct access.
        """
        ...

    @property
    def description(self) -> list[tuple[str, Any]] | None:
        """Get column metadata from last query.

        Returns:
            List of column description tuples (name, type_code) or None.
        """
        ...
