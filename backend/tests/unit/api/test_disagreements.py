"""Unit tests for LLM disagreement alerts API (FEAT-035).

Tests disagreement detection API endpoints:
- GET /api/disagreements - List disagreements with filtering
- GET /api/disagreements/stats - Statistics and trends
- GET /api/disagreements/{symbol} - Symbol-specific disagreements
- Severity filtering (minor, major)
- Empty result handling
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_storage() -> MagicMock:
    """Mock storage with query method."""
    mock = MagicMock()

    # Default: return empty
    mock_df = MagicMock()
    mock_df.is_empty.return_value = True
    mock_df.to_dicts.return_value = []
    mock.query.return_value = mock_df

    return mock


@pytest.fixture
def sample_disagreement() -> dict:
    """Sample disagreement data."""
    return {
        "review_pair_id": "pair-123",
        "symbol": "AAPL",
        "created_at": datetime.now(UTC).isoformat(),
        "agreement_score": 0.3,
        "disagreement_severity": "major",
        "gemini_review": "Bullish outlook based on strong fundamentals",
        "claude_review": "Bearish concerns due to valuation risks",
    }


# =============================================================================
# Test List Disagreements Endpoint
# =============================================================================


class TestListDisagreements:
    """Tests for GET /api/disagreements endpoint."""

    def test_list_disagreements_empty(self, mock_storage: MagicMock) -> None:
        """Test listing disagreements when none exist."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = True
            mock_df.to_dicts.return_value = []
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements")

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert len(data["items"]) == 0
            assert data["total"] == 0

    def test_list_disagreements_with_data(
        self, mock_storage: MagicMock, sample_disagreement: dict
    ) -> None:
        """Test listing disagreements with data."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [sample_disagreement]
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["total"] == 1

            item = data["items"][0]
            assert item["symbol"] == "AAPL"
            assert item["disagreement_severity"] == "major"
            assert item["agreement_score"] == 0.3
            assert item["review_pair_id"] == "pair-123"
            assert "gemini_review" in item
            assert "claude_review" in item
            assert "consensus_summary" in item

    def test_list_disagreements_default_params(
        self, mock_storage: MagicMock, sample_disagreement: dict
    ) -> None:
        """Test default parameters (7 days, no severity filter, limit 50)."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [sample_disagreement]
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements")

            assert response.status_code == 200

            # Verify query was called with correct params (7 days back)
            mock_storage.query.assert_called_once()
            call_args = mock_storage.query.call_args
            query_params = call_args[0][1]  # Second arg is params list

            # First param is 'since' datetime (7 days ago)
            since_date = query_params[0]
            now = datetime.now(UTC)
            expected_since = now - timedelta(days=7)
            time_diff = abs((since_date - expected_since).total_seconds())
            assert time_diff < 2  # Within 2 seconds tolerance

            # Last param is limit (50)
            assert query_params[-1] == 50

    def test_list_disagreements_with_severity_filter(
        self, mock_storage: MagicMock
    ) -> None:
        """Test filtering disagreements by severity."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [
                {
                    "review_pair_id": "pair-1",
                    "symbol": "GOOGL",
                    "created_at": datetime.now(UTC).isoformat(),
                    "agreement_score": 0.4,
                    "disagreement_severity": "major",
                    "gemini_review": "Review 1",
                    "claude_review": "Review 2",
                }
            ]
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements?severity=major")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["disagreement_severity"] == "major"

            # Verify severity filter was applied in query
            mock_storage.query.assert_called_once()
            call_args = mock_storage.query.call_args
            query_params = call_args[0][1]
            # Second param should be severity value
            assert query_params[1] == "major"

    def test_list_disagreements_custom_days(self, mock_storage: MagicMock) -> None:
        """Test custom days parameter."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = True
            mock_df.to_dicts.return_value = []
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements?days=30")

            assert response.status_code == 200

            # Verify query was called with 30 days lookback
            call_args = mock_storage.query.call_args
            since_date = call_args[0][1][0]
            now = datetime.now(UTC)
            expected_since = now - timedelta(days=30)
            time_diff = abs((since_date - expected_since).total_seconds())
            assert time_diff < 2

    def test_list_disagreements_custom_limit(self, mock_storage: MagicMock) -> None:
        """Test custom limit parameter."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = True
            mock_df.to_dicts.return_value = []
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements?limit=100")

            assert response.status_code == 200

            # Verify query was called with limit=100
            call_args = mock_storage.query.call_args
            limit_param = call_args[0][1][-1]
            assert limit_param == 100


# =============================================================================
# Test Disagreement Stats Endpoint
# =============================================================================


class TestDisagreementStats:
    """Tests for GET /api/disagreements/stats endpoint."""

    def test_get_stats_no_data(self, mock_storage: MagicMock) -> None:
        """Test stats endpoint when no reviews exist."""
        with patch("app.api.disagreements.storage", mock_storage):
            # Empty stats
            mock_df = MagicMock()
            mock_df.is_empty.return_value = True
            mock_df.to_dicts.return_value = []
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements/stats")

            assert response.status_code == 200
            data = response.json()

            # Should return valid structure with zero values
            assert data["total_reviews"] == 0
            assert data["total_review_pairs"] == 0
            assert data["agreement_rate"] == 1.0  # 100% when no data
            assert data["minor_disagreement_rate"] == 0.0
            assert data["major_disagreement_rate"] == 0.0
            assert isinstance(data["trend_7d"], list)

    def test_get_stats_with_data(self, mock_storage: MagicMock) -> None:
        """Test stats endpoint with actual data."""
        with patch("app.api.disagreements.storage", mock_storage):
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

            assert data["total_reviews"] == 100
            assert data["total_review_pairs"] == 50
            assert data["agreement_count"] == 80
            assert data["minor_disagreement_count"] == 15
            assert data["major_disagreement_count"] == 5
            assert data["agreement_rate"] == 0.8  # 80/100
            assert data["minor_disagreement_rate"] == 0.15  # 15/100
            assert data["major_disagreement_rate"] == 0.05  # 5/100
            assert data["avg_agreement_score"] == 0.85
            assert len(data["trend_7d"]) == 2

    def test_get_stats_custom_days(self, mock_storage: MagicMock) -> None:
        """Test stats with custom days parameter."""
        with patch("app.api.disagreements.storage", mock_storage):
            # Empty stats
            mock_df = MagicMock()
            mock_df.is_empty.return_value = True
            mock_df.to_dicts.return_value = []
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements/stats?days=90")

            assert response.status_code == 200

            # Verify first query used 90 days
            call_args = mock_storage.query.call_args_list[0]
            since_date = call_args[0][1][0]
            now = datetime.now(UTC)
            expected_since = now - timedelta(days=90)
            time_diff = abs((since_date - expected_since).total_seconds())
            assert time_diff < 2


# =============================================================================
# Test Symbol-Specific Disagreements Endpoint
# =============================================================================


class TestSymbolDisagreements:
    """Tests for GET /api/disagreements/{symbol} endpoint."""

    def test_get_symbol_disagreements_no_data(self, mock_storage: MagicMock) -> None:
        """Test getting disagreements for a symbol with no data."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = True
            mock_df.to_dicts.return_value = []
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements/AAPL")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 0
            assert data["total"] == 0

    def test_get_symbol_disagreements_with_data(
        self, mock_storage: MagicMock
    ) -> None:
        """Test getting disagreements for a specific symbol."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [
                {
                    "review_pair_id": "pair-1",
                    "symbol": "GOOGL",
                    "created_at": datetime.now(UTC).isoformat(),
                    "agreement_score": 0.7,
                    "disagreement_severity": "minor",
                    "gemini_review": "Some concerns about valuation",
                    "claude_review": "Mild caution on growth outlook",
                }
            ]
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements/GOOGL")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["symbol"] == "GOOGL"
            assert data["items"][0]["disagreement_severity"] == "minor"

            # Verify query included symbol filter
            call_args = mock_storage.query.call_args
            query_params = call_args[0][1]
            # Second param should be uppercase symbol
            assert query_params[1] == "GOOGL"

    def test_get_symbol_disagreements_uppercase_conversion(
        self, mock_storage: MagicMock
    ) -> None:
        """Test that symbol parameter is converted to uppercase."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = True
            mock_df.to_dicts.return_value = []
            mock_storage.query.return_value = mock_df

            # Request with lowercase symbol
            response = client.get("/api/disagreements/aapl")

            assert response.status_code == 200

            # Verify query was called with uppercase symbol
            call_args = mock_storage.query.call_args
            symbol_param = call_args[0][1][1]
            assert symbol_param == "AAPL"

    def test_get_symbol_disagreements_custom_days(
        self, mock_storage: MagicMock
    ) -> None:
        """Test symbol disagreements with custom days parameter."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = True
            mock_df.to_dicts.return_value = []
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements/TSLA?days=60")

            assert response.status_code == 200

            # Verify query used 60 days lookback
            call_args = mock_storage.query.call_args
            since_date = call_args[0][1][0]
            now = datetime.now(UTC)
            expected_since = now - timedelta(days=60)
            time_diff = abs((since_date - expected_since).total_seconds())
            assert time_diff < 2


# =============================================================================
# Test Error Handling
# =============================================================================


class TestDisagreementsErrorHandling:
    """Tests for error handling in disagreements API."""

    def test_list_disagreements_database_error(self, mock_storage: MagicMock) -> None:
        """Test handling of database errors in list endpoint."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_storage.query.side_effect = Exception("Database connection failed")

            response = client.get("/api/disagreements")

            assert response.status_code == 500
            assert "Database connection failed" in response.json()["detail"]

    def test_get_stats_database_error(self, mock_storage: MagicMock) -> None:
        """Test handling of database errors in stats endpoint."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_storage.query.side_effect = Exception("Query timeout")

            response = client.get("/api/disagreements/stats")

            assert response.status_code == 500
            assert "Query timeout" in response.json()["detail"]

    def test_get_symbol_disagreements_database_error(
        self, mock_storage: MagicMock
    ) -> None:
        """Test handling of database errors in symbol endpoint."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_storage.query.side_effect = Exception("Connection lost")

            response = client.get("/api/disagreements/AAPL")

            assert response.status_code == 500
            assert "Connection lost" in response.json()["detail"]


