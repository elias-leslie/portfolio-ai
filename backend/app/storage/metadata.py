"""PostgreSQL metadata management operations.

This module handles table metadata tracking and database status operations.
Uses PostgreSQLDuckDBWrapper for DuckDB-compatible interface over PostgreSQL.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

# Type hint only - actual connection is PostgreSQL via PostgreSQLDuckDBWrapper
# See connection.py for wrapper implementation
if TYPE_CHECKING:
    import duckdb  # type: ignore[import-not-found]

    from .connection import ConnectionManager

logger = logging.getLogger(__name__)


class MetadataManager:
    """Manages table metadata and database status operations.

    Handles table_registry updates, row count tracking, and status reporting.
    """

    def __init__(self, connection_mgr: ConnectionManager) -> None:
        """Initialize metadata manager.

        Args:
            connection_mgr: ConnectionManager instance for database access.
        """
        self.connection_mgr = connection_mgr

    def update_table_metadata(self, conn: duckdb.DuckDBPyConnection, table_name: str) -> None:
        """Update table_registry metadata after data write.

        Updates last_written timestamp and row_count for the specified table.

        Args:
            conn: Active DuckDB connection
            table_name: Name of the table that was updated
        """
        # Check if table_registry exists (PostgreSQL-compatible query)
        result = conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'table_registry'
        """).fetchone()

        if not result:
            return  # table_registry not initialized yet

        # Get current row count
        try:
            result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            row_count = result[0] if result else 0
        except Exception:
            row_count = 0

        # Update table_registry
        conn.execute(
            """
            UPDATE table_registry
            SET last_written = now(),
                row_count = ?
            WHERE table_name = ?
            """,
            [row_count, table_name],
        )

    def get_table_counts(self) -> dict[str, int]:
        """Get row counts for all tables.

        Returns:
            Dictionary mapping table names to row counts
        """
        with self.connection_mgr.connection() as conn:
            tables = [
                "portfolio_accounts",
                "portfolio_positions",
                "user_preferences",
                "price_cache",
                "agent_runs",
                "agent_ideas",
                "agent_tool_calls",
                "validation_results",
            ]
            counts = {}
            for table in tables:
                try:
                    result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                    counts[table] = result[0] if result else 0
                except Exception:
                    counts[table] = 0
            return counts

    def print_status(self, prefix: str = "[duckdb]") -> None:
        """Print current database status with row counts."""
        counts = self.get_table_counts()
        print(f"{prefix} Database status:")
        for table, count in counts.items():
            if count > 0:
                print(f"{prefix}   {table}: {count:,} rows")

        total_portfolio_rows = counts.get("portfolio_accounts", 0) + counts.get(
            "portfolio_positions", 0
        )
        total_agent_rows = (
            counts.get("agent_runs", 0)
            + counts.get("agent_ideas", 0)
            + counts.get("agent_tool_calls", 0)
        )
        if total_portfolio_rows > 0:
            print(f"{prefix}   Total portfolio rows: {total_portfolio_rows:,}")
        if total_agent_rows > 0:
            print(f"{prefix}   Total agent rows: {total_agent_rows:,}")
