"""Receipts and card charges are two records of one purchase, not two purchases."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from app.services.household_receipt_reconciliation_service import (
    HouseholdReceiptReconciliationService,
    _merchant_tokens,
)


class _FakeConnection:
    """Answers the service's two reads and records what it would have written."""

    def __init__(
        self,
        *,
        receipts: list[tuple[Any, ...]],
        candidates: list[tuple[Any, ...]],
        line_items: list[tuple[Any, ...]] | None = None,
        purchase_items: list[tuple[Any, ...]] | None = None,
    ) -> None:
        self._receipts = receipts
        self._candidates = candidates
        self._line_items = line_items or []
        self._purchase_items = purchase_items or []
        self.updates: list[tuple[str, list[Any]]] = []
        self.committed = False

    def execute(self, query: str, parameters: list[Any] | None = None) -> Any:
        if query.strip().startswith("UPDATE"):
            self.updates.append((query, list(parameters or [])))
            return self
        if "household_purchase_items" in query:
            self._last = self._purchase_items
        elif "household_import_rows" in query:
            self._last = self._line_items
        elif "t.metadata" in query:
            self._last = self._receipts
        else:
            self._last = self._candidates
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._last)

    def commit(self) -> None:
        self.committed = True

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class _FakeStorage:
    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    def connection(self) -> _FakeConnection:
        return self._conn


class _FakeService:
    def __init__(self, conn: _FakeConnection) -> None:
        self.storage = _FakeStorage(conn)


def _receipt(
    amount: float,
    *,
    merchant: str = "Walmart",
    transaction_id: str = "receipt-1",
    document_id: str = "doc-1",
) -> tuple[Any, ...]:
    return (
        transaction_id,
        date(2026, 8, 17),
        merchant,
        f"{merchant} receipt",
        amount,
        {},
        document_id,
    )


def _charge(
    charge_id: str, amount: float, *, merchant: str = "WALMART.COM 8009256278"
) -> tuple[Any, ...]:
    return (charge_id, date(2026, 8, 17), merchant, merchant, amount, "Prime Visa")


def _line_item(document_id: str, description: str, amount: float) -> tuple[Any, ...]:
    return (document_id, description, amount)


def _item_updates(conn: _FakeConnection) -> list[list[Any]]:
    return [
        params
        for query, params in conn.updates
        if "household_purchase_items" in query
    ]


def _charge_evidence(conn: _FakeConnection) -> list[dict[str, Any]]:
    return [
        json.loads(params[0])["receipt_evidence"]
        for query, params in conn.updates
        if "household_transactions" in query and "receipt_evidence" in params[0]
    ]


def _retirements(conn: _FakeConnection) -> list[list[Any]]:
    return [params for query, params in conn.updates if "removed = TRUE" in query]


def _reconciliation(conn: _FakeConnection, index: int = 0) -> dict[str, Any]:
    retirements = _retirements(conn)
    assert retirements, "expected the receipt row to be retired"
    metadata = json.loads(retirements[index][0])
    return dict(metadata["reconciliation"])


def test_receipt_is_retired_when_one_charge_carries_the_whole_total() -> None:
    conn = _FakeConnection(
        receipts=[_receipt(54.06)],
        candidates=[_charge("charge-a", 54.06)],
    )

    summary = HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    assert summary == {
        "examined": 1,
        "reconciled": 1,
        "charges_matched": 1,
        "duplicate_receipts": 0,
    }
    assert _reconciliation(conn)["charge_ids"] == ["charge-a"]


def test_receipt_matches_an_order_that_posted_as_two_charges() -> None:
    """A split shipment is one purchase the card reports twice.

    A $54.06 Walmart order that settles as $50.48 and $3.58 is the ordinary
    shape of a pickup with a substitution. Requiring a single charge of the full
    amount leaves the receipt standing as its own spend, and the household is
    billed once but told twice.
    """
    conn = _FakeConnection(
        receipts=[_receipt(54.06)],
        candidates=[_charge("charge-a", 50.48), _charge("charge-b", 3.58)],
    )

    summary = HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    assert summary["reconciled"] == 1
    reconciliation = _reconciliation(conn)
    assert sorted(reconciliation["charge_ids"]) == ["charge-a", "charge-b"]
    assert reconciliation["charge_total"] == 54.06


