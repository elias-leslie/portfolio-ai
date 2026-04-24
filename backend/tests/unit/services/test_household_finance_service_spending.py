"""Unit tests for household spending rollups."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import Mock

from app.models.household_finance import (
    HouseholdConfirmedFact,
    HouseholdSpendingCategory,
    HouseholdSpendingSummary,
    HouseholdSpendingView,
)
from app.services.household_finance_service import HouseholdFinanceService


def test_get_spending_reconciles_found_and_confirmed_budget_rollups() -> None:
    service = HouseholdFinanceService()
    service.transaction_service = Mock()
    service.transaction_service.build_spending_view.return_value = HouseholdSpendingView(
        generated_at="2026-04-24T00:00:00Z",
        summary=HouseholdSpendingSummary(
            timeframe_key="3m",
            timeframe_label="3 months",
            total_spend=15099,
            average_monthly_spend=5033,
            transaction_count=62,
            coverage_months=3,
            account_count=2,
        ),
        categories=[
            HouseholdSpendingCategory(
                category="Household",
                essentiality="mixed",
                total_spend=4446,
                average_monthly_spend=1482,
                share_of_spend=0.4,
                transaction_count=30,
            ),
            HouseholdSpendingCategory(
                category="Retail",
                essentiality="discretionary",
                total_spend=3861,
                average_monthly_spend=1287,
                share_of_spend=0.35,
                transaction_count=22,
            ),
            HouseholdSpendingCategory(
                category="Groceries",
                essentiality="essential",
                total_spend=738,
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

    spending = service.get_spending(window="3m")

    service.transaction_service.build_spending_view.assert_called_once_with(window="3m")
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
