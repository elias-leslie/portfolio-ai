"""Tests for multi-source data fetching with failover and rate limit management.

This module tests the MultiSourceFetcher class and source adapters.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import Mock

import polars as pl
import pytest
from httpx import HTTPStatusError, Response

from app.sources.base import DATASET_REFERENCE, DatasetRequest
from app.sources.multi_source_fetcher import MultiSourceFetcher
from app.sources.polygon_source import PolygonSource
from app.sources.yfinance_source import YFinanceSource
from app.storage import PortfolioStorage

# Fixtures


@pytest.fixture
def mock_storage(tmp_path):  # type: ignore[no-untyped-def]
    """Create a test storage instance."""
    from app.storage import get_storage

    storage = get_storage()

    # Clean source_performance table to ensure fresh metrics for each test
    with storage.connection() as conn:
        conn.execute("DELETE FROM source_performance")

    return storage


@pytest.fixture
def sample_request() -> DatasetRequest:
    """Create a sample DatasetRequest."""
    return DatasetRequest(
        dataset=DATASET_REFERENCE,
        profile=None,
        tickers=["AAPL", "GOOGL"],
        start=dt.date(2025, 1, 28),
        end=dt.date(2025, 1, 28),
        timezone="UTC",
    )


@pytest.fixture
def mock_yfinance_source() -> Mock:
    """Create a mock YFinanceSource."""
    source = Mock(spec=YFinanceSource)
    source.name = "yfinance"
    source.priority = 1
    source.supports_day = True
    source.supports_reference = True
    source.supports_news = False
    source.is_enabled.return_value = True
    return source


@pytest.fixture
def mock_polygon_source() -> Mock:
    """Create a mock PolygonSource."""
    source = Mock(spec=PolygonSource)
    source.name = "polygon"
    source.priority = 10
    source.supports_day = True
    source.supports_reference = True
    source.supports_news = False
    source.is_enabled.return_value = True
    return source


# Tests


def test_multi_source_fetcher_initialization(
    mock_yfinance_source: Mock, mock_polygon_source: Mock, mock_storage: PortfolioStorage
) -> None:
    """Test MultiSourceFetcher initializes with sources sorted by priority."""
    fetcher = MultiSourceFetcher([mock_polygon_source, mock_yfinance_source], storage=mock_storage)

    # Should be sorted by priority (yfinance=1, polygon=10)
    assert len(fetcher.sources) == 2
    assert fetcher.sources[0].name == "yfinance"
    assert fetcher.sources[1].name == "polygon"


def test_yfinance_primary_success(
    mock_yfinance_source: Mock,
    mock_polygon_source: Mock,
    mock_storage: PortfolioStorage,
    sample_request: DatasetRequest,
) -> None:
    """Test successful fetch from yfinance (primary source)."""
    # Mock yfinance returning valid data
    mock_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "GOOGL"],
            "as_of_date": [dt.date(2025, 1, 28), dt.date(2025, 1, 28)],
            "payload": ['{"price": 180.0}', '{"price": 140.0}'],
            "source": ["yfinance", "yfinance"],
        }
    )
    mock_yfinance_source.fetch_reference_payload.return_value = mock_data

    fetcher = MultiSourceFetcher([mock_yfinance_source, mock_polygon_source], storage=mock_storage)

    df, _errors = fetcher.fetch_with_fallback(sample_request)

    # Should succeed with yfinance
    assert df is not None
    assert len(df) == 2
    assert set(df["ticker"].to_list()) == {"AAPL", "GOOGL"}

    # Polygon should not be called (yfinance succeeded)
    mock_polygon_source.fetch_reference_payload.assert_not_called()

    # Check metrics
    metrics = fetcher.get_source_metrics("yfinance")
    assert "yfinance" in metrics
    assert metrics["yfinance"].success_count == 1
    assert metrics["yfinance"].failure_count == 0


def test_polygon_failover_on_yfinance_429(
    mock_yfinance_source: Mock,
    mock_polygon_source: Mock,
    mock_storage: PortfolioStorage,
    sample_request: DatasetRequest,
) -> None:
    """Test failover to Polygon when yfinance returns 429 (rate limit)."""
    # Mock yfinance raising 429 error
    mock_response = Response(status_code=429)
    mock_yfinance_source.fetch_reference_payload.side_effect = HTTPStatusError(
        "Rate limit", request=Mock(), response=mock_response
    )

    # Mock Polygon returning valid data
    mock_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "GOOGL"],
            "as_of_date": [dt.date(2025, 1, 28), dt.date(2025, 1, 28)],
            "payload": ['{"price": 180.0}', '{"price": 140.0}'],
            "source": ["polygon", "polygon"],
        }
    )
    mock_polygon_source.fetch_reference_payload.return_value = mock_data

    fetcher = MultiSourceFetcher([mock_yfinance_source, mock_polygon_source], storage=mock_storage)

    df, _errors = fetcher.fetch_with_fallback(sample_request)

    # Should succeed with Polygon
    assert df is not None
    assert len(df) == 2
    assert all(df["source"] == "polygon")

    # Both sources called
    mock_yfinance_source.fetch_reference_payload.assert_called_once()
    mock_polygon_source.fetch_reference_payload.assert_called_once()

    # Check metrics - yfinance should have failure + rate limit hit
    yf_metrics = fetcher.get_source_metrics("yfinance")
    assert yf_metrics["yfinance"].failure_count == 1
    assert yf_metrics["yfinance"].rate_limit_hits == 1

    # Polygon should have success
    pg_metrics = fetcher.get_source_metrics("polygon")
    assert pg_metrics["polygon"].success_count == 1


def test_polygon_failover_on_yfinance_timeout(
    mock_yfinance_source: Mock,
    mock_polygon_source: Mock,
    mock_storage: PortfolioStorage,
    sample_request: DatasetRequest,
) -> None:
    """Test failover to Polygon when yfinance times out."""
    # Mock yfinance timing out
    mock_yfinance_source.fetch_reference_payload.side_effect = TimeoutError("Request timeout")

    # Mock Polygon returning valid data
    mock_data = pl.DataFrame(
        {
            "ticker": ["AAPL", "GOOGL"],
            "as_of_date": [dt.date(2025, 1, 28), dt.date(2025, 1, 28)],
            "payload": ['{"price": 180.0}', '{"price": 140.0}'],
            "source": ["polygon", "polygon"],
        }
    )
    mock_polygon_source.fetch_reference_payload.return_value = mock_data

    fetcher = MultiSourceFetcher([mock_yfinance_source, mock_polygon_source], storage=mock_storage)

    df, _errors = fetcher.fetch_with_fallback(sample_request)

    # Should succeed with Polygon
    assert df is not None
    assert len(df) == 2

    # Both sources called
    mock_yfinance_source.fetch_reference_payload.assert_called_once()
    mock_polygon_source.fetch_reference_payload.assert_called_once()


def test_all_sources_fail(
    mock_yfinance_source: Mock,
    mock_polygon_source: Mock,
    mock_storage: PortfolioStorage,
    sample_request: DatasetRequest,
) -> None:
    """Test all sources failing returns None with error details."""
    # Mock both sources failing
    mock_yfinance_source.fetch_reference_payload.side_effect = Exception("YFinance error")
    mock_polygon_source.fetch_reference_payload.side_effect = Exception("Polygon error")

    fetcher = MultiSourceFetcher([mock_yfinance_source, mock_polygon_source], storage=mock_storage)

    df, errors = fetcher.fetch_with_fallback(sample_request)

    # Should return None
    assert df is None

    # Should have errors from both sources
    assert "yfinance" in errors
    assert "polygon" in errors
    assert "YFinance error" in errors["yfinance"][0]
    assert "Polygon error" in errors["polygon"][0]


def test_rate_limit_cooldown_skips_source(
    mock_yfinance_source: Mock,
    mock_polygon_source: Mock,
    mock_storage: PortfolioStorage,
    sample_request: DatasetRequest,
) -> None:
    """Test that source in cooldown is skipped."""
    # Create fetcher and manually set yfinance to cooldown
    fetcher = MultiSourceFetcher([mock_yfinance_source, mock_polygon_source], storage=mock_storage)

    # Manually set yfinance in rate limit cooldown
    metric = fetcher.metrics_manager.get_metric("yfinance")
    assert metric is not None
    metric.rate_limit_hits = 1
    metric.last_rate_limit_at = dt.datetime.now(dt.UTC)

    # Mock Polygon returning valid data
    mock_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "as_of_date": [dt.date(2025, 1, 28)],
            "payload": ['{"price": 180.0}'],
            "source": ["polygon"],
        }
    )
    mock_polygon_source.fetch_reference_payload.return_value = mock_data

    df, _errors = fetcher.fetch_with_fallback(sample_request)

    # Should succeed with Polygon only
    assert df is not None

    # YFinance should NOT be called (in cooldown)
    mock_yfinance_source.fetch_reference_payload.assert_not_called()

    # Polygon should be called
    mock_polygon_source.fetch_reference_payload.assert_called_once()


def test_source_performance_tracking(
    mock_yfinance_source: Mock, mock_storage: PortfolioStorage, sample_request: DatasetRequest
) -> None:
    """Test that source performance metrics are tracked correctly."""
    # Mock yfinance returning valid data
    mock_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "as_of_date": [dt.date(2025, 1, 28)],
            "payload": ['{"price": 180.0}'],
            "source": ["yfinance"],
        }
    )
    mock_yfinance_source.fetch_reference_payload.return_value = mock_data

    fetcher = MultiSourceFetcher([mock_yfinance_source], storage=mock_storage)

    # Get initial count (may have loaded from DB)
    initial_metrics = fetcher.get_source_metrics("yfinance")
    initial_count = initial_metrics["yfinance"].success_count

    # Perform multiple fetches
    for _ in range(3):
        df, _ = fetcher.fetch_with_fallback(sample_request)
        assert df is not None

    # Check metrics - should have increased by 3
    metrics = fetcher.get_source_metrics("yfinance")
    assert metrics["yfinance"].success_count == initial_count + 3
    assert metrics["yfinance"].failure_count == 0
    assert metrics["yfinance"].success_rate == 100.0


def test_source_metrics_persistence(
    mock_yfinance_source: Mock, mock_storage: PortfolioStorage, sample_request: DatasetRequest
) -> None:
    """Test that source metrics are persisted to database."""
    # Mock yfinance returning valid data
    mock_data = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "as_of_date": [dt.date(2025, 1, 28)],
            "payload": ['{"price": 180.0}'],
            "source": ["yfinance"],
        }
    )
    mock_yfinance_source.fetch_reference_payload.return_value = mock_data

    fetcher = MultiSourceFetcher([mock_yfinance_source], storage=mock_storage)

    df, _ = fetcher.fetch_with_fallback(sample_request)
    assert df is not None

    # Check that metrics were persisted to database
    metrics_df = mock_storage.query(
        "SELECT * FROM source_performance WHERE source_name = ?", ["yfinance"]
    )

    assert not metrics_df.is_empty()
    row = metrics_df.to_dicts()[0]
    assert row["source_name"] == "yfinance"
    assert row["success_count"] >= 1


def test_no_sources_available() -> None:
    """Test behavior when no sources are available for dataset."""
    request = DatasetRequest(
        dataset="unknown_dataset",
        profile=None,
        tickers=["AAPL"],
        start=dt.date(2025, 1, 28),
        end=dt.date(2025, 1, 28),
    )

    fetcher = MultiSourceFetcher([])

    df, errors = fetcher.fetch_with_fallback(request)

    assert df is None
    assert "error" in errors
    assert "No sources available" in errors["error"][0]
