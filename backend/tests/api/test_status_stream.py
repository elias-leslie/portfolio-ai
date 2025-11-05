import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.utils.health_checks import (
    AgentStats,
    CacheStats,
    CheckResult,
    WatchlistStats,
)

client = TestClient(app)


@patch("app.api.status_stream.get_all_service_statuses")
@patch("app.api.health.get_api_quotas")
@patch("app.api.health.get_watchlist_stats")
@patch("app.api.health.get_agent_stats")
@patch("app.api.health.get_cache_stats")
@patch("app.api.health.check_sources")
@patch("app.api.health.check_database")
class TestStatusEventStream:
    """Tests for status event stream generator."""

    @pytest.mark.asyncio
    async def test_status_event_stream_yields_sse_format(
        self,
        mock_check_db,
        mock_check_sources,
        mock_get_cache_stats,
        mock_get_agent_stats,
        mock_get_watchlist_stats,
        mock_get_api_quotas,
        mock_get_all_service_statuses,
    ) -> None:
        """Test that status_event_stream yields data in SSE format."""
        print("Starting test_status_event_stream_yields_sse_format")
        from app.api.status_stream import status_event_stream

        # Configure mocks
        mock_check_db.return_value = CheckResult(status="ok")
        mock_check_sources.return_value = {}
        mock_get_cache_stats.return_value = CacheStats(total_cached=0)
        mock_get_agent_stats.return_value = AgentStats(
            total_runs=0, completed_runs=0, failed_runs=0
        )
        mock_get_watchlist_stats.return_value = WatchlistStats(total_items=0)
        mock_get_api_quotas.return_value = []
        mock_get_all_service_statuses.return_value = {}

        # Collect first 2 events
        events: list[str] = []
        async for event in status_event_stream(max_iterations=2):
            print(f"Received event: {event}")
            events.append(event)

        # Verify we got events
        assert len(events) == 2

        # Each event should start with "data: " and end with "\n\n"
        for event in events:
            assert event.startswith("data: ")
            assert event.endswith("\n\n")

            # Extract JSON part
            json_str = event[6:-2]  # Remove "data: " prefix and "\n\n" suffix
            data = json.loads(json_str)

            # Verify expected fields
            assert "status" in data
            assert "services" in data
            assert "timestamp" in data
            assert isinstance(data["services"], dict)
        print("Finished test_status_event_stream_yields_sse_format")

    @pytest.mark.asyncio
    async def test_status_event_stream_handles_cancellation(
        self,
        mock_check_db,
        mock_check_sources,
        mock_get_cache_stats,
        mock_get_agent_stats,
        mock_get_watchlist_stats,
        mock_get_api_quotas,
        mock_get_all_service_statuses,
    ) -> None:
        """Test that status_event_stream handles asyncio.CancelledError gracefully."""
        print("Starting test_status_event_stream_handles_cancellation")
        from app.api.status_stream import status_event_stream

        # Configure mocks
        mock_check_db.return_value = CheckResult(status="ok")
        mock_check_sources.return_value = {}
        mock_get_cache_stats.return_value = CacheStats(total_cached=0)
        mock_get_agent_stats.return_value = AgentStats(
            total_runs=0, completed_runs=0, failed_runs=0
        )
        mock_get_watchlist_stats.return_value = WatchlistStats(total_items=0)
        mock_get_api_quotas.return_value = []
        mock_get_all_service_statuses.return_value = {}

        # Start stream and cancel it
        stream = status_event_stream(max_iterations=2)
        first_event = await anext(stream)

        # Verify first event is valid
        assert first_event.startswith("data: ")

        # Cancel the stream (simulates client disconnect)
        await stream.aclose()
        print("Finished test_status_event_stream_handles_cancellation")
