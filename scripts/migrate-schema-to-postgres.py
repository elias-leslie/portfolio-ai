#!/usr/bin/env python3
"""PostgreSQL schema migration script - converts PostgreSQL schema to PostgreSQL.

This script creates all 19 tables from the PostgreSQL schema in PostgreSQL with:
- Type conversions (TIMESTAMP → TIMESTAMPTZ, JSON → JSONB, etc.)
- Foreign key constraints with CASCADE DELETE
- Performance indexes
- Transaction safety with rollback on error
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as PgConnection

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def connect_to_postgres() -> PgConnection:
    """Connect to PostgreSQL using DATABASE_URL from environment."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://portfolio_app:$PGPASSWORD@localhost:5432/portfolio_ai",
    )
    try:
        conn = psycopg2.connect(database_url)
        logger.info("Connected to PostgreSQL database")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        sys.exit(1)


def create_config_tables(conn: PgConnection) -> None:
    """Create configuration tables (6 tables)."""
    cur = conn.cursor()

    # source_registry
    cur.execute("""
        CREATE TABLE IF NOT EXISTS source_registry (
            source_id              TEXT PRIMARY KEY,
            display_name           TEXT NOT NULL,
            priority               INTEGER NOT NULL,
            enabled                BOOLEAN DEFAULT true,
            definition             JSONB NOT NULL,
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            updated_at             TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    logger.info("Created table: source_registry")

    # source_credentials
    cur.execute("""
        CREATE TABLE IF NOT EXISTS source_credentials (
            source_id              TEXT NOT NULL,
            field                  TEXT NOT NULL,
            value                  TEXT NOT NULL,
            updated_at             TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (source_id, field)
        )
    """)
    logger.info("Created table: source_credentials")

    # endpoint_catalog
    cur.execute("""
        CREATE TABLE IF NOT EXISTS endpoint_catalog (
            id                     TEXT PRIMARY KEY,
            source_id              TEXT NOT NULL,
            endpoint_key           TEXT NOT NULL,
            target_table           TEXT NOT NULL,
            path_template          TEXT NOT NULL,
            field_mapping          JSONB NOT NULL,
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (source_id) REFERENCES source_registry(source_id) ON DELETE CASCADE
        )
    """)
    logger.info("Created table: endpoint_catalog")

    # portfolio_accounts
    cur.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_accounts (
            id                     TEXT PRIMARY KEY,
            name                   TEXT NOT NULL,
            account_type           TEXT NOT NULL,
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            updated_at             TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    logger.info("Created table: portfolio_accounts")

    # portfolio_positions
    cur.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_positions (
            id                     TEXT PRIMARY KEY,
            account_id             TEXT NOT NULL,
            symbol                 TEXT NOT NULL,
            shares                 DOUBLE PRECISION NOT NULL,
            cost_basis             DOUBLE PRECISION NOT NULL,
            position_type          TEXT NOT NULL,
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            updated_at             TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (account_id) REFERENCES portfolio_accounts(id) ON DELETE CASCADE
        )
    """)
    logger.info("Created table: portfolio_positions")

    # user_preferences
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id                     TEXT PRIMARY KEY,
            risk_tolerance         INTEGER NOT NULL,
            allow_long             BOOLEAN DEFAULT true,
            allow_short            BOOLEAN DEFAULT false,
            allow_options          BOOLEAN DEFAULT false,
            allow_crypto           BOOLEAN DEFAULT false,
            allow_futures          BOOLEAN DEFAULT false,
            max_position_size_pct  DOUBLE PRECISION DEFAULT 10.0,
            watchlist_refresh_minutes INTEGER DEFAULT 5,
            watchlist_auto_expand    BOOLEAN DEFAULT false,
            watchlist_price_weight   DOUBLE PRECISION DEFAULT 50.0,
            watchlist_technical_weight DOUBLE PRECISION DEFAULT 50.0,
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            updated_at             TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    logger.info("Created table: user_preferences")

    cur.close()


