"""Tests for volume analytics functions."""

from __future__ import annotations

import datetime as dt
from unittest.mock import Mock

import polars as pl
import pytest

from app.analytics.volume import calculate_rvol, get_high_volume_symbols


@pytest.fixture
def mock_storage() -> Mock:
    """Create a mock storage instance."""
    storage = Mock()
    return storage


def test_calculate_rvol_success(mock_storage: Mock) -> None:
    """Test successful RVOL calculation."""
    # Mock current day's volume
    current_result = pl.DataFrame({"volume": [100000000]})

    # Mock average volume over lookback period
    avg_result = pl.DataFrame({"avg_volume": [50000000.0]})

    # Configure mock to return different results for different queries
    def query_side_effect(sql: str, params: list) -> pl.DataFrame:  # type: ignore[type-arg]
        if "SELECT volume" in sql:
            return current_result
        if "SELECT AVG(volume)" in sql:
            return avg_result
        return pl.DataFrame()

    mock_storage.query.side_effect = query_side_effect

    # Calculate RVOL
    rvol = calculate_rvol(mock_storage, "AAPL", dt.date(2025, 1, 15), lookback_days=20)

    # Verify RVOL is 2.0 (100M / 50M)
    assert rvol is not None
    assert rvol == 2.0

    # Verify storage.query was called twice
    assert mock_storage.query.call_count == 2


def test_calculate_rvol_with_string_date(mock_storage: Mock) -> None:
    """Test RVOL calculation with string date."""
    current_result = pl.DataFrame({"volume": [80000000]})
    avg_result = pl.DataFrame({"avg_volume": [100000000.0]})

    def query_side_effect(sql: str, params: list) -> pl.DataFrame:  # type: ignore[type-arg]
        if "SELECT volume" in sql:
            return current_result
        if "SELECT AVG(volume)" in sql:
            return avg_result
        return pl.DataFrame()

    mock_storage.query.side_effect = query_side_effect

    # Calculate RVOL with string date
    rvol = calculate_rvol(mock_storage, "MSFT", "2025-01-15", lookback_days=20)

    # Verify RVOL is 0.8 (80M / 100M = below average volume)
    assert rvol is not None
    assert rvol == 0.8


def test_calculate_rvol_no_current_data(mock_storage: Mock) -> None:
    """Test RVOL calculation when no current data exists."""
    # Mock empty result for current day
    empty_result = pl.DataFrame({"volume": []})
    mock_storage.query.return_value = empty_result

    # Calculate RVOL
    rvol = calculate_rvol(mock_storage, "INVALID", dt.date(2025, 1, 15), lookback_days=20)

    # Should return None
    assert rvol is None


def test_calculate_rvol_zero_current_volume(mock_storage: Mock) -> None:
    """Test RVOL calculation when current volume is zero."""
    current_result = pl.DataFrame({"volume": [0]})
    mock_storage.query.return_value = current_result

    # Calculate RVOL
    rvol = calculate_rvol(mock_storage, "AAPL", dt.date(2025, 1, 15), lookback_days=20)

    # Should return None for zero volume
    assert rvol is None


def test_calculate_rvol_no_lookback_data(mock_storage: Mock) -> None:
    """Test RVOL calculation when no lookback data exists."""
    current_result = pl.DataFrame({"volume": [100000000]})
    empty_avg_result = pl.DataFrame({"avg_volume": []})

    def query_side_effect(sql: str, params: list) -> pl.DataFrame:  # type: ignore[type-arg]
        if "SELECT volume" in sql:
            return current_result
        if "SELECT AVG(volume)" in sql:
            return empty_avg_result
        return pl.DataFrame()

    mock_storage.query.side_effect = query_side_effect

    # Calculate RVOL
    rvol = calculate_rvol(mock_storage, "NEWSTOCK", dt.date(2025, 1, 15), lookback_days=20)

    # Should return None when no lookback data
    assert rvol is None


def test_calculate_rvol_zero_avg_volume(mock_storage: Mock) -> None:
    """Test RVOL calculation when average volume is zero."""
    current_result = pl.DataFrame({"volume": [100000000]})
    zero_avg_result = pl.DataFrame({"avg_volume": [0.0]})

    def query_side_effect(sql: str, params: list) -> pl.DataFrame:  # type: ignore[type-arg]
        if "SELECT volume" in sql:
            return current_result
        if "SELECT AVG(volume)" in sql:
            return zero_avg_result
        return pl.DataFrame()

    mock_storage.query.side_effect = query_side_effect

    # Calculate RVOL
    rvol = calculate_rvol(mock_storage, "AAPL", dt.date(2025, 1, 15), lookback_days=20)

    # Should return None when avg volume is zero
    assert rvol is None


def test_calculate_rvol_custom_lookback(mock_storage: Mock) -> None:
    """Test RVOL calculation with custom lookback period."""
    current_result = pl.DataFrame({"volume": [150000000]})
    avg_result = pl.DataFrame({"avg_volume": [100000000.0]})

    def query_side_effect(sql: str, params: list) -> pl.DataFrame:  # type: ignore[type-arg]
        if "SELECT volume" in sql:
            return current_result
        if "SELECT AVG(volume)" in sql:
            return avg_result
        return pl.DataFrame()

    mock_storage.query.side_effect = query_side_effect

    # Calculate RVOL with 10-day lookback
    rvol = calculate_rvol(mock_storage, "GOOGL", dt.date(2025, 1, 15), lookback_days=10)

    # Verify RVOL is 1.5 (150M / 100M)
    assert rvol is not None
    assert rvol == 1.5


