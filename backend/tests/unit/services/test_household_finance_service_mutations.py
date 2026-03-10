"""Unit tests for household transaction mutations."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.models.household_finance import HouseholdTransactionCategoryUpdate
from app.services.household_finance_service import HouseholdFinanceService


def test_update_transaction_category_can_apply_rule_to_merchant() -> None:
    service = HouseholdFinanceService()
    service.storage = MagicMock()
    conn = service.storage.connection.return_value.__enter__.return_value
    select_target = MagicMock()
    select_target.fetchone.return_value = ("txn-1", "merchant-1")
    update_transaction = MagicMock()
    update_transaction.fetchone.return_value = ("txn-1",)
    update_merchant_transactions = MagicMock()
    update_merchant = MagicMock()
    conn.execute.side_effect = [
        select_target,
        update_transaction,
        update_merchant_transactions,
        update_merchant,
    ]

    updated = service.update_transaction_category(
        "txn-1",
        HouseholdTransactionCategoryUpdate(
            category="Bills",
            essentiality="essential",
            apply_to_merchant=True,
        ),
    )

    assert updated is True
    assert conn.execute.call_count == 4
    merchant_update_sql = conn.execute.call_args_list[3].args[0]
    assert "UPDATE household_merchants" in merchant_update_sql
