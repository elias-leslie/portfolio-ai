"""Unit tests for household dashboard helper sections."""

from __future__ import annotations

from app.services._household_dashboard_sections import (
    budget_input_status,
    compute_visibility_score,
    next_best_action,
)


def test_compute_visibility_score_counts_assets_targets_and_documents() -> None:
    values = {
        "monthly_net_income_target": 8000,
        "monthly_essential_target": 3500,
        "monthly_discretionary_target": 1200,
        "target_retirement_spend": 5000,
        "target_retirement_age": 60,
    }

    score = compute_visibility_score(
        account_count=2,
        position_count=4,
        cash_reserve=10000,
        retirement_assets=150000,
        taxable_assets=25000,
        resolved_numeric_value=values.get,
        document_count=3,
    )

    assert score == 100


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
