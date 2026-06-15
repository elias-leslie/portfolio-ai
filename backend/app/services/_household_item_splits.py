"""Pure helpers that split itemized transactions across item categories.

This module is THE seam between purchase items and budget/spending math.
Splits are persisted once at link time (``allocated_amount``), loaded with a
single GROUP BY, and applied to report rows only inside category-level
aggregations. ``expand_rows_with_item_splits`` with empty splits is identity,
which is the regression guarantee that un-itemized figures never move.
"""

from __future__ import annotations

from typing import Any

ItemSplit = dict[str, Any]


def allocate_overhead_cents(line_cents: list[int], transaction_cents: int) -> list[int]:
    """Allocate a transaction total across line items, integer cents, exact sum.

    Each line receives its printed amount plus a proportional share of the
    overhead (tax, fees, or negative discounts) so the result sums to
    ``transaction_cents`` exactly. Largest-remainder rounding; lines with a
    zero base split overhead equally.
    """
    if not line_cents:
        return []
    base = sum(line_cents)
    if base == transaction_cents:
        return list(line_cents)
    if base == 0:
        share, leftover = divmod(transaction_cents, len(line_cents))
        return [share + (1 if index < leftover else 0) for index in range(len(line_cents))]
    floors: list[int] = []
    remainders: list[tuple[int, int]] = []
    for index, line in enumerate(line_cents):
        exact_numerator = line * transaction_cents
        floor, remainder = divmod(exact_numerator, base)
        floors.append(floor)
        remainders.append((remainder, index))
    leftover = transaction_cents - sum(floors)
    # divmod with a positive base keeps 0 <= remainder < base, so leftover is
    # the count of +1 cents to hand out; with a negative base the same holds
    # with signs flipped, which sorting by remainder still resolves.
    for _, index in sorted(remainders, key=lambda entry: (-entry[0], entry[1]))[: abs(leftover)]:
        floors[index] += 1 if leftover > 0 else -1
    return floors


def load_item_splits(conn: Any) -> dict[str, list[ItemSplit]]:
    """Load per-transaction category splits from persisted purchase items.

    One GROUP BY over linked, allocated, non-removed items. Transactions whose
    allocated cents do not sum exactly to the transaction amount are dropped
    here, which falls those rows back to transaction-level categorization at
    read time.
    """
    rows = conn.execute(
        """
        SELECT
            i.transaction_id::text,
            i.category,
            i.essentiality,
            NULLIF(TRIM(i.metadata ->> 'owner_name'), ''),
            SUM(i.allocated_amount),
            COUNT(*),
            MAX(CAST(t.amount AS DOUBLE PRECISION))
        FROM household_purchase_items i
        JOIN household_transactions t ON t.id = i.transaction_id
        WHERE i.transaction_id IS NOT NULL
          AND i.allocated_amount IS NOT NULL
          AND i.removed IS NOT TRUE
          AND t.removed IS NOT TRUE
        GROUP BY i.transaction_id, i.category, i.essentiality, NULLIF(TRIM(i.metadata ->> 'owner_name'), '')
        """
    ).fetchall()

    by_transaction: dict[str, list[ItemSplit]] = {}
    transaction_amount_cents: dict[str, int] = {}
    allocated_cents: dict[str, int] = {}
    for row in rows:
        transaction_id = str(row[0])
        amount = float(row[4] or 0.0)
        by_transaction.setdefault(transaction_id, []).append(
            {
                "category": str(row[1] or ""),
                "essentiality": str(row[2] or ""),
                "owner_name": str(row[3]) if row[3] else None,
                "amount": round(amount, 2),
                "item_count": int(row[5] or 0),
            }
        )
        transaction_amount_cents[transaction_id] = round(float(row[6] or 0.0) * 100)
        allocated_cents[transaction_id] = allocated_cents.get(transaction_id, 0) + round(
            amount * 100
        )

    return {
        transaction_id: splits
        for transaction_id, splits in by_transaction.items()
        if allocated_cents.get(transaction_id) == transaction_amount_cents.get(transaction_id)
    }


def split_identity(row: dict[str, Any]) -> str:
    """Identity for distinct-transaction counts across split copies."""
    return str(row.get("split_parent_id") or row.get("id") or "")


def expand_rows_with_item_splits(
    rows: list[dict[str, Any]],
    splits: dict[str, list[ItemSplit]],
) -> list[dict[str, Any]]:
    """Replace itemized rows with per-category split copies.

    Empty splits is identity (returns ``rows`` unchanged). Split copies carry
    ``split_parent_id`` and ``is_item_split`` so consumers can count distinct
    transactions instead of split rows. Rows whose split parts no longer sum
    to the row amount (or refund rows) pass through unchanged.
    """
    if not splits:
        return rows
    expanded: list[dict[str, Any]] = []
    for row in rows:
        row_splits = splits.get(str(row.get("id") or ""))
        signed_amount = float(row.get("signed_amount", row.get("amount", 0.0)))
        if (
            not row_splits
            or row.get("source_kind") == "import"
            or signed_amount < 0
            or abs(sum(part["amount"] for part in row_splits) - signed_amount) > 0.005
        ):
            expanded.append(row)
            continue
        for index, part in enumerate(row_splits):
            split_row = dict(row)
            split_row["id"] = f"{row['id']}::{index}"
            split_row["split_parent_id"] = str(row["id"])
            split_row["is_item_split"] = True
            split_row["category"] = part["category"]
            split_row["essentiality"] = part["essentiality"]
            split_row["amount"] = part["amount"]
            split_row["signed_amount"] = part["amount"]
            expanded.append(split_row)
    return expanded
