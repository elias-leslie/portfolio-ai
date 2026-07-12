"""PostgreSQL ingestion methods for portfolio and agent data.

This module handles data insertion and upserting operations for portfolio tables.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import polars as pl

from app.storage.types import DatabaseConnection

from ..logging_config import get_logger

if TYPE_CHECKING:
    from .connection import ConnectionManager
    from .metadata import MetadataManager

logger = get_logger(__name__)


class IngestionManager:
    """Manages data ingestion operations for PostgreSQL storage.

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

    def _validate_table_exists(self, conn: DatabaseConnection, table_name: str) -> bool:
        """Validate table exists in public schema (SQL injection prevention).

        Args:
            conn: Database connection
            table_name: Table name to validate

        Returns:
            True if table exists, False otherwise
        """
        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
            """,
            [table_name],
        ).fetchone()
        return result is not None and isinstance(result[0], int) and result[0] > 0

    def _validate_column_exists(
        self, conn: DatabaseConnection, table_name: str, column_name: str
    ) -> bool:
        """Validate column exists in table (SQL injection prevention).

        Args:
            conn: Database connection
            table_name: Table name (already validated)
            column_name: Column name to validate

        Returns:
            True if column exists, False otherwise
        """
        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            """,
            [table_name, column_name],
        ).fetchone()
        return result is not None and isinstance(result[0], int) and result[0] > 0

    def _upsert_dataframe(
        self,
        conn: Any,
        table_name: str,
        df: pl.DataFrame,
    ) -> None:
        """Helper method to upsert DataFrame using PostgreSQL ON CONFLICT.

        Args:
            conn: Database connection
            table_name: Table to upsert into
            df: DataFrame with data to upsert
        """
        # Get primary key columns for this table
        pk_query = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = 'public'
                AND tc.table_name = %s
            ORDER BY kcu.ordinal_position
        """
        pk_result = conn.execute(pk_query, [table_name]).fetchall()
        if not pk_result:
            raise ValueError(f"No primary key found for table '{table_name}'")

        pk_columns = [row[0] for row in pk_result]

        # Get all columns from dataframe
        all_columns = df.columns
        invalid_columns = [
            column
            for column in all_columns
            if not self._validate_column_exists(conn, table_name, column)
        ]
        if invalid_columns:
            raise ValueError(
                f"Columns {invalid_columns!r} do not exist in table '{table_name}'"
            )
        non_pk_columns = [col for col in all_columns if col not in pk_columns]

        # Convert Polars DataFrame to pandas for to_sql
        pdf = df.to_pandas()

        # Build ON CONFLICT DO UPDATE query
        columns_str = ", ".join(all_columns)
        values_placeholders = ", ".join([f"%({col})s" for col in all_columns])
        pk_conflict = ", ".join(pk_columns)
        update_assignments = []
        for col in non_pk_columns:
            if table_name == "day_bars" and col == "vwap":
                update_assignments.append(
                    "vwap = CASE "
                    "WHEN EXCLUDED.vwap IS NOT NULL "
                    "AND EXCLUDED.vwap::text <> 'NaN' "
                    "AND EXCLUDED.vwap > 0 "
                    "THEN EXCLUDED.vwap ELSE day_bars.vwap END"
                )
            else:
                update_assignments.append(f"{col} = EXCLUDED.{col}")
        conflict_action = (
            f"DO UPDATE SET {', '.join(update_assignments)}"
            if update_assignments
            else "DO NOTHING"
        )

        # Build and execute INSERT ... ON CONFLICT statement
        for _, row in pdf.iterrows():
            values = {col: row[col] for col in all_columns}
            query = f"""
                INSERT INTO {table_name} ({columns_str})
                VALUES ({values_placeholders})
                ON CONFLICT ({pk_conflict})
                {conflict_action}
            """
            conn.execute(query, values)

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
            mode: 'append', 'replace', or 'upsert'

        Returns:
            Number of rows inserted
        """
        if df.is_empty():
            return 0

        with self.connection_mgr.connection() as conn:
            # Validate table exists to prevent SQL injection
            if not self._validate_table_exists(conn, table_name):
                raise ValueError(f"Table '{table_name}' does not exist in public schema")

            if mode == "replace":
                conn.execute(
                    f"DELETE FROM {table_name}"
                )  # validated: table from information_schema
                conn.commit()  # Commit the deletion before insert
            elif mode == "upsert":
                # Use PostgreSQL ON CONFLICT for upsert
                self._upsert_dataframe(conn, table_name, df)
                conn.commit()

                row_count = len(df)
                if self.metadata_mgr:
                    self.metadata_mgr.update_table_metadata(conn, table_name)
                    conn.commit()

                logger.info("rows_upserted", table=table_name, count=row_count)
                return row_count

            # Use explicit DataFrame insertion instead of variable reference
            conn.insert_dataframe(table_name, df, if_exists="append")

            # CRITICAL: Commit the INSERT to persist data
            conn.commit()

            row_count = len(df)

            # Update metadata if manager exists
            if self.metadata_mgr:
                self.metadata_mgr.update_table_metadata(conn, table_name)
                conn.commit()

            logger.info("rows_inserted", table=table_name, count=row_count)
            return row_count

    def upsert_by_id(
        self,
        table_name: str,
        df: pl.DataFrame,
        id_column: str = "id",
    ) -> int:
        """Atomically upsert data by primary key without deleting rows.

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
            # Validate table and column exist to prevent SQL injection
            if not self._validate_table_exists(conn, table_name):
                raise ValueError(f"Table '{table_name}' does not exist in public schema")
            if not self._validate_column_exists(conn, table_name, id_column):
                raise ValueError(f"Column '{id_column}' does not exist in table '{table_name}'")

            if id_column not in df.columns:
                raise ValueError(f"DataFrame is missing ID column '{id_column}'")

            # PostgreSQL's ON CONFLICT path updates the existing row in place.
            # This preserves dependent foreign keys and keeps the old row intact
            # if validation or insertion fails before the single commit.
            self._upsert_dataframe(conn, table_name, df)

            row_count = len(df)

            # Update metadata if manager exists
            if self.metadata_mgr:
                self.metadata_mgr.update_table_metadata(conn, table_name)

            conn.commit()

            logger.info("rows_upserted", table=table_name, count=row_count)
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
