"""PostgreSQL connection management with SQLAlchemy connection pooling.

This module provides connection lifecycle management for PostgreSQL storage.
Connections are pooled using SQLAlchemy QueuePool for concurrent access.
A PostgreSQL wrapper is provided to minimize code changes.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Engine

from app.config import sqlalchemy_database_url

# Import DATABASE_URL from constants (which handles dotenv loading)
from app.constants import DATABASE_URL as CONSTANTS_DATABASE_URL

from ..logging_config import get_logger
from ._connection_wrapper import (
    DatabaseValue,
    ParameterValue,
    PostgreSQLConnectionWrapper,
)

__all__ = [
    "ConnectionManager",
    "DatabaseValue",
    "ParameterValue",
    "PostgreSQLConnectionWrapper",
    "get_connection_manager",
]

logger = get_logger(__name__)

# Singleton instance
_connection_mgr: ConnectionManager | None = None


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
        """
        # Prefer an explicit URL, then the current environment override, then the
        # import-time config snapshot. Tests rewrite PORTFOLIO_DB_URL at runtime.
        runtime_database_url = os.getenv("PORTFOLIO_DB_URL")
        url = database_url or runtime_database_url or CONSTANTS_DATABASE_URL
        if url is None:
            raise RuntimeError("DATABASE_URL must be set")
        self.database_url: str = url
        self.sqlalchemy_database_url: str = sqlalchemy_database_url(url)

        # This service shares the host PostgreSQL instance with Hatchet and other
        # managed applications. Keep each API/worker process inside a small,
        # explicit connection budget; callers can still override it for larger
        # standalone deployments.
        pool_size_value = int(os.getenv("DB_POOL_SIZE", "4"))
        max_overflow_value = int(os.getenv("DB_MAX_OVERFLOW", "2"))

        self.engine: Engine = create_engine(
            self.sqlalchemy_database_url,
            poolclass=pool.QueuePool,
            pool_size=pool_size_value,
            max_overflow=max_overflow_value,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )

        logger.info(
            "connection_manager_initialized",
            pool_size=pool_size_value,
            max_overflow=max_overflow_value,
        )

    @contextmanager
    def connection(self) -> Iterator[PostgreSQLConnectionWrapper]:
        """Context manager for PostgreSQL connections with PostgreSQL interface.

        Yields:
            PostgreSQLConnectionWrapper: Connection wrapper supporting
                execute/fetchall/fetchone/fetchdf/pl/insert_dataframe/commit/rollback.
        """
        logger.debug("pool_connection_checkout")
        pg_conn = self.engine.raw_connection()
        # Rollback any implicit transaction to start fresh and see latest committed data
        pg_conn.rollback()
        wrapper = PostgreSQLConnectionWrapper(pg_conn, engine=self.engine)
        try:
            yield wrapper
        finally:
            wrapper.close()
            logger.debug("pool_connection_returned")


def get_connection_manager(database_url: str | None = None) -> ConnectionManager:
    """Get or create singleton ConnectionManager instance.

    Args:
        database_url: Optional PostgreSQL connection string. Only used on first call.

    Returns:
        ConnectionManager instance (singleton).
    """
    global _connection_mgr  # noqa: PLW0603
    if _connection_mgr is None:
        _connection_mgr = ConnectionManager(database_url=database_url)
        logger.info("connection_manager_singleton_created")
    return _connection_mgr
