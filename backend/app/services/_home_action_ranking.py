"""Ranking helpers for the home action queue."""

from __future__ import annotations

PRIORITY_RANK = {
    "critical": 0,
    "high": 1,
    "warning": 2,
    "medium": 3,
    "low": 4,
}
PRIORITY_POINTS = {
    "critical": 3000.0,
    "high": 2000.0,
    "warning": 1000.0,
    "medium": 500.0,
    "low": 0.0,
}


def numeric_value(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def action_rank_score(
    priority: object,
    *,
    impact: float = 0.0,
    confidence: float = 0.0,
    freshness: float = 0.0,
    effort: float = 0.0,
) -> float:
    return (
        PRIORITY_POINTS.get(str(priority or "low"), PRIORITY_POINTS["low"])
        + impact
        + confidence
        + freshness
        - effort
    )


def internal_rank_score(action: dict[str, object]) -> float:
    score = action.get("_rank_score")
    if isinstance(score, (int, float)):
        return float(score)
    return action_rank_score(action.get("priority", "low"))


def public_action(action: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in action.items() if key != "_rank_score"}


def position_impact_score(portfolio_position: object | None) -> float:
    position = getattr(portfolio_position, "position", portfolio_position)
    if position is None:
        return 0.0

    weight_impact = abs(numeric_value(getattr(position, "weight_pct", None))) * 5
    gain_impact = min(abs(numeric_value(getattr(position, "gain_pct", None))), 100.0)
    return min(weight_impact + gain_impact, 500.0)


def household_rank_score(need: object) -> float:
    action_href = str(getattr(need, "action_href", "") or "")
    need_id = str(getattr(need, "id", "") or "")
    need_type = str(getattr(need, "need_type", "") or "")
    priority = getattr(need, "priority", "low")

    score = action_rank_score(priority)
    if "focus=account-coverage" in action_href:
        score = action_rank_score(priority, impact=260.0, freshness=140.0, effort=20.0)
    elif "focus=discovered-accounts" in action_href:
        score = action_rank_score(priority, impact=220.0, freshness=120.0, effort=30.0)
    elif "utility=evidence" in action_href:
        score = action_rank_score(priority, impact=180.0, freshness=160.0, effort=60.0)
    elif "utility=planning" in action_href:
        impact = 170.0 if "housing" in need_id else 130.0
        score = action_rank_score(priority, impact=impact, effort=80.0)
    elif getattr(need, "related_question_id", None):
        score = action_rank_score(priority, impact=120.0, freshness=80.0, effort=40.0)
    elif need_type == "confirm":
        score = action_rank_score(priority, impact=120.0, effort=40.0)
    return score
