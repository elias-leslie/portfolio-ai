"""Anti-sycophancy consensus-shift rule for feedback rounds.

When the user enters a new claim mid-run, the system asks every analyst
and risk voter to score the claim ∈ {weak, mistaken, partial, decisive}
and report whether their stance shifts. The PM only revises the
decision if a numerical threshold is crossed — agreement isn't
sufficient on its own.

Per plans/sunny-puzzling-sprout.md §Anti-sycophancy:

  shifted_analysts = sum(1 for a in analysts if a.revised_stance != a.prior_stance)
  risk_median_before = median(prior_risk_scores)
  risk_median_after  = median(new_risk_scores)
  should_revise = shifted_analysts >= 3 or abs(risk_median_after - risk_median_before) >= 0.2
"""

from __future__ import annotations

from statistics import median

from .schemas import FeedbackAgentResponse, RiskVoteOutput


def should_revise_decision(
    *,
    analyst_responses: list[FeedbackAgentResponse],
    prior_risk_votes: list[RiskVoteOutput],
    new_risk_votes: list[RiskVoteOutput],
) -> tuple[bool, dict[str, float | int]]:
    """Apply the consensus-shift rule. Returns (should_revise, telemetry).

    Telemetry is surfaced into the ``run.feedback.resolved`` event so
    the UI + tests can see exactly which side of the rule fired.
    """
    shifted = sum(
        1
        for response in analyst_responses
        if response.revised_stance != response.prior_stance
    )
    risk_before = median([v.score for v in prior_risk_votes]) if prior_risk_votes else 0.0
    risk_after = median([v.score for v in new_risk_votes]) if new_risk_votes else 0.0
    risk_delta = abs(risk_after - risk_before)
    should = shifted >= 3 or risk_delta >= 0.2
    return should, {
        "analysts_shifted": shifted,
        "risk_median_before": risk_before,
        "risk_median_after": risk_after,
        "risk_delta": risk_delta,
    }


def compose_rebuttal_md(analyst_responses: list[FeedbackAgentResponse]) -> str:
    """Compose the user-facing rebuttal markdown from agent concessions/pushback.

    Used when ``should_revise_decision`` returns False — the decision
    stays, but the user receives an explicit, evidence-cited
    counter-argument from each analyst.
    """
    if not analyst_responses:
        return ""
    lines = ["The committee considered your claim and did not revise its decision. Detailed reads:", ""]
    for response in analyst_responses:
        lines.append(
            f"- **{response.agent_slug}** ({response.score}): {response.rebuttal_or_concession.strip()}"
        )
    return "\n".join(lines)
