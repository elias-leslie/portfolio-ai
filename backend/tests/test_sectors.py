"""Tests for sector rotation analytics."""

from __future__ import annotations

import datetime as dt
from unittest.mock import Mock

import polars as pl
import pytest

from app.analytics.sectors import get_sector_performance_detail, get_sector_rotation


@pytest.fixture
def mock_storage() -> Mock:
    """Create a mock storage instance."""
    return Mock()


def test_get_sector_rotation_success(mock_storage: Mock) -> None:
    """Test successful sector rotation calculation."""
    # Mock sector data query
    sector_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "JPM", "BAC"],
            "sector": ["Technology", "Technology", "Financial Services", "Financial Services"],
        }
    )

    # Mock returns data query
    returns_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "JPM", "BAC"],
            "close_now": [180.0, 380.0, 150.0, 35.0],
            "volume": [50000000, 25000000, 15000000, 30000000],
            "close_5d": [175.0, 370.0, 148.0, 34.5],
            "close_20d": [170.0, 360.0, 145.0, 33.0],
            "return_5d": [2.86, 2.70, 1.35, 1.45],
            "return_20d": [5.88, 5.56, 3.45, 6.06],
        }
    )

    # Set up mock responses
    mock_storage.query.side_effect = [sector_data, returns_data]

    # Execute
    result = get_sector_rotation(mock_storage, "2025-01-15", lookback_days=20)

    # Verify
    assert result is not None
    assert len(result) == 2  # Two sectors
    assert "sector" in result.columns
    assert "momentum_5d" in result.columns
    assert "momentum_20d" in result.columns
    assert "num_stocks" in result.columns

    # Verify sectors are sorted by momentum_20d descending
    assert result["momentum_20d"][0] > result["momentum_20d"][1]


def test_get_sector_rotation_no_sector_data(mock_storage: Mock) -> None:
    """Test sector rotation when no sector data is available."""
    # Mock empty sector data
    mock_storage.query.return_value = pl.DataFrame()

    # Execute
    result = get_sector_rotation(mock_storage, "2025-01-15")

    # Verify
    assert result is None


def test_get_sector_rotation_no_returns_data(mock_storage: Mock) -> None:
    """Test sector rotation when no returns data is available."""
    # Mock sector data
    sector_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT"],
            "sector": ["Technology", "Technology"],
        }
    )

    # Mock empty returns data
    mock_storage.query.side_effect = [sector_data, pl.DataFrame()]

    # Execute
    result = get_sector_rotation(mock_storage, "2025-01-15")

    # Verify
    assert result is None


def test_get_sector_rotation_string_date(mock_storage: Mock) -> None:
    """Test sector rotation with string date input."""
    # Mock data
    sector_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "sector": ["Technology"],
        }
    )

    returns_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "close_now": [180.0],
            "volume": [50000000],
            "close_5d": [175.0],
            "close_20d": [170.0],
            "return_5d": [2.86],
            "return_20d": [5.88],
        }
    )

    mock_storage.query.side_effect = [sector_data, returns_data]

    # Execute with string date
    result = get_sector_rotation(mock_storage, "2025-01-15")

    # Verify
    assert result is not None


def test_get_sector_performance_detail_success(mock_storage: Mock) -> None:
    """Test successful sector performance detail calculation."""
    # Mock tickers in sector
    tickers_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "GOOGL"],
        }
    )

    # Mock performance data
    performance_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "GOOGL"],
            "sector": ["Technology", "Technology", "Technology"],
            "close": [180.0, 380.0, 140.0],
            "volume": [50000000, 25000000, 20000000],
            "return_5d": [2.86, 2.70, 1.50],
            "return_20d": [5.88, 5.56, 3.20],
        }
    )

    mock_storage.query.side_effect = [tickers_data, performance_data]

    # Execute
    result = get_sector_performance_detail(mock_storage, "Technology", "2025-01-15")

    # Verify
    assert result is not None
    assert len(result) == 3  # Three stocks
    assert "ticker" in result.columns
    assert "sector" in result.columns
    assert "return_5d" in result.columns
    assert "return_20d" in result.columns
    assert "volume" in result.columns
    assert "close" in result.columns


def test_get_sector_performance_detail_no_tickers(mock_storage: Mock) -> None:
    """Test sector performance detail when no tickers found in sector."""
    # Mock empty tickers
    mock_storage.query.return_value = pl.DataFrame()

    # Execute
    result = get_sector_performance_detail(mock_storage, "Technology", "2025-01-15")

    # Verify
    assert result is None


def test_get_sector_performance_detail_no_performance_data(mock_storage: Mock) -> None:
    """Test sector performance detail when no performance data available."""
    # Mock tickers
    tickers_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT"],
        }
    )

    # Mock empty performance data
    mock_storage.query.side_effect = [tickers_data, pl.DataFrame()]

    # Execute
    result = get_sector_performance_detail(mock_storage, "Technology", "2025-01-15")

    # Verify
    assert result is None


def test_get_sector_performance_detail_date_object(mock_storage: Mock) -> None:
    """Test sector performance detail with date object input."""
    # Mock data
    tickers_data = pl.DataFrame({"ticker": ["AAPL"]})
    performance_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "sector": ["Technology"],
            "close": [180.0],
            "volume": [50000000],
            "return_5d": [2.86],
            "return_20d": [5.88],
        }
    )

    mock_storage.query.side_effect = [tickers_data, performance_data]

    # Execute with date object
    result = get_sector_performance_detail(mock_storage, "Technology", dt.date(2025, 1, 15))

    # Verify
    assert result is not None
