"""Integration test for the soft -> hard charge reconciler (plan §5).

Proves the anti-double-counting core: a soft charge writes a mirror row that
counts toward spend immediately; when the matching Plaid hard row arrives, the
reconciler flips the soft charge to ``matched`` and voids the mirror so the hard
row is the single source of truth.

Runs against the test database via the standard ``get_storage`` fixture.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime

import pytest

from app.services.household_soft_charge_service import (
    HouseholdSoftChargeService,
    SoftChargeReconciler,
)


@pytest.fixture
def storage():
    from app.storage import get_storage

    return get_storage()


def _insert_account(storage, account_id: str) -> None:
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO household_accounts (id, name, account_type, created_at, updated_at)
            VALUES (%s, %s, 'credit_card', %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            [account_id, f"Test card {account_id[:8]}", datetime.now(UTC), datetime.now(UTC)],
        )
        conn.commit()


def _insert_hard_plaid_row(storage, *, account_id: str, amount: float, on: date, merchant: str) -> str:
    """Simulate the row PlaidService._upsert_transaction would write for a hard txn."""
    txn_id = f"plaid-test-{uuid.uuid4()}"
    row_hash = hashlib.sha256(f"plaid|{txn_id}".encode()).hexdigest()
    row_id = str(uuid.uuid4())
    # The hard row needs a document anchor (NOT NULL FK). Reuse the soft-charge
    # service's anchor helper indirectly by creating a minimal document here.
    doc_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO household_documents (
                id, filename, stored_path, source_type, document_type, status,
                content_type, file_size_bytes, uploaded_at, parsed_at, metadata,
                review_status
            ) VALUES (%s, 'plaid-test', 'plaid://test', 'plaid', 'api_sync', 'parsed',
                      'application/json', 0, %s, %s, '{}'::jsonb, 'complete')
            """,
            [doc_id, now, now],
        )
        conn.execute(
            """
            INSERT INTO household_transactions (
                id, document_id, household_account_id, row_hash, transaction_date,
                description, raw_merchant, amount, currency, flow_type, category,
                confidence, metadata, source_system, external_transaction_id,
                categorization_source, categorization_version, pending, removed,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'USD', 'expense', 'Dining',
                      1.0, '{}'::jsonb, 'plaid', %s, 'plaid', 'test', FALSE, FALSE, %s, %s)
            """,
            [
                row_id,
                doc_id,
                account_id,
                row_hash,
                datetime.combine(on, datetime.min.time(), tzinfo=UTC),
                merchant,
                merchant,
                amount,
                txn_id,
                now,
                now,
            ],
        )
        conn.commit()
    return row_hash


def _cleanup(storage, *, account_id: str, soft_id: str) -> None:
    with storage.connection() as conn:
        conn.execute("DELETE FROM household_soft_charges WHERE id = %s", [soft_id])
        conn.execute(
            "DELETE FROM household_transactions WHERE household_account_id = %s", [account_id]
        )
        conn.execute("DELETE FROM household_accounts WHERE id = %s", [account_id])
        conn.commit()


def test_soft_charge_matches_hard_and_voids_mirror(storage) -> None:
    account_id = str(uuid.uuid4())
    _insert_account(storage, account_id)
    service = HouseholdSoftChargeService(storage=storage)
    soft = service.create_soft_charge(
        amount=87.65,
        description="Lunch at the test cafe",
        merchant="Test Cafe",
        category="Dining",
        occurred_at="2026-06-09",
        household_account_id=account_id,
    )
    try:
        # Mirror row exists, pending, not removed -> counts toward spend.
        with storage.connection() as conn:
            mirror = conn.execute(
                "SELECT pending, removed, amount FROM household_transactions WHERE id = %s",
                [soft.ledger_transaction_id],
            ).fetchone()
        assert mirror is not None
        assert bool(mirror[0]) is True  # pending
        assert bool(mirror[1]) is False  # not removed
        assert float(mirror[2]) == pytest.approx(87.65)

        # The matching Plaid hard row posts two days later (auth->post lag).
        row_hash = _insert_hard_plaid_row(
            storage, account_id=account_id, amount=87.65, on=date(2026, 6, 11), merchant="Test Cafe"
        )

        # Run the reconciler exactly as PlaidService._upsert_transaction would.
        with storage.connection() as conn:
            matched_id = SoftChargeReconciler.try_match(
                conn=conn,
                hard_row_hash=row_hash,
                household_account_id=account_id,
                amount=87.65,
                occurred_on=date(2026, 6, 11),
                merchant="Test Cafe",
                description="Test Cafe purchase",
            )
            conn.commit()
        assert matched_id == soft.id

        with storage.connection() as conn:
            status = conn.execute(
                "SELECT status, match_method FROM household_soft_charges WHERE id = %s", [soft.id]
            ).fetchone()
            mirror_after = conn.execute(
                "SELECT removed FROM household_transactions WHERE id = %s",
                [soft.ledger_transaction_id],
            ).fetchone()
            # No double counting: exactly one non-removed expense row remains for
            # this account (the hard row); the mirror is voided.
            live_rows = conn.execute(
                """
                SELECT COUNT(*) FROM household_transactions
                WHERE household_account_id = %s AND removed = FALSE AND flow_type = 'expense'
                """,
                [account_id],
            ).fetchone()
        assert status[0] == "matched"
        assert status[1] == "auto_plaid_sync"
        assert bool(mirror_after[0]) is True  # mirror voided
        assert int(live_rows[0]) == 1  # single source of truth
    finally:
        _cleanup(storage, account_id=account_id, soft_id=soft.id)


def test_soft_charge_below_threshold_does_not_match(storage) -> None:
    """A hard row with a very different amount must NOT match."""
    account_id = str(uuid.uuid4())
    _insert_account(storage, account_id)
    service = HouseholdSoftChargeService(storage=storage)
    soft = service.create_soft_charge(
        amount=50.00,
        description="Coffee",
        merchant="Cafe A",
        category="Dining",
        occurred_at="2026-06-09",
        household_account_id=account_id,
    )
    try:
        row_hash = _insert_hard_plaid_row(
            storage, account_id=account_id, amount=500.00, on=date(2026, 6, 10), merchant="Cafe A"
        )
        with storage.connection() as conn:
            matched_id = SoftChargeReconciler.try_match(
                conn=conn,
                hard_row_hash=row_hash,
                household_account_id=account_id,
                amount=500.00,
                occurred_on=date(2026, 6, 10),
                merchant="Cafe A",
                description="Cafe A",
            )
            conn.commit()
        assert matched_id is None
        with storage.connection() as conn:
            status = conn.execute(
                "SELECT status FROM household_soft_charges WHERE id = %s", [soft.id]
            ).fetchone()
        assert status[0] == "pending"
    finally:
        _cleanup(storage, account_id=account_id, soft_id=soft.id)
