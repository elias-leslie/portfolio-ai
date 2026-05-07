"""Unit tests for extracted Jenny scoring helpers."""

from __future__ import annotations

import pytest

from app.models.jenny import JennyAgentEvaluation, JennyTradeReview
from app.services._jenny_scoring import (
    aggregate_symbol_review,
    build_scorecard,
    link_evaluations_to_reviews,
    summarize_scorecard,
)

FINAL_VERDICT_PRIORITY = {
    "exit": 5,
    "trim": 4,
    "review": 3,
    "buy": 2,
    "avoid": 1,
    "hold": 0,
}
POSITIVE_VERDICTS = {"buy", "hold"}


def _evaluation(
    *,
    evaluation_id: str,
    symbol: str,
    verdict: str,
    confidence: float | None,
    created_at: str,
    rationale: str,
) -> JennyAgentEvaluation:
    return JennyAgentEvaluation(
        id=evaluation_id,
        routine_id="routine-1",
        symbol=symbol,
        agent_name="persona",
        provider="served-provider",
        model="served-model",
        verdict=verdict,
        confidence=confidence,
        rationale=rationale,
        recommendation=None,
        strengths=[],
        weaknesses=[],
        thesis_id=None,
        agent_run_id=None,
        created_at=created_at,
        metadata={},
    )


def _review(
    *,
    review_id: str,
    symbol: str,
    return_pct: float | None,
    created_at: str,
    agent_verdicts: dict[str, str] | None = None,
) -> JennyTradeReview:
    return JennyTradeReview(
        id=review_id,
        symbol=symbol,
        thesis_id=None,
        idea_id=None,
        review_source="paper_trade",
        outcome_label="win" if (return_pct or 0) > 0 else "loss",
        return_pct=return_pct,
        lesson="lesson",
        what_worked=None,
        what_failed=None,
        next_time=None,
        created_at=created_at,
        updated_at=created_at,
        agent_consensus={"agent_verdicts": agent_verdicts or {}},
        metadata={},
    )


def test_link_evaluations_to_reviews_prefers_first_review_after_evaluation() -> None:
    evaluation = _evaluation(
        evaluation_id="eval-1",
        symbol="AAPL",
        verdict="buy",
        confidence=0.8,
        created_at="2026-03-07T12:00:00+00:00",
        rationale="Strong setup",
    )
    earlier_review = _review(
        review_id="review-early",
        symbol="AAPL",
        return_pct=-2.0,
        created_at="2026-03-07T11:00:00+00:00",
    )
    later_review = _review(
        review_id="review-late",
        symbol="AAPL",
        return_pct=5.0,
        created_at="2026-03-08T12:00:00+00:00",
    )

    linked = link_evaluations_to_reviews([evaluation], {"AAPL": [earlier_review, later_review]})

    assert linked == [(evaluation, later_review)]


def test_aggregate_symbol_review_builds_transient_evaluations_from_dicts() -> None:
    review = aggregate_symbol_review(
        symbol="NVDA",
        evaluations=[
            {
                "agent_name": "analyst",
                "verdict": "hold",
                "confidence": 0.6,
                "rationale": "Trend is fine.",
            },
            {
                "agent_name": "critic",
                "verdict": "review",
                "confidence": 0.7,
                "rationale": "Position is stretched.",
            },
        ],
        thesis=None,
        final_verdict_priority=FINAL_VERDICT_PRIORITY,
        now_iso="2026-03-10T00:00:00+00:00",
    )

    assert review.final_verdict == "review"
    assert review.average_confidence == pytest.approx(0.65)
    assert len(review.evaluations) == 2
    assert review.evaluations[0].routine_id == "transient"


def test_build_scorecard_uses_consensus_and_calibration_metrics() -> None:
    evaluations = [
        _evaluation(
            evaluation_id="eval-1",
            symbol="AAPL",
            verdict="buy",
            confidence=0.9,
            created_at="2026-03-07T12:00:00+00:00",
            rationale="Breakout setup",
        ),
        _evaluation(
            evaluation_id="eval-2",
            symbol="AAPL",
            verdict="trim",
            confidence=0.6,
            created_at="2026-03-07T12:05:00+00:00",
            rationale="Large position",
        ),
    ]
    reviews_by_symbol = {
        "AAPL": [
            _review(
                review_id="review-1",
                symbol="AAPL",
                return_pct=10.0,
                created_at="2026-03-08T12:00:00+00:00",
                agent_verdicts={"persona": "trim"},
            )
        ]
    }

    scorecard = build_scorecard(
        agent_name="persona",
        evaluations=evaluations,
        reviews_by_symbol=reviews_by_symbol,
        final_verdict_priority=FINAL_VERDICT_PRIORITY,
        positive_verdicts=POSITIVE_VERDICTS,
        now_iso="2026-03-10T00:00:00+00:00",
    )

    assert scorecard.completed_reviews == 1
    assert scorecard.win_rate == 1.0
    assert scorecard.agreement_rate == 0.5
    assert scorecard.exit_timing_score == 95.0
    assert scorecard.calibration_score == 75.0
    assert scorecard.last_evaluation_at == "2026-03-07T12:05:00+00:00"


def test_summarize_scorecard_returns_default_messages_without_history() -> None:
    strengths, weaknesses = summarize_scorecard(
        win_rate=None,
        avg_return=None,
        agreement_rate=None,
        calibration_score=None,
        entry_quality_score=None,
        risk_judgment_score=None,
        exit_timing_score=None,
        alert_discipline_score=None,
    )

    assert strengths == ["Jenny is still gathering enough history to judge this agent fairly."]
    assert weaknesses == ["No persistent weakness stands out from the current sample."]
