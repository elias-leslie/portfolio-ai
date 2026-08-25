"""Unit tests for the item-to-money coverage report."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services._household_item_linkage import build_linkage_coverage, classify_item

_FEEDS = {"acct-prime": date(2025, 12, 24)}


def test_linked_item_needs_no_further_explanation() -> None:
    assert (
        classify_item(
            transaction_id="tx-1",
            paid_account_id="acct-prime",
            card_mask="1000",
            purchase_day=date(2026, 5, 4),
            feed_starts=_FEEDS,
        )
        == "linked"
    )


def test_a_purchase_older_than_its_feed_is_not_a_matching_failure() -> None:
    assert (
        classify_item(
            transaction_id=None,
            paid_account_id="acct-prime",
            card_mask="3000",
            purchase_day=date(2019, 3, 1),
            feed_starts=_FEEDS,
        )
        == "before_feed"
    )


def test_a_card_no_account_claims_is_named_as_such() -> None:
    assert (
        classify_item(
            transaction_id=None,
            paid_account_id=None,
            card_mask="4000",
            purchase_day=date(2013, 3, 1),
            feed_starts=_FEEDS,
        )
        == "card_not_in_registry"
    )


def test_a_source_that_never_said_what_paid_is_not_blamed_on_a_card() -> None:
    assert (
        classify_item(
            transaction_id=None,
            paid_account_id=None,
            card_mask=None,
            purchase_day=date(2026, 6, 1),
            feed_starts=_FEEDS,
        )
        == "no_card_named"
    )


def test_an_account_that_sends_no_transactions_is_distinguished_from_a_miss() -> None:
    assert (
        classify_item(
            transaction_id=None,
            paid_account_id="acct-silent",
            card_mask="6000",
            purchase_day=date(2026, 6, 1),
            feed_starts=_FEEDS,
        )
        == "no_spending_feed"
    )


def test_inside_the_feed_on_a_known_card_with_no_charge_is_a_real_miss() -> None:
    assert (
        classify_item(
            transaction_id=None,
            paid_account_id="acct-prime",
            card_mask="1000",
            purchase_day=date(2026, 6, 1),
            feed_starts=_FEEDS,
        )
        == "unmatched"
    )


class _Conn:
    def __init__(self, feeds: list[tuple[Any, ...]], items: list[tuple[Any, ...]]) -> None:
        self.feeds = feeds
        self.items = items
        self._result: list[Any] = []

    def execute(self, sql: str, _params: list[Any] | None = None) -> _Conn:
        self._result = self.feeds if "FROM household_transactions" in sql else self.items
        return self

    def fetchall(self) -> list[Any]:
        return list(self._result)


def test_the_reported_share_is_over_items_whose_charge_could_exist() -> None:
    """Counting a 2013 order against today's feed answers a question nobody asked."""
    conn = _Conn(
        feeds=[("acct-prime", date(2025, 12, 24))],
        items=[
            ("tx-1", "acct-prime", "1000", date(2026, 5, 4), 20.0, "current_card"),
            (None, "acct-prime", "1000", date(2026, 5, 6), 15.0, "current_card"),
            (None, "acct-prime", "3000", date(2019, 3, 1), 40.0, "reissued_card"),
            (None, None, "4000", date(2013, 3, 1), 60.0, "unknown_card"),
        ],
    )
    coverage = build_linkage_coverage(conn)
    assert coverage.total_items == 4
    assert coverage.linked_items == 1
    assert coverage.addressable_items == 2
    assert coverage.addressable_linked_share == 0.5
    assert [bucket["state"] for bucket in coverage.buckets] == [
        "linked",
        "unmatched",
        "before_feed",
        "card_not_in_registry",
    ]


def test_a_card_nothing_claims_is_reported_with_the_window_it_was_used_in() -> None:
    conn = _Conn(
        feeds=[("acct-prime", date(2025, 12, 24))],
        items=[
            (None, None, "4000", date(2013, 3, 1), 60.0, "unknown_card"),
            (None, None, "4000", date(2014, 8, 5), 40.0, "unknown_card"),
        ],
    )
    coverage = build_linkage_coverage(conn)
    assert len(coverage.unknown_cards) == 1
    card = coverage.unknown_cards[0]
    assert card.mask == "4000"
    assert card.item_count == 2
    assert card.amount == 100.0
    assert card.first_seen == date(2013, 3, 1)
    assert card.last_seen == date(2014, 8, 5)


def test_a_number_the_account_no_longer_carried_is_not_called_unknown() -> None:
    """The registry has seen these digits; it has not seen them on that day."""
    assert (
        classify_item(
            transaction_id=None,
            paid_account_id=None,
            card_mask="2000",
            purchase_day=date(2026, 7, 1),
            feed_starts=_FEEDS,
            card_state="outside_card_window",
        )
        == "card_retired_by_then"
    )


def test_no_addressable_items_reports_no_share_rather_than_zero() -> None:
    conn = _Conn(feeds=[], items=[(None, None, None, date(2026, 6, 1), 10.0, "no_card_named")])
    coverage = build_linkage_coverage(conn)
    assert coverage.addressable_items == 0
    assert coverage.addressable_linked_share is None
