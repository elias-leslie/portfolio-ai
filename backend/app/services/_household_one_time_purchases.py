"""Tell a month's spending apart from the one purchase that *was* the month.

"We were over budget because of this one purchase but everything else was under"
is one of the four sentences the review screen has to be able to answer (D2.3).
It cannot be answered from a category total, because a $11,633 air conditioner
and a year of groceries both land in a bar labelled "Household".

The test is deliberately conservative, because wrongly setting a purchase aside
understates real spending -- which is the failure this whole revamp exists to
stop. A purchase is only set aside when all three hold: it is large in absolute
terms, it is a large share of its own month, and the merchant has never charged
anything like it in any other month on record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Below this a purchase is ordinary however unusual its shape, and calling it
# one-time would let a $300 flight rewrite a month.
ABSOLUTE_FLOOR = 1000.0

# A purchase has to be a real slice of its own month before it can be blamed for it.
MIN_SHARE_OF_MONTH = 0.20

# A prior charge at this fraction of the candidate is precedent: the merchant has
# billed at this scale before, so this month is not an exception.
PRECEDENT_RATIO = 0.5


@dataclass(frozen=True)
class OneTimePurchase:
    transaction_id: str
    date: Any
    merchant: str
    category: str
    amount: float
    share_of_month: float
    reason: str


def _merchant_key(row: dict[str, Any]) -> str:
    return str(row.get("merchant") or "").strip().lower()


def find_one_time_purchases(
    month_rows: list[dict[str, Any]],
    *,
    history_rows: list[dict[str, Any]],
    month_total: float,
) -> list[OneTimePurchase]:
    """Purchases in `month_rows` that the rest of the ledger has no precedent for.

    `history_rows` is every spend row on record, this month's included; rows from
    the reported month are ignored when looking for precedent, so an order split
    across two cards on the same day does not become its own precedent.
    """
    if month_total <= 0:
        return []

    month_ids = {str(row.get("id")) for row in month_rows}
    precedent_by_merchant: dict[str, float] = {}
    for row in history_rows:
        if str(row.get("id")) in month_ids:
            continue
        amount = float(row.get("signed_amount", row.get("amount", 0.0)) or 0.0)
        if amount <= 0:
            continue
        key = _merchant_key(row)
        precedent_by_merchant[key] = max(precedent_by_merchant.get(key, 0.0), amount)

    found: list[OneTimePurchase] = []
    for row in month_rows:
        amount = float(row.get("signed_amount", row.get("amount", 0.0)) or 0.0)
        if amount < ABSOLUTE_FLOOR:
            continue
        share = amount / month_total
        if share < MIN_SHARE_OF_MONTH:
            continue
        largest_before = precedent_by_merchant.get(_merchant_key(row), 0.0)
        if largest_before >= amount * PRECEDENT_RATIO:
            continue
        merchant = str(row.get("merchant") or "").strip() or "Unknown merchant"
        found.append(
            OneTimePurchase(
                transaction_id=str(row.get("id")),
                date=row.get("date"),
                merchant=merchant,
                category=str(row.get("category") or ""),
                amount=round(amount, 2),
                share_of_month=round(share, 4),
                reason=(
                    f"{share:.0%} of the month on its own, and the largest "
                    f"{merchant} charge in any other month on record is "
                    f"${largest_before:,.2f}"
                ),
            )
        )
    return sorted(found, key=lambda item: item.amount, reverse=True)
