"""Anti-sycophancy consensus-shift rule tests."""

from __future__ import annotations

import pytest

from app.agents.committee import graph as graph_mod
from app.agents.committee.feedback import (
    compose_rebuttal_md,
    should_revise_decision,
)
from app.agents.committee.schemas import (
    AnalystOutput,
    FeedbackAgentResponse,
    IpsCheck,
    IpsResult,
    PmDecision,
    RiskVoteOutput,
    TradeProposal,
)


def _analyst_response(
    *,
    slug: str,
    prior: str,
    revised: str,
    score: str = "weak",
    rebuttal: str = "no change",
) -> FeedbackAgentResponse:
    return FeedbackAgentResponse(
        agent_slug=slug,
        score=score,
        revised_stance=revised,
        rebuttal_or_concession=rebuttal,
        prior_stance=prior,
    )


def _risk_vote(slug: str, score: float) -> RiskVoteOutput:
    return RiskVoteOutput(
        agent_slug=slug,
        vote="downgrade",
        score=score,
        narrative_md="",
    )


def test_unanimous_weak_user_input_does_not_shift_decision() -> None:
    """Plan §Anti-sycophancy contract: weak user input must NOT revise."""
    analysts = [
        _analyst_response(slug=f"a{idx}", prior="bull", revised="bull", score="weak")
        for idx in range(4)
    ]
    prior_risk = [_risk_vote(f"r{i}", 0.2) for i in range(3)]
    new_risk = [_risk_vote(f"r{i}", 0.25) for i in range(3)]  # small move

    should, telemetry = should_revise_decision(
        analyst_responses=analysts,
        prior_risk_votes=prior_risk,
        new_risk_votes=new_risk,
    )
    assert should is False
    assert telemetry["analysts_shifted"] == 0
    assert telemetry["risk_delta"] < 0.2


def test_three_or_more_analysts_shifted_triggers_revise() -> None:
    """3+ stance flips meets the threshold even if risk median barely moves."""
    analysts = [
        _analyst_response(slug="a0", prior="bull", revised="bear", score="decisive"),
        _analyst_response(slug="a1", prior="bull", revised="bear", score="decisive"),
        _analyst_response(slug="a2", prior="bull", revised="bear", score="decisive"),
        _analyst_response(slug="a3", prior="bear", revised="bear", score="weak"),
    ]
    prior_risk = [_risk_vote(f"r{i}", 0.0) for i in range(3)]
    new_risk = [_risk_vote(f"r{i}", 0.05) for i in range(3)]

    should, telemetry = should_revise_decision(
        analyst_responses=analysts,
        prior_risk_votes=prior_risk,
        new_risk_votes=new_risk,
    )
    assert should is True
    assert telemetry["analysts_shifted"] == 3


def test_risk_median_swing_alone_triggers_revise() -> None:
    """Even without any analyst stance flip, a 0.2+ risk-median swing revises."""
    analysts = [
        _analyst_response(slug=f"a{i}", prior="bull", revised="bull")
        for i in range(4)
    ]
    prior_risk = [_risk_vote(f"r{i}", 0.5) for i in range(3)]
    new_risk = [_risk_vote(f"r{i}", 0.2) for i in range(3)]

    should, telemetry = should_revise_decision(
        analyst_responses=analysts,
        prior_risk_votes=prior_risk,
        new_risk_votes=new_risk,
    )
    assert should is True
    assert telemetry["risk_delta"] == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_process_feedback_claim_with_unanimous_weak_keeps_decision_and_emits_rebuttal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration: unanimous weak input must NOT shift decision AND must emit non-empty rebuttal_md.

    Mocks ``run_analyst_feedback`` and ``run_risk_feedback`` so the test
    runs offline (no Agent Hub I/O). Verifies the runner's
    ``_process_feedback_claim`` honors the consensus-shift rule and the
    composed rebuttal arrives via the emit callback.
    """
    analyst_outputs = [
        AnalystOutput(agent_slug=f"a{i}-v1", content_md="bull thesis", score=0.6, evidence=[])
        for i in range(4)
    ]
    risk_votes_prior = [
        RiskVoteOutput(agent_slug=f"r{i}", vote="approve", score=0.4, narrative_md="")
        for i in range(3)
    ]
    proposal = TradeProposal(
        action="buy",
        qty_pct=0.05,
        entry_price=100.0,
        horizon="3mo",
        rationale_md="reasoned buy",
    )
    decision = PmDecision(
        action="buy",
        qty_pct=0.05,
        confidence=0.7,
        horizon="3mo",
        rationale_md="initial decision",
        signers=["fundamentals-v1"],
    )
    ips_result = IpsResult(
        checks=[IpsCheck(name="concentration", passed=True, severity="info", detail="ok")],
        all_passed=True,
    )

    async def fake_analyst_feedback(slug: str, **kwargs):
        return FeedbackAgentResponse(
            agent_slug=slug,
            score="weak",
            revised_stance="bull",
            rebuttal_or_concession=f"{slug}: claim does not shift the read.",
            prior_stance="bull",
        )

    async def fake_risk_feedback(slug: str, *, prior_vote: RiskVoteOutput, **kwargs):
        return prior_vote.model_copy(update={"score": prior_vote.score + 0.01})

    monkeypatch.setattr(graph_mod.stages, "run_analyst_feedback", fake_analyst_feedback)
    monkeypatch.setattr(graph_mod.stages, "run_risk_feedback", fake_risk_feedback)

    emitted: list[dict] = []

    async def emit(type, *, stage_name=None, agent_slug=None, role=None,
                   content=None, score=None, tokens=None, latency_ms=None):
        emitted.append({"type": type, "stage": stage_name, "content": content or {}})
        return 1

    counters: dict[str, float] = {"tokens": 0.0, "cost_usd": 0.0}
    revised_decision = await graph_mod._process_feedback_claim(
        run_id="run-test",
        symbol="NVDA",
        household_id=None,
        context={},
        analyst_outputs=analyst_outputs,
        debate_summary=[],
        ips_result=ips_result,
        proposal=proposal,
        risk_votes_prior=risk_votes_prior,
        past_decisions=[],
        decision=decision,
        counters=counters,
        claim={"user_input": "What about the China tariff news?", "round": 1, "input_id": None},
        emit=emit,
    )

    assert revised_decision == decision, "decision must be unchanged when claim is unanimously weak"

    resolved = [e for e in emitted if e["type"] == "run.feedback.resolved"]
    assert len(resolved) == 1
    payload = resolved[0]["content"]
    assert payload["decision_shifted"] is False
    assert payload["rebuttal_md"], "rebuttal_md must be non-empty when decision does not shift"
    # Each analyst's rebuttal line should be present in the composed markdown.
    for output in analyst_outputs:
        assert output.agent_slug in payload["rebuttal_md"]

    # No new pm.decision event should have fired.
    assert not [e for e in emitted if e["type"] == "pm.decision"]


def test_compose_rebuttal_includes_per_agent_lines() -> None:
    """When the decision does NOT shift, the rebuttal renders each agent's pushback."""
    analysts = [
        _analyst_response(
            slug="fundamentals-v1",
            prior="bull",
            revised="bull",
            rebuttal="Tariff news is priced in by FY24 guidance.",
        ),
        _analyst_response(
            slug="technical-v1",
            prior="bull",
            revised="bull",
            rebuttal="200DMA support intact post-news.",
        ),
    ]
    markdown = compose_rebuttal_md(analysts)
    assert "fundamentals-v1" in markdown
    assert "technical-v1" in markdown
    assert "Tariff news is priced in by FY24 guidance." in markdown
    assert "200DMA support intact post-news." in markdown
