"""Unit tests for PriceDataFetcher."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from app.portfolio.price_fetcher import PriceDataFetcher
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
def price_fetcher(storage: DuckDBStorage) -> PriceDataFetcher:
    """Create a PriceDataFetcher instance."""
    return PriceDataFetcher(storage)


def test_cache_prices(price_fetcher: PriceDataFetcher) -> None:
    """Test caching price data."""
    from app.portfolio.models import PriceData

    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, beta=1.2, sector="Technology"),
    }

    price_fetcher._cache_prices(price_data)

    # Verify data was cached
    df = price_fetcher.storage.query("SELECT * FROM price_cache WHERE symbol = 'AAPL'")
    assert not df.is_empty()
    assert df["symbol"][0] == "AAPL"
    assert df["price"][0] == 180.0


def test_get_cached_prices_valid(price_fetcher: PriceDataFetcher) -> None:
    """Test retrieving valid cached prices."""
    from app.portfolio.models import PriceData

    # Cache some data
    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0, beta=1.2, sector="Technology"),
    }
    price_fetcher._cache_prices(price_data)

    # Retrieve from cache
    cached = price_fetcher._get_cached_prices(["AAPL"])

    assert "AAPL" in cached
    assert cached["AAPL"].price == 180.0
    assert cached["AAPL"].beta == 1.2


def test_get_cached_prices_expired(price_fetcher: PriceDataFetcher) -> None:
    """Test that expired cache entries are not returned."""
    # Manually insert an expired cache entry
    old_time = datetime.now() - timedelta(minutes=30)

    df = pl.DataFrame(
        [
            {
                "symbol": "AAPL",
                "price": 180.0,
                "beta": 1.2,
                "volatility": None,
                "sector": "Technology",
                "cached_at": old_time,
                "source": "yfinance",
                "error": None,
            }
        ]
    )
    price_fetcher.storage.insert_dataframe("price_cache", df, mode="append")

    # Try to get cached price (should return empty since it's expired)
    cached = price_fetcher._get_cached_prices(["AAPL"])

    assert cached == {}


@patch("app.portfolio.price_fetcher.yf.Ticker")
def test_fetch_from_yfinance_success(
    mock_ticker: MagicMock,
    price_fetcher: PriceDataFetcher,
) -> None:
    """Test successful fetch from yfinance."""
    # Mock yfinance response
    mock_info = {
        "currentPrice": 180.0,
        "beta": 1.2,
        "fiftyTwoWeekHigh": 200.0,
        "fiftyTwoWeekLow": 150.0,
        "sector": "Technology",
    }
    mock_ticker.return_value.info = mock_info

    result = price_fetcher._fetch_from_yfinance(["AAPL"])

    assert "AAPL" in result
    assert result["AAPL"].price == 180.0
    assert result["AAPL"].beta == 1.2
    assert result["AAPL"].sector == "Technology"
    assert result["AAPL"].source == "yfinance"


@patch("app.portfolio.price_fetcher.yf.Ticker")
def test_fetch_from_yfinance_no_price(
    mock_ticker: MagicMock,
    price_fetcher: PriceDataFetcher,
) -> None:
    """Test yfinance fetch with no price available."""
    # Mock yfinance response with no price
    mock_ticker.return_value.info = {}

    result = price_fetcher._fetch_from_yfinance(["AAPL"])

    # Now returns PriceData with error set
    assert "AAPL" in result
    assert result["AAPL"].error == "No price data available"
    assert result["AAPL"].price == 0.0


@patch("app.portfolio.price_fetcher.yf.Ticker")
def test_fetch_from_yfinance_exception(
    mock_ticker: MagicMock,
    price_fetcher: PriceDataFetcher,
) -> None:
    """Test yfinance fetch handling exceptions."""
    # Mock yfinance to raise an exception
    mock_ticker.side_effect = Exception("API error")

    result = price_fetcher._fetch_from_yfinance(["AAPL"])

    # Now returns PriceData with error set
    assert "AAPL" in result
    assert result["AAPL"].error is not None
    assert "API error" in result["AAPL"].error
    assert result["AAPL"].price == 0.0


@patch("app.portfolio.price_fetcher.yf.Ticker")
def test_fetch_price_data_with_cache_hit(
    mock_ticker: MagicMock,
    price_fetcher: PriceDataFetcher,
) -> None:
    """Test fetch_price_data uses cache when available."""
    from app.portfolio.models import PriceData

    # Pre-populate cache
    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0),
    }
    price_fetcher._cache_prices(price_data)

    # Fetch (should use cache, not call yfinance)
    result = price_fetcher.fetch_price_data(["AAPL"])

    assert "AAPL" in result
    assert result["AAPL"].price == 180.0

    # yfinance should not have been called
    mock_ticker.assert_not_called()


@patch("app.portfolio.price_fetcher.yf.Ticker")
def test_fetch_price_data_cache_miss(
    mock_ticker: MagicMock,
    price_fetcher: PriceDataFetcher,
) -> None:
    """Test fetch_price_data fetches fresh data on cache miss."""
    # Mock yfinance response
    mock_info = {
        "currentPrice": 180.0,
        "beta": 1.2,
        "sector": "Technology",
    }
    mock_ticker.return_value.info = mock_info

    # Fetch (cache miss)
    result = price_fetcher.fetch_price_data(["AAPL"])

    assert "AAPL" in result
    assert result["AAPL"].price == 180.0

    # Verify data was cached
    df = price_fetcher.storage.query("SELECT * FROM price_cache WHERE symbol = 'AAPL'")
    assert not df.is_empty()
