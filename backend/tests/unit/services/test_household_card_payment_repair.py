"""Guard the narrow historical correction of explicit card payments."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.household_card_payment_repair import _is_card_credit, _target


def _card_credit() -> dict[str, object]:
    return {
        "date": "2026-09-13",
        "description": "AUTOMATIC PAYMENT - THANK",
        "amount": Decimal("5896.50"),
        "flow_type": "income",
        "category": "Income",
        "essentiality": "essential",
        "source_system": "plaid",
        "categorization_source": "plaid",
        "transaction_rule_id": None,
        "spend_override": None,
        "original_category": "INCOME_SALARY",
        "metadata": {},
        "plaid_account_type": "credit",
        "plaid_signed_amount": Decimal("-5896.50"),
        "merchant_metadata": {},
        "active_merchant_rule": False,
    }


def _cash_debit() -> dict[str, object]:
    return {
        **_card_credit(),
        "date": "2026-09-15",
        "description": "DIRECT DEBIT CHASE CREDIT CAUTOPAY (Cash)",
        "flow_type": "expense",
        "category": "Bills",
        "source_system": "snaptrade",
        "categorization_source": "snaptrade",
        "original_category": "WITHDRAWAL",
        "metadata": {"source": "snaptrade_activity_bridge"},
        "plaid_account_type": "",
        "plaid_signed_amount": None,
    }


def test_repair_requires_source_evidence_and_matching_payment() -> None:
    credit = _card_credit()
    debit = _cash_debit()
    assert _is_card_credit(credit)
    assert _target(credit, [credit]) == ("payment", "Transfers", "mixed")
    assert _target(debit, [credit]) == ("transfer_out", "Transfers", "mixed")
    assert _target(debit, []) is None
    assert _target({**debit, "description": "DIRECT DEBIT DUKE ENERGY AUTOPAY (Cash)"}, [credit]) is None
    assert _target({**credit, "plaid_account_type": "depository"}, [credit]) is None


@pytest.mark.parametrize(
    "guard",
    [
        {"categorization_source": "manual"},
        {"categorization_source": "transaction_audit_agent"},
        {"transaction_rule_id": "user-rule"},
        {"spend_override": "include"},
        {"merchant_metadata": {"manual_rule": {"category": "Bills"}}},
        {"active_merchant_rule": True},
    ],
)
def test_repair_preserves_household_decisions(guard: dict[str, object]) -> None:
    credit = _card_credit()
    assert _target({**credit, **guard}, [credit]) is None