def create_timeseries_tables(conn: PgConnection) -> None:
    """Create time-series data tables (4 tables)."""
    cur = conn.cursor()

    # price_cache
    cur.execute("""
        CREATE TABLE IF NOT EXISTS price_cache (
            symbol                 TEXT NOT NULL,
            price                  DOUBLE PRECISION NOT NULL,
            beta                   DOUBLE PRECISION,
            volatility             DOUBLE PRECISION,
            sector                 TEXT,
            cached_at              TIMESTAMPTZ NOT NULL,
            source                 TEXT NOT NULL,
            error                  TEXT,
            PRIMARY KEY (symbol, cached_at)
        )
    """)
    logger.info("Created table: price_cache")

    # day_bars
    cur.execute("""
        CREATE TABLE IF NOT EXISTS day_bars (
            ticker                 TEXT NOT NULL,
            date                   DATE NOT NULL,
            open                   DOUBLE PRECISION NOT NULL,
            high                   DOUBLE PRECISION NOT NULL,
            low                    DOUBLE PRECISION NOT NULL,
            close                  DOUBLE PRECISION NOT NULL,
            volume                 BIGINT NOT NULL,
            vwap                   DOUBLE PRECISION,
            source                 TEXT NOT NULL,
            ingest_run_id          TEXT,
            PRIMARY KEY (ticker, date)
        )
    """)
    logger.info("Created table: day_bars")

    # minute_bars
    cur.execute("""
        CREATE TABLE IF NOT EXISTS minute_bars (
            ticker                 TEXT NOT NULL,
            ts_utc                 TIMESTAMPTZ NOT NULL,
            open                   DOUBLE PRECISION NOT NULL,
            high                   DOUBLE PRECISION NOT NULL,
            low                    DOUBLE PRECISION NOT NULL,
            close                  DOUBLE PRECISION NOT NULL,
            volume                 BIGINT NOT NULL,
            vwap                   DOUBLE PRECISION,
            source                 TEXT NOT NULL,
            PRIMARY KEY (ticker, ts_utc)
        )
    """)
    logger.info("Created table: minute_bars")

    # technical_indicators
    cur.execute("""
        CREATE TABLE IF NOT EXISTS technical_indicators (
            ticker                 TEXT NOT NULL,
            date                   DATE NOT NULL,
            rsi_14                 DOUBLE PRECISION,
            macd                   DOUBLE PRECISION,
            macd_signal            DOUBLE PRECISION,
            macd_histogram         DOUBLE PRECISION,
            bb_upper               DOUBLE PRECISION,
            bb_middle              DOUBLE PRECISION,
            bb_lower               DOUBLE PRECISION,
            sma_20                 DOUBLE PRECISION,
            sma_50                 DOUBLE PRECISION,
            sma_200                DOUBLE PRECISION,
            ema_20                 DOUBLE PRECISION,
            ema_50                 DOUBLE PRECISION,
            ema_200                DOUBLE PRECISION,
            atr_14                 DOUBLE PRECISION,
            stoch_k                DOUBLE PRECISION,
            stoch_d                DOUBLE PRECISION,
            calculated_at          TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (ticker, date)
        )
    """)
    logger.info("Created table: technical_indicators")

    cur.close()


