"""Review and ledger agree across posted-date boundaries, refunds and item splits."""

import uuid
from datetime import date
from types import SimpleNamespace

from tests.integration.services.test_household_transaction_dedup import (
    _insert_account,
    _insert_document,
    _insert_txn,
)

from app.services.household_ledger_service import HouseholdLedgerService
from app.services.household_transaction_service import HouseholdTransactionService


def test_named_month_uses_review_rows_and_signed_category_allocations():
    transactions = HouseholdTransactionService()
    storage = transactions.storage
    account = _insert_account(storage)
    document = _insert_document(storage, source_type="bank")

    def purchase(on, amount, merchant="Warehouse", category="Retail"):
        return _insert_txn(
            storage,
            account_id=account,
            document_id=document,
            source_system="snaptrade",
            on=on,
            amount=amount,
            raw_merchant=merchant,
            category=category,
            categorization_source="manual",
        )

    charge = purchase(date(2026, 8, 31), 100)
    refund = purchase(date(2026, 8, 15), 10, "Grocery refund", "Groceries")
    transfer = purchase(date(2026, 8, 10), 50, "Own transfer", "Transfers")
    purchase(date(2026, 9, 1), 200)
    purchase(date(2026, 7, 31), 400)
    with storage.connection() as conn:
        conn.execute(
            "UPDATE household_transactions SET posted_date='2026-09-02', balance_after=123 WHERE id=%s",
            [charge],
        )
        conn.execute(
            "UPDATE household_transactions SET flow_type='refund', balance_after=456 WHERE id=%s",
            [refund],
        )
        conn.execute(
            "UPDATE household_transactions SET flow_type='transfer_out' WHERE id=%s", [transfer]
        )
        for category, amount in [("Groceries", 60), ("Household", 40)]:
            import_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO household_import_rows (id,document_id,dataset_type,row_hash,row_metadata,created_at,updated_at) VALUES (%s,%s,'receipt',%s,'{}'::jsonb,NOW(),NOW())",
                [import_id, document, import_id],
            )
            conn.execute(
                "INSERT INTO household_purchase_items (id,import_row_id,document_id,purchase_group_key,transaction_id,description,amount,allocated_amount,category,essentiality) VALUES (%s,%s,%s,'receipt',%s,%s,%s,%s,%s,'mixed')",
                [
                    str(uuid.uuid4()),
                    import_id,
                    document,
                    charge,
                    category,
                    amount,
                    amount,
                    category,
                ],
            )
        conn.commit()
    service = SimpleNamespace(storage=storage, transaction_service=transactions)
    ledger_service = HouseholdLedgerService()
    report = transactions.build_spending_view(month="2026-08")
    ledger = ledger_service.get_ledger(
        service, month="2026-08", kind="transactions", status="all", inclusion="included", limit=1
    )
    assert ledger.review_spend_total == report.summary.total_spend == 90
    assert ledger.filtered_count == 2
    assert len(ledger.entries) == 1
    assert ledger.entries[0].id == charge
    assert ledger.entries[0].balance_after == 123
    for category in report.categories:
        filtered = ledger_service.get_ledger(
            service,
            month="2026-08",
            kind="transactions",
            category=category.category,
            inclusion="included",
            status="all",
        )
        assert filtered.review_spend_total == category.total_spend
    groceries = ledger_service.get_ledger(
        service,
        month="2026-08",
        kind="transactions",
        category="Groceries",
        inclusion="included",
        status="all",
    )
    assert groceries.review_spend_total == 50
    assert {row.id: row.review_amount for row in groceries.entries} == {charge: 60, refund: -10}
    excluded = ledger_service.get_ledger(
        service, month="2026-08", kind="transactions", inclusion="excluded", status="all"
    )
    assert [row.id for row in excluded.entries] == [transfer]
    assert excluded.review_spend_total == 0
    absent_source = ledger_service.get_ledger(
        service, month="2026-08", kind="transactions", source="plaid"
    )
    assert absent_source.review_spend_total == 0


def test_monthly_agreement_persists_and_invalid_replacement_preserves_it():
    import json

    import pytest

    from app.services.household_finance_service import HouseholdFinanceService

    service = HouseholdFinanceService()
    key = "monthly_review:2026-08"
    agreed = {
        "expected_income": 3000,
        "planned_asset_draw": 1000,
        "planned_spending": 3800,
        "additional_commitments": 200,
        "decisions": [{"action": "Review the phone bill", "outcome": "not_reviewed"}],
    }
    saved = service.confirm_fact(key, json.dumps(agreed))
    assert json.loads(saved.fact_value)["planned_asset_draw"] == 1000
    with pytest.raises(ValueError):
        service.confirm_fact(key, '{"expected_income": -1}')
    facts = [fact for fact in service.list_confirmed_facts() if fact.fact_key == key]
    assert len(facts) == 1
    assert json.loads(facts[0].fact_value)["decisions"][0]["outcome"] == "not_reviewed"
    agreed["decisions"][0]["outcome"] = "kept"
    service.confirm_fact(key, json.dumps(agreed))
    updated = next(fact for fact in service.list_confirmed_facts() if fact.fact_key == key)
    assert json.loads(updated.fact_value)["decisions"][0]["outcome"] == "kept"
