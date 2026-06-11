"""Integration tests: cross-document duplicate collapse on the real schema.

Reproduces the production failure: the same card charge imported from
overlapping CSV exports plus the Plaid feed (with a one-day posted-date
skew) inflated healthcare spend ~4x. The dedup service must keep one copy
per real charge, preserve manual categorization, and leave legitimate
same-day pairs alone.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from app.services.household_transaction_dedup_service import (
    HouseholdTransactionDedupService,
)


@pytest.fixture
def storage():
    from app.storage import get_storage

    return get_storage()


def _insert_account(storage) -> str:
    account_id = str(uuid.uuid4())
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO household_accounts (
                id, canonical_label, asset_group, account_type, source_type,
                metadata, created_at, updated_at
            )
            VALUES (%s, %s, 'cash', 'credit_card', 'credit_card', '{}'::jsonb, %s, %s)
            """,
            [account_id, f"Dedup test card {account_id[:8]}", datetime.now(UTC), datetime.now(UTC)],
        )
        conn.commit()
    return account_id


def _insert_document(storage, *, source_type: str) -> str:
    doc_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO household_documents (
                id, filename, stored_path, source_type, document_type, status,
                content_type, file_size_bytes, uploaded_at, parsed_at, metadata,
                review_status
            ) VALUES (%s, 'dedup-test', 'test://dedup', %s, 'statement', 'parsed',
                      'text/csv', 0, %s, %s, '{}'::jsonb, 'complete')
            """,
            [doc_id, source_type, now, now],
        )
        conn.commit()
    return doc_id


def _insert_txn(
    storage,
    *,
    account_id: str,
    document_id: str,
    source_system: str,
    on: date,
    amount: float,
    raw_merchant: str,
    categorization_source: str = "parser",
    category: str = "Healthcare",
) -> str:
    row_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO household_transactions (
                id, document_id, household_account_id, row_hash, transaction_date,
                description, raw_merchant, amount, currency, flow_type, category,
                confidence, metadata, source_system, categorization_source,
                categorization_version, pending, removed, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'USD', 'expense', %s,
                      1.0, '{}'::jsonb, %s, %s, 'test', FALSE, FALSE, %s, %s)
            """,
            [
                row_id,
                document_id,
                account_id,
                f"dedup-test-{row_id}",
                datetime.combine(on, datetime.min.time(), tzinfo=UTC),
                raw_merchant,
                raw_merchant,
                amount,
                category,
                source_system,
                categorization_source,
                now,
                now,
            ],
        )
        conn.commit()
    return row_id


def _flags(storage, row_ids: list[str]) -> dict[str, dict]:
    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, removed, category, categorization_source, metadata
            FROM household_transactions
            WHERE id = ANY(%s)
            """,
            [row_ids],
        ).fetchall()
    return {
        str(r[0]): {
            "removed": bool(r[1]),
            "category": r[2],
            "categorization_source": r[3],
            "metadata": r[4] or {},
        }
        for r in rows
    }


def test_overlapping_exports_and_plaid_skew_collapse_to_true_charges(storage) -> None:
    account_id = _insert_account(storage)
    on = date(2026, 1, 2)
    ids: list[str] = []
    # Three overlapping CSV exports, each containing the same two real
    # charges (two ortho contracts billed the same day at the same price).
    for _ in range(3):
        doc = _insert_document(storage, source_type="statement_csv")
        ids.append(
            _insert_txn(
                storage,
                account_id=account_id,
                document_id=doc,
                source_system="statement_csv",
                on=on,
                amount=132.08,
                raw_merchant="ALL SMILES ORTHO LARGO | Sale",
            )
        )
        ids.append(
            _insert_txn(
                storage,
                account_id=account_id,
                document_id=doc,
                source_system="statement_csv",
                on=on,
                amount=132.08,
                raw_merchant="ALL SMILES ORTHO CLEAR | Sale",
            )
        )
    # One of the duplicate CSV rows carries a manual categorization.
    manual_id = ids[0]
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE household_transactions
            SET categorization_source = 'manual', category = 'Kids', category_updated_by = 'user'
            WHERE id = %s
            """,
            [manual_id],
        )
        conn.commit()
    # Plaid delivers the same pair one day later with truncated merchants.
    plaid_doc = _insert_document(storage, source_type="plaid")
    plaid_largo = _insert_txn(
        storage,
        account_id=account_id,
        document_id=plaid_doc,
        source_system="plaid",
        on=date(2026, 1, 3),
        amount=132.08,
        raw_merchant="All Smiles Ortho",
    )
    plaid_clear = _insert_txn(
        storage,
        account_id=account_id,
        document_id=plaid_doc,
        source_system="plaid",
        on=date(2026, 1, 3),
        amount=132.08,
        raw_merchant="All Smiles Ortho Clear",
    )
    ids.extend([plaid_largo, plaid_clear])

    summary = HouseholdTransactionDedupService(storage).dedupe_transactions(
        household_account_ids=[account_id]
    )
    assert summary["removed"] == 6

    flags = _flags(storage, ids)
    survivors = [i for i in ids if not flags[i]["removed"]]
    removed = [i for i in ids if flags[i]["removed"]]
    assert len(survivors) == 2
    assert len(removed) == 6
    # The manual row's unit wins (manual count outranks plaid priority),
    # so the user's category survives without copying.
    assert manual_id in survivors
    assert flags[manual_id]["category"] == "Kids"
    for row_id in removed:
        dedup_meta = flags[row_id]["metadata"].get("dedup", {})
        assert dedup_meta.get("reason") == "cross_document_duplicate"
        assert dedup_meta.get("kept_transaction_id") in survivors


