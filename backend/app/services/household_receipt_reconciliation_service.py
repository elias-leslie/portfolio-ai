"""Reconcile receipt-derived spend against the card feed that already carries it.

A receipt and a card charge are two records of one purchase. Ingesting both as
spend counts the money twice, and the household sees a total it cannot square
with its own statement. The card feed is what actually moved money, so it stays;
the receipt keeps its real job, which is the line-item detail the feed does not
carry -- a card charge says ``WALMART $54.06`` and the receipt says what was in
the bag.

Matching is not a single-amount lookup, because one order routinely posts as
several charges: a split shipment, a pickup with a substitution, a partial
fulfilment. A receipt total that equals the sum of two or three charges at the
same merchant in the same few days is that order, not a coincidence, so the
reconciliation looks for small sets and not just a twin.

The same purchase can also arrive twice as a receipt. A byte-identical re-upload
is caught at ingest by its content hash, but a receipt photographed a second time
or re-downloaded is a different file describing the same trip, and nothing
upstream compares them. Two receipts are treated as one only on proof, not on
resemblance: same merchant, same date, same total, and an identical set of line
items. Matching totals alone would collapse two genuine trips that happened to
cost the same.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from itertools import combinations
from typing import Any

from app.logging_config import get_logger
from app.services._household_item_splits import allocate_overhead_cents

logger = get_logger(__name__)

# How far a receipt and its charge may sit apart. A card charge posts the same
# day or the next business day; a weekend pushes it to three.
_WINDOW_DAYS = 4
# One order splitting into more than three postings is rare enough that treating
# a four-way sum as the same purchase risks absorbing an unrelated charge.
_MAX_CHARGES = 3
_CENT = 0.005

_RECEIPT_SOURCES = ("receipt_summary", "receipt_transaction")
_FEED_SOURCES = ("plaid", "statement_csv", "statement_activity", "bank_statement")


def _sql_in(values: tuple[str, ...]) -> str:
    """Render a literal IN list. A tuple repr would emit a trailing comma at one
    element and stop being SQL, which is a bad way to find out the set shrank."""
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"

_RECEIPT_ROWS_SQL = f"""
    SELECT t.id, t.transaction_date, t.raw_merchant, t.description,
           CAST(t.amount AS DOUBLE PRECISION), t.metadata, t.document_id
    FROM household_transactions t
    WHERE t.removed IS NOT TRUE
      AND t.flow_type = 'expense'
      AND t.source_system IN {_sql_in(_RECEIPT_SOURCES)}
    ORDER BY t.transaction_date ASC, t.id ASC
    LIMIT %s
"""

_CANDIDATE_SQL = f"""
    SELECT t.id, t.transaction_date, t.raw_merchant, t.description,
           CAST(t.amount AS DOUBLE PRECISION), t.account_label
    FROM household_transactions t
    WHERE t.removed IS NOT TRUE
      AND t.flow_type = 'expense'
      AND t.source_system IN {_sql_in(_FEED_SOURCES)}
      AND t.transaction_date >= %s - INTERVAL '{_WINDOW_DAYS} days'
      AND t.transaction_date <= %s + INTERVAL '{_WINDOW_DAYS} days'
      -- jsonb_exists rather than the containment operator: the driver reads
      -- that operator's character as a placeholder, even inside a comment, and
      -- the statement stops parsing.
      AND NOT EXISTS (
          SELECT 1 FROM household_transactions r
          WHERE r.removed
            AND jsonb_exists(
                r.metadata -> 'reconciliation' -> 'charge_ids', t.id::text
            )
      )
    ORDER BY t.transaction_date ASC, t.id ASC
"""

# Line items are what make two receipts provably the same trip rather than two
# trips that cost the same. Ordering happens in Python so a NULL amount and a
# NULL description sort the same way on either side of the comparison.
_LINE_ITEM_SQL = """
    SELECT document_id, LOWER(COALESCE(description, '')),
           ROUND(CAST(COALESCE(amount, 0) AS numeric), 2)
    FROM household_import_rows
    WHERE dataset_type = 'receipt_line_items'
      AND document_id = ANY(%s)
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _merchant_tokens(*values: object) -> set[str]:
    """Words long enough to identify a merchant across two spellings of it.

    A receipt says ``Walmart`` where the feed says ``WALMART.COM 8009256278``.
    Short words carry no signal and would match anything, so they are dropped
    rather than weighted.
    """
    tokens: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        tokens.update(
            token for token in re.split(r"[^a-z0-9]+", value.lower()) if len(token) >= 4
        )
    return tokens


