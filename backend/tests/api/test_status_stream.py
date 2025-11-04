"""Tests for SSE status streaming endpoints."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestStatusEventStream:
    """Tests for status event stream generator."""

    @pytest.mark.asyncio
    async def test_status_event_stream_yields_sse_format(self) -> None:
        """Test that status_event_stream yields data in SSE format."""
        from app.api.status_stream import status_event_stream

        # Collect first 2 events
        events: list[str] = []
        async for event in status_event_stream():
            events.append(event)
            if len(events) >= 2:
                break

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

    @pytest.mark.asyncio
    async def test_status_event_stream_handles_cancellation(self) -> None:
        """Test that status_event_stream handles asyncio.CancelledError gracefully."""
        from app.api.status_stream import status_event_stream

        # Start stream and cancel it
        stream = status_event_stream()
        first_event = await anext(stream)

        # Verify first event is valid
        assert first_event.startswith("data: ")

        # Cancel the stream (simulates client disconnect)
        await stream.aclose()


class TestStatusStreamEndpoint:
    """Tests for SSE streaming endpoint."""

    def test_status_stream_endpoint_returns_event_stream(self) -> None:
        """Test GET /api/status/stream returns event-stream content type."""
        # Use stream=True to get streaming response
        with client.stream("GET", "/api/status/stream") as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["connection"] == "keep-alive"

            # Read first few chunks
            chunks_read = 0
            for chunk in response.iter_lines():
                if chunk:
                    # Should be SSE format: "data: {...}"
                    assert chunk.startswith("data: ")
                    chunks_read += 1
                    if chunks_read >= 2:
                        break

            assert chunks_read >= 2

    def test_status_stream_endpoint_sends_valid_json(self) -> None:
        """Test that SSE endpoint sends valid JSON in data field."""
        with client.stream("GET", "/api/status/stream") as response:
            assert response.status_code == 200

            # Read first event
            for line in response.iter_lines():
                if line.startswith("data: "):
                    json_str = line[6:]  # Remove "data: " prefix
                    data = json.loads(json_str)

                    # Verify structure
                    assert "status" in data
                    assert "services" in data
                    assert "timestamp" in data
                    break
