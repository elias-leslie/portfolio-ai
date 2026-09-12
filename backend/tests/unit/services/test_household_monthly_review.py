"""A declared draw funds a plan without becoming earned income."""

import json

import pytest
from pydantic import ValidationError

from app.models.household_finance import HouseholdProfileUpdate
from app.models.household_finance_types import (
    HouseholdCapPlan,
    HouseholdCapPlanRow,
    HouseholdConfirmedFact,
    HouseholdSpendingSummary,
    HouseholdSpendingView,
)
from app.services.household_monthly_review import build_review_plan, validate_review_fact
from tests.unit.services.test_household_budget_verdict import _category


def test_funding_does_not_double_count_sinking_fund_categories():
    view = HouseholdSpendingView(
        generated_at="2026-09-11",
        summary=HouseholdSpendingSummary(
            month="2026-08",
            month_label="August",
            total_spend=1000,
            average_monthly_spend=1000,
            transaction_count=2,
            coverage_months=1,
            account_count=1,
        ),
        categories=[
            _category("Groceries", spend=900, cap=800),
            _category("Travel", spend=100, cap=500),
        ],
        cap_plan=HouseholdCapPlan(
            anchor_monthly_income=600,
            savings_target=0,
            sinking_fund_total=100,
            card_fee_monthly=50,
            rows=[
                HouseholdCapPlanRow(
                    category="Travel",
                    essentiality="discretionary",
                    source="sinking_fund",
                    proposed_cap=100,
                    trailing_monthly=100,
                    detail="reserve",
                )
            ],
        ),
    )
    first = build_review_plan(view, [])
    assert first.planned_spending == 800
    assert first.additional_commitments == 150
    assert first.funding_balance is None  # absent draw is not an agreed zero
    fact = HouseholdConfirmedFact(
        fact_key="monthly_review:2026-08",
        fact_value=json.dumps({"planned_asset_draw": 350}),
        confirmed_at="2026-09-11",
    )
    agreed = build_review_plan(view, [fact])
    assert agreed.expected_income == 600
    assert agreed.planned_asset_draw == 350
    assert agreed.funding_balance == 0
    view.categories.append(_category("Healthcare", spend=100))
    assert build_review_plan(view, [fact]).funding_balance is None


def test_review_notes_are_bounded_and_unknown_outcomes_stay_unknown():
    saved = json.loads(
        validate_review_fact(
            "monthly_review:2026-09", '{"decisions":[{"action":"Check phone bill"}]}'
        )
    )
    assert saved["decisions"][0]["outcome"] == "not_reviewed"
    for value in [
        '{"planned_asset_draw":-1}',
        '{"expected_income":NaN}',
        '{"decisions":[{"action":"one"},{"action":"two"},{"action":"three"},{"action":"four"}]}',
    ]:
        with pytest.raises(ValueError):
            validate_review_fact("monthly_review:2026-09", value)
    with pytest.raises(ValueError):
        validate_review_fact("monthly_review:2026-13", "{}")


@pytest.mark.parametrize(
    "field,value",
    [
        ("social_security_payable_ratio", 77),
        ("effective_tax_rate", 101),
        ("target_spouse_retirement_age", 49.5),
        ("retirement_horizon_years", 0),
        ("monthly_net_income_target", float("inf")),
    ],
)
def test_invalid_assumption_units_are_rejected_at_the_server(field, value):
    with pytest.raises(ValidationError):
        HouseholdProfileUpdate.model_validate({field: value})
