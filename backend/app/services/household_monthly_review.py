"""Funding and agreed changes for one month, reusing canonical inputs and notes."""

from __future__ import annotations

from pydantic import ValidationError

from app.models.household_finance_types import HouseholdConfirmedFact, HouseholdSpendingView
from app.models.household_review import MonthlyReviewPlan, MonthlyReviewRecord
from app.services._household_month_coverage import previous_month
from app.services._household_spend_periods import is_month_key

REVIEW_PREFIX = "monthly_review:"


def validate_review_fact(key: str, value: str) -> str:
    if not key.startswith(REVIEW_PREFIX):
        return value
    if not is_month_key(key.removeprefix(REVIEW_PREFIX)):
        raise ValueError("A monthly review needs a YYYY-MM period.")
    return MonthlyReviewRecord.model_validate_json(value).model_dump_json()


def review_record(
    facts: list[HouseholdConfirmedFact], month: str
) -> tuple[MonthlyReviewRecord, str | None]:
    fact = next((fact for fact in facts if fact.fact_key == REVIEW_PREFIX + month), None)
    if fact:
        try:
            return MonthlyReviewRecord.model_validate_json(fact.fact_value), fact.confirmed_at
        except ValidationError:
            pass
    return MonthlyReviewRecord(), None


def build_review_plan(
    view: HouseholdSpendingView, facts: list[HouseholdConfirmedFact]
) -> MonthlyReviewPlan:
    record, confirmed_at = review_record(facts, view.summary.month)
    prior_month = previous_month(view.summary.month)
    prior_record, prior_at = review_record(facts, prior_month)
    caps = view.cap_plan
    # Sinking-fund categories already have a reserve in commitments. Do not
    # add their whole category cap and their reserve to the same spending plan.
    funded_categories = (
        {row.category for row in caps.rows if row.source == "sinking_fund"} if caps else set()
    )
    ordinary = [
        row
        for row in view.categories
        if row.category not in funded_categories and not row.budget_disabled
    ]
    proposed_spending = round(sum(row.confirmed_monthly_budget or 0.0 for row in ordinary), 2)
    missing = [
        row.category
        for row in ordinary
        if row.confirmed_monthly_budget is None and row.total_spend > 0
    ]
    income = (
        record.expected_income
        if record.expected_income is not None
        else caps.anchor_monthly_income
        if caps
        else None
    )
    spend = (
        record.planned_spending
        if record.planned_spending is not None
        else proposed_spending if any(row.confirmed_monthly_budget is not None for row in ordinary) else None
    )
    commitments = (
        record.additional_commitments
        if record.additional_commitments is not None
        else round(caps.savings_target + caps.sinking_fund_total + caps.card_fee_monthly, 2)
        if caps
        else None
    )
    known = (
        income is not None
        and record.planned_asset_draw is not None
        and spend is not None
        and commitments is not None
    )
    complete = not missing or record.planned_spending is not None
    balance = (
        round(income + record.planned_asset_draw - spend - commitments, 2)
        if known and complete
        else None
    )
    return MonthlyReviewPlan(
        month=view.summary.month,
        record=record,
        confirmed_at=confirmed_at,
        previous_month=prior_month if prior_at else None,
        previous_record=prior_record if prior_at else None,
        expected_income=income,
        income_source="Agreed for this month"
        if record.expected_income is not None
        else "Income anchor: declared override or median of the last three complete months",
        planned_asset_draw=record.planned_asset_draw,
        planned_spending=spend,
        additional_commitments=commitments,
        funding_balance=balance,
        unplanned_categories=missing if record.planned_spending is None else [],
        detail="Planned cash or portfolio withdrawals are funding, not earned income. The proposed spending amount uses ordinary category caps; saving, sinking-fund reserves and annual card-fee reserves sit in commitments. Adjust commitments if a reserve is already included in your chosen spending amount. These are monthly planning amounts, not another total of this month's transactions.",
    )
