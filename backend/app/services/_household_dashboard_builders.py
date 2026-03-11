"""Pure builder functions for household dashboard sections (no DB access)."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta
from typing import Any

from app.models.household_finance import (
    BudgetLane,
    BudgetReadiness,
    HouseholdActionItem,
    HouseholdBudgetSnapshot,
    HouseholdCategorizationCandidate,
    HouseholdRecurringCommitment,
    HouseholdRetirementContributionTracker,
    HouseholdRetirementScenario,
    HouseholdSinkingFund,
)

_PRIORITY_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}

_CADENCE_MULTIPLIERS: dict[str, int] = {
    "weekly": 52,
    "biweekly": 26,
    "monthly": 12,
    "quarterly": 4,
}

_CADENCE_OFFSETS: dict[str, timedelta] = {
    "weekly": timedelta(days=7),
    "biweekly": timedelta(days=14),
    "monthly": timedelta(days=30),
    "quarterly": timedelta(days=90),
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
    return HouseholdRecurringCommitment(
        merchant=merchant,
        category=str(row[1]),
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


def _pace_info(
    *, has_plan: bool, monthly_plan_total: float, month_to_date_spend: float
) -> tuple[float | None, str, str]:
    if not has_plan:
        return None, "unknown", "Jenny needs a monthly plan before it can judge pacing."
    today = datetime.now(UTC).date()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    month_progress = today.day / days_in_month
    month_to_date_plan = round(monthly_plan_total * month_progress, 2)
    pace_delta = month_to_date_spend - month_to_date_plan
    tolerance = max(month_to_date_plan * 0.05, 100)
    if abs(pace_delta) <= tolerance:
        return month_to_date_plan, "on_track", "Month-to-date spend is tracking close to the plan."
    if pace_delta > 0:
        detail = (
            f"Month-to-date spend is ahead of plan by ${pace_delta:,.0f}. "
            "Review discretionary and recurring categories before the month hardens."
        )
        return month_to_date_plan, "running_hot", detail
    detail = (
        f"Month-to-date spend is ${abs(pace_delta):,.0f} below plan. "
        "The plan still has room for remaining bills and savings."
    )
    return month_to_date_plan, "under_plan", detail


def _snapshot_status(*, has_plan: bool, profile: Any, reports: Any) -> tuple[str, str]:
    if not has_plan:
        return (
            "setup_needed",
            "Set the core monthly plan so Jenny can judge whether current spending is on pace.",
        )
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
    month_to_date_plan, pace_status, pace_detail = _pace_info(
        has_plan=has_plan,
        monthly_plan_total=monthly_plan_total,
        month_to_date_spend=month_to_date_spend,
    )
    status, summary = _snapshot_status(has_plan=has_plan, profile=profile, reports=reports)
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


def _action_items_from_questions(questions: list[Any]) -> list[HouseholdActionItem]:
    return [
        HouseholdActionItem(
            title="Answer Jenny follow-up",
            detail=question.question,
            action_label="Answer in Money System",
            href="/money",
            priority=question.priority,
            source="question",
        )
        for question in questions[:3]
    ]


def _action_items_from_budget(budget_readiness: BudgetReadiness) -> list[HouseholdActionItem]:
    return [
        HouseholdActionItem(
            title="Finish the monthly plan",
            detail=missing_input,
            action_label="Update plan",
            href="/money",
            priority="high",
            source="budget_readiness",
        )
        for missing_input in budget_readiness.missing_inputs[:2]
    ]


def _action_items_from_opportunities(opportunities: list[Any]) -> list[HouseholdActionItem]:
    return [
        HouseholdActionItem(
            title=opportunity.title,
            detail=opportunity.detail,
            action_label="Review in Money System",
            href="/money",
            priority="medium",
            source=opportunity.category,
        )
        for opportunity in opportunities[:2]
    ]


def build_action_items(
    *,
    questions: list[Any],
    opportunities: list[Any],
    next_best_action: str,
    reports: Any,
    budget_readiness: BudgetReadiness,
    categorization_queue: list[HouseholdCategorizationCandidate] | None = None,
) -> list[HouseholdActionItem]:
    categorization_queue = categorization_queue or []
    items: list[HouseholdActionItem] = (
        _action_items_from_questions(questions)
        + _action_items_from_budget(budget_readiness)
        + _action_items_from_opportunities(opportunities)
    )

    if reports.executive.tracked_expense_count == 0:
        items.append(
            HouseholdActionItem(
                title="Feed the household ledger",
                detail="Upload a recent checking or credit-card statement so the budget view is based on real transactions.",
                action_label="Upload documents",
                href="/money",
                priority="high",
                source="documents",
            )
        )

    if categorization_queue:
        count = len(categorization_queue)
        items.append(
            HouseholdActionItem(
                title="Review uncategorized spending",
                detail=f"{count} transaction{'s' if count != 1 else ''} still need clean categories.",
                action_label="Categorize now",
                href="/money",
                priority="high",
                source="categorization_queue",
            )
        )

    if not items:
        items.append(
            HouseholdActionItem(
                title="Next best household step",
                detail=next_best_action,
                action_label="Open Money System",
                href="/money",
                priority="medium",
                source="overview",
            )
        )

    seen: set[tuple[str, str]] = set()
    deduped: list[HouseholdActionItem] = []
    for item in items:
        key = (item.title, item.detail)
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return sorted(
        deduped,
        key=lambda item: (_PRIORITY_RANK.get(item.priority, 3), item.title),
    )[:6]


def build_starter_lanes(resolved_numeric_value: Any) -> list[BudgetLane]:
    """Build the three starter budget lanes from resolved values."""
    lane_configs = [
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
    return [
        BudgetLane(
            name=name,
            objective=objective,
            status="Configured" if resolved_numeric_value(field) is not None else "Needs target",
        )
        for name, objective, field in lane_configs
    ]
