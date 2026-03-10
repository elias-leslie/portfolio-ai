"""Unit tests for new household dashboard action helpers."""

from __future__ import annotations

from types import SimpleNamespace

from app.models.household_finance import (
    BudgetReadiness,
    HouseholdOpportunity,
    HouseholdProfile,
    HouseholdQuestion,
)
from app.services.household_finance_service import HouseholdFinanceService


def test_build_budget_snapshot_uses_targets_and_actuals() -> None:
    service = object.__new__(HouseholdFinanceService)
    profile = HouseholdProfile(
        id="profile-1",
        household_name="Household",
        monthly_net_income_target=12500,
        monthly_essential_target=5200,
        monthly_discretionary_target=1800,
        monthly_savings_target=2600,
        target_retirement_age=None,
        target_retirement_spend=None,
        notes=None,
        created_at="2026-03-10T00:00:00Z",
        updated_at="2026-03-10T00:00:00Z",
    )
    reports = SimpleNamespace(
        executive=SimpleNamespace(
            average_monthly_spend=574.0,
            average_monthly_essentials=420.0,
            average_monthly_discretionary=154.0,
        )
    )

    snapshot = service._build_budget_snapshot(profile=profile, reports=reports)

    assert snapshot.monthly_plan_total == 9600
    assert snapshot.remaining_cash_after_plan == 2900
    assert snapshot.discretionary_headroom == 1646
    assert snapshot.status == "on_track"


def test_build_action_items_prioritizes_questions_and_budget_gaps() -> None:
    service = object.__new__(HouseholdFinanceService)
    questions = [
        HouseholdQuestion(
            id="question-1",
            field_name="monthly_net_income_target",
            status="open",
            priority="high",
            question="What is the monthly household take-home income?",
            rationale=None,
            recommendation=None,
            answer_text=None,
            source_document_id=None,
            metadata={},
            created_at="2026-03-10T00:00:00Z",
            answered_at=None,
        )
    ]
    opportunities = [
        HouseholdOpportunity(
            title="Tighten grocery baseline",
            category="budgeting",
            impact="high",
            detail="Recurring grocery merchants are visible now.",
            next_step="Confirm the monthly grocery cap.",
        )
    ]
    reports = SimpleNamespace(
        executive=SimpleNamespace(
            tracked_expense_count=10,
        )
    )
    budget_readiness = BudgetReadiness(
        status="setup_needed",
        summary="Budget needs one more input.",
        priorities=[],
        missing_inputs=["Confirm monthly take-home income."],
        starter_lanes=[],
    )

    items = service._build_action_items(
        questions=questions,
        opportunities=opportunities,
        next_best_action="Confirm monthly take-home income.",
        reports=reports,
        budget_readiness=budget_readiness,
    )

    assert items[0].title == "Answer Jenny follow-up"
    assert items[0].priority == "high"
    assert any(item.title == "Tighten grocery baseline" for item in items)
