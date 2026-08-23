"""An account the ledger spends *from* has to be discoverable, not just one it pays *to*."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services._household_dashboard_unknown_accounts import (
    _detect_unlinked_spending_accounts,
)


class _FakeConnection:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def execute(self, query: str, parameters: list[Any] | None = None) -> _FakeConnection:
        del query, parameters
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._rows)


def test_a_card_named_only_on_receipts_is_surfaced_for_identification() -> None:
    """A card never appears in a transfer description, so the old query missed it.

    Money spent from an account the registry does not know sits outside every
    account total, and nothing asked about it.
    """
    conn = _FakeConnection(
        [
            ("Visa Credit ****4635", 2, date(2026, 2, 15), date(2026, 4, 27)),
            ("Visa credit ending 4635", 1, date(2025, 10, 6), date(2025, 10, 6)),
            ("Visa ending 4635", 2, date(2025, 8, 27), date(2025, 9, 19)),
        ]
    )

    detected = _detect_unlinked_spending_accounts(conn, known_masks=set())

    assert len(detected) == 1
    entry = detected[0]
    assert entry["partial_account"] == "4635"
    assert entry["occurrence_count"] == 5
    assert entry["asset_group"] == "credit"
    assert "3 different ways" in entry["detail"]
    assert "2025-08-27 and 2026-04-27" in entry["detail"]


def test_an_account_already_on_file_is_not_reported_as_unknown() -> None:
    conn = _FakeConnection([("Visa ending 3627", 4, date(2026, 1, 1), date(2026, 2, 1))])

    assert _detect_unlinked_spending_accounts(conn, known_masks={"3627"}) == []


def test_two_masks_are_two_accounts() -> None:
    conn = _FakeConnection(
        [
            ("Visa ending 4635", 2, date(2026, 1, 1), date(2026, 1, 2)),
            ("Visa ending 1234", 3, date(2026, 1, 1), date(2026, 1, 2)),
        ]
    )

    detected = _detect_unlinked_spending_accounts(conn, known_masks=set())

    assert sorted(entry["partial_account"] for entry in detected) == ["1234", "4635"]


def test_a_label_with_no_mask_identifies_nothing_and_is_skipped() -> None:
    """"Soft charge" or "Manual entries" name no account; reporting them is noise."""
    conn = _FakeConnection([("Soft charge", 9, date(2026, 1, 1), date(2026, 1, 2))])

    assert _detect_unlinked_spending_accounts(conn, known_masks=set()) == []
