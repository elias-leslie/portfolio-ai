"""SSE endpoint for live Investment Committee events.

The stream:

1. Replays every persisted event for the run ordered by ``seq`` so
   late subscribers see the full history.
2. Subscribes to the per-run asyncio.Queue and yields new events as
   they are emitted by the runner.
3. Terminates when a terminal event lands or the client disconnects.

The Next.js proxy at ``frontend/app/api/[...path]/route.ts`` passes
``text/event-stream`` through unchanged; the
``Cache-Control: no-cache, no-transform`` + ``X-Accel-Buffering: no``
headers prevent intermediaries from buffering the stream.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.agents.committee import store
from app.agents.committee import stream as committee_stream
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/committee", tags=["committee"])

_KEEPALIVE_INTERVAL_SECONDS = 15


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, request: Request) -> StreamingResponse:
    """Server-Sent Events endpoint for a single committee run."""
    try:
        uuid.UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid run_id: {exc}") from exc

    run = await run_in_threadpool(store.get_run_summary, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"committee_run {run_id} not found")

    return StreamingResponse(
        _event_iterator(run_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _event_iterator(run_id: str, request: Request):
    """Yield SSE-formatted lines.

    Phase 1 replays persisted events; phase 2 tails the live queue. A
    periodic comment line keeps the connection alive through
    intermediaries that would otherwise idle-close it.
    """
    history = await run_in_threadpool(store.load_events, run_id)
    seen_seqs = {e["seq"] for e in history if isinstance(e.get("seq"), int)}
    for event in history:
        if await request.is_disconnected():
            return
        yield _format_sse(event)

    summary = await run_in_threadpool(store.get_run_summary, run_id)
    if summary and summary["status"] in {"complete", "approved", "aborted", "failed"}:
        return

    async for chunk in _live_tail(run_id, request, seen_seqs):
        yield chunk


async def _live_tail(
    run_id: str,
    request: Request,
    seen_seqs: set[int],
):
    """Subscribe to the in-memory queue and yield SSE chunks."""
    entry = committee_stream.get(run_id)
    if entry is None:
        return

    keepalive_task: asyncio.Task[None] | None = None
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=64)

    async def _keepalive() -> None:
        while True:
            await asyncio.sleep(_KEEPALIVE_INTERVAL_SECONDS)
            await queue.put(": keepalive\n\n")

    async def _drain() -> None:
        try:
            async for event in committee_stream.subscribe(run_id):
                seq = event.get("seq")
                if isinstance(seq, int):
                    if seq in seen_seqs:
                        continue
                    seen_seqs.add(seq)
                await queue.put(_format_sse(event))
        finally:
            await queue.put("__done__")

    drain_task = asyncio.create_task(_drain())
    keepalive_task = asyncio.create_task(_keepalive())

    try:
        while True:
            if await request.is_disconnected():
                return
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_INTERVAL_SECONDS)
            except TimeoutError:
                continue
            if item == "__done__":
                return
            yield item
    finally:
        keepalive_task.cancel()
        drain_task.cancel()
        for task in (keepalive_task, drain_task):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task


def _format_sse(event: dict[str, Any]) -> str:
    event_type = event.get("type") or "message"
    payload = json.dumps(event, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"
