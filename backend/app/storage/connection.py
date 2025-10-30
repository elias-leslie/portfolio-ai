"""DuckDB connection management with singleton pattern.

This module provides connection lifecycle management for DuckDB storage.
Connections are pooled using a singleton pattern to ensure single connection
per process.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb

from ..constants import DEFAULT_DUCKDB_PATH as DEFAULT_DB_PATH

logger = logging.getLogger(__name__)

# Singleton instance
_connection_mgr: ConnectionManager | None = None


class ConnectionManager:
    """Manages DuckDB database connections with singleton pattern.

    Provides context manager for connection lifecycle and ensures
    single connection instance per process for connection pooling.

    Example:
        >>> mgr = get_connection_manager()
        >>> with mgr.connection() as conn:
        ...     result = conn.execute("SELECT * FROM my_table").fetchall()
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Initialize connection manager.

        Args:
            db_path: Path to DuckDB database file. If None, uses DEFAULT_DB_PATH.

        Example:
            >>> mgr = ConnectionManager("/path/to/db.duckdb")
            >>> mgr = ConnectionManager()  # Uses default path
        """
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"ConnectionManager initialized with db_path: {self.db_path}")

    @contextmanager
    def connection(self) -> Iterator[duckdb.DuckDBPyConnection]:
        """Context manager for DuckDB connections.

        Opens connection, yields it for use, and ensures it's closed on exit.
        Handles both successful completion and exceptions.

        Yields:
            duckdb.DuckDBPyConnection: Active database connection.

        Example:
            >>> mgr = ConnectionManager()
            >>> with mgr.connection() as conn:
            ...     conn.execute("CREATE TABLE test (id INT)")
            ...     # connection automatically closed after block
        """
        logger.debug(f"Opening DuckDB connection to {self.db_path}")
        # Open with read_write access for concurrent operations
        # DuckDB handles concurrency automatically with its MVCC system
        conn = duckdb.connect(str(self.db_path), read_only=False)
        try:
            # Configure for better concurrent performance
            conn.execute("SET enable_object_cache=true")
            conn.execute("SET threads=2")  # Limit threads per connection
            yield conn
        finally:
            conn.close()
            logger.debug("DuckDB connection closed")


def get_connection_manager(db_path: str | Path | None = None) -> ConnectionManager:
    """Get or create singleton ConnectionManager instance.

    Args:
        db_path: Optional path to DuckDB database file. Only used on first call.

    Returns:
        ConnectionManager instance (singleton).

    Example:
        >>> mgr = get_connection_manager()  # Creates singleton
        >>> mgr2 = get_connection_manager()  # Returns same instance
        >>> assert mgr is mgr2
    """
    global _connection_mgr  # noqa: PLW0603
    if _connection_mgr is None:
        _connection_mgr = ConnectionManager(db_path=db_path)
        logger.info("Created new ConnectionManager singleton")
    return _connection_mgr
