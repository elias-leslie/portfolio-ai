"""Dashboard composition helpers for household finance views."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import (
    BudgetReadiness,
    HouseholdActionItem,
    HouseholdBudgetSnapshot,
    HouseholdCategorizationCandidate,
    HouseholdFinanceDashboard,
    HouseholdOverview,
    HouseholdRecurringCommitment,
    HouseholdRetirementContributionTracker,
    HouseholdRetirementScenario,
    HouseholdSinkingFund,
    ImportCenter,
    ImportFormat,
    JennyMoneyBrief,
    RetirementPreparedness,
)
from app.services._household_dashboard_builders import (
    build_action_items,
    build_budget_snapshot,
    build_retirement_contribution_tracker,
    build_retirement_scenarios,
    build_sinking_funds,
    build_starter_lanes,
)
from app.services._household_dashboard_queries import (
    fetch_categorization_queue,
    fetch_current_month_spend,
    fetch_monthly_retirement_contributions,
    fetch_recurring_commitments,
)

_IMPORT_CENTER = ImportCenter(
    headline="Use statements for coverage, then receipts and invoices for savings intelligence.",
    tracked_documents=0,
    parsed_documents=0,
    suggested_first_uploads=[
        "Checking statements for the last 3 months",
        "Primary household credit-card statements for the last 3 months",
        "Most recent brokerage and retirement statements",
        "Utility, insurance, and mortgage or rent invoices",
    ],
    automations=[
        "Normalize merchants across accounts into one spend ledger.",
        "Detect recurring charges, annual renewals, and price creep.",
        "Reconcile brokerage cash flows, dividends, and fees against account balances.",
    ],
    supported_documents=[
        ImportFormat(
            label="Bank and credit statements",
            formats=["PDF", "CSV", "OFX", "QFX"],
            extracts=["transactions", "merchant names", "statement totals", "fees"],
        ),
        ImportFormat(
            label="Brokerage and retirement statements",
            formats=["PDF", "CSV"],
            extracts=["holdings", "cash flows", "dividends", "contributions", "fees"],
        ),
        ImportFormat(
            label="Receipts and invoices",
            formats=["PDF", "PNG", "JPG", "HEIC"],
            extracts=["merchant", "date", "line items", "subtotal", "tax", "total"],
        ),
    ],
)

_JENNY_BRIEF = JennyMoneyBrief(
    headline="Jenny can now see actual merchant flows, not just document summaries.",
    body=(
        "The household profile, documents, investment accounts, and transaction ledger now share one surface. "
        "That lets Jenny move from document review into real cash-flow analysis, merchant normalization, and budget coaching."
    ),
    prompts=[
        "Show me the executive household cash-flow report.",
        "Which merchants are driving our essentials spend?",
        "Where is our money leaking month to month?",
    ],
)


def _build_import_center(documents: list[Any]) -> ImportCenter:
    parsed_count = sum(1 for d in documents if d.status in {"parsed", "needs_review"})
    return ImportCenter(
        headline=_IMPORT_CENTER.headline,
        tracked_documents=len(documents),
        parsed_documents=parsed_count,
        suggested_first_uploads=_IMPORT_CENTER.suggested_first_uploads,
        automations=_IMPORT_CENTER.automations,
        supported_documents=_IMPORT_CENTER.supported_documents,
    )


def _build_overview(
    *,
    service: Any,
    accounts: list[Any],
    live_positions: list[Any],
    holdings_by_account: dict[str, float],
    documents: list[Any],
    questions: list[Any],
    resolved_values: list[Any],
) -> tuple[HouseholdOverview, float, float, float, float]:
    invested_assets = sum(holdings_by_account.values())
    cash_reserve = sum(account.cash_balance for account in accounts)
    retirement_assets = 0.0
    taxable_assets = 0.0
    for account in accounts:
        account_total = account.cash_balance + holdings_by_account.get(account.id, 0.0)
        if account.account_type in service.RETIREMENT_ACCOUNT_TYPES:
            retirement_assets += account_total
        if account.account_type in service.TAXABLE_ACCOUNT_TYPES:
            taxable_assets += account_total
    total_tracked_assets = invested_assets + cash_reserve
    visibility_score = service._compute_visibility_score(
        account_count=len(accounts),
        position_count=len(live_positions),
        cash_reserve=cash_reserve,
        retirement_assets=retirement_assets,
        taxable_assets=taxable_assets,
        resolved_values=resolved_values,
        document_count=len(documents),
    )
    return (
        HouseholdOverview(
            invested_assets=invested_assets,
            retirement_assets=retirement_assets,
            taxable_assets=taxable_assets,
            cash_reserve=cash_reserve,
            total_tracked_assets=total_tracked_assets,
            visibility_score=visibility_score,
            visibility_label=service._visibility_label(visibility_score),
            next_best_action=service._next_best_action(
                documents,
                visibility_score,
                questions=questions,
                resolved_values=resolved_values,
            ),
        ),
        retirement_assets,
        taxable_assets,
        cash_reserve,
        total_tracked_assets,
    )


def _build_budget_readiness(*, service: Any, resolved_values: list[Any], documents: list[Any]) -> BudgetReadiness:
    budget_inputs = service._budget_input_status(resolved_values, documents)
    resolved_numeric_value = lambda field: service._resolved_numeric_value(resolved_values, field)  # noqa: E731
    return BudgetReadiness(
        status="ready_for_budgeting" if budget_inputs["budget_ready"] else "setup_needed",
        summary=(
            "Jenny can enforce budget guardrails once household income targets and transaction documents are in place."
            if budget_inputs["budget_ready"]
            else "Budgeting is one step away: define the monthly plan and keep feeding the system statements."
        ),
        priorities=budget_inputs["priorities"],
        missing_inputs=budget_inputs["missing_inputs"],
        starter_lanes=build_starter_lanes(resolved_numeric_value),
    )


def _build_retirement_preparedness(
    *,
    service: Any,
    resolved_values: list[Any],
    documents: list[Any],
    retirement_assets: float,
    taxable_assets: float,
    cash_reserve: float,
    total_tracked_assets: float,
) -> RetirementPreparedness:
    retirement_share = (retirement_assets / total_tracked_assets) * 100 if total_tracked_assets > 0 else 0.0
    return RetirementPreparedness(
        status="scenario_ready" if service._retirement_ready(resolved_values, documents) else "baseline_visible",
        summary=(
            "Retirement planning can move from rough intuition to defensible scenario planning."
            if service._retirement_ready(resolved_values, documents)
            else "Retirement assets are visible, but retirement readiness still depends on real spending and future-income assumptions."
        ),
        retirement_account_share=retirement_share,
        strengths=service._retirement_strengths(retirement_assets, taxable_assets, cash_reserve, resolved_values),
        blockers=service._retirement_blockers(resolved_values, documents),
        next_steps=service._retirement_next_steps(resolved_values, documents),
    )


class HouseholdDashboardComposer:
    """Build the household dashboard from existing service dependencies."""

    def build_dashboard(self, service: Any) -> HouseholdFinanceDashboard:
        profile = service.get_profile()
        documents = service.list_documents(limit=12).items
        questions = service.list_questions(limit=12).items
        resolved_values = service.get_resolved_values(profile=profile, questions=questions)
        accounts = [a for a in service.portfolio_mgr.get_accounts() if a.account_type != "paper"]
        positions = service.portfolio_mgr.get_positions()
        account_ids = {a.id for a in accounts}
        live_positions = [p for p in positions if p.account_id in account_ids]
        price_data = service._fetch_prices(live_positions)
        holdings_by_account = service._calculate_holdings_by_account(live_positions, price_data)

        overview, retirement_assets, taxable_assets, cash_reserve, total_tracked_assets = _build_overview(
            service=service,
            accounts=accounts,
            live_positions=live_positions,
            holdings_by_account=holdings_by_account,
            documents=documents,
            questions=questions,
            resolved_values=resolved_values,
        )
        budget_readiness = _build_budget_readiness(
            service=service, resolved_values=resolved_values, documents=documents
        )
        retirement_preparedness = _build_retirement_preparedness(
            service=service,
            resolved_values=resolved_values,
            documents=documents,
            retirement_assets=retirement_assets,
            taxable_assets=taxable_assets,
            cash_reserve=cash_reserve,
            total_tracked_assets=total_tracked_assets,
        )
        opportunities = service._build_opportunities(
            resolved_values=resolved_values,
            documents=documents,
            taxable_assets=taxable_assets,
            retirement_assets=retirement_assets,
        )
        reports = service.transaction_service.build_reports()
        budget_snapshot = service._build_budget_snapshot(profile=profile, reports=reports)
        categorization_queue = service._build_categorization_queue()
        recurring_commitments = service._build_recurring_commitments()
        sinking_funds = service._build_sinking_funds(recurring_commitments=recurring_commitments)
        retirement_contribution_tracker = service._build_retirement_contribution_tracker(
            profile=profile,
            estimated_monthly_contributions=service._estimate_monthly_retirement_contributions(),
        )
        retirement_scenarios = service._build_retirement_scenarios(
            retirement_assets=retirement_assets,
            target_retirement_spend=profile.target_retirement_spend,
            baseline_monthly_spend=reports.executive.average_monthly_spend,
        )
        action_items = service._build_action_items(
            questions=questions,
            opportunities=opportunities,
            next_best_action=overview.next_best_action,
            reports=reports,
            budget_readiness=budget_readiness,
            categorization_queue=categorization_queue,
        )

        return HouseholdFinanceDashboard(
            generated_at=datetime.now(UTC).isoformat(),
            overview=overview,
            profile=profile,
            resolved_values=resolved_values,
            budget_readiness=budget_readiness,
            budget_snapshot=budget_snapshot,
            retirement_preparedness=retirement_preparedness,
            action_items=action_items,
            opportunities=opportunities,
            reports=reports,
            categorization_queue=categorization_queue,
            recurring_commitments=recurring_commitments,
            sinking_funds=sinking_funds,
            retirement_contribution_tracker=retirement_contribution_tracker,
            retirement_scenarios=retirement_scenarios,
            import_center=_build_import_center(documents),
            questions=questions,
            jenny_brief=_JENNY_BRIEF,
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

    def build_action_items(
        self,
        *,
        questions: list[Any],
        opportunities: list[Any],
        next_best_action: str,
        reports: Any,
        budget_readiness: BudgetReadiness,
        categorization_queue: list[HouseholdCategorizationCandidate] | None = None,
    ) -> list[HouseholdActionItem]:
        return build_action_items(
            questions=questions,
            opportunities=opportunities,
            next_best_action=next_best_action,
            reports=reports,
            budget_readiness=budget_readiness,
            categorization_queue=categorization_queue,
        )

    def build_categorization_queue(
        self, service: Any, limit: int = 6
    ) -> list[HouseholdCategorizationCandidate]:
        return fetch_categorization_queue(service.storage, service.transaction_service, limit)

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
