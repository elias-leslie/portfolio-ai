"""Caps are priced from income and only shaped by history (D6)."""

from __future__ import annotations

from app.models.household_finance import (
    HouseholdCardCommitment,
    HouseholdCardCommitments,
    HouseholdIncomeAnchor,
    HouseholdSavingsPlan,
    HouseholdSinkingFund,
    HouseholdSpendingCategory,
)
from app.services._household_dashboard_builders import build_cap_plan


def _category(name: str, *, essentiality: str, monthly: float) -> HouseholdSpendingCategory:
    return HouseholdSpendingCategory(
        category=name,
        essentiality=essentiality,
        total_spend=monthly,
        average_monthly_spend=monthly,
        share_of_spend=0.0,
        transaction_count=1,
        gross_monthly_spend=monthly,
    )


def _anchor(income: float | None) -> HouseholdIncomeAnchor:
    return HouseholdIncomeAnchor(status="measured", monthly_income=income)


def _savings(target: float | None, status: str = "active") -> HouseholdSavingsPlan:
    return HouseholdSavingsPlan(status=status, monthly_target=target)


def _fund(key: str, label: str, target: float | None) -> HouseholdSinkingFund:
    return HouseholdSinkingFund(key=key, label=label, monthly_target=target)


CATEGORIES = [
    _category("Groceries", essentiality="essential", monthly=1600.0),
    _category("Household", essentiality="mixed", monthly=2400.0),
    _category("Retail", essentiality="discretionary", monthly=800.0),
    _category("Travel", essentiality="discretionary", monthly=1400.0),
]
FUNDS = [
    _fund("travel", "Travel", 800.0),
    _fund("gifts_holidays", "Gifts & holidays", None),
]


def _card_fees(monthly: float, yearly: float, count: int = 2) -> HouseholdCardCommitments:
    return HouseholdCardCommitments(
        status="committed",
        annual_fee_monthly=monthly,
        annual_fee_yearly=yearly,
        cards=[
            HouseholdCardCommitment(
                card_id=f"card-{index}",
                product_name="Chase Sapphire Preferred",
                annual_fee=yearly / count,
            )
            for index in range(count)
        ],
    )


def test_the_total_comes_from_income_before_history_touches_it() -> None:
    plan = build_cap_plan(
        categories=CATEGORIES,
        anchor=_anchor(6000.0),
        savings_plan=_savings(500.0),
        sinking_funds=FUNDS,
    )

    assert plan.status == "proposed"
    assert plan.available_for_categories == 4700.0
    assert plan.essentials_total == 1600.0
    assert plan.discretionary_pool == 3100.0


def test_essentials_are_held_at_cost_rather_than_trimmed() -> None:
    """A groceries cap the household cannot live on is not a plan."""
    plan = build_cap_plan(
        categories=CATEGORIES,
        anchor=_anchor(6000.0),
        savings_plan=_savings(500.0),
        sinking_funds=FUNDS,
    )
    groceries = next(row for row in plan.rows if row.category == "Groceries")

    assert groceries.source == "essential"
    assert groceries.proposed_cap == 1600.0
    assert groceries.change_from_trailing == 0.0


def test_the_pool_is_split_by_what_the_household_actually_spends() -> None:
    plan = build_cap_plan(
        categories=CATEGORIES,
        anchor=_anchor(6000.0),
        savings_plan=_savings(500.0),
        sinking_funds=FUNDS,
    )
    household = next(row for row in plan.rows if row.category == "Household")
    retail = next(row for row in plan.rows if row.category == "Retail")

    assert household.share == 0.75
    assert household.proposed_cap == 2325.0
    assert retail.proposed_cap == 775.0
    assert round(household.proposed_cap + retail.proposed_cap, 2) == 3100.0


