"""Dashboard assembly helpers: overview, budget readiness, retirement, portfolio context, brief."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import (
    BudgetLane,
    BudgetReadiness,
    HouseholdFinanceDashboard,
    HouseholdOverview,
    HouseholdProfile,
    HouseholdReports,
    HouseholdResolvedValue,
    ImportCenter,
    ImportFormat,
    JennyMoneyBrief,
    JennyNeed,
    JennyProgression,
    PortfolioHouseholdContext,
    RetirementPreparedness,
)
from app.services._household_dashboard_builders import (
    build_retirement_contribution_tracker,
    build_retirement_scenarios,
    build_sinking_funds,
)
from app.services._household_dashboard_queries import (
    infer_profile_from_transactions,
)
from app.services._household_jenny_needs_builders import (
    _jenny_account_question_needs,
    _jenny_confirmation_needs,
    _jenny_freshness_needs,
    _jenny_retirement_category_needs,
    _jenny_statement_needs,
)

# ---------------------------------------------------------------------------
# Static configuration
# ---------------------------------------------------------------------------

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
        ImportFormat(label="Bank and credit statements", formats=["PDF", "CSV", "OFX", "QFX"], extracts=["transactions", "merchant names", "statement totals", "fees"]),
        ImportFormat(label="Brokerage and retirement statements", formats=["PDF", "CSV"], extracts=["holdings", "cash flows", "dividends", "contributions", "fees"]),
        ImportFormat(label="Planning and payroll documents", formats=["PDF", "PNG", "JPG"], extracts=["pay frequency", "benefits deductions", "tax withholding", "loan balance", "insurance coverage", "retirement income estimates"]),
        ImportFormat(label="Receipts and invoices", formats=["PDF", "PNG", "JPG", "HEIC"], extracts=["merchant", "date", "line items", "subtotal", "tax", "total"]),
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

_LANE_CONFIGS: list[tuple[str, str, str]] = [
    ("Essentials", "Protect fixed bills and groceries before lifestyle spending expands.", "monthly_essential_target"),
    ("Lifestyle", "Cap shopping, dining, convenience, and entertainment with clear guardrails.", "monthly_discretionary_target"),
    ("Savings", "Reserve dollars for investing, emergency cash, and future big-ticket items.", "monthly_savings_target"),
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def fields_with_confident_inferences(
    resolved_values: list[HouseholdResolvedValue], *, threshold: float
) -> set[str]:
    """Return field names that have inferred values at or above the given confidence threshold."""
    return {
        rv.field_name
        for rv in resolved_values
        if rv.source == "jenny_inference" and rv.confidence is not None and rv.confidence >= threshold and rv.value is not None
    }


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_import_center(documents: list[Any], planning: Any) -> ImportCenter:
    parsed_count = sum(1 for d in documents if d.status in {"parsed", "needs_review"})
    suggested_uploads = [r.label for r in planning.document_requirements if r.status == "missing"]
    return ImportCenter(
        headline=_IMPORT_CENTER.headline, tracked_documents=len(documents), parsed_documents=parsed_count,
        suggested_first_uploads=suggested_uploads[:6] or _IMPORT_CENTER.suggested_first_uploads,
        automations=_IMPORT_CENTER.automations, supported_documents=_IMPORT_CENTER.supported_documents,
    )


def update_overview_action(overview: HouseholdOverview, title: str) -> HouseholdOverview:
    return HouseholdOverview(
        invested_assets=overview.invested_assets, retirement_assets=overview.retirement_assets,
        taxable_assets=overview.taxable_assets, cash_reserve=overview.cash_reserve,
        total_tracked_assets=overview.total_tracked_assets, visibility_score=overview.visibility_score,
        visibility_label=overview.visibility_label, next_best_action=title,
    )


def build_jenny_needs(
    *, profile: HouseholdProfile, planning: Any, documents: list[Any], questions: list[Any],
    resolved_values: list[HouseholdResolvedValue], reports: HouseholdReports,
    confirmed_facts: dict[str, str], detected_accounts: list[dict[str, str]],
    freshness: dict[str, Any], categorization_queue: list[Any],
) -> list[JennyNeed]:
    coverage_months = freshness.get("coverage_months", 0)
    days_since_latest = freshness.get("days_since_latest")
    return [
        *_jenny_statement_needs(coverage_months, days_since_latest),
        *_jenny_confirmation_needs(confirmed_facts, planning, profile),
        *_jenny_account_question_needs(detected_accounts, questions),
        *_jenny_retirement_category_needs(profile, categorization_queue),
        *_jenny_freshness_needs(documents, days_since_latest),
    ]


def build_overview(
    *, service: Any, accounts: list[Any], live_positions: list[Any],
    holdings_by_account: dict[str, float], documents: list[Any],
    questions: list[Any], resolved_values: list[HouseholdResolvedValue],
) -> tuple[HouseholdOverview, float, float, float, float]:
    invested_assets = sum(holdings_by_account.values())
    cash_reserve = sum(a.cash_balance for a in accounts)
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
        account_count=len(accounts), position_count=len(live_positions),
        cash_reserve=cash_reserve, retirement_assets=retirement_assets,
        taxable_assets=taxable_assets, resolved_values=resolved_values, document_count=len(documents),
    )
    overview = HouseholdOverview(
        invested_assets=invested_assets, retirement_assets=retirement_assets,
        taxable_assets=taxable_assets, cash_reserve=cash_reserve,
        total_tracked_assets=total_tracked_assets, visibility_score=visibility_score,
        visibility_label=service._visibility_label(visibility_score),
        next_best_action=service._next_best_action(documents, visibility_score, questions=questions, resolved_values=resolved_values),
    )
    return overview, retirement_assets, taxable_assets, cash_reserve, total_tracked_assets


def build_budget_readiness(
    *, service: Any, resolved_values: list[HouseholdResolvedValue], documents: list[Any]
) -> BudgetReadiness:
    budget_inputs = service._budget_input_status(resolved_values, documents)
    rnv = lambda field: service._resolved_numeric_value(resolved_values, field)  # noqa: E731
    starter_lanes = [
        BudgetLane(name=name, objective=objective, status="Configured" if rnv(field) is not None else "Needs target")
        for name, objective, field in _LANE_CONFIGS
    ]
    return BudgetReadiness(
        status="ready_for_budgeting" if budget_inputs["budget_ready"] else "setup_needed",
        summary=(
            "Jenny can enforce budget guardrails once household income targets and transaction documents are in place."
            if budget_inputs["budget_ready"]
            else "Budgeting is one step away: define the monthly plan and keep feeding the system statements."
        ),
        priorities=budget_inputs["priorities"], missing_inputs=budget_inputs["missing_inputs"],
        starter_lanes=starter_lanes,
    )


def build_retirement_preparedness(
    *, service: Any, resolved_values: list[HouseholdResolvedValue], documents: list[Any],
    retirement_assets: float, taxable_assets: float, cash_reserve: float, total_tracked_assets: float,
) -> RetirementPreparedness:
    retirement_share = (retirement_assets / total_tracked_assets) * 100 if total_tracked_assets > 0 else 0.0
    ready = service._retirement_ready(resolved_values, documents)
    return RetirementPreparedness(
        status="scenario_ready" if ready else "baseline_visible",
        summary=(
            "Retirement planning can move from rough intuition to defensible scenario planning."
            if ready
            else "Retirement assets are visible, but retirement readiness still depends on real spending and future-income assumptions."
        ),
        retirement_account_share=retirement_share,
        strengths=service._retirement_strengths(retirement_assets, taxable_assets, cash_reserve, resolved_values),
        blockers=service._retirement_blockers(resolved_values, documents),
        next_steps=service._retirement_next_steps(resolved_values, documents),
    )


def build_portfolio_context(
    *, total_tracked_assets: float, cash_reserve: float, profile: HouseholdProfile, reports: HouseholdReports,
) -> PortfolioHouseholdContext | None:
    monthly_essential = (
        profile.monthly_essential_target if (profile.monthly_essential_target or 0) > 0
        else reports.executive.average_monthly_essentials or None
    )
    monthly_discretionary = (
        profile.monthly_discretionary_target if (profile.monthly_discretionary_target or 0) > 0
        else reports.executive.average_monthly_discretionary or None
    )
    annual_spend: float | None = (monthly_essential + (monthly_discretionary or 0)) * 12 if monthly_essential is not None else None
    cash_reserves_months: float | None = cash_reserve / monthly_essential if cash_reserve > 0 and monthly_essential and monthly_essential > 0 else None
    portfolio_to_annual_spend_ratio: float | None = total_tracked_assets / annual_spend if total_tracked_assets > 0 and annual_spend else None
    total_portfolio_value: float | None = total_tracked_assets if total_tracked_assets > 0 else None
    if total_portfolio_value is None and cash_reserves_months is None and portfolio_to_annual_spend_ratio is None:
        return None
    insights: list[str] = []
    if cash_reserves_months is not None:
        insights.append(f"Your cash reserves cover {cash_reserves_months:.1f} months of essential spending.")
    if portfolio_to_annual_spend_ratio is not None:
        insights.append(f"Your portfolio represents {portfolio_to_annual_spend_ratio:.1f}x your annual spending.")
    return PortfolioHouseholdContext(
        total_portfolio_value=total_portfolio_value, cash_reserves_months=cash_reserves_months,
        portfolio_to_annual_spend_ratio=portfolio_to_annual_spend_ratio, insights=insights,
    )


# ---------------------------------------------------------------------------
# Brief & progression
# ---------------------------------------------------------------------------

def _found_items(executive: Any, resolved_values: list[HouseholdResolvedValue]) -> list[str]:
    found: list[str] = []
    if executive.recurring_merchant_count > 0:
        s = "s" if executive.recurring_merchant_count != 1 else ""
        found.append(f"Detected {executive.recurring_merchant_count} recurring monthly commitment{s} from your statements")
    if executive.average_monthly_essentials > 0:
        s = "s" if executive.coverage_months != 1 else ""
        found.append(f"Your essential spending averages ${executive.average_monthly_essentials:,.0f}/mo across {executive.coverage_months} month{s}")
    if executive.tracked_expense_count > 0:
        s = "s" if executive.tracked_expense_count != 1 else ""
        found.append(f"{executive.tracked_expense_count} transaction{s} tracked and categorized from your statements")
    inferred_count = sum(1 for rv in resolved_values if rv.source == "jenny_inference" and rv.value is not None)
    if inferred_count > 0:
        s = "s" if inferred_count != 1 else ""
        found.append(f"{inferred_count} profile value{s} auto-resolved from your data")
    return found


def build_progression(*, reports: HouseholdReports, resolved_values: list[HouseholdResolvedValue], profile: HouseholdProfile) -> JennyProgression:
    executive = reports.executive
    found = _found_items(executive, resolved_values)
    profile_fields = {"monthly_net_income_target", "monthly_essential_target", "monthly_discretionary_target", "monthly_savings_target", "target_retirement_age", "target_retirement_spend"}
    confirmed_fields = {rv.field_name for rv in resolved_values if rv.source == "user" and rv.field_name in profile_fields}
    all_known = fields_with_confident_inferences(resolved_values, threshold=0.7) | confirmed_fields
    if executive.coverage_months < 3:
        working_on = "Building spending baselines \u2014 more statement history will improve accuracy"
    elif len(all_known) < len(profile_fields):
        working_on = "Refining your financial picture as more data comes in"
    else:
        working_on = "Monitoring budget pacing and identifying optimization opportunities"
    return JennyProgression(found=found, working_on=working_on)


def build_jenny_brief(profile: Any, reports: Any, resolved_values: list[HouseholdResolvedValue]) -> JennyMoneyBrief:
    return JennyMoneyBrief(
        headline=_JENNY_BRIEF.headline, body=_JENNY_BRIEF.body, prompts=_JENNY_BRIEF.prompts,
        progression=build_progression(reports=reports, resolved_values=resolved_values, profile=profile),
    )


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

def gather_service_data(service: Any) -> dict[str, Any]:
    profile = service.get_profile()
    planning = service.get_planning_snapshot()
    documents = service.list_documents(limit=12).items
    questions = service.list_questions(limit=12).items
    accounts = [a for a in service.portfolio_mgr.get_accounts() if a.account_type != "paper"]
    positions = service.portfolio_mgr.get_positions()
    account_ids = {a.id for a in accounts}
    live_positions = [p for p in positions if p.account_id in account_ids]
    price_data = service._fetch_prices(live_positions)
    holdings_by_account = service._calculate_holdings_by_account(live_positions, price_data)
    reports = service.transaction_service.build_reports()
    return {
        "profile": profile, "planning": planning, "documents": documents, "questions": questions,
        "accounts": accounts, "live_positions": live_positions,
        "holdings_by_account": holdings_by_account, "reports": reports,
    }


def resolve_dashboard_values(service: Any, *, profile: Any, reports: Any, questions: list[Any]) -> tuple[list[Any], list[Any]]:
    infer_profile_from_transactions(service.storage, profile=profile, reports=reports, existing_inferences=service._get_inferred_value_rows())
    resolved_values = service.get_resolved_values(profile=profile, questions=questions)
    non_inferable_fields = {"target_retirement_age", "target_retirement_spend"}
    inferred_fields = fields_with_confident_inferences(resolved_values, threshold=0.7)
    visible_questions = [q for q in questions if q.field_name is None or q.field_name in non_inferable_fields or q.field_name not in inferred_fields]
    return resolved_values, visible_questions


def assemble_finance_dashboard(
    *, d: dict[str, Any], service: Any, overview: HouseholdOverview,
    resolved_values: list[HouseholdResolvedValue], visible_questions: list[Any],
    jenny_needs: list[JennyNeed], retirement_assets: float, taxable_assets: float,
    cash_reserve: float, total_tracked_assets: float,
    categorization_queue: list[Any], recurring_commitments: list[Any],
) -> HouseholdFinanceDashboard:
    profile, reports, documents, planning = d["profile"], d["reports"], d["documents"], d["planning"]
    return HouseholdFinanceDashboard(
        generated_at=datetime.now(UTC).isoformat(),
        overview=overview, profile=profile, resolved_values=resolved_values,
        budget_readiness=build_budget_readiness(service=service, resolved_values=resolved_values, documents=documents),
        budget_snapshot=service._build_budget_snapshot(profile=profile, reports=reports),
        retirement_preparedness=build_retirement_preparedness(
            service=service, resolved_values=resolved_values, documents=documents,
            retirement_assets=retirement_assets, taxable_assets=taxable_assets,
            cash_reserve=cash_reserve, total_tracked_assets=total_tracked_assets,
        ),
        jenny_needs=jenny_needs, reports=reports,
        categorization_queue=categorization_queue, recurring_commitments=recurring_commitments,
        sinking_funds=build_sinking_funds(recurring_commitments=recurring_commitments),
        retirement_contribution_tracker=build_retirement_contribution_tracker(
            profile=profile, estimated_monthly_contributions=service._estimate_monthly_retirement_contributions(),
        ),
        retirement_scenarios=build_retirement_scenarios(
            retirement_assets=retirement_assets, target_retirement_spend=profile.target_retirement_spend,
            baseline_monthly_spend=reports.executive.average_monthly_spend,
        ),
        import_center=build_import_center(documents, planning),
        questions=visible_questions,
        jenny_brief=build_jenny_brief(profile, reports, resolved_values),
        portfolio_context=build_portfolio_context(
            total_tracked_assets=total_tracked_assets, cash_reserve=cash_reserve,
            profile=profile, reports=reports,
        ),
        planning=planning,
    )
