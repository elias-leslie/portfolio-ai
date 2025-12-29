"""Unit tests for watchlist score history API endpoint (FEAT-125)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.watchlist import get_score_history
from app.watchlist.history import ScoreTimelinePoint


class TestGetScoreHistoryEndpoint:
    """Tests for GET /api/watchlist/{item_id}/history endpoint."""

    @pytest.fixture
    def mock_repo(self) -> MagicMock:
        """Create mock watchlist repository instance."""
        return MagicMock()

    @pytest.fixture
    def sample_item_data(self) -> dict:
        """Sample watchlist item data."""
        return {
            "id": "item-123",
            "symbol": "AAPL",
            "note": "Test item",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

    @pytest.fixture
    def sample_snapshots_data(self) -> list[dict]:
        """Sample snapshot data from database."""
        now = datetime.now(UTC)
        return [
            {
                "item_id": "item-123",
                "fetched_at": now - timedelta(hours=2),
                "price": 180.0,
                "technical_score": 80.0,
                "overall_score": 75.0,
                "raw_metrics": json.dumps(
                    {
                        "price": {"score": 70.0},
                        "technical": {"score": 80.0},
                    }
                ),
            },
            {
                "item_id": "item-123",
                "fetched_at": now - timedelta(days=1),
                "price": 175.0,
                "technical_score": 75.0,
                "overall_score": 70.0,
                "raw_metrics": json.dumps(
                    {
                        "price": {"score": 65.0},
                        "technical": {"score": 75.0},
                    }
                ),
            },
        ]

    @pytest.mark.asyncio
    async def test_returns_score_history_for_valid_item(
        self, mock_repo: MagicMock, sample_item_data: dict, sample_snapshots_data: list[dict]
    ) -> None:
        """Test that score history is returned for valid watchlist item."""
        # Mock item query
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = [{"symbol": "AAPL"}]
        mock_repo.get_symbol_by_item_id.return_value = item_df

        # Mock snapshots query
        snapshots_df = MagicMock()
        snapshots_df.is_empty.return_value = False
        snapshots_df.to_dicts.return_value = sample_snapshots_data
        mock_repo.get_snapshots_with_metrics.return_value = snapshots_df

        with patch("app.api.watchlist.watchlist_repo", mock_repo):
            response = await get_score_history(item_id="item-123", days=10)

            assert response.item_id == "item-123"
            assert response.symbol == "AAPL"
            assert len(response.history) > 0

    @pytest.mark.asyncio
    async def test_raises_404_when_item_not_found(self, mock_repo: MagicMock) -> None:
        """Test that 404 is raised when watchlist item doesn't exist."""
        item_df = MagicMock()
        item_df.is_empty.return_value = True
        mock_repo.get_symbol_by_item_id.return_value = item_df

        with patch("app.api.watchlist.watchlist_repo", mock_repo), pytest.raises(
            HTTPException
        ) as exc_info:
            await get_score_history(item_id="nonexistent-id")

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_returns_empty_history_when_no_snapshots(
        self, mock_repo: MagicMock, sample_item_data: dict
    ) -> None:
        """Test that empty history is returned when no snapshots exist."""
        # Mock item query - item exists
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = [{"symbol": "AAPL"}]
        mock_repo.get_symbol_by_item_id.return_value = item_df

        # Mock snapshots query - no snapshots
        snapshots_df = MagicMock()
        snapshots_df.is_empty.return_value = True
        mock_repo.get_snapshots_with_metrics.return_value = snapshots_df

        with patch("app.api.watchlist.watchlist_repo", mock_repo):
            response = await get_score_history(item_id="item-123")

            assert response.item_id == "item-123"
            assert response.symbol == "AAPL"
            assert len(response.history) == 0

    @pytest.mark.asyncio
    async def test_respects_days_parameter(
        self, mock_repo: MagicMock, sample_snapshots_data: list[dict]
    ) -> None:
        """Test that the days parameter is respected when fetching history."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = [{"symbol": "AAPL"}]
        mock_repo.get_symbol_by_item_id.return_value = item_df

        snapshots_df = MagicMock()
        snapshots_df.is_empty.return_value = False
        snapshots_df.to_dicts.return_value = sample_snapshots_data
        mock_repo.get_snapshots_with_metrics.return_value = snapshots_df

        with patch("app.api.watchlist.watchlist_repo", mock_repo), patch(
            "app.api.watchlist.build_score_timeline"
        ) as mock_timeline:
            mock_timeline.return_value = []

            await get_score_history(item_id="item-123", days=30)

            # Verify build_score_timeline was called with correct window_days
            mock_timeline.assert_called_once()
            call_kwargs = mock_timeline.call_args.kwargs
            assert call_kwargs["window_days"] == 30

    @pytest.mark.asyncio
    async def test_parses_json_raw_metrics(
        self, mock_repo: MagicMock, sample_snapshots_data: list[dict]
    ) -> None:
        """Test that JSON raw_metrics are correctly parsed."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = [{"symbol": "AAPL"}]
        mock_repo.get_symbol_by_item_id.return_value = item_df

        snapshots_df = MagicMock()
        snapshots_df.is_empty.return_value = False
        snapshots_df.to_dicts.return_value = sample_snapshots_data
        mock_repo.get_snapshots_with_metrics.return_value = snapshots_df

        with patch("app.api.watchlist.watchlist_repo", mock_repo), patch(
            "app.api.watchlist.build_score_timeline"
        ) as mock_timeline:
            mock_timeline.return_value = []

            await get_score_history(item_id="item-123")

            # Verify that snapshots were created with parsed raw_metrics
            call_args = mock_timeline.call_args[0][0]  # First positional arg is snapshots list
            assert len(call_args) == 2

            # Check that raw_metrics was parsed from JSON string
            first_snapshot = call_args[0]
            assert isinstance(first_snapshot.raw_metrics, dict)
            assert "price" in first_snapshot.raw_metrics
            assert first_snapshot.raw_metrics["price"]["score"] == 70.0

    @pytest.mark.asyncio
    async def test_handles_null_raw_metrics(self, mock_repo: MagicMock) -> None:
        """Test that NULL raw_metrics values are handled gracefully."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = [{"symbol": "AAPL"}]
        mock_repo.get_symbol_by_item_id.return_value = item_df

        snapshots_with_null = [
            {
                "item_id": "item-123",
                "fetched_at": datetime.now(UTC),
                "price": 180.0,
                "technical_score": 80.0,
                "overall_score": 75.0,
                "raw_metrics": None,  # NULL value
            }
        ]

        snapshots_df = MagicMock()
        snapshots_df.is_empty.return_value = False
        snapshots_df.to_dicts.return_value = snapshots_with_null
        mock_repo.get_snapshots_with_metrics.return_value = snapshots_df

        with patch("app.api.watchlist.watchlist_repo", mock_repo), patch(
            "app.api.watchlist.build_score_timeline"
        ) as mock_timeline:
            mock_timeline.return_value = []

            # Should not raise error
            await get_score_history(item_id="item-123")

            # Verify snapshot was created with empty dict for raw_metrics
            call_args = mock_timeline.call_args[0][0]
            first_snapshot = call_args[0]
            assert first_snapshot.raw_metrics == {}

    @pytest.mark.asyncio
    async def test_converts_timeline_to_response_format(
        self, mock_repo: MagicMock, sample_snapshots_data: list[dict]
    ) -> None:
        """Test that timeline points are converted to API response format."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = [{"symbol": "AAPL"}]
        mock_repo.get_symbol_by_item_id.return_value = item_df

        snapshots_df = MagicMock()
        snapshots_df.is_empty.return_value = False
        snapshots_df.to_dicts.return_value = sample_snapshots_data
        mock_repo.get_snapshots_with_metrics.return_value = snapshots_df

        # Mock timeline with sample points
        mock_timeline_points = [
            ScoreTimelinePoint(
                date=datetime(2025, 12, 10, 0, 0, 0, tzinfo=UTC),
                overall_score=75.0,
                price_score=70.0,
                technical_score=80.0,
            ),
            ScoreTimelinePoint(
                date=datetime(2025, 12, 9, 0, 0, 0, tzinfo=UTC),
                overall_score=72.0,
                price_score=68.0,
                technical_score=76.0,
            ),
        ]

        with patch("app.api.watchlist.watchlist_repo", mock_repo), patch(
            "app.api.watchlist.build_score_timeline"
        ) as mock_timeline:
            mock_timeline.return_value = mock_timeline_points

            response = await get_score_history(item_id="item-123")

            assert len(response.history) == 2

            # Check first point
            point1 = response.history[0]
            assert point1.timestamp == "2025-12-10T00:00:00+00:00"
            assert point1.overall == 75.0
            assert point1.price_score == 70.0
            assert point1.technical_score == 80.0

            # Check second point
            point2 = response.history[1]
            assert point2.timestamp == "2025-12-09T00:00:00+00:00"
            assert point2.overall == 72.0

    @pytest.mark.asyncio
    async def test_handles_none_price_and_technical_scores(
        self, mock_repo: MagicMock, sample_snapshots_data: list[dict]
    ) -> None:
        """Test that None price/technical scores default to 0.0 in response."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = [{"symbol": "AAPL"}]
        mock_repo.get_symbol_by_item_id.return_value = item_df

        snapshots_df = MagicMock()
        snapshots_df.is_empty.return_value = False
        snapshots_df.to_dicts.return_value = sample_snapshots_data
        mock_repo.get_snapshots_with_metrics.return_value = snapshots_df

        # Timeline point with None scores
        mock_timeline_points = [
            ScoreTimelinePoint(
                date=datetime(2025, 12, 10, 0, 0, 0, tzinfo=UTC),
                overall_score=75.0,
                price_score=None,
                technical_score=None,
            ),
        ]

        with patch("app.api.watchlist.watchlist_repo", mock_repo), patch(
            "app.api.watchlist.build_score_timeline"
        ) as mock_timeline:
            mock_timeline.return_value = mock_timeline_points

            response = await get_score_history(item_id="item-123")

            point = response.history[0]
            assert point.price_score == 0.0
            assert point.technical_score == 0.0

    @pytest.mark.asyncio
    async def test_raises_500_on_database_error(self, mock_repo: MagicMock) -> None:
        """Test that 500 error is raised on database errors."""
        mock_repo.get_symbol_by_item_id.side_effect = Exception("Database connection failed")

        with patch("app.api.watchlist.watchlist_repo", mock_repo), pytest.raises(
            HTTPException
        ) as exc_info:
            await get_score_history(item_id="item-123")

        assert exc_info.value.status_code == 500
        assert "Failed to get history" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_uses_repository_methods(self, mock_repo: MagicMock) -> None:
        """Test that the endpoint uses repository methods."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = [{"symbol": "AAPL"}]
        mock_repo.get_symbol_by_item_id.return_value = item_df

        snapshots_df = MagicMock()
        snapshots_df.is_empty.return_value = True
        mock_repo.get_snapshots_with_metrics.return_value = snapshots_df

        with patch("app.api.watchlist.watchlist_repo", mock_repo):
            await get_score_history(item_id="item-123")

            # Verify repository methods were called
            mock_repo.get_symbol_by_item_id.assert_called_once_with("item-123")
            mock_repo.get_snapshots_with_metrics.assert_called_once_with("item-123")