def test_a_funded_category_is_capped_by_its_fund_not_the_pool() -> None:
    """Otherwise the same dollar funds a buffer and a cap."""
    plan = build_cap_plan(
        categories=CATEGORIES,
        anchor=_anchor(6000.0),
        savings_plan=_savings(500.0),
        sinking_funds=FUNDS,
    )
    travel = next(row for row in plan.rows if row.category == "Travel")

    assert travel.source == "sinking_fund"
    assert travel.proposed_cap == 800.0
    assert "draws the fund down" in travel.detail
    assert travel.category not in {row.category for row in plan.rows if row.source == "shaped"}


def test_the_gap_to_what_is_actually_spent_is_stated_as_a_cut() -> None:
    plan = build_cap_plan(
        categories=CATEGORIES,
        anchor=_anchor(6000.0),
        savings_plan=_savings(500.0),
        sinking_funds=FUNDS,
    )

    # Groceries + Household + Retail run at 4,800 against 4,700 available.
    assert plan.trailing_monthly_total == 4800.0
    assert plan.gap_to_trailing == -100.0
    assert "a cut, not a description" in plan.drift_detail


def test_a_paused_savings_target_is_not_subtracted() -> None:
    plan = build_cap_plan(
        categories=CATEGORIES,
        anchor=_anchor(6000.0),
        savings_plan=_savings(500.0, status="paused"),
        sinking_funds=FUNDS,
    )

    assert plan.savings_target == 0.0
    assert plan.available_for_categories == 5200.0


def test_essentials_above_income_are_named_instead_of_capped() -> None:
    plan = build_cap_plan(
        categories=[_category("Groceries", essentiality="essential", monthly=5000.0)],
        anchor=_anchor(4000.0),
        savings_plan=_savings(None, status="undeclared"),
        sinking_funds=FUNDS,
    )

    assert plan.status == "essentials_exceed_income"
    assert "Essentials alone run $1,800 above" in plan.headline
    assert plan.discretionary_pool == 0.0


def test_no_measurable_income_proposes_nothing() -> None:
    plan = build_cap_plan(
        categories=CATEGORIES,
        anchor=_anchor(None),
        savings_plan=_savings(None, status="undeclared"),
        sinking_funds=FUNDS,
    )

    assert plan.status == "no_anchor"
    assert plan.rows == []
    assert "Declare an anchor" in plan.detail


def test_the_cards_annual_fees_come_out_before_the_categories_divide() -> None:
    """$190 charged once a year is $16/mo the caps cannot also spend (P0-20)."""
    plan = build_cap_plan(
        categories=CATEGORIES,
        anchor=_anchor(6000.0),
        savings_plan=_savings(500.0),
        sinking_funds=FUNDS,
        card_commitments=_card_fees(15.83, 190.0),
    )

    assert plan.card_fee_monthly == 15.83
    assert plan.available_for_categories == 4684.17
    assert plan.discretionary_pool == 3084.17
    assert "$16 card fees" in plan.detail
    assert plan.card_fee_detail == (
        "$190/yr across 2 cards, held back monthly so the renewal is already "
        "paid for when it posts."
    )


def test_cards_that_cost_nothing_to_keep_subtract_nothing() -> None:
    plan = build_cap_plan(
        categories=CATEGORIES,
        anchor=_anchor(6000.0),
        savings_plan=_savings(500.0),
        sinking_funds=FUNDS,
        card_commitments=HouseholdCardCommitments(status="committed"),
    )

    assert plan.card_fee_monthly == 0.0
    assert plan.available_for_categories == 4700.0
    assert plan.card_fee_detail == "None of the open cards charges an annual fee."


def test_no_card_reading_at_all_says_so_rather_than_implying_zero_fees() -> None:
    plan = build_cap_plan(
        categories=CATEGORIES,
        anchor=_anchor(6000.0),
        savings_plan=_savings(500.0),
        sinking_funds=FUNDS,
    )

    assert plan.card_fee_monthly == 0.0
    assert plan.card_fee_detail == "No card fees are being read into the plan."
