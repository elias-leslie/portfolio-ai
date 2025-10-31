"""Unit tests for watchlist price change calculation with fallback logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import polars as pl
import pytest

from app.watchlist.service import _calculate_price_change


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create a mock DuckDBStorage instance."""
    return MagicMock()


def test_calculate_price_change_with_day_bars_data(mock_storage: MagicMock) -> None:
    """Test price change calculation when day_bars data is available."""
    # Mock day_bars query result (2 days of data)
    mock_df = pl.DataFrame({"close": [100.0, 95.0]})
    mock_storage.query.return_value = mock_df

    # Current price is 105, previous close was 95
    # Expected change: (105 - 95) / 95 * 100 = 10.526%
    change_pct, has_historical_data = _calculate_price_change(
        mock_storage, "AAPL", 105.0, "item-123"
    )

    assert change_pct == pytest.approx(10.526315789473683)
    assert has_historical_data is True
    mock_storage.query.assert_called_once()


def test_calculate_price_change_without_day_bars_with_snapshot(
    mock_storage: MagicMock,
) -> None:
    """Test fallback to snapshot when day_bars data is missing."""

    def mock_query(sql: str, params: list[str]) -> pl.DataFrame:
        # First call: day_bars query (empty result)
        if "day_bars" in sql:
            return pl.DataFrame({"close": []})
        # Second call: watchlist_snapshots query (has data)
        return pl.DataFrame({"price": [98.0]})

    mock_storage.query.side_effect = mock_query

    # Current price is 105, previous snapshot was 98
    # Expected change: (105 - 98) / 98 * 100 = 7.142857%
    change_pct, has_historical_data = _calculate_price_change(
        mock_storage, "NEWCO", 105.0, "item-456"
    )

    assert change_pct == pytest.approx(7.142857142857143)
    assert has_historical_data is False  # No day_bars data
    assert mock_storage.query.call_count == 2


def test_calculate_price_change_no_data_at_all(mock_storage: MagicMock) -> None:
    """Test when neither day_bars nor snapshots are available."""
    # Both queries return empty results
    mock_storage.query.return_value = pl.DataFrame({"close": []})

    change_pct, has_historical_data = _calculate_price_change(
        mock_storage, "BRAND_NEW", 100.0, "item-789"
    )

    assert change_pct is None
    assert has_historical_data is False
    assert mock_storage.query.call_count == 2


def test_calculate_price_change_invalid_price(mock_storage: MagicMock) -> None:
    """Test that None/zero price returns None without querying."""
    change_pct, has_historical_data = _calculate_price_change(
        mock_storage, "AAPL", None, "item-123"
    )

    assert change_pct is None
    assert has_historical_data is False
    mock_storage.query.assert_not_called()

    change_pct, has_historical_data = _calculate_price_change(mock_storage, "AAPL", 0.0, "item-123")

    assert change_pct is None
    assert has_historical_data is False


def test_calculate_price_change_without_item_id(mock_storage: MagicMock) -> None:
    """Test that snapshot fallback is skipped when no item_id provided."""
    # Day_bars query returns empty
    mock_storage.query.return_value = pl.DataFrame({"close": []})

    change_pct, has_historical_data = _calculate_price_change(
        mock_storage,
        "AAPL",
        100.0,
        None,  # No item_id
    )

    assert change_pct is None
    assert has_historical_data is False
    assert mock_storage.query.call_count == 1  # Only day_bars query


def test_calculate_price_change_day_bars_only_one_row(mock_storage: MagicMock) -> None:
    """Test that single day_bars row triggers snapshot fallback."""
    mock_df_day_bars = pl.DataFrame({"close": [100.0]})  # Only 1 row
    mock_df_snapshot = pl.DataFrame({"price": [95.0]})

    def mock_query(sql: str, params: list[str]) -> pl.DataFrame:
        if "day_bars" in sql:
            return mock_df_day_bars
        return mock_df_snapshot

    mock_storage.query.side_effect = mock_query

    change_pct, has_historical_data = _calculate_price_change(
        mock_storage, "AAPL", 105.0, "item-123"
    )

    # Should fall back to snapshot: (105 - 95) / 95 * 100 = 10.526%
    assert change_pct == pytest.approx(10.526315789473683)
    assert has_historical_data is False  # Insufficient day_bars
    assert mock_storage.query.call_count == 2


def test_calculate_price_change_day_bars_with_zero_close(mock_storage: MagicMock) -> None:
    """Test that zero close price in day_bars triggers snapshot fallback."""
    mock_df_day_bars = pl.DataFrame({"close": [100.0, 0.0]})  # Invalid prev close
    mock_df_snapshot = pl.DataFrame({"price": [90.0]})

    def mock_query(sql: str, params: list[str]) -> pl.DataFrame:
        if "day_bars" in sql:
            return mock_df_day_bars
        return mock_df_snapshot

    mock_storage.query.side_effect = mock_query

    change_pct, has_historical_data = _calculate_price_change(
        mock_storage, "AAPL", 105.0, "item-123"
    )

    # Should fall back to snapshot: (105 - 90) / 90 * 100 = 16.667%
    assert change_pct == pytest.approx(16.666666666666668)
    assert has_historical_data is False
    assert mock_storage.query.call_count == 2
