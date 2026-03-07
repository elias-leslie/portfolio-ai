"""Integration test for portfolio CRUD flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.cache import clear_cache
from app.storage import get_storage


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_database() -> Generator[None]:
    """Clean up database before and after each test."""
    storage = get_storage()

    # Clean up before test
    with storage.connection() as conn:
        conn.execute("DELETE FROM portfolio_positions")
        conn.execute("DELETE FROM portfolio_accounts")
        conn.execute("DELETE FROM price_cache")  # Clear price cache too

    yield

    # Clean up after test
    with storage.connection() as conn:
        conn.execute("DELETE FROM portfolio_positions")
        conn.execute("DELETE FROM portfolio_accounts")
        conn.execute("DELETE FROM price_cache")  # Clear price cache too


@pytest.fixture(autouse=True)
def clear_response_cache() -> None:
    """Ensure cached analytics responses don't leak between tests."""
    clear_cache()


@pytest.fixture(autouse=True)
def mock_price_data() -> Generator[None]:
    """Mock price fetcher to return valid price data for test symbols."""
    from app.portfolio.models import PriceData
    from app.portfolio.price_fetcher import PriceDataFetcher

    # Create a function that returns mock PriceData objects
    def mock_fetch_fresh_prices(symbols: list[str]) -> dict[str, PriceData]:
        """Return mock price data for requested symbols."""
        price_map = {"AAPL": 180.0, "MSFT": 350.0, "GOOGL": 140.0}

        return {
            symbol: PriceData(
                symbol=symbol,
                price=price_map.get(symbol, 100.0),
                beta=1.2,
                sector="Technology",
                source="yfinance",
                error=None,
            )
            for symbol in symbols
        }

    # Patch the _fetch_fresh_prices method
    with patch.object(PriceDataFetcher, "_fetch_fresh_prices", side_effect=mock_fetch_fresh_prices):
        yield


