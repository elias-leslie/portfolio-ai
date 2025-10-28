"""DuckDB schema management for portfolio-ai.

This module manages database schema creation and table registry metadata.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Schema version migrations (version, SQL)
MIGRATIONS: list[tuple[str, str]] = []


class SchemaManager:
    """Manages DuckDB schema creation for portfolio-ai.

    Handles schema creation for all 8 tables and table registry metadata.
    """

    def __init__(self, connection_mgr) -> None:
        """Initialize schema manager.

        Args:
            connection_mgr: ConnectionManager instance for database access.
        """
        self.connection_mgr = connection_mgr

    def ensure_schema(self) -> None:
        """Create all 8 database tables in a single transaction.

        Creates tables in dependency order with transaction wrapper for atomicity.
        """
        with self.connection_mgr.connection() as conn:
            try:
                conn.execute("BEGIN TRANSACTION")

                self._create_config_tables(conn)
                self._create_timeseries_tables(conn)
                self._create_metadata_tables(conn)

                # Apply migrations and populate registry
                self._apply_migrations(conn)
                self._populate_registry_metadata(conn)

                conn.execute("COMMIT")
                logger.info("Schema initialization completed successfully (8 tables)")

            except Exception as e:
                conn.execute("ROLLBACK")
                logger.error(f"Schema initialization failed, rolled back: {e}")
                raise

    def _create_config_tables(self, conn) -> None:
        """Create configuration tables (3 tables)."""
        # portfolio_accounts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_accounts (
                id                     TEXT PRIMARY KEY,
                name                   TEXT NOT NULL,
                account_type           TEXT NOT NULL,
                created_at             TIMESTAMP DEFAULT now(),
                updated_at             TIMESTAMP DEFAULT now()
            )
        """)

        # portfolio_positions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_positions (
                id                     TEXT PRIMARY KEY,
                account_id             TEXT NOT NULL,
                symbol                 TEXT NOT NULL,
                shares                 DOUBLE NOT NULL,
                cost_basis             DOUBLE NOT NULL,
                position_type          TEXT NOT NULL,
                created_at             TIMESTAMP DEFAULT now(),
                updated_at             TIMESTAMP DEFAULT now(),
                FOREIGN KEY (account_id) REFERENCES portfolio_accounts(id)
            )
        """)

        # user_preferences
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id                     TEXT PRIMARY KEY,
                risk_tolerance         INTEGER NOT NULL,
                allow_long             BOOLEAN DEFAULT true,
                allow_short            BOOLEAN DEFAULT false,
                allow_options          BOOLEAN DEFAULT false,
                allow_crypto           BOOLEAN DEFAULT false,
                allow_futures          BOOLEAN DEFAULT false,
                max_position_size_pct  DOUBLE DEFAULT 10.0,
                created_at             TIMESTAMP DEFAULT now(),
                updated_at             TIMESTAMP DEFAULT now()
            )
        """)

    def _create_timeseries_tables(self, conn) -> None:
        """Create time-series data tables (1 table)."""
        # price_cache
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_cache (
                symbol                 TEXT NOT NULL,
                price                  DOUBLE NOT NULL,
                beta                   DOUBLE,
                volatility             DOUBLE,
                sector                 TEXT,
                cached_at              TIMESTAMP NOT NULL,
                source                 TEXT NOT NULL,
                error                  TEXT,
                PRIMARY KEY (symbol, cached_at)
            )
        """)

    def _create_metadata_tables(self, conn) -> None:
        """Create metadata and tracking tables (4 tables)."""
        # agent_runs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id                     TEXT PRIMARY KEY,
                agent_type             TEXT NOT NULL,
                started_at             TIMESTAMP NOT NULL,
                completed_at           TIMESTAMP,
                status                 TEXT NOT NULL,
                num_ideas              INTEGER DEFAULT 0,
                cost_usd               DOUBLE DEFAULT 0.0,
                error_message          TEXT,
                metadata               JSON
            )
        """)

        # agent_ideas
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_ideas (
                id                     TEXT PRIMARY KEY,
                agent_run_id           TEXT NOT NULL,
                idea_type              TEXT NOT NULL,
                title                  TEXT NOT NULL,
                thesis                 TEXT NOT NULL,
                action                 TEXT NOT NULL,
                confidence_score       DOUBLE NOT NULL,
                risk_level             TEXT NOT NULL,
                reward_estimate        TEXT,
                portfolio_impact       TEXT,
                data_needed            TEXT,
                risks                  TEXT,
                status                 TEXT DEFAULT 'pending',
                created_at             TIMESTAMP DEFAULT now(),
                updated_at             TIMESTAMP DEFAULT now(),
                FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id)
            )
        """)

        # agent_tool_calls
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_tool_calls (
                id                     TEXT PRIMARY KEY,
                agent_run_id           TEXT NOT NULL,
                tool_name              TEXT NOT NULL,
                parameters             JSON NOT NULL,
                response_summary       TEXT,
                duration_ms            INTEGER,
                called_at              TIMESTAMP DEFAULT now(),
                FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id)
            )
        """)

        # validation_results
        conn.execute("""
            CREATE TABLE IF NOT EXISTS validation_results (
                id                     TEXT PRIMARY KEY,
                idea_id                TEXT NOT NULL,
                validation_type        TEXT NOT NULL,
                passed                 BOOLEAN NOT NULL,
                details                TEXT,
                validated_at           TIMESTAMP DEFAULT now(),
                FOREIGN KEY (idea_id) REFERENCES agent_ideas(id)
            )
        """)

        # table_registry (for metadata tracking)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS table_registry (
                table_name             TEXT PRIMARY KEY,
                table_type             TEXT,
                description            TEXT,
                row_count              BIGINT DEFAULT 0,
                last_written           TIMESTAMP,
                created_at             TIMESTAMP DEFAULT now()
            )
        """)

    def _apply_migrations(self, conn) -> None:
        """Apply backward-compatible schema migrations.

        Uses ADD COLUMN IF NOT EXISTS to allow safe re-runs.
        """
        for version, sql in MIGRATIONS:
            try:
                conn.execute(sql)
                logger.debug(f"Applied migration {version}")
            except Exception as e:
                logger.warning(f"Migration {version} failed (may already exist): {e}")

    def _populate_registry_metadata(self, conn) -> None:
        """Populate table_registry with metadata for all tables."""
        registry_entries = [
            ("portfolio_accounts", "config", "Portfolio account definitions"),
            ("portfolio_positions", "config", "Portfolio position holdings"),
            ("user_preferences", "config", "User risk tolerance and trade preferences"),
            ("price_cache", "timeseries", "Cached price and analytics data"),
            ("agent_runs", "metadata", "Agent execution tracking"),
            ("agent_ideas", "metadata", "Investment ideas generated by agents"),
            ("agent_tool_calls", "metadata", "Tool calls made during agent execution"),
            ("validation_results", "metadata", "Idea validation results"),
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

        logger.debug("Populated table_registry with 8 entries")
