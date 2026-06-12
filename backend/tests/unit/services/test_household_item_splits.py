"""Unit tests for the purchase-item budget-split seam."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services._household_item_splits import (
    allocate_overhead_cents,
    expand_rows_with_item_splits,
    load_item_splits,
    split_identity,
)


def _row(
    *,
    row_id: str = "tx-1",
    amount: float = 34.96,
    category: str = "Retail",
    essentiality: str = "discretionary",
    source_kind: str = "transaction",
) -> dict[str, Any]:
    return {
        "id": row_id,
        "date": date(2026, 5, 4),
        "merchant": "Ulta Beauty",
        "description": "ULTA #123",
        "amount": amount,
        "signed_amount": amount,
        "category": category,
        "essentiality": essentiality,
        "source_kind": source_kind,
    }


# ---------------------------------------------------------------------------
# allocate_overhead_cents
# ---------------------------------------------------------------------------


def test_allocate_overhead_distributes_tax_proportionally_and_sums_exactly() -> None:
    # $28.00 + $4.99 lines against a $34.96 charge ($1.97 tax/fees overhead).
    allocated = allocate_overhead_cents([2800, 499], 3496)
    assert sum(allocated) == 3496
    assert allocated[0] > 2800 and allocated[1] > 499
    # Larger line absorbs the larger overhead share.
    assert allocated[0] - 2800 > allocated[1] - 499


def test_allocate_overhead_handles_negative_overhead_discounts() -> None:
    allocated = allocate_overhead_cents([1000, 1000, 1000], 2850)
    assert sum(allocated) == 2850
    assert all(cents < 1000 for cents in allocated)


def test_allocate_overhead_identity_when_lines_already_reconcile() -> None:
    assert allocate_overhead_cents([1250, 750], 2000) == [1250, 750]


def test_allocate_overhead_zero_base_splits_equally() -> None:
    allocated = allocate_overhead_cents([0, 0, 0], 1000)
    assert sum(allocated) == 1000
    assert sorted(allocated) == [333, 333, 334]


def test_allocate_overhead_empty_lines() -> None:
    assert allocate_overhead_cents([], 1000) == []


def test_allocate_overhead_awkward_thirds_sum_exactly() -> None:
    allocated = allocate_overhead_cents([100, 100, 100], 1000)
    assert sum(allocated) == 1000


# ---------------------------------------------------------------------------
# expand_rows_with_item_splits
# ---------------------------------------------------------------------------


def test_expand_with_empty_splits_is_identity() -> None:
    rows = [_row(), _row(row_id="tx-2", amount=12.5)]
    assert expand_rows_with_item_splits(rows, {}) is rows


def test_expand_replaces_itemized_row_with_category_split_copies() -> None:
    rows = [_row(), _row(row_id="tx-2", amount=12.5)]
    splits = {
        "tx-1": [
            {"category": "Personal Care", "essentiality": "discretionary", "amount": 29.97, "item_count": 1},
            {"category": "Household", "essentiality": "mixed", "amount": 4.99, "item_count": 1},
        ]
    }
    expanded = expand_rows_with_item_splits(rows, splits)
    assert len(expanded) == 3
    split_rows = [row for row in expanded if row.get("is_item_split")]
    assert {row["category"] for row in split_rows} == {"Personal Care", "Household"}
    assert all(row["split_parent_id"] == "tx-1" for row in split_rows)
    assert round(sum(row["signed_amount"] for row in split_rows), 2) == 34.96
    assert {split_identity(row) for row in split_rows} == {"tx-1"}
    # The un-itemized row passes through byte-identical.
    assert expanded[-1] is rows[-1]


def test_expand_leaves_refund_rows_alone() -> None:
    refund = _row()
    refund["signed_amount"] = -34.96
    splits = {
        "tx-1": [
            {"category": "Personal Care", "essentiality": "discretionary", "amount": 34.96, "item_count": 1}
        ]
    }
    expanded = expand_rows_with_item_splits([refund], splits)
    assert expanded == [refund]


def test_expand_falls_back_when_split_amounts_drift_from_row_amount() -> None:
    rows = [_row()]
    splits = {
        "tx-1": [
            {"category": "Personal Care", "essentiality": "discretionary", "amount": 20.0, "item_count": 1}
        ]
    }
    expanded = expand_rows_with_item_splits(rows, splits)
    assert expanded == rows


# ---------------------------------------------------------------------------
# load_item_splits
# ---------------------------------------------------------------------------


class _SplitConn:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def execute(self, sql: str, params: list[Any] | None = None) -> _SplitConn:
        del sql, params
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


def test_load_item_splits_keeps_exact_sums_and_drops_drifted_transactions() -> None:
    rows = [
        # tx-good: 29.97 + 4.99 == 34.96 transaction amount.
        ("tx-good", "Personal Care", "discretionary", 29.97, 1, 34.96),
        ("tx-good", "Household", "mixed", 4.99, 1, 34.96),
        # tx-drift: allocated 20.00 vs amount 25.00 -> dropped.
        ("tx-drift", "Groceries", "essential", 20.0, 2, 25.0),
    ]
    splits = load_item_splits(_SplitConn(rows))
    assert set(splits) == {"tx-good"}
    assert {part["category"] for part in splits["tx-good"]} == {"Personal Care", "Household"}
    assert round(sum(part["amount"] for part in splits["tx-good"]), 2) == 34.96
