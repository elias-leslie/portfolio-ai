import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestStatusEventStream:
    """Tests for status event stream generator."""

    @pytest.mark.asyncio
    @patch("app.api.status_stream.gather_comprehensive_status")
    async def test_status_event_stream_yields_sse_format(
        self,
        mock_gather_status,
    ) -> None:
        """Test that status_event_stream yields data in SSE format."""
        print("Starting test_status_event_stream_yields_sse_format")
        from app.api.status_stream import status_event_stream

        # Configure mock status payload
        mock_gather_status.return_value = {
            "status": "healthy",
            "services": {},
            "timestamp": "2025-11-12T00:00:00Z",
        }

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
    @patch("app.api.status_stream.gather_comprehensive_status")
    async def test_status_event_stream_handles_cancellation(
        self,
        mock_gather_status,
    ) -> None:
        """Test that status_event_stream handles asyncio.CancelledError gracefully."""
        print("Starting test_status_event_stream_handles_cancellation")
        from app.api.status_stream import status_event_stream

        mock_gather_status.return_value = {
            "status": "healthy",
            "services": {},
            "timestamp": "2025-11-12T00:00:00Z",
        }

        # Start stream and cancel it
        stream = status_event_stream(max_iterations=2)
        first_event = await anext(stream)

        # Verify first event is valid
        assert first_event.startswith("data: ")

        # Cancel the stream (simulates client disconnect)
        await stream.aclose()
        print("Finished test_status_event_stream_handles_cancellation")
