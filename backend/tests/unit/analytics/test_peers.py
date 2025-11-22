"""Tests for peer comparison analytics."""

from __future__ import annotations

import datetime as dt
from unittest.mock import Mock

import polars as pl
import pytest

from app.analytics.peers import (
    _validate_and_get_group_data,
    get_peer_comparison,
    get_peer_group_detail,
)


@pytest.fixture
def mock_storage() -> Mock:
    """Create a mock storage instance."""
    return Mock()


def test_validate_and_get_group_data_success(mock_storage: Mock) -> None:
    """Test successful validation and group data retrieval."""
    # Mock ticker group data
    ticker_group_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "sector": ["Technology"],
        }
    )

    # Mock peers data
    peers_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "GOOGL"],
        }
    )

    mock_storage.query.side_effect = [ticker_group_data, peers_data]

    # Execute
    group_name, peer_tickers = _validate_and_get_group_data(mock_storage, "AAPL", "sector")

    # Verify
    assert group_name == "Technology"
    assert peer_tickers == ["AAPL", "MSFT", "GOOGL"]


def test_validate_and_get_group_data_invalid_group_by(mock_storage: Mock) -> None:
    """Test validation with invalid group_by parameter."""
    # Execute
    group_name, peer_tickers = _validate_and_get_group_data(mock_storage, "AAPL", "invalid")

    # Verify
    assert group_name is None
    assert peer_tickers is None


def test_validate_and_get_group_data_no_ticker_data(mock_storage: Mock) -> None:
    """Test when ticker has no group data."""
    # Mock empty ticker group data
    mock_storage.query.return_value = pl.DataFrame()

    # Execute
    group_name, peer_tickers = _validate_and_get_group_data(mock_storage, "AAPL", "sector")

    # Verify
    assert group_name is None
    assert peer_tickers is None


def test_get_peer_comparison_success(mock_storage: Mock) -> None:
    """Test successful peer comparison calculation."""
    # Mock ticker group data
    ticker_group_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "sector": ["Technology"],
        }
    )

    # Mock peers data
    peers_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "GOOGL", "META"],
        }
    )

    # Mock returns data
    returns_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "GOOGL", "META"],
            "return_5d": [2.5, 3.0, 1.5, 2.0],
            "return_20d": [8.0, 10.0, 6.0, 7.0],
        }
    )

    mock_storage.query.side_effect = [
        ticker_group_data,
        peers_data,
        returns_data,
    ]

    # Execute
    result = get_peer_comparison(mock_storage, "AAPL", "2025-01-15")

    # Verify
    assert result is not None
    assert len(result) == 1

    # Check columns
    expected_cols = [
        "ticker",
        "sector",
        "return_5d",
        "return_20d",
        "sector_avg_5d",
        "sector_avg_20d",
        "relative_perf_5d",
        "relative_perf_20d",
        "peer_rank",
        "peer_count",
        "percentile",
    ]
    for col in expected_cols:
        assert col in result.columns

    # Verify values
    assert result["ticker"][0] == "AAPL"
    assert result["sector"][0] == "Technology"
    assert result["return_5d"][0] == 2.5
    assert result["return_20d"][0] == 8.0
    assert result["peer_count"][0] == 4

    # AAPL ranks #2 out of 4 (MSFT is #1 with 10.0% return)
    assert result["peer_rank"][0] == 2
    # Percentile should be 75.0 for rank 2 out of 4
    assert result["percentile"][0] == 75.0


def test_get_peer_comparison_no_group_data(mock_storage: Mock) -> None:
    """Test peer comparison when no group data available."""
    # Mock empty group data
    mock_storage.query.return_value = pl.DataFrame()

    # Execute
    result = get_peer_comparison(mock_storage, "AAPL", "2025-01-15")

    # Verify
    assert result is None


def test_get_peer_comparison_no_returns_data(mock_storage: Mock) -> None:
    """Test peer comparison when no returns data available."""
    # Mock ticker group data
    ticker_group_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "sector": ["Technology"],
        }
    )

    # Mock peers data
    peers_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT"],
        }
    )

    # Mock empty returns data
    mock_storage.query.side_effect = [
        ticker_group_data,
        peers_data,
        pl.DataFrame(),
    ]

    # Execute
    result = get_peer_comparison(mock_storage, "AAPL", "2025-01-15")

    # Verify
    assert result is None


