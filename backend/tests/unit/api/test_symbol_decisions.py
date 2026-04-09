"""Unit tests for shared symbol decision resolution."""

from __future__ import annotations

from app.api.symbols.decisions import build_symbol_decision
from app.models.jenny import JennyAgentEvaluation, JennyNotification, JennySymbolReview


def test_build_symbol_decision_prefers_active_jenny_alert() -> None:
    decision = build_symbol_decision(
        symbol="NVDA",
        recommendation={
            "action": "BUY_MORE",
            "reasoning": ["Strong BUY signal (7/10)"],
        },
        generated_at="2026-04-08T15:00:00+00:00",
        notifications=[
            JennyNotification(
                id="note-1",
                routine_id="routine-1",
                symbol="NVDA",
                category="position_exit",
                severity="critical",
                status="open",
                title="NVDA: Exit this position",
                detail="The thesis broke.",
                recommendation="Reduce risk now.",
                created_at="2026-04-08T14:00:00+00:00",
            )
        ],
    )

    assert decision.action == "position_exit"
    assert decision.headline == "Exit this position"
    assert decision.summary == "Reduce risk now."
    assert decision.reasoning == ["The thesis broke.", "Reduce risk now."]
    assert decision.source_kind == "jenny_alert"
    assert decision.source_label == "Jenny alert"
    assert decision.severity == "critical"
    assert decision.source_timestamp == "2026-04-08T14:00:00+00:00"


def test_build_symbol_decision_uses_recent_review_before_live_model() -> None:
    decision = build_symbol_decision(
        symbol="NVDA",
        recommendation={
            "action": "BUY_MORE",
            "reasoning": ["Strong BUY signal (7/10)"],
        },
        generated_at="2026-04-08T15:00:00+00:00",
        latest_review=JennySymbolReview(
            symbol="NVDA",
            final_verdict="review",
            management_action="trim",
            management_detail="Position is oversized after the run.",
            reasons=["Risk has outrun upside."],
            evaluations=[
                JennyAgentEvaluation(
                    id="eval-1",
                    routine_id="routine-1",
                    symbol="NVDA",
                    agent_name="risk-manager",
                    verdict="review",
                    confidence=0.7,
                    rationale="Position is stretched.",
                    created_at="2026-04-08T13:30:00+00:00",
                )
            ],
        ),
    )

    assert decision.action == "trim"
    assert decision.headline == "Trim"
    assert decision.summary == "Position is oversized after the run."
    assert decision.reasoning == [
        "Position is oversized after the run.",
        "Risk has outrun upside.",
    ]
    assert decision.source_kind == "jenny_review"
    assert decision.source_label == "Jenny review"
    assert decision.source_timestamp == "2026-04-08T13:30:00+00:00"


def test_build_symbol_decision_falls_back_to_live_model() -> None:
    decision = build_symbol_decision(
        symbol="NVDA",
        recommendation={
            "action": "BUY_MORE",
            "reasoning": ["Strong BUY signal (7/10)", "Market in Fear (28)"],
        },
        generated_at="2026-04-08T15:00:00+00:00",
    )

    assert decision.action == "BUY_MORE"
    assert decision.headline == "Buy more"
    assert decision.summary == "Strong BUY signal (7/10)"
    assert decision.reasoning == ["Strong BUY signal (7/10)", "Market in Fear (28)"]
    assert decision.source_kind == "live_signal_model"
    assert decision.source_label == "Live signal model"
    assert decision.source_timestamp == "2026-04-08T15:00:00+00:00"
