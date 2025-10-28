"""Integration tests for Market API endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.portfolio.models import PriceData
from app.storage import DuckDBStorage


@pytest.fixture
def test_storage() -> DuckDBStorage:
    """Create a DuckDBStorage instance with a temporary database."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_api_market.duckdb"

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
def client(test_storage: DuckDBStorage) -> TestClient:
    """Create a test client with patched storage."""
    # Patch storage at multiple import points
    with (
        patch("app.api.market.storage", test_storage),
        patch("app.api.market.get_storage", return_value=test_storage),
    ):
        yield TestClient(app)


@patch("app.api.market.price_fetcher.fetch_price_data")
def test_get_market_conditions_success(mock_fetch: Mock, client: TestClient) -> None:
    """Test GET /api/market/conditions with successful data fetch."""
    # Mock price data for market indicators
    mock_fetch.return_value = {
        "^GSPC": PriceData(
            symbol="^GSPC",
            price=4500.50,
            beta=None,
            volatility=None,
            sector=None,
        ),
        "^VIX": PriceData(symbol="^VIX", price=18.5, beta=None, volatility=None, sector=None),
        "^TNX": PriceData(symbol="^TNX", price=4.25, beta=None, volatility=None, sector=None),
        "DX-Y.NYB": PriceData(
            symbol="DX-Y.NYB", price=103.5, beta=None, volatility=None, sector=None
        ),
    }

    response = client.get("/api/market/conditions")

    assert response.status_code == 200
    data = response.json()

    # Verify all market indicators are present
    assert "sp500" in data
    assert data["sp500"]["price"] == 4500.50

    assert "vix" in data
    assert data["vix"]["price"] == 18.5

    assert "tnx" in data
    assert data["tnx"]["yield"] == 4.25

    assert "dxy" in data
    assert data["dxy"]["price"] == 103.5

    # Verify the correct symbols were requested
    mock_fetch.assert_called_once_with(["^GSPC", "^VIX", "^TNX", "DX-Y.NYB"])


@patch("app.api.market.price_fetcher.fetch_price_data")
def test_get_market_conditions_partial_data(mock_fetch: Mock, client: TestClient) -> None:
    """Test GET /api/market/conditions when some data is missing."""
    # Mock with only S&P 500 and VIX available
    mock_fetch.return_value = {
        "^GSPC": PriceData(symbol="^GSPC", price=4500.50, beta=None, volatility=None, sector=None),
        "^VIX": PriceData(symbol="^VIX", price=18.5, beta=None, volatility=None, sector=None),
    }

    response = client.get("/api/market/conditions")

    assert response.status_code == 200
    data = response.json()

    # Verify available data is present
    assert data["sp500"]["price"] == 4500.50
    assert data["vix"]["price"] == 18.5

    # Verify missing data is None
    assert data["tnx"]["yield"] is None
    assert data["dxy"]["price"] is None


@patch("app.api.market.price_fetcher.fetch_price_data")
def test_get_market_conditions_empty_data(mock_fetch: Mock, client: TestClient) -> None:
    """Test GET /api/market/conditions when no data is available."""
    mock_fetch.return_value = {}

    response = client.get("/api/market/conditions")

    assert response.status_code == 200
    data = response.json()

    # Verify all prices are None
    assert data["sp500"]["price"] is None
    assert data["vix"]["price"] is None
    assert data["tnx"]["yield"] is None
    assert data["dxy"]["price"] is None


@patch("app.api.market.price_fetcher.fetch_price_data")
def test_get_prices_single_symbol(mock_fetch: Mock, client: TestClient) -> None:
    """Test GET /api/market/prices with a single symbol."""
    mock_fetch.return_value = {
        "AAPL": PriceData(
            symbol="AAPL",
            price=185.50,
            beta=1.2,
            volatility=0.25,
            sector="Technology",
        ),
    }

    response = client.get("/api/market/prices?symbols=AAPL")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 1
    assert "AAPL" in data["prices"]

    aapl = data["prices"]["AAPL"]
    assert aapl["symbol"] == "AAPL"
    assert aapl["price"] == 185.50
    assert aapl["beta"] == 1.2
    assert aapl["volatility"] == 0.25
    assert aapl["sector"] == "Technology"

    # Verify price fetcher was called with uppercase symbol
    mock_fetch.assert_called_once_with(["AAPL"])


