"""Anti-sycophancy consensus-shift rule tests."""

from __future__ import annotations

import pytest

from app.agents.committee.feedback import (
    compose_rebuttal_md,
    should_revise_decision,
)
from app.agents.committee.schemas import FeedbackAgentResponse, RiskVoteOutput


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
        score=score,  # type: ignore[arg-type]
        revised_stance=revised,  # type: ignore[arg-type]
        rebuttal_or_concession=rebuttal,
        prior_stance=prior,  # type: ignore[arg-type]
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
