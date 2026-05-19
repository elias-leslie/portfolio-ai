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
    assert sem._value == 3


def test_get_llm_semaphore_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMMITTEE_LLM_CONCURRENCY", raising=False)
    monkeypatch.setitem(stages._llm_semaphore_cell, "sem", None)
    sem = stages._get_llm_semaphore()
    assert sem._value == stages._DEFAULT_LLM_CONCURRENCY


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
            captured["payload"] = __import__("json").loads(kw["messages"][0]["content"])
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
    assert "signal_sleeve" in captured["payload"]
    assert "cluster_weights" in captured["payload"]


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


# ---------- portfolio_context wiring ----------


def _install_capturing_agent_hub_client(
    monkeypatch: pytest.MonkeyPatch, captured: dict[str, Any], response_json: str
) -> None:
    """Replace AgentHubAPIClient with a fake that captures the user payload."""
    import json as _json

    class FakeAgentHubClient:
        def __init__(self, **_kw: Any) -> None:
            return None

        async def complete_messages_async(self, **kw: Any) -> Any:
            user_msg = kw["messages"][0]["content"]
            captured["payload"] = _json.loads(user_msg)
            captured["agent_slug"] = kw.get("agent_slug")
            return type("R", (), {"content": response_json, "tokens": 1})()

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(stages, "AgentHubAPIClient", FakeAgentHubClient)
    monkeypatch.setitem(stages._llm_semaphore_cell, "sem", None)


_PORTFOLIO_CTX_FIXTURE: dict[str, Any] = {
    "held": True,
    "position_in_symbol": {"shares": 10.0, "weight_pct": 8.0},
    "target_sector": "Technology",
    "sector_exposure_pct": 28.0,
    "top_5_positions": [{"symbol": "NVDA", "weight_pct": 8.0, "sector": "Technology"}],
    "cash_pct": 12.5,
}


@pytest.mark.asyncio
async def test_run_trader_forwards_portfolio_context(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    _install_capturing_agent_hub_client(
        monkeypatch,
        captured,
        response_json=(
            '{"action": "buy", "qty_pct": 0.05, "entry_price": 800.0, '
            '"stop_price": 760.0, "horizon": "swing", "rationale_md": "ok"}'
        ),
    )
    await stages.run_trader(
        symbol="NVDA",
        analyst_outputs=[],
        debate_history=[],
        portfolio_value=1_000_000.0,
        current_price=800.0,
        past_decisions=[],
        portfolio_context=_PORTFOLIO_CTX_FIXTURE,
    )
    assert captured["agent_slug"] == stages.SLUG_TRADER
    assert captured["payload"]["portfolio_context"] == _PORTFOLIO_CTX_FIXTURE


@pytest.mark.asyncio
async def test_run_risk_forwards_portfolio_context(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.committee.schemas import IpsResult, TradeProposal

    captured: dict[str, Any] = {}
    _install_capturing_agent_hub_client(
        monkeypatch,
        captured,
        response_json='{"vote": "approve", "score": 0.4, "narrative_md": "ok", "objections": []}',
    )
    proposal = TradeProposal(
        action="buy",
        qty_pct=0.05,
        entry_price=800.0,
        stop_price=760.0,
        horizon="swing",
        rationale_md="",
        signers=[],
        tokens=0,
        latency_ms=0,
    )
    await stages.run_risk(
        stages.SLUG_RISK_NEUTRAL,
        proposal=proposal,
        analyst_outputs=[],
        debate_history=[],
        ips_result=IpsResult(checks=[], all_passed=True),
        portfolio_context=_PORTFOLIO_CTX_FIXTURE,
    )
    assert captured["payload"]["portfolio_context"] == _PORTFOLIO_CTX_FIXTURE


@pytest.mark.asyncio
async def test_run_pm_forwards_portfolio_context(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.committee.schemas import IpsResult, TradeProposal

    captured: dict[str, Any] = {}
    _install_capturing_agent_hub_client(
        monkeypatch,
        captured,
        response_json=(
            '{"action": "buy", "qty_pct": 0.04, "confidence": 0.6, '
            '"horizon": "swing", "rationale_md": "ok"}'
        ),
    )
    proposal = TradeProposal(
        action="buy",
        qty_pct=0.05,
        entry_price=800.0,
        stop_price=760.0,
        horizon="swing",
        rationale_md="",
        signers=[],
        tokens=0,
        latency_ms=0,
    )
    await stages.run_pm(
        proposal=proposal,
        debate_history=[],
        risk_votes=[],
        ips_result=IpsResult(checks=[], all_passed=True),
        past_decisions=[],
        portfolio_context=_PORTFOLIO_CTX_FIXTURE,
    )
    assert captured["payload"]["portfolio_context"] == _PORTFOLIO_CTX_FIXTURE
    assert captured["agent_slug"] == stages.SLUG_PM


def test_context_slice_for_includes_portfolio_for_analysts() -> None:
    """Analyst slices include portfolio context for actionability."""
    context = {
        "fundamentals": {"pillar": 0.7},
        "valuation": {"overall_score": 0.5},
        "fundamentals_raw": {"valuation": {"pe_ratio_trailing": 30}},
        "news": {"section": {"items": []}},
        "news_raw": {"articles": [{"headline": "x"}]},
        "sentiment": {},
        "options": {},
        "ohlcv": {},
        "indicators": {},
        "technical_indicators_raw": {"rsi_14": 60},
        "portfolio": {"position_in_symbol": {"shares": 10.0}},
    }
    for slug in stages.ANALYST_SLUGS:
        slice_ = stages._context_slice_for(slug, context)
        assert slice_["portfolio"] == {"position_in_symbol": {"shares": 10.0}}
