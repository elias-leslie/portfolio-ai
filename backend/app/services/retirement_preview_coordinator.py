"""Share identical previews and bound CPU work without caching failures."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Callable
from time import monotonic
from typing import Any

from starlette.concurrency import run_in_threadpool


class PreviewCoordinator:
    def __init__(self) -> None:
        self.running: dict[str, asyncio.Task[Any]] = {}
        self.completed: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self.limit = asyncio.Semaphore(2)
        self.generation = 0
        self.waiters: dict[str, int] = {}
        self.started: set[str] = set()

    def invalidate(self) -> None:
        self.completed.clear()
        self.generation += 1

    async def get(self, key: str, calculate: Callable[[], Any]) -> Any:
        key = f"{self.generation}:{key}"
        saved = self.completed.get(key)
        if saved and monotonic() - saved[0] < 30:
            return saved[1]
        if key not in self.running:

            async def execute() -> Any:
                try:
                    async with self.limit:
                        self.started.add(key)
                        value = await run_in_threadpool(calculate)
                    self.completed[key] = (monotonic(), value)
                    self.completed.move_to_end(key)
                    while len(self.completed) > 16:
                        self.completed.popitem(last=False)
                    return value
                finally:
                    self.running.pop(key, None)
                    self.started.discard(key)

            self.running[key] = asyncio.create_task(execute())
        self.waiters[key] = self.waiters.get(key, 0) + 1
        try:
            # A disconnected waiter cannot cancel work shared with another preview.
            return await asyncio.shield(self.running[key])
        finally:
            self.waiters[key] -= 1
            if self.waiters[key] == 0:
                self.waiters.pop(key)
                queued = self.running.get(key)
                if queued is not None and key not in self.started:
                    queued.cancel()


preview_coordinator = PreviewCoordinator()
