"""DuckDB schema management for portfolio-ai.

This module manages database schema creation and table registry metadata.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import duckdb

from .migrations import MigrationManager

if TYPE_CHECKING:
    from .connection import ConnectionManager

logger = logging.getLogger(__name__)

# Schema version migrations (version, SQL) - Deprecated, use migrations/ directory
MIGRATIONS: list[tuple[str, str]] = []


class SchemaManager:
    """Manages DuckDB schema creation for portfolio-ai.

    Handles schema creation for all 19 tables and table registry metadata.
    """

    def __init__(self, connection_mgr: ConnectionManager) -> None:
        """Initialize schema manager.

        Args:
            connection_mgr: ConnectionManager instance for database access.
        """
        self.connection_mgr = connection_mgr

    def ensure_schema(self) -> None:
        """Create all domain tables and apply pending migrations."""
        migration_mgr = MigrationManager(self.connection_mgr)

        with self.connection_mgr.connection() as conn:
            try:
                conn.execute("BEGIN TRANSACTION")

                self._create_config_tables(conn)
                self._create_timeseries_tables(conn)
                self._create_watchlist_tables(conn)
                self._create_metadata_tables(conn)

                # Apply legacy migrations and populate registry
                self._apply_migrations(conn)
                self._populate_registry_metadata(conn)

                conn.execute("COMMIT")
                logger.info("Schema initialization completed successfully with watchlist tables")

            except Exception as e:
                conn.execute("ROLLBACK")
                logger.error(f"Schema initialization failed, rolled back: {e}")
                raise

        # Apply SQL file migrations after base schema exists
        migration_mgr.apply_migrations()

    def _create_config_tables(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create configuration tables (6 tables)."""
        # source_registry - Data source definitions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_registry (
                source_id              TEXT PRIMARY KEY,
                display_name           TEXT NOT NULL,
                priority               INTEGER NOT NULL,
                enabled                BOOLEAN DEFAULT true,
                definition             JSON NOT NULL,
                created_at             TIMESTAMP DEFAULT now(),
                updated_at             TIMESTAMP DEFAULT now()
            )
        """)

        # source_credentials - API keys and secrets
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_credentials (
                source_id              TEXT NOT NULL,
                field                  TEXT NOT NULL,
                value                  TEXT NOT NULL,
                updated_at             TIMESTAMP DEFAULT now(),
                PRIMARY KEY (source_id, field)
            )
        """)

        # endpoint_catalog - API endpoint definitions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS endpoint_catalog (
                id                     TEXT PRIMARY KEY,
                source_id              TEXT NOT NULL,
                endpoint_key           TEXT NOT NULL,
                target_table           TEXT NOT NULL,
                path_template          TEXT NOT NULL,
                field_mapping          JSON NOT NULL,
                created_at             TIMESTAMP DEFAULT now(),
                FOREIGN KEY (source_id) REFERENCES source_registry(source_id)
            )
        """)

        # Indexes for efficient lookups
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_source_priority ON source_registry(priority, enabled)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_endpoint_source ON endpoint_catalog(source_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_endpoint_target ON endpoint_catalog(target_table)"
        )

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
                watchlist_refresh_minutes INTEGER DEFAULT 5,
                watchlist_auto_expand    BOOLEAN DEFAULT false,
                watchlist_price_weight   DOUBLE DEFAULT 50.0,
                watchlist_technical_weight DOUBLE DEFAULT 50.0,
                created_at             TIMESTAMP DEFAULT now(),
                updated_at             TIMESTAMP DEFAULT now()
            )
        """)

    def _create_timeseries_tables(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create time-series data tables (4 tables)."""
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

        # day_bars (historical OHLCV data)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS day_bars (
                ticker                 TEXT NOT NULL,
                date                   DATE NOT NULL,
                open                   DOUBLE NOT NULL,
                high                   DOUBLE NOT NULL,
                low                    DOUBLE NOT NULL,
                close                  DOUBLE NOT NULL,
                volume                 BIGINT NOT NULL,
                vwap                   DOUBLE,
                source                 TEXT NOT NULL,
                ingest_run_id          TEXT,
                PRIMARY KEY (ticker, date)
            )
        """)

        # Create index for day_bars ticker lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_day_bars_ticker ON day_bars(ticker)
        """)

        # minute_bars (intraday data - optional feature)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS minute_bars (
                ticker                 TEXT NOT NULL,
                ts_utc                 TIMESTAMP NOT NULL,
                open                   DOUBLE NOT NULL,
                high                   DOUBLE NOT NULL,
                low                    DOUBLE NOT NULL,
                close                  DOUBLE NOT NULL,
                volume                 BIGINT NOT NULL,
                vwap                   DOUBLE,
                source                 TEXT NOT NULL,
                PRIMARY KEY (ticker, ts_utc)
            )
        """)

        # technical_indicators (cached technical indicator values)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS technical_indicators (
                ticker                 TEXT NOT NULL,
                date                   DATE NOT NULL,
                rsi_14                 DOUBLE,
                macd                   DOUBLE,
                macd_signal            DOUBLE,
                macd_histogram         DOUBLE,
                bb_upper               DOUBLE,
                bb_middle              DOUBLE,
                bb_lower               DOUBLE,
                sma_20                 DOUBLE,
                sma_50                 DOUBLE,
                sma_200                DOUBLE,
                ema_20                 DOUBLE,
                ema_50                 DOUBLE,
                ema_200                DOUBLE,
                atr_14                 DOUBLE,
                stoch_k                DOUBLE,
                stoch_d                DOUBLE,
                calculated_at          TIMESTAMP NOT NULL,
                PRIMARY KEY (ticker, date)
            )
        """)

        # Create index for technical_indicators ticker lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_indicators_ticker ON technical_indicators(ticker, date)
        """)

    def _create_watchlist_tables(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create watchlist and reference tables (3 tables)."""
        # reference_cache stores raw reference data per ticker/source
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reference_cache (
                ticker                 TEXT NOT NULL,
                as_of_date             DATE NOT NULL,
                payload                JSON NOT NULL,
                source                 TEXT NOT NULL,
                created_at             TIMESTAMP DEFAULT now(),
                PRIMARY KEY (ticker, as_of_date, source)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reference_cache_ticker
            ON reference_cache(ticker, as_of_date)
        """)

        # watchlist_items group tickers per account with metadata + notes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_items (
                id                     TEXT PRIMARY KEY,
                account_id             TEXT NOT NULL,
                symbol                 TEXT NOT NULL,
                metadata               JSON,
                note                   TEXT,
                created_at             TIMESTAMP DEFAULT now(),
                updated_at             TIMESTAMP DEFAULT now(),
                UNIQUE (account_id, symbol),
                FOREIGN KEY (account_id) REFERENCES portfolio_accounts(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_watchlist_items_account
            ON watchlist_items(account_id, symbol)
        """)

        # watchlist_snapshots cache scoring outputs over time
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_snapshots (
                item_id                TEXT NOT NULL,
                fetched_at             TIMESTAMP NOT NULL,
                price                  DOUBLE,
                change_pct             DOUBLE,
                beta                   DOUBLE,
                volatility             DOUBLE,
                news_score             DOUBLE,
                technical_score        DOUBLE,
                fundamental_score      DOUBLE,
                ai_score               DOUBLE,
                ai_confidence          DOUBLE,
                sector_score           DOUBLE,
                competitor_score       DOUBLE,
                overall_score          DOUBLE,
                raw_metrics            JSON,
                PRIMARY KEY (item_id, fetched_at),
                FOREIGN KEY (item_id) REFERENCES watchlist_items(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_watchlist_snapshots_item
            ON watchlist_snapshots(item_id, fetched_at)
        """)

    def _create_metadata_tables(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Create metadata and tracking tables (7 tables)."""
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
                metadata               JSON,
                celery_task_id         TEXT
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

        # source_performance (for multi-source failover tracking)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_performance (
                source_name            TEXT PRIMARY KEY,
                success_count          INTEGER DEFAULT 0,
                failure_count          INTEGER DEFAULT 0,
                total_latency_ms       BIGINT DEFAULT 0,
                rate_limit_hits        INTEGER DEFAULT 0,
                last_success_at        TIMESTAMP
            )
        """)

        # idea_outcomes (for paper trading tracking)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS idea_outcomes (
                idea_id                TEXT NOT NULL PRIMARY KEY,
                agent_run_id           TEXT NOT NULL,
                ticker                 TEXT NOT NULL,
                idea_type              TEXT NOT NULL,
                entry_price            DOUBLE,
                entry_date             DATE,
                target_price           DOUBLE,
                stop_loss_price        DOUBLE,
                current_price          DOUBLE,
                current_return_pct     DOUBLE,
                status                 TEXT NOT NULL,
                exit_price             DOUBLE,
                exit_date              DATE,
                exit_reason            TEXT,
                realized_return_pct    DOUBLE,
                holding_days           INTEGER,
                max_favorable_pct      DOUBLE,
                max_adverse_pct        DOUBLE,
                created_at             TIMESTAMP NOT NULL,
                updated_at             TIMESTAMP NOT NULL,
                FOREIGN KEY (idea_id) REFERENCES agent_ideas(id)
            )
        """)

        # Create index for idea_outcomes status lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_outcomes_status ON idea_outcomes(status)
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

    def _apply_migrations(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Apply backward-compatible schema migrations.

        Uses ADD COLUMN IF NOT EXISTS to allow safe re-runs.
        """
        for version, sql in MIGRATIONS:
            try:
                conn.execute(sql)
                logger.debug(f"Applied migration {version}")
            except Exception as e:
                logger.warning(f"Migration {version} failed (may already exist): {e}")

    def _populate_registry_metadata(self, conn: duckdb.DuckDBPyConnection) -> None:
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
            ("minute_bars", "timeseries", "Intraday minute-level OHLCV data"),
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
