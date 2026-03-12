"""PostgreSQL schema validation for portfolio-ai.

This module validates that core tables exist at startup.
Schema migrations are managed by alembic (run `alembic upgrade head`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging_config import get_logger

if TYPE_CHECKING:
    from .connection import ConnectionManager

logger = get_logger(__name__)


class SchemaManager:
    """Validates PostgreSQL schema initialization for portfolio-ai.

    Verifies that core tables exist. Migrations are handled by alembic.
    """

    def __init__(self, connection_mgr: ConnectionManager) -> None:
        self.connection_mgr = connection_mgr

    def ensure_schema(self) -> None:
        """Verify database schema is initialized.

        Validates that core tables exist. Does NOT create or migrate tables.
        Use `alembic upgrade head` to apply migrations.

        Raises:
            RuntimeError: If core tables are missing
        """
        with self.connection_mgr.connection() as conn:
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
                    "Run migrations first:\n"
                    "  cd ~/portfolio-ai/backend\n"
                    "  alembic upgrade head"
                )

            logger.info("schema_validation_passed", core_tables=core_table_count)
