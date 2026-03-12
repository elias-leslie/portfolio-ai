"""Dashboard composition helpers for household finance views."""

from __future__ import annotations

from typing import Any

from app.models.household_finance import (
    HouseholdBudgetSnapshot,
    HouseholdCategorizationCandidate,
    HouseholdFinanceDashboard,
    HouseholdRecurringCommitment,
    HouseholdRetirementContributionTracker,
    HouseholdRetirementScenario,
    HouseholdSinkingFund,
)
from app.services._household_dashboard_builders import (
    _assemble_finance_dashboard,
    _build_jenny_needs,
    _build_overview,
    _fields_with_confident_inferences,
    _gather_service_data,
    _update_overview_action,
    build_budget_snapshot,
    build_retirement_contribution_tracker,
    build_retirement_scenarios,
    build_sinking_funds,
)
from app.services._household_dashboard_queries import (
    check_statement_freshness,
    detect_unknown_accounts,
    fetch_categorization_queue,
    fetch_confirmed_facts,
    fetch_current_month_spend,
    fetch_monthly_retirement_contributions,
    fetch_recurring_commitments,
    infer_profile_from_transactions,
)


def _resolve_dashboard_values(
    service: Any,
    *,
    profile: Any,
    reports: Any,
    questions: list[Any],
) -> tuple[list[Any], list[Any]]:
    """Run transaction inferences and return (resolved_values, visible_questions)."""
    infer_profile_from_transactions(
        service.storage,
        profile=profile,
        reports=reports,
        existing_inferences=service._get_inferred_value_rows(),
    )
    resolved_values = service.get_resolved_values(profile=profile, questions=questions)
    non_inferable_fields = {"target_retirement_age", "target_retirement_spend"}
    inferred_fields = _fields_with_confident_inferences(resolved_values, threshold=0.7)
    visible_questions = [
        q for q in questions
        if q.field_name is None
        or q.field_name in non_inferable_fields
        or q.field_name not in inferred_fields
    ]
    return resolved_values, visible_questions


class HouseholdDashboardComposer:
    """Build the household dashboard from existing service dependencies."""

    def build_dashboard(self, service: Any) -> HouseholdFinanceDashboard:
        d = _gather_service_data(service)
        resolved_values, visible_questions = _resolve_dashboard_values(
            service, profile=d["profile"], reports=d["reports"], questions=d["questions"]
        )
        overview, retirement_assets, taxable_assets, cash_reserve, total_tracked_assets = (
            _build_overview(
                service=service, accounts=d["accounts"], live_positions=d["live_positions"],
                holdings_by_account=d["holdings_by_account"], documents=d["documents"],
                questions=visible_questions, resolved_values=resolved_values,
            )
        )
        categorization_queue = service._build_categorization_queue()
        recurring_commitments = service._build_recurring_commitments()
        jenny_needs = _build_jenny_needs(
            profile=d["profile"], planning=d["planning"], documents=d["documents"],
            questions=visible_questions, resolved_values=resolved_values, reports=d["reports"],
            confirmed_facts=fetch_confirmed_facts(service.storage),
            detected_accounts=detect_unknown_accounts(service.storage, d["documents"]),
            freshness=check_statement_freshness(service.storage),
            categorization_queue=categorization_queue,
        )
        if jenny_needs:
            overview = _update_overview_action(overview, jenny_needs[0].title)
        return _assemble_finance_dashboard(
            d=d, service=service, overview=overview, resolved_values=resolved_values,
            visible_questions=visible_questions, jenny_needs=jenny_needs,
            retirement_assets=retirement_assets, taxable_assets=taxable_assets,
            cash_reserve=cash_reserve, total_tracked_assets=total_tracked_assets,
            categorization_queue=categorization_queue, recurring_commitments=recurring_commitments,
        )

    def build_budget_snapshot(
        self,
        service: Any,
        *,
        profile: Any,
        reports: Any,
    ) -> HouseholdBudgetSnapshot:
        return build_budget_snapshot(
            profile=profile,
            reports=reports,
            month_to_date_spend=service._current_month_spend(),
        )

    def build_categorization_queue(
        self, service: Any, limit: int = 6
    ) -> list[HouseholdCategorizationCandidate]:
        return fetch_categorization_queue(service.storage, limit)

    def build_recurring_commitments(
        self, service: Any, limit: int = 6
    ) -> list[HouseholdRecurringCommitment]:
        return fetch_recurring_commitments(service.storage, service.transaction_service, limit)

    def build_sinking_funds(
        self, *, recurring_commitments: list[HouseholdRecurringCommitment]
    ) -> list[HouseholdSinkingFund]:
        return build_sinking_funds(recurring_commitments=recurring_commitments)

    def build_retirement_contribution_tracker(
        self,
        *,
        profile: Any,
        estimated_monthly_contributions: float,
    ) -> HouseholdRetirementContributionTracker:
        return build_retirement_contribution_tracker(
            profile=profile,
            estimated_monthly_contributions=estimated_monthly_contributions,
        )

    def build_retirement_scenarios(
        self,
        *,
        retirement_assets: float,
        target_retirement_spend: float | None,
        baseline_monthly_spend: float,
    ) -> list[HouseholdRetirementScenario]:
        return build_retirement_scenarios(
            retirement_assets=retirement_assets,
            target_retirement_spend=target_retirement_spend,
            baseline_monthly_spend=baseline_monthly_spend,
        )

    def estimate_monthly_retirement_contributions(self, service: Any) -> float:
        return fetch_monthly_retirement_contributions(service.storage)

    def current_month_spend(self, service: Any) -> float:
        return fetch_current_month_spend(service.storage)
