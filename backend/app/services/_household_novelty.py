"""Merchants the household has never paid before, grouped into what they were.

D2's fourth sentence -- "we were over because of these 4 items Mariana bought
that she never buys" -- needs two things the ledger cannot currently say. This
module supplies the first: which merchants are genuinely new this month.

The grouping matters as much as the detection. July 2026 has 44 charges at 34
merchants the ledger has never seen, and listing them is 34 mystery lines that
tell the reader nothing. Almost all of them are two trips: a run of new places
between the 2nd and the 13th, and another between the 19th and the 29th.
Presented as two clusters they are recognisable at a glance; presented as a list
they look like fraud.

Clusters are built from **dates alone**, because dates are what the ledger
actually knows. There is no location on these rows -- the Plaid metadata carries
an item id and a transaction id and nothing else -- so this module never claims a
place. "13 new places over 12 days, mostly Dining" is checkable; "the El Salvador
trip" would be a guess dressed as a fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

# Two days apart is the same outing; three is a different week. At three the
# whole of July 2026 collapses into one cluster, which is the same failure as
# not clustering at all.
MAX_CLUSTER_GAP_DAYS = 2

# Below this it is not a pattern, it is a merchant. Shown, but on its own.
MIN_CLUSTER_MERCHANTS = 3


@dataclass(frozen=True)
class NewMerchant:
    merchant: str
    category: str
    amount: float
    transaction_count: int
    first_seen: date


@dataclass(frozen=True)
class NoveltyCluster:
    key: str
    label: str
    detail: str
    start_date: date
    end_date: date
    total: float
    merchant_count: int
    transaction_count: int
    is_cluster: bool
    merchants: list[NewMerchant]


def _merchant_key(row: dict[str, Any]) -> str:
    return str(row.get("merchant") or "").strip().lower()


def _amount(row: dict[str, Any]) -> float:
    return float(row.get("signed_amount", row.get("amount", 0.0)) or 0.0)


def _dominant_category(merchants: list[NewMerchant]) -> str | None:
    totals: dict[str, float] = {}
    for merchant in merchants:
        if not merchant.category:
            continue
        totals[merchant.category] = totals.get(merchant.category, 0.0) + merchant.amount
    if not totals:
        return None
    leader, leader_total = max(totals.items(), key=lambda item: item[1])
    overall = sum(totals.values())
    return leader if overall > 0 and leader_total / overall >= 0.35 else None


def _span_text(start: date, end: date) -> str:
    if start == end:
        return start.strftime("%-d %B")
    if start.month == end.month:
        return f"{start.day}-{end.day} {end.strftime('%B')}"
    return f"{start.strftime('%-d %b')} to {end.strftime('%-d %b')}"


def find_new_merchants(
    month_rows: list[dict[str, Any]],
    *,
    history_rows: list[dict[str, Any]],
    coverage_months: int = 0,
) -> list[NoveltyCluster]:
    """New-to-the-ledger merchants in `month_rows`, grouped by when they happened.

    `history_rows` is every spend row on record, this month's included; rows from
    the reported month are ignored when deciding what counts as history, so a
    merchant visited twice in one week does not become its own precedent.
    """
    month_ids = {str(row.get("id")) for row in month_rows}
    known: set[str] = {
        _merchant_key(row)
        for row in history_rows
        if str(row.get("id")) not in month_ids
    }

    by_merchant: dict[str, dict[str, Any]] = {}
    for row in month_rows:
        key = _merchant_key(row)
        if not key or key in known:
            continue
        amount = _amount(row)
        if amount <= 0:
            continue
        bucket = by_merchant.setdefault(
            key,
            {
                "merchant": str(row.get("merchant") or "").strip(),
                "category": str(row.get("category") or ""),
                "amount": 0.0,
                "count": 0,
                "first_seen": row["date"],
            },
        )
        bucket["amount"] += amount
        bucket["count"] += 1
        bucket["first_seen"] = min(bucket["first_seen"], row["date"])

    merchants = sorted(
        (
            NewMerchant(
                merchant=bucket["merchant"] or "Unknown merchant",
                category=bucket["category"],
                amount=round(bucket["amount"], 2),
                transaction_count=int(bucket["count"]),
                first_seen=bucket["first_seen"],
            )
            for bucket in by_merchant.values()
        ),
        key=lambda item: (item.first_seen, item.merchant),
    )
    if not merchants:
        return []

    groups: list[list[NewMerchant]] = [[merchants[0]]]
    for merchant in merchants[1:]:
        previous = groups[-1][-1]
        if (merchant.first_seen - previous.first_seen).days <= MAX_CLUSTER_GAP_DAYS:
            groups[-1].append(merchant)
        else:
            groups.append([merchant])

    coverage_text = (
        f"the {coverage_months} months on record"
        if coverage_months
        else "any earlier month on record"
    )
    clusters: list[NoveltyCluster] = []
    for group in groups:
        if len(group) < MIN_CLUSTER_MERCHANTS:
            # Two merchants a day apart are two merchants. Emitting one entry
            # per group here would file the second one's money under the first
            # one's name, which is worse than not grouping at all.
            for merchant in group:
                clusters.append(
                    NoveltyCluster(
                        key=f"{merchant.first_seen.isoformat()}:{merchant.merchant}",
                        label=merchant.merchant,
                        detail=(
                            f"First charge from this merchant in {coverage_text}"
                            + (f" · {merchant.category}" if merchant.category else "")
                            + "."
                        ),
                        start_date=merchant.first_seen,
                        end_date=merchant.first_seen,
                        total=merchant.amount,
                        merchant_count=1,
                        transaction_count=merchant.transaction_count,
                        is_cluster=False,
                        merchants=[merchant],
                    )
                )
            continue
        start = min(item.first_seen for item in group)
        end = max(item.first_seen for item in group)
        dominant = _dominant_category(group)
        clusters.append(
            NoveltyCluster(
                key=f"{start.isoformat()}:{len(group)}",
                label=f"{len(group)} new places, {_span_text(start, end)}",
                detail=(
                    (f"Mostly {dominant}. " if dominant else "")
                    + f"None of them charged the household in {coverage_text}."
                ),
                start_date=start,
                end_date=end,
                total=round(sum(item.amount for item in group), 2),
                merchant_count=len(group),
                transaction_count=sum(item.transaction_count for item in group),
                is_cluster=True,
                merchants=list(group),
            )
        )
    return sorted(clusters, key=lambda cluster: cluster.total, reverse=True)
