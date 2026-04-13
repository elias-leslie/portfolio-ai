"""Unit tests for household dashboard helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import Mock, patch

from app.models.household_finance import (
    HouseholdAccountSummary,
    HouseholdDocumentList,
    HouseholdExecutiveReport,
    HouseholdProfile,
    HouseholdQuestion,
    HouseholdQuestionList,
    HouseholdRecentTransaction,
    HouseholdReports,
    HouseholdResolvedValue,
)
from app.models.household_planning import empty_household_planning_snapshot
from app.services._household_dashboard_assembly import (
    _apply_account_freshness_visibility_cap,
    build_overview,
)
from app.services.household_finance_service import HouseholdFinanceService


def _service() -> HouseholdFinanceService:
    return HouseholdFinanceService()


def test_get_dashboard_returns_composed_household_view() -> None:
    service = _service()
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
        ),
        recent_transactions=[
            HouseholdRecentTransaction(
                date="2026-03-07",
                merchant="Amazon",
                description="Imported order",
                amount=29.95,
                category="Household shopping",
                essentiality="mixed",
            )
        ],
    )

    service.get_profile = cast(Any, Mock(return_value=profile))
    service.list_documents = cast(Any, Mock(return_value=HouseholdDocumentList(items=[])))
    service.list_questions = cast(Any, Mock(return_value=HouseholdQuestionList(items=[question])))
    service.get_resolved_values = cast(Any, Mock(return_value=[resolved_value]))
    mock_conn = Mock()
    mock_conn.execute.return_value.fetchall.return_value = []
    mock_conn.execute.return_value.fetchone.side_effect = [
        (0, None, None),
        (0, None, None),
        (None, 0, None),
    ]
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)
    service.storage = Mock()
    service.storage.connection.return_value = mock_conn
    service.portfolio_mgr = Mock()
    service.portfolio_mgr.get_accounts.return_value = []
    service.portfolio_mgr.get_positions.return_value = []
    service.transaction_service = Mock()
    service.transaction_service.build_reports.return_value = reports
    service.get_planning_snapshot = cast(
        Any, Mock(return_value=empty_household_planning_snapshot())
    )

    assembly_path = "app.services._household_dashboard_assembly"
    with (
        patch(f"{assembly_path}.compute_visibility_score", return_value=88),
        patch(f"{assembly_path}.visibility_label", return_value="High"),
        patch(f"{assembly_path}.next_best_action", return_value="Review the dashboard."),
        patch(f"{assembly_path}.budget_input_status", return_value={"budget_ready": True, "priorities": [], "missing_inputs": []}),
        patch(f"{assembly_path}.retirement_ready", return_value=True),
        patch(f"{assembly_path}.retirement_strengths", return_value=["Visible retirement assets"]),
        patch(f"{assembly_path}.retirement_blockers", return_value=[]),
        patch(f"{assembly_path}.retirement_next_steps", return_value=["Keep saving"]),
        patch(f"{assembly_path}.fetch_current_month_spend", return_value=1200.0),
        patch(f"{assembly_path}.fetch_monthly_retirement_contributions", return_value=900.0),
        patch(f"{assembly_path}.fetch_inferred_value_rows", return_value={}),
        patch(f"{assembly_path}.infer_profile_from_transactions"),
        patch("app.services.household_dashboard_composer.fetch_categorization_queue", return_value=[]),
        patch("app.services.household_dashboard_composer.fetch_recurring_commitments", return_value=[]),
    ):
        dashboard = service.get_dashboard()

    assert dashboard.profile.household_name == "Household"
    assert dashboard.overview.visibility_score == 88
    assert dashboard.overview.coverage_months == 3
    assert dashboard.overview.last_transaction_date == "2026-03-07"
    assert dashboard.overview.net_worth_status == "unavailable"
    assert dashboard.overview.monthly_spend_status == "unavailable"
    assert dashboard.budget_readiness.status == "ready_for_budgeting"
    assert dashboard.retirement_preparedness.status == "scenario_ready"
    assert dashboard.questions[0].id == "question-1"
    assert dashboard.overview.inbox_count >= 1
    assert dashboard.inbox[0].category in {"intake", "question"}
    assert dashboard.accounts == []
    assert isinstance(dashboard.jenny_needs, list)
    assert datetime.fromisoformat(dashboard.generated_at).tzinfo == UTC


def test_visibility_score_is_capped_when_account_freshness_is_degraded() -> None:
    accounts = [
        Mock(freshness_status="fresh"),
        Mock(freshness_status="stale"),
        Mock(freshness_status="needs_evidence"),
    ]

    assert _apply_account_freshness_visibility_cap(100, accounts) == 79
    assert _apply_account_freshness_visibility_cap(
        100,
        [Mock(freshness_status="fresh"), Mock(freshness_status="aging")],
    ) == 79
    assert _apply_account_freshness_visibility_cap(
        100,
        [
            Mock(freshness_status="fresh"),
            Mock(freshness_status="fresh"),
            Mock(freshness_status="stale"),
        ],
    ) == 99


def test_build_overview_prefers_account_summary_totals_over_legacy_portfolio_inputs() -> None:
    account_summaries = [
        HouseholdAccountSummary(
            id="rollover",
            label="Rollover IRA",
            asset_group="retirement",
            account_type="ira",
            source_type="retirement",
            current_value=8230.59,
            cash_balance=None,
            money_role="net_worth_only",
            last_balance_at="2026-03-09T00:00:00+00:00",
            balance_freshness_status="stale",
            balance_freshness_label="Stale",
            transaction_freshness_status="not_applicable",
            transaction_freshness_label="Not required",
            freshness_status="stale",
            freshness_label="Stale",
            match_status="tracked",
        ),
        HouseholdAccountSummary(
            id="529",
            label="529",
            asset_group="education",
            account_type="529",
            source_type="brokerage",
            current_value=3087.29,
            cash_balance=None,
            money_role="net_worth_only",
            last_balance_at="2026-03-12T00:00:00+00:00",
            balance_freshness_status="stale",
            balance_freshness_label="Stale",
            transaction_freshness_status="not_applicable",
            transaction_freshness_label="Not required",
            freshness_status="stale",
            freshness_label="Stale",
            match_status="tracked",
        ),
        HouseholdAccountSummary(
            id="cash",
            label="Cash Management",
            asset_group="taxable",
            account_type="brokerage",
            source_type="brokerage",
            current_value=39400.59,
            cash_balance=39400.59,
            money_role="spend_driver",
            last_balance_at="2026-04-13T00:00:00+00:00",
            balance_freshness_status="fresh",
            balance_freshness_label="Fresh",
            transaction_freshness_status="aging",
            transaction_freshness_label="Refresh soon",
            freshness_status="aging",
            freshness_label="Refresh soon",
            match_status="linked",
        ),
        HouseholdAccountSummary(
            id="tod",
            label="Individual - TOD",
            asset_group="taxable",
            account_type="brokerage",
            source_type="brokerage",
            current_value=507248.61,
            cash_balance=2917.07,
            money_role="net_worth_only",
            last_balance_at="2026-04-13T00:00:00+00:00",
            balance_freshness_status="fresh",
            balance_freshness_label="Fresh",
            transaction_freshness_status="not_applicable",
            transaction_freshness_label="Not required",
            freshness_status="fresh",
            freshness_label="Fresh",
            match_status="linked",
        ),
        HouseholdAccountSummary(
            id="trad",
            label="Traditional IRA",
            asset_group="retirement",
            account_type="ira",
            source_type="retirement",
            current_value=347053.83,
            cash_balance=1971.10,
            money_role="net_worth_only",
            last_balance_at="2026-04-13T00:00:00+00:00",
            balance_freshness_status="fresh",
            balance_freshness_label="Fresh",
            transaction_freshness_status="not_applicable",
            transaction_freshness_label="Not required",
            freshness_status="fresh",
            freshness_label="Fresh",
            match_status="linked",
        ),
        HouseholdAccountSummary(
            id="roth",
            label="ROTH IRA",
            asset_group="retirement",
            account_type="roth_ira",
            source_type="retirement",
            current_value=48014.15,
            cash_balance=48014.15,
            money_role="net_worth_only",
            last_balance_at="2026-04-13T00:00:00+00:00",
            balance_freshness_status="fresh",
            balance_freshness_label="Fresh",
            transaction_freshness_status="not_applicable",
            transaction_freshness_label="Not required",
            freshness_status="fresh",
            freshness_label="Fresh",
            match_status="linked",
        ),
        HouseholdAccountSummary(
            id="card",
            label="Chase Amazon card",
            asset_group="credit",
            account_type="credit_card",
            source_type="credit_card",
            current_value=2958.17,
            cash_balance=None,
            money_role="spend_driver",
            last_balance_at="2026-04-12T00:00:00+00:00",
            balance_freshness_status="fresh",
            balance_freshness_label="Fresh",
            transaction_freshness_status="fresh",
            transaction_freshness_label="Fresh",
            freshness_status="fresh",
            freshness_label="Fresh",
            match_status="tracked",
        ),
    ]
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
        ),
        recent_transactions=[],
    )

    overview, retirement_assets, taxable_assets, cash_reserve, total_tracked_assets = build_overview(
        accounts=[Mock(id="legacy", account_type="Taxable", cash_balance=999999.0)],
        live_positions=[],
        evidence_accounts=[],
        account_summaries=account_summaries,
        inbox=[],
        statement_freshness={"coverage_months": 3, "gap_months": [], "most_recent_date": "2026-04-10"},
        reports=reports,
        holdings_by_account={"legacy": 999999.0},
        documents=[],
        questions=[],
        resolved_values=[],
        service=None,
    )

    assert round(total_tracked_assets, 2) == 953035.06
    assert round(overview.liabilities_total, 2) == 2958.17
    assert round(overview.net_worth, 2) == 950076.89
    assert round(retirement_assets, 2) == 403298.57
    assert round(taxable_assets, 2) == 549736.49
    assert round(cash_reserve, 2) == 39400.59
