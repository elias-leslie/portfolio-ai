"""Unit tests for DuckDB schema creation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.storage.connection import ConnectionManager
from app.storage.schema import SchemaManager


@pytest.fixture
def temp_db_path() -> Path:
    """Create a temporary database path for testing."""
    # Create temp directory and path (don't create the file)
    temp_dir = tempfile.mkdtemp()
    path = Path(temp_dir) / "test.duckdb"
    yield path
    # Cleanup
    if path.exists():
        path.unlink()
    Path(temp_dir).rmdir()


@pytest.fixture
def connection_mgr(temp_db_path: Path) -> ConnectionManager:
    """Create a ConnectionManager with a temporary database."""
    return ConnectionManager(db_path=temp_db_path)


@pytest.fixture
def schema_mgr(connection_mgr: ConnectionManager) -> SchemaManager:
    """Create a SchemaManager instance."""
    return SchemaManager(connection_mgr)


def test_schema_manager_initialization(schema_mgr: SchemaManager) -> None:
    """Test that SchemaManager can be initialized."""
    assert schema_mgr is not None
    assert schema_mgr.connection_mgr is not None


def test_ensure_schema_creates_all_tables(schema_mgr: SchemaManager) -> None:
    """Test that ensure_schema creates all 8 expected tables."""
    schema_mgr.ensure_schema()

    # Verify all tables exist
    with schema_mgr.connection_mgr.connection() as conn:
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = {t[0] for t in tables}

        expected_tables = {
            "portfolio_accounts",
            "portfolio_positions",
            "user_preferences",
            "price_cache",
            "agent_runs",
            "agent_ideas",
            "agent_tool_calls",
            "validation_results",
            "table_registry",
        }

        assert expected_tables.issubset(
            table_names
        ), f"Missing tables: {expected_tables - table_names}"


def test_portfolio_accounts_table_structure(schema_mgr: SchemaManager) -> None:
    """Test that portfolio_accounts table has the correct structure."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        result = conn.execute("DESCRIBE portfolio_accounts").fetchall()
        columns = {row[0]: row[1] for row in result}

        assert "id" in columns
        assert "name" in columns
        assert "account_type" in columns
        assert "created_at" in columns
        assert "updated_at" in columns


def test_portfolio_positions_table_structure(schema_mgr: SchemaManager) -> None:
    """Test that portfolio_positions table has the correct structure."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        result = conn.execute("DESCRIBE portfolio_positions").fetchall()
        columns = {row[0]: row[1] for row in result}

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
        result = conn.execute("DESCRIBE user_preferences").fetchall()
        columns = {row[0]: row[1] for row in result}

        assert "id" in columns
        assert "risk_tolerance" in columns
        assert "allow_long" in columns
        assert "allow_short" in columns
        assert "max_position_size_pct" in columns


def test_price_cache_table_structure(schema_mgr: SchemaManager) -> None:
    """Test that price_cache table has the correct structure."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        result = conn.execute("DESCRIBE price_cache").fetchall()
        columns = {row[0]: row[1] for row in result}

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
        result = conn.execute("DESCRIBE agent_runs").fetchall()
        columns = {row[0]: row[1] for row in result}

        assert "id" in columns
        assert "agent_type" in columns
        assert "started_at" in columns
        assert "completed_at" in columns
        assert "status" in columns
        assert "num_ideas" in columns
        assert "cost_usd" in columns


def test_agent_ideas_table_structure(schema_mgr: SchemaManager) -> None:
    """Test that agent_ideas table has the correct structure."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        result = conn.execute("DESCRIBE agent_ideas").fetchall()
        columns = {row[0]: row[1] for row in result}

        assert "id" in columns
        assert "agent_run_id" in columns
        assert "idea_type" in columns
        assert "title" in columns
        assert "thesis" in columns
        assert "action" in columns
        assert "confidence_score" in columns
        assert "risk_level" in columns


def test_table_registry_populated(schema_mgr: SchemaManager) -> None:
    """Test that table_registry is populated with metadata."""
    schema_mgr.ensure_schema()

    with schema_mgr.connection_mgr.connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM table_registry").fetchone()
        assert result[0] >= 8, "table_registry should have at least 8 entries"


def test_schema_idempotent(schema_mgr: SchemaManager) -> None:
    """Test that calling ensure_schema multiple times is safe."""
    schema_mgr.ensure_schema()
    schema_mgr.ensure_schema()  # Should not raise

    with schema_mgr.connection_mgr.connection() as conn:
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = {t[0] for t in tables}

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
        assert result[0] == 1
