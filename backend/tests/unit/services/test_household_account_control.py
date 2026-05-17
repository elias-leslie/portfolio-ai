"""Unit tests for household account-control safety checks."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.models.household_finance import (
    HouseholdAccountControl,
    HouseholdAccountControlIssue,
    HouseholdAccountSummary,
)
from app.services.household_account_control import (
    SourceAccountRow,
    _collapse_source_rows,
    apply_account_control_to_summaries,
)


def _source_row(
    source_account_id: str,
    *,
    balance: str = "41840.64",
    cash_balance: str | None = "41840.64",
    household_account_id: str = "household-cash",
    label: str = "Cash Management",
    institution_name: str = "Fidelity",
    account_mask: str = "1234",
) -> SourceAccountRow:
    return SourceAccountRow(
        source="snaptrade",
        source_account_id=source_account_id,
        connection_id="auth-1",
        household_account_id=household_account_id,
        account_label=label,
        institution_name=institution_name,
        account_mask=account_mask,
        current_value=Decimal(balance),
        cash_balance=Decimal(cash_balance) if cash_balance is not None else None,
        currency="USD",
        last_synced_at=datetime(2026, 5, 16, tzinfo=UTC),
    )


def test_duplicate_source_aliases_are_collapsed_without_double_counting() -> None:
    values, source_owned_ids, issues = _collapse_source_rows(
        [
            _source_row("snaptrade-account-1"),
            _source_row("snaptrade-account-2"),
        ]
    )

    assert source_owned_ids == {"household-cash"}
    assert values["household-cash"]["current_value"] == Decimal("41840.64")
    assert len(issues) == 1
    assert issues[0].code == "duplicate_source_alias"
    assert issues[0].affects_totals is False
    assert sorted(issues[0].source_account_ids) == [
        "snaptrade-account-1",
        "snaptrade-account-2",
    ]


def test_conflicting_source_values_block_trusted_totals() -> None:
    values, source_owned_ids, issues = _collapse_source_rows(
        [
            _source_row("snaptrade-account-1", balance="41840.64"),
            _source_row("snaptrade-account-2", balance="41841.64"),
        ]
    )

    assert source_owned_ids == {"household-cash"}
    assert values["household-cash"]["current_value"] == Decimal("41841.64")
    assert len(issues) == 1
    assert issues[0].code == "source_value_conflict"
    assert issues[0].affects_totals is True


def test_unlinked_source_account_with_value_blocks_trusted_totals() -> None:
    values, source_owned_ids, issues = _collapse_source_rows(
        [
            _source_row(
                "snaptrade-account-1",
                household_account_id=None,
                label="Unlinked Brokerage",
            )
        ]
    )

    assert values == {}
    assert source_owned_ids == set()
    assert len(issues) == 1
    assert issues[0].code == "unlinked_source_account"
    assert issues[0].affects_totals is True


def test_account_control_issues_are_added_to_account_gap_flags() -> None:
    account = HouseholdAccountSummary(
        id="account-1",
        household_account_id="household-cash",
        label="Cash Management",
        asset_group="taxable",
        account_type="brokerage",
        source_type="brokerage",
        current_value=41840.64,
        cash_balance=41840.64,
        money_role="spend_driver",
        balance_freshness_status="fresh",
        balance_freshness_label="Fresh",
        transaction_freshness_status="aging",
        transaction_freshness_label="Refresh soon",
        freshness_status="aging",
        freshness_label="Refresh soon",
        match_status="linked",
    )
    control = HouseholdAccountControl(
        status="review",
        summary="1 account control review item found.",
        issue_count=1,
        blocking_issue_count=0,
        checked_at="2026-05-16T00:00:00+00:00",
        issues=[
            HouseholdAccountControlIssue(
                id="duplicate_source_alias:household-cash",
                code="duplicate_source_alias",
                severity="medium",
                title="Duplicate source aliases collapsed",
                detail="Cash Management is represented by two matching source rows.",
                household_account_id="household-cash",
                account_label="Cash Management",
                source="snaptrade",
                source_account_ids=["snaptrade-account-1", "snaptrade-account-2"],
                affects_totals=False,
            )
        ],
    )

    updated = apply_account_control_to_summaries([account], control)

    assert updated[0].gap_flags[-1].code == "duplicate_source_alias"
    assert updated[0].gap_flags[-1].severity == "medium"
