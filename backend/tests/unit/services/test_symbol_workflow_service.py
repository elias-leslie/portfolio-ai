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
