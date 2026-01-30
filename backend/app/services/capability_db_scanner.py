"""Database table capability scanner."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine, inspect

from app.storage.types import DatabaseConnection

from ..constants import DATABASE_URL
from ..logging_config import get_logger
from .capability_db_scanner_columns import (
    analyze_column_completeness,
    calculate_completeness_pct,
    detect_date_range,
)
from .capability_db_scanner_health import (
    calculate_freshness_status,
    calculate_health_status,
    get_foreign_key_references,
)
from .capability_db_scanner_persistence import save_capabilities as save_capabilities_to_db
from .config_loader import (
    categorize_by_name,
    get_expected_freshness,
    load_capabilities_config,
)

if TYPE_CHECKING:
    from ..storage.connection import ConnectionManager

logger = get_logger(__name__)


class DatabaseScanner:
    """Scans database tables to auto-discover capabilities.

    Detects table metadata including row counts, columns, field completeness,
    date ranges, and calculates freshness status based on config rules.
    """

    def __init__(
        self,
        connection_mgr: ConnectionManager,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize database scanner.

        Args:
            connection_mgr: ConnectionManager instance for database access
            config: Optional config dict (loads from file if not provided)
        """
        self.conn_mgr = connection_mgr
        self.config = config or load_capabilities_config()
        self.db_config = self.config["scan_config"]["targets"]["database"]

    def scan(self) -> list[dict[str, Any]]:
        """Scan all database tables and return capability metadata.

        Returns:
            List of dicts with table metadata:
                - table_name: str
                - category: str
                - row_count: int
                - total_columns: int
                - columns: list[str]
                - columns_with_data: list[str]
                - columns_mostly_null: list[str]
                - completeness_pct: int
                - date_range_start: date | None
                - date_range_end: date | None
                - expected_freshness: str
                - days_since_update: int | None
                - freshness_status: str
        """
        if not self.db_config["enabled"]:
            logger.info("database_scan_disabled")
            return []

        logger.info("scanning_database_tables")

        # Create SQLAlchemy engine for table introspection only
        engine = create_engine(DATABASE_URL)  # type: ignore[arg-type]
        inspector = inspect(engine)

        capabilities = []

        # Use our connection manager for executing queries
        with self.conn_mgr.connection() as conn:
            for table_name in inspector.get_table_names():
                try:
                    capability = self._scan_single_table(table_name, conn, inspector)
                    capabilities.append(capability)
                except Exception as e:
                    logger.error(
                        "table_scan_failed",
                        table=table_name,
                        error=str(e),
                    )

        logger.info(
            "database_scan_complete",
            tables_scanned=len(capabilities),
        )

        return capabilities

    def _scan_single_table(
        self,
        table_name: str,
        conn: DatabaseConnection,
        inspector: Any,
    ) -> dict[str, Any]:
        """Scan a single table for metadata.

        Args:
            table_name: Name of table to scan
            conn: SQLAlchemy connection
            inspector: SQLAlchemy inspector

        Returns:
            Dict with table metadata
        """
        # Get row count
        # Note: table_name is from database introspection, not user input
        result = conn.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        )  # validated: table from SQLAlchemy inspector
        row = result.fetchone()
        row_count_value = row[0] if row else 0
        row_count: int = (
            int(row_count_value) if isinstance(row_count_value, (int, float, str)) else 0
        )

        # Get columns
        columns = inspector.get_columns(table_name)
        column_names = [col["name"] for col in columns]
        total_columns = len(column_names)

        # Detect columns with data and mostly null columns
        columns_with_data: list[str] = []
        columns_mostly_null: list[str] = []

        if self.db_config["track_field_completeness"] and row_count > 0:
            null_threshold = self.db_config["null_threshold_pct"]
            if not isinstance(null_threshold, (int, float)):
                null_threshold = 50

            columns_with_data, columns_mostly_null = analyze_column_completeness(
                table_name=table_name,
                column_names=column_names,
                row_count=row_count,
                conn=conn,
                null_threshold_pct=null_threshold,
            )

        # Calculate completeness percentage
        completeness_pct = calculate_completeness_pct(columns_with_data, total_columns)

        # Detect date range
        date_range_start = None
        date_range_end = None

        if self.db_config["track_freshness"]:
            date_range_start, date_range_end = detect_date_range(
                table_name, conn, column_names
            )

        # Get expected freshness and calculate status
        expected_freshness = get_expected_freshness(table_name)
        days_since_update = None
        freshness_status = "unknown"

        if date_range_end:
            days_since_update = (datetime.now(UTC).date() - date_range_end).days
            freshness_status = calculate_freshness_status(
                expected_freshness,
                days_since_update,
            )

        # Categorize table
        category = categorize_by_name(table_name)

        # Check for foreign key references (tables that depend on this one)
        fk_references = get_foreign_key_references(table_name, conn)

        # Calculate health status (now considers FK references)
        health_status = calculate_health_status(
            table_name=table_name,
            row_count=row_count,
            columns_with_data=columns_with_data,
            columns=column_names,
            freshness_status=freshness_status,
            days_since_update=days_since_update,
            fk_references=fk_references,
        )

        return {
            "table_name": table_name,
            "category": category,
            "row_count": row_count,
            "total_columns": total_columns,
            "columns": column_names,
            "columns_with_data": columns_with_data,
            "columns_mostly_null": columns_mostly_null,
            "completeness_pct": completeness_pct,
            "date_range_start": date_range_start,
            "date_range_end": date_range_end,
            "expected_freshness": expected_freshness,
            "days_since_update": days_since_update,
            "freshness_status": freshness_status,
            "health_status": health_status,
            "fk_referenced_by": fk_references,  # NEW: tables that have FK to this table
        }


    def save_capabilities(self, capabilities: list[dict[str, Any]]) -> int:
        """Save scanned capabilities to db_capabilities table.

        Uses UPSERT logic (INSERT ... ON CONFLICT DO UPDATE) to update existing records.

        Args:
            capabilities: List of capability dicts from scan()

        Returns:
            Number of rows inserted/updated
        """
        return save_capabilities_to_db(self.conn_mgr, capabilities)
