"""Graph runner contract tests for ``app.agents.committee.graph``.

All Agent Hub I/O is monkeypatched at the ``stages.*`` boundary so
the test runs offline. Storage writes are replaced with in-memory
captures. The aim is to pin the plan's contract: stage order,
3-round debate, KPI ticker behavior, every SSE event type firing
at least once, past-context loader invocation, cooperative abort.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.agents.committee import graph as graph_mod
from app.agents.committee import stream as committee_stream
from app.agents.committee.schemas import (
    AnalystOutput,
    Evidence,
    IpsCheck,
    IpsResult,
    PastDecisionEntry,
    PmDecision,
    ResearcherOutput,
    RiskObjection,
    RiskVoteOutput,
    TradeProposal,
)


def _analyst(slug: str, score: float = 0.5) -> AnalystOutput:
    return AnalystOutput(
        agent_slug=slug,
        content_md=f"{slug} thesis content with enough text to be realistic.",
        score=score,
        evidence=[Evidence(claim=f"{slug} evidence", side="bull", weight=1.0)],
        tokens=1000,
        latency_ms=400,
    )


def _researcher(slug: str, role: Any, score: float) -> ResearcherOutput:
    return ResearcherOutput(
        agent_slug=slug,
        role=role,
        argument_md=f"{slug} argument body",
        rebuttals_md="",
        score=score,
        evidence=[Evidence(claim=f"{slug} ev", side=role, weight=1.0)],
        tokens=800,
        latency_ms=350,
    )


def _proposal(action: Any = "buy") -> TradeProposal:
    return TradeProposal(
        action=action,
        qty_pct=0.04,
        entry_price=200.0,
        stop_price=180.0,
        horizon="3-6mo",
        rationale_md="canned trader rationale",
        signers=["fundamentals-v1"],
        tokens=600,
        latency_ms=250,
    )


def _risk_vote(slug: str, score: float = 0.3) -> RiskVoteOutput:
    return RiskVoteOutput(
        agent_slug=slug,
        vote="approve",
        score=score,
        narrative_md=f"{slug} narrative",
        objections=[RiskObjection(claim="tail risk", severity="low")],
        tokens=500,
        latency_ms=200,
    )


def _pm_decision(action: Any = "buy") -> PmDecision:
    return PmDecision(
        action=action,
        qty_pct=0.04,
        qty=100,
        confidence=0.78,
        horizon="3-6mo",
        signers=[
            "fundamentals-v1",
            "news-grounded-v1",
            "bull-researcher-v1",
            "trader-v1",
        ],
        rationale_md="canned PM rationale",
        tokens=700,
        latency_ms=300,
    )


def _ips_pass() -> IpsResult:
    return IpsResult(
        checks=[
            IpsCheck(
                name="concentration",
                passed=True,
                severity="info",
                detail="ok",
                value=0.04,
                threshold=0.25,
            ),
            IpsCheck(
                name="tax_bill",
                passed=True,
                severity="info",
                detail="ok",
                value=0.0,
                threshold=None,
            ),
            IpsCheck(
                name="sector_exposure",
                passed=True,
                severity="info",
                detail="ok",
                value=0.18,
                threshold=0.35,
            ),
            IpsCheck(
                name="wash_sale",
                passed=True,
                severity="info",
                detail="ok",
            ),
        ],
        all_passed=True,
    )


@pytest.fixture(autouse=True)
def _reset_stream_registry():
    """Clear the module-level stream registry between tests.

    The committee.stream registry persists across tests in the same
    process. After ``stream.abort`` flips a registry entry to
    ``aborted``, the *next* test's ``stream.register("run-uuid")``
    would return that same entry — which would make the runner exit
    immediately at the first ``check_control``. Clearing the registry
    keeps each test self-contained.
    """
    committee_stream._registry.clear()
    yield
    committee_stream._registry.clear()


@pytest.fixture
def captured_events(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace storage + Agent Hub layer with in-memory captures."""
    events: list[dict[str, Any]] = []
    counters = {"seq": 0}

    def fake_persist_event(run_id: str, **kw: Any) -> tuple[int, int]:
        counters["seq"] += 1
        events.append({"run_id": run_id, **kw})
        return counters["seq"], counters["seq"]

    async def fake_stream_emit(run_id: str, event: dict[str, Any]) -> None:
        return None

    def fake_create_run(**kw: Any) -> str:
        return "run-uuid"

    def fake_mark(*_a: Any, **_k: Any) -> None:
        return None

    def fake_load_past_decisions(symbol: str, household_id: str | None, *, limit: int = 5):
        # Capture into a sentinel event so the assertion can see it.
        events.append(
            {
                "type": "__past_decisions_loaded__",
                "symbol": symbol,
                "household_id": household_id,
                "limit": limit,
            }
        )
        return [
            PastDecisionEntry(
                run_id=f"prior-{i}",
                started_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
                action="hold",
                qty_pct=0.0,
                realized_pnl=0.0,
                horizon="1mo",
            )
            for i in range(2)
        ]

    monkeypatch.setattr(graph_mod.store, "create_run", fake_create_run)
    monkeypatch.setattr(graph_mod.store, "mark_running", fake_mark)
    monkeypatch.setattr(graph_mod.store, "mark_complete", fake_mark)
    monkeypatch.setattr(graph_mod.store, "mark_aborted", fake_mark)
    monkeypatch.setattr(graph_mod.store, "mark_failed", fake_mark)
    monkeypatch.setattr(graph_mod.store, "persist_event", fake_persist_event)
    monkeypatch.setattr(graph_mod.store, "load_past_decisions", fake_load_past_decisions)
    monkeypatch.setattr(committee_stream, "emit", fake_stream_emit)

    # Skip the symbol-intelligence build (it tries real HTTP).
    async def fake_ensure(symbol: str) -> None:
        return None

    async def fake_build_context(symbol: str) -> dict[str, Any]:
        return {"current_price": 200.0}

    monkeypatch.setattr(graph_mod, "_ensure_ohlcv", fake_ensure)
    monkeypatch.setattr(graph_mod, "_build_context", fake_build_context)
    monkeypatch.setattr(graph_mod, "_portfolio_value_estimate", lambda _hh: 500_000.0)

    # Stages.
    async def fake_run_analyst(slug: str, **kw: Any) -> AnalystOutput:
        return _analyst(slug)

    async def fake_run_researcher(side: str, **kw: Any) -> ResearcherOutput:
        slug = "bull-researcher-v1" if side == "bull" else "bear-researcher-v1"
        return _researcher(slug, role=side, score=0.6 if side == "bull" else 0.4)

    async def fake_run_trader(**kw: Any) -> TradeProposal:
        return _proposal()

    async def fake_run_risk(slug: str, **kw: Any) -> RiskVoteOutput:
        return _risk_vote(slug)

    async def fake_run_pm(**kw: Any) -> PmDecision:
        return _pm_decision()

    monkeypatch.setattr(graph_mod.stages, "run_analyst", fake_run_analyst)
    monkeypatch.setattr(graph_mod.stages, "run_researcher", fake_run_researcher)
    monkeypatch.setattr(graph_mod.stages, "run_trader", fake_run_trader)
    monkeypatch.setattr(graph_mod.stages, "run_risk", fake_run_risk)
    monkeypatch.setattr(graph_mod.stages, "run_pm", fake_run_pm)

    # IPS is deterministic but pulls real DB — short-circuit.
    monkeypatch.setattr(
        graph_mod.ips_mod, "ips_evaluate", lambda *_a, **_kw: _ips_pass()
    )

    # Tighten the feedback-wait so the test doesn't sleep 30 seconds.
    monkeypatch.setattr(graph_mod, "_FEEDBACK_WAIT_SECONDS", 0.1)
    monkeypatch.setattr(graph_mod, "_FEEDBACK_POLL_INTERVAL", 0.02)
    monkeypatch.setattr(graph_mod, "_KPI_TICK_INTERVAL", 0.05)

    return events


