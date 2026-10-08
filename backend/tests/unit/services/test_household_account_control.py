"""Unit tests for household account-control safety checks."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.household_finance import (
    HouseholdAccountControl,
    HouseholdAccountControlIssue,
    HouseholdAccountSummary,
)
from app.services._household_account_summary_utils import _BALANCE_FRESHNESS_THRESHOLDS
from app.services.household_account_control import (
    SourceAccountRow,
    _collapse_source_rows,
    _source_rows,
    account_control_inbox_items,
    apply_account_control_to_summaries,
)


class _QueryResult:
    def __init__(self, rows: list[list[object]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[list[object]]:
        return self.rows


class _QueryRecordingStorage:
    def __init__(self, rows: list[list[object]] | None = None) -> None:
        self.query = ""
        self.rows = rows or []

    def connection(self) -> _QueryRecordingStorage:
        return self

    def __enter__(self) -> _QueryRecordingStorage:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str) -> _QueryResult:
        self.query = " ".join(query.split())
        return _QueryResult(self.rows)


def _source_row(
    source_account_id: str,
    *,
    balance: str = "41840.64",
    cash_balance: str | None = "41840.64",
    household_account_id: str = "household-cash",
    label: str = "Cash Management",
    institution_name: str = "Fidelity",
    account_mask: str = "1234",
    connection_id: str = "auth-1",
) -> SourceAccountRow:
    return SourceAccountRow(
        source="snaptrade",
        source_account_id=source_account_id,
        connection_id=connection_id,
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


def test_same_account_across_connections_is_shared_not_duplicate() -> None:
    # A joint account surfaced under two different logins (e.g. each spouse's
    # Fidelity connection) is shared, not an accidental duplicate connection.
    values, source_owned_ids, issues = _collapse_source_rows(
        [
            _source_row("snaptrade-account-1", connection_id="auth-alex-demo"),
            _source_row("snaptrade-account-2", connection_id="auth-marian"),
        ]
    )

    assert source_owned_ids == {"household-cash"}
    assert values["household-cash"]["current_value"] == Decimal("41840.64")
    assert len(issues) == 1
    assert issues[0].code == "shared_source_account"
    assert issues[0].affects_totals is False
    assert "no action is needed" in issues[0].detail
    assert "removed" not in issues[0].detail
    assert sorted(issues[0].source_account_ids) == [
        "snaptrade-account-1",
        "snaptrade-account-2",
    ]


def test_same_account_across_connections_with_conflicting_balances_blocks_totals() -> None:
    values, source_owned_ids, issues = _collapse_source_rows(
        [
            _source_row("snaptrade-account-1", balance="41840.64", connection_id="auth-old"),
            _source_row("snaptrade-account-2", balance="41841.64", connection_id="auth-new"),
        ]
    )

    assert source_owned_ids == {"household-cash"}
    assert values["household-cash"]["current_value"] == Decimal("41841.64")
    assert len(issues) == 1
    assert issues[0].code == "source_value_conflict"
    assert issues[0].affects_totals is True


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


def test_current_source_values_exclude_removed_provider_snapshots() -> None:
    storage = _QueryRecordingStorage()

    assert _source_rows(storage) == []

    assert "sa.is_active = true" in storage.query
    assert "sc.is_active = true" in storage.query
    assert "pa.is_active = true" in storage.query
    assert "pi.status = 'active'" in storage.query
    assert storage.query.count("ha.asset_group") == 2


def test_source_rows_carry_canonical_asset_group_for_freshness_selection() -> None:
    synced_at = datetime(2026, 5, 16, tzinfo=UTC)
    storage = _QueryRecordingStorage(
        [
            [
                "snaptrade",
                "snaptrade-account",
                "authorization",
                "household-retirement",
                "Traditional IRA",
                "Fidelity",
                "1234",
                Decimal("1200"),
                Decimal("200"),
                "USD",
                synced_at,
                None,
                "retirement",
            ]
        ]
    )

    rows = _source_rows(storage)

    assert len(rows) == 1
    assert rows[0].asset_group == "retirement"
    assert rows[0].last_synced_at == synced_at


def test_later_plaid_total_preserves_freshest_snaptrade_balance_and_cash() -> None:
    older = replace(
        _source_row("snaptrade-older", cash_balance="1200"),
        last_synced_at=datetime(2026, 5, 15, tzinfo=UTC),
    )
    snaptrade = _source_row("snaptrade-current", cash_balance="1200", account_mask="Z00001234")
    plaid = replace(
        _source_row("plaid-account", cash_balance=None),
        source="plaid",
        connection_id="plaid-item",
        last_synced_at=datetime(2026, 5, 17, tzinfo=UTC),
    )
    incomplete = replace(
        snaptrade,
        source_account_id="snaptrade-incomplete",
        current_value=None,
        cash_balance=None,
        last_synced_at=datetime(2026, 5, 18, tzinfo=UTC),
    )

    values, source_owned_ids, issues = _collapse_source_rows([plaid, older, snaptrade, incomplete])

    assert source_owned_ids == {"household-cash"}
    assert values["household-cash"]["current_value"] == Decimal("41840.64")
    assert values["household-cash"]["cash_balance"] == Decimal("1200")
    assert values["household-cash"]["last_synced_at"] == snaptrade.last_synced_at
    assert values["household-cash"]["source"] == "snaptrade"
    assert issues == []


@pytest.mark.parametrize(
    "changed_field,changed_value",
    [
        ("current_value", Decimal("41841.64")),
        ("cash_balance", Decimal("1201")),
        ("currency", "EUR"),
    ],
)
def test_comparable_provider_disagreements_still_block_totals(
    changed_field: str, changed_value: object
) -> None:
    snaptrade = _source_row("snaptrade-account", cash_balance="1200")
    plaid = replace(snaptrade, source="plaid", source_account_id="plaid-account")
    plaid = replace(plaid, **{changed_field: changed_value})

    values, _, issues = _collapse_source_rows([snaptrade, plaid])

    assert values["household-cash"]["source"] == "snaptrade"
    assert len(issues) == 1
    assert issues[0].code == "source_value_conflict"
    assert issues[0].affects_totals is True


def test_missing_provider_details_do_not_contradict_known_values() -> None:
    snaptrade = _source_row("snaptrade-account", cash_balance="1200")
    plaid = replace(
        snaptrade,
        source="plaid",
        source_account_id="plaid-account",
        cash_balance=None,
        currency=None,
        account_mask=None,
        institution_name=None,
    )

    _, _, issues = _collapse_source_rows([snaptrade, plaid])

    assert issues == []


@pytest.mark.parametrize("invalid_balance", [None, Decimal("NaN"), Decimal("Infinity")])
def test_plaid_is_balance_fallback_when_snaptrade_has_no_usable_snapshot(
    invalid_balance: Decimal | None,
) -> None:
    snaptrade = replace(
        _source_row("snaptrade-account", cash_balance=None),
        current_value=invalid_balance,
        last_synced_at=datetime(2026, 5, 18, tzinfo=UTC),
        transaction_synced_at=datetime(2026, 5, 18, tzinfo=UTC),
    )
    plaid = replace(
        _source_row("plaid-account", cash_balance=None),
        source="plaid",
        last_synced_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    values, _, issues = _collapse_source_rows([snaptrade, plaid])

    assert values["household-cash"]["source"] == "plaid"
    assert values["household-cash"]["current_value"] == plaid.current_value
    assert values["household-cash"]["last_synced_at"] == plaid.last_synced_at
    assert values["household-cash"]["transaction_synced_at"] == snaptrade.transaction_synced_at
    assert values["household-cash"]["transaction_coverage_source"] == "snaptrade"
    assert issues == []


def test_plaid_only_account_uses_freshest_usable_balance() -> None:
    older = replace(_source_row("plaid-older", cash_balance=None), source="plaid")
    newer = replace(
        older,
        source_account_id="plaid-current",
        current_value=Decimal("42000"),
        last_synced_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    values, source_owned_ids, _ = _collapse_source_rows([older, newer])

    assert source_owned_ids == {"household-cash"}
    assert values["household-cash"]["source"] == "plaid"
    assert values["household-cash"]["current_value"] == Decimal("42000")
    assert values["household-cash"]["last_synced_at"] == newer.last_synced_at


def test_complete_plaid_total_takes_priority_over_partial_snaptrade_cash() -> None:
    snaptrade = replace(
        _source_row("snaptrade-account", cash_balance="200"),
        current_value=None,
    )
    plaid = replace(
        snaptrade,
        source="plaid",
        source_account_id="plaid-account",
        current_value=Decimal("1200"),
        cash_balance=None,
        last_synced_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    values, _, issues = _collapse_source_rows([snaptrade, plaid])

    assert values["household-cash"]["source"] == "plaid"
    assert values["household-cash"]["current_value"] == Decimal("1200")
    assert values["household-cash"]["cash_balance"] is None
    assert issues == []


@pytest.mark.parametrize("invalid_cash", [Decimal("NaN"), Decimal("Infinity")])
@pytest.mark.parametrize("with_plaid", [False, True])
def test_invalid_cash_never_reaches_selected_source_values(
    invalid_cash: Decimal,
    with_plaid: bool,
) -> None:
    snaptrade = replace(_source_row("snaptrade-account"), cash_balance=invalid_cash)
    plaid = replace(
        snaptrade,
        source="plaid",
        source_account_id="plaid-account",
        cash_balance=None,
    )

    values, _, issues = _collapse_source_rows([snaptrade, plaid] if with_plaid else [snaptrade])

    assert values["household-cash"]["source"] == ("plaid" if with_plaid else "snaptrade")
    assert values["household-cash"]["current_value"] == snaptrade.current_value
    assert values["household-cash"]["cash_balance"] is None
    assert issues == []


def test_invalid_total_and_cash_are_omitted_when_no_valid_provider_snapshot_exists() -> None:
    snaptrade = replace(
        _source_row("snaptrade-account"),
        current_value=Decimal("NaN"),
        cash_balance=Decimal("Infinity"),
    )

    values, source_owned_ids, _ = _collapse_source_rows([snaptrade])

    assert source_owned_ids == {"household-cash"}
    assert values["household-cash"]["current_value"] is None
    assert values["household-cash"]["cash_balance"] is None


@pytest.mark.parametrize("asset_group", ["cash", "taxable", "retirement"])
@pytest.mark.parametrize("older_tier", ["aging", "stale", "unknown"])
def test_fresher_plaid_tier_is_primary_over_older_snaptrade(
    asset_group: str,
    older_tier: str,
) -> None:
    now = datetime.now(UTC)
    fresh_days, aging_days = _BALANCE_FRESHNESS_THRESHOLDS[asset_group]
    older_days = fresh_days + 1 if older_tier == "aging" else aging_days + 1
    snaptrade = replace(
        _source_row("snaptrade-account", cash_balance="1200"),
        asset_group=asset_group,
        last_synced_at=None if older_tier == "unknown" else now - timedelta(days=older_days),
    )
    plaid = replace(
        snaptrade,
        source="plaid",
        source_account_id="plaid-account",
        cash_balance=None,
        last_synced_at=now - timedelta(days=fresh_days),
    )

    values, _, issues = _collapse_source_rows([snaptrade, plaid])

    assert values["household-cash"]["source"] == "plaid"
    assert values["household-cash"]["last_synced_at"] == plaid.last_synced_at
    assert issues == []


@pytest.mark.parametrize("asset_group", ["cash", "taxable", "retirement"])
def test_snaptrade_detail_stays_primary_within_the_same_freshness_tier(asset_group: str) -> None:
    now = datetime.now(UTC)
    fresh_days, _ = _BALANCE_FRESHNESS_THRESHOLDS[asset_group]
    snaptrade = replace(
        _source_row("snaptrade-account", cash_balance="1200"),
        asset_group=asset_group,
        last_synced_at=now - timedelta(days=fresh_days),
    )
    plaid = replace(
        snaptrade,
        source="plaid",
        source_account_id="plaid-account",
        cash_balance=None,
        last_synced_at=now,
    )

    values, _, issues = _collapse_source_rows([snaptrade, plaid])

    assert values["household-cash"]["source"] == "snaptrade"
    assert values["household-cash"]["cash_balance"] == Decimal("1200")
    assert values["household-cash"]["last_synced_at"] == snaptrade.last_synced_at
    assert issues == []


def test_zero_snaptrade_balance_is_usable_primary_snapshot() -> None:
    snaptrade = _source_row("snaptrade-account", balance="0", cash_balance="0")
    plaid = replace(
        snaptrade,
        source="plaid",
        source_account_id="plaid-account",
        cash_balance=None,
        last_synced_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    values, _, issues = _collapse_source_rows([snaptrade, plaid])

    assert values["household-cash"]["source"] == "snaptrade"
    assert values["household-cash"]["cash_balance"] == Decimal("0")
    assert issues == []


@pytest.mark.parametrize("coverage_source", ["plaid", "snaptrade"])
def test_transaction_coverage_uses_freshest_activity_independently_of_balance(
    coverage_source: str,
) -> None:
    latest_activity = datetime(2026, 5, 18, tzinfo=UTC)
    older_activity = datetime(2026, 5, 14, tzinfo=UTC)
    snaptrade = replace(
        _source_row("snaptrade-account", cash_balance="1200"),
        transaction_synced_at=latest_activity if coverage_source == "snaptrade" else older_activity,
    )
    plaid = replace(
        _source_row("plaid-account", cash_balance=None),
        source="plaid",
        last_synced_at=datetime(2026, 5, 17, tzinfo=UTC),
        transaction_synced_at=latest_activity if coverage_source == "plaid" else older_activity,
    )

    values, _, _ = _collapse_source_rows([snaptrade, plaid])

    assert values["household-cash"]["source"] == "snaptrade"
    assert values["household-cash"]["last_synced_at"] == snaptrade.last_synced_at
    assert values["household-cash"]["transaction_synced_at"] == latest_activity
    assert values["household-cash"]["transaction_coverage_source"] == coverage_source


def test_balance_refresh_does_not_invent_transaction_coverage() -> None:
    values, _, _ = _collapse_source_rows([_source_row("snaptrade-account")])

    assert values["household-cash"]["transaction_synced_at"] is None
    assert values["household-cash"]["transaction_coverage_source"] is None


@pytest.mark.parametrize(
    "changed_field,changed_value",
    [
        ("account_mask", "9999"),
        ("account_mask", "Y00001234"),
        ("institution_name", "Other Bank"),
    ],
)
def test_cross_provider_identity_disagreements_still_block_totals(
    changed_field: str, changed_value: str
) -> None:
    snaptrade = _source_row("snaptrade-account", account_mask="Z00001234")
    plaid = replace(
        snaptrade,
        source="plaid",
        source_account_id="plaid-account",
        account_mask="1234",
    )
    plaid = replace(plaid, **{changed_field: changed_value})

    _, _, issues = _collapse_source_rows([snaptrade, plaid])

    assert len(issues) == 1
    assert issues[0].code == "source_identity_collision"
    assert issues[0].affects_totals is True


def _account_summary() -> HouseholdAccountSummary:
    return HouseholdAccountSummary(
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


def test_review_only_account_control_issues_do_not_add_ui_gap_flags() -> None:
    account = _account_summary()
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

    assert updated[0].gap_flags == []
    assert account_control_inbox_items(control) == []


def test_blocking_account_control_issues_are_added_to_gap_flags_and_inbox() -> None:
    account = _account_summary()
    control = HouseholdAccountControl(
        status="blocked",
        summary="1 account control issue blocks trusted totals.",
        issue_count=1,
        blocking_issue_count=1,
        checked_at="2026-05-16T00:00:00+00:00",
        issues=[
            HouseholdAccountControlIssue(
                id="source_value_conflict:household-cash",
                code="source_value_conflict",
                severity="high",
                title="Source balances conflict",
                detail="Cash Management has source rows with different balances.",
                household_account_id="household-cash",
                account_label="Cash Management",
                source="source_accounts",
                source_account_ids=["snaptrade-account-1", "snaptrade-account-2"],
                affects_totals=True,
            )
        ],
    )

    updated = apply_account_control_to_summaries([account], control)
    inbox = account_control_inbox_items(control)

    assert updated[0].gap_flags[-1].code == "source_value_conflict"
    assert updated[0].gap_flags[-1].severity == "high"
    assert inbox[0].title == "Source balances conflict"
