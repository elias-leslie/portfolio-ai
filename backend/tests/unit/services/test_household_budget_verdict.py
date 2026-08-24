"""The month's verdict, and the per-category over/under it nets out of.

D2's first two acceptance sentences: "we're under budget overall", and
"overspent on groceries but underspent on gas and overall we're under". Both
are one subtraction, and both have to be answerable from the payload rather
than assembled by whichever screen is asking.
"""

from __future__ import annotations

from app.models.household_finance import HouseholdSpendingCategory
from app.services.household_finance_service import _budget_verdict


def _category(
    name: str,
    *,
    spend: float,
    cap: float | None = None,
    disabled: bool = False,
) -> HouseholdSpendingCategory:
    return HouseholdSpendingCategory(
        category=name,
        essentiality="mixed",
        total_spend=spend,
        average_monthly_spend=spend,
        share_of_spend=0.0,
        transaction_count=1,
        confirmed_monthly_budget=cap,
        budget_disabled=disabled,
    )


def test_over_on_one_category_and_under_on_another_nets_to_one_answer() -> None:
    verdict = _budget_verdict(
        [
            _category("Groceries", spend=1200.0, cap=1000.0),
            _category("Gas", spend=150.0, cap=400.0),
        ],
        month_label="June 2026",
    )

    assert verdict.over_total == 200.0
    assert verdict.under_total == 250.0
    assert verdict.variance == -50.0
    assert verdict.status == "under_plan"
    assert "$50 under your caps" in verdict.headline
    assert "1 over by $200" in verdict.detail
    assert "1 under by $250" in verdict.detail


def test_the_verdict_names_the_category_that_drove_it() -> None:
    verdict = _budget_verdict(
        [
            _category("Household", spend=3000.0, cap=1000.0),
            _category("Dining", spend=120.0, cap=100.0),
        ],
        month_label="June 2026",
    )

    assert verdict.status == "over_plan"
    assert verdict.largest_over_category == "Household"
    assert verdict.largest_over_amount == 2000.0
    assert "most of it Household" in verdict.detail


def test_a_month_mostly_outside_the_plan_gets_no_overall_verdict() -> None:
    """A verdict about a quarter of the money is not a verdict about the month."""
    verdict = _budget_verdict(
        [
            _category("Groceries", spend=800.0, cap=1000.0),
            _category("Household", spend=9000.0),
        ],
        month_label="July 2026",
    )

    assert verdict.status == "plan_incomplete"
    assert verdict.uncapped_spend == 9000.0
    assert verdict.uncapped_category_count == 1
    assert "no overall verdict yet" in verdict.headline
    # The capped part is still reported -- refusing the headline is not a
    # reason to withhold the arithmetic that is available.
    assert verdict.under_total == 200.0


def test_no_caps_at_all_says_so_instead_of_reporting_a_perfect_month() -> None:
    verdict = _budget_verdict(
        [_category("Household", spend=9000.0)],
        month_label="July 2026",
    )

    assert verdict.status == "no_plan"
    assert verdict.cap_total == 0.0
    assert "nothing to be judged against" in verdict.headline


def test_a_disabled_category_is_neither_capped_nor_counted_as_unjudged() -> None:
    verdict = _budget_verdict(
        [
            _category("Groceries", spend=800.0, cap=1000.0),
            _category("Reimbursed", spend=5000.0, disabled=True),
        ],
        month_label="July 2026",
    )

    assert verdict.status == "under_plan"
    assert verdict.uncapped_spend == 0.0
    assert verdict.capped_actual == 800.0


def test_suggested_caps_never_become_the_verdict() -> None:
    """A cap drawn from the household's own spending cannot grade it."""
    category = _category("Household", spend=9000.0)
    category = category.model_copy(update={"found_monthly_budget": 8500.0})

    verdict = _budget_verdict([category], month_label="July 2026")

    assert verdict.status == "no_plan"
    assert verdict.cap_total == 0.0
