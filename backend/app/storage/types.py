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
    compatibility with different connection implementations (psycopg3, DuckDB, etc.).

    Methods:
        execute: Execute a SQL query with optional parameters
        fetchdf: Fetch query results as a DataFrame
        pl: Return a Polars-compatible interface
        commit: Commit the current transaction
    """

    def execute(self, query: str, params: list[Any] | None = None) -> Any:
        """Execute a SQL query with optional parameters.

        Args:
            query: SQL query string
            params: Optional list of query parameters

        Returns:
            Query execution result (implementation-specific)
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