def test_get_peer_comparison_ticker_not_in_returns(mock_storage: Mock) -> None:
    """Test peer comparison when target ticker has no returns data."""
    # Mock ticker group data
    ticker_group_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "sector": ["Technology"],
        }
    )

    # Mock peers data
    peers_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT"],
        }
    )

    # Mock returns data without AAPL
    returns_data = pl.DataFrame(
        {
            "ticker": ["MSFT"],
            "return_5d": [3.0],
            "return_20d": [10.0],
        }
    )

    mock_storage.query.side_effect = [
        ticker_group_data,
        peers_data,
        returns_data,
    ]

    # Execute
    result = get_peer_comparison(mock_storage, "AAPL", "2025-01-15")

    # Verify
    assert result is None


def test_get_peer_comparison_invalid_group_by(mock_storage: Mock) -> None:
    """Test peer comparison with invalid group_by parameter."""
    # Execute
    result = get_peer_comparison(mock_storage, "AAPL", "2025-01-15", group_by="invalid")

    # Verify
    assert result is None


def test_get_peer_comparison_date_object(mock_storage: Mock) -> None:
    """Test peer comparison with date object input."""
    # Mock data
    ticker_group_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "sector": ["Technology"],
        }
    )
    peers_data = pl.DataFrame({"ticker": ["AAPL", "MSFT"]})
    returns_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT"],
            "return_5d": [2.5, 3.0],
            "return_20d": [8.0, 10.0],
        }
    )

    mock_storage.query.side_effect = [
        ticker_group_data,
        peers_data,
        returns_data,
    ]

    # Execute with date object
    result = get_peer_comparison(mock_storage, "AAPL", dt.date(2025, 1, 15))

    # Verify
    assert result is not None


def test_get_peer_group_detail_success(mock_storage: Mock) -> None:
    """Test successful peer group detail retrieval."""
    # Mock ticker group data
    ticker_group_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "sector": ["Technology"],
        }
    )

    # Mock peers data
    peers_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "GOOGL"],
        }
    )

    # Mock returns data
    returns_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT", "GOOGL"],
            "return_5d": [2.5, 3.0, 1.5],
            "return_20d": [8.0, 10.0, 6.0],
        }
    )

    mock_storage.query.side_effect = [
        ticker_group_data,
        peers_data,
        returns_data,
    ]

    # Execute
    result = get_peer_group_detail(mock_storage, "AAPL", "2025-01-15")

    # Verify
    assert result is not None
    assert len(result) == 3
    assert "ticker" in result.columns
    assert "sector" in result.columns
    assert "return_5d" in result.columns
    assert "return_20d" in result.columns
    assert "rank" in result.columns
    assert "is_target" in result.columns

    # Verify sorted by return_20d descending
    assert result["return_20d"][0] > result["return_20d"][1]
    assert result["return_20d"][1] > result["return_20d"][2]

    # Verify ranks
    assert result["rank"][0] == 1
    assert result["rank"][1] == 2
    assert result["rank"][2] == 3

    # Verify is_target flag
    target_rows = result.filter(pl.col("is_target"))
    assert len(target_rows) == 1
    assert target_rows["ticker"][0] == "AAPL"


def test_get_peer_group_detail_no_group_data(mock_storage: Mock) -> None:
    """Test peer group detail when no group data available."""
    # Mock empty group data
    mock_storage.query.return_value = pl.DataFrame()

    # Execute
    result = get_peer_group_detail(mock_storage, "AAPL", "2025-01-15")

    # Verify
    assert result is None


def test_get_peer_group_detail_no_returns_data(mock_storage: Mock) -> None:
    """Test peer group detail when no returns data available."""
    # Mock ticker group data
    ticker_group_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "sector": ["Technology"],
        }
    )

    # Mock peers data
    peers_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "MSFT"],
        }
    )

    # Mock empty returns data
    mock_storage.query.side_effect = [
        ticker_group_data,
        peers_data,
        pl.DataFrame(),
    ]

    # Execute
    result = get_peer_group_detail(mock_storage, "AAPL", "2025-01-15")

    # Verify
    assert result is None


def test_get_peer_group_detail_industry_grouping(mock_storage: Mock) -> None:
    """Test peer group detail with industry grouping."""
    # Mock ticker group data
    ticker_group_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "industry": ["Consumer Electronics"],
        }
    )

    # Mock peers data
    peers_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "SONY"],
        }
    )

    # Mock returns data
    returns_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "SONY"],
            "return_5d": [2.5, 3.0],
            "return_20d": [8.0, 10.0],
        }
    )

    mock_storage.query.side_effect = [
        ticker_group_data,
        peers_data,
        returns_data,
    ]

    # Execute with industry grouping
    result = get_peer_group_detail(mock_storage, "AAPL", "2025-01-15", group_by="industry")

    # Verify
    assert result is not None
    assert "industry" in result.columns