def test_get_high_volume_symbols_success(mock_storage: Mock) -> None:
    """Test finding high volume symbols."""
    # Mock symbols for the date
    symbols_result = pl.DataFrame({"symbol": ["AAPL", "MSFT", "GOOGL"]})

    # Volume data per symbol
    volume_data = {
        "AAPL": {"volume": 200000000, "avg": 100000000.0},  # RVOL=2.0
        "MSFT": {"volume": 100000000, "avg": 100000000.0},  # RVOL=1.0
        "GOOGL": {"volume": 80000000, "avg": 100000000.0},  # RVOL=0.8
    }

    # Mock volume data for each symbol
    def query_side_effect(sql: str, params: list) -> pl.DataFrame:  # type: ignore[type-arg]
        if "SELECT DISTINCT symbol" in sql:
            return symbols_result
        if params and params[0] in volume_data:
            symbol_data = volume_data[params[0]]
            if "SELECT volume" in sql:
                return pl.DataFrame({"volume": [symbol_data["volume"]]})
            if "SELECT AVG(volume)" in sql:
                return pl.DataFrame({"avg_volume": [symbol_data["avg"]]})
        return pl.DataFrame()

    mock_storage.query.side_effect = query_side_effect

    # Get high volume symbols (threshold = 1.5x)
    high_vol = get_high_volume_symbols(
        mock_storage,
        dt.date(2025, 1, 15),
        rvol_threshold=1.5,
        lookback_days=20,
        min_symbols=1,
    )

    # Should only return AAPL (RVOL=2.0)
    assert len(high_vol) == 1
    assert high_vol[0]["symbol"] == "AAPL"
    assert high_vol[0]["rvol"] == 2.0
    assert high_vol[0]["current_volume"] == 200000000
    assert high_vol[0]["avg_volume"] == 100000000


def test_get_high_volume_symbols_with_string_date(mock_storage: Mock) -> None:
    """Test finding high volume symbols with string date."""
    symbols_result = pl.DataFrame({"symbol": ["AAPL"]})

    def query_side_effect(sql: str, params: list) -> pl.DataFrame:  # type: ignore[type-arg]
        if "SELECT DISTINCT symbol" in sql:
            return symbols_result
        if "SELECT volume" in sql:
            return pl.DataFrame({"volume": [150000000]})
        if "SELECT AVG(volume)" in sql:
            return pl.DataFrame({"avg_volume": [100000000.0]})
        return pl.DataFrame()

    mock_storage.query.side_effect = query_side_effect

    # Get high volume symbols with string date
    high_vol = get_high_volume_symbols(
        mock_storage,
        "2025-01-15",
        rvol_threshold=1.4,
        lookback_days=20,
    )

    # Should return AAPL (RVOL=1.5)
    assert len(high_vol) >= 1
    assert high_vol[0]["symbol"] == "AAPL"
    assert high_vol[0]["rvol"] == 1.5


def test_get_high_volume_symbols_no_data(mock_storage: Mock) -> None:
    """Test finding high volume symbols when no data exists."""
    empty_result = pl.DataFrame({"symbol": []})
    mock_storage.query.return_value = empty_result

    # Get high volume symbols
    high_vol = get_high_volume_symbols(
        mock_storage,
        dt.date(2025, 1, 15),
        rvol_threshold=1.5,
    )

    # Should return empty list
    assert len(high_vol) == 0


def test_get_high_volume_symbols_sorted_by_rvol(mock_storage: Mock) -> None:
    """Test that high volume symbols are sorted by RVOL descending."""
    symbols_result = pl.DataFrame({"symbol": ["AAPL", "MSFT", "GOOGL"]})

    # Helper to reduce complexity - AAPL has RVOL=2.0
    def get_aapl_data(sql: str) -> pl.DataFrame:
        if "SELECT volume" in sql:
            return pl.DataFrame({"volume": [200000000]})
        return pl.DataFrame({"avg_volume": [100000000.0]})

    # MSFT has RVOL=3.0 (highest)
    def get_msft_data(sql: str) -> pl.DataFrame:
        if "SELECT volume" in sql:
            return pl.DataFrame({"volume": [300000000]})
        return pl.DataFrame({"avg_volume": [100000000.0]})

    # GOOGL has RVOL=1.5
    def get_googl_data(sql: str) -> pl.DataFrame:
        if "SELECT volume" in sql:
            return pl.DataFrame({"volume": [150000000]})
        return pl.DataFrame({"avg_volume": [100000000.0]})

    def query_side_effect(sql: str, params: list) -> pl.DataFrame:  # type: ignore[type-arg]
        if "SELECT DISTINCT symbol" in sql:
            return symbols_result
        if params and params[0] == "AAPL":
            return get_aapl_data(sql)
        if params and params[0] == "MSFT":
            return get_msft_data(sql)
        if params and params[0] == "GOOGL":
            return get_googl_data(sql)
        return pl.DataFrame()

    mock_storage.query.side_effect = query_side_effect

    # Get high volume symbols
    high_vol = get_high_volume_symbols(
        mock_storage,
        dt.date(2025, 1, 15),
        rvol_threshold=1.4,
        lookback_days=20,
    )

    # Should be sorted: MSFT (3.0), AAPL (2.0), GOOGL (1.5)
    assert len(high_vol) == 3
    assert high_vol[0]["symbol"] == "MSFT"
    assert high_vol[0]["rvol"] == 3.0
    assert high_vol[1]["symbol"] == "AAPL"
    assert high_vol[1]["rvol"] == 2.0
    assert high_vol[2]["symbol"] == "GOOGL"
    assert high_vol[2]["rvol"] == 1.5
