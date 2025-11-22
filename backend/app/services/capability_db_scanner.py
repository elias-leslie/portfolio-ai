"""Database table capability scanner."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine, inspect

from app.storage.types import DatabaseConnection

from ..constants import DATABASE_URL
from ..logging_config import get_logger
from .capability_utils import _to_json_string
from .config_loader import (
    categorize_by_name,
    get_expected_freshness,
    get_freshness_thresholds,
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
        engine = create_engine(DATABASE_URL)
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
        columns_with_data = []
        columns_mostly_null = []

        if self.db_config["track_field_completeness"] and row_count > 0:
            null_threshold = self.db_config["null_threshold_pct"]
            if not isinstance(null_threshold, (int, float)):
                null_threshold = 50

            for col_name in column_names:
                try:
                    # Count non-NULL values
                    # Note: col_name from introspection, not user input
                    result = conn.execute(
                        f"SELECT COUNT({col_name}) as cnt FROM {table_name}"
                    )  # validated: table/column from SQLAlchemy inspector
                    row = result.fetchone()
                    non_null_value = row[0] if row else 0
                    non_null_count: int = (
                        int(non_null_value) if isinstance(non_null_value, (int, float, str)) else 0
                    )

                    if non_null_count > 0:
                        columns_with_data.append(col_name)

                    # Calculate NULL percentage
                    if row_count > 0:
                        null_pct = ((row_count - non_null_count) / row_count) * 100
                    else:
                        null_pct = 0

                    if null_pct > null_threshold:
                        columns_mostly_null.append(col_name)

                except Exception:
                    # Skip columns that cause errors (e.g., incompatible types)
                    continue

        # Calculate completeness percentage
        completeness_pct = (
            int((len(columns_with_data) / total_columns) * 100) if total_columns > 0 else 0
        )

        # Detect date range
        date_range_start = None
        date_range_end = None

        if self.db_config["track_freshness"]:
            date_range_start, date_range_end = self._detect_date_range(
                table_name, conn, column_names
            )

        # Get expected freshness and calculate status
        expected_freshness = get_expected_freshness(table_name)
        days_since_update = None
        freshness_status = "unknown"

        if date_range_end:
            days_since_update = (datetime.now(UTC).date() - date_range_end).days
            freshness_status = self._calculate_freshness_status(
                expected_freshness,
                days_since_update,
            )

        # Categorize table
        category = categorize_by_name(table_name)

        # Calculate health status
        health_status = self._calculate_health_status(
            row_count=row_count,
            columns_with_data=columns_with_data,
            columns=column_names,
            freshness_status=freshness_status,
            days_since_update=days_since_update,
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
        }

    def _detect_date_range(
        self,
        table_name: str,
        conn: DatabaseConnection,
        column_names: list[str],
    ) -> tuple[Any | None, Any | None]:
        """Detect date range for a table by finding MIN/MAX of timestamp columns.

        Args:
            table_name: Name of table
            conn: SQLAlchemy connection
            column_names: List of column names in table

        Returns:
            Tuple of (min_date, max_date) or (None, None) if no date columns found
        """
        # Try common timestamp column names in order of preference
        date_columns = ["created_at", "updated_at", "as_of_date", "date", "timestamp"]

        for col_name in date_columns:
            if col_name in column_names:
                try:
                    # validated: table_name from inspector.get_table_names(), col_name from schema column list
                    # Note: col_name validated from column_names list, not user input
                    result = conn.execute(
                        f"SELECT MIN({col_name}), MAX({col_name}) FROM {table_name} WHERE {col_name} IS NOT NULL"
                    )
                    row = result.fetchone()
                    if row is None:
                        continue

                    min_date, max_date = row

                    if min_date is not None and max_date is not None:
                        # Convert to date if timestamp
                        if hasattr(min_date, "date"):
                            min_date = min_date.date()
                        if hasattr(max_date, "date"):
                            max_date = max_date.date()

                        return min_date, max_date

                except Exception:
                    # Skip if column causes errors
                    continue

        return None, None

    def _calculate_freshness_status(
        self,
        expected_freshness: str,
        days_since_update: int,
    ) -> str:
        """Calculate freshness status based on expected freshness and days since update.

        Args:
            expected_freshness: Expected freshness string (e.g., "daily", "hourly")
            days_since_update: Days since last update

        Returns:
            Freshness status: "current", "acceptable", "stale", or "critical"
        """
        thresholds = get_freshness_thresholds(expected_freshness)

        if days_since_update <= thresholds["current"]:
            return "current"
        if days_since_update <= thresholds["acceptable"]:
            return "acceptable"
        if days_since_update <= thresholds["stale"]:
            return "stale"
        return "critical"

    def _calculate_health_status(
        self,
        row_count: int,
        columns_with_data: list[str],
        columns: list[str],
        freshness_status: str,
        days_since_update: int | None,
    ) -> str:
        """Calculate health status for database table.

        Args:
            row_count: Number of rows in table
            columns_with_data: Columns with non-NULL values
            columns: All columns
            freshness_status: Current freshness status
            days_since_update: Days since last update

        Returns:
            Health status: "active", "orphaned", "legacy", or "suspect"

        Database health logic:
        - orphaned: Very low row count (<100) AND no substantial data
        - legacy: No data (row_count=0) OR critically stale (>30 days + critical freshness)
        - suspect: Low data completeness (<20%) OR stale freshness
        - active: default (healthy table)
        """
        # Legacy: No data at all
        if row_count == 0:
            return "legacy"

        # Orphaned: Very low row count and minimal data
        if row_count < 100:
            # Calculate data completeness
            completeness = len(columns_with_data) / len(columns) if columns else 0
            if completeness < 0.2:  # Less than 20% columns have data
                return "orphaned"

        # Legacy: Critically stale data
        if (
            freshness_status == "critical"
            and days_since_update is not None
            and days_since_update > 30
        ):
            return "legacy"

        # Suspect: Low completeness or stale
        completeness = len(columns_with_data) / len(columns) if columns else 0
        if completeness < 0.3:  # Less than 30% columns have data
            return "suspect"

        if freshness_status in ["stale", "critical"]:
            return "suspect"

        return "active"

    def save_capabilities(self, capabilities: list[dict[str, Any]]) -> int:
        """Save scanned capabilities to db_capabilities table.

        Uses UPSERT logic (INSERT ... ON CONFLICT DO UPDATE) to update existing records.

        Args:
            capabilities: List of capability dicts from scan()

        Returns:
            Number of rows inserted/updated
        """
        if not capabilities:
            logger.info("no_db_capabilities_to_save")
            return 0

        logger.info("saving_db_capabilities", count=len(capabilities))

        with self.conn_mgr.connection() as conn:
            for cap in capabilities:
                # Convert lists to JSON strings for JSONB columns
                columns_json = _to_json_string(cap["columns"])
                columns_with_data_json = _to_json_string(cap["columns_with_data"])
                columns_mostly_null_json = _to_json_string(cap["columns_mostly_null"])

                # UPSERT query
                conn.execute(
                    """
                    INSERT INTO db_capabilities (
                        table_name, category, row_count, total_columns,
                        columns, columns_with_data, columns_mostly_null,
                        completeness_pct, date_range_start, date_range_end,
                        expected_freshness, days_since_update, freshness_status,
                        health_status, last_scanned_at, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (table_name) DO UPDATE SET
                        category = EXCLUDED.category,
                        row_count = EXCLUDED.row_count,
                        total_columns = EXCLUDED.total_columns,
                        columns = EXCLUDED.columns,
                        columns_with_data = EXCLUDED.columns_with_data,
                        columns_mostly_null = EXCLUDED.columns_mostly_null,
                        completeness_pct = EXCLUDED.completeness_pct,
                        date_range_start = EXCLUDED.date_range_start,
                        date_range_end = EXCLUDED.date_range_end,
                        expected_freshness = EXCLUDED.expected_freshness,
                        days_since_update = EXCLUDED.days_since_update,
                        freshness_status = EXCLUDED.freshness_status,
                        health_status = EXCLUDED.health_status,
                        last_scanned_at = EXCLUDED.last_scanned_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    [
                        cap["table_name"],
                        cap["category"],
                        cap["row_count"],
                        cap["total_columns"],
                        columns_json,
                        columns_with_data_json,
                        columns_mostly_null_json,
                        cap["completeness_pct"],
                        cap["date_range_start"],
                        cap["date_range_end"],
                        cap["expected_freshness"],
                        cap["days_since_update"],
                        cap["freshness_status"],
                        cap["health_status"],
                        datetime.now(UTC),  # last_scanned_at
                        datetime.now(UTC),  # created_at
                        datetime.now(UTC),  # updated_at
                    ],
                )
                conn.commit()

        logger.info("db_capabilities_saved", count=len(capabilities))
        return len(capabilities)
