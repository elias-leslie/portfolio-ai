"""Unit tests for PostgreSQL schema creation."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.storage.connection import ConnectionManager
from app.storage.queries import QueryManager
from app.storage.schema import SchemaManager


def get_table_columns(conn: Any, table_name: str) -> dict[str, str]:
    """Get table columns using PostgreSQL information_schema.

    Args:
        conn: Database connection
        table_name: Name of the table

    Returns:
        Dictionary mapping column names to data types
    """
    result = conn.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = ?
        ORDER BY ordinal_position
        """,
        [table_name],
    ).fetchall()
    return {row[0]: row[1] for row in result}


@pytest.fixture
def temp_db_path() -> Generator[Path]:
    """Create a temporary database path for testing."""
    # Create temp directory and path (don't create the file)
    temp_dir = tempfile.mkdtemp()
    path = Path(temp_dir) / "test.db"
    yield path
    # Cleanup
    if path.exists():
        path.unlink()
    Path(temp_dir).rmdir()


@pytest.fixture
def connection_mgr(temp_db_path: Path) -> ConnectionManager:
    """Create a ConnectionManager with a temporary database."""
    return ConnectionManager()


@pytest.fixture
def schema_mgr(connection_mgr: ConnectionManager) -> SchemaManager:
    """Create a SchemaManager instance."""
    return SchemaManager(connection_mgr)


@pytest.fixture
def query_mgr(connection_mgr: ConnectionManager) -> QueryManager:
    """Create a QueryManager instance."""
    return QueryManager(connection_mgr)


def test_schema_manager_initialization(schema_mgr: SchemaManager) -> None:
    """Test that SchemaManager can be initialized."""
    assert schema_mgr is not None
    assert schema_mgr.connection_mgr is not None


def test_ensure_schema_creates_all_tables(schema_mgr: SchemaManager) -> None:
    """Test that ensure_schema creates all expected tables."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        # PostgreSQL-compatible query to list tables
        tables = conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """).fetchall()
        table_names = {str(t[0]) for t in tables}

        expected_tables = {
            "source_registry",
            "source_credentials",
            "endpoint_catalog",
            "portfolio_accounts",
            "portfolio_positions",
            "automation_preferences",
            "user_preferences",
            "reference_cache",
            "price_cache",
            "day_bars",
            "technical_indicators",
            "watchlist_items",
            "watchlist_snapshots",
            "agent_runs",
            "agent_tool_calls",
            "cross_validation_results",
            "source_performance",
            "idea_outcomes",
            "table_registry",
        }

        missing = expected_tables - table_names
        assert not missing, f"Missing tables: {missing}"


def test_portfolio_accounts_table_structure(schema_mgr: SchemaManager) -> None:
    """Test that portfolio_accounts table has the correct structure."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        columns = get_table_columns(conn, "portfolio_accounts")

        assert "id" in columns
        assert "name" in columns
        assert "account_type" in columns
        assert "household_account_id" in columns
        assert "created_at" in columns
        assert "updated_at" in columns


def test_portfolio_positions_table_structure(schema_mgr: SchemaManager) -> None:
    """Test that portfolio_positions table has the correct structure."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        columns = get_table_columns(conn, "portfolio_positions")

        assert "id" in columns
        assert "account_id" in columns
        assert "symbol" in columns
        assert "shares" in columns
        assert "cost_basis" in columns
        assert "position_type" in columns


def test_user_preferences_table_structure(schema_mgr: SchemaManager) -> None:
    """Test that user_preferences table has the correct structure."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        columns = get_table_columns(conn, "user_preferences")

        assert "id" in columns
        assert "risk_tolerance" in columns
        assert "allow_long" in columns
        assert "allow_short" in columns
        assert "max_position_size_pct" in columns
        assert "watchlist_refresh_minutes" in columns
        assert "watchlist_auto_expand" in columns
        assert "watchlist_price_weight" in columns
        assert "watchlist_technical_weight" in columns


def test_user_preferences_defaults(schema_mgr: SchemaManager) -> None:
    """Ensure new watchlist preference columns receive defaults."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        conn.execute(
            "INSERT INTO user_preferences (id, risk_tolerance) VALUES (?, ?)",
            ["user-1", 5],
        )
        row = conn.execute(
            """
            SELECT
                watchlist_refresh_minutes,
                watchlist_auto_expand,
                watchlist_price_weight,
                watchlist_technical_weight
            FROM user_preferences
            WHERE id = ?
            """,
            ["user-1"],
        ).fetchone()

    assert row is not None
    assert row[0] == 5
    assert row[1] is False
    assert pytest.approx(row[2], rel=1e-6) == 50.0
    assert pytest.approx(row[3], rel=1e-6) == 50.0


