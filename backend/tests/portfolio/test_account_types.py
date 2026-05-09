"""Truth-table tests for the account_types helpers."""

from __future__ import annotations

import pytest

from app.portfolio.account_types import (
    ACCOUNT_TYPES,
    is_paper,
    is_tax_advantaged,
    is_taxable,
)


@pytest.mark.parametrize(
    ("account_type", "taxable", "tax_advantaged", "paper"),
    [
        ("Taxable", True, False, False),
        ("IRA", False, True, False),
        ("Roth", False, True, False),
        ("401k", False, True, False),
        ("HSA", False, True, False),
        ("paper", False, False, True),
    ],
)
def test_account_type_helpers_truth_table(
    account_type: str,
    taxable: bool,
    tax_advantaged: bool,
    paper: bool,
) -> None:
    assert is_taxable(account_type) is taxable
    assert is_tax_advantaged(account_type) is tax_advantaged
    assert is_paper(account_type) is paper


def test_account_types_tuple_is_exhaustive() -> None:
    assert set(ACCOUNT_TYPES) == {"IRA", "Taxable", "401k", "Roth", "HSA", "paper"}


def test_unknown_account_type_helpers_return_false() -> None:
    assert is_taxable("Unknown") is False
    assert is_tax_advantaged("Unknown") is False
    assert is_paper("Unknown") is False
