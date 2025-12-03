"""Unit tests for disagreements API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestDisagreementsAPI:
    """Tests for disagreements API endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client with mocked storage."""
        with patch("app.api.disagreements.get_storage") as mock_storage:
            # Create mock storage
            mock_storage_instance = MagicMock()
            mock_storage.return_value = mock_storage_instance

            # Mock query to return empty by default
            mock_storage_instance.query.return_value = MagicMock(
                is_empty=lambda: True, to_dicts=lambda: []
            )

            from app.main import app

            return TestClient(app)

    def test_list_disagreements_empty(self, client: TestClient) -> None:
        """Test listing disagreements when none exist."""
        with patch("app.api.disagreements.storage") as mock_storage:
            mock_df = MagicMock()
            mock_df.is_empty.return_value = True
            mock_df.to_dicts.return_value = []
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data

    def test_list_disagreements_with_data(self, client: TestClient) -> None:
        """Test listing disagreements with data."""
        with patch("app.api.disagreements.storage") as mock_storage:
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [
                {
                    "review_pair_id": "test-pair-1",
                    "symbol": "AAPL",
                    "created_at": datetime.now(UTC).isoformat(),
                    "agreement_score": 0.3,
                    "disagreement_severity": "major",
                    "gemini_review": "Bullish outlook.",
                    "claude_review": "Bearish concerns.",
                }
            ]
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements")
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["symbol"] == "AAPL"
            assert data["items"][0]["disagreement_severity"] == "major"

    def test_list_disagreements_with_severity_filter(
        self, client: TestClient
    ) -> None:
        """Test filtering disagreements by severity."""
        with patch("app.api.disagreements.storage") as mock_storage:
            mock_df = MagicMock()
            mock_df.is_empty.return_value = True
            mock_df.to_dicts.return_value = []
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements?severity=major")
            assert response.status_code == 200

    def test_get_disagreement_stats(self, client: TestClient) -> None:
        """Test getting disagreement statistics."""
        with patch("app.api.disagreements.storage") as mock_storage:
            # Mock stats query
            stats_df = MagicMock()
            stats_df.is_empty.return_value = False
            stats_df.to_dicts.return_value = [
                {
                    "total_reviews": 100,
                    "total_pairs": 50,
                    "agreement_count": 80,
                    "minor_count": 15,
                    "major_count": 5,
                    "avg_agreement": 0.85,
                }
            ]

            # Mock trend query
            trend_df = MagicMock()
            trend_df.is_empty.return_value = False
            trend_df.to_dicts.return_value = [
                {
                    "date": "2025-12-01",
                    "reviews": 10,
                    "disagreements": 2,
                    "avg_score": 0.9,
                },
                {
                    "date": "2025-12-02",
                    "reviews": 15,
                    "disagreements": 3,
                    "avg_score": 0.85,
                },
            ]

            mock_storage.query.side_effect = [stats_df, trend_df]

            response = client.get("/api/disagreements/stats")
            assert response.status_code == 200
            data = response.json()
            assert "total_reviews" in data
            assert "agreement_rate" in data
            assert "trend_7d" in data

    def test_get_symbol_disagreements(self, client: TestClient) -> None:
        """Test getting disagreements for a specific symbol."""
        with patch("app.api.disagreements.storage") as mock_storage:
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [
                {
                    "review_pair_id": "test-pair-1",
                    "symbol": "GOOGL",
                    "created_at": datetime.now(UTC).isoformat(),
                    "agreement_score": 0.7,
                    "disagreement_severity": "minor",
                    "gemini_review": "Some concerns.",
                    "claude_review": "Mild caution.",
                }
            ]
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements/GOOGL")
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["symbol"] == "GOOGL"
