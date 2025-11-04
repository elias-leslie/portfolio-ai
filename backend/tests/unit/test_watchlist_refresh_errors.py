"""Unit tests for watchlist refresh with per-ticker error handling."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import polars as pl
import pytest

from app.portfolio.price_fetcher import PriceData
from app.watchlist.service import refresh_watchlist_scores


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create a mock PortfolioStorage instance."""
    storage = MagicMock()
    storage.query_mgr = MagicMock()

    # Mock connection context manager for fundamentals/earnings caching
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []  # Empty cache results
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    storage.connection.return_value = mock_conn

    return storage


@pytest.fixture
def mock_price_fetcher() -> MagicMock:
    """Create a mock PriceDataFetcher."""
    return MagicMock()


def test_refresh_returns_detailed_results_all_success(
    mock_storage: MagicMock, mock_price_fetcher: MagicMock
) -> None:
    """Test that refresh returns detailed success/failed lists when all succeed."""
    # Mock watchlist items
    items_df = pl.DataFrame(
        {
            "id": ["item-1", "item-2"],
            "account_id": ["acc-1", "acc-1"],
            "symbol": ["AAPL", "GOOGL"],
        }
    )

    def mock_query(sql: str, params: list[str] | None = None) -> pl.DataFrame:
        if "watchlist_items" in sql:
            return items_df
        # Day_bars data - provide volume data (at least 20 rows as required by service)
        if "day_bars" in sql:
            if "volume" in sql:
                # Volume query returns 20 rows for RVOL calculation
                return pl.DataFrame({"volume": [1000000.0 + (i * 10000) for i in range(20)]})
            return pl.DataFrame({"close": [100.0, 95.0]})
        # User preferences
        if "user_preferences" in sql:
            return pl.DataFrame(
                {
                    "watchlist_price_weight": [50.0],
                    "watchlist_technical_weight": [50.0],
                    "watchlist_refresh_minutes": [5],
                }
            )
        # Technical indicators
        if "technical_indicators" in sql:
            return pl.DataFrame()  # Empty for simplicity
        return pl.DataFrame()

    mock_storage.query.side_effect = mock_query

    # Mock price fetcher to return valid data
    mock_price_fetcher.fetch_price_data.return_value = {
        "AAPL": PriceData(
            symbol="AAPL",
            price=150.0,
            beta=1.2,
            volatility=0.25,
            fetched_at=datetime.now(UTC),
            source="yfinance",
        ),
        "GOOGL": PriceData(
            symbol="GOOGL",
            price=2800.0,
            beta=1.1,
            volatility=0.22,
            fetched_at=datetime.now(UTC),
            source="yfinance",
        ),
    }

    # Call refresh
    result = refresh_watchlist_scores(
        mock_storage, account_id="acc-1", price_fetcher=mock_price_fetcher
    )

    # Verify detailed results
    assert result["processed"] == 2
    assert result["success_count"] == 2
    assert result["failed_count"] == 0
    assert len(result["success"]) == 2
    assert len(result["failed"]) == 0
    assert "AAPL" in result["success"]
    assert "GOOGL" in result["success"]


