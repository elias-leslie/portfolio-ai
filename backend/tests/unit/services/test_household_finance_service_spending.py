"""Unit tests for household spending rollups."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import Mock

from app.models.household_finance import (
    HouseholdConfirmedFact,
    HouseholdProfile,
    HouseholdSpendingCategory,
    HouseholdSpendingSummary,
    HouseholdSpendingView,
)
from app.services.household_finance_service import HouseholdFinanceService


def test_get_spending_reconciles_found_and_confirmed_budget_rollups() -> None:
    service = HouseholdFinanceService()
    service.transaction_service = Mock()
    # No income history reaches the anchor here, so the cap plan proposes
    # nothing and the rollup falls back to history-shaped suggestions -- which
    # is exactly the reconciliation this test is about.
    service.transaction_service.income_totals_by_month.return_value = {}
    service.transaction_service.spend_rows_for_window.return_value = []
    service.get_profile = cast(
        Any,
        Mock(
            return_value=HouseholdProfile(
                id="profile-1",
                household_name="Household",
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            )
        ),
    )
    service.transaction_service.build_spending_view.return_value = HouseholdSpendingView(
        generated_at="2026-04-24T00:00:00Z",
        summary=HouseholdSpendingSummary(
            month="2026-04",
            month_label="April 2026",
            total_spend=5033,
            average_monthly_spend=5033,
            transaction_count=62,
            coverage_months=3,
            account_count=2,
        ),
        categories=[
            HouseholdSpendingCategory(
                category="Household",
                essentiality="mixed",
                total_spend=1482,
                average_monthly_spend=1482,
                share_of_spend=0.4,
                transaction_count=30,
            ),
            HouseholdSpendingCategory(
                category="Retail",
                essentiality="discretionary",
                total_spend=1287,
                average_monthly_spend=1287,
                share_of_spend=0.35,
                transaction_count=22,
            ),
            HouseholdSpendingCategory(
                category="Groceries",
                essentiality="essential",
                total_spend=246,
                average_monthly_spend=246,
                share_of_spend=0.08,
                transaction_count=10,
            ),
        ],
    )
    service.list_confirmed_facts = cast(
        Any,
        Mock(
            return_value=[
                HouseholdConfirmedFact(
                    fact_key="category_budget:Retail",
                    fact_value=(
                        '{"category":"Retail","monthlyTarget":1200,'
                        '"source":"accepted","note":"Accepted cap","disabled":false}'
                    ),
                    confirmed_at="2026-04-24T00:00:00Z",
                )
            ]
        ),
    )

    spending = service.get_spending(month="2026-04")

    service.transaction_service.build_spending_view.assert_called_once_with(month="2026-04")
    assert spending.summary.found_budget_total == 1650
    assert spending.summary.confirmed_budget_total == 1200
    assert spending.summary.budgeted_category_count == 3
    assert spending.summary.found_budget_category_count == 2
    assert spending.summary.confirmed_budget_category_count == 1
    assert spending.summary.over_budget_count == 2
    assert spending.summary.found_over_budget_count == 1
    assert spending.summary.confirmed_over_budget_count == 1

    categories = {row.category: row for row in spending.categories}
    assert categories["Household"].found_monthly_budget == 1400
    assert categories["Household"].budget_status == "found_over_budget"
    assert categories["Retail"].confirmed_monthly_budget == 1200
    assert categories["Retail"].budget_status == "over_budget"
    assert categories["Retail"].budget_note == "Accepted cap"
    assert categories["Groceries"].found_monthly_budget == 250
    assert categories["Groceries"].budget_status == "found_unconfirmed"


def test_suggested_caps_come_from_the_income_anchored_plan() -> None:
    """The old suggestion handed an overspent category its own overspend back."""
    service = HouseholdFinanceService()
    service.transaction_service = Mock()
    service.transaction_service.income_totals_by_month.return_value = {
        "2026-01": 6000.0,
        "2026-02": 6000.0,
        "2026-03": 6000.0,
    }
    service.transaction_service.spend_rows_for_window.return_value = []
    service.get_profile = cast(
        Any,
        Mock(
            return_value=HouseholdProfile(
                id="profile-1",
                household_name="Household",
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            )
        ),
    )
    service.transaction_service.build_spending_view.return_value = HouseholdSpendingView(
        generated_at="2026-04-24T00:00:00Z",
        summary=HouseholdSpendingSummary(
            month="2026-04",
            month_label="April 2026",
            total_spend=9000,
            average_monthly_spend=9000,
            transaction_count=60,
            coverage_months=3,
            account_count=2,
        ),
        categories=[
            HouseholdSpendingCategory(
                category="Groceries",
                essentiality="essential",
                total_spend=2000,
                average_monthly_spend=2000,
                share_of_spend=0.22,
                transaction_count=30,
            ),
            HouseholdSpendingCategory(
                category="Retail",
                essentiality="discretionary",
                total_spend=7000,
                average_monthly_spend=7000,
                share_of_spend=0.78,
                transaction_count=29,
            ),
            HouseholdSpendingCategory(
                category="Donations",
                essentiality="discretionary",
                total_spend=0.29,
                average_monthly_spend=0.29,
                share_of_spend=0.0,
                transaction_count=1,
            ),
        ],
    )
    service.list_confirmed_facts = cast(Any, Mock(return_value=[]))

    spending = service.get_spending(month="2026-04")
    categories = {row.category: row for row in spending.categories}

    # $6,000 anchor, nothing saved or accrued, essentials held at their $2,000
    # cost, and the $4,000 left divided by share -- not $7,000 handed back to
    # Retail because that is what Retail spent. Donations' 17c share is not a
    # cap anyone can act on, so it gets no suggestion and is not in the total.
    assert categories["Groceries"].found_monthly_budget == 2000
    assert categories["Retail"].found_monthly_budget == 3999.83
    assert categories["Donations"].found_monthly_budget is None
    assert spending.summary.found_budget_total == 5999.83
