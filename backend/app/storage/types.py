"""Type definitions for storage layer.

This module provides Protocol definitions for database connections and storage
interfaces, enabling proper type checking and IDE autocomplete while maintaining
duck typing compatibility.
"""

from typing import Any, Protocol


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

    def execute(self, query: str, parameters: list[Any] | tuple[Any, ...] | None = None) -> Any:
        """Execute a SQL query with optional parameters.

        Args:
            query: SQL query string
            parameters: Optional list or tuple of query parameters

        Returns:
            Query execution result (implementation-specific)
        """
        ...

    def fetchall(self) -> list[tuple[Any, ...]]:
        """Fetch all results from last query.

        Returns:
            List of result rows as tuples
        """
        ...

    def fetchone(self) -> tuple[Any, ...] | None:
        """Fetch one result from last query.

        Returns:
            Single result row as tuple, or None if no results
        """
        ...

    def fetchdf(self) -> Any:
        """Fetch query results as a DataFrame.

        Returns:
            DataFrame containing query results (pandas or similar)
        """
        ...

    def pl(self) -> Any:
        """Return a Polars-compatible interface.

        Returns:
            Polars DataFrame or lazy frame interface
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