def create_watchlist_tables(conn: PgConnection) -> None:
    """Create watchlist and reference tables (3 tables)."""
    cur = conn.cursor()

    # reference_cache
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reference_cache (
            ticker                 TEXT NOT NULL,
            as_of_date             DATE NOT NULL,
            payload                JSONB NOT NULL,
            source                 TEXT NOT NULL,
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (ticker, as_of_date, source)
        )
    """)
    logger.info("Created table: reference_cache")

    # watchlist_items
    cur.execute("""
        CREATE TABLE IF NOT EXISTS watchlist_items (
            id                     TEXT PRIMARY KEY,
            account_id             TEXT NOT NULL,
            symbol                 TEXT NOT NULL,
            metadata               JSONB,
            note                   TEXT,
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            updated_at             TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (account_id, symbol),
            FOREIGN KEY (account_id) REFERENCES portfolio_accounts(id) ON DELETE CASCADE
        )
    """)
    logger.info("Created table: watchlist_items")

    # watchlist_snapshots
    cur.execute("""
        CREATE TABLE IF NOT EXISTS watchlist_snapshots (
            item_id                TEXT NOT NULL,
            fetched_at             TIMESTAMPTZ NOT NULL,
            price                  DOUBLE PRECISION,
            change_pct             DOUBLE PRECISION,
            beta                   DOUBLE PRECISION,
            volatility             DOUBLE PRECISION,
            news_score             DOUBLE PRECISION,
            technical_score        DOUBLE PRECISION,
            fundamental_score      DOUBLE PRECISION,
            ai_score               DOUBLE PRECISION,
            ai_confidence          DOUBLE PRECISION,
            sector_score           DOUBLE PRECISION,
            competitor_score       DOUBLE PRECISION,
            overall_score          DOUBLE PRECISION,
            raw_metrics            JSONB,
            PRIMARY KEY (item_id, fetched_at),
            FOREIGN KEY (item_id) REFERENCES watchlist_items(id) ON DELETE CASCADE
        )
    """)
    logger.info("Created table: watchlist_snapshots")

    cur.close()


def create_metadata_tables(conn: PgConnection) -> None:
    """Create metadata and tracking tables (6 tables)."""
    cur = conn.cursor()

    # agent_runs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_runs (
            id                     TEXT PRIMARY KEY,
            agent_type             TEXT NOT NULL,
            started_at             TIMESTAMPTZ NOT NULL,
            completed_at           TIMESTAMPTZ,
            status                 TEXT NOT NULL,
            num_ideas              INTEGER DEFAULT 0,
            cost_usd               DOUBLE PRECISION DEFAULT 0.0,
            error_message          TEXT,
            metadata               JSONB,
            celery_task_id         TEXT
        )
    """)
    logger.info("Created table: agent_runs")

    # agent_ideas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_ideas (
            id                     TEXT PRIMARY KEY,
            agent_run_id           TEXT NOT NULL,
            idea_type              TEXT NOT NULL,
            title                  TEXT NOT NULL,
            thesis                 TEXT NOT NULL,
            action                 TEXT NOT NULL,
            confidence_score       DOUBLE PRECISION NOT NULL,
            risk_level             TEXT NOT NULL,
            reward_estimate        TEXT,
            portfolio_impact       TEXT,
            data_needed            TEXT,
            risks                  TEXT,
            status                 TEXT DEFAULT 'pending',
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            updated_at             TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
        )
    """)
    logger.info("Created table: agent_ideas")

    # agent_tool_calls
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_tool_calls (
            id                     TEXT PRIMARY KEY,
            agent_run_id           TEXT NOT NULL,
            tool_name              TEXT NOT NULL,
            parameters             JSONB NOT NULL,
            response_summary       TEXT,
            duration_ms            INTEGER,
            called_at              TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (agent_run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
        )
    """)
    logger.info("Created table: agent_tool_calls")

    # validation_results
    cur.execute("""
        CREATE TABLE IF NOT EXISTS validation_results (
            id                     TEXT PRIMARY KEY,
            idea_id                TEXT NOT NULL,
            validation_type        TEXT NOT NULL,
            passed                 BOOLEAN NOT NULL,
            details                TEXT,
            validated_at           TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (idea_id) REFERENCES agent_ideas(id) ON DELETE CASCADE
        )
    """)
    logger.info("Created table: validation_results")

    # source_performance
    cur.execute("""
        CREATE TABLE IF NOT EXISTS source_performance (
            source_name            TEXT PRIMARY KEY,
            success_count          INTEGER DEFAULT 0,
            failure_count          INTEGER DEFAULT 0,
            total_latency_ms       BIGINT DEFAULT 0,
            rate_limit_hits        INTEGER DEFAULT 0,
            last_success_at        TIMESTAMPTZ
        )
    """)
    logger.info("Created table: source_performance")

    # idea_outcomes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS idea_outcomes (
            idea_id                TEXT NOT NULL PRIMARY KEY,
            agent_run_id           TEXT NOT NULL,
            ticker                 TEXT NOT NULL,
            idea_type              TEXT NOT NULL,
            entry_price            DOUBLE PRECISION,
            entry_date             DATE,
            target_price           DOUBLE PRECISION,
            stop_loss_price        DOUBLE PRECISION,
            current_price          DOUBLE PRECISION,
            current_return_pct     DOUBLE PRECISION,
            status                 TEXT NOT NULL,
            exit_price             DOUBLE PRECISION,
            exit_date              DATE,
            exit_reason            TEXT,
            realized_return_pct    DOUBLE PRECISION,
            holding_days           INTEGER,
            max_favorable_pct      DOUBLE PRECISION,
            max_adverse_pct        DOUBLE PRECISION,
            created_at             TIMESTAMPTZ NOT NULL,
            updated_at             TIMESTAMPTZ NOT NULL,
            FOREIGN KEY (idea_id) REFERENCES agent_ideas(id) ON DELETE CASCADE
        )
    """)
    logger.info("Created table: idea_outcomes")

    # table_registry
    cur.execute("""
        CREATE TABLE IF NOT EXISTS table_registry (
            table_name             TEXT PRIMARY KEY,
            table_type             TEXT,
            description            TEXT,
            row_count              BIGINT DEFAULT 0,
            last_written           TIMESTAMPTZ,
            created_at             TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    logger.info("Created table: table_registry")

    cur.close()


def create_indexes(conn: PgConnection) -> None:
    """Create performance indexes."""
    cur = conn.cursor()

    indexes = [
        ("idx_source_priority", "source_registry", "(priority, enabled)"),
        ("idx_endpoint_source", "endpoint_catalog", "(source_id)"),
        ("idx_endpoint_target", "endpoint_catalog", "(target_table)"),
        ("idx_day_bars_ticker", "day_bars", "(ticker)"),
        ("idx_indicators_ticker", "technical_indicators", "(ticker, date)"),
        ("idx_reference_cache_ticker", "reference_cache", "(ticker, as_of_date)"),
        ("idx_watchlist_items_account", "watchlist_items", "(account_id, symbol)"),
        ("idx_watchlist_snapshots_item", "watchlist_snapshots", "(item_id, fetched_at DESC)"),
        ("idx_outcomes_status", "idea_outcomes", "(status)"),
        ("idx_price_cache_symbol", "price_cache", "(symbol, cached_at DESC)"),
    ]

    for idx_name, table_name, columns in indexes:
        try:
            cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name} {columns}")
            logger.info(f"Created index: {idx_name}")
        except Exception as e:
            logger.warning(f"Index {idx_name} creation failed (may already exist): {e}")

    cur.close()


def main() -> None:
    """Execute PostgreSQL schema migration."""
    logger.info("Starting PostgreSQL schema migration...")

    conn = connect_to_postgres()

    try:
        # Create tables in dependency order
        logger.info("Creating config tables...")
        create_config_tables(conn)

        logger.info("Creating timeseries tables...")
        create_timeseries_tables(conn)

        logger.info("Creating watchlist tables...")
        create_watchlist_tables(conn)

        logger.info("Creating metadata tables...")
        create_metadata_tables(conn)

        logger.info("Creating indexes...")
        create_indexes(conn)

        # Commit transaction
        conn.commit()
        logger.info("✅ Schema migration completed successfully!")
        logger.info("19 tables created with foreign keys and indexes")

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Schema migration failed, rolled back: {e}")
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
