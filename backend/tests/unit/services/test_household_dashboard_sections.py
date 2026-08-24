"""Unit tests for household dashboard helper sections."""

from __future__ import annotations

from app.services._household_dashboard_sections import (
    budget_input_status,
    next_best_action,
)


def test_next_best_action_prefers_open_questions_before_setup_prompts() -> None:
    action = next_best_action(
        documents=[],
        visibility_score=10,
        questions=["Answer Jenny's salary question."],
        resolved_numeric_value=lambda _field: None,
    )

    assert action == "Answer Jenny's salary question."


def test_budget_input_status_reports_missing_inputs_without_documents() -> None:
    status = budget_input_status(
        resolved_numeric_value=lambda _field: None,
        documents=[],
    )

    assert status["budget_ready"] is False
    assert "Monthly income target" in status["missing_inputs"]
    assert "Recent financial evidence" in status["missing_inputs"]
