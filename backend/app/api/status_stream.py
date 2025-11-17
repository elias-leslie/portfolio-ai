"""Server-Sent Events (SSE) streaming for real-time status updates."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..api.health import health_service
from ..logging_config import get_logger
from ..services.service_monitor import get_all_service_statuses
from .types import SystemStatusDict

logger = get_logger(__name__)

router = APIRouter(prefix="/api/status", tags=["status"])


def gather_comprehensive_status() -> SystemStatusDict:
    """Gather comprehensive system status from health check and service monitor.

    Returns:
        Dictionary with status, services, timestamp, and other health info
    """
    # Get full health check (includes database, sources, stats)
    health_response = health_service.perform_health_check()

    # Get service statuses (skip slow Celery inspect for streaming performance)
    service_statuses = get_all_service_statuses(skip_slow_checks=True)
    services: dict[str, object] = {
        name: status.model_dump() for name, status in service_statuses.items()
    }

    # Combine into comprehensive status
    # Use model_dump(mode='json') to ensure datetime objects are serialized
    return {
        "status": health_response["status"],  # type: ignore
        "services": services,
        "timestamp": datetime.now(UTC).isoformat(),
        "uptime_seconds": health_response["uptime_seconds"],  # type: ignore
        "checks": {
            name: check.model_dump(mode="json") for name, check in health_response["checks"].items()
        },
        "sources": {
            name: source.model_dump(mode="json")
            for name, source in health_response["sources"].items()
        },
    }


async def status_event_stream(max_iterations: int | None = None) -> AsyncGenerator[str]:
    """Generate Server-Sent Events stream for status updates.

    Yields SSE-formatted messages every 2 seconds with current system status.
    Handles client disconnection via asyncio.CancelledError.

    Yields:
        SSE-formatted strings: "data: {json}\n\n"
    """
    try:
        count = 0
        while True:
            if max_iterations is not None and count >= max_iterations:
                break
            # Gather current status
            status_data = gather_comprehensive_status()

            # Format as SSE event
            json_str = json.dumps(status_data)
            sse_message = f"data: {json_str}\n\n"

            yield sse_message

            count += 1

            # Wait 2 seconds before next update
            await asyncio.sleep(2)

    except asyncio.CancelledError:
        # Client disconnected - clean shutdown
        logger.info("status_stream_client_disconnected")
        raise


@router.get("/stream")
async def stream_status_updates() -> StreamingResponse:
    """SSE endpoint for real-time status updates.

    Streams status updates every 2 seconds in Server-Sent Events format.
    Clients should use EventSource API to consume this stream.

    Returns:
        StreamingResponse with text/event-stream content type
    """
    return StreamingResponse(
        status_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
