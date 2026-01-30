"""Health status calculation for database scanner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging_config import get_logger
from .config_loader import get_freshness_thresholds

if TYPE_CHECKING:
    from app.storage.types import DatabaseConnection

logger = get_logger(__name__)


# Infrastructure tables that should NOT be marked legacy/suspect based on freshness
# These tables don't need frequent updates to be considered healthy
FRESHNESS_EXEMPT_TABLES: set[str] = {
    # API credentials - only updated when credentials change
    "source_credentials",
    # Capabilities system - only updated during scans
    "capability_insights",
    "capability_notes",
    "db_capabilities",
    "celery_capabilities",
    "api_capabilities",
    # Celery infrastructure - managed by Celery
    "celery_taskmeta",
    "celery_tasksetmeta",
    # Migration tracking - only updated during migrations
    "schema_migrations",
    "alembic_version",
    # Maintenance tracking
    "maintenance_log",
}


def calculate_freshness_status(
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


def get_foreign_key_references(
    table_name: str,
    conn: DatabaseConnection,
) -> list[str]:
    """Get tables that have foreign keys pointing TO this table.

    This helps identify tables that cannot be safely removed because
    other tables depend on them.

    Args:
        table_name: Name of table to check
        conn: Database connection

    Returns:
        List of table names that reference this table via FK
    """
    try:
        result = conn.execute(
            """
            SELECT DISTINCT tc.table_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND ccu.table_name = %s
                AND tc.table_name != %s
            """,
            [table_name, table_name],
        )
        return [str(row[0]) for row in result.fetchall() if row[0]]
    except Exception as e:
        logger.debug("fk_reference_check_failed", table=table_name, error=str(e))
        return []


def calculate_health_status(
    table_name: str,
    row_count: int,
    columns_with_data: list[str],
    columns: list[str],
    freshness_status: str,
    days_since_update: int | None,
    fk_references: list[str] | None = None,
) -> str:
    """Calculate health status for database table.

    Args:
        table_name: Name of the table
        row_count: Number of rows in table
        columns_with_data: Columns with non-NULL values
        columns: All columns
        freshness_status: Current freshness status
        days_since_update: Days since last update
        fk_references: Tables that have FK refs to this table

    Returns:
        Health status: "active", "orphaned", "legacy", or "suspect"

    Database health logic:
    - active: Has FK references (other tables depend on it) OR healthy data
    - orphaned: Very low row count (<100) AND no substantial data AND no FK refs
    - legacy: No data (row_count=0) AND no FK refs OR critically stale (>30 days)
    - suspect: Low data completeness (<20%) OR stale freshness

    Note: Infrastructure tables (FRESHNESS_EXEMPT_TABLES) are exempt from
    freshness-based degradation since they don't need frequent updates.
    """
    # If other tables reference this via FK, it's active (needed for schema)
    if fk_references:
        return "active"

    # Infrastructure tables with data are always active (exempt from freshness checks)
    if table_name in FRESHNESS_EXEMPT_TABLES and row_count > 0:
        return "active"

    # Legacy: No data at all (and no FK refs)
    if row_count == 0:
        return "legacy"

    # Calculate completeness once
    completeness = len(columns_with_data) / len(columns) if columns else 0

    # Orphaned: Very low row count and minimal data
    if row_count < 100 and completeness < 0.2:
        return "orphaned"

    # Legacy: Critically stale data (>30 days with critical freshness)
    # Skip for infrastructure tables
    if table_name not in FRESHNESS_EXEMPT_TABLES:
        is_critically_stale = (
            freshness_status == "critical"
            and days_since_update is not None
            and days_since_update > 30
        )
        if is_critically_stale:
            return "legacy"

    # Suspect: Low completeness (<30%) or stale/critical freshness
    # Skip freshness check for infrastructure tables
    if table_name in FRESHNESS_EXEMPT_TABLES:
        is_suspect = completeness < 0.3
    else:
        is_suspect = completeness < 0.3 or freshness_status in ["stale", "critical"]
    return "suspect" if is_suspect else "active"
