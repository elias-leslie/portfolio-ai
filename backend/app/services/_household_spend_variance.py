"""Why this month differs from the last one, and what is left once the outlier goes.

"We were over budget because of this one purchase but everything else was under"
is D2's third sentence, and a month total cannot say it: $16,708 against $13,704
reads as a household that overspent by $3,004, when in fact it bought an air
conditioner and spent less than usual on everything else.

Two things answer it. **Contribution to variance** attributes the change to the
categories that actually moved it, so the reader sees which lines are the story
and which are noise. **Setting the one-time purchases aside** re-runs the same
comparison without them -- on both sides, because a comparator month with its own
outlier would otherwise flatter the reported month for free.

Nothing here decides what a one-time purchase is; that stays with
`find_one_time_purchases`, which is deliberately conservative about it.
"""

from __future__ import annotations

from typing import Any

from app.models.household_finance import (
    HouseholdSpendVariance,
    HouseholdVarianceDriver,
)

# Categories moving less than this are not the story, and listing them buries the
# ones that are. They stay in every total; they are simply not named.
MIN_DRIVER_CONTRIBUTION = 25.0

# At most this many named movers. A "what changed" list that runs to twenty rows
# is the category table again, which the reader already has.
MAX_DRIVERS = 6


def _money(value: float) -> str:
    return f"${abs(value):,.0f}"


def _signed_amount(row: dict[str, Any]) -> float:
    return float(row.get("signed_amount", row.get("amount", 0.0)) or 0.0)


def _totals_by_category(rows: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        category = str(row.get("category") or "Uncategorized")
        totals[category] = totals.get(category, 0.0) + _signed_amount(row)
    return totals


def _largest_row_by_category(
    rows: list[dict[str, Any]],
) -> dict[str, tuple[str, float]]:
    largest: dict[str, tuple[str, float]] = {}
    for row in rows:
        category = str(row.get("category") or "Uncategorized")
        amount = _signed_amount(row)
        if amount <= 0:
            continue
        current = largest.get(category)
        if current is None or amount > current[1]:
            merchant = str(row.get("merchant") or "").strip() or "Unknown merchant"
            largest[category] = (merchant, round(amount, 2))
    return largest


def build_spend_variance(
    *,
    month_label_text: str,
    comparator_key: str,
    comparator_label: str,
    month_rows: list[dict[str, Any]],
    comparator_rows: list[dict[str, Any]],
    month_one_time_ids: set[str],
    comparator_one_time_ids: set[str],
    set_aside_label: str | None = None,
) -> HouseholdSpendVariance:
    """Attribute the change between two months, with and without the outliers."""
    month_spend = round(sum(_signed_amount(row) for row in month_rows), 2)
    comparator_spend = round(sum(_signed_amount(row) for row in comparator_rows), 2)
    change = round(month_spend - comparator_spend, 2)

    month_everyday_rows = [
        row for row in month_rows if str(row.get("id")) not in month_one_time_ids
    ]
    comparator_everyday_rows = [
        row
        for row in comparator_rows
        if str(row.get("id")) not in comparator_one_time_ids
    ]
    everyday_month = round(sum(_signed_amount(r) for r in month_everyday_rows), 2)
    everyday_comparator = round(
        sum(_signed_amount(r) for r in comparator_everyday_rows), 2
    )
    everyday_change = round(everyday_month - everyday_comparator, 2)

    # Drivers are measured on the everyday rows. A category whose whole movement
    # is one set-aside purchase is not a category that changed its behaviour, and
    # naming it as a driver would contradict the line directly above it.
    month_totals = _totals_by_category(month_everyday_rows)
    comparator_totals = _totals_by_category(comparator_everyday_rows)
    largest_by_category = _largest_row_by_category(month_everyday_rows)

    drivers: list[HouseholdVarianceDriver] = []
    for category in set(month_totals) | set(comparator_totals):
        this_month = round(month_totals.get(category, 0.0), 2)
        that_month = round(comparator_totals.get(category, 0.0), 2)
        contribution = round(this_month - that_month, 2)
        if abs(contribution) < MIN_DRIVER_CONTRIBUTION:
            continue
        largest = largest_by_category.get(category)
        drivers.append(
            HouseholdVarianceDriver(
                category=category,
                month_spend=this_month,
                comparator_spend=that_month,
                contribution=contribution,
                # Divided by the *magnitude* of the change so the sign tracks the
                # money. Dividing by a signed total makes a category that spent
                # $5,157 less read as "+60%" in a month that fell, which is the
                # opposite of what the reader takes from it.
                share_of_change=(
                    round(contribution / abs(everyday_change), 4)
                    if everyday_change
                    else 0.0
                ),
                largest_purchase_merchant=largest[0] if largest else None,
                largest_purchase_amount=largest[1] if largest else 0.0,
            )
        )
    drivers.sort(key=lambda driver: abs(driver.contribution), reverse=True)
    drivers = drivers[:MAX_DRIVERS]

    one_time_month = round(month_spend - everyday_month, 2)
    one_time_comparator = round(comparator_spend - everyday_comparator, 2)

    direction = "more" if change > 0 else "less"
    headline = (
        f"{month_label_text} spent {_money(change)} {direction} than "
        f"{comparator_label}."
    )
    if abs(change) < 1:
        headline = f"{month_label_text} spent about the same as {comparator_label}."

    if one_time_month or one_time_comparator:
        everyday_direction = "more" if everyday_change > 0 else "less"
        set_aside_text = (
            f" ({set_aside_label})" if set_aside_label else ""
        )
        detail = (
            f"Set the one-time purchases aside{set_aside_text} — "
            f"{_money(one_time_month)} this month against "
            f"{_money(one_time_comparator)} then — and everyday spending was "
            f"{_money(everyday_change)} {everyday_direction}."
        )
    elif drivers:
        leader = drivers[0]
        detail = (
            f"No one-time purchase either month. The biggest mover is "
            f"{leader.category}, {_money(leader.contribution)} "
            f"{'more' if leader.contribution > 0 else 'less'}."
        )
    else:
        detail = "No category moved enough to explain the difference on its own."

    return HouseholdSpendVariance(
        comparator_key=comparator_key,
        comparator_label=comparator_label,
        month_spend=month_spend,
        comparator_spend=comparator_spend,
        change=change,
        change_pct=(
            round(change / comparator_spend, 4) if comparator_spend > 0 else None
        ),
        headline=headline,
        detail=detail,
        everyday_month_spend=everyday_month,
        everyday_comparator_spend=everyday_comparator,
        everyday_change=everyday_change,
        one_time_month_spend=one_time_month,
        one_time_comparator_spend=one_time_comparator,
        drivers=drivers,
    )
