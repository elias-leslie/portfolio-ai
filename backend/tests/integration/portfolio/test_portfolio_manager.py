"""Unit tests for PortfolioManager."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.portfolio.manager import PortfolioManager
from app.storage import PortfolioStorage, get_storage


@pytest.fixture
def storage() -> PortfolioStorage:
    """Get the storage instance (uses PostgreSQL test database).

    Test isolation is handled by the clean_database fixture in conftest.py.
    """
    return get_storage()


@pytest.fixture
def portfolio_mgr(storage: PortfolioStorage) -> PortfolioManager:
    """Create a PortfolioManager instance."""
    return PortfolioManager(storage)


def test_add_account(portfolio_mgr: PortfolioManager) -> None:
    """Test adding a new account."""
    account = portfolio_mgr.add_account("My IRA", "IRA")

    assert account.id is not None
    assert account.name == "My IRA"
    assert account.account_type == "IRA"
    assert account.cash_balance == 0.0
    assert account.initial_cash == 0.0
    assert account.created_at is not None


def test_add_paper_account_defaults_to_starting_cash(portfolio_mgr: PortfolioManager) -> None:
    """Paper accounts should preserve their dedicated starting balance."""
    account = portfolio_mgr.add_account("Paper", "paper")

    assert account.cash_balance == 100000.0
    assert account.initial_cash == 100000.0


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


def test_get_accounts_normalizes_household_account_uuid(portfolio_mgr: PortfolioManager) -> None:
    """UUID-backed household links from PostgreSQL should round-trip as strings."""
    account = portfolio_mgr.add_account("IRA", "IRA")
    household_account_id = str(uuid4())

    with portfolio_mgr.storage.connection() as conn:
        conn.execute(
            "UPDATE portfolio_accounts SET household_account_id = %s WHERE id = %s",
            [household_account_id, account.id],
        )

    accounts = portfolio_mgr.get_accounts()

    assert len(accounts) == 1
    assert accounts[0].household_account_id == household_account_id


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

    watchlist_rows = portfolio_mgr.storage.query(
        "SELECT symbol, source FROM watchlist_items WHERE symbol = 'AAPL'"
    )
    assert watchlist_rows.height == 1
    watchlist_row = watchlist_rows.to_dicts()[0]
    assert watchlist_row["symbol"] == "AAPL"
    assert watchlist_row["source"] == "portfolio"


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

    portfolio_mgr.add_position(account.id, "AAPL", 100.0, 150.0)
    portfolio_mgr.add_position(account.id, "GOOGL", 50.0, 2000.0)

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


def test_update_position_symbol_syncs_new_ticker_to_watchlist(
    portfolio_mgr: PortfolioManager,
) -> None:
    """Updating a symbol should sync the replacement ticker into the watchlist."""
    account = portfolio_mgr.add_account("Test Account", "Taxable")
    position = portfolio_mgr.add_position(account.id, "AAPL", 100.0, 150.0)

    updated = portfolio_mgr.update_position(position.id, symbol="msft")

    assert updated.symbol == "MSFT"

    watchlist_rows = portfolio_mgr.storage.query(
        "SELECT symbol, source FROM watchlist_items WHERE symbol = 'MSFT'"
    )
    assert watchlist_rows.height == 1
    watchlist_row = watchlist_rows.to_dicts()[0]
    assert watchlist_row["symbol"] == "MSFT"
    assert watchlist_row["source"] == "portfolio"


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


def test_update_account_cash_balance(portfolio_mgr: PortfolioManager) -> None:
    """Account cash balances should be updateable for live brokerage sync."""
    account = portfolio_mgr.add_account("Brokerage", "Taxable")

    updated = portfolio_mgr.update_account_cash_balance(
        account.id,
        cash_balance=1427.53,
        initial_cash=1427.53,
    )

    assert updated.cash_balance == 1427.53
    assert updated.initial_cash == 1427.53
