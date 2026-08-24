"""Attributing a month's change, and what survives setting the outlier aside.

D2's third sentence: "we were over budget because of this one purchase but
everything else was under". A month total says the opposite of that sentence,
so both readings have to be published.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services._household_spend_variance import build_spend_variance


def _row(
    row_id: str,
    *,
    category: str,
    amount: float,
    merchant: str = "Somewhere",
    day: int = 5,
) -> dict[str, Any]:
    return {
        "id": row_id,
        "date": date(2026, 7, day),
        "category": category,
        "merchant": merchant,
        "amount": amount,
        "signed_amount": amount,
    }


def _variance(month_rows, comparator_rows, *, month_one_time=(), comparator_one_time=()):
    return build_spend_variance(
        month_label_text="July 2026",
        comparator_key="prior_month",
        comparator_label="June 2026",
        month_rows=list(month_rows),
        comparator_rows=list(comparator_rows),
        month_one_time_ids=set(month_one_time),
        comparator_one_time_ids=set(comparator_one_time),
    )


def test_the_month_rose_and_everyday_spending_fell_are_both_reported() -> None:
    variance = _variance(
        [
            _row("ac", category="Household", amount=11633.0, merchant="Costco"),
            _row("food", category="Groceries", amount=700.0),
        ],
        [_row("food-june", category="Groceries", amount=1500.0)],
        month_one_time=["ac"],
    )

    assert variance.change == 10833.0
    assert variance.everyday_change == -800.0
    assert "spent $10,833 more" in variance.headline
    assert "$800 less" in variance.detail


def test_the_comparator_month_gets_its_outlier_removed_too() -> None:
    """Otherwise a comparator carrying its own outlier flatters this month free."""
    variance = _variance(
        [_row("food", category="Groceries", amount=900.0)],
        [
            _row("roof", category="Home", amount=9000.0, merchant="Roofer"),
            _row("food-june", category="Groceries", amount=1000.0),
        ],
        comparator_one_time=["roof"],
    )

    assert variance.change == -9100.0
    assert variance.everyday_change == -100.0
    assert variance.one_time_comparator_spend == 9000.0


def test_a_category_that_only_moved_because_of_the_outlier_is_not_a_driver() -> None:
    variance = _variance(
        [
            _row("ac", category="Household", amount=11633.0, merchant="Costco"),
            _row("food", category="Groceries", amount=700.0),
        ],
        [_row("food-june", category="Groceries", amount=1500.0)],
        month_one_time=["ac"],
    )

    assert [driver.category for driver in variance.drivers] == ["Groceries"]


def test_a_driver_reads_in_the_direction_its_money_moved() -> None:
    """Dividing by a signed total made a category that fell read as +60%."""
    variance = _variance(
        [
            _row("travel", category="Travel", amount=100.0),
            _row("food", category="Groceries", amount=400.0),
        ],
        [
            _row("travel-june", category="Travel", amount=1100.0),
            _row("food-june", category="Groceries", amount=400.0),
        ],
    )

    (driver,) = variance.drivers
    assert driver.category == "Travel"
    assert driver.contribution == -1000.0
    assert driver.share_of_change == -1.0


def test_small_movers_stay_in_the_totals_but_out_of_the_story() -> None:
    variance = _variance(
        [
            _row("food", category="Groceries", amount=1000.0),
            _row("coffee", category="Dining", amount=105.0),
        ],
        [
            _row("food-june", category="Groceries", amount=500.0),
            _row("coffee-june", category="Dining", amount=100.0),
        ],
    )

    assert variance.change == 505.0
    assert [driver.category for driver in variance.drivers] == ["Groceries"]


def test_a_month_with_no_outlier_either_side_names_its_biggest_mover() -> None:
    variance = _variance(
        [_row("travel", category="Travel", amount=6000.0, merchant="Lufthansa")],
        [_row("travel-june", category="Travel", amount=500.0)],
    )

    assert "No one-time purchase either month" in variance.detail
    assert "Travel" in variance.detail
    assert variance.drivers[0].largest_purchase_merchant == "Lufthansa"
