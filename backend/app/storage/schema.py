"""PostgreSQL schema validation for portfolio-ai.

This module validates database schema initialization and applies incremental
migrations. Schema creation is handled by scripts/migrate-schema-to-postgres.py
to ensure proper PostgreSQL type conversion.

Note:
    Do NOT add inline DDL here. Keep migration script as single source of truth.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging_config import get_logger
from .migrations import MigrationManager
from .types import DatabaseConnection

if TYPE_CHECKING:
    from .connection import ConnectionManager

logger = get_logger(__name__)

# Schema version migrations (version, SQL) - Deprecated, use migrations/ directory
MIGRATIONS: list[tuple[str, str]] = []


class SchemaManager:
    """Validates PostgreSQL schema initialization for portfolio-ai.

    Verifies that core tables exist and applies incremental migrations.
    Schema creation must be done via migration script first.
    """

    def __init__(self, connection_mgr: ConnectionManager) -> None:
        """Initialize schema manager.

        Args:
            connection_mgr: ConnectionManager instance for database access.
        """
        self.connection_mgr = connection_mgr

    def ensure_schema(self) -> None:
        """Verify database schema is initialized.

        This method validates that core tables exist. It does NOT create tables.
        Schema creation is handled by the migration script for proper PostgreSQL
        type conversion and foreign key constraints.

        Raises:
            RuntimeError: If core tables are missing (schema not initialized)

        Note:
            To initialize schema, run:
            python scripts/migrate-schema-to-postgres.py
        """
        migration_mgr = MigrationManager(self.connection_mgr)

        with self.connection_mgr.connection() as conn:
            # Check if core tables exist
            result = conn.execute("""
                SELECT COUNT(DISTINCT table_name)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN (
                    'source_registry',
                    'source_credentials',
                    'portfolio_accounts',
                    'portfolio_positions',
                    'watchlist_items',
                    'watchlist_snapshots',
                    'day_bars',
                    'price_cache',
                    'agent_runs'
                )
            """).fetchone()

            core_table_count_raw = result[0] if result else 0
            core_table_count = core_table_count_raw if isinstance(core_table_count_raw, int) else 0

            if core_table_count < 9:
                raise RuntimeError(
                    f"Database schema incomplete: found {core_table_count}/9 core tables. "
                    "Initialize schema first:\n"
                    "  cd ~/portfolio-ai/backend\n"
                    "  python ../scripts/migrate-schema-to-postgres.py"
                )

            logger.info(f"Schema validation passed: {core_table_count} core tables exist")

        # Apply SQL file migrations (incremental schema updates)
        migration_mgr.apply_migrations()

    def _apply_migrations(self, conn: DatabaseConnection) -> None:
        """Apply backward-compatible schema migrations.

        Uses ADD COLUMN IF NOT EXISTS to allow safe re-runs.
        """
        for version, sql in MIGRATIONS:
            try:
                conn.execute(sql)
                logger.debug(f"Applied migration {version}")
            except Exception as e:
                logger.warning(f"Migration {version} failed (may already exist): {e}")

    def _populate_registry_metadata(self, conn: DatabaseConnection) -> None:
        """Populate table_registry with metadata for all tables."""
        registry_entries = [
            ("source_registry", "config", "Data source definitions"),
            ("source_credentials", "config", "API keys and secrets for data sources"),
            ("endpoint_catalog", "config", "API endpoint definitions and field mappings"),
            ("portfolio_accounts", "config", "Portfolio account definitions"),
            ("portfolio_positions", "config", "Portfolio position holdings"),
            ("user_preferences", "config", "User risk tolerance and trade preferences"),
            ("reference_cache", "config", "Cached reference metadata for watchlist tickers"),
            ("price_cache", "timeseries", "Cached price and analytics data"),
            ("day_bars", "timeseries", "Historical daily OHLCV data"),
            # minute_bars removed by /scrub_it 2025-12-02 (never implemented)
            ("technical_indicators", "timeseries", "Cached technical indicator values"),
            ("watchlist_items", "watchlist", "User watchlist items and notes"),
            ("watchlist_snapshots", "watchlist", "Cached watchlist scoring snapshots"),
            ("agent_runs", "metadata", "Agent execution tracking"),
            ("agent_ideas", "metadata", "Investment ideas generated by agents"),
            ("agent_tool_calls", "metadata", "Tool calls made during agent execution"),
            ("validation_results", "metadata", "Idea validation results"),
            ("source_performance", "metadata", "Multi-source failover performance tracking"),
            ("idea_outcomes", "metadata", "Paper trading outcomes for agent ideas"),
        ]

        for table_name, table_type, description in registry_entries:
            conn.execute(
                """
                INSERT INTO table_registry (table_name, table_type, description)
                VALUES (?, ?, ?)
                ON CONFLICT (table_name) DO UPDATE SET
                    table_type = EXCLUDED.table_type,
                    description = EXCLUDED.description
                """,
                [table_name, table_type, description],
            )

        logger.debug("Populated table_registry with %d entries", len(registry_entries))