def test_a_single_charge_is_preferred_over_a_sum_that_also_fits() -> None:
    """The least speculative reading wins when both are arithmetically valid."""
    conn = _FakeConnection(
        receipts=[_receipt(54.06)],
        candidates=[
            _charge("charge-split-a", 50.48),
            _charge("charge-split-b", 3.58),
            _charge("charge-exact", 54.06),
        ],
    )

    HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    assert _reconciliation(conn)["charge_ids"] == ["charge-exact"]


def test_receipt_with_no_matching_charge_stays_as_the_only_record() -> None:
    """Cash, or a card with no feed, leaves the receipt as the household's record."""
    conn = _FakeConnection(
        receipts=[_receipt(54.06)],
        candidates=[_charge("charge-a", 12.00)],
    )

    summary = HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    assert summary == {
        "examined": 1,
        "reconciled": 0,
        "charges_matched": 0,
        "duplicate_receipts": 0,
    }
    assert _retirements(conn) == []


def test_a_charge_at_a_different_merchant_is_not_absorbed() -> None:
    """Same amount, same day, different shop is a coincidence, not a match."""
    conn = _FakeConnection(
        receipts=[_receipt(54.06, merchant="Walmart")],
        candidates=[_charge("charge-a", 54.06, merchant="PUBLIX SUPER MARKET")],
    )

    summary = HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    assert summary["reconciled"] == 0


def test_merchant_tokens_drop_words_too_short_to_identify_anything() -> None:
    assert _merchant_tokens("Walmart Neighborhood Mkt") == {
        "walmart",
        "neighborhood",
    }
    assert _merchant_tokens("A B C") == set()


def test_the_same_receipt_uploaded_twice_is_counted_once() -> None:
    """A re-photographed receipt is a new file describing an old purchase.

    The ingest content hash only catches a byte-identical re-upload. A receipt
    captured again, or re-downloaded from the merchant, sails past it and the
    household is charged once but billed twice in its own totals.
    """
    conn = _FakeConnection(
        receipts=[
            _receipt(54.06, transaction_id="receipt-original", document_id="doc-1"),
            _receipt(54.06, transaction_id="receipt-reupload", document_id="doc-2"),
        ],
        candidates=[],
        line_items=[
            _line_item("doc-1", "bananas", 3.58),
            _line_item("doc-1", "detergent", 50.48),
            _line_item("doc-2", "detergent", 50.48),
            _line_item("doc-2", "bananas", 3.58),
        ],
    )

    summary = HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    assert summary["duplicate_receipts"] == 1
    assert len(_retirements(conn)) == 1
    assert _retirements(conn)[0][1] == "receipt-reupload"
    reconciliation = _reconciliation(conn)
    assert reconciliation["reason"] == "duplicate_receipt_upload"
    assert reconciliation["duplicate_of_transaction_id"] == "receipt-original"


def test_two_trips_that_cost_the_same_are_both_kept() -> None:
    """Identical totals are not proof; identical line items are."""
    conn = _FakeConnection(
        receipts=[
            _receipt(54.06, transaction_id="receipt-morning", document_id="doc-1"),
            _receipt(54.06, transaction_id="receipt-evening", document_id="doc-2"),
        ],
        candidates=[],
        line_items=[
            _line_item("doc-1", "detergent", 54.06),
            _line_item("doc-2", "car charger", 54.06),
        ],
    )

    summary = HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    assert summary["duplicate_receipts"] == 0
    assert _retirements(conn) == []


def test_receipts_without_line_items_are_never_merged_on_resemblance() -> None:
    """With nothing to compare, the safe reading is two separate purchases."""
    conn = _FakeConnection(
        receipts=[
            _receipt(54.06, transaction_id="receipt-a", document_id="doc-1"),
            _receipt(54.06, transaction_id="receipt-b", document_id="doc-2"),
        ],
        candidates=[],
        line_items=[],
    )

    summary = HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    assert summary["duplicate_receipts"] == 0
    assert _retirements(conn) == []


