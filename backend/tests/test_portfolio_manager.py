"""Unit tests for PortfolioManager."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.portfolio.manager import PortfolioManager
from app.storage import DuckDBStorage


@pytest.fixture
def storage() -> DuckDBStorage:
    """Create a DuckDBStorage instance with a temporary database."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.duckdb"

    # Create fresh storage instance (bypass singleton)
    from app.storage.connection import ConnectionManager
    from app.storage.ingestion import IngestionManager
    from app.storage.metadata import MetadataManager
    from app.storage.queries import QueryManager
    from app.storage.schema import SchemaManager

    storage_inst = DuckDBStorage.__new__(DuckDBStorage)
    storage_inst.connection_mgr = ConnectionManager(db_path=db_path)
    storage_inst.schema_mgr = SchemaManager(storage_inst.connection_mgr)
    storage_inst.metadata_mgr = MetadataManager(storage_inst.connection_mgr)
    storage_inst.ingestion_mgr = IngestionManager(
        storage_inst.connection_mgr, storage_inst.metadata_mgr
    )
    storage_inst.query_mgr = QueryManager(storage_inst.connection_mgr)
    storage_inst.schema_mgr.ensure_schema()

    yield storage_inst

    # Cleanup
    if db_path.exists():
        db_path.unlink()
    Path(temp_dir).rmdir()


@pytest.fixture
def portfolio_mgr(storage: DuckDBStorage) -> PortfolioManager:
    """Create a PortfolioManager instance."""
    return PortfolioManager(storage)


def test_add_account(portfolio_mgr: PortfolioManager) -> None:
    """Test adding a new account."""
    account = portfolio_mgr.add_account("My IRA", "IRA")

    assert account.id is not None
    assert account.name == "My IRA"
    assert account.account_type == "IRA"
    assert account.created_at is not None


def test_get_accounts_empty(portfolio_mgr: PortfolioManager) -> None:
    """Test getting accounts when none exist."""
    accounts = portfolio_mgr.get_accounts()
    assert accounts == []


def test_get_accounts(portfolio_mgr: PortfolioManager) -> None:
    """Test getting all accounts."""
    account1 = portfolio_mgr.add_account("IRA", "IRA")
    account2 = portfolio_mgr.add_account("Taxable", "Taxable")

    accounts = portfolio_mgr.get_accounts()

    assert len(accounts) == 2
    assert accounts[0].id == account1.id
    assert accounts[1].id == account2.id


def test_add_position(portfolio_mgr: PortfolioManager) -> None:
    """Test adding a new position."""
    account = portfolio_mgr.add_account("Test Account", "Taxable")

    position = portfolio_mgr.add_position(
        account_id=account.id,
        symbol="AAPL",
        shares=100.0,
        cost_basis=150.0,
        position_type="long",
    )

    assert position.id is not None
    assert position.account_id == account.id
    assert position.symbol == "AAPL"
    assert position.shares == 100.0
    assert position.cost_basis == 150.0
    assert position.position_type == "long"


def test_add_position_uppercase_symbol(portfolio_mgr: PortfolioManager) -> None:
    """Test that symbols are converted to uppercase."""
    account = portfolio_mgr.add_account("Test Account", "Taxable")

    position = portfolio_mgr.add_position(
        account_id=account.id,
        symbol="aapl",
        shares=100.0,
        cost_basis=150.0,
    )

    assert position.symbol == "AAPL"


def test_get_positions_empty(portfolio_mgr: PortfolioManager) -> None:
    """Test getting positions when none exist."""
    positions = portfolio_mgr.get_positions()
    assert positions == []


def test_get_positions(portfolio_mgr: PortfolioManager) -> None:
    """Test getting all positions."""
    account = portfolio_mgr.add_account("Test Account", "Taxable")

    pos1 = portfolio_mgr.add_position(account.id, "AAPL", 100.0, 150.0)
    pos2 = portfolio_mgr.add_position(account.id, "GOOGL", 50.0, 2000.0)

    positions = portfolio_mgr.get_positions()

    assert len(positions) == 2
    # Positions should be ordered by symbol
    assert positions[0].symbol == "AAPL"
    assert positions[1].symbol == "GOOGL"


def test_get_positions_by_account(portfolio_mgr: PortfolioManager) -> None:
    """Test filtering positions by account."""
    account1 = portfolio_mgr.add_account("Account 1", "IRA")
    account2 = portfolio_mgr.add_account("Account 2", "Taxable")

    portfolio_mgr.add_position(account1.id, "AAPL", 100.0, 150.0)
    portfolio_mgr.add_position(account2.id, "GOOGL", 50.0, 2000.0)

    positions_acc1 = portfolio_mgr.get_positions(account_id=account1.id)
    positions_acc2 = portfolio_mgr.get_positions(account_id=account2.id)

    assert len(positions_acc1) == 1
    assert positions_acc1[0].symbol == "AAPL"

    assert len(positions_acc2) == 1
    assert positions_acc2[0].symbol == "GOOGL"


def test_update_position_shares(portfolio_mgr: PortfolioManager) -> None:
    """Test updating position shares."""
    account = portfolio_mgr.add_account("Test Account", "Taxable")
    position = portfolio_mgr.add_position(account.id, "AAPL", 100.0, 150.0)

    updated = portfolio_mgr.update_position(position.id, shares=200.0)

    assert updated.shares == 200.0
    assert updated.cost_basis == 150.0


def test_update_position_cost_basis(portfolio_mgr: PortfolioManager) -> None:
    """Test updating position cost basis."""
    account = portfolio_mgr.add_account("Test Account", "Taxable")
    position = portfolio_mgr.add_position(account.id, "AAPL", 100.0, 150.0)

    updated = portfolio_mgr.update_position(position.id, cost_basis=160.0)

    assert updated.shares == 100.0
    assert updated.cost_basis == 160.0


def test_update_position_both(portfolio_mgr: PortfolioManager) -> None:
    """Test updating both shares and cost basis."""
    account = portfolio_mgr.add_account("Test Account", "Taxable")
    position = portfolio_mgr.add_position(account.id, "AAPL", 100.0, 150.0)

    updated = portfolio_mgr.update_position(position.id, shares=200.0, cost_basis=160.0)

    assert updated.shares == 200.0
    assert updated.cost_basis == 160.0


def test_update_position_not_found(portfolio_mgr: PortfolioManager) -> None:
    """Test updating a non-existent position raises ValueError."""
    with pytest.raises(ValueError, match="Position .* not found"):
        portfolio_mgr.update_position("nonexistent-id", shares=100.0)


def test_delete_position(portfolio_mgr: PortfolioManager) -> None:
    """Test deleting a position."""
    account = portfolio_mgr.add_account("Test Account", "Taxable")
    position = portfolio_mgr.add_position(account.id, "AAPL", 100.0, 150.0)

    portfolio_mgr.delete_position(position.id)

    positions = portfolio_mgr.get_positions()
    assert len(positions) == 0


def test_delete_position_idempotent(portfolio_mgr: PortfolioManager) -> None:
    """Test that deleting a non-existent position doesn't raise an error."""
    # Should not raise
    portfolio_mgr.delete_position("nonexistent-id")
