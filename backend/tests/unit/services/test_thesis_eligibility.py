"""Unit tests for thesis decision eligibility."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.thesis import (
    Thesis,
    ThesisAction,
    ThesisDecisionEligibility,
    ThesisReason,
    ThesisStatus,
    ThesisValidation,
)
from app.services.thesis.thesis_eligibility import (
    evaluate_thesis_decision_eligibility,
    unavailable_thesis_eligibility,
)

NOW = datetime(2026, 4, 24, 18, 0, tzinfo=UTC)


def _thesis(
    *,
    hours_old: float = 2,
    current_price: float = 263.15,
    fear_greed: int = 45,
    vix: float = 19.3,
    issues: list[str] | None = None,
    approved: bool = True,
) -> Thesis:
    timestamp = (NOW - timedelta(hours=hours_old)).isoformat()
    return Thesis(
        id="thesis-1",
        symbol="AMZN",
        version=1,
        status=ThesisStatus.ACTIVE,
        action=ThesisAction.HOLD,
        core_reasons=[
            ThesisReason(
                reason=(
                    f"Current price of ${current_price:.2f}; "
                    f"Fear & Greed at {fear_greed}; VIX at {vix:.1f}."
                ),
                confidence=0.8,
            )
        ],
        claude_validation=ThesisValidation(
            provider="risk-manager",
            approved=approved,
            confidence=0.8,
            review_summary="Review",
            issues=issues or [],
        ),
        cross_validation_score=0.8,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _intelligence(
    *,
    price: float = 263.15,
    fear_greed: int = 45,
    vix: float = 19.3,
) -> dict:
    return {
        "scores": {
            "pillars": {"price": {"metadata": {"price": price}}},
        },
        "market": {
            "fear_greed_score": fear_greed,
            "vix": vix,
        },
    }


def test_evaluate_thesis_decision_eligibility_allows_fresh_current_thesis() -> None:
    eligibility = evaluate_thesis_decision_eligibility(
        _thesis(),
        _intelligence(),
        now=NOW,
    )

    assert eligibility == ThesisDecisionEligibility(
        eligible=True,
        status="eligible",
        reasons=[],
        age_hours=2.0,
        evaluated_at=NOW.isoformat(),
    )


def test_evaluate_thesis_decision_eligibility_blocks_stale_age() -> None:
    eligibility = evaluate_thesis_decision_eligibility(
        _thesis(hours_old=25),
        _intelligence(),
        now=NOW,
    )

    assert eligibility.eligible is False
    assert eligibility.status == "review_required"
    assert "refresh required" in eligibility.reasons[0]


def test_evaluate_thesis_decision_eligibility_blocks_material_validation_issue() -> None:
    eligibility = evaluate_thesis_decision_eligibility(
        _thesis(
            issues=[
                "FACTUAL ERROR: position weight was read as 0.025% when it was 2.5%."
            ]
        ),
        _intelligence(),
        now=NOW,
    )

    assert eligibility.eligible is False
    assert any("material issue" in reason for reason in eligibility.reasons)


def test_evaluate_thesis_decision_eligibility_blocks_price_drift() -> None:
    eligibility = evaluate_thesis_decision_eligibility(
        _thesis(current_price=213.49),
        _intelligence(price=263.15),
        now=NOW,
    )

    assert eligibility.eligible is False
    assert any("Price assumption drifted" in reason for reason in eligibility.reasons)


def test_evaluate_thesis_decision_eligibility_blocks_regime_drift() -> None:
    eligibility = evaluate_thesis_decision_eligibility(
        _thesis(fear_greed=11, vix=29.5),
        _intelligence(fear_greed=45, vix=19.3),
        now=NOW,
    )

    assert eligibility.eligible is False
    assert any("Fear & Greed drifted" in reason for reason in eligibility.reasons)
    assert any("VIX drifted" in reason for reason in eligibility.reasons)


def test_unavailable_thesis_eligibility_blocks_current_decision_evidence() -> None:
    eligibility = unavailable_thesis_eligibility(now=NOW)

    assert eligibility.eligible is False
    assert eligibility.status == "unavailable"
    assert eligibility.reasons == ["No thesis is available for this symbol."]