@pytest.mark.asyncio
async def test_happy_path_emits_every_stage_in_plan_order_with_three_debate_rounds(
    captured_events: list[dict[str, Any]],
) -> None:
    """Plan: analysts -> researchers (x3 rounds) -> trader -> ips -> risk -> pm -> run.complete."""
    await committee_stream.register("run-uuid")
    await graph_mod.run_committee(
        run_id="run-uuid",
        symbol="NVDA",
        household_id=None,
    )

    stage_enters = [e for e in captured_events if e.get("type") == "stage.enter"]
    stages_seen = [
        (e.get("content") or {}).get("stage") for e in stage_enters
    ]
    assert stages_seen == [
        "analysts",
        "researchers",
        "trader",
        "ips",
        "risk",
        "pm",
    ]

    round_starts = [e for e in captured_events if e.get("type") == "debate.round.start"]
    round_ends = [e for e in captured_events if e.get("type") == "debate.round.end"]
    assert len(round_starts) == 3
    assert len(round_ends) == 3

    # Each round produced one bull + one bear agent.output (concurrent — order may vary).
    debate_outputs = [
        e
        for e in captured_events
        if e.get("type") == "agent.output" and e.get("stage") == "researchers"
    ]
    assert len(debate_outputs) == 6  # 3 rounds x (bull + bear)
    roles = {e.get("role") for e in debate_outputs}
    assert roles == {"bull", "bear"}