def test_portfolio_crud_integration_flow(client: TestClient) -> None:
    """Test complete portfolio CRUD flow: add account → add position → fetch analytics → delete position."""

    # Step 1: Create an account
    account_response = client.post(
        "/api/portfolio/account", json={"name": "Test IRA", "account_type": "IRA"}
    )
    assert account_response.status_code == 200
    account_data = account_response.json()
    account_id = account_data["id"]
    assert account_data["name"] == "Test IRA"
    assert account_data["account_type"] == "IRA"

    # Step 2: Add a position
    position_response = client.post(
        "/api/portfolio/position",
        json={
            "account_id": account_id,
            "symbol": "AAPL",
            "shares": 100,
            "cost_basis": 150.00,
            "position_type": "long",
        },
    )
    assert position_response.status_code == 200
    position_data = position_response.json()
    position_id = position_data["id"]
    assert position_data["symbol"] == "AAPL"
    assert position_data["shares"] == 100
    assert position_data["cost_basis"] == 150.00

    # Step 3: Get portfolio (should include the position with current values)
    portfolio_response = client.get("/api/portfolio/")
    assert portfolio_response.status_code == 200
    portfolio = portfolio_response.json()
    assert len(portfolio["positions"]) == 1
    assert portfolio["positions"][0]["symbol"] == "AAPL"
    assert portfolio["positions"][0]["shares"] == 100
    assert portfolio["total_cost_basis"] == 15000.00  # 100 * 150

    # Step 4: Fetch analytics
    analytics_response = client.get("/api/portfolio/analytics")
    assert analytics_response.status_code == 200
    analytics = analytics_response.json()
    assert analytics["num_positions"] == 1
    assert analytics["num_symbols"] == 1
    assert analytics["portfolio_value"]["total_cost_basis"] == 15000.00
    assert "portfolio_beta" in analytics
    assert "sector_exposure" in analytics
    assert "concentration" in analytics
    assert "risk_profile" in analytics
    assert "diversification_score" in analytics
    assert "top_performers" in analytics
    assert "bottom_performers" in analytics

    # Step 5: Add a second position
    position2_response = client.post(
        "/api/portfolio/position",
        json={
            "account_id": account_id,
            "symbol": "MSFT",
            "shares": 50,
            "cost_basis": 300.00,
            "position_type": "long",
        },
    )
    assert position2_response.status_code == 200

    # Step 6: Verify portfolio now has 2 positions
    portfolio_response = client.get("/api/portfolio/")
    assert portfolio_response.status_code == 200
    portfolio = portfolio_response.json()
    assert len(portfolio["positions"]) == 2
    # Verify we have both symbols
    symbols = [p["symbol"] for p in portfolio["positions"]]
    assert "AAPL" in symbols
    assert "MSFT" in symbols

    # Step 7: Delete the first position
    delete_response = client.delete(f"/api/portfolio/position/{position_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"

    # Step 8: Verify portfolio now has 1 position
    portfolio_response = client.get("/api/portfolio/")
    assert portfolio_response.status_code == 200
    portfolio = portfolio_response.json()
    assert len(portfolio["positions"]) == 1
    assert portfolio["positions"][0]["symbol"] == "MSFT"

    # Step 9: Delete the second position
    position2_id = position2_response.json()["id"]
    delete_response = client.delete(f"/api/portfolio/position/{position2_id}")
    assert delete_response.status_code == 200

    # Step 10: Verify portfolio is now empty
    portfolio_response = client.get("/api/portfolio/")
    assert portfolio_response.status_code == 200
    portfolio = portfolio_response.json()
    assert len(portfolio["positions"]) == 0
    assert portfolio["total_value"] == 0
    assert portfolio["total_cost_basis"] == 0


def test_portfolio_multiple_accounts_flow(client: TestClient) -> None:
    """Test portfolio with multiple accounts."""

    # Create two accounts
    account1_response = client.post(
        "/api/portfolio/account", json={"name": "IRA Account", "account_type": "IRA"}
    )
    account1_id = account1_response.json()["id"]

    account2_response = client.post(
        "/api/portfolio/account", json={"name": "Taxable Account", "account_type": "Taxable"}
    )
    account2_id = account2_response.json()["id"]

    # Add positions to each account
    client.post(
        "/api/portfolio/position",
        json={
            "account_id": account1_id,
            "symbol": "AAPL",
            "shares": 100,
            "cost_basis": 150.00,
            "position_type": "long",
        },
    )

    client.post(
        "/api/portfolio/position",
        json={
            "account_id": account2_id,
            "symbol": "GOOGL",
            "shares": 50,
            "cost_basis": 2000.00,
            "position_type": "long",
        },
    )

    # Verify portfolio aggregates both accounts
    portfolio_response = client.get("/api/portfolio/")
    assert portfolio_response.status_code == 200
    portfolio = portfolio_response.json()
    assert len(portfolio["positions"]) == 2

    # Verify analytics includes both positions
    analytics_response = client.get("/api/portfolio/analytics")
    assert analytics_response.status_code == 200
    analytics = analytics_response.json()
    assert analytics["num_positions"] == 2
    assert analytics["num_symbols"] == 2


def test_portfolio_totals_include_account_cash_balances(client: TestClient) -> None:
    """Live portfolio totals should include cash reserves alongside positions."""
    account_response = client.post(
        "/api/portfolio/account", json={"name": "Cash IRA", "account_type": "IRA"}
    )
    assert account_response.status_code == 200
    account = account_response.json()
    account_id = account["id"]

    storage = get_storage()
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE portfolio_accounts
            SET cash_balance = $1,
                initial_cash = $1
            WHERE id = $2
            """,
            [5000.0, account_id],
        )
        conn.commit()

    position_response = client.post(
        "/api/portfolio/position",
        json={
            "account_id": account_id,
            "symbol": "AAPL",
            "shares": 10,
            "cost_basis": 150.00,
            "position_type": "long",
        },
    )
    assert position_response.status_code == 200

    accounts_response = client.get("/api/portfolio/accounts")
    assert accounts_response.status_code == 200
    accounts = accounts_response.json()
    assert accounts[0]["cash_balance"] == 5000.0

    portfolio_response = client.get("/api/portfolio")
    assert portfolio_response.status_code == 200
    portfolio = portfolio_response.json()
    assert portfolio["cash_balance_total"] == 5000.0
    assert portfolio["total_cost_basis"] == 6500.0
    assert portfolio["total_gain"] == 300.0
    assert portfolio["total_value"] == 6800.0
    assert portfolio["total_gain_pct"] == pytest.approx((300.0 / 6500.0) * 100)


def test_portfolio_returns_cash_only_accounts(client: TestClient) -> None:
    """Cash-only live accounts should still appear in totals and account responses."""
    account_response = client.post(
        "/api/portfolio/account", json={"name": "Roth Cash", "account_type": "Roth"}
    )
    assert account_response.status_code == 200
    account = account_response.json()
    account_id = account["id"]

    storage = get_storage()
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE portfolio_accounts
            SET cash_balance = $1,
                initial_cash = $1
            WHERE id = $2
            """,
            [47880.13, account_id],
        )
        conn.commit()

    portfolio_response = client.get("/api/portfolio")
    assert portfolio_response.status_code == 200
    portfolio = portfolio_response.json()
    assert portfolio["positions"] == []
    assert portfolio["cash_balance_total"] == 47880.13
    assert portfolio["total_value"] == 47880.13
    assert portfolio["total_cost_basis"] == 47880.13
    assert portfolio["total_gain"] == 0.0
    assert portfolio["total_gain_pct"] == 0.0

    accounts_response = client.get("/api/portfolio/accounts")
    assert accounts_response.status_code == 200
    accounts = accounts_response.json()
    assert accounts[0]["name"] == "Roth Cash"
    assert accounts[0]["cash_balance"] == 47880.13


