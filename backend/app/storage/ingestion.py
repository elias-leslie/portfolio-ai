"""DuckDB ingestion methods for portfolio and agent data.

This module handles data insertion and upserting operations for portfolio tables.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import polars as pl

if TYPE_CHECKING:
    from .connection import ConnectionManager
    from .metadata import MetadataManager

logger = logging.getLogger(__name__)


class IngestionManager:
    """Manages data ingestion operations for DuckDB storage.

    Handles insertion of portfolio positions, accounts, agent runs, and ideas.
    """

    def __init__(
        self, connection_mgr: ConnectionManager, metadata_mgr: MetadataManager | None = None
    ) -> None:
        """Initialize ingestion manager.

        Args:
            connection_mgr: ConnectionManager instance for database access.
            metadata_mgr: Optional MetadataManager for table metadata updates.
        """
        self.connection_mgr = connection_mgr
        self.metadata_mgr = metadata_mgr

    def insert_dataframe(
        self,
        table_name: str,
        df: pl.DataFrame,
        mode: str = "append",
    ) -> int:
        """Insert a Polars DataFrame into a table.

        Args:
            table_name: Name of the table to insert into
            df: Polars DataFrame to insert
            mode: 'append' or 'replace'

        Returns:
            Number of rows inserted
        """
        if df.is_empty():
            return 0

        with self.connection_mgr.connection() as conn:
            # Convert polars to pandas for DuckDB
            pandas_df = df.to_pandas()  # noqa: F841 - DuckDB uses this variable in SQL

            if mode == "replace":
                conn.execute(f"DELETE FROM {table_name}")

            conn.execute(
                f"INSERT INTO {table_name} SELECT * FROM pandas_df",
            )

            row_count = len(df)

            # Update metadata if manager exists
            if self.metadata_mgr:
                self.metadata_mgr.update_table_metadata(conn, table_name)  # type: ignore[arg-type]

            logger.info(f"Inserted {row_count} rows into {table_name}")
            return row_count

    def upsert_by_id(
        self,
        table_name: str,
        df: pl.DataFrame,
        id_column: str = "id",
    ) -> int:
        """Upsert data by primary key (delete + insert).

        Args:
            table_name: Name of the table
            df: Polars DataFrame with data to upsert
            id_column: Name of the ID column for upsert key

        Returns:
            Number of rows upserted
        """
        if df.is_empty():
            return 0

        with self.connection_mgr.connection() as conn:
            # Get unique IDs to delete
            ids = df[id_column].to_list()
            placeholders = ",".join(["?" for _ in ids])

            # Delete existing rows
            conn.execute(
                f"DELETE FROM {table_name} WHERE {id_column} IN ({placeholders})",
                ids,
            )

            # Insert new rows
            pandas_df = df.to_pandas()  # noqa: F841 - DuckDB uses this variable in SQL
            conn.execute(
                f"INSERT INTO {table_name} SELECT * FROM pandas_df",
            )

            row_count = len(df)

            # Update metadata if manager exists
            if self.metadata_mgr:
                self.metadata_mgr.update_table_metadata(conn, table_name)  # type: ignore[arg-type]

            logger.info(f"Upserted {row_count} rows in {table_name}")
            return row_count

    def insert_dict(
        self,
        table_name: str,
        data: dict[str, Any],
    ) -> None:
        """Insert a single dictionary as a row.

        Args:
            table_name: Name of the table to insert into
            data: Dictionary with column names as keys
        """
        df = pl.DataFrame([data])
        self.insert_dataframe(table_name, df)

    def bulk_insert(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
    ) -> int:
        """Insert multiple rows from list of dictionaries.

        Args:
            table_name: Name of the table to insert into
            rows: List of dictionaries with column names as keys

        Returns:
            Number of rows inserted
        """
        if not rows:
            return 0

        df = pl.DataFrame(rows)
        return self.insert_dataframe(table_name, df)