@pytest.mark.asyncio
async def test_every_plan_schema_event_type_fires_at_least_once(
    captured_events: list[dict[str, Any]],
) -> None:
    """Plan §SSE event schema: every event_type below must fire on a happy run."""
    await committee_stream.register("run-uuid")
    await graph_mod.run_committee(
        run_id="run-uuid",
        symbol="NVDA",
        household_id=None,
    )

    types_seen = {e.get("type") for e in captured_events if "type" in e}
    expected = {
        "run.start",
        "stage.enter",
        "agent.output",
        "debate.round.start",
        "debate.round.end",
        "ips.check",
        "trader.proposal",
        "risk.vote",
        "pm.decision",
        "run.complete",
        "kpi.tick",
    }
    missing = expected - types_seen
    assert not missing, f"plan-schema event types missing: {missing}"


@pytest.mark.asyncio
async def test_past_decision_loader_called_with_symbol_and_household(
    captured_events: list[dict[str, Any]],
) -> None:
    """Plan §Memory injection: past decisions loaded with symbol + household + limit=5."""
    await committee_stream.register("run-uuid")
    await graph_mod.run_committee(
        run_id="run-uuid",
        symbol="NVDA",
        household_id="hh-1",
    )

    loader_events = [
        e for e in captured_events if e.get("type") == "__past_decisions_loaded__"
    ]
    assert len(loader_events) == 1
    assert loader_events[0]["symbol"] == "NVDA"
    assert loader_events[0]["household_id"] == "hh-1"
    assert loader_events[0]["limit"] == 5


@pytest.mark.asyncio
async def test_kpi_tick_fires_during_run_and_stops_after_complete(
    captured_events: list[dict[str, Any]],
) -> None:
    """KPI ticker must fire at least once and be cancelled before run.complete persists.

    Implementation contract: the ticker is awaited in try/finally so a
    cancellation cannot leak. We assert: at least one kpi.tick was
    emitted while the run was alive, and no kpi.tick is emitted after
    the run.complete event.
    """
    await committee_stream.register("run-uuid")
    await graph_mod.run_committee(
        run_id="run-uuid",
        symbol="NVDA",
        household_id=None,
    )

    ticks = [e for e in captured_events if e.get("type") == "kpi.tick"]
    assert len(ticks) >= 1, "kpi.tick should have fired during the run"

    # No tick should appear after run.complete (the ticker was cancelled in try/finally).
    types_in_order = [e.get("type") for e in captured_events if "type" in e]
    assert "run.complete" in types_in_order
    complete_idx = types_in_order.index("run.complete")
    after_complete = types_in_order[complete_idx + 1 :]
    assert "kpi.tick" not in after_complete, (
        "kpi.tick leaked past run.complete — ticker was not cancelled"
    )


@pytest.mark.asyncio
async def test_abort_cancels_ticker_and_emits_run_aborted(
    monkeypatch: pytest.MonkeyPatch,
    captured_events: list[dict[str, Any]],
) -> None:
    """A user abort flips the stream control and the runner emits run.aborted."""
    await committee_stream.register("run-uuid")

    # Override stages.run_analyst so it blocks long enough for the abort to fire.
    abort_signaled = asyncio.Event()

    async def slow_analyst(slug: str, **kw: Any) -> AnalystOutput:
        # The first analyst signals + blocks; the runner notices the abort via
        # check_control between stages.
        abort_signaled.set()
        await asyncio.sleep(0.1)
        return _analyst(slug)

    monkeypatch.setattr(graph_mod.stages, "run_analyst", slow_analyst)

    runner = asyncio.create_task(
        graph_mod.run_committee(
            run_id="run-uuid",
            symbol="NVDA",
            household_id=None,
        )
    )

    await abort_signaled.wait()
    committee_stream.abort("run-uuid")
    await runner

    types_in_order = [e.get("type") for e in captured_events if "type" in e]
    assert "run.aborted" in types_in_order

    # No kpi.tick should leak after run.aborted.
    aborted_idx = types_in_order.index("run.aborted")
    after_abort = types_in_order[aborted_idx + 1 :]
    assert "kpi.tick" not in after_abort, (
        "kpi.tick leaked past run.aborted — ticker not cancelled in finally"
    )
