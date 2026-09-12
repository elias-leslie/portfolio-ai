"""Unit tests for persisted symbol workflow logic."""

from __future__ import annotations

from app.services.symbol_workflow_service import (
    SymbolWorkflowService,
    available_transitions_for_stage,
    derive_default_stage,
    stage_for_outcome_action,
)


def test_derive_default_stage_prefers_live_position_over_other_signals() -> None:
    stage = derive_default_stage(
        has_watchlist_item=True,
        has_thesis=True,
        has_live_position=True,
        has_trade_review=False,
    )

    assert stage == "live"


def test_derive_default_stage_uses_review_due_when_outcome_history_exists() -> None:
    stage = derive_default_stage(
        has_watchlist_item=True,
        has_thesis=True,
        has_live_position=False,
        has_trade_review=True,
    )

    assert stage == "review_due"


def test_available_transitions_expose_closure_actions_for_live_positions() -> None:
    transitions = available_transitions_for_stage("live")

    assert "review_due" in transitions
    assert "exited" in transitions
    assert "invalidated" in transitions


def test_normalize_transition_note_trims_and_defaults_empty_notes() -> None:
    service = SymbolWorkflowService()

    assert service._normalize_transition_note("  Thesis confirmed after review.  ") == (
        "Thesis confirmed after review."
    )
    assert service._normalize_transition_note("   ") == "Workflow updated from product UI."


def test_stage_for_outcome_action_maps_live_decisions_into_workflow() -> None:
    assert stage_for_outcome_action("hold") == "live"
    assert stage_for_outcome_action("trim") == "review_due"
    assert stage_for_outcome_action("exit") == "exited"


def test_record_decision_requires_rationale_and_actual_position(mocker):
    import pytest

    service = SymbolWorkflowService()
    mocker.patch.object(
        service,
        "get_workflow",
        return_value={
            "stage": "discover",
            "position": None,
            "available_actions": ["watch", "pass"],
        },
    )
    persist = mocker.patch.object(service._store, "persist_transition")
    side_effect = mocker.patch.object(service, "_apply_stage_side_effect")
    capture = mocker.patch.object(
        service,
        "_capture_evidence",
        return_value={
            "version": 1,
            "portfolio": {"held": False},
            "quote": {"price": 123},
            "decision": {"source_kind": "live_signal_model"},
        },
    )
    for action, note in (
        ("hold", "A reason exists."),
        ("trim", "A reason exists."),
        ("watch", "   "),
    ):
        with pytest.raises(ValueError):
            service.record_outcome("AAPL", action, note)
    persist.assert_not_called()
    capture.assert_not_called()
    service.record_outcome(
        "AAPL",
        "pass",
        "Waiting for updated earnings.",
        jenny_verdict="fabricated client attribution",
    )
    saved = persist.call_args.kwargs
    assert saved["stage"] == "passed"
    assert saved["metadata"]["evidence_snapshot"]["quote"]["price"] == 123
    assert "jenny" not in saved["metadata"]
    side_effect.assert_called_once_with("AAPL", "passed", "Waiting for updated earnings.")
    capture.return_value = {"portfolio": {"held": True}}
    with pytest.raises(ValueError, match="changed"):
        service.record_outcome("AAPL", "watch", "Waiting for updated earnings.")
    assert persist.call_count == 1


def test_transition_cannot_bypass_position_guard_and_needs_note(mocker):
    import pytest

    service = SymbolWorkflowService()
    mocker.patch.object(
        service,
        "get_workflow",
        return_value={"stage": "discover", "available_transitions": ["tracked", "thesis_ready"]},
    )
    persist = mocker.patch.object(service._store, "persist_transition")
    for stage, note in (("live", "I cannot invent shares."), ("tracked", "")):
        with pytest.raises(ValueError):
            service.transition("AAPL", stage, note)
    persist.assert_not_called()
