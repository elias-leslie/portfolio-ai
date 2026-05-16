"""Dashboard composition helpers for household finance views."""

from __future__ import annotations

from typing import Any

from app.models.household_finance import (
    HouseholdBudgetSnapshot,
    HouseholdCategorizationCandidate,
    HouseholdDiscoveredAccount,
    HouseholdFinanceDashboard,
    HouseholdRecurringCommitment,
    HouseholdRetirementContributionTracker,
    HouseholdRetirementScenario,
    HouseholdSinkingFund,
)
from app.services._household_account_summary import (
    build_account_summaries,
    build_money_inbox,
)
from app.services._household_dashboard_assembly import (
    assemble_finance_dashboard,
    build_jenny_needs,
    build_overview,
    gather_service_data,
    resolve_dashboard_values,
    update_overview_action,
)
from app.services._household_dashboard_builders import (
    build_budget_snapshot,
    build_retirement_contribution_tracker,
    build_retirement_scenarios,
    build_sinking_funds,
)
from app.services._household_dashboard_date_issues import (
    fetch_transaction_date_issues,
)
from app.services._household_dashboard_queries import (
    check_statement_freshness,
    fetch_categorization_queue,
    fetch_confirmed_facts,
    fetch_current_month_spend,
    fetch_latest_transaction_dates_by_account_label,
    fetch_latest_transaction_dates_by_document,
    fetch_latest_transaction_dates_by_household_account,
    fetch_monthly_retirement_contributions,
    fetch_recurring_commitments,
)
from app.services._household_dashboard_unknown_accounts import (
    detect_unknown_accounts,
)


class HouseholdDashboardComposer:
    """Build the household dashboard from existing service dependencies."""

    def build_dashboard(self, service: Any) -> HouseholdFinanceDashboard:
        d = gather_service_data(service)
        freshness = check_statement_freshness(service.storage)
        transaction_date_issues = fetch_transaction_date_issues(service.storage)
        resolved_values, visible_questions = resolve_dashboard_values(
            service, profile=d["profile"], reports=d["reports"], questions=d["questions"]
        )
        latest_transaction_dates_by_document = fetch_latest_transaction_dates_by_document(
            service.storage
        )
        latest_transaction_dates_by_account_label = (
            fetch_latest_transaction_dates_by_account_label(service.storage)
        )
        latest_transaction_dates_by_household_account = (
            fetch_latest_transaction_dates_by_household_account(service.storage)
        )
        discovered_accounts = [
            HouseholdDiscoveredAccount.model_validate(item)
            for item in detect_unknown_accounts(service.storage, d["documents"])
        ]
        account_summaries = build_account_summaries(
            evidence_accounts=d["evidence_accounts"],
            documents=d["documents"],
            portfolio_accounts=d["accounts"],
            tracked_accounts=d["tracked_accounts"],
            account_valuations=d["account_valuations"],
            source_owned_household_account_ids=d["source_owned_household_account_ids"],
            source_owned_account_values=d["source_owned_account_values"],
            holdings_by_account=d["holdings_by_account"],
            statement_freshness=freshness,
            latest_transaction_dates_by_document=latest_transaction_dates_by_document,
            latest_transaction_dates_by_account_label=latest_transaction_dates_by_account_label,
            latest_transaction_dates_by_household_account=latest_transaction_dates_by_household_account,
        )
        inbox = build_money_inbox(
            accounts=account_summaries,
            discovered_accounts=discovered_accounts,
            questions=visible_questions,
            tracked_documents=len(d["documents"]),
            parsed_documents=sum(1 for document in d["documents"] if document.status in {"parsed", "needs_review"}),
            statement_freshness=freshness,
        )
        overview, retirement_assets, taxable_assets, cash_reserve, total_tracked_assets = build_overview(
            accounts=d["accounts"], live_positions=d["live_positions"],
            evidence_accounts=d["evidence_accounts"], account_summaries=account_summaries,
            inbox=inbox, statement_freshness=freshness,
            reports=d["reports"],
            holdings_by_account=d["holdings_by_account"], documents=d["documents"],
            questions=visible_questions, resolved_values=resolved_values,
            service=service,
        )
        categorization_queue = fetch_categorization_queue(service.storage, 6)
        recurring_commitments = fetch_recurring_commitments(service.storage, service.transaction_service, 6)
        jenny_needs = build_jenny_needs(
            profile=d["profile"], planning=d["planning"], documents=d["documents"],
            questions=visible_questions, resolved_values=resolved_values, reports=d["reports"],
            confirmed_facts=fetch_confirmed_facts(service.storage),
            detected_accounts=[account.model_dump() for account in discovered_accounts],
            freshness=freshness,
            categorization_queue=categorization_queue,
        )
        if inbox:
            overview = update_overview_action(overview, inbox[0].title)
        elif jenny_needs:
            overview = update_overview_action(overview, jenny_needs[0].title)
        return assemble_finance_dashboard(
            d=d, service=service, overview=overview, resolved_values=resolved_values,
            visible_questions=visible_questions, jenny_needs=jenny_needs,
            retirement_assets=retirement_assets, taxable_assets=taxable_assets,
            cash_reserve=cash_reserve, total_tracked_assets=total_tracked_assets,
            categorization_queue=categorization_queue, recurring_commitments=recurring_commitments,
            transaction_date_issues=transaction_date_issues,
            account_summaries=account_summaries, discovered_accounts=discovered_accounts, inbox=inbox,
        )

    def build_budget_snapshot(self, service: Any, *, profile: Any, reports: Any) -> HouseholdBudgetSnapshot:
        return build_budget_snapshot(profile=profile, reports=reports, month_to_date_spend=fetch_current_month_spend(service.storage))

    def build_categorization_queue(self, service: Any, limit: int = 6) -> list[HouseholdCategorizationCandidate]:
        return fetch_categorization_queue(service.storage, limit)

    def build_recurring_commitments(self, service: Any, limit: int = 6) -> list[HouseholdRecurringCommitment]:
        return fetch_recurring_commitments(service.storage, service.transaction_service, limit)

    def build_sinking_funds(self, *, recurring_commitments: list[HouseholdRecurringCommitment]) -> list[HouseholdSinkingFund]:
        return build_sinking_funds(recurring_commitments=recurring_commitments)

    def build_retirement_contribution_tracker(self, *, profile: Any, estimated_monthly_contributions: float) -> HouseholdRetirementContributionTracker:
        return build_retirement_contribution_tracker(profile=profile, estimated_monthly_contributions=estimated_monthly_contributions)

    def build_retirement_scenarios(self, *, retirement_assets: float, target_retirement_spend: float | None, baseline_monthly_spend: float) -> list[HouseholdRetirementScenario]:
        return build_retirement_scenarios(retirement_assets=retirement_assets, target_retirement_spend=target_retirement_spend, baseline_monthly_spend=baseline_monthly_spend)

    def estimate_monthly_retirement_contributions(self, service: Any) -> float:
        return fetch_monthly_retirement_contributions(service.storage)

    def current_month_spend(self, service: Any) -> float:
        return fetch_current_month_spend(service.storage)
