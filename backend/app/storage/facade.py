"""PostgreSQL storage facade integrating all manager classes.

This module provides the main PortfolioStorage class that delegates operations to
specialized managers while maintaining a unified API. Uses PostgreSQLConnectionWrapper
to provide a PostgreSQL interface over PostgreSQL.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

from app.storage.types import DatabaseConnection, DatabaseValue, ParameterValue

from ..logging_config import get_logger

# Type hint only - actual connection is PostgreSQL via PostgreSQLConnectionWrapper
# See connection.py for wrapper implementation
if TYPE_CHECKING:
    pass  # Type hints for database connections

from .connection import get_connection_manager
from .ingestion import IngestionManager
from .metadata import MetadataManager
from .queries import QueryManager
from .schema import SchemaManager

logger = get_logger(__name__)


class PortfolioStorage:
    """Portfolio storage facade with modular manager delegation.

    This class provides a unified interface for database operations while
    delegating to specialized managers:
    - ConnectionManager: Connection pooling and lifecycle
    - SchemaManager: Schema creation and migrations
    - IngestionManager: Data insertion operations
    - MetadataManager: Table metadata tracking
    - QueryManager: Query operations
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Initialize portfolio storage with all managers.

        Args:
            db_path: Path to database file. If None, uses default PostgreSQL connection.
        """
        # Initialize connection manager (singleton)
        self.connection_mgr = get_connection_manager(db_path)  # type: ignore[arg-type]

        # Initialize specialized managers
        self.schema_mgr = SchemaManager(self.connection_mgr)
        self.metadata_mgr = MetadataManager(self.connection_mgr)
        self.ingestion_mgr = IngestionManager(self.connection_mgr, self.metadata_mgr)
        self.query_mgr = QueryManager(self.connection_mgr)

        # Ensure schema is initialized
        self.schema_mgr.ensure_schema()

        logger.info("PortfolioStorage initialized with modular managers")

    # Expose connection manager's connection method
    def connection(self) -> AbstractContextManager[DatabaseConnection]:
        """Context manager for PostgreSQL connections.

        Yields:
            PostgreSQL connection wrapper with query methods.
        """
        return self.connection_mgr.connection()

    # Schema methods
    def ensure_schema(self) -> None:
        """Ensure database schema is initialized."""
        return self.schema_mgr.ensure_schema()

    # Ingestion methods (delegate to IngestionManager)
    def insert_dataframe(self, table_name: str, df: pl.DataFrame, mode: str = "append") -> int:
        """Insert a Polars DataFrame into a table."""
        return self.ingestion_mgr.insert_dataframe(table_name, df, mode)

    def upsert_by_id(self, table_name: str, df: pl.DataFrame, id_column: str = "id") -> int:
        """Upsert data by primary key (delete + insert)."""
        return self.ingestion_mgr.upsert_by_id(table_name, df, id_column)

    def insert_dict(self, table_name: str, data: dict[str, DatabaseValue]) -> None:
        """Insert a single dictionary as a row."""
        return self.ingestion_mgr.insert_dict(table_name, data)

    def bulk_insert(self, table_name: str, rows: list[dict[str, DatabaseValue]]) -> int:
        """Insert multiple rows from list of dictionaries."""
        return self.ingestion_mgr.bulk_insert(table_name, rows)

    # Metadata methods (delegate to MetadataManager)
    def _update_table_metadata(self, conn: DatabaseConnection, table_name: str) -> None:
        """Update table_registry metadata after data write."""
        return self.metadata_mgr.update_table_metadata(conn, table_name)

    def get_table_counts(self) -> dict[str, int]:
        """Get row counts for all tables."""
        return self.metadata_mgr.get_table_counts()

    def print_status(self, prefix: str = "[storage]") -> None:
        """Print current database status with row counts."""
        return self.metadata_mgr.print_status(prefix)

    # Query methods (delegate to QueryManager)
    def query(self, sql: str, params: list[ParameterValue] | None = None) -> pl.DataFrame:
        """Execute a SQL query and return results as a Polars DataFrame."""
        return self.query_mgr.query(sql, params)

    def execute(self, sql: str, params: list[ParameterValue] | None = None) -> None:
        """Execute a write SQL query (INSERT, UPDATE, DELETE).

        Args:
            sql: SQL query string
            params: Optional list of query parameters
        """
        with self.connection() as conn:
            conn.execute(sql, params)
            conn.commit()


# Singleton instance
_storage: PortfolioStorage | None = None


def get_storage(db_path: str | Path | None = None) -> PortfolioStorage:
    """Get or create the singleton portfolio storage instance.

    Args:
        db_path: Optional path to database file

    Returns:
        PortfolioStorage instance
    """
    global _storage  # noqa: PLW0603
    if _storage is None:
        _storage = PortfolioStorage(db_path=db_path)
        logger.info("Created new PortfolioStorage singleton")
    return _storage
