"""Unit tests for resolving an account when its card number has changed."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services.household_card_masks import CardMaskDirectory, extract_card_mask


class _Conn:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows

    def execute(self, _sql: str, _params: list[Any] | None = None) -> _Conn:
        return self

    def fetchall(self) -> list[Any]:
        return list(self.rows)


def _account(
    *,
    account_id: str = "acct-prime",
    label: str = "Chase Prime Visa / Amazon card",
    mask: str | None = "1000",
    prior: list[dict[str, Any]] | None = None,
) -> tuple[Any, ...]:
    return (account_id, label, mask, {"prior_masks": prior} if prior else {})


def test_extract_card_mask_reads_the_shapes_the_sources_print() -> None:
    assert extract_card_mask("Visa - 2000") == "2000"
    assert extract_card_mask("Visa Credit ****3000") == "3000"
    assert extract_card_mask("Chase Visa ending 1000") == "1000"
    assert extract_card_mask("CHASEVISA-1000") == "1000"


def test_extract_card_mask_takes_the_card_when_a_gift_balance_paid_part() -> None:
    assert extract_card_mask("Gift Certificate/Card and Visa - 1000") == "1000"


def test_extract_card_mask_returns_none_when_no_card_is_named() -> None:
    assert extract_card_mask("Gift Certificate/Card") is None
    assert extract_card_mask("Not Available") is None
    assert extract_card_mask("") is None


def test_resolve_matches_the_number_the_account_carries_today() -> None:
    directory = CardMaskDirectory.load(_Conn([_account()]))
    match = directory.resolve("Visa - 1000", on_date=date(2026, 6, 1))
    assert match is not None
    assert match.account_id == "acct-prime"
    assert match.reissued is False


def test_resolve_matches_a_number_the_account_used_to_carry() -> None:
    directory = CardMaskDirectory.load(
        _Conn([_account(prior=[{"mask": "2000", "from": "2025-12-30", "through": "2026-04-08"}])])
    )
    match = directory.resolve("Visa - 2000", on_date=date(2026, 2, 14))
    assert match is not None
    assert match.account_id == "acct-prime"
    assert match.reissued is True


def test_resolve_refuses_a_retired_number_outside_the_window_it_was_live() -> None:
    directory = CardMaskDirectory.load(
        _Conn([_account(prior=[{"mask": "2000", "from": "2025-12-30", "through": "2026-04-08"}])])
    )
    assert directory.resolve("Visa - 2000", on_date=date(2026, 7, 1)) is None
    assert directory.explain("Visa - 2000", on_date=date(2026, 7, 1)) == "outside_card_window"
    assert directory.knows_mask("Visa - 2000") is True


def test_resolve_refuses_when_two_accounts_claim_the_same_four_digits() -> None:
    directory = CardMaskDirectory.load(
        _Conn(
            [
                _account(),
                _account(account_id="acct-other", label="Other card", mask="1000"),
            ]
        )
    )
    assert directory.resolve("Visa - 1000", on_date=date(2026, 6, 1)) is None
    assert directory.explain("Visa - 1000", on_date=date(2026, 6, 1)) == "ambiguous_card"


def test_resolve_returns_none_for_a_card_the_registry_never_saw() -> None:
    directory = CardMaskDirectory.load(_Conn([_account()]))
    assert directory.resolve("Visa - 5000", on_date=date(2026, 6, 1)) is None
    assert directory.explain("Visa - 5000", on_date=date(2026, 6, 1)) == "unknown_card"
    assert directory.knows_mask("Visa - 5000") is False
