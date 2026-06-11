"""Tests for portfolio-account matching in household summaries."""

from __future__ import annotations

from types import SimpleNamespace

from app.services._household_account_summary_matching import (
    _match_portfolio_account,
)


def _portfolio_account(
    account_id: str,
    name: str,
    household_account_id: str | None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=account_id,
        name=name,
        account_type="IRA",
        household_account_id=household_account_id,
    )


def test_fk_linked_account_is_not_label_matched_to_sibling() -> None:
    """Two same-label household accounts (his/hers FRS) must not collapse.

    Regression: a manual holdings portfolio account FK-linked to one FRS plan
    was label-matched to the other FRS plan too, overwriting its documented
    balance with the sibling's live-quote valuation.
    """
    linked = _portfolio_account("pa-1", "FRS Investment Plan", "hh-spouse")

    # The FK owner resolves via the direct branch.
    assert (
        _match_portfolio_account(
            household_account_id="hh-spouse",
            label="FRS Investment Plan",
            account_name=None,
            asset_group="retirement",
            portfolio_accounts=[linked],
        )
        is linked
    )

    # The same-label sibling must NOT claim it via the label fallback.
    assert (
        _match_portfolio_account(
            household_account_id="hh-primary",
            label="FRS Investment Plan",
            account_name=None,
            asset_group="retirement",
            portfolio_accounts=[linked],
        )
        is None
    )


def test_unlinked_account_still_label_matches() -> None:
    legacy = _portfolio_account("pa-2", "Traditional IRA", None)
    assert (
        _match_portfolio_account(
            household_account_id="hh-any",
            label="Traditional IRA",
            account_name=None,
            asset_group="retirement",
            portfolio_accounts=[legacy],
        )
        is legacy
    )
