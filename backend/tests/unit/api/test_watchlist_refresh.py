"""Unit tests for watchlist refresh endpoint (FEAT-033).

Tests POST /api/watchlist/refresh endpoint:
- Successful refresh with all items
- Successful refresh with no items in watchlist
- Partial success with some failures (207 Multi-Status)
- Complete failure scenario (500)
- Background task scheduling verification
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_repo() -> MagicMock:
    """Mock watchlist repository."""
    mock = MagicMock()

    # Default: return empty watchlist
    mock_df = MagicMock()
    mock_df.is_empty.return_value = True
    mock_df.to_dicts.return_value = []
    mock.get_all_symbols.return_value = mock_df

    return mock


@pytest.fixture
def mock_refresh_service() -> MagicMock:
    """Mock refresh_watchlist_scores_service."""
    return MagicMock(
        return_value={
            "success_count": 3,
            "failed_count": 0,
            "failed": [],
        }
    )


@pytest.fixture
def mock_schedule_tasks() -> MagicMock:
    """Mock schedule_refresh_tasks."""
    return MagicMock()


# =============================================================================
# Test Successful Refresh
# =============================================================================


class TestWatchlistRefreshSuccess:
    """Tests for successful watchlist refresh scenarios."""

    def test_refresh_empty_watchlist(self, mock_repo: MagicMock) -> None:
        """Test refresh when watchlist has no items."""
        with (
            patch("app.api.watchlist.watchlist_repo", mock_repo),
            patch("app.api.watchlist.schedule_refresh_tasks") as mock_schedule,
            patch("app.api.watchlist.refresh_watchlist_scores_service") as mock_refresh,
        ):
            # Empty watchlist
            mock_df = MagicMock()
            mock_df.is_empty.return_value = True
            mock_df.to_dicts.return_value = []
            mock_repo.get_all_symbols.return_value = mock_df

            response = client.post("/api/watchlist/refresh", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["message"] == "No items in watchlist"
            assert data["refreshed_count"] == 0
            assert data["failed_count"] == 0
            assert data["failed"] == []

            # Should not trigger background tasks or refresh for empty watchlist
            mock_schedule.assert_not_called()
            mock_refresh.assert_not_called()

    def test_refresh_all_items_success(
        self, mock_repo: MagicMock, mock_refresh_service: MagicMock
    ) -> None:
        """Test successful refresh of all watchlist items."""
        with (
            patch("app.api.watchlist.watchlist_repo", mock_repo),
            patch("app.api.watchlist.schedule_refresh_tasks") as mock_schedule,
            patch(
                "app.api.watchlist.refresh_watchlist_scores_service", mock_refresh_service
            ),
        ):
            # Mock watchlist with 3 items
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [
                {"id": "item-1", "symbol": "AAPL"},
                {"id": "item-2", "symbol": "GOOGL"},
                {"id": "item-3", "symbol": "MSFT"},
            ]
            mock_repo.get_all_symbols.return_value = mock_df

            # All successful
            mock_refresh_service.return_value = {
                "success_count": 3,
                "failed_count": 0,
                "failed": [],
            }

            response = client.post("/api/watchlist/refresh", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "Refreshed all 3 items successfully" in data["message"]
            assert data["refreshed_count"] == 3
            assert data["failed_count"] == 0
            assert data["failed"] == []

            # Verify background tasks scheduled
            mock_schedule.assert_called_once_with(["AAPL", "GOOGL", "MSFT"])


# =============================================================================
# Test Partial Success (207 Multi-Status)
# =============================================================================


class TestWatchlistRefreshPartialSuccess:
    """Tests for partial success scenarios (some items fail)."""

    def test_refresh_partial_success(
        self, mock_repo: MagicMock, mock_refresh_service: MagicMock
    ) -> None:
        """Test refresh with some failures returns 207 Multi-Status."""
        with (
            patch("app.api.watchlist.watchlist_repo", mock_repo),
            patch("app.api.watchlist.schedule_refresh_tasks") as mock_schedule,
            patch(
                "app.api.watchlist.refresh_watchlist_scores_service", mock_refresh_service
            ),
        ):
            # Mock watchlist with 3 items
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [
                {"id": "item-1", "symbol": "AAPL"},
                {"id": "item-2", "symbol": "INVALID"},
                {"id": "item-3", "symbol": "GOOGL"},
            ]
            mock_repo.get_all_symbols.return_value = mock_df

            # Partial success (1 failure)
            mock_refresh_service.return_value = {
                "success_count": 2,
                "failed_count": 1,
                "failed": [
                    {"symbol": "INVALID", "reason": "Symbol not found"},
                ],
            }

            response = client.post("/api/watchlist/refresh", json={})

            assert response.status_code == 207  # Multi-Status
            data = response.json()
            assert data["status"] == "partial_success"
            assert "Refreshed 2 of 3 items" in data["message"]
            assert data["refreshed_count"] == 2
            assert data["failed_count"] == 1
            assert len(data["failed"]) == 1
            assert data["failed"][0]["symbol"] == "INVALID"
            assert data["failed"][0]["reason"] == "Symbol not found"

            # Background tasks should still be scheduled for all symbols
            mock_schedule.assert_called_once_with(["AAPL", "INVALID", "GOOGL"])


# =============================================================================
# Test Complete Failure
# =============================================================================


class TestWatchlistRefreshFailure:
    """Tests for complete failure scenarios."""

    def test_refresh_all_items_fail(
        self, mock_repo: MagicMock, mock_refresh_service: MagicMock
    ) -> None:
        """Test refresh when all items fail returns 500."""
        with (
            patch("app.api.watchlist.watchlist_repo", mock_repo),
            patch("app.api.watchlist.schedule_refresh_tasks") as mock_schedule,
            patch(
                "app.api.watchlist.refresh_watchlist_scores_service", mock_refresh_service
            ),
        ):
            # Mock watchlist with 2 items
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [
                {"id": "item-1", "symbol": "INVALID1"},
                {"id": "item-2", "symbol": "INVALID2"},
            ]
            mock_repo.get_all_symbols.return_value = mock_df

            # Complete failure
            mock_refresh_service.return_value = {
                "success_count": 0,
                "failed_count": 2,
                "failed": [
                    {"symbol": "INVALID1", "reason": "API error"},
                    {"symbol": "INVALID2", "reason": "API error"},
                ],
            }

            response = client.post("/api/watchlist/refresh", json={})

            assert response.status_code == 500
            assert "Failed to refresh any items" in response.json()["detail"]

    def test_refresh_service_exception(self, mock_repo: MagicMock) -> None:
        """Test handling of unexpected exceptions during refresh."""
        with (
            patch("app.api.watchlist.watchlist_repo", mock_repo),
            patch("app.api.watchlist.schedule_refresh_tasks"),
            patch(
                "app.api.watchlist.refresh_watchlist_scores_service",
                side_effect=Exception("Database connection failed"),
            ),
        ):
            # Mock non-empty watchlist
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [
                {"id": "item-1", "symbol": "AAPL"},
            ]
            mock_repo.get_all_symbols.return_value = mock_df

            response = client.post("/api/watchlist/refresh", json={})

            assert response.status_code == 500
            assert "Failed to refresh" in response.json()["detail"]


# =============================================================================
# Test Background Task Scheduling
# =============================================================================


class TestWatchlistRefreshBackgroundTasks:
    """Tests for background task scheduling during refresh."""

    def test_background_tasks_scheduled_for_all_symbols(
        self, mock_repo: MagicMock, mock_refresh_service: MagicMock
    ) -> None:
        """Test that background data refresh tasks are scheduled for all symbols."""
        with (
            patch("app.api.watchlist.watchlist_repo", mock_repo),
            patch("app.api.watchlist.schedule_refresh_tasks") as mock_schedule,
            patch(
                "app.api.watchlist.refresh_watchlist_scores_service", mock_refresh_service
            ),
        ):
            # Mock watchlist
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"]
            mock_df.to_dicts.return_value = [
                {"id": f"item-{i}", "symbol": sym} for i, sym in enumerate(symbols)
            ]
            mock_repo.get_all_symbols.return_value = mock_df

            # All successful
            mock_refresh_service.return_value = {
                "success_count": 5,
                "failed_count": 0,
                "failed": [],
            }

            response = client.post("/api/watchlist/refresh", json={})

            assert response.status_code == 200

            # Verify background tasks called with correct symbols
            mock_schedule.assert_called_once()
            call_args = mock_schedule.call_args[0][0]
            assert set(call_args) == set(symbols)
