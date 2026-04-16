"""Unit tests for shared symbol decision resolution."""

from __future__ import annotations

from app.api.symbols.decisions import build_symbol_decision
from app.api.symbols.models import PositionInfo
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


def test_build_symbol_decision_replaces_stored_position_facts_with_live_context() -> None:
    decision = build_symbol_decision(
        symbol="VTI",
        recommendation={
            "action": "CONSIDER_TRIMMING",
            "reasoning": ["Position is oversized."],
        },
        generated_at="2026-04-08T15:00:00+00:00",
        notifications=[
            JennyNotification(
                id="note-1",
                routine_id="routine-1",
                symbol="VTI",
                category="position_trim",
                severity="warning",
                status="open",
                title="VTI: Trim this position",
                detail="VTI is up 31.1% and now makes up 39.2% of the portfolio.",
                recommendation="Take partial profits so one winner does not become oversized.",
                created_at="2026-04-08T14:00:00+00:00",
            )
        ],
        portfolio_position=PositionInfo(
            shares=1488,
            cost_basis=198.4,
            current_value=499149.6,
            gain=203931.85,
            gain_pct=69.0784514142527,
            weight_pct=58.706470117146225,
            concentration_weight_pct=21.3,
            concentration_method="lookthrough",
            top_exposure_name="NVIDIA",
        ),
    )

    assert decision.reasoning == [
        "Current live position: VTI is up 69.1% from cost basis. Fund weight is 58.7% of invested assets, but largest look-through exposure is NVIDIA at 21.3%.",
        "Take partial profits so one winner does not become oversized.",
    ]


def test_build_symbol_decision_keeps_missing_live_position_facts_unknown() -> None:
    decision = build_symbol_decision(
        symbol="VTI",
        recommendation={"action": "HOLD_POSITION", "reasoning": ["Hold"]},
        generated_at="2026-04-08T15:00:00+00:00",
        notifications=[
            JennyNotification(
                id="note-1",
                routine_id="routine-1",
                symbol="VTI",
                category="position_review",
                severity="warning",
                status="open",
                title="VTI: Review this position",
                detail="VTI is up 31.1% and now makes up 39.2% of the portfolio.",
                recommendation="Wait for live position facts before sizing the next action.",
                created_at="2026-04-08T14:00:00+00:00",
            )
        ],
        portfolio_position=PositionInfo(
            shares=10,
            cost_basis=200,
            current_value=None,
            gain=None,
            gain_pct=None,
            weight_pct=None,
        ),
    )

    assert decision.reasoning == [
        "Current live position: VTI is held, but live price and invested weight are unavailable.",
        "Wait for live position facts before sizing the next action.",
    ]


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


def test_build_symbol_decision_ignores_stale_trim_alert_for_broad_etf() -> None:
    decision = build_symbol_decision(
        symbol="VTI",
        recommendation={
            "action": "HOLD_POSITION",
            "reasoning": [
                "Current gain: 56.2%",
                "Fund weight is 62.6% of invested assets, but largest look-through exposure is NVIDIA at 3.9%.",
            ],
        },
        generated_at="2026-04-08T15:00:00+00:00",
        notifications=[
            JennyNotification(
                id="note-1",
                routine_id="routine-1",
                symbol="VTI",
                category="position_trim",
                severity="warning",
                status="open",
                title="VTI: Trim this position",
                detail="VTI is up 31.1% and now makes up 39.2% of the portfolio.",
                recommendation="Take partial profits so one winner does not become oversized.",
                created_at="2026-04-08T14:00:00+00:00",
            )
        ],
        portfolio_position=PositionInfo(
            shares=2482.409,
            cost_basis=221.39,
            current_value=858615.62,
            gain=309016.06,
            gain_pct=56.2,
            weight_pct=62.6,
            concentration_weight_pct=3.9,
            concentration_method="lookthrough",
            top_exposure_name="NVIDIA",
        ),
    )

    assert decision.action == "HOLD_POSITION"
    assert decision.source_kind == "live_signal_model"
