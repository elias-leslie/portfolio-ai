"""Unit tests for household transaction mutations."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.models.household_finance import (
    HouseholdQuestion,
    HouseholdTransactionCategoryUpdate,
    HouseholdTransactionOwnerUpdate,
)
from app.services.household_finance_service import HouseholdFinanceService


def test_update_transaction_category_can_apply_rule_to_merchant() -> None:
    service = HouseholdFinanceService()
    service.storage = MagicMock()
    conn = service.storage.connection.return_value.__enter__.return_value
    select_target = MagicMock()
    select_target.fetchone.return_value = ("txn-1", "merchant-1")
    update_transaction = MagicMock()
    update_transaction.fetchone.return_value = ("txn-1",)
    select_existing_rule = MagicMock()
    select_existing_rule.fetchone.return_value = None
    select_applied_count = MagicMock()
    select_applied_count.fetchone.return_value = (3,)
    insert_rule = MagicMock()
    update_merchant_transactions = MagicMock()
    update_merchant = MagicMock()
    conn.execute.side_effect = [
        select_target,
        update_transaction,
        select_existing_rule,
        select_applied_count,
        insert_rule,
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
    assert conn.execute.call_count == 7
    merchant_update_sql = conn.execute.call_args_list[6].args[0]
    assert "UPDATE household_merchants" in merchant_update_sql


def test_update_transaction_owner_can_apply_rule_to_merchant() -> None:
    service = HouseholdFinanceService()
    service.storage = MagicMock()
    conn = service.storage.connection.return_value.__enter__.return_value
    select_target = MagicMock()
    select_target.fetchone.return_value = ("txn-1", "merchant-1")
    update_transaction = MagicMock()
    update_transaction.fetchone.return_value = ("txn-1",)
    update_merchant = MagicMock()
    update_merchant_transactions = MagicMock()
    conn.execute.side_effect = [
        select_target,
        update_transaction,
        update_merchant,
        update_merchant_transactions,
    ]

    updated = service.update_transaction_owner(
        "txn-1",
        HouseholdTransactionOwnerUpdate(
            owner_name="Cats",
            apply_to_merchant=True,
        ),
    )

    assert updated is True
    assert conn.execute.call_count == 4
    owner_patch = conn.execute.call_args_list[1].args[1][0]
    assert '"owner_name": "Cats"' in owner_patch
    merchant_patch = conn.execute.call_args_list[2].args[1][0]
    assert "manual_owner_rule" in merchant_patch
    conn.commit.assert_called_once()


def test_ask_jenny_creates_user_to_jenny_question() -> None:
    service = HouseholdFinanceService()
    service.storage = MagicMock()
    conn = service.storage.connection.return_value.__enter__.return_value

    result = service.ask_jenny("How much should I save each month?")

    assert isinstance(result, HouseholdQuestion)
    assert result.question == "How much should I save each month?"
    assert result.direction == "user_to_jenny"
    assert result.status == "open"
    assert result.priority == "medium"
    assert result.question_format == "short_text"
    assert result.field_name is None

    insert_sql = conn.execute.call_args_list[0].args[0]
    assert "INSERT INTO household_questions" in insert_sql
    assert "user_to_jenny" in conn.execute.call_args_list[0].args[0]
    conn.commit.assert_called_once()


def test_ask_jenny_strips_whitespace() -> None:
    service = HouseholdFinanceService()
    service.storage = MagicMock()
    conn = service.storage.connection.return_value.__enter__.return_value

    result = service.ask_jenny("  What is my net worth?  ")

    assert result.question == "What is my net worth?"
    assert conn.execute.call_args_list[0].args[1][1] == "What is my net worth?"
