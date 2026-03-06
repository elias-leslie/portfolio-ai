"""Unit tests for watchlist refresh endpoint (FEAT-033).

Tests refresh_watchlist_scores endpoint function directly:
- Successful refresh with all items
- Successful refresh with no items in watchlist
- Partial success with some failures (207 Multi-Status)
- Complete failure scenario (500)
- Background task scheduling verification
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.watchlist.refresh_router import get_refresh_endpoint, refresh_watchlist_scores
from app.watchlist.response_builders import RefreshRequest, RefreshResponse

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

    @pytest.mark.asyncio
    async def test_refresh_empty_watchlist(self, mock_repo: MagicMock) -> None:
        """Test refresh when watchlist has no items."""
        with (
            patch("app.api.watchlist.refresh_router.watchlist_repo", mock_repo),
            patch("app.api.watchlist.refresh_router.schedule_refresh_tasks") as mock_schedule,
            patch("app.api.watchlist.refresh_router.refresh_watchlist_scores_service") as mock_refresh,
        ):
            # Empty watchlist
            mock_df = MagicMock()
            mock_df.is_empty.return_value = True
            mock_df.to_dicts.return_value = []
            mock_repo.get_all_symbols.return_value = mock_df

            result = await refresh_watchlist_scores(data=RefreshRequest())

            assert isinstance(result, RefreshResponse)
            assert result.status == "success"
            assert result.message == "No items in watchlist"
            assert result.refreshed_count == 0
            assert result.failed_count == 0
            assert result.failed == []

            # Should not trigger background tasks or refresh for empty watchlist
            mock_schedule.assert_not_called()
            mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_all_items_success(
        self, mock_repo: MagicMock, mock_refresh_service: MagicMock
    ) -> None:
        """Test successful refresh of all watchlist items."""
        with (
            patch("app.api.watchlist.refresh_router.watchlist_repo", mock_repo),
            patch("app.api.watchlist.refresh_router.schedule_refresh_tasks") as mock_schedule,
            patch("app.api.watchlist.refresh_router.refresh_watchlist_scores_service", mock_refresh_service),
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

            result = await refresh_watchlist_scores(data=RefreshRequest())

            assert isinstance(result, RefreshResponse)
            assert result.status == "success"
            assert "Refreshed all 3 items successfully" in result.message
            assert result.refreshed_count == 3
            assert result.failed_count == 0
            assert result.failed == []

            # Verify background tasks scheduled
            mock_schedule.assert_called_once_with(["AAPL", "GOOGL", "MSFT"])

    @pytest.mark.asyncio
    async def test_refresh_filters_blocked_test_symbols_before_processing(
        self, mock_repo: MagicMock, mock_refresh_service: MagicMock
    ) -> None:
        """Test refresh skips leaked ZZTEST symbols in the live refresh path."""
        with (
            patch("app.api.watchlist.refresh_router.watchlist_repo", mock_repo),
            patch("app.api.watchlist.refresh_router.schedule_refresh_tasks") as mock_schedule,
            patch("app.api.watchlist.refresh_router.refresh_watchlist_scores_service", mock_refresh_service),
        ):
            mock_df = MagicMock()
            mock_df.is_empty.return_value = False
            mock_df.to_dicts.return_value = [
                {"id": "item-1", "symbol": "AAPL"},
                {"id": "item-2", "symbol": "ZZTEST999"},
                {"id": "item-3", "symbol": "MSFT"},
            ]
            mock_repo.get_all_symbols.return_value = mock_df

            mock_refresh_service.return_value = {
                "success_count": 2,
                "failed_count": 0,
                "failed": [],
            }

            result = await refresh_watchlist_scores(data=RefreshRequest())

            assert isinstance(result, RefreshResponse)
            mock_schedule.assert_called_once_with(["AAPL", "MSFT"])

    @pytest.mark.asyncio
    async def test_refresh_get_endpoint_returns_method_guidance(self) -> None:
        """Test GET /refresh returns an explicit method error instead of item lookup."""
        with pytest.raises(HTTPException) as exc_info:
            await get_refresh_endpoint()

        assert exc_info.value.status_code == 405
        assert "POST /api/watchlist/refresh" in str(exc_info.value.detail)


# =============================================================================
# Test Partial Success (207 Multi-Status)
# =============================================================================


class TestWatchlistRefreshPartialSuccess:
    """Tests for partial success scenarios (some items fail)."""

    @pytest.mark.asyncio
    async def test_refresh_partial_success(
        self, mock_repo: MagicMock, mock_refresh_service: MagicMock
    ) -> None:
        """Test refresh with some failures returns 207 Multi-Status."""
        from fastapi.responses import JSONResponse

        with (
            patch("app.api.watchlist.refresh_router.watchlist_repo", mock_repo),
            patch("app.api.watchlist.refresh_router.schedule_refresh_tasks") as mock_schedule,
            patch("app.api.watchlist.refresh_router.refresh_watchlist_scores_service", mock_refresh_service),
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

            result = await refresh_watchlist_scores(data=RefreshRequest())

            # 207 Multi-Status returned as JSONResponse
            assert isinstance(result, JSONResponse)
            assert result.status_code == 207

            import json as json_mod
            data = json_mod.loads(result.body if isinstance(result.body, (str, bytes, bytearray)) else bytes(result.body))
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

    @pytest.mark.asyncio
    async def test_refresh_all_items_fail(
        self, mock_repo: MagicMock, mock_refresh_service: MagicMock
    ) -> None:
        """Test refresh when all items fail raises HTTPException with 500."""
        with (
            patch("app.api.watchlist.refresh_router.watchlist_repo", mock_repo),
            patch("app.api.watchlist.refresh_router.schedule_refresh_tasks") as mock_schedule,
            patch("app.api.watchlist.refresh_router.refresh_watchlist_scores_service", mock_refresh_service),
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

            with pytest.raises(HTTPException) as exc_info:
                await refresh_watchlist_scores(data=RefreshRequest())

            assert exc_info.value.status_code == 500
            assert "Failed to refresh any items" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_refresh_service_exception(self, mock_repo: MagicMock) -> None:
        """Test handling of unexpected exceptions during refresh raises HTTPException."""
        with (
            patch("app.api.watchlist.refresh_router.watchlist_repo", mock_repo),
            patch("app.api.watchlist.refresh_router.schedule_refresh_tasks"),
            patch(
                "app.api.watchlist.refresh_router.refresh_watchlist_scores_service",
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

            with pytest.raises(HTTPException) as exc_info:
                await refresh_watchlist_scores(data=RefreshRequest())

            assert exc_info.value.status_code == 500
            assert "Failed to refresh" in exc_info.value.detail


# =============================================================================
# Test Background Task Scheduling
# =============================================================================


class TestWatchlistRefreshBackgroundTasks:
    """Tests for background task scheduling during refresh."""

    @pytest.mark.asyncio
    async def test_background_tasks_scheduled_for_all_symbols(
        self, mock_repo: MagicMock, mock_refresh_service: MagicMock
    ) -> None:
        """Test that background data refresh tasks are scheduled for all symbols."""
        with (
            patch("app.api.watchlist.refresh_router.watchlist_repo", mock_repo),
            patch("app.api.watchlist.refresh_router.schedule_refresh_tasks") as mock_schedule,
            patch("app.api.watchlist.refresh_router.refresh_watchlist_scores_service", mock_refresh_service),
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

            result = await refresh_watchlist_scores(data=RefreshRequest())

            assert isinstance(result, RefreshResponse)

            # Verify background tasks called with correct symbols
            mock_schedule.assert_called_once()
            call_args = mock_schedule.call_args[0][0]
            assert set(call_args) == set(symbols)
