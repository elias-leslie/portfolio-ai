"""Soft-charge ledger: phone-entered provisional spend that counts immediately.

The anti-surprise core (plan §5). A soft charge is a charge the user knows they
made — a pending purchase, a receipt photo, a "I just spent $X" phone entry —
before Plaid has synced the real (hard) transaction. To make it count toward the
budget the instant it is entered, every soft charge writes a **mirror row** into
the canonical ``household_transactions`` ledger (``source_system='soft_charge'``,
``pending=TRUE``, ``flow_type='expense'``). Because ``build_spending_view`` reads
that table, ``month_to_date_spend``, category totals, and budget pace light up
with zero new spend math.

When Plaid later syncs the matching hard transaction, ``SoftChargeReconciler``
(called from ``PlaidService._upsert_transaction`` in the *same* DB transaction)
matches it, flips the soft charge to ``matched``, and marks the mirror row
``removed=TRUE`` so the hard row is the single source of truth — no double
counting (the #1 risk). A soft charge whose Plaid txn never lands expires after
~35 days and its mirror row stays as genuine spend.

The ``document_id`` NOT NULL FK on ``household_transactions`` is satisfied by a
singleton synthetic ``household_documents`` anchor (``source_type='soft_charge'``)
when no receipt was uploaded, or by the uploaded receipt's document otherwise —
mirroring ``PlaidService._ensure_sync_document``.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.logging_config import get_logger
from app.models.credit_cards import SoftCharge
from app.storage import get_storage

logger = get_logger(__name__)

# Match threshold for soft -> hard reconciliation (plan §5).
MATCH_THRESHOLD: float = 0.75
# Auth->post lag window: a soft charge can match a hard txn dated a little before
# (pre-auth) up to several days after (settlement).
MATCH_DATE_BACK_DAYS: int = 1
MATCH_DATE_FORWARD_DAYS: int = 5
# Unmatched soft charges older than this become ``expired`` (the mirror row stays
# as real spend — a charge that genuinely happened but never synced via Plaid).
EXPIRE_AFTER_DAYS: int = 35
# Generic spend category for a phone entry with no category. Must NOT be an
# excluded cash-movement category (see _household_spend_filters) so it counts.
DEFAULT_SOFT_CATEGORY: str = "Retail"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _td(days: int) -> timedelta:
    return timedelta(days=days)


def _json(value: object) -> str:
    return json.dumps(value, default=str)


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value.strip()[:10])
    return _now().date()


def _tokens(*parts: str | None) -> set[str]:
    """Lowercased alphanumeric word tokens for merchant/description overlap."""
    text = " ".join(p for p in parts if p)
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= 3}


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


_SOFT_CHARGE_COLUMNS = (
    "id, household_account_id, amount, description, merchant, category, essentiality, "
    "occurred_at, source_document_id, status, matched_plaid_transaction_id, matched_at, "
    "match_confidence, match_method, ledger_transaction_id, metadata, created_at, updated_at"
)


def _row_to_soft_charge(row: tuple[Any, ...]) -> SoftCharge:
    metadata = row[15]
    if isinstance(metadata, str):
        metadata = json.loads(metadata or "{}")
    return SoftCharge(
        id=str(row[0]),
        household_account_id=str(row[1]) if row[1] else None,
        amount=float(row[2]),
        description=str(row[3]),
        merchant=str(row[4]) if row[4] else None,
        category=str(row[5]) if row[5] else None,
        essentiality=str(row[6]) if row[6] else None,
        occurred_at=_iso(row[7]) or "",
        source_document_id=str(row[8]) if row[8] else None,
        status=str(row[9]),
        matched_plaid_transaction_id=str(row[10]) if row[10] else None,
        matched_at=_iso(row[11]),
        match_confidence=float(row[12]) if row[12] is not None else None,
        match_method=str(row[13]) if row[13] else None,
        ledger_transaction_id=str(row[14]) if row[14] else None,
        metadata=metadata or {},
        created_at=_iso(row[16]),
        updated_at=_iso(row[17]),
    )


class SoftChargeReconciler:
    """Matches a freshly-upserted hard Plaid row to a pending soft charge.

    Stateless and idempotent. ``try_match`` operates on a caller-supplied
    connection and does NOT commit — the Plaid sync owns the transaction so the
    hard upsert and the mirror void are atomic (plan §5).
    """

    @staticmethod
    def try_match(
        *,
        conn: Any,
        hard_row_hash: str,
        household_account_id: str | None,
        amount: float | Decimal,
        occurred_on: date,
        merchant: str | None,
        description: str | None,
    ) -> str | None:
        """Match the hard row (identified by ``hard_row_hash``) to the best
        pending soft charge for its account. Returns the matched soft-charge id,
        or ``None``. Marks the soft charge ``matched`` and voids its mirror row.
        """
        if not household_account_id:
            return None
        hard_amount = float(amount)
        # Candidate soft charges: same account, still pending, within the lag
        # window. (occurred_at is a DATE.)
        candidates = conn.execute(
            """
            SELECT id, amount, occurred_at, merchant, description, ledger_transaction_id
            FROM household_soft_charges
            WHERE status = 'pending'
              AND household_account_id = %s
              AND occurred_at BETWEEN %s AND %s
            """,
            [
                household_account_id,
                occurred_on - _td(MATCH_DATE_FORWARD_DAYS),
                occurred_on + _td(MATCH_DATE_BACK_DAYS),
            ],
        ).fetchall()
        if not candidates:
            return None

        hard_tokens = _tokens(merchant, description)
        best_id: str | None = None
        best_ledger_id: str | None = None
        best_score = 0.0
        tolerance = max(1.0, hard_amount * 0.015)  # $1 or 1.5% for tips/FX/pre-auth
        for cand in candidates:
            soft_id = str(cand[0])
            soft_amount = float(cand[1])
            soft_date = _as_date(cand[2])
            amount_delta = abs(soft_amount - hard_amount)
            if amount_delta > tolerance:
                continue
            score = 0.6  # within account + window + amount tolerance => base match
            if amount_delta <= 0.005:
                score += 0.2  # exact amount
            day_gap = abs((soft_date - occurred_on).days)
            if day_gap <= 1:
                score += 0.1
            soft_tokens = _tokens(cand[3], cand[4])
            if hard_tokens and soft_tokens and (hard_tokens & soft_tokens):
                score += 0.15
            if score > best_score:
                best_score = score
                best_id = soft_id
                best_ledger_id = str(cand[5]) if cand[5] else None

        if best_id is None or best_score < MATCH_THRESHOLD:
            return None

        hard_row = conn.execute(
            "SELECT id FROM household_transactions WHERE row_hash = %s",
            [hard_row_hash],
        ).fetchone()
        hard_id = str(hard_row[0]) if hard_row else None

        now = _now()
        # Mark the soft charge matched (immediately, so one soft never matches two
        # hard rows on the same sync batch).
        conn.execute(
            """
            UPDATE household_soft_charges
            SET status = 'matched',
                matched_plaid_transaction_id = %s,
                matched_at = %s,
                match_confidence = %s,
                match_method = 'auto_plaid_sync',
                updated_at = %s
            WHERE id = %s AND status = 'pending'
            """,
            [hard_id, now, round(best_score, 3), now, best_id],
        )
        # Void the mirror row so the hard row is the single source -> no double count.
        if best_ledger_id:
            conn.execute(
                """
                UPDATE household_transactions
                SET removed = TRUE, updated_at = %s
                WHERE id = %s
                """,
                [now, best_ledger_id],
            )
        logger.info(
            "soft_charge_matched",
            soft_charge_id=best_id,
            hard_transaction_id=hard_id,
            score=round(best_score, 3),
        )
        return best_id


class HouseholdSoftChargeService:
    """CRUD + mirror-row management for the soft-charge ledger."""

    def __init__(self, storage: Any | None = None) -> None:
        self.storage = storage or get_storage()

    # -- document anchor (resolves the NOT NULL household_transactions.document_id)

    def _ensure_soft_charge_document(self, conn: Any) -> str:
        """Singleton synthetic document anchoring receipt-less soft charges.

        Mirrors PlaidService._ensure_sync_document so soft mirror rows satisfy the
        NOT NULL document_id FK without inventing a fake statement per charge.
        """
        existing = conn.execute(
            """
            SELECT id FROM household_documents
            WHERE source_type = 'soft_charge' AND document_type = 'manual_entry'
            ORDER BY uploaded_at ASC
            LIMIT 1
            """,
        ).fetchone()
        if existing is not None:
            return str(existing[0])
        document_id = str(uuid.uuid4())
        now = _now()
        conn.execute(
            """
            INSERT INTO household_documents (
                id, filename, stored_path, source_type, document_type, status,
                account_label, content_type, file_size_bytes,
                classification_confidence, uploaded_at, parsed_at, metadata,
                review_status, review_summary, review_confidence
            ) VALUES (
                %s, %s, %s, 'soft_charge', 'manual_entry', 'parsed',
                %s, 'application/json', 0,
                1.0, %s, %s, %s::jsonb,
                'complete', %s, 1.0
            )
            """,
            [
                document_id,
                "Phone-entered charges",
                "soft_charge://manual",
                "Manual entries",
                now,
                now,
                _json({"source": "soft_charge"}),
                "Provisional phone-entered charges (soft ledger).",
            ],
        )
        return document_id

    def _resolve_default_account(self, conn: Any) -> str | None:
        """The current primary-active card's linked household account, if any."""
        row = conn.execute(
            """
            SELECT household_account_id
            FROM household_credit_cards
            WHERE is_primary_active = TRUE AND household_account_id IS NOT NULL
            LIMIT 1
            """,
        ).fetchone()
        return str(row[0]) if row and row[0] else None

    # -- create

    def create_soft_charge(
        self,
        *,
        amount: float,
        description: str,
        merchant: str | None = None,
        category: str | None = None,
        essentiality: str | None = None,
        occurred_at: str | date | None = None,
        household_account_id: str | None = None,
        source_document_id: str | None = None,
    ) -> SoftCharge:
        if amount is None or float(amount) <= 0:
            raise ValueError("Soft charge amount must be positive.")
        if not description or not description.strip():
            raise ValueError("Soft charge requires a description.")

        soft_id = str(uuid.uuid4())
        ledger_id = str(uuid.uuid4())
        money = _money(amount)
        occurred = _as_date(occurred_at)
        clean_category = (category or DEFAULT_SOFT_CATEGORY).strip()
        clean_description = description.strip()
        now = _now()

        with self.storage.connection() as conn:
            account_id = household_account_id or self._resolve_default_account(conn)
            # Mirror row uses the uploaded receipt's document when present, else
            # the singleton soft-charge anchor.
            document_id = source_document_id or self._ensure_soft_charge_document(conn)
            row_hash = hashlib.sha256(f"soft|{soft_id}".encode()).hexdigest()

            # 1) Mirror row in the canonical ledger -> counts toward budget now.
            conn.execute(
                """
                INSERT INTO household_transactions (
                    id, document_id, household_account_id, row_hash,
                    transaction_date, posted_date, description, raw_merchant, account_label,
                    amount, currency, flow_type, category, essentiality, confidence,
                    metadata, source_system, external_transaction_id, original_category,
                    categorization_source, categorization_version, pending, removed,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, NULL, %s, %s, %s,
                    %s, 'USD', 'expense', %s, %s, 1.0,
                    %s::jsonb, 'soft_charge', %s, %s,
                    'manual', 'soft-charge', TRUE, FALSE,
                    %s, %s
                )
                """,
                [
                    ledger_id,
                    document_id,
                    account_id,
                    row_hash,
                    datetime.combine(occurred, datetime.min.time(), tzinfo=UTC),
                    clean_description,
                    merchant,
                    "Soft charge",
                    money,
                    clean_category,
                    essentiality,
                    _json({"soft_charge_id": soft_id, "source": "soft_charge"}),
                    f"soft:{soft_id}",
                    clean_category,
                    now,
                    now,
                ],
            )
            # 2) The soft-charge ledger row, pointing back at the mirror.
            conn.execute(
                """
                INSERT INTO household_soft_charges (
                    id, household_account_id, amount, description, merchant, category,
                    essentiality, occurred_at, source_document_id, status,
                    ledger_transaction_id, metadata, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, '{}'::jsonb, %s, %s
                )
                """,
                [
                    soft_id,
                    account_id,
                    money,
                    clean_description,
                    merchant,
                    clean_category,
                    essentiality,
                    occurred,
                    source_document_id,
                    ledger_id,
                    now,
                    now,
                ],
            )
            conn.commit()
            stored = conn.execute(
                f"SELECT {_SOFT_CHARGE_COLUMNS} FROM household_soft_charges WHERE id = %s",
                [soft_id],
            ).fetchone()
        logger.info("soft_charge_created", soft_charge_id=soft_id, amount=float(money), account_id=account_id)
        return _row_to_soft_charge(stored)

    # -- read

    def list_soft_charges(self, *, status: str | None = None, limit: int = 200) -> list[SoftCharge]:
        sql = f"SELECT {_SOFT_CHARGE_COLUMNS} FROM household_soft_charges"
        params: list[Any] = []
        if status:
            sql += " WHERE status = %s"
            params.append(status)
        sql += " ORDER BY occurred_at DESC, created_at DESC LIMIT %s"
        params.append(int(limit))
        with self.storage.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_soft_charge(row) for row in rows]

    # -- manual match (UI "this soft charge is this Plaid row")

    def match_soft_charge(self, soft_id: str, plaid_transaction_id: str) -> SoftCharge:
        now = _now()
        with self.storage.connection() as conn:
            row = conn.execute(
                "SELECT ledger_transaction_id, status FROM household_soft_charges WHERE id = %s",
                [soft_id],
            ).fetchone()
            if row is None:
                raise KeyError(f"Soft charge {soft_id} not found.")
            ledger_id = str(row[0]) if row[0] else None
            conn.execute(
                """
                UPDATE household_soft_charges
                SET status = 'matched', matched_plaid_transaction_id = %s, matched_at = %s,
                    match_confidence = 1.0, match_method = 'manual', updated_at = %s
                WHERE id = %s
                """,
                [plaid_transaction_id, now, now, soft_id],
            )
            if ledger_id:
                conn.execute(
                    "UPDATE household_transactions SET removed = TRUE, updated_at = %s WHERE id = %s",
                    [now, ledger_id],
                )
            conn.commit()
            stored = conn.execute(
                f"SELECT {_SOFT_CHARGE_COLUMNS} FROM household_soft_charges WHERE id = %s",
                [soft_id],
            ).fetchone()
        return _row_to_soft_charge(stored)

    # -- delete / void (remove the provisional spend entirely)

    def delete_soft_charge(self, soft_id: str) -> None:
        now = _now()
        with self.storage.connection() as conn:
            row = conn.execute(
                "SELECT ledger_transaction_id FROM household_soft_charges WHERE id = %s",
                [soft_id],
            ).fetchone()
            if row is None:
                raise KeyError(f"Soft charge {soft_id} not found.")
            ledger_id = str(row[0]) if row[0] else None
            if ledger_id:
                conn.execute(
                    "UPDATE household_transactions SET removed = TRUE, updated_at = %s WHERE id = %s",
                    [now, ledger_id],
                )
            conn.execute(
                "UPDATE household_soft_charges SET status = 'voided', updated_at = %s WHERE id = %s",
                [now, soft_id],
            )
            conn.commit()
        logger.info("soft_charge_voided", soft_charge_id=soft_id)

    # -- daily maintenance: age out unmatched soft charges (mirror row stays).

    def expire_stale(self, *, older_than_days: int = EXPIRE_AFTER_DAYS) -> int:
        cutoff = _now().date() - _td(older_than_days)
        with self.storage.connection() as conn:
            result = conn.execute(
                """
                UPDATE household_soft_charges
                SET status = 'expired', updated_at = %s
                WHERE status = 'pending' AND occurred_at < %s
                """,
                [_now(), cutoff],
            )
            affected = getattr(result, "rowcount", 0) or 0
            conn.commit()
        if affected:
            logger.info("soft_charges_expired", count=int(affected))
        return int(affected)
