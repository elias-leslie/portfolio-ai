"""How much of the item layer is tied to money, and why the rest is not.

Counting linked items against every item ever imported answers a question
nobody asked. An Amazon order from 2014 has no charge to find: the ledger's
oldest transaction is years younger than it, and no amount of matching will
change that. The share worth reporting is over the items whose charge could
plausibly be in the ledger at all -- bought on an account the household has a
feed for, inside the window that feed covers -- and every item outside that
share is owed a reason instead of a silent pending.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

# Ordered worst-explained first: an unmatched item is a matching failure, the
# rest are limits of what the household has connected.
_BUCKET_LABELS: dict[str, tuple[str, str]] = {
    "linked": ("Tied to a charge", "the item and the money are the same event"),
    "unmatched": (
        "No charge found",
        "bought on a card we have a feed for, on a day the feed covers, and still nothing matched",
    ),
    "before_feed": (
        "Older than the feed",
        "bought on a known card before that account's feed begins",
    ),
    "no_spending_feed": (
        "Account has no feed",
        "the card that paid is in the registry but sends us no transactions",
    ),
    "card_not_in_registry": (
        "Card we don't know",
        "the source names a card no account claims",
    ),
    "card_retired_by_then": (
        "Card was already replaced",
        "an account carried this number once, but not on the day of this purchase",
    ),
    "card_claimed_twice": (
        "Two accounts, one number",
        "more than one account claims these four digits for that day, so neither is assumed",
    ),
    "no_card_named": (
        "No card named",
        "the source never said what paid — a gift balance, or a blank field",
    ),
}


@dataclass
class _Bucket:
    state: str
    item_count: int = 0
    amount: float = 0.0
    masks: set[str] = field(default_factory=set)


@dataclass
class UnknownCard:
    mask: str
    item_count: int
    amount: float
    first_seen: date | None
    last_seen: date | None


@dataclass
class LinkageCoverage:
    generated_at: str
    total_items: int
    linked_items: int
    addressable_items: int
    addressable_linked_share: float | None
    buckets: list[dict[str, Any]]
    unknown_cards: list[UnknownCard]
    feed_starts_on: date | None


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


_UNRESOLVED_CARD_STATES = {
    "outside_card_window": "card_retired_by_then",
    "ambiguous_card": "card_claimed_twice",
}


def classify_item(
    *,
    transaction_id: Any,
    paid_account_id: str | None,
    card_mask: str | None,
    purchase_day: date | None,
    feed_starts: dict[str, date],
    card_state: str | None = None,
) -> str:
    """Which bucket an item falls in, and therefore what it is owed."""
    if transaction_id is not None:
        return "linked"
    if not paid_account_id:
        if card_state in _UNRESOLVED_CARD_STATES:
            return _UNRESOLVED_CARD_STATES[card_state]
        return "card_not_in_registry" if card_mask else "no_card_named"
    account_start = feed_starts.get(paid_account_id)
    if account_start is None:
        return "no_spending_feed"
    if purchase_day is not None and purchase_day < account_start:
        return "before_feed"
    return "unmatched"


def build_linkage_coverage(conn: Any) -> LinkageCoverage:
    feed_rows = conn.execute(
        """
        SELECT household_account_id::text, MIN(transaction_date)::date
        FROM household_transactions
        WHERE flow_type = 'expense'
          AND removed IS NOT TRUE
          AND household_account_id IS NOT NULL
        GROUP BY household_account_id
        """
    ).fetchall()
    feed_starts: dict[str, date] = {}
    for row in feed_rows:
        start = _as_date(row[1])
        if start is not None:
            feed_starts[str(row[0])] = start

    item_rows = conn.execute(
        """
        SELECT i.transaction_id,
               i.metadata->>'paid_account_id',
               i.metadata->>'card_mask',
               i.purchase_date::date,
               COALESCE(i.allocated_amount, i.amount, 0),
               i.metadata->>'paid_account_state'
        FROM household_purchase_items i
        WHERE i.removed IS NOT TRUE
        """
    ).fetchall()

    buckets: dict[str, _Bucket] = {state: _Bucket(state=state) for state in _BUCKET_LABELS}
    unknown: dict[str, _Bucket] = {}
    unknown_days: dict[str, list[date]] = {}
    for transaction_id, paid_account_id, card_mask, purchase_day, amount, card_state in item_rows:
        day = _as_date(purchase_day)
        state = classify_item(
            transaction_id=transaction_id,
            paid_account_id=str(paid_account_id) if paid_account_id else None,
            card_mask=str(card_mask) if card_mask else None,
            purchase_day=day,
            feed_starts=feed_starts,
            card_state=str(card_state) if card_state else None,
        )
        bucket = buckets[state]
        bucket.item_count += 1
        bucket.amount += float(amount or 0.0)
        if state == "card_not_in_registry" and card_mask:
            mask = str(card_mask)
            entry = unknown.setdefault(mask, _Bucket(state=mask))
            entry.item_count += 1
            entry.amount += float(amount or 0.0)
            if day is not None:
                unknown_days.setdefault(mask, []).append(day)

    total_items = len(item_rows)
    linked_items = buckets["linked"].item_count
    # An item is addressable when its charge could be in the ledger: the card is
    # known, the account reports, and the purchase falls inside what it reports.
    addressable = linked_items + buckets["unmatched"].item_count
    unknown_cards = sorted(
        (
            UnknownCard(
                mask=mask,
                item_count=entry.item_count,
                amount=round(entry.amount, 2),
                first_seen=min(unknown_days.get(mask), default=None),
                last_seen=max(unknown_days.get(mask), default=None),
            )
            for mask, entry in unknown.items()
        ),
        key=lambda card: card.item_count,
        reverse=True,
    )
    ordered = [
        {
            "state": state,
            "label": _BUCKET_LABELS[state][0],
            "detail": _BUCKET_LABELS[state][1],
            "item_count": buckets[state].item_count,
            "amount": round(buckets[state].amount, 2),
        }
        for state in _BUCKET_LABELS
        if buckets[state].item_count
    ]
    return LinkageCoverage(
        generated_at=datetime.now(UTC).isoformat(),
        total_items=total_items,
        linked_items=linked_items,
        addressable_items=addressable,
        addressable_linked_share=(round(linked_items / addressable, 4) if addressable else None),
        buckets=ordered,
        unknown_cards=unknown_cards,
        feed_starts_on=min(feed_starts.values(), default=None),
    )