def test_two_identical_purchases_read_off_one_receipt_both_stand() -> None:
    """One document listing a line twice is two real purchases, not a re-upload."""
    conn = _FakeConnection(
        receipts=[
            _receipt(4.79, transaction_id="receipt-a", document_id="doc-1"),
            _receipt(4.79, transaction_id="receipt-b", document_id="doc-1"),
        ],
        candidates=[],
        line_items=[_line_item("doc-1", "coffee", 4.79)],
    )

    summary = HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    assert summary["duplicate_receipts"] == 0
    assert _retirements(conn) == []


def test_the_surviving_copy_is_the_one_matched_against_the_card_feed() -> None:
    """Deduping first keeps the charge on the row the household will still see."""
    conn = _FakeConnection(
        receipts=[
            _receipt(54.06, transaction_id="receipt-original", document_id="doc-1"),
            _receipt(54.06, transaction_id="receipt-reupload", document_id="doc-2"),
        ],
        candidates=[_charge("charge-a", 54.06)],
        line_items=[
            _line_item("doc-1", "detergent", 54.06),
            _line_item("doc-2", "detergent", 54.06),
        ],
    )

    summary = HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    assert summary["duplicate_receipts"] == 1
    assert summary["reconciled"] == 1
    retired = {params[1] for params in _retirements(conn)}
    assert retired == {"receipt-original", "receipt-reupload"}
    assert _reconciliation(conn, 1)["charge_ids"] == ["charge-a"]


def test_line_items_move_to_the_charge_the_household_can_still_see() -> None:
    """The receipt is retired, so its breakdown has to travel or it is lost.

    A card charge says WALMART $54.06 and nothing else. Retiring the receipt row
    hides it from the ledger and the items hang off it, so without this the
    reconciliation would delete the one thing the receipt was kept for.
    """
    conn = _FakeConnection(
        receipts=[_receipt(54.06)],
        candidates=[_charge("charge-a", 54.06)],
        purchase_items=[("item-1", 50.48), ("item-2", 3.58)],
    )

    HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    moved = _item_updates(conn)
    assert [params[0] for params in moved] == ["charge-a", "charge-a"]
    # Allocated cents must land on the charge total exactly, or the split loader
    # drops the transaction and the items count for nothing.
    assert sum(round(params[1] * 100) for params in moved) == 5406


def test_allocation_follows_the_charge_when_tax_makes_it_larger() -> None:
    """Line prices exclude tax; the charge does not. The overhead is spread."""
    conn = _FakeConnection(
        receipts=[_receipt(54.06)],
        candidates=[_charge("charge-a", 54.06)],
        purchase_items=[("item-1", 25.00), ("item-2", 25.00)],
    )

    HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    moved = _item_updates(conn)
    assert sum(round(params[1] * 100) for params in moved) == 5406
    assert {params[1] for params in moved} == {27.03}


def test_a_split_order_keeps_its_items_rather_than_restating_their_prices() -> None:
    """Re-allocating a whole basket onto one leg would misstate every price."""
    conn = _FakeConnection(
        receipts=[_receipt(54.06)],
        candidates=[_charge("charge-a", 50.48), _charge("charge-b", 3.58)],
        purchase_items=[("item-1", 50.48), ("item-2", 3.58)],
    )

    HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    assert _item_updates(conn) == []


def test_both_legs_of_a_split_order_point_back_at_the_receipt() -> None:
    """Items cannot span charges yet, so the link has to be findable from either."""
    conn = _FakeConnection(
        receipts=[_receipt(54.06)],
        candidates=[_charge("charge-a", 50.48), _charge("charge-b", 3.58)],
    )

    HouseholdReceiptReconciliationService().reconcile(_FakeService(conn))

    evidence = _charge_evidence(conn)
    assert len(evidence) == 2
    for entry in evidence:
        assert entry["receipt_transaction_id"] == "receipt-1"
        assert entry["receipt_document_id"] == "doc-1"
        assert entry["receipt_total"] == 54.06
        assert sorted(entry["charge_ids"]) == ["charge-a", "charge-b"]