def test_refresh_returns_detailed_results_partial_failure(
    mock_storage: MagicMock, mock_price_fetcher: MagicMock
) -> None:
    """Test that refresh tracks individual failures and continues processing."""
    # Mock watchlist items
    items_df = pl.DataFrame(
        {
            "id": ["item-1", "item-2", "item-3"],
            "account_id": ["acc-1", "acc-1", "acc-1"],
            "symbol": ["AAPL", "INVALID", "GOOGL"],
        }
    )

    def mock_query(sql: str, params: list[str] | None = None) -> pl.DataFrame:
        if "watchlist_items" in sql:
            return items_df
        # Day_bars data - provide volume data (at least 20 rows as required by service)
        if "day_bars" in sql:
            if "volume" in sql:
                # Volume query returns 20 rows for RVOL calculation
                return pl.DataFrame({"volume": [1000000.0 + (i * 10000) for i in range(20)]})
            return pl.DataFrame({"close": [100.0, 95.0]})
        # User preferences
        if "user_preferences" in sql:
            return pl.DataFrame(
                {
                    "watchlist_price_weight": [50.0],
                    "watchlist_technical_weight": [50.0],
                    "watchlist_refresh_minutes": [5],
                }
            )
        # Technical indicators
        if "technical_indicators" in sql:
            return pl.DataFrame()
        return pl.DataFrame()

    mock_storage.query.side_effect = mock_query

    # Mock price fetcher: INVALID ticker returns None/invalid price
    mock_price_fetcher.fetch_price_data.return_value = {
        "AAPL": PriceData(
            symbol="AAPL",
            price=150.0,
            beta=1.2,
            volatility=0.25,
            fetched_at=datetime.now(UTC),
            source="yfinance",
        ),
        "INVALID": PriceData(
            symbol="INVALID",
            price=0.0,  # Invalid price
            beta=None,
            volatility=None,
            fetched_at=datetime.now(UTC),
            source="yfinance",
        ),
        "GOOGL": PriceData(
            symbol="GOOGL",
            price=2800.0,
            beta=1.1,
            volatility=0.22,
            fetched_at=datetime.now(UTC),
            source="yfinance",
        ),
    }

    # Call refresh
    result = refresh_watchlist_scores(
        mock_storage, account_id="acc-1", price_fetcher=mock_price_fetcher
    )

    # Verify partial success tracking
    assert result["processed"] == 2  # AAPL and GOOGL succeeded
    assert result["success_count"] == 2
    assert result["failed_count"] == 1
    assert len(result["success"]) == 2
    assert len(result["failed"]) == 1
    assert "AAPL" in result["success"]
    assert "GOOGL" in result["success"]
    assert result["failed"][0]["symbol"] == "INVALID"
    assert "price" in result["failed"][0]["reason"].lower()


def test_refresh_continues_after_individual_failures(
    mock_storage: MagicMock, mock_price_fetcher: MagicMock
) -> None:
    """Test that refresh continues processing even if one ticker fails."""
    # Mock watchlist items
    items_df = pl.DataFrame(
        {
            "id": ["item-1", "item-2"],
            "account_id": ["acc-1", "acc-1"],
            "symbol": ["AAPL", "GOOGL"],
        }
    )

    call_count = {"query": 0}

    def mock_query(sql: str, params: list[str] | None = None) -> pl.DataFrame:
        call_count["query"] += 1
        if "watchlist_items" in sql:
            return items_df
        if "day_bars" in sql:
            if "volume" in sql:
                # Volume query returns 20 rows for RVOL calculation
                return pl.DataFrame({"volume": [1000000.0 + (i * 10000) for i in range(20)]})
            # First call (AAPL) succeeds, second call (GOOGL) also succeeds
            return pl.DataFrame({"close": [100.0, 95.0]})
        if "user_preferences" in sql:
            return pl.DataFrame(
                {
                    "watchlist_price_weight": [50.0],
                    "watchlist_technical_weight": [50.0],
                    "watchlist_refresh_minutes": [5],
                }
            )
        if "technical_indicators" in sql:
            return pl.DataFrame()
        return pl.DataFrame()

    mock_storage.query.side_effect = mock_query

    # AAPL fails (price = 0), GOOGL succeeds
    mock_price_fetcher.fetch_price_data.return_value = {
        "AAPL": PriceData(
            symbol="AAPL",
            price=0.0,  # Invalid
            beta=None,
            volatility=None,
            fetched_at=datetime.now(UTC),
            source="yfinance",
        ),
        "GOOGL": PriceData(
            symbol="GOOGL",
            price=2800.0,
            beta=1.1,
            volatility=0.22,
            fetched_at=datetime.now(UTC),
            source="yfinance",
        ),
    }

    result = refresh_watchlist_scores(
        mock_storage, account_id="acc-1", price_fetcher=mock_price_fetcher
    )

    # Verify GOOGL was still processed after AAPL failed
    assert result["processed"] == 1  # Only GOOGL succeeded
    assert result["failed_count"] == 1
    assert "GOOGL" in result["success"]
    assert result["failed"][0]["symbol"] == "AAPL"
