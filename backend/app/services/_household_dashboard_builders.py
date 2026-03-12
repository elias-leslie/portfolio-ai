"""Pure builder functions for household dashboard sections (no DB access)."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta

from app.models.household_finance import (
    BudgetLane,
    BudgetReadiness,
    HouseholdBudgetSnapshot,
    HouseholdFinanceDashboard,
    HouseholdOverview,
    HouseholdRecurringCommitment,
    HouseholdRetirementContributionTracker,
    HouseholdRetirementScenario,
    HouseholdSinkingFund,
    ImportCenter,
    ImportFormat,
    JennyMoneyBrief,
    JennyNeed,
    JennyProgression,
    PortfolioHouseholdContext,
    RetirementPreparedness,
)
from app.services._household_jenny_needs_builders import (
    _jenny_account_question_needs,
    _jenny_confirmation_needs,
    _jenny_freshness_needs,
    _jenny_retirement_category_needs,
    _jenny_statement_needs,
)

_CADENCE_MULTIPLIERS: dict[str, int] = {
    "weekly": 52,
    "biweekly": 26,
    "monthly": 12,
    "quarterly": 4,
}

_CADENCE_OFFSETS: dict[str, timedelta | relativedelta] = {
    "weekly": timedelta(weeks=1),
    "biweekly": timedelta(weeks=2),
    "monthly": relativedelta(months=1),
    "quarterly": relativedelta(months=3),
}

_SUBSCRIPTION_CATEGORIES = {"subscriptions", "dining"}
_RECURRING_CADENCES = {"monthly", "biweekly", "weekly", "quarterly"}

_CATEGORY_KEYWORDS: list[tuple[list[str], str]] = [
    (["spotify", "netflix", "prime"], "Subscriptions"),
    (["walmart", "publix", "whole foods"], "Groceries"),
    (["shell", "speedway"], "Gas"),
    (["insurance", "duke", "mortgage"], "Bills"),
]
_ESSENTIAL_CATEGORIES = {"Groceries", "Gas", "Bills"}


def suggest_category(merchant: str, description: str) -> str:
    candidate = f"{merchant} {description}".lower()
    for keywords, category in _CATEGORY_KEYWORDS:
        if any(kw in candidate for kw in keywords):
            return category
    return "Household"


def suggest_essentiality(merchant: str, description: str) -> str:
    category = suggest_category(merchant, description)
    return "essential" if category in _ESSENTIAL_CATEGORIES else "discretionary"


def estimate_next_commitment_date(last_seen: datetime, cadence: str) -> str | None:
    offset = _CADENCE_OFFSETS.get(cadence)
    if offset is None:
        return None
    return (last_seen + offset).isoformat()


def build_recurring_commitment(
    row: Any,
    cadence: str,
    cadence_info: dict[str, Any],
    today: Any,
) -> HouseholdRecurringCommitment | None:
    """Build a single recurring commitment from a DB row, or return None to skip."""
    if cadence not in _RECURRING_CADENCES:
        return None
    average_amount = float(row[2] or 0.0)
    last_seen = row[4]
    if last_seen is None:
        return None
    merchant = str(row[0])
    annualized_cost = average_amount * _CADENCE_MULTIPLIERS.get(cadence, 12)
    commitment_type = (
        "subscription" if str(row[1]).lower() in _SUBSCRIPTION_CATEGORIES else "bill"
    )
    next_expected = estimate_next_commitment_date(last_seen, cadence)
    next_expected_date = (
        datetime.fromisoformat(next_expected).date() if next_expected is not None else None
    )
    days_until_due = (
        (next_expected_date - today).days if next_expected_date is not None else None
    )
    if days_until_due is None:
        due_status = "unknown"
    elif days_until_due < 0:
        due_status = "overdue"
    elif days_until_due <= 3:
        due_status = "due_soon"
    else:
        due_status = "upcoming"
    return HouseholdRecurringCommitment(
        merchant=merchant,
        category=str(row[1]),
        cadence=cadence,
        average_amount=round(average_amount, 2),
        annualized_cost=round(annualized_cost, 2),
        last_seen=last_seen.isoformat(),
        next_expected=next_expected,
        days_until_due=days_until_due,
        due_status=due_status,
        due_confidence=float(cadence_info.get("confidence") or 0.0),
        commitment_type=commitment_type,
    )


def build_sinking_funds(
    *, recurring_commitments: list[HouseholdRecurringCommitment]
) -> list[HouseholdSinkingFund]:
    funds: list[HouseholdSinkingFund] = []
    for commitment in recurring_commitments:
        if commitment.cadence not in {"quarterly", "irregular"} and commitment.average_amount < 150:
            continue
        monthly_target = round(commitment.annualized_cost / 12, 2)
        funds.append(
            HouseholdSinkingFund(
                name=f"{commitment.merchant} buffer",
                monthly_target=monthly_target,
                annual_cost=round(commitment.annualized_cost, 2),
                rationale="Set aside a monthly buffer so periodic or lumpy household costs stop surprising the budget.",
            )
        )
    return funds[:4]


def build_retirement_contribution_tracker(
    *,
    profile: Any,
    estimated_monthly_contributions: float,
) -> HouseholdRetirementContributionTracker:
    monthly_target = profile.monthly_savings_target
    if monthly_target is None:
        return HouseholdRetirementContributionTracker(
            status="target_missing",
            monthly_target=None,
            estimated_monthly_contributions=estimated_monthly_contributions,
            monthly_gap=0.0,
            detail="Set the monthly savings target so Jenny can compare current retirement contributions against the plan.",
        )
    monthly_gap = max(monthly_target - estimated_monthly_contributions, 0.0)
    status = "gap" if monthly_gap > 0 else "on_track"
    detail = (
        "Recent retirement contributions are trailing the household savings target."
        if monthly_gap > 0
        else "Recent retirement contributions are keeping up with the savings target."
    )
    return HouseholdRetirementContributionTracker(
        status=status,
        monthly_target=monthly_target,
        estimated_monthly_contributions=estimated_monthly_contributions,
        monthly_gap=monthly_gap,
        detail=detail,
    )


def build_retirement_scenarios(
    *,
    retirement_assets: float,
    target_retirement_spend: float | None,
    baseline_monthly_spend: float,
) -> list[HouseholdRetirementScenario]:
    base_monthly_spend = target_retirement_spend or baseline_monthly_spend or 0.0
    if base_monthly_spend <= 0:
        return []
    scenario_inputs = [
        ("Base plan", base_monthly_spend),
        ("Higher-spend stretch", round(base_monthly_spend * 1.15, 2)),
        ("Lean floor", round(base_monthly_spend * 0.85, 2)),
    ]
    return [
        HouseholdRetirementScenario(
            name=name,
            monthly_spend=round(monthly_spend, 2),
            annual_spend=round(monthly_spend * 12, 2),
            funded_years=round(retirement_assets / (monthly_spend * 12), 1) if monthly_spend > 0 else 0.0,
            readiness=(
                "strong"
                if (retirement_assets / (monthly_spend * 12) if monthly_spend > 0 else 0) >= 25
                else "developing"
                if (retirement_assets / (monthly_spend * 12) if monthly_spend > 0 else 0) >= 15
                else "short"
            ),
            detail="A plain-language spend scenario using currently visible retirement assets.",
        )
        for name, monthly_spend in scenario_inputs
    ]


def _budget_analysis(
    *,
    has_plan: bool,
    monthly_plan_total: float,
    month_to_date_spend: float,
    profile: Any,
    reports: Any,
) -> tuple[float | None, str, str, str, str]:
    """Return (mtd_plan, pace_status, pace_detail, status, summary) for budget snapshot."""
    if not has_plan:
        return (
            None, "unknown",
            "Jenny needs a monthly plan before it can judge pacing.",
            "setup_needed",
            "Set the core monthly plan so Jenny can judge whether current spending is on pace.",
        )
    today = datetime.now(UTC).date()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    month_to_date_plan = round(monthly_plan_total * (today.day / days_in_month), 2)
    pace_delta = month_to_date_spend - month_to_date_plan
    tolerance = max(month_to_date_plan * 0.05, 100)
    if abs(pace_delta) <= tolerance:
        pace_status, pace_detail = "on_track", "Month-to-date spend is tracking close to the plan."
    elif pace_delta > 0:
        pace_status = "running_hot"
        pace_detail = (
            f"Month-to-date spend is ahead of plan by ${pace_delta:,.0f}. "
            "Review discretionary and recurring categories before the month hardens."
        )
    else:
        pace_status = "under_plan"
        pace_detail = (
            f"Month-to-date spend is ${abs(pace_delta):,.0f} below plan. "
            "The plan still has room for remaining bills and savings."
        )
    if (
        profile.monthly_essential_target is not None
        and reports.executive.average_monthly_essentials > profile.monthly_essential_target
    ):
        status, summary = "essentials_above_plan", "Essential spending is running above the current target and needs review."
    elif (
        profile.monthly_discretionary_target is not None
        and reports.executive.average_monthly_discretionary > profile.monthly_discretionary_target
    ):
        status, summary = "discretionary_above_plan", "Discretionary spending is running above the current cap."
    else:
        status, summary = "on_track", "The current monthly spending profile is inside the available budget guardrails."
    return month_to_date_plan, pace_status, pace_detail, status, summary


def build_budget_snapshot(
    *,
    profile: Any,
    reports: Any,
    month_to_date_spend: float,
) -> HouseholdBudgetSnapshot:
    plan_values = (
        profile.monthly_essential_target,
        profile.monthly_discretionary_target,
        profile.monthly_savings_target,
    )
    monthly_plan_total = sum(v for v in plan_values if v is not None)
    has_plan = any(v is not None for v in plan_values)
    remaining_cash_after_plan = (
        profile.monthly_net_income_target - monthly_plan_total
        if profile.monthly_net_income_target is not None and has_plan
        else None
    )
    discretionary_headroom = (
        profile.monthly_discretionary_target - reports.executive.average_monthly_discretionary
        if profile.monthly_discretionary_target is not None
        else None
    )
    month_to_date_plan, pace_status, pace_detail, status, summary = _budget_analysis(
        has_plan=has_plan,
        monthly_plan_total=monthly_plan_total,
        month_to_date_spend=month_to_date_spend,
        profile=profile,
        reports=reports,
    )
    return HouseholdBudgetSnapshot(
        status=status,
        summary=summary,
        monthly_income_target=profile.monthly_net_income_target,
        monthly_plan_total=monthly_plan_total if has_plan else None,
        essential_target=profile.monthly_essential_target,
        discretionary_target=profile.monthly_discretionary_target,
        savings_target=profile.monthly_savings_target,
        actual_monthly_spend=reports.executive.average_monthly_spend,
        actual_essential_monthly_spend=reports.executive.average_monthly_essentials,
        actual_discretionary_monthly_spend=reports.executive.average_monthly_discretionary,
        month_to_date_spend=month_to_date_spend,
        month_to_date_plan=month_to_date_plan,
        pace_status=pace_status,
        pace_detail=pace_detail,
        remaining_cash_after_plan=remaining_cash_after_plan,
        discretionary_headroom=discretionary_headroom,
    )


# ---------------------------------------------------------------------------
# Dashboard-level builder helpers (moved from household_dashboard_composer)
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
            label="Planning and payroll documents",
            formats=["PDF", "PNG", "JPG"],
            extracts=[
                "pay frequency",
                "benefits deductions",
                "tax withholding",
                "loan balance",
                "insurance coverage",
                "retirement income estimates",
            ],
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


def _fields_with_confident_inferences(resolved_values: list[Any], *, threshold: float) -> set[str]:
    """Return field names that have inferred values at or above the given confidence threshold."""
    return {
        rv.field_name
        for rv in resolved_values
        if (
            rv.source == "jenny_inference"
            and rv.confidence is not None
            and rv.confidence >= threshold
            and rv.value is not None
        )
    }


def _build_import_center(documents: list[Any], planning: Any) -> ImportCenter:
    parsed_count = sum(1 for d in documents if d.status in {"parsed", "needs_review"})
    suggested_uploads = [
        requirement.label
        for requirement in planning.document_requirements
        if requirement.status == "missing"
    ]
    return ImportCenter(
        headline=_IMPORT_CENTER.headline,
        tracked_documents=len(documents),
        parsed_documents=parsed_count,
        suggested_first_uploads=suggested_uploads[:6] or _IMPORT_CENTER.suggested_first_uploads,
        automations=_IMPORT_CENTER.automations,
        supported_documents=_IMPORT_CENTER.supported_documents,
    )


def _update_overview_action(overview: HouseholdOverview, title: str) -> HouseholdOverview:
    """Return a copy of overview with next_best_action replaced."""
    return HouseholdOverview(
        invested_assets=overview.invested_assets,
        retirement_assets=overview.retirement_assets,
        taxable_assets=overview.taxable_assets,
        cash_reserve=overview.cash_reserve,
        total_tracked_assets=overview.total_tracked_assets,
        visibility_score=overview.visibility_score,
        visibility_label=overview.visibility_label,
        next_best_action=title,
    )


def _build_jenny_needs(
    *,
    profile: Any,
    planning: Any,
    documents: list[Any],
    questions: list[Any],
    resolved_values: list[Any],
    reports: Any,
    confirmed_facts: dict[str, str],
    detected_accounts: list[dict[str, str]],
    freshness: dict[str, Any],
    categorization_queue: list[Any],
) -> list[JennyNeed]:
    """Build the unified priority-ordered jenny_needs list. Only unsatisfied needs are returned."""
    coverage_months = freshness.get("coverage_months", 0)
    days_since_latest = freshness.get("days_since_latest")
    return [
        *_jenny_statement_needs(coverage_months, days_since_latest),
        *_jenny_confirmation_needs(confirmed_facts, planning, profile),
        *_jenny_account_question_needs(detected_accounts, questions),
        *_jenny_retirement_category_needs(profile, categorization_queue),
        *_jenny_freshness_needs(documents, days_since_latest),
    ]


def _build_progression(
    *,
    reports: Any,
    resolved_values: list[Any],
    profile: Any,
) -> JennyProgression:
    """Build the found/working-on progression for the Jenny brief."""
    executive = reports.executive
    found: list[str] = []
    if executive.recurring_merchant_count > 0:
        found.append(
            f"Detected {executive.recurring_merchant_count} recurring monthly "
            f"commitment{'s' if executive.recurring_merchant_count != 1 else ''} "
            f"from your statements"
        )
    if executive.average_monthly_essentials > 0:
        found.append(
            f"Your essential spending averages ${executive.average_monthly_essentials:,.0f}/mo "
            f"across {executive.coverage_months} month{'s' if executive.coverage_months != 1 else ''}"
        )
    if executive.tracked_expense_count > 0:
        found.append(
            f"{executive.tracked_expense_count} transaction{'s' if executive.tracked_expense_count != 1 else ''} "
            f"tracked and categorized from your statements"
        )
    inferred_count = sum(
        1 for rv in resolved_values
        if rv.source == "jenny_inference" and rv.value is not None
    )
    if inferred_count > 0:
        found.append(
            f"{inferred_count} profile value{'s' if inferred_count != 1 else ''} "
            f"auto-resolved from your data"
        )
    profile_fields = {
        "monthly_net_income_target", "monthly_essential_target", "monthly_discretionary_target",
        "monthly_savings_target", "target_retirement_age", "target_retirement_spend",
    }
    confirmed_fields = {rv.field_name for rv in resolved_values if rv.source == "user" and rv.field_name in profile_fields}
    all_known = _fields_with_confident_inferences(resolved_values, threshold=0.7) | confirmed_fields
    if executive.coverage_months < 3:
        working_on = "Building spending baselines \u2014 more statement history will improve accuracy"
    elif len(all_known) < len(profile_fields):
        working_on = "Refining your financial picture as more data comes in"
    else:
        working_on = "Monitoring budget pacing and identifying optimization opportunities"
    return JennyProgression(found=found, working_on=working_on)


def _build_portfolio_context(
    *,
    total_tracked_assets: float,
    cash_reserve: float,
    profile: Any,
    reports: Any,
) -> PortfolioHouseholdContext | None:
    """Bridge portfolio data with household spending to produce cross-domain insights."""
    monthly_essential = (
        profile.monthly_essential_target
        if (profile.monthly_essential_target or 0) > 0
        else reports.executive.average_monthly_essentials or None
    )
    monthly_discretionary = (
        profile.monthly_discretionary_target
        if (profile.monthly_discretionary_target or 0) > 0
        else reports.executive.average_monthly_discretionary or None
    )
    annual_spend: float | None = None
    if monthly_essential is not None:
        annual_spend = (monthly_essential + (monthly_discretionary or 0)) * 12
    cash_reserves_months: float | None = (
        cash_reserve / monthly_essential
        if cash_reserve > 0 and monthly_essential and monthly_essential > 0
        else None
    )
    portfolio_to_annual_spend_ratio: float | None = (
        total_tracked_assets / annual_spend
        if total_tracked_assets > 0 and annual_spend
        else None
    )
    total_portfolio_value: float | None = total_tracked_assets if total_tracked_assets > 0 else None
    if total_portfolio_value is None and cash_reserves_months is None and portfolio_to_annual_spend_ratio is None:
        return None
    insights: list[str] = []
    if cash_reserves_months is not None:
        insights.append(f"Your cash reserves cover {cash_reserves_months:.1f} months of essential spending.")
    if portfolio_to_annual_spend_ratio is not None:
        insights.append(f"Your portfolio represents {portfolio_to_annual_spend_ratio:.1f}x your annual spending.")
    return PortfolioHouseholdContext(
        total_portfolio_value=total_portfolio_value,
        cash_reserves_months=cash_reserves_months,
        portfolio_to_annual_spend_ratio=portfolio_to_annual_spend_ratio,
        insights=insights,
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


def _build_budget_readiness(
    *, service: Any, resolved_values: list[Any], documents: list[Any]
) -> BudgetReadiness:
    budget_inputs = service._budget_input_status(resolved_values, documents)
    rnv = lambda field: service._resolved_numeric_value(resolved_values, field)  # noqa: E731
    _lane_configs = [
        (
            "Essentials",
            "Protect fixed bills and groceries before lifestyle spending expands.",
            "monthly_essential_target",
        ),
        (
            "Lifestyle",
            "Cap shopping, dining, convenience, and entertainment with clear guardrails.",
            "monthly_discretionary_target",
        ),
        (
            "Savings",
            "Reserve dollars for investing, emergency cash, and future big-ticket items.",
            "monthly_savings_target",
        ),
    ]
    starter_lanes = [
        BudgetLane(
            name=name,
            objective=objective,
            status="Configured" if rnv(field) is not None else "Needs target",
        )
        for name, objective, field in _lane_configs
    ]
    return BudgetReadiness(
        status="ready_for_budgeting" if budget_inputs["budget_ready"] else "setup_needed",
        summary=(
            "Jenny can enforce budget guardrails once household income targets and transaction documents are in place."
            if budget_inputs["budget_ready"]
            else "Budgeting is one step away: define the monthly plan and keep feeding the system statements."
        ),
        priorities=budget_inputs["priorities"],
        missing_inputs=budget_inputs["missing_inputs"],
        starter_lanes=starter_lanes,
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


def _gather_service_data(service: Any) -> dict[str, Any]:
    """Load all raw data from the service layer in one pass."""
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
        "profile": profile,
        "planning": planning,
        "documents": documents,
        "questions": questions,
        "accounts": accounts,
        "live_positions": live_positions,
        "holdings_by_account": holdings_by_account,
        "reports": reports,
    }


def _assemble_finance_dashboard(
    *,
    d: dict[str, Any],
    service: Any,
    overview: HouseholdOverview,
    resolved_values: list[Any],
    visible_questions: list[Any],
    jenny_needs: list[JennyNeed],
    retirement_assets: float,
    taxable_assets: float,
    cash_reserve: float,
    total_tracked_assets: float,
    categorization_queue: list[Any],
    recurring_commitments: list[Any],
) -> HouseholdFinanceDashboard:
    profile, reports, documents, planning = d["profile"], d["reports"], d["documents"], d["planning"]
    budget_readiness = _build_budget_readiness(
        service=service, resolved_values=resolved_values, documents=documents)
    retirement_preparedness = _build_retirement_preparedness(
        service=service, resolved_values=resolved_values, documents=documents,
        retirement_assets=retirement_assets, taxable_assets=taxable_assets,
        cash_reserve=cash_reserve, total_tracked_assets=total_tracked_assets)
    jenny_brief = JennyMoneyBrief(
        headline=_JENNY_BRIEF.headline, body=_JENNY_BRIEF.body, prompts=_JENNY_BRIEF.prompts,
        progression=_build_progression(reports=reports, resolved_values=resolved_values, profile=profile))
    return HouseholdFinanceDashboard(
        generated_at=datetime.now(UTC).isoformat(),
        overview=overview, profile=profile, resolved_values=resolved_values,
        budget_readiness=budget_readiness,
        budget_snapshot=service._build_budget_snapshot(profile=profile, reports=reports),
        retirement_preparedness=retirement_preparedness,
        jenny_needs=jenny_needs, reports=reports,
        categorization_queue=categorization_queue, recurring_commitments=recurring_commitments,
        sinking_funds=build_sinking_funds(recurring_commitments=recurring_commitments),
        retirement_contribution_tracker=build_retirement_contribution_tracker(
            profile=profile,
            estimated_monthly_contributions=service._estimate_monthly_retirement_contributions(),
        ),
        retirement_scenarios=build_retirement_scenarios(
            retirement_assets=retirement_assets,
            target_retirement_spend=profile.target_retirement_spend,
            baseline_monthly_spend=reports.executive.average_monthly_spend,
        ),
        import_center=_build_import_center(documents, planning),
        questions=visible_questions, jenny_brief=jenny_brief,
        portfolio_context=_build_portfolio_context(
            total_tracked_assets=total_tracked_assets, cash_reserve=cash_reserve,
            profile=profile, reports=reports,
        ),
        planning=planning,
    )