def test_portfolio_cache_invalidation_handles_slash_variants(client: TestClient) -> None:
    """Creating a position should invalidate both /api/portfolio and /api/portfolio/ cache entries."""
    empty_response = client.get("/api/portfolio")
    assert empty_response.status_code == 200
    assert empty_response.headers["x-cache-hit"] == "false"
    assert empty_response.json()["positions"] == []

    cached_empty_response = client.get("/api/portfolio")
    assert cached_empty_response.status_code == 200
    assert cached_empty_response.headers["x-cache-hit"] == "true"
    assert cached_empty_response.json()["positions"] == []

    account_response = client.post(
        "/api/portfolio/account",
        json={"name": "Slash Cache IRA", "account_type": "IRA"},
    )
    account_id = account_response.json()["id"]

    position_response = client.post(
        "/api/portfolio/position",
        json={
            "account_id": account_id,
            "symbol": "AAPL",
            "shares": 5,
            "cost_basis": 150.00,
            "position_type": "long",
        },
    )
    assert position_response.status_code == 200

    refreshed_response = client.get("/api/portfolio")
    assert refreshed_response.status_code == 200
    assert refreshed_response.headers["x-cache-hit"] == "false"
    payload = refreshed_response.json()
    assert len(payload["positions"]) == 1
    assert payload["positions"][0]["symbol"] == "AAPL"


def test_portfolio_error_handling(client: TestClient) -> None:
    """Test error handling in portfolio CRUD operations."""

    # Try to add position with non-existent account
    response = client.post(
        "/api/portfolio/position",
        json={
            "account_id": "non-existent-id",
            "symbol": "AAPL",
            "shares": 100,
            "cost_basis": 150.00,
            "position_type": "long",
        },
    )
    assert response.status_code == 404
    assert "Account not found" in response.json()["detail"]

    # Empty analytics should return a valid zero-state payload instead of a 404.
    response = client.get("/api/portfolio/analytics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["num_positions"] == 0
    assert payload["num_symbols"] == 0
    assert payload["portfolio_value"]["total_value"] == 0
    assert payload["top_performers"] == []
    assert payload["bottom_performers"] == []

    # Delete non-existent position (should be idempotent)
    response = client.delete("/api/portfolio/position/non-existent-id")
    assert response.status_code == 200


def test_recommendations_accept_trailing_slash(client: TestClient) -> None:
    """Frontend polling should not 404 on the slash variant of recommendations."""
    response = client.get("/api/recommendations/?min_strength=6&limit=6&signal_type=BUY")

    assert response.status_code == 200
    payload = response.json()
    assert "recommendations" in payload
    assert "summary" in payload
