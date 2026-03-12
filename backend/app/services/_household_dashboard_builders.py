"""Pure builder functions for household dashboard sections (no DB access)."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta

from dateutil.relativedelta import relativedelta

from app.models.household_finance import (
    HouseholdBudgetSnapshot,
    HouseholdProfile,
    HouseholdRecurringCommitment,
    HouseholdReports,
    HouseholdRetirementContributionTracker,
    HouseholdRetirementScenario,
    HouseholdSinkingFund,
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


def _commitment_due_status(days_until_due: int | None) -> str:
    if days_until_due is None:
        return "unknown"
    if days_until_due < 0:
        return "overdue"
    if days_until_due <= 3:
        return "due_soon"
    return "upcoming"


def build_recurring_commitment(
    row: object,
    cadence: str,
    cadence_info: dict[str, object],
    today: object,
) -> HouseholdRecurringCommitment | None:
    """Build a single recurring commitment from a DB row, or return None to skip."""
    if cadence not in _RECURRING_CADENCES:
        return None
    row_seq = row  # type: ignore[assignment]
    average_amount = float(row_seq[2] or 0.0)  # type: ignore[index]
    last_seen = row_seq[4]  # type: ignore[index]
    if last_seen is None:
        return None
    merchant = str(row_seq[0])  # type: ignore[index]
    annualized_cost = average_amount * _CADENCE_MULTIPLIERS.get(cadence, 12)
    commitment_type = (
        "subscription" if str(row_seq[1]).lower() in _SUBSCRIPTION_CATEGORIES else "bill"  # type: ignore[index]
    )
    next_expected = estimate_next_commitment_date(last_seen, cadence)
    next_expected_date = (
        datetime.fromisoformat(next_expected).date() if next_expected is not None else None
    )
    days_until_due = (
        (next_expected_date - today).days  # type: ignore[operator]
        if next_expected_date is not None
        else None
    )
    return HouseholdRecurringCommitment(
        merchant=merchant,
        category=str(row_seq[1]),  # type: ignore[index]
        cadence=cadence,
        average_amount=round(average_amount, 2),
        annualized_cost=round(annualized_cost, 2),
        last_seen=last_seen.isoformat(),
        next_expected=next_expected,
        days_until_due=days_until_due,
        due_status=_commitment_due_status(days_until_due),
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
    profile: HouseholdProfile,
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


def _retirement_readiness(funded_years: float) -> str:
    if funded_years >= 25:
        return "strong"
    if funded_years >= 15:
        return "developing"
    return "short"


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
            readiness=_retirement_readiness(
                retirement_assets / (monthly_spend * 12) if monthly_spend > 0 else 0.0
            ),
            detail="A plain-language spend scenario using currently visible retirement assets.",
        )
        for name, monthly_spend in scenario_inputs
    ]


def _budget_pace(
    month_to_date_spend: float,
    month_to_date_plan: float,
) -> tuple[str, str]:
    pace_delta = month_to_date_spend - month_to_date_plan
    tolerance = max(month_to_date_plan * 0.05, 100)
    if abs(pace_delta) <= tolerance:
        return "on_track", "Month-to-date spend is tracking close to the plan."
    if pace_delta > 0:
        return "running_hot", (
            f"Month-to-date spend is ahead of plan by ${pace_delta:,.0f}. "
            "Review discretionary and recurring categories before the month hardens."
        )
    return "under_plan", (
        f"Month-to-date spend is ${abs(pace_delta):,.0f} below plan. "
        "The plan still has room for remaining bills and savings."
    )


def _budget_status(profile: HouseholdProfile, reports: HouseholdReports) -> tuple[str, str]:
    if (
        profile.monthly_essential_target is not None
        and reports.executive.average_monthly_essentials > profile.monthly_essential_target
    ):
        return "essentials_above_plan", "Essential spending is running above the current target and needs review."
    if (
        profile.monthly_discretionary_target is not None
        and reports.executive.average_monthly_discretionary > profile.monthly_discretionary_target
    ):
        return "discretionary_above_plan", "Discretionary spending is running above the current cap."
    return "on_track", "The current monthly spending profile is inside the available budget guardrails."


def _budget_analysis(
    *,
    has_plan: bool,
    monthly_plan_total: float,
    month_to_date_spend: float,
    profile: HouseholdProfile,
    reports: HouseholdReports,
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
    pace_status, pace_detail = _budget_pace(month_to_date_spend, month_to_date_plan)
    status, summary = _budget_status(profile, reports)
    return month_to_date_plan, pace_status, pace_detail, status, summary


def build_budget_snapshot(
    *,
    profile: HouseholdProfile,
    reports: HouseholdReports,
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