def test_price_cache_table_structure(schema_mgr: SchemaManager) -> None:
    """Test that price_cache table has the correct structure."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        columns = get_table_columns(conn, "price_cache")

        assert "symbol" in columns
        assert "price" in columns
        assert "beta" in columns
        assert "volatility" in columns
        assert "sector" in columns
        assert "cached_at" in columns
        assert "source" in columns


def test_agent_runs_table_structure(schema_mgr: SchemaManager) -> None:
    """Test that agent_runs table has the correct structure."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        columns = get_table_columns(conn, "agent_runs")

        assert "id" in columns
        assert "agent_type" in columns
        assert "started_at" in columns
        assert "completed_at" in columns
        assert "status" in columns
        assert "num_ideas" in columns
        assert "cost_usd" in columns


def test_table_registry_populated(schema_mgr: SchemaManager) -> None:
    """Test that table_registry is populated with metadata."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM table_registry").fetchone()
        assert result is not None
        assert isinstance(result[0], int)
        assert result[0] >= 19, "table_registry should have at least 19 entries"


def test_schema_idempotent(schema_mgr: SchemaManager) -> None:
    """Test that calling ensure_schema multiple times is safe."""
    schema_mgr.ensure_schema()
    schema_mgr.ensure_schema()  # Should not raise

    with schema_mgr.connection_mgr.connection() as conn:
        # PostgreSQL-compatible query to list tables
        tables = conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """).fetchall()
        table_names = {str(t[0]) for t in tables}

        # Should still have all tables
        assert "portfolio_accounts" in table_names
        assert "agent_runs" in table_names


def test_insert_into_portfolio_accounts(schema_mgr: SchemaManager) -> None:
    """Test that we can insert data into portfolio_accounts."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        conn.execute(
            """
            INSERT INTO portfolio_accounts (id, name, account_type)
            VALUES (?, ?, ?)
            """,
            ["test-account-1", "Test Account", "Taxable"],
        )

        result = conn.execute("SELECT COUNT(*) FROM portfolio_accounts").fetchone()
        assert result is not None
        assert result[0] == 1


def test_watchlist_tables_structure(schema_mgr: SchemaManager) -> None:
    """Ensure watchlist tables have required columns."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        items_columns = get_table_columns(conn, "watchlist_items")
        snapshots_columns = get_table_columns(conn, "watchlist_snapshots")
        reference_columns = get_table_columns(conn, "reference_cache")

        assert {"id", "symbol", "metadata", "note"}.issubset(items_columns)
        assert {
            "item_id",
            "fetched_at",
            "price",
            "news_score",
            "overall_score",
            "raw_metrics",
        }.issubset(snapshots_columns)
        assert {"symbol", "as_of_date", "payload", "source"}.issubset(reference_columns)


def test_watchlist_snapshot_history_and_upsert(
    schema_mgr: SchemaManager, query_mgr: QueryManager
) -> None:
    """Ensure snapshot upserts and history retrieval behave correctly."""
    schema_mgr.ensure_schema()

    now = datetime.now(UTC)
    earlier = now - timedelta(minutes=5)

    with schema_mgr.connection_mgr.connection() as conn:
        conn.execute(
            """
            INSERT INTO symbols (symbol, company_name)
            VALUES (?, ?)
            ON CONFLICT (symbol) DO NOTHING
            """,
            ["AAPL", "Apple Inc."],
        )
        conn.execute(
            """
            INSERT INTO watchlist_items (id, symbol, metadata)
            VALUES (?, ?, ?)
            """,
            ["item-1", "AAPL", "{}"],
        )
        conn.commit()  # Commit the inserts

    # Initial insert
    query_mgr.upsert_watchlist_snapshot(
        "item-1",
        earlier,
        price=182.50,
        technical_score=72.3,
        overall_score=75.0,
        raw_metrics={"rsi": 58.2},
    )

    # Update same timestamp with new data
    query_mgr.upsert_watchlist_snapshot(
        "item-1",
        earlier,
        price=183.10,
        technical_score=73.0,
        overall_score=76.5,
        raw_metrics={"rsi": 59.0},
    )

    # Insert a newer snapshot
    query_mgr.upsert_watchlist_snapshot(
        "item-1",
        now,
        price=184.25,
        change_pct=1.2,
        technical_score=74.5,
        overall_score=78.0,
    )

    history = query_mgr.get_watchlist_snapshot_history("item-1", limit=5)
    assert history.height == 2

    sorted_history = history.sort("fetched_at")
    latest_price = sorted_history["price"].to_list()[-1]
    assert latest_price == 184.25

    earliest_raw_metrics = sorted_history["raw_metrics"].to_list()[0]
    # PostgreSQL JSONB returns dict, not JSON string
    assert earliest_raw_metrics["rsi"] == 59.0 or '"rsi": 59.0' in str(earliest_raw_metrics)


def test_migrations_applied(schema_mgr: SchemaManager) -> None:
    """Verify that the database is at the repository's single Alembic head."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        applied_heads = {
            str(row[0]) for row in conn.execute("SELECT version_num FROM alembic_version").fetchall()
        }

    alembic_config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    script = ScriptDirectory.from_config(alembic_config)
    repository_heads = set(script.get_heads())

    assert len(repository_heads) == 1, "Migration history must have exactly one deployable head"
    assert applied_heads == repository_heads