def test_manual_category_copied_when_its_row_is_removed(storage) -> None:
    account_id = _insert_account(storage)
    on = date(2026, 2, 12)
    # Winning unit: plaid pair (two rows). Losing unit: one CSV row with a
    # manual category — it must be copied onto the compatible survivor.
    plaid_doc = _insert_document(storage, source_type="plaid")
    plaid_largo = _insert_txn(
        storage,
        account_id=account_id,
        document_id=plaid_doc,
        source_system="plaid",
        on=on,
        amount=132.08,
        raw_merchant="All Smiles Ortho",
    )
    plaid_clear = _insert_txn(
        storage,
        account_id=account_id,
        document_id=plaid_doc,
        source_system="plaid",
        on=on,
        amount=132.08,
        raw_merchant="All Smiles Ortho Clear",
    )
    csv_doc = _insert_document(storage, source_type="statement_csv")
    csv_manual = _insert_txn(
        storage,
        account_id=account_id,
        document_id=csv_doc,
        source_system="statement_csv",
        on=on,
        amount=132.08,
        raw_merchant="ALL SMILES ORTHO LARGO | Sale",
        categorization_source="manual",
        category="Kids",
    )

    summary = HouseholdTransactionDedupService(storage).dedupe_transactions(
        household_account_ids=[account_id]
    )
    assert summary["removed"] == 1
    assert summary["category_copies"] == 1

    flags = _flags(storage, [plaid_largo, plaid_clear, csv_manual])
    assert flags[csv_manual]["removed"] is True
    assert flags[plaid_largo]["removed"] is False
    assert flags[plaid_largo]["category"] == "Kids"
    assert flags[plaid_largo]["categorization_source"] == "manual"
    assert flags[plaid_clear]["category"] == "Healthcare"


def test_legitimate_rows_left_alone_and_dry_run_writes_nothing(storage) -> None:
    account_id = _insert_account(storage)
    # Same-day same-amount pair within a single document: two real charges.
    doc = _insert_document(storage, source_type="statement_csv")
    pair_a = _insert_txn(
        storage,
        account_id=account_id,
        document_id=doc,
        source_system="statement_csv",
        on=date(2026, 3, 2),
        amount=20.0,
        raw_merchant="WALGREENS #6803",
    )
    pair_b = _insert_txn(
        storage,
        account_id=account_id,
        document_id=doc,
        source_system="statement_csv",
        on=date(2026, 3, 2),
        amount=20.0,
        raw_merchant="CVS/PHARMACY #05786",
    )
    # Cross-source same amount two days apart with incompatible merchants:
    # different real charges, must not merge.
    plaid_doc = _insert_document(storage, source_type="plaid")
    other = _insert_txn(
        storage,
        account_id=account_id,
        document_id=plaid_doc,
        source_system="plaid",
        on=date(2026, 3, 4),
        amount=20.0,
        raw_merchant="Target",
    )
    summary = HouseholdTransactionDedupService(storage).dedupe_transactions(
        household_account_ids=[account_id]
    )
    assert summary["removed"] == 0
    flags = _flags(storage, [pair_a, pair_b, other])
    assert all(not f["removed"] for f in flags.values())

    # Dry run over a real duplicate writes nothing.
    dup_doc = _insert_document(storage, source_type="statement_csv")
    dup = _insert_txn(
        storage,
        account_id=account_id,
        document_id=dup_doc,
        source_system="statement_csv",
        on=date(2026, 3, 2),
        amount=20.0,
        raw_merchant="WALGREENS #6803",
    )
    dry = HouseholdTransactionDedupService(storage).dedupe_transactions(
        household_account_ids=[account_id], dry_run=True
    )
    assert dry["removed"] == 1
    assert dry["dry_run"] is True
    flags = _flags(storage, [pair_a, pair_b, dup])
    assert all(not f["removed"] for f in flags.values())
