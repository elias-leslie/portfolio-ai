"""Repair actual shared merchant rows without losing a person's category."""

from __future__ import annotations

import json
import uuid
from datetime import date

import pytest
from tests.integration.services.test_household_transaction_dedup import (
    _insert_account,
    _insert_document,
    _insert_txn,
)

from app.services.household_merchant_repair import repair_household_merchants
from app.services.household_transaction_service import HouseholdTransactionService


@pytest.mark.parametrize("source", ["transaction_audit", "manual"], ids=["automatic", "person"])
def test_preview_apply_and_repeat_preserve_source_and_manual_choices(source: str) -> None:
    service = HouseholdTransactionService()
    storage = service.storage
    account = _insert_account(storage)
    document = _insert_document(storage, source_type="bank")
    merchant_id = str(uuid.uuid4())
    old_name = "Debit Card Purchase Cash App Jordan Demo"
    description = "DEBIT CARD PURCHASE PUBLIX #1309 FL090326 (Cash)"
    transaction_id = _insert_txn(
        storage, account_id=account, document_id=document, source_system="snaptrade",
        on=date(2026, 9, 8), amount=43.89, raw_merchant=description,
        categorization_source=source, category="Peer Payments",
    )
    with storage.connection() as conn:
        conn.execute(
            "INSERT INTO household_merchants (id,canonical_name,normalized_key,metadata) VALUES (%s,%s,%s,%s::jsonb)",
            [merchant_id, old_name, "biller:debitcard", json.dumps({"alias_keys": ["biller:debitcard"]})],
        )
        conn.execute(
            "UPDATE household_transactions SET raw_merchant=%s,merchant_id=%s,metadata=%s::jsonb WHERE id=%s",
            [old_name, merchant_id, json.dumps({"source": "snaptrade_activity_bridge"}), transaction_id],
        )
        conn.commit()
    preview = repair_household_merchants(service)
    assert not preview["applied"]
    with storage.connection() as conn:
        original = conn.execute("SELECT raw_merchant FROM household_transactions WHERE id=%s", [transaction_id]).fetchone()
        assert original is not None
        assert original[0] == old_name
    with pytest.raises(ValueError, match="changed since"):
        repair_household_merchants(service, expected_fingerprint="outdated")
    repair_household_merchants(service, expected_fingerprint=preview["fingerprint"])
    with storage.connection() as conn:
        row = conn.execute(
            "SELECT t.raw_merchant,t.description,t.category,m.canonical_name FROM household_transactions t JOIN household_merchants m ON m.id=t.merchant_id WHERE t.id=%s",
            [transaction_id],
        ).fetchone()
        assert row == (description, description, "Peer Payments" if source == "manual" else "Groceries", "Publix")
    repeated = repair_household_merchants(service)
    assert repeated["transactions"] == []
    assert repeated["merchants"] == []
