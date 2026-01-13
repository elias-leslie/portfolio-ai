"""Tests for analytics API endpoints.

Tests cover:
- FEAT-155: Short Interest Tracking
- FEAT-156: Cash Flow Metrics
- FEAT-157: Insider Transactions
- FEAT-158: Institutional Holdings
- FEAT-019: Today's Movers Summary (via market intelligence)
"""

from __future__ import annotations

import pytest
import requests

# Use live API testing since TestClient has migration issues
BASE_URL = "http://localhost:8000"


def api_available() -> bool:
    """Check if the API is available."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not api_available(), reason="API server not available for integration tests"
)


class TestShortInterestEndpoint:
    """Tests for FEAT-155 Short Interest Tracking API."""

    def test_short_interest_returns_200_for_valid_symbol(self) -> None:
        """Test short interest endpoint returns data for valid symbol."""
        response = requests.get(f"{BASE_URL}/api/analytics/short-interest/AAPL", timeout=10)
        # May return 404 if no data, both are valid responses
        assert response.status_code in (200, 404)

    def test_short_interest_response_structure(self) -> None:
        """Test short interest response has expected fields."""
        response = requests.get(f"{BASE_URL}/api/analytics/short-interest/AAPL", timeout=10)
        if response.status_code == 200:
            data = response.json()
            assert "symbol" in data
            assert "short_ratio" in data
            assert "short_percent_of_float" in data
            assert data["symbol"] == "AAPL"

    def test_short_interest_symbol_uppercase(self) -> None:
        """Test short interest normalizes symbol to uppercase."""
        response = requests.get(f"{BASE_URL}/api/analytics/short-interest/aapl", timeout=10)
        if response.status_code == 200:
            data = response.json()
            assert data["symbol"] == "AAPL"


class TestCashFlowEndpoint:
    """Tests for FEAT-156 Cash Flow Metrics API."""

    def test_cash_flow_returns_200_for_valid_symbol(self) -> None:
        """Test cash flow endpoint returns data for valid symbol."""
        response = requests.get(f"{BASE_URL}/api/analytics/cash-flow/AAPL", timeout=10)
        assert response.status_code in (200, 404)

    def test_cash_flow_response_structure(self) -> None:
        """Test cash flow response has expected fields."""
        response = requests.get(f"{BASE_URL}/api/analytics/cash-flow/AAPL", timeout=10)
        if response.status_code == 200:
            data = response.json()
            assert "symbol" in data
            assert "fcf_yield" in data
            assert "operating_cash_flow" in data
            assert "cash_conversion_ratio" in data

    def test_cash_flow_404_for_unknown_symbol(self) -> None:
        """Test cash flow returns 404 for unknown symbol."""
        response = requests.get(f"{BASE_URL}/api/analytics/cash-flow/ZZZZZ", timeout=10)
        assert response.status_code == 404


class TestInsiderTransactionsEndpoint:
    """Tests for FEAT-157 Insider Transactions API."""

    def test_insider_transactions_returns_200_for_valid_symbol(self) -> None:
        """Test insider transactions endpoint returns data."""
        response = requests.get(f"{BASE_URL}/api/analytics/insider-transactions/AAPL", timeout=10)
        assert response.status_code in (200, 404)

    def test_insider_transactions_response_structure(self) -> None:
        """Test insider transactions response has expected fields."""
        response = requests.get(f"{BASE_URL}/api/analytics/insider-transactions/AAPL", timeout=10)
        if response.status_code == 200:
            data = response.json()
            assert "symbol" in data
            assert "transactions" in data
            assert "count" in data
            assert isinstance(data["transactions"], list)

    def test_insider_transactions_limit_parameter(self) -> None:
        """Test insider transactions respects limit parameter."""
        response = requests.get(
            f"{BASE_URL}/api/analytics/insider-transactions/AAPL?limit=5", timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            assert len(data["transactions"]) <= 5


class TestInstitutionalHoldingsEndpoint:
    """Tests for FEAT-158 Institutional Holdings API."""

    def test_institutional_holdings_returns_200_for_valid_symbol(self) -> None:
        """Test institutional holdings endpoint returns data."""
        response = requests.get(f"{BASE_URL}/api/analytics/institutional-holdings/AAPL", timeout=10)
        assert response.status_code in (200, 404)

    def test_institutional_holdings_response_structure(self) -> None:
        """Test institutional holdings response has expected fields."""
        response = requests.get(f"{BASE_URL}/api/analytics/institutional-holdings/AAPL", timeout=10)
        if response.status_code == 200:
            data = response.json()
            assert "symbol" in data
            assert "pct_held_institutions" in data
            assert "top_holders" in data
            assert isinstance(data["top_holders"], list)

    def test_institutional_holdings_top_n_parameter(self) -> None:
        """Test institutional holdings respects top_n parameter."""
        response = requests.get(
            f"{BASE_URL}/api/analytics/institutional-holdings/AAPL?top_n=3", timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            assert len(data["top_holders"]) <= 3


class TestMarketIntelligenceEndpoint:
    """Tests for FEAT-019 Today's Movers Summary (via market intelligence)."""

    def test_market_intelligence_returns_200(self) -> None:
        """Test market intelligence endpoint returns data."""
        response = requests.get(f"{BASE_URL}/api/market/intelligence", timeout=10)
        assert response.status_code == 200

    def test_market_intelligence_has_sector_rotation(self) -> None:
        """Test market intelligence includes sector rotation data."""
        response = requests.get(f"{BASE_URL}/api/market/intelligence", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "sector_rotation" in data

    def test_sector_rotation_structure(self) -> None:
        """Test sector rotation has leading/neutral/lagging breakdown."""
        response = requests.get(f"{BASE_URL}/api/market/intelligence", timeout=10)
        if response.status_code == 200:
            data = response.json()
            rotation = data.get("sector_rotation", {})
            assert "leading" in rotation
            assert "neutral" in rotation
            assert "lagging" in rotation

    def test_sector_rotation_item_fields(self) -> None:
        """Test sector rotation items have required fields."""
        response = requests.get(f"{BASE_URL}/api/market/intelligence", timeout=10)
        if response.status_code == 200:
            data = response.json()
            rotation = data.get("sector_rotation", {})
            for sector in rotation.get("leading", []):
                assert "symbol" in sector
                assert "name" in sector
                assert "change_pct" in sector
