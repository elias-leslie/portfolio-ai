"""Pure builder functions for household dashboard sections (no DB access)."""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta

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
from app.services._household_recurrence import (
    BILL,
    CADENCE_DAYS,
    CADENCE_FOR_LABEL,
    LAPSED_AFTER_CYCLES,
    SUBSCRIPTION,
    RecurrencePattern,
    commitment_type_for,
)

_CADENCE_MULTIPLIERS: dict[str, int] = {
    "weekly": 52,
    "biweekly": 26,
    "monthly": 12,
    "bimonthly": 6,
    "quarterly": 4,
    "semiannual": 2,
    "annual": 1,
}

_CADENCE_OFFSETS: dict[str, timedelta | relativedelta] = {
    "weekly": timedelta(weeks=1),
    "biweekly": timedelta(weeks=2),
    "monthly": relativedelta(months=1),
    "bimonthly": relativedelta(months=2),
    "quarterly": relativedelta(months=3),
    "semiannual": relativedelta(months=6),
    "annual": relativedelta(years=1),
}

# Annual belongs here even though nothing can infer it from two sightings a year
# apart: it is the cadence a household declares, and leaving it out meant a
# property tax or an HOA due once a year could never become a commitment at all,
# which is precisely the gap that under-funds the sinking fund by a twelfth of
# itself every month.
_RECURRING_CADENCES = set(_CADENCE_MULTIPLIERS)
_CADENCE_LABEL_MAP = CADENCE_FOR_LABEL
# Commitments that are obligations rather than habits. Only these count toward
# what is due soon or gets a sinking fund: a merchant the household merely
# visits on a rhythm owes nothing on a date.
_OBLIGATION_TYPES = {BILL, SUBSCRIPTION}

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


def estimate_next_commitment_date(last_seen: date | datetime, cadence: str) -> str | None:
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
    *,
    merchant: str,
    category: str,
    pattern: RecurrencePattern,
    today: date,
) -> HouseholdRecurringCommitment | None:
    """Turn a proven cadence into a commitment, or return None to skip."""
    if pattern.cadence not in _RECURRING_CADENCES:
        return None
    if (today - pattern.last_seen).days > LAPSED_AFTER_CYCLES * CADENCE_DAYS[pattern.cadence]:
        return None
    annualized_cost = pattern.typical_amount * _CADENCE_MULTIPLIERS[pattern.cadence]
    next_expected = estimate_next_commitment_date(pattern.last_seen, pattern.cadence)
    next_expected_date = (
        datetime.fromisoformat(next_expected).date() if next_expected is not None else None
    )
    days_until_due = (
        (next_expected_date - today).days
        if next_expected_date is not None
        else None
    )
    return HouseholdRecurringCommitment(
        merchant=merchant,
        category=category,
        cadence=pattern.label,
        average_amount=round(pattern.typical_amount, 2),
        annualized_cost=round(annualized_cost, 2),
        last_seen=pattern.last_seen.isoformat(),
        next_expected=next_expected,
        days_until_due=days_until_due,
        due_status=_commitment_due_status(days_until_due),
        due_confidence=pattern.confidence,
        commitment_type=commitment_type_for(category),
        evidence=pattern.evidence,
    )


def build_sinking_funds(
    *, recurring_commitments: list[HouseholdRecurringCommitment]
) -> list[HouseholdSinkingFund]:
    funds: list[HouseholdSinkingFund] = []
    for commitment in recurring_commitments:
        # A sinking fund smooths an obligation the household owes. A merchant it
        # simply visits often is not one, however large the yearly total looks.
        if commitment.commitment_type not in _OBLIGATION_TYPES:
            continue
        normalized_cadence = _CADENCE_LABEL_MAP.get(commitment.cadence, commitment.cadence)
        if normalized_cadence in {"weekly", "biweekly", "monthly"} and commitment.average_amount < 150:
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
    plan_is_partial: bool,
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
    status, summary = _budget_status(profile, reports)
    if plan_is_partial:
        # Total spend cannot be paced against a partial plan without reading as
        # structurally "hot"; surface the partial-plan state instead of a verdict.
        return (
            month_to_date_plan,
            "partial_plan",
            "The current plan only covers part of the month, so total spend is not paced against it yet. Set the remaining targets for a real pace.",
            status,
            summary,
        )
    pace_status, pace_detail = _budget_pace(month_to_date_spend, month_to_date_plan)
    return month_to_date_plan, pace_status, pace_detail, status, summary


def build_budget_snapshot(
    *,
    profile: HouseholdProfile,
    reports: HouseholdReports,
    month_to_date_spend: float,
    cash_reserve: float | None = None,
    recurring_commitments: list[HouseholdRecurringCommitment] | None = None,
) -> HouseholdBudgetSnapshot:
    plan_components = (
        ("essentials", profile.monthly_essential_target),
        ("discretionary", profile.monthly_discretionary_target),
        ("savings", profile.monthly_savings_target),
    )
    plan_values = tuple(value for _, value in plan_components)
    monthly_plan_total = sum(v for v in plan_values if v is not None)
    has_plan = any(v is not None for v in plan_values)
    missing_plan_components = [name for name, value in plan_components if value is None]
    plan_is_partial = has_plan and bool(missing_plan_components)
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
        plan_is_partial=plan_is_partial,
        monthly_plan_total=monthly_plan_total,
        month_to_date_spend=month_to_date_spend,
        profile=profile,
        reports=reports,
    )
    operating_cushion = (
        profile.monthly_essential_target
        if profile.monthly_essential_target is not None
        else reports.executive.average_monthly_essentials
    )
    due_soon_bills_total: float | None = None
    safe_to_spend: float | None = None
    safe_to_spend_constraint: str | None = None
    if cash_reserve is not None and recurring_commitments is not None:
        due_soon_bills_total = round(
            sum(
                commitment.average_amount
                for commitment in recurring_commitments
                if commitment.commitment_type in _OBLIGATION_TYPES
                and commitment.days_until_due is not None
                and commitment.days_until_due <= 14
            ),
            2,
        )
        # min() keeps the first candidate on ties, so the cash path wins
        # ambiguous ties — the most conservative reading for the user.
        candidates: list[tuple[float, str]] = [
            (cash_reserve - operating_cushion - due_soon_bills_total, "cash_after_cushion"),
        ]
        if remaining_cash_after_plan is not None:
            candidates.append((remaining_cash_after_plan, "plan_residual"))
        if discretionary_headroom is not None:
            candidates.append((discretionary_headroom, "discretionary_cap"))
        binding_value, safe_to_spend_constraint = min(candidates, key=lambda item: item[0])
        safe_to_spend = round(max(binding_value, 0.0), 2)
    return HouseholdBudgetSnapshot(
        status=status,
        summary=summary,
        monthly_income_target=profile.monthly_net_income_target,
        monthly_plan_total=monthly_plan_total if has_plan else None,
        monthly_plan_source="household_profile_targets" if has_plan else "none",
        monthly_plan_source_label=(
            "Household profile targets" if has_plan else "No monthly plan"
        ),
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
        plan_is_partial=plan_is_partial,
        missing_plan_components=missing_plan_components,
        remaining_cash_after_plan=remaining_cash_after_plan,
        discretionary_headroom=discretionary_headroom,
        safe_to_spend=safe_to_spend,
        safe_to_spend_constraint=safe_to_spend_constraint,
        due_soon_bills_total=due_soon_bills_total,
        operating_cushion=round(operating_cushion, 2),
    )
