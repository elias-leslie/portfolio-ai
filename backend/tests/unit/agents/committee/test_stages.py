"""Unit tests for committee stage Agent Hub wrappers."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.agents.committee import stages


@pytest.mark.asyncio
async def test_complete_times_out_and_closes_agent_hub_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = False

    class SlowAgentHubClient:
        def __init__(self, **_kw: Any) -> None:
            return None

        async def complete_messages_async(self, **_kw: Any) -> Any:
            await asyncio.sleep(1)

        async def aclose(self) -> None:
            nonlocal closed
            closed = True

    monkeypatch.setattr(stages, "AgentHubAPIClient", SlowAgentHubClient)
    monkeypatch.setattr(stages, "_AGENT_COMPLETION_TIMEOUT_SECONDS", 0.01)

    with pytest.raises(TimeoutError, match="committee.test timed out after 0.01s"):
        await stages._complete("test-agent", {"symbol": "NVDA"}, purpose="committee.test")

    assert closed is True


@pytest.mark.asyncio
async def test_complete_acquires_concurrency_semaphore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cap simultaneous in-flight LLM calls at the configured concurrency."""
    monkeypatch.setattr(stages, "_AGENT_COMPLETION_TIMEOUT_SECONDS", 5)
    monkeypatch.setenv("COMMITTEE_LLM_CONCURRENCY", "2")
    monkeypatch.setitem(stages._llm_semaphore_cell, "sem", None)

    in_flight = 0
    peak = 0
    gate = asyncio.Event()

    class GatedAgentHubClient:
        def __init__(self, **_kw: Any) -> None:
            return None

        async def complete_messages_async(self, **_kw: Any) -> Any:
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await gate.wait()
            in_flight -= 1
            return type("R", (), {"content": "{}", "tokens": 0})()

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(stages, "AgentHubAPIClient", GatedAgentHubClient)

    tasks = [
        asyncio.create_task(
            stages._complete("test-agent", {"i": i}, purpose=f"committee.test.{i}")
        )
        for i in range(5)
    ]
    # Let the first wave acquire the semaphore.
    for _ in range(20):
        await asyncio.sleep(0)
    assert peak == 2, f"expected the semaphore to cap concurrency at 2, saw peak={peak}"

    gate.set()
    await asyncio.gather(*tasks)
    assert peak == 2  # never exceeded 2 despite 5 callers


def test_get_llm_semaphore_honors_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMMITTEE_LLM_CONCURRENCY", "3")
    monkeypatch.setitem(stages._llm_semaphore_cell, "sem", None)
    sem = stages._get_llm_semaphore()
    assert sem._value == 3  # type: ignore[attr-defined]


def test_get_llm_semaphore_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMMITTEE_LLM_CONCURRENCY", raising=False)
    monkeypatch.setitem(stages._llm_semaphore_cell, "sem", None)
    sem = stages._get_llm_semaphore()
    assert sem._value == stages._DEFAULT_LLM_CONCURRENCY  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_run_tier1_screen_parses_response_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tier-1 returns a typed Tier1Verdict with score / conviction / top_factor coerced."""
    captured: dict[str, Any] = {}

    class FakeAgentHubClient:
        def __init__(self, **_kw: Any) -> None:
            return None

        async def complete_messages_async(self, **kw: Any) -> Any:
            captured.update(kw)
            return type("R", (), {
                "content": '{"score": 0.72, "conviction": "high", "top_factor": "mom_xover", "one_line_rationale": "Decisive multi-factor setup."}',
                "tokens": 42,
            })()

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(stages, "AgentHubAPIClient", FakeAgentHubClient)
    monkeypatch.setitem(stages._llm_semaphore_cell, "sem", None)
    monkeypatch.setenv("COMMITTEE_LLM_CONCURRENCY", "4")

    verdict = await stages.run_tier1_screen(
        symbol="nvda",
        scanner_factors={"rank": 1, "composite_pct": 98.0},
        context_bundle={"current_price": 120.5},
        gate_zone="FULL_DEPLOY",
    )

    assert verdict.symbol == "NVDA"
    assert verdict.score == pytest.approx(0.72)
    assert verdict.conviction == "high"
    assert verdict.top_factor == "mom_xover"
    assert verdict.agent_slug == stages.SLUG_TIER1
    # Concurrency cap shouldn't be re-bound by a second call.
    assert captured["agent_slug"] == stages.SLUG_TIER1


@pytest.mark.asyncio
async def test_run_tier1_screen_coerces_bad_enum_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown conviction / top_factor values fall back to safe defaults rather than crashing."""

    class FakeAgentHubClient:
        def __init__(self, **_kw: Any) -> None:
            return None

        async def complete_messages_async(self, **_kw: Any) -> Any:
            return type("R", (), {
                "content": '{"score": 1.7, "conviction": "EXTREME", "top_factor": "VIBES", "one_line_rationale": ""}',
                "tokens": 0,
            })()

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(stages, "AgentHubAPIClient", FakeAgentHubClient)
    monkeypatch.setitem(stages._llm_semaphore_cell, "sem", None)

    verdict = await stages.run_tier1_screen(
        symbol="aapl",
        scanner_factors={},
        context_bundle={},
        gate_zone="REDUCED",
    )

    # score clamped to [-1, 1]
    assert verdict.score == pytest.approx(1.0)
    assert verdict.conviction == "low"
    assert verdict.top_factor == "other"
