"""PostgreSQL storage facade integrating all manager classes.

This module provides the main StorageFacade class (DuckDBStorage name kept for backward compatibility)
that delegates operations to specialized managers while maintaining a unified API.
Uses PostgreSQLDuckDBWrapper to provide a DuckDB-compatible interface over PostgreSQL.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from ..logging_config import get_logger

# Type hint only - actual connection is PostgreSQL via PostgreSQLDuckDBWrapper
# See connection.py for wrapper implementation
if TYPE_CHECKING:
    import duckdb  # type: ignore[import-not-found]

from .connection import get_connection_manager
from .ingestion import IngestionManager
from .metadata import MetadataManager
from .queries import QueryManager
from .schema import SchemaManager

logger = get_logger(__name__)


class DuckDBStorage:
    """DuckDB storage facade with modular manager delegation.

    This class provides a unified interface for database operations while
    delegating to specialized managers:
    - ConnectionManager: Connection pooling and lifecycle
    - SchemaManager: Schema creation and migrations
    - IngestionManager: Data insertion operations
    - MetadataManager: Table metadata tracking
    - QueryManager: Query operations
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Initialize DuckDB storage with all managers.

        Args:
            db_path: Path to DuckDB database file. If None, uses default path.
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

        logger.info("DuckDBStorage initialized with modular managers")

    # Expose connection manager's connection method
    def connection(self) -> AbstractContextManager[duckdb.DuckDBPyConnection]:
        """Context manager for DuckDB connections.

        Yields:
            duckdb.DuckDBPyConnection: Active database connection.
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

    def insert_dict(self, table_name: str, data: dict[str, Any]) -> None:
        """Insert a single dictionary as a row."""
        return self.ingestion_mgr.insert_dict(table_name, data)

    def bulk_insert(self, table_name: str, rows: list[dict[str, Any]]) -> int:
        """Insert multiple rows from list of dictionaries."""
        return self.ingestion_mgr.bulk_insert(table_name, rows)

    # Metadata methods (delegate to MetadataManager)
    def _update_table_metadata(self, conn: duckdb.DuckDBPyConnection, table_name: str) -> None:
        """Update table_registry metadata after data write."""
        return self.metadata_mgr.update_table_metadata(conn, table_name)

    def get_table_counts(self) -> dict[str, int]:
        """Get row counts for all tables."""
        return self.metadata_mgr.get_table_counts()

    def print_status(self, prefix: str = "[duckdb]") -> None:
        """Print current database status with row counts."""
        return self.metadata_mgr.print_status(prefix)

    # Query methods (delegate to QueryManager)
    def query(self, sql: str, params: list[Any] | None = None) -> pl.DataFrame:
        """Execute a SQL query and return results as a Polars DataFrame."""
        return self.query_mgr.query(sql, params)


# Singleton instance
_storage: DuckDBStorage | None = None


def get_storage(db_path: str | Path | None = None) -> DuckDBStorage:
    """Get or create the singleton DuckDB storage instance.

    Args:
        db_path: Optional path to DuckDB database file

    Returns:
        DuckDBStorage instance
    """
    global _storage  # noqa: PLW0603
    if _storage is None:
        _storage = DuckDBStorage(db_path=db_path)
        logger.info("Created new DuckDBStorage singleton")
    return _storage