@patch("app.api.market.price_fetcher.fetch_price_data")
def test_get_prices_multiple_symbols(mock_fetch: Mock, client: TestClient) -> None:
    """Test GET /api/market/prices with multiple symbols."""
    mock_fetch.return_value = {
        "AAPL": PriceData(
            symbol="AAPL",
            price=185.50,
            beta=1.2,
            volatility=0.25,
            sector="Technology",
        ),
        "GOOGL": PriceData(
            symbol="GOOGL",
            price=142.30,
            beta=1.1,
            volatility=0.22,
            sector="Technology",
        ),
        "MSFT": PriceData(
            symbol="MSFT",
            price=410.75,
            beta=0.9,
            volatility=0.20,
            sector="Technology",
        ),
    }

    response = client.get("/api/market/prices?symbols=AAPL,GOOGL,MSFT")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 3
    assert "AAPL" in data["prices"]
    assert "GOOGL" in data["prices"]
    assert "MSFT" in data["prices"]

    # Verify all price data is present
    assert data["prices"]["AAPL"]["price"] == 185.50
    assert data["prices"]["GOOGL"]["price"] == 142.30
    assert data["prices"]["MSFT"]["price"] == 410.75


@patch("app.api.market.price_fetcher.fetch_price_data")
def test_get_prices_with_whitespace(mock_fetch: Mock, client: TestClient) -> None:
    """Test GET /api/market/prices handles whitespace in symbols."""
    mock_fetch.return_value = {
        "AAPL": PriceData(
            symbol="AAPL",
            price=185.50,
            beta=1.2,
            volatility=0.25,
            sector="Technology",
        ),
        "GOOGL": PriceData(
            symbol="GOOGL",
            price=142.30,
            beta=1.1,
            volatility=0.22,
            sector="Technology",
        ),
    }

    response = client.get("/api/market/prices?symbols= AAPL , googl ")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 2
    assert "AAPL" in data["prices"]
    assert "GOOGL" in data["prices"]

    # Verify symbols were cleaned (whitespace stripped, uppercase)
    mock_fetch.assert_called_once_with(["AAPL", "GOOGL"])


@patch("app.api.market.price_fetcher.fetch_price_data")
def test_get_prices_with_optional_fields_none(mock_fetch: Mock, client: TestClient) -> None:
    """Test GET /api/market/prices when optional fields are None."""
    mock_fetch.return_value = {
        "AAPL": PriceData(
            symbol="AAPL",
            price=185.50,
            beta=None,  # No beta available
            volatility=None,  # No volatility available
            sector=None,  # No sector available
        ),
    }

    response = client.get("/api/market/prices?symbols=AAPL")

    assert response.status_code == 200
    data = response.json()

    aapl = data["prices"]["AAPL"]
    assert aapl["price"] == 185.50
    assert aapl["beta"] is None
    assert aapl["volatility"] is None
    assert aapl["sector"] is None


@patch("app.api.market.price_fetcher.fetch_price_data")
def test_get_prices_empty_result(mock_fetch: Mock, client: TestClient) -> None:
    """Test GET /api/market/prices when no prices are found."""
    mock_fetch.return_value = {}

    response = client.get("/api/market/prices?symbols=INVALID")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 0
    assert data["prices"] == {}


def test_get_prices_missing_symbols_parameter(client: TestClient) -> None:
    """Test GET /api/market/prices without symbols parameter."""
    response = client.get("/api/market/prices")

    # Should return 422 validation error (required field missing)
    assert response.status_code == 422


@patch("app.api.market.price_fetcher.fetch_price_data")
def test_market_api_response_structure(mock_fetch: Mock, client: TestClient) -> None:
    """Test that API responses have correct structure and field types."""
    mock_fetch.return_value = {
        "AAPL": PriceData(
            symbol="AAPL",
            price=185.50,
            beta=1.2,
            volatility=0.25,
            sector="Technology",
        ),
    }

    response = client.get("/api/market/prices?symbols=AAPL")

    assert response.status_code == 200
    data = response.json()

    # Verify top-level structure
    assert "prices" in data
    assert "count" in data
    assert isinstance(data["prices"], dict)
    assert isinstance(data["count"], int)

    # Verify price object structure
    price_obj = data["prices"]["AAPL"]
    assert "symbol" in price_obj
    assert "price" in price_obj
    assert "beta" in price_obj
    assert "volatility" in price_obj
    assert "sector" in price_obj
