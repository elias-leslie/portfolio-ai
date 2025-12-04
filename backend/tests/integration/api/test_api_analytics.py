"""Integration tests for Analytics API endpoints."""

from __future__ import annotations

from unittest.mock import patch

import polars as pl
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


@patch("app.api.analytics.calculate_rvol")
def test_get_rvol_success(mock_calculate_rvol, client: TestClient) -> None:
    """Test successful RVOL retrieval."""
    # Mock the calculate_rvol function
    mock_calculate_rvol.return_value = 1.8

    # Make request
    response = client.get("/api/analytics/rvol/AAPL?date=2025-01-15")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["date"] == "2025-01-15"
    assert data["rvol"] == 1.8
    assert "interpretation" in data


@patch("app.api.analytics.calculate_rvol")
def test_get_rvol_not_found(mock_calculate_rvol, client: TestClient) -> None:
    """Test RVOL retrieval when ticker not found."""
    # Mock the calculate_rvol function to return None
    mock_calculate_rvol.return_value = None

    # Make request
    response = client.get("/api/analytics/rvol/INVALID?date=2025-01-15")

    # Verify
    assert response.status_code == 404
    assert "Could not calculate RVOL" in response.json()["detail"]


@patch("app.api.analytics.calculate_rvol")
def test_get_rvol_invalid_date(mock_calculate_rvol, client: TestClient) -> None:
    """Test RVOL retrieval with invalid date format."""
    # Make request with invalid date
    response = client.get("/api/analytics/rvol/AAPL?date=invalid-date")

    # Verify
    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]


@patch("app.api.analytics.get_sector_rotation")
def test_get_sectors_rotation_success(mock_get_sector_rotation, client: TestClient) -> None:
    """Test successful sector rotation retrieval."""
    # Mock the get_sector_rotation function
    mock_df = pl.DataFrame(
        {
            "sector": ["Technology", "Healthcare"],
            "momentum_5d": [5.2, 3.1],
            "momentum_20d": [12.5, 8.3],
            "num_stocks": [50, 30],
            "avg_volume": [10000000.0, 5000000.0],
        }
    )
    mock_get_sector_rotation.return_value = mock_df

    # Make request
    response = client.get("/api/analytics/sectors/rotation?date=2025-01-15")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2025-01-15"
    assert data["count"] == 2
    assert len(data["sectors"]) == 2
    assert data["sectors"][0]["sector"] == "Technology"
    assert data["sectors"][0]["momentum_20d"] == 12.5


@patch("app.api.analytics.get_sector_rotation")
def test_get_sectors_rotation_not_found(mock_get_sector_rotation, client: TestClient) -> None:
    """Test sector rotation when no data available."""
    # Mock the get_sector_rotation function to return None
    mock_get_sector_rotation.return_value = None

    # Make request
    response = client.get("/api/analytics/sectors/rotation?date=2025-01-15")

    # Verify
    assert response.status_code == 404
    assert "Could not calculate sector rotation" in response.json()["detail"]


@patch("app.api.analytics.get_peer_comparison")
def test_get_peer_comparison_success(mock_get_peer_comparison, client: TestClient) -> None:
    """Test successful peer comparison retrieval."""
    # Mock the get_peer_comparison function
    mock_df = pl.DataFrame(
        {
            "symbol": ["AAPL"],
            "sector": ["Technology"],
            "return_5d": [2.5],
            "return_20d": [8.0],
            "sector_avg_5d": [2.0],
            "sector_avg_20d": [7.0],
            "relative_perf_5d": [0.5],
            "relative_perf_20d": [1.0],
            "peer_rank": [2],
            "peer_count": [50],
            "percentile": [96.0],
        }
    )
    mock_get_peer_comparison.return_value = mock_df

    # Make request
    response = client.get("/api/analytics/peers/AAPL?date=2025-01-15")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["sector"] == "Technology"
    assert data["date"] == "2025-01-15"
    assert data["peer_rank"] == 2
    assert data["peer_count"] == 50
    assert data["percentile"] == 96.0


@patch("app.api.analytics.get_peer_comparison")
def test_get_peer_comparison_not_found(mock_get_peer_comparison, client: TestClient) -> None:
    """Test peer comparison when ticker not found."""
    # Mock the get_peer_comparison function to return None
    mock_get_peer_comparison.return_value = None

    # Make request
    response = client.get("/api/analytics/peers/INVALID?date=2025-01-15")

    # Verify
    assert response.status_code == 404
    assert "Could not calculate peer comparison" in response.json()["detail"]


@patch("app.api.analytics.get_peer_comparison")
def test_get_peer_comparison_invalid_group_by(mock_get_peer_comparison, client: TestClient) -> None:
    """Test peer comparison with invalid group_by parameter."""
    # Make request with invalid group_by
    response = client.get("/api/analytics/peers/AAPL?date=2025-01-15&group_by=invalid")

    # Verify
    assert response.status_code == 400
    assert "Invalid group_by parameter" in response.json()["detail"]


@patch("app.api.analytics.get_peer_group_detail")
def test_get_peer_group_detail_success(mock_get_peer_group_detail, client: TestClient) -> None:
    """Test successful peer group detail retrieval."""
    # Mock the get_peer_group_detail function
    mock_df = pl.DataFrame(
        {
            "symbol": ["MSFT", "AAPL", "GOOGL"],
            "sector": ["Technology", "Technology", "Technology"],
            "return_5d": [3.0, 2.5, 2.0],
            "return_20d": [10.0, 8.0, 7.0],
            "rank": [1, 2, 3],
            "is_target": [False, True, False],
        }
    )
    mock_get_peer_group_detail.return_value = mock_df

    # Make request
    response = client.get("/api/analytics/peers/AAPL/detail?date=2025-01-15")

    # Verify
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["sector"] == "Technology"
    assert data["date"] == "2025-01-15"
    assert data["count"] == 3
    assert len(data["peers"]) == 3
    # Verify target ticker is marked
    target_peer = next(p for p in data["peers"] if p["is_target"])
    assert target_peer["symbol"] == "AAPL"


@patch("app.api.analytics.get_peer_group_detail")
def test_get_peer_group_detail_not_found(mock_get_peer_group_detail, client: TestClient) -> None:
    """Test peer group detail when ticker not found."""
    # Mock the get_peer_group_detail function to return None
    mock_get_peer_group_detail.return_value = None

    # Make request
    response = client.get("/api/analytics/peers/INVALID/detail?date=2025-01-15")

    # Verify
    assert response.status_code == 404
    assert "Could not get peer group detail" in response.json()["detail"]


def test_analytics_endpoints_registered(client: TestClient) -> None:
    """Test that all analytics endpoints are registered."""
    # Get OpenAPI schema
    response = client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()
    paths = schema["paths"]

    # Verify all analytics endpoints are registered
    assert "/api/analytics/rvol/{symbol}" in paths
    assert "/api/analytics/sectors/rotation" in paths
    assert "/api/analytics/peers/{symbol}" in paths
    assert "/api/analytics/peers/{symbol}/detail" in paths
