"""Unit tests for new household dashboard action helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

from app.models.household_finance import (
    BudgetReadiness,
    HouseholdDocumentList,
    HouseholdExecutiveReport,
    HouseholdOpportunity,
    HouseholdProfile,
    HouseholdQuestion,
    HouseholdQuestionList,
    HouseholdReports,
    HouseholdResolvedValue,
)
from app.services.household_finance_service import HouseholdFinanceService


def test_build_budget_snapshot_uses_targets_and_actuals() -> None:
    service = object.__new__(HouseholdFinanceService)
    service._current_month_spend = lambda: 2800.0
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
    assert snapshot.month_to_date_spend == 2800.0
    assert snapshot.month_to_date_plan is not None
    assert snapshot.pace_status in {"on_track", "running_hot", "under_plan"}


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


def test_build_retirement_contribution_tracker_highlights_gap_to_target() -> None:
    service = object.__new__(HouseholdFinanceService)
    profile = HouseholdProfile(
        id="profile-1",
        household_name="Household",
        monthly_net_income_target=12000,
        monthly_essential_target=5200,
        monthly_discretionary_target=1800,
        monthly_savings_target=2500,
        target_retirement_age=60,
        target_retirement_spend=5500,
        notes=None,
        created_at="2026-03-10T00:00:00Z",
        updated_at="2026-03-10T00:00:00Z",
    )

    tracker = service._build_retirement_contribution_tracker(
        profile=profile,
        estimated_monthly_contributions=900,
    )

    assert tracker.monthly_target == 2500
    assert tracker.estimated_monthly_contributions == 900
    assert tracker.monthly_gap == 1600
    assert tracker.status == "gap"


def test_build_retirement_scenarios_uses_assets_and_target_spend() -> None:
    service = object.__new__(HouseholdFinanceService)

    scenarios = service._build_retirement_scenarios(
        retirement_assets=600000,
        target_retirement_spend=5000,
        baseline_monthly_spend=4300,
    )

    assert len(scenarios) == 3
    assert scenarios[0].name == "Base plan"
    assert scenarios[0].monthly_spend == 5000
    assert scenarios[0].funded_years == 10.0
    assert scenarios[1].monthly_spend > scenarios[0].monthly_spend


def test_get_dashboard_returns_composed_household_view() -> None:
    service = object.__new__(HouseholdFinanceService)
    profile = HouseholdProfile(
        id="profile-1",
        household_name="Household",
        monthly_net_income_target=12500,
        monthly_essential_target=5200,
        monthly_discretionary_target=1800,
        monthly_savings_target=2600,
        target_retirement_age=60,
        target_retirement_spend=5500,
        notes=None,
        created_at="2026-03-10T00:00:00Z",
        updated_at="2026-03-10T00:00:00Z",
    )
    question = HouseholdQuestion(
        id="question-1",
        field_name="monthly_net_income_target",
        status="open",
        priority="high",
        question="Confirm income?",
        rationale=None,
        recommendation=None,
        answer_text=None,
        source_document_id=None,
        metadata={},
        created_at="2026-03-10T00:00:00Z",
        answered_at=None,
    )
    resolved_value = HouseholdResolvedValue(
        field_name="monthly_net_income_target",
        label="Monthly take-home income",
        value="12500",
        confidence=1.0,
        status="confirmed",
        source="manual",
        rationale="Provided directly.",
        question=None,
    )
    reports = HouseholdReports(
        executive=HouseholdExecutiveReport(
            headline="Visible household cash flow",
            summary="Current spending is visible.",
            average_monthly_spend=3000.0,
            average_monthly_essentials=2000.0,
            average_monthly_discretionary=700.0,
            recent_30_day_spend=2500.0,
            recurring_merchant_count=2,
            tracked_expense_count=8,
            coverage_months=3,
        )
    )

    service.get_profile = Mock(return_value=profile)
    service.list_documents = Mock(return_value=HouseholdDocumentList(items=[]))
    service.list_questions = Mock(return_value=HouseholdQuestionList(items=[question]))
    service.get_resolved_values = Mock(return_value=[resolved_value])
    service.portfolio_mgr = Mock()
    service.portfolio_mgr.get_accounts.return_value = []
    service.portfolio_mgr.get_positions.return_value = []
    service._fetch_prices = Mock(return_value={})
    service._calculate_holdings_by_account = Mock(return_value={})
    service._compute_visibility_score = Mock(return_value=88)
    service._budget_input_status = Mock(
        return_value={
            "budget_ready": True,
            "priorities": ["Keep feeding statements."],
            "missing_inputs": [],
        }
    )
    service._visibility_label = Mock(return_value="High")
    service._next_best_action = Mock(return_value="Review the dashboard.")
    service._retirement_ready = Mock(return_value=True)
    service._retirement_strengths = Mock(return_value=["Visible retirement assets"])
    service._retirement_blockers = Mock(return_value=[])
    service._retirement_next_steps = Mock(return_value=["Keep saving"])
    service._build_opportunities = Mock(return_value=[])
    service.transaction_service = Mock()
    service.transaction_service.build_reports.return_value = reports
    service._build_budget_snapshot = Mock(
        return_value={
            "status": "on_track",
            "summary": "On plan.",
            "actual_monthly_spend": 3000.0,
            "actual_essential_monthly_spend": 2000.0,
            "actual_discretionary_monthly_spend": 700.0,
            "month_to_date_spend": 1200.0,
            "pace_detail": "Tracking well.",
        }
    )
    service._build_categorization_queue = Mock(return_value=[])
    service._build_recurring_commitments = Mock(return_value=[])
    service._build_sinking_funds = Mock(return_value=[])
    service._estimate_monthly_retirement_contributions = Mock(return_value=900.0)
    service._build_retirement_contribution_tracker = Mock(
        return_value={
            "status": "gap",
            "monthly_target": 2600.0,
            "estimated_monthly_contributions": 900.0,
            "monthly_gap": 1700.0,
            "detail": "Contributions trail the target.",
        }
    )
    service._build_retirement_scenarios = Mock(return_value=[])
    service._build_action_items = Mock(return_value=[])

    dashboard = service.get_dashboard()

    assert dashboard.profile.household_name == "Household"
    assert dashboard.overview.visibility_score == 88
    assert dashboard.budget_readiness.status == "ready_for_budgeting"
    assert dashboard.retirement_preparedness.status == "scenario_ready"
    assert dashboard.questions[0].id == "question-1"
    assert datetime.fromisoformat(dashboard.generated_at).tzinfo == UTC