# =============================================================================
# Test Consensus Summary Generation
# =============================================================================


class TestConsensusSummary:
    """Tests for consensus summary generation."""

    def test_summary_for_major_disagreement(self, mock_storage: MagicMock) -> None:
        """Test summary generation for major disagreements."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [
                {
                    "review_pair_id": "pair-1",
                    "symbol": "NVDA",
                    "created_at": datetime.now(UTC).isoformat(),
                    "agreement_score": 0.2,
                    "disagreement_severity": "major",
                    "gemini_review": "Strong buy",
                    "claude_review": "Strong sell",
                }
            ]
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements")

            assert response.status_code == 200
            data = response.json()
            summary = data["items"][0]["consensus_summary"]
            assert "ALERT" in summary
            assert "manual review" in summary.lower()

    def test_summary_for_minor_disagreement(self, mock_storage: MagicMock) -> None:
        """Test summary generation for minor disagreements."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [
                {
                    "review_pair_id": "pair-1",
                    "symbol": "AMD",
                    "created_at": datetime.now(UTC).isoformat(),
                    "agreement_score": 0.7,
                    "disagreement_severity": "minor",
                    "gemini_review": "Moderate buy",
                    "claude_review": "Mild buy",
                }
            ]
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements")

            assert response.status_code == 200
            data = response.json()
            summary = data["items"][0]["consensus_summary"]
            assert "minor differences" in summary.lower()
            assert "align on direction" in summary.lower()

    def test_summary_for_agreement(self, mock_storage: MagicMock) -> None:
        """Test summary generation when reviewers agree."""
        with patch("app.api.disagreements.storage", mock_storage):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [
                {
                    "review_pair_id": "pair-1",
                    "symbol": "INTC",
                    "created_at": datetime.now(UTC).isoformat(),
                    "agreement_score": 0.95,
                    "disagreement_severity": "none",  # Use "none" instead of None
                    "gemini_review": "Hold",
                    "claude_review": "Hold",
                }
            ]
            mock_storage.query.return_value = mock_df

            response = client.get("/api/disagreements")

            assert response.status_code == 200
            data = response.json()
            summary = data["items"][0]["consensus_summary"]
            assert "agree" in summary.lower()