def _load_metadata(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


class HouseholdReceiptReconciliationService:
    """Retire receipt spend the card feed already accounts for."""

    def reconcile(self, service: Any, *, limit: int = 200) -> dict[str, int]:
        """Match live receipt rows to feed charges and retire the matches.

        Runs over every live receipt row rather than one document's, because the
        two halves of a purchase arrive in either order: a receipt captured in
        the store is days ahead of the charge that settles it. Whichever lands
        second is the one that closes the pair.
        """
        summary = {
            "examined": 0,
            "reconciled": 0,
            "charges_matched": 0,
            "duplicate_receipts": 0,
        }
        with service.storage.connection() as conn:
            receipts = conn.execute(_RECEIPT_ROWS_SQL, [limit]).fetchall()
            summary["examined"] = len(receipts)
            batch_id = str(uuid.uuid4())
            # Duplicates go first so the copy that survives is the one offered to
            # the card feed. Matching a doomed row would spend the charge on it
            # and leave its twin looking like unmatched spend.
            receipts = self._retire_duplicate_receipts(
                conn, receipts=receipts, batch_id=batch_id, summary=summary
            )
            claimed: set[str] = set()
            for receipt in receipts:
                matched = self._match_receipt(conn, receipt=receipt, claimed=claimed)
                if not matched:
                    continue
                self._retire_receipt_row(
                    conn, receipt=receipt, charges=matched, batch_id=batch_id
                )
                claimed.update(str(charge[0]) for charge in matched)
                summary["reconciled"] += 1
                summary["charges_matched"] += len(matched)
            conn.commit()
        if summary["reconciled"] or summary["duplicate_receipts"]:
            logger.info("household_receipts_reconciled", **summary)
        return summary

    def _retire_duplicate_receipts(
        self,
        conn: Any,
        *,
        receipts: list[tuple[Any, ...]],
        batch_id: str,
        summary: dict[str, int],
    ) -> list[tuple[Any, ...]]:
        """Drop re-uploads of a receipt already on file, returning the survivors.

        Only rows from *different* documents are compared. Two lines within one
        document are two real purchases the parser read off one page.
        """
        groups: dict[tuple[Any, ...], list[tuple[Any, ...]]] = {}
        for receipt in receipts:
            key = (
                receipt[1],
                round(float(receipt[4] or 0.0), 2),
                frozenset(_merchant_tokens(receipt[2], receipt[3])),
            )
            groups.setdefault(key, []).append(receipt)

        contested = [
            rows
            for key, rows in groups.items()
            if key[2] and len({str(row[6]) for row in rows if row[6]}) > 1
        ]
        if not contested:
            return receipts

        document_ids = sorted(
            {str(row[6]) for rows in contested for row in rows if row[6]}
        )
        fingerprints = self._line_item_fingerprints(conn, document_ids=document_ids)

        retired: set[str] = set()
        for rows in contested:
            seen: dict[tuple[Any, ...], tuple[Any, ...]] = {}
            for row in rows:
                fingerprint = fingerprints.get(str(row[6]))
                if not fingerprint:
                    # No line items means no proof. An unparsed receipt stays as
                    # its own record rather than being merged on resemblance.
                    continue
                original = seen.get(fingerprint)
                if original is None:
                    seen[fingerprint] = row
                    continue
                self._retire_receipt_row(
                    conn,
                    receipt=row,
                    charges=[],
                    batch_id=batch_id,
                    duplicate_of=original,
                )
                retired.add(str(row[0]))
                summary["duplicate_receipts"] += 1
        if not retired:
            return receipts
        return [row for row in receipts if str(row[0]) not in retired]

    def _line_item_fingerprints(
        self, conn: Any, *, document_ids: list[str]
    ) -> dict[str, tuple[tuple[str, float], ...]]:
        items: dict[str, list[tuple[str, float]]] = {}
        for row in conn.execute(_LINE_ITEM_SQL, [document_ids]).fetchall():
            items.setdefault(str(row[0]), []).append((str(row[1]), float(row[2])))
        return {
            document_id: tuple(sorted(lines)) for document_id, lines in items.items()
        }

    def _match_receipt(
        self,
        conn: Any,
        *,
        receipt: tuple[Any, ...],
        claimed: set[str],
    ) -> list[tuple[Any, ...]]:
        total = float(receipt[4] or 0.0)
        if total <= 0:
            return []
        receipt_tokens = _merchant_tokens(receipt[2], receipt[3])
        if not receipt_tokens:
            return []
        candidates = [
            row
            for row in conn.execute(_CANDIDATE_SQL, [receipt[1], receipt[1]]).fetchall()
            if str(row[0]) not in claimed
            and receipt_tokens & _merchant_tokens(row[2], row[3])
        ]
        if not candidates:
            return []
        # A single charge for the whole receipt is the ordinary case and the
        # least speculative reading, so it is settled before any sum is tried.
        for size in range(1, _MAX_CHARGES + 1):
            for combination in combinations(candidates, size):
                if abs(sum(float(row[4] or 0.0) for row in combination) - total) <= _CENT:
                    return list(combination)
        return []

    def _retire_receipt_row(
        self,
        conn: Any,
        *,
        receipt: tuple[Any, ...],
        charges: list[tuple[Any, ...]],
        batch_id: str,
        duplicate_of: tuple[Any, ...] | None = None,
    ) -> None:
        metadata = _load_metadata(receipt[5])
        if duplicate_of is not None:
            metadata["reconciliation"] = {
                "reason": "duplicate_receipt_upload",
                "batch_id": batch_id,
                "duplicate_of_transaction_id": str(duplicate_of[0]),
                "duplicate_of_document_id": str(duplicate_of[6] or ""),
                "reconciled_at": _now_iso(),
                "note": (
                    "This receipt was already on file under another upload, with "
                    "the same merchant, date, total and line items."
                ),
            }
            self._write_metadata(conn, receipt=receipt, metadata=metadata)
            return
        metadata["reconciliation"] = {
            "reason": "card_feed_carries_this_purchase",
            "batch_id": batch_id,
            "charge_ids": [str(charge[0]) for charge in charges],
            "charge_total": round(sum(float(charge[4] or 0.0) for charge in charges), 2),
            "reconciled_at": _now_iso(),
            "note": (
                "The card feed already records this purchase"
                + (
                    f" as {len(charges)} charges"
                    if len(charges) > 1
                    else ""
                )
                + ". The receipt stays as its line-item evidence."
            ),
        }
        self._write_metadata(conn, receipt=receipt, metadata=metadata)
        self._carry_evidence_to_charge(conn, receipt=receipt, charges=charges)

    def _carry_evidence_to_charge(
        self,
        conn: Any,
        *,
        receipt: tuple[Any, ...],
        charges: list[tuple[Any, ...]],
    ) -> None:
        """Move the receipt's line items onto the charge that survives.

        Retiring the receipt row hides it from the ledger, and its line items
        hang off it -- so the breakdown the receipt exists to provide would go
        with it. The items belong on the charge the household can actually see.

        Only a one-charge match is moved. Splitting a basket across two charges
        would mean inventing which items landed on which, and re-allocating the
        whole basket against one leg would restate what every item cost -- the
        one number a receipt is trusted for. Those stay put until an item can
        span charges; the reciprocal ids below keep the pair discoverable.
        """
        for charge in charges:
            conn.execute(
                """
                UPDATE household_transactions
                SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [
                    json.dumps(
                        {
                            "receipt_evidence": {
                                "receipt_transaction_id": str(receipt[0]),
                                "receipt_document_id": str(receipt[6] or ""),
                                "receipt_total": round(float(receipt[4] or 0.0), 2),
                                "charge_ids": [str(row[0]) for row in charges],
                            }
                        }
                    ),
                    charge[0],
                ],
            )
        if len(charges) != 1:
            return
        items = conn.execute(
            """
            SELECT id, CAST(COALESCE(amount, 0) AS DOUBLE PRECISION)
            FROM household_purchase_items
            WHERE transaction_id = %s AND removed IS NOT TRUE
            ORDER BY id
            """,
            [receipt[0]],
        ).fetchall()
        if not items:
            return
        # Re-allocate rather than only re-point: the split loader drops any
        # transaction whose allocated cents miss the transaction amount, so an
        # untouched allocation would leave the items linked but uncounted.
        allocated = allocate_overhead_cents(
            [round(float(item[1] or 0.0) * 100) for item in items],
            round(float(charges[0][4] or 0.0) * 100),
        )
        for item, cents in zip(items, allocated, strict=True):
            conn.execute(
                """
                UPDATE household_purchase_items
                SET transaction_id = %s,
                    allocated_amount = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [charges[0][0], cents / 100.0, item[0]],
            )
        logger.info(
            "household_receipt_items_carried_to_charge",
            receipt_transaction_id=str(receipt[0]),
            charge_id=str(charges[0][0]),
            items=len(items),
        )

    def _write_metadata(
        self, conn: Any, *, receipt: tuple[Any, ...], metadata: dict[str, Any]
    ) -> None:
        """Retire a row without deleting it: the audit trail is the point."""
        conn.execute(
            """
            UPDATE household_transactions
            SET removed = TRUE,
                metadata = %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            [json.dumps(metadata), receipt[0]],
        )
