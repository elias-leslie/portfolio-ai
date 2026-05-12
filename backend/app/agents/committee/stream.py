"""Per-run asyncio.Queue registry + pause/resume/abort control flags.

The committee runner emits events into a per-run-id queue. The SSE
endpoint subscribes to that queue and forwards events to the client.
The same registry holds a control flag so the runner can honor user
pause/resume/abort between stages (no hard cost ceiling).

Lifetime: registry entries are created at run.start, cleared when the
final terminal event (run.complete, run.aborted, or run.failed) is
emitted AND all subscribers have drained.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RunControl:
    """Pause/resume/abort signal carrier for one run."""

    state: str = "running"  # "running" | "paused" | "aborted"
    event: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self) -> None:
        self.event.set()  # starts "go"


@dataclass
class _RunRegistry:
    queue: asyncio.Queue[dict[str, Any]]
    control: RunControl
    feedback: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    subscribers: int = 0
    terminated: bool = False


_registry: dict[str, _RunRegistry] = {}
_registry_lock = asyncio.Lock()

_SENTINEL_DONE = {"__sentinel__": "done"}


async def register(run_id: str) -> _RunRegistry:
    """Create the per-run queue + control entry. Idempotent."""
    async with _registry_lock:
        if run_id in _registry:
            return _registry[run_id]
        entry = _RunRegistry(
            queue=asyncio.Queue(maxsize=1024),
            control=RunControl(),
        )
        _registry[run_id] = entry
        return entry


def get(run_id: str) -> _RunRegistry | None:
    """Return the registry entry if present, else None."""
    return _registry.get(run_id)


async def emit(run_id: str, event: dict[str, Any]) -> None:
    """Push an event into the run's queue. No-op if the run is unknown."""
    entry = _registry.get(run_id)
    if entry is None:
        logger.warning("committee_emit_unknown_run", run_id=run_id, type=event.get("type"))
        return
    await entry.queue.put(event)
    if event.get("type") in {"run.complete", "run.aborted", "run.failed"}:
        entry.terminated = True
        await entry.queue.put(_SENTINEL_DONE)


async def check_control(run_id: str) -> None:
    """Block while the run is paused; raise CancelledError if aborted.

    The runner calls this between stages and inside the debate loop so
    pause/resume/abort take effect promptly without forcing every
    coroutine to know about the control object.
    """
    entry = _registry.get(run_id)
    if entry is None:
        return
    if entry.control.state == "aborted":
        raise asyncio.CancelledError("committee run aborted by user")
    if entry.control.state == "paused":
        await entry.control.event.wait()
        if entry.control.state == "aborted":
            raise asyncio.CancelledError("committee run aborted by user")


def pause(run_id: str) -> bool:
    """Mark the run paused. Returns True if the state changed."""
    entry = _registry.get(run_id)
    if entry is None or entry.control.state != "running":
        return False
    entry.control.state = "paused"
    entry.control.event.clear()
    return True


def resume(run_id: str) -> bool:
    """Unblock a paused run. Returns True if the state changed."""
    entry = _registry.get(run_id)
    if entry is None or entry.control.state != "paused":
        return False
    entry.control.state = "running"
    entry.control.event.set()
    return True


def abort(run_id: str) -> bool:
    """Signal abort; the runner picks it up at the next check_control."""
    entry = _registry.get(run_id)
    if entry is None:
        return False
    entry.control.state = "aborted"
    entry.control.event.set()
    return True


def enqueue_feedback(run_id: str, payload: dict[str, Any]) -> bool:
    """Enqueue a user feedback claim for the running graph to consume.

    Returns False if the run is unknown (terminated + cleaned up); the
    API layer still persists the input for the audit trail in that
    case but the live re-evaluation can't fire.
    """
    entry = _registry.get(run_id)
    if entry is None:
        return False
    entry.feedback.put_nowait(payload)
    return True


def drain_feedback(run_id: str) -> list[dict[str, Any]]:
    """Pop every queued feedback claim. Non-blocking; returns ``[]`` if none."""
    entry = _registry.get(run_id)
    if entry is None:
        return []
    drained: list[dict[str, Any]] = []
    while not entry.feedback.empty():
        try:
            drained.append(entry.feedback.get_nowait())
        except asyncio.QueueEmpty:
            break
    return drained


async def subscribe(run_id: str):
    """Async iterator over events for one run.

    Yields each event as it lands in the queue. Terminates when the
    sentinel is observed (run reached a terminal event).
    """
    entry = _registry.get(run_id)
    if entry is None:
        return
    entry.subscribers += 1
    try:
        while True:
            event = await entry.queue.get()
            if event is _SENTINEL_DONE:
                # Re-post sentinel so other subscribers (if any) also terminate.
                await entry.queue.put(_SENTINEL_DONE)
                return
            yield event
    finally:
        entry.subscribers -= 1
        if entry.terminated and entry.subscribers <= 0:
            _registry.pop(run_id, None)
