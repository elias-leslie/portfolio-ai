"""First-time merchants, and the outings they were.

D2's fourth sentence needs to know which merchants the household has never paid
before. Detecting them is half the job: 34 unfamiliar names in a list is not
information, and reads like a fraud report rather than a holiday.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services._household_novelty import find_new_merchants


def _row(
    row_id: str,
    *,
    merchant: str,
    day: int,
    amount: float = 20.0,
    category: str = "Dining",
    month: int = 7,
) -> dict[str, Any]:
    return {
        "id": row_id,
        "date": date(2026, month, day),
        "merchant": merchant,
        "category": category,
        "amount": amount,
        "signed_amount": amount,
    }


def test_a_merchant_the_ledger_has_seen_before_is_not_new() -> None:
    month = [_row("a", merchant="Publix", day=4)]
    history = [*month, _row("old", merchant="Publix", day=4, month=5)]

    assert find_new_merchants(month, history_rows=history) == []


def test_a_run_of_first_time_places_becomes_one_outing() -> None:
    month = [
        _row("a", merchant="Memos Cabanas", day=3),
        _row("b", merchant="Pollo Campestre", day=5),
        _row("c", merchant="Cafe Albania", day=6),
    ]

    (cluster,) = find_new_merchants(month, history_rows=month, coverage_months=6)

    assert cluster.is_cluster is True
    assert cluster.merchant_count == 3
    assert cluster.label == "3 new places, 3-6 July"
    assert "the 6 months on record" in cluster.detail


def test_a_gap_of_three_days_starts_a_different_outing() -> None:
    """At three days the whole month collapses into one cluster."""
    month = [
        _row("a", merchant="One", day=1),
        _row("b", merchant="Two", day=2),
        _row("c", merchant="Three", day=3),
        _row("d", merchant="Four", day=20),
        _row("e", merchant="Five", day=21),
        _row("f", merchant="Six", day=22),
    ]

    clusters = find_new_merchants(month, history_rows=month)

    assert [cluster.merchant_count for cluster in clusters] == [3, 3]


def test_two_merchants_a_day_apart_stay_two_merchants() -> None:
    """Filing the second one's money under the first one's name is worse than
    not grouping at all."""
    month = [
        _row("a", merchant="Meyer Feinkost", day=16, amount=23.44),
        _row("b", merchant="Hsr K", day=16, amount=6.75),
    ]

    clusters = find_new_merchants(month, history_rows=month)

    assert [cluster.label for cluster in clusters] == ["Meyer Feinkost", "Hsr K"]
    assert [cluster.total for cluster in clusters] == [23.44, 6.75]
    assert all(cluster.is_cluster is False for cluster in clusters)


def test_a_cluster_names_the_category_it_is_mostly_made_of() -> None:
    month = [
        _row("a", merchant="Cafe One", day=3, amount=100.0, category="Dining"),
        _row("b", merchant="Cafe Two", day=4, amount=100.0, category="Dining"),
        _row("c", merchant="A Shop", day=5, amount=10.0, category="Retail"),
    ]

    (cluster,) = find_new_merchants(month, history_rows=month)

    assert "Mostly Dining" in cluster.detail


def test_a_cluster_with_no_dominant_category_claims_none() -> None:
    month = [
        _row("a", merchant="One", day=3, amount=100.0, category="Dining"),
        _row("b", merchant="Two", day=4, amount=100.0, category="Retail"),
        _row("c", merchant="Three", day=5, amount=100.0, category="Travel"),
    ]

    (cluster,) = find_new_merchants(month, history_rows=month)

    assert "Mostly" not in cluster.detail


def test_a_merchant_visited_twice_this_month_is_not_its_own_precedent() -> None:
    month = [
        _row("a", merchant="Memos Cabanas", day=3, amount=32.0),
        _row("b", merchant="Memos Cabanas", day=9, amount=18.0),
    ]

    (cluster,) = find_new_merchants(month, history_rows=month)

    assert cluster.merchant_count == 1
    assert cluster.transaction_count == 2
    assert cluster.total == 50.0
