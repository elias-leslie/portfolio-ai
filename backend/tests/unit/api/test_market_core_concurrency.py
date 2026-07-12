"""Concurrency guarantees for synchronous market providers behind async routes."""

from __future__ import annotations

import asyncio
import time
from importlib import import_module
from threading import Event, Timer
from types import SimpleNamespace

import pytest

from app.api.health import simple_health_check
from app.portfolio.models import PriceData

core_router = import_module("app.api.market.core_router")
core_helpers = import_module("app.api.market._core_helpers")


@pytest.mark.asyncio
async def test_slow_market_provider_does_not_stall_simple_health(monkeypatch) -> None:
    entered = Event()
    release = Event()

    class SlowPriceFetcher:
        def fetch_cached_price_data(self, _symbols: list[str]) -> dict[str, PriceData]:
            entered.set()
            release.wait()
            return {
                "AAPL": PriceData(
                    symbol="AAPL",
                    price=200.0,
                    beta=None,
                    volatility=None,
                    sector="Technology",
                )
            }

    monkeypatch.setattr(core_helpers, "_get_price_fetcher", SlowPriceFetcher)

    # The timer guarantees a broken implementation cannot deadlock the suite. Without
    # threadpool offload, the market call monopolizes the event loop until it fires.
    fail_safe_release = Timer(0.5, release.set)
    fail_safe_release.start()
    started = time.perf_counter()
    market_task = asyncio.create_task(
        core_router.get_prices.__wrapped__(SimpleNamespace(), symbols="AAPL")
    )
    try:
        await asyncio.sleep(0)
        assert await asyncio.to_thread(entered.wait, 0.2)

        health = await simple_health_check()
        health_elapsed = time.perf_counter() - started
        release.set()
        prices = await market_task
    finally:
        release.set()
        fail_safe_release.cancel()
        if not market_task.done():
            await market_task

    assert health == {"status": "healthy"}
    assert health_elapsed < 0.35
    assert prices.count == 1
