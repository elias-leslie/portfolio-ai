"""Unit tests for PriceDataFetcher."""

from __future__ import annotations

import datetime as dt
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import polars as pl
import pytest

from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import PortfolioStorage


@pytest.fixture
def storage() -> PortfolioStorage:
    """Create a PortfolioStorage instance with a temporary database."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"

    # Create fresh storage instance (bypass singleton)
    from app.storage.connection import ConnectionManager
    from app.storage.ingestion import IngestionManager
    from app.storage.metadata import MetadataManager
    from app.storage.queries import QueryManager
    from app.storage.schema import SchemaManager

    storage_inst = PortfolioStorage.__new__(PortfolioStorage)
    storage_inst.connection_mgr = ConnectionManager()
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
def price_fetcher(storage: PortfolioStorage) -> PriceDataFetcher:
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


def test_fetch_fresh_prices_success(
    price_fetcher: PriceDataFetcher,
) -> None:
    """Test successful fetch using MultiSourceFetcher."""
    # Mock the MultiSourceFetcher.fetch_with_fallback method
    mock_df = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "as_of_date": [dt.date.today()],
            "payload": [json.dumps({"price": 180.0, "beta": 1.2, "sector": "Technology"})],
            "source": ["yfinance"],
        }
    )

    with patch.object(
        price_fetcher.multi_source_fetcher, "fetch_with_fallback", return_value=(mock_df, {})
    ):
        result = price_fetcher._fetch_fresh_prices(["AAPL"])

        assert "AAPL" in result
        assert result["AAPL"].price == 180.0
        assert result["AAPL"].beta == 1.2
        assert result["AAPL"].sector == "Technology"
        assert result["AAPL"].source == "yfinance"


def test_fetch_fresh_prices_no_price(
    price_fetcher: PriceDataFetcher,
) -> None:
    """Test fetch with no price available in response."""
    # Mock response with no price (price = 0)
    mock_df = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "as_of_date": [dt.date.today()],
            "payload": [json.dumps({"price": 0, "sector": "Technology"})],
            "source": ["yfinance"],
        }
    )

    with patch.object(
        price_fetcher.multi_source_fetcher, "fetch_with_fallback", return_value=(mock_df, {})
    ):
        result = price_fetcher._fetch_fresh_prices(["AAPL"])

        # Now returns PriceData with error set
        assert "AAPL" in result
        assert result["AAPL"].error == "No price data available"
        assert result["AAPL"].price == 0.0


def test_fetch_fresh_prices_all_sources_failed(
    price_fetcher: PriceDataFetcher,
) -> None:
    """Test handling when all sources fail."""
    # Mock all sources failing (returns None with errors)
    errors_by_source = {"yfinance": ["API error"], "polygon": ["Service unavailable"]}

    with patch.object(
        price_fetcher.multi_source_fetcher,
        "fetch_with_fallback",
        return_value=(None, errors_by_source),
    ):
        result = price_fetcher._fetch_fresh_prices(["AAPL"])

        # Now returns PriceData with error set
        assert "AAPL" in result
        assert result["AAPL"].error is not None
        assert "All sources failed" in result["AAPL"].error
        assert result["AAPL"].price == 0.0


def test_fetch_price_data_with_cache_hit(
    price_fetcher: PriceDataFetcher,
) -> None:
    """Test fetch_price_data uses cache when available."""
    from app.portfolio.models import PriceData

    # Pre-populate cache
    price_data = {
        "AAPL": PriceData(symbol="AAPL", price=180.0),
    }
    price_fetcher._cache_prices(price_data)

    # Mock the fetch_with_fallback to ensure it's NOT called
    with patch.object(price_fetcher.multi_source_fetcher, "fetch_with_fallback") as mock_fetch:
        # Fetch (should use cache, not call fetch_with_fallback)
        result = price_fetcher.fetch_price_data(["AAPL"])

        assert "AAPL" in result
        assert result["AAPL"].price == 180.0

        # MultiSourceFetcher should not have been called
        mock_fetch.assert_not_called()


def test_fetch_price_data_cache_miss(
    price_fetcher: PriceDataFetcher,
) -> None:
    """Test fetch_price_data fetches fresh data on cache miss."""
    # Mock MultiSourceFetcher response
    mock_df = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "as_of_date": [dt.date.today()],
            "payload": [json.dumps({"price": 180.0, "beta": 1.2, "sector": "Technology"})],
            "source": ["yfinance"],
        }
    )

    with patch.object(
        price_fetcher.multi_source_fetcher, "fetch_with_fallback", return_value=(mock_df, {})
    ):
        # Fetch (cache miss)
        result = price_fetcher.fetch_price_data(["AAPL"])

        assert "AAPL" in result
        assert result["AAPL"].price == 180.0

        # Verify data was cached
        df = price_fetcher.storage.query("SELECT * FROM price_cache WHERE symbol = 'AAPL'")
        assert not df.is_empty()


def test_fetch_partial_success(
    price_fetcher: PriceDataFetcher,
) -> None:
    """Test partial success (some symbols succeed, some fail)."""
    # Mock response where AAPL succeeds but INVALID has no data
    mock_df = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "as_of_date": [dt.date.today()],
            "payload": [json.dumps({"price": 180.0, "beta": 1.2, "sector": "Technology"})],
            "source": ["yfinance"],
        }
    )

    with patch.object(
        price_fetcher.multi_source_fetcher, "fetch_with_fallback", return_value=(mock_df, {})
    ):
        result = price_fetcher._fetch_fresh_prices(["AAPL", "INVALID"])

        # AAPL should succeed
        assert "AAPL" in result
        assert result["AAPL"].price == 180.0
        assert result["AAPL"].error is None

        # INVALID should not be in result (not returned by source)
        assert "INVALID" not in result


def _insert_day_bars(
    storage: PortfolioStorage,
    ticker: str,
    start_date: datetime,
    closes: list[float],
) -> None:
    rows = []
    for idx, close in enumerate(closes):
        current_date = (start_date + timedelta(days=idx)).date()
        rows.append(
            {
                "ticker": ticker,
                "date": current_date,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 1_000_000,
                "vwap": close,
                "source": "test",
                "ingest_run_id": None,
            }
        )

    storage.insert_dataframe("day_bars", pl.DataFrame(rows), mode="append")


def test_fresh_prices_compute_risk_metrics_from_history(
    price_fetcher: PriceDataFetcher,
) -> None:
    """When upstream data lacks beta/volatility, compute from local history."""

    market_returns = np.array(
        [0.01, -0.005, 0.012, -0.004, 0.008, -0.006, 0.009, -0.007, 0.011, -0.005]
    )
    symbol_returns = market_returns * 1.4

    market_closes = [100.0]
    symbol_closes = [150.0]
    for mr, sr in zip(market_returns, symbol_returns, strict=True):
        market_closes.append(market_closes[-1] * (1 + mr))
        symbol_closes.append(symbol_closes[-1] * (1 + sr))

    base_date = datetime.now(UTC) - timedelta(days=len(market_returns) + 5)
    _insert_day_bars(price_fetcher.storage, "SPY", base_date, market_closes)
    _insert_day_bars(price_fetcher.storage, "AAPL", base_date, symbol_closes)

    mock_df = pl.DataFrame(
        {
            "ticker": ["AAPL"],
            "as_of_date": [dt.date.today()],
            "payload": [json.dumps({"price": 180.0, "sector": "Technology"})],
            "source": ["yfinance"],
        }
    )

    with patch.object(
        price_fetcher.multi_source_fetcher, "fetch_with_fallback", return_value=(mock_df, {})
    ):
        result = price_fetcher._fetch_fresh_prices(["AAPL"])

    price_data = result["AAPL"]
    assert price_data.beta is not None
    assert price_data.volatility is not None
    assert pytest.approx(price_data.beta, rel=0.2) == 1.4
    assert price_data.volatility > 0
