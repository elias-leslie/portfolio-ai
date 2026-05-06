"""Dashboard assembly helpers: overview, budget readiness, retirement, portfolio context, brief."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from app.models.household_finance import (
    BudgetLane,
    BudgetReadiness,
    HouseholdEvidenceAccount,
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
from app.portfolio.account_valuation import calculate_account_valuations
from app.services._household_dashboard_builders import (
    build_budget_snapshot,
    build_retirement_contribution_tracker,
    build_retirement_scenarios,
    build_sinking_funds,
)
from app.services._household_dashboard_profile_inference import (
    infer_profile_from_transactions,
)
from app.services._household_dashboard_queries import (
    fetch_current_month_spend,
    fetch_inferred_value_rows,
    fetch_monthly_retirement_contributions,
)
from app.services._household_dashboard_sections import (
    VISIBILITY_STRONG_THRESHOLD,
    budget_input_status,
    compute_visibility_score,
    next_best_action,
    retirement_blockers,
    retirement_next_steps,
    retirement_ready,
    retirement_strengths,
    visibility_label,
)
from app.services._household_finance_utils import (
    RETIREMENT_ACCOUNT_TYPES,
    TAXABLE_ACCOUNT_TYPES,
    resolved_numeric_value,
)
from app.services._household_jenny_needs_builders import (
    _jenny_account_question_needs,
    _jenny_confirmation_needs,
    _jenny_freshness_needs,
    _jenny_retirement_category_needs,
    _jenny_statement_needs,
    _jenny_transaction_date_quality_needs,
)

# ---------------------------------------------------------------------------
# Static configuration
# ---------------------------------------------------------------------------

_IMPORT_CENTER = ImportCenter(
    headline="Use one intake inbox for statements, screenshots, exports, and planning documents.",
    tracked_documents=0,
    parsed_documents=0,
    suggested_first_uploads=[
        "Recent bank or credit-card statements",
        "Brokerage or retirement screenshots and statements",
        "CSV, OFX, or QFX account exports",
        "Payroll, tax, mortgage, insurance, or bill documents",
    ],
    automations=[
        "Classify uploads into cash-flow, portfolio, planning, or reference context.",
        "Normalize merchants and account evidence into one spend ledger.",
        "Reconcile brokerage cash flows, balances, dividends, and fees against account context.",
    ],
    supported_documents=[
        ImportFormat(label="Cash-flow evidence", formats=["PDF", "CSV", "OFX", "QFX"], extracts=["transactions", "merchant names", "statement totals", "fees"]),
        ImportFormat(label="Portfolio evidence", formats=["PDF", "CSV", "PNG", "JPG"], extracts=["holdings", "balances", "cash flows", "dividends", "contributions", "fees"]),
        ImportFormat(label="Planning evidence", formats=["PDF", "PNG", "JPG", "HEIC"], extracts=["pay frequency", "benefits deductions", "tax withholding", "loan balance", "insurance coverage", "retirement income estimates"]),
        ImportFormat(label="Receipt and billing evidence", formats=["PDF", "PNG", "JPG", "HEIC"], extracts=["merchant", "date", "line items", "subtotal", "tax", "total"]),
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
_DEGRADED_ACCOUNT_FRESHNESS_STATUSES = {"aging", "stale", "needs_evidence"}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _call_service_override(
    service: Any | None,
    attr: str,
    fallback: Any,
    /,
    *args: Any,
    **kwargs: Any,
) -> Any:
    override = getattr(service, attr, None) if service is not None else None
    if callable(override):
        return override(*args, **kwargs)
    return fallback(*args, **kwargs)


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
    return overview.model_copy(update={"next_best_action": title})


def _apply_account_freshness_visibility_cap(
    visibility_score: int,
    account_summaries: list[Any],
) -> int:
    if not account_summaries:
        return visibility_score

    degraded_count = sum(
        1
        for account in account_summaries
        if account.freshness_status in _DEGRADED_ACCOUNT_FRESHNESS_STATUSES
    )
    if degraded_count == 0:
        return visibility_score

    if degraded_count * 2 >= len(account_summaries):
        return min(visibility_score, VISIBILITY_STRONG_THRESHOLD - 1)

    return min(visibility_score, 99)


def _pluralize(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")


def _format_issue_counts(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _latest_visible_date(
    accounts: list[Any],
    *,
    attr_name: str,
) -> str | None:
    return max(
        (
            str(getattr(account, attr_name))
            for account in accounts
            if getattr(account, attr_name, None)
        ),
        default=None,
    )


def _overview_totals_from_account_summaries(
    account_summaries: list[Any],
) -> tuple[float, float, float, float, float, float] | None:
    if not account_summaries:
        return None

    asset_accounts = [
        account
        for account in account_summaries
        if account.current_value is not None and account.asset_group not in {"credit", "debt"}
    ]
    liability_accounts = [
        account
        for account in account_summaries
        if account.current_value is not None and account.asset_group in {"credit", "debt"}
    ]
    if not asset_accounts and not liability_accounts:
        return None

    total_tracked_assets = sum(float(account.current_value or 0.0) for account in asset_accounts)
    liabilities_total = sum(float(account.current_value or 0.0) for account in liability_accounts)
    retirement_assets = sum(
        float(account.current_value or 0.0)
        for account in asset_accounts
        if account.asset_group == "retirement"
    )
    taxable_assets = sum(
        float(account.current_value or 0.0)
        for account in asset_accounts
        if account.asset_group in {"taxable", "education"}
    )
    cash_reserve = sum(
        float(
            account.cash_balance
            if account.cash_balance is not None
            else account.current_value or 0.0
        )
        for account in asset_accounts
        if account.asset_group in {"cash", "taxable"}
        and account.money_role == "spend_driver"
    )
    invested_assets = max(total_tracked_assets - cash_reserve, 0.0)
    return (
        invested_assets,
        cash_reserve,
        retirement_assets,
        taxable_assets,
        total_tracked_assets,
        liabilities_total,
    )


def _net_worth_trust(
    account_summaries: list[Any],
) -> tuple[str, str]:
    if not account_summaries:
        return (
            "unavailable",
            "Net worth is not available yet because Jenny has not matched any balance-bearing accounts.",
        )

    visible_accounts = [
        account
        for account in account_summaries
        if account.current_value is not None
    ]
    currentish_accounts = [
        account
        for account in visible_accounts
        if account.balance_freshness_status in {"fresh", "aging"}
    ]
    if not visible_accounts:
        return (
            "unavailable",
            "Net worth is not available yet because Jenny does not have any usable balance evidence.",
        )

    missing_balance_count = sum(
        1
        for account in account_summaries
        if account.current_value is None
        or account.balance_freshness_status == "needs_evidence"
    )
    stale_balance_count = sum(
        1
        for account in account_summaries
        if account.balance_freshness_status == "stale"
    )
    aging_balance_count = sum(
        1
        for account in account_summaries
        if account.balance_freshness_status == "aging"
    )
    candidate_count = sum(
        1
        for account in account_summaries
        if account.match_status == "candidate"
    )
    latest_balance_at = _latest_visible_date(
        visible_accounts,
        attr_name="last_balance_at",
    )
    as_of_detail = (
        f" Latest visible balance date {latest_balance_at[:10]}."
        if latest_balance_at is not None
        else ""
    )

    estimate_issue_parts: list[str] = []
    if missing_balance_count > 0:
        estimate_issue_parts.append(
            f"{missing_balance_count} {_pluralize(missing_balance_count, 'account')} missing current balances"
        )
    if candidate_count > 0:
        estimate_issue_parts.append(
            f"{candidate_count} possible {_pluralize(candidate_count, 'account')} still need confirmation"
        )
    if stale_balance_count > 0:
        estimate_issue_parts.append(
            f"{stale_balance_count} {_pluralize(stale_balance_count, 'account')} stale"
        )
    if estimate_issue_parts and (missing_balance_count > 0 or candidate_count > 0):
        return (
            "estimated",
            (
                f"Known net worth from {len(visible_accounts)} of {len(account_summaries)} tracked "
                f"{_pluralize(len(account_summaries), 'account')}. "
                f"{_format_issue_counts(estimate_issue_parts).capitalize()}."
                f"{as_of_detail}"
            ),
        )
    refresh_count = stale_balance_count + aging_balance_count
    if refresh_count > 0:
        return (
            "stale",
            (
                f"Known net worth subtotal from {len(visible_accounts)} tracked "
                f"{_pluralize(len(visible_accounts), 'account')}. "
                f"{refresh_count} {_pluralize(refresh_count, 'account')} should refresh before review."
                f"{as_of_detail}"
            ),
        )

    if latest_balance_at is not None:
        return (
            "current",
            f"Net worth reflects {len(currentish_accounts)} covered {_pluralize(len(currentish_accounts), 'account')} through {latest_balance_at[:10]}.",
        )
    return (
        "current",
        f"Net worth reflects {len(currentish_accounts)} covered {_pluralize(len(currentish_accounts), 'account')}.",
    )


def _monthly_spend_trust(
    account_summaries: list[Any],
    statement_freshness: dict[str, Any],
) -> tuple[str, str]:
    spend_accounts = [
        account
        for account in account_summaries
        if account.money_role == "spend_driver"
    ]
    if not spend_accounts:
        return (
            "unavailable",
            "Monthly spend is not available yet because Jenny does not have any checking, card, or debt accounts with transaction history.",
        )

    fresh_transaction_count = sum(
        1
        for account in spend_accounts
        if account.transaction_freshness_status == "fresh"
    )
    aging_transaction_count = sum(
        1
        for account in spend_accounts
        if account.transaction_freshness_status == "aging"
    )
    stale_transaction_count = sum(
        1
        for account in spend_accounts
        if account.transaction_freshness_status == "stale"
    )
    missing_transaction_count = sum(
        1
        for account in spend_accounts
        if account.transaction_freshness_status == "needs_evidence"
    )
    historical_transaction_count = sum(
        1
        for account in spend_accounts
        if account.last_transaction_at is not None
        or account.transaction_freshness_status in {"fresh", "aging", "stale"}
    )
    latest_transaction_date = statement_freshness.get("most_recent_date")
    days_since_latest = statement_freshness.get("days_since_latest")
    gap_months = statement_freshness.get("gap_months") or []
    coverage_months = int(statement_freshness.get("coverage_months") or 0)
    visible_spend_accounts = max(
        fresh_transaction_count + aging_transaction_count + stale_transaction_count,
        historical_transaction_count,
    )
    latest_suffix = (
        f" Latest covered transaction date {latest_transaction_date}."
        if latest_transaction_date is not None
        else ""
    )

    if coverage_months <= 0 and visible_spend_accounts <= 0:
        return (
            "unavailable",
            "Monthly spend is not available yet because Jenny does not have any usable spending history.",
        )

    issue_parts: list[str] = []
    if missing_transaction_count > 0:
        issue_parts.append(
            f"{missing_transaction_count} {_pluralize(missing_transaction_count, 'spending account')} missing transactions"
        )
    if stale_transaction_count > 0:
        issue_parts.append(
            f"{stale_transaction_count} {_pluralize(stale_transaction_count, 'spending account')} stale"
        )
    if gap_months:
        issue_parts.append(str(gap_months[0]).lower())
    if days_since_latest is None:
        issue_parts.append("latest covered transaction date unknown")
    elif days_since_latest > 7:
        issue_parts.append(f"latest covered transaction is {days_since_latest} days old")
    if fresh_transaction_count + aging_transaction_count <= 0 and visible_spend_accounts > 0:
        return (
            "stale",
            (
                f"Monthly spend subtotal is based on older history from {visible_spend_accounts} of "
                f"{len(spend_accounts)} spending {_pluralize(len(spend_accounts), 'account')}."
                f"{latest_suffix} Refresh before using it for a weekly review."
            ),
        )
    if issue_parts:
        return (
            "estimated",
            (
                f"Monthly spend estimate from {visible_spend_accounts} of {len(spend_accounts)} spending "
                f"{_pluralize(len(spend_accounts), 'account')}. "
                f"{_format_issue_counts(issue_parts).capitalize()}."
                f"{latest_suffix}"
            ),
        )
    if aging_transaction_count > 0:
        return (
            "stale",
            (
                f"Monthly spend subtotal comes from {fresh_transaction_count + aging_transaction_count} covered "
                f"spending {_pluralize(fresh_transaction_count + aging_transaction_count, 'account')}, "
                f"but {aging_transaction_count} should refresh before weekly review."
                f"{latest_suffix}"
            ),
        )

    detail = (
        f"Monthly spend reflects {fresh_transaction_count} covered "
        f"{_pluralize(fresh_transaction_count, 'spending account')}"
        f"{f' through {latest_transaction_date}' if latest_transaction_date else ''}."
    )
    return ("current", detail)


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
        *_jenny_transaction_date_quality_needs(freshness),
        *_jenny_freshness_needs(documents, days_since_latest),
    ]


def build_overview(
    *, accounts: list[Any], live_positions: list[Any],
    evidence_accounts: list[HouseholdEvidenceAccount],
    account_summaries: list[Any],
    inbox: list[Any],
    statement_freshness: dict[str, Any],
    reports: HouseholdReports,
    holdings_by_account: dict[str, float], documents: list[Any],
    questions: list[Any], resolved_values: list[HouseholdResolvedValue],
    service: Any | None = None,
) -> tuple[HouseholdOverview, float, float, float, float]:
    summary_totals = _overview_totals_from_account_summaries(account_summaries)
    if summary_totals is not None:
        (
            invested_assets,
            cash_reserve,
            retirement_assets,
            taxable_assets,
            total_tracked_assets,
            liabilities_total,
        ) = summary_totals
    else:
        invested_assets = sum(holdings_by_account.values())
        cash_reserve = sum(a.cash_balance for a in accounts)
        retirement_assets = 0.0
        taxable_assets = 0.0
        for account in accounts:
            account_total = account.cash_balance + holdings_by_account.get(account.id, 0.0)
            if account.account_type in RETIREMENT_ACCOUNT_TYPES:
                retirement_assets += account_total
            if account.account_type in TAXABLE_ACCOUNT_TYPES:
                taxable_assets += account_total
    evidence_totals = service.evidence_service.totals_by_group(evidence_accounts) if service is not None else {
        "cash": 0.0,
        "retirement": 0.0,
        "taxable": 0.0,
        "education": 0.0,
        "debt": 0.0,
        "credit": 0.0,
        "other": 0.0,
    }
    if cash_reserve <= 0:
        cash_reserve += evidence_totals.get("cash", 0.0)
    if retirement_assets <= 0:
        retirement_fallback = evidence_totals.get("retirement", 0.0)
        retirement_assets += retirement_fallback
        invested_assets += retirement_fallback
    if taxable_assets <= 0:
        taxable_fallback = evidence_totals.get("taxable", 0.0) + evidence_totals.get("education", 0.0)
        taxable_assets += taxable_fallback
        invested_assets += taxable_fallback
    if invested_assets <= 0:
        invested_assets += evidence_totals.get("other", 0.0)
    if summary_totals is None:
        total_tracked_assets = invested_assets + cash_reserve
        liabilities_total = evidence_totals.get("debt", 0.0) + evidence_totals.get("credit", 0.0)
    net_worth = total_tracked_assets - liabilities_total
    rnv = lambda field: resolved_numeric_value(resolved_values, field)  # noqa: E731
    effective_account_count = len(account_summaries) or len(accounts) or len(evidence_accounts)
    effective_position_count = len(live_positions) or (
        service.evidence_service.investment_like_count(evidence_accounts) if service is not None else 0
    )
    visibility_score = _apply_account_freshness_visibility_cap(
        _call_service_override(
            service,
            "_compute_visibility_score",
            compute_visibility_score,
            account_count=effective_account_count,
            position_count=effective_position_count,
            cash_reserve=cash_reserve,
            retirement_assets=retirement_assets,
            taxable_assets=taxable_assets,
            resolved_numeric_value=rnv,
            document_count=len(documents),
        ),
        account_summaries,
    )
    needs_refresh_count = sum(
        1
        for account in account_summaries
        if account.freshness_status in _DEGRADED_ACCOUNT_FRESHNESS_STATUSES
    )
    latest_report_transaction = max((txn.date for txn in reports.recent_transactions), default=None)
    last_transaction_date = latest_report_transaction or (
        str(statement_freshness.get("most_recent_date")) if statement_freshness.get("most_recent_date") else None
    )
    net_worth_status, net_worth_detail = _net_worth_trust(account_summaries)
    monthly_spend_status, monthly_spend_detail = _monthly_spend_trust(
        account_summaries,
        statement_freshness,
    )
    overview = HouseholdOverview(
        invested_assets=invested_assets, retirement_assets=retirement_assets,
        taxable_assets=taxable_assets, cash_reserve=cash_reserve,
        total_tracked_assets=total_tracked_assets, liabilities_total=liabilities_total,
        net_worth=net_worth,
        net_worth_status=net_worth_status,
        net_worth_detail=net_worth_detail,
        tracked_account_count=len(account_summaries),
        needs_refresh_count=needs_refresh_count,
        candidate_account_count=sum(1 for account in account_summaries if account.match_status == "candidate"),
        gap_count=sum(len(account.gap_flags) for account in account_summaries),
        inbox_count=len(inbox),
        coverage_months=max(
            int(statement_freshness.get("coverage_months") or 0),
            reports.executive.coverage_months,
        ),
        last_transaction_date=last_transaction_date,
        visibility_score=visibility_score,
        visibility_label=_call_service_override(service, "_visibility_label", visibility_label, visibility_score),
        monthly_spend_status=monthly_spend_status,
        monthly_spend_detail=monthly_spend_detail,
        next_best_action=_call_service_override(
            service,
            "_next_best_action",
            next_best_action,
            documents,
            visibility_score,
            questions=[q.question for q in questions],
            resolved_numeric_value=rnv,
        ),
    )
    return overview, retirement_assets, taxable_assets, cash_reserve, total_tracked_assets


def build_budget_readiness(
    *, resolved_values: list[HouseholdResolvedValue], documents: list[Any], service: Any | None = None
) -> BudgetReadiness:
    rnv = lambda field: resolved_numeric_value(resolved_values, field)  # noqa: E731
    budget_inputs = _call_service_override(service, "_budget_input_status", budget_input_status, rnv, documents)
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
    *, resolved_values: list[HouseholdResolvedValue], documents: list[Any],
    retirement_assets: float, taxable_assets: float, cash_reserve: float, total_tracked_assets: float,
    service: Any | None = None,
) -> RetirementPreparedness:
    retirement_share = (retirement_assets / total_tracked_assets) * 100 if total_tracked_assets > 0 else 0.0
    rnv = lambda field: resolved_numeric_value(resolved_values, field)  # noqa: E731
    ready = _call_service_override(service, "_retirement_ready", retirement_ready, rnv, documents)
    return RetirementPreparedness(
        status="scenario_ready" if ready else "baseline_visible",
        summary=(
            "Retirement planning can move from rough intuition to defensible scenario planning."
            if ready
            else "Retirement assets are visible, but retirement readiness still depends on real spending and future-income assumptions."
        ),
        retirement_account_share=retirement_share,
        strengths=_call_service_override(
            service,
            "_retirement_strengths",
            retirement_strengths,
            retirement_assets,
            taxable_assets,
            cash_reserve,
            rnv,
        ),
        blockers=_call_service_override(service, "_retirement_blockers", retirement_blockers, rnv, documents),
        next_steps=_call_service_override(service, "_retirement_next_steps", retirement_next_steps, rnv, documents),
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
    registry_service = getattr(service, "account_registry_service", None)
    sync_gate = getattr(service, "_ensure_dashboard_registry_sync", None)
    if callable(sync_gate):
        sync_gate(limit=1000)
    elif registry_service is not None:
        registry_service.sync_registry(service, limit=1000)
    profile = service.get_profile()
    planning = service.get_planning_snapshot()
    documents = service.list_documents(limit=100).items
    evidence_accounts = service.list_evidence_accounts(limit=1000, dedupe=False)
    tracked_accounts = service.list_tracked_accounts(limit=100)
    questions = service.list_questions(limit=25).items
    accounts = [a for a in service.portfolio_mgr.get_accounts() if a.account_type != "paper"]
    positions = service.portfolio_mgr.get_positions()
    account_ids = {a.id for a in accounts}
    live_positions = [p for p in positions if p.account_id in account_ids]
    symbols = sorted({p.symbol for p in live_positions})
    price_data = cast(dict[str, object], service.price_fetcher.fetch_cached_price_data(symbols)) if symbols else {}
    account_valuations = calculate_account_valuations(
        accounts,
        live_positions,
        cast(dict[str, Any], price_data),
    )
    holdings_by_account: dict[str, float] = {
        account_id: valuation.priced_positions_value
        for account_id, valuation in account_valuations.items()
        if valuation.priced_positions_value > 0
    }
    reports = service.transaction_service.build_reports()
    return {
        "profile": profile, "planning": planning, "documents": documents, "questions": questions,
        "evidence_accounts": evidence_accounts,
        "tracked_accounts": tracked_accounts,
        "accounts": accounts, "live_positions": live_positions,
        "account_valuations": account_valuations,
        "holdings_by_account": holdings_by_account, "reports": reports,
    }


def resolve_dashboard_values(service: Any, *, profile: Any, reports: Any, questions: list[Any]) -> tuple[list[Any], list[Any]]:
    infer_profile_from_transactions(service.storage, profile=profile, reports=reports, existing_inferences=fetch_inferred_value_rows(service.storage))
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
    transaction_date_issues: list[Any],
    account_summaries: list[Any], discovered_accounts: list[Any], inbox: list[Any],
) -> HouseholdFinanceDashboard:
    profile, reports, documents, planning = d["profile"], d["reports"], d["documents"], d["planning"]
    return HouseholdFinanceDashboard(
        generated_at=datetime.now(UTC).isoformat(),
        overview=overview, profile=profile, resolved_values=resolved_values,
        budget_readiness=build_budget_readiness(
            resolved_values=resolved_values,
            documents=documents,
            service=service,
        ),
        budget_snapshot=build_budget_snapshot(
            profile=profile,
            reports=reports,
            month_to_date_spend=fetch_current_month_spend(service.storage),
        ),
        retirement_preparedness=build_retirement_preparedness(
            resolved_values=resolved_values, documents=documents,
            retirement_assets=retirement_assets, taxable_assets=taxable_assets,
            cash_reserve=cash_reserve, total_tracked_assets=total_tracked_assets,
            service=service,
        ),
        jenny_needs=jenny_needs, reports=reports,
        categorization_queue=categorization_queue, recurring_commitments=recurring_commitments,
        transaction_date_issues=transaction_date_issues,
        sinking_funds=build_sinking_funds(recurring_commitments=recurring_commitments),
        retirement_contribution_tracker=build_retirement_contribution_tracker(
            profile=profile, estimated_monthly_contributions=fetch_monthly_retirement_contributions(service.storage),
        ),
        retirement_scenarios=build_retirement_scenarios(
            retirement_assets=retirement_assets, target_retirement_spend=profile.target_retirement_spend,
            baseline_monthly_spend=reports.executive.average_monthly_spend,
        ),
        import_center=build_import_center(documents, planning),
        evidence_accounts=d["evidence_accounts"],
        accounts=account_summaries,
        discovered_accounts=discovered_accounts,
        inbox=inbox,
        questions=visible_questions,
        jenny_brief=build_jenny_brief(profile, reports, resolved_values),
        portfolio_context=build_portfolio_context(
            total_tracked_assets=total_tracked_assets, cash_reserve=cash_reserve,
            profile=profile, reports=reports,
        ),
        planning=planning,
    )
