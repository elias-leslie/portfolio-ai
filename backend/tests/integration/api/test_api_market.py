"""Integration tests for Market API endpoints."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.cache import clear_cache
from app.portfolio.models import PriceData
from app.storage import PortfolioStorage, get_storage


@pytest.fixture(autouse=True)
def clear_response_cache() -> None:
    """Ensure cached API responses don't leak between tests."""
    clear_cache()


@pytest.fixture(autouse=True)
def test_storage() -> Generator[PortfolioStorage]:
    """Get shared storage instance for market API tests."""
    storage = get_storage()
    yield storage


@pytest.fixture
def client() -> Generator[TestClient]:
    """Create a test client, clearing lazy-init caches."""
    import importlib

    # __init__.py shadows submodule names with re-exported routers, so use importlib
    _core_mod = importlib.import_module("app.api.market.core_router")
    _corp_mod = importlib.import_module("app.api.market.corporate_router")
    _hist_mod = importlib.import_module("app.api.market.historical_router")
    _helpers_mod = importlib.import_module("app.api.market._core_helpers")

    _core_mod._state.clear()
    _corp_mod._state.clear()
    _hist_mod._state.clear()
    _helpers_mod._state.clear()

    yield TestClient(app)

    _core_mod._state.clear()
    _corp_mod._state.clear()
    _hist_mod._state.clear()
    _helpers_mod._state.clear()


@patch("app.api.market._core_helpers._get_price_fetcher")
def test_get_market_conditions_success(mock_get_fetcher: Mock, client: TestClient) -> None:
    """Test GET /api/market/conditions with successful data fetch."""
    # Mock price data for market indicators
    mock_fetcher = Mock()
    mock_get_fetcher.return_value = mock_fetcher
    mock_fetcher.fetch_cached_price_data.return_value = {
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

    # Verify the correct symbols were requested for both indicator and sector fetches
    assert mock_fetcher.fetch_cached_price_data.call_count == 2
    indicator_call, sector_call = mock_fetcher.fetch_cached_price_data.call_args_list
    assert indicator_call.args[0] == ["^GSPC", "^VIX", "^TNX", "DX-Y.NYB"]
    assert sector_call.args[0] == [
        "XLK",
        "XLF",
        "XLE",
        "XLV",
        "XLY",
        "XLP",
        "XLI",
        "XLU",
        "XLRE",
        "XLB",
        "XLC",
    ]


@patch("app.api.market._core_helpers._get_price_fetcher")
def test_get_market_conditions_partial_data(mock_get_fetcher: Mock, client: TestClient) -> None:
    """Test GET /api/market/conditions when some data is missing."""
    # Mock with only S&P 500 and VIX available
    mock_fetcher = Mock()
    mock_get_fetcher.return_value = mock_fetcher
    mock_fetcher.fetch_cached_price_data.return_value = {
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


@patch("app.api.market._core_helpers._get_price_fetcher")
def test_get_market_conditions_empty_data(mock_get_fetcher: Mock, client: TestClient) -> None:
    """Test GET /api/market/conditions when no data is available."""
    mock_fetcher = Mock()
    mock_get_fetcher.return_value = mock_fetcher
    mock_fetcher.fetch_cached_price_data.return_value = {}

    response = client.get("/api/market/conditions")

    assert response.status_code == 200
    data = response.json()

    # Verify all prices are None
    assert data["sp500"]["price"] is None
    assert data["vix"]["price"] is None
    assert data["tnx"]["yield"] is None
    assert data["dxy"]["price"] is None


@patch("app.api.market._core_helpers._get_price_fetcher")
def test_get_prices_single_symbol(mock_get_fetcher: Mock, client: TestClient) -> None:
    """Test GET /api/market/prices with a single symbol."""
    mock_fetcher = Mock()
    mock_get_fetcher.return_value = mock_fetcher
    mock_fetcher.fetch_cached_price_data.return_value = {
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
    mock_fetcher.fetch_cached_price_data.assert_called_once_with(["AAPL"])


@patch("app.api.market._core_helpers._get_price_fetcher")
def test_get_prices_multiple_symbols(mock_get_fetcher: Mock, client: TestClient) -> None:
    """Test GET /api/market/prices with multiple symbols."""
    mock_fetcher = Mock()
    mock_get_fetcher.return_value = mock_fetcher
    mock_fetcher.fetch_cached_price_data.return_value = {
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


@patch("app.api.market._core_helpers._get_price_fetcher")
def test_get_prices_with_whitespace(mock_get_fetcher: Mock, client: TestClient) -> None:
    """Test GET /api/market/prices handles whitespace in symbols."""
    mock_fetcher = Mock()
    mock_get_fetcher.return_value = mock_fetcher
    mock_fetcher.fetch_cached_price_data.return_value = {
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
    mock_fetcher.fetch_cached_price_data.assert_called_once_with(["AAPL", "GOOGL"])


@patch("app.api.market._core_helpers._get_price_fetcher")
def test_get_prices_with_optional_fields_none(mock_get_fetcher: Mock, client: TestClient) -> None:
    """Test GET /api/market/prices when optional fields are None."""
    mock_fetcher = Mock()
    mock_get_fetcher.return_value = mock_fetcher
    mock_fetcher.fetch_cached_price_data.return_value = {
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


@patch("app.api.market._core_helpers._get_price_fetcher")
def test_get_prices_empty_result(mock_get_fetcher: Mock, client: TestClient) -> None:
    """Test GET /api/market/prices when no prices are found."""
    mock_fetcher = Mock()
    mock_get_fetcher.return_value = mock_fetcher
    mock_fetcher.fetch_cached_price_data.return_value = {}

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


@patch("app.api.market._core_helpers._get_price_fetcher")
def test_market_api_response_structure(mock_get_fetcher: Mock, client: TestClient) -> None:
    """Test that API responses have correct structure and field types."""
    mock_fetcher = Mock()
    mock_get_fetcher.return_value = mock_fetcher
    mock_fetcher.fetch_cached_price_data.return_value = {
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
