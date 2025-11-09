"""Tests for portfolio-watchlist sync functionality."""

from __future__ import annotations

from app.portfolio.manager import PortfolioManager
from app.storage import get_storage


def test_portfolio_ticker_auto_added_to_empty_watchlist() -> None:
    """Test that portfolio ticker is automatically added to an empty watchlist."""
    storage = get_storage()
    manager = PortfolioManager(storage)

    # Clear watchlist
    with storage.connection() as conn:
        conn.execute("DELETE FROM watchlist_items")
        conn.commit()

    # Sync portfolio tickers
    manager.sync_portfolio_to_watchlist(["AAPL", "GOOGL"])

    # Verify tickers added
    df = storage.query("SELECT symbol, source FROM watchlist_items ORDER BY symbol")
    assert df.height == 2
    rows = df.to_dicts()
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["source"] == "portfolio"
    assert rows[1]["symbol"] == "GOOGL"
    assert rows[1]["source"] == "portfolio"


def test_existing_manual_watchlist_ticker_not_modified() -> None:
    """Test that existing manual watchlist ticker is not modified by sync."""
    storage = get_storage()
    manager = PortfolioManager(storage)

    # Clear watchlist and add a manual ticker
    with storage.connection() as conn:
        conn.execute("DELETE FROM watchlist_items")
        conn.execute(
            """
            INSERT INTO watchlist_items (id, symbol, source, note, created_at, updated_at)
            VALUES ('test-1', 'AAPL', 'manual', 'My manual note', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        conn.commit()

    # Sync portfolio tickers (including AAPL)
    manager.sync_portfolio_to_watchlist(["AAPL", "MSFT"])

    # Verify AAPL still has manual source and note
    df = storage.query("SELECT symbol, source, note FROM watchlist_items WHERE symbol = 'AAPL'")
    assert df.height == 1
    row = df.to_dicts()[0]
    assert row["symbol"] == "AAPL"
    assert row["source"] == "manual"
    assert row["note"] == "My manual note"

    # Verify MSFT was added with portfolio source
    df = storage.query("SELECT symbol, source FROM watchlist_items WHERE symbol = 'MSFT'")
    assert df.height == 1
    row = df.to_dicts()[0]
    assert row["symbol"] == "MSFT"
    assert row["source"] == "portfolio"


def test_multiple_portfolio_tickers_synced_correctly() -> None:
    """Test that multiple portfolio tickers are synced correctly."""
    storage = get_storage()
    manager = PortfolioManager(storage)

    # Clear watchlist
    with storage.connection() as conn:
        conn.execute("DELETE FROM watchlist_items")
        conn.commit()

    # Sync multiple portfolio tickers
    tickers = ["AAPL", "GOOGL", "MSFT", "NVDA", "TSLA"]
    manager.sync_portfolio_to_watchlist(tickers)

    # Verify all tickers added
    df = storage.query("SELECT symbol, source FROM watchlist_items ORDER BY symbol")
    assert df.height == 5
    rows = df.to_dicts()
    expected_symbols = sorted(tickers)
    for i, row in enumerate(rows):
        assert row["symbol"] == expected_symbols[i]
        assert row["source"] == "portfolio"


def test_idempotent_calling_twice_no_duplicates() -> None:
    """Test that calling sync twice does not create duplicates."""
    storage = get_storage()
    manager = PortfolioManager(storage)

    # Clear watchlist
    with storage.connection() as conn:
        conn.execute("DELETE FROM watchlist_items")
        conn.commit()

    # Sync portfolio tickers twice
    tickers = ["AAPL", "GOOGL"]
    manager.sync_portfolio_to_watchlist(tickers)
    manager.sync_portfolio_to_watchlist(tickers)

    # Verify no duplicates
    df = storage.query("SELECT symbol FROM watchlist_items ORDER BY symbol")
    assert df.height == 2
    rows = df.to_dicts()
    assert rows[0]["symbol"] == "AAPL"
    assert rows[1]["symbol"] == "GOOGL"


def test_source_column_correctly_set_to_portfolio() -> None:
    """Test that source column is correctly set to 'portfolio' for synced tickers."""
    storage = get_storage()
    manager = PortfolioManager(storage)

    # Clear watchlist
    with storage.connection() as conn:
        conn.execute("DELETE FROM watchlist_items")
        conn.commit()

    # Sync portfolio tickers
    manager.sync_portfolio_to_watchlist(["AAPL"])

    # Verify source is 'portfolio'
    df = storage.query("SELECT source FROM watchlist_items WHERE symbol = 'AAPL'")
    assert df.height == 1
    assert df.to_dicts()[0]["source"] == "portfolio"


def test_empty_tickers_list_no_changes() -> None:
    """Test that syncing empty tickers list makes no changes."""
    storage = get_storage()
    manager = PortfolioManager(storage)

    # Clear watchlist and add a ticker
    with storage.connection() as conn:
        conn.execute("DELETE FROM watchlist_items")
        conn.execute(
            """
            INSERT INTO watchlist_items (id, symbol, source, created_at, updated_at)
            VALUES ('test-1', 'AAPL', 'manual', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        conn.commit()

    # Sync empty list
    manager.sync_portfolio_to_watchlist([])

    # Verify no changes
    df = storage.query("SELECT symbol FROM watchlist_items")
    assert df.height == 1
    assert df.to_dicts()[0]["symbol"] == "AAPL"


def test_lowercase_tickers_converted_to_uppercase() -> None:
    """Test that lowercase tickers are converted to uppercase."""
    storage = get_storage()
    manager = PortfolioManager(storage)

    # Clear watchlist
    with storage.connection() as conn:
        conn.execute("DELETE FROM watchlist_items")
        conn.commit()

    # Sync with lowercase tickers
    manager.sync_portfolio_to_watchlist(["aapl", "googl"])

    # Verify tickers are uppercase
    df = storage.query("SELECT symbol FROM watchlist_items ORDER BY symbol")
    assert df.height == 2
    rows = df.to_dicts()
    assert rows[0]["symbol"] == "AAPL"
    assert rows[1]["symbol"] == "GOOGL"
