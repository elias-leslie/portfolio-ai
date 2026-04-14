"""Unit tests for tracked household account CRUD identity rules."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import Mock

from pytest import raises

from app.models.household_finance import HouseholdTrackedAccount, HouseholdTrackedAccountInput
from app.services.household_tracked_account_service import HouseholdTrackedAccountService


def _tracked_account(
    *,
    account_id: str,
    household_account_id: str | None = None,
    label: str,
    asset_group: str,
    account_type: str,
    source_type: str,
    match_key: str | None = None,
    institution_name: str | None = None,
    owner_name: str | None = None,
    account_mask: str | None = None,
) -> HouseholdTrackedAccount:
    return HouseholdTrackedAccount(
        id=account_id,
        household_account_id=household_account_id,
        label=label,
        asset_group=asset_group,
        account_type=account_type,
        source_type=source_type,
        match_key=match_key,
        institution_name=institution_name,
        owner_name=owner_name,
        account_mask=account_mask,
        notes=None,
        created_at="2026-04-13T00:00:00Z",
        updated_at="2026-04-13T00:00:00Z",
    )


class _FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object] | None]] = []
        self.committed = False

    def execute(self, sql: str, params: list[object] | None = None) -> Mock:
        self.calls.append((sql, params))
        return Mock(rowcount=1)

    def commit(self) -> None:
        self.committed = True


class _FakeStorage:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    @contextmanager
    def connection(self):  # type: ignore[override]
        yield self._connection


def test_ensure_unique_identity_rejects_duplicate_institution_mask() -> None:
    service = HouseholdTrackedAccountService()
    service.list_accounts = lambda _service, **_kwargs: [  # type: ignore[method-assign]
        _tracked_account(
            account_id="acct-1",
            label="Cash Management (Joint WROS)",
            asset_group="taxable",
            account_type="brokerage",
            source_type="brokerage",
            institution_name="Fidelity",
            account_mask="Z38367298",
        )
    ]

    with raises(ValueError, match="already exists"):
        service._ensure_unique_identity(  # type: ignore[attr-defined]
            object(),
            account={
                "label": "Main Cash Management",
                "asset_group": "taxable",
                "account_type": "brokerage",
                "source_type": "brokerage",
                "match_key": None,
                "institution_name": "Fidelity",
                "owner_name": None,
                "account_mask": "Z38367298",
                "notes": None,
            },
        )


def test_ensure_unique_identity_allows_same_row_on_update() -> None:
    service = HouseholdTrackedAccountService()
    service.list_accounts = lambda _service, **_kwargs: [  # type: ignore[method-assign]
        _tracked_account(
            account_id="acct-1",
            label="Cash Management (Joint WROS)",
            asset_group="taxable",
            account_type="brokerage",
            source_type="brokerage",
            institution_name="Fidelity",
            account_mask="Z38367298",
        )
    ]

    service._ensure_unique_identity(  # type: ignore[attr-defined]
        object(),
        account={
            "label": "Main Cash Management",
            "asset_group": "taxable",
            "account_type": "brokerage",
            "source_type": "brokerage",
            "match_key": None,
            "institution_name": "Fidelity",
            "owner_name": None,
            "account_mask": "Z38367298",
            "notes": None,
        },
        exclude_account_id="acct-1",
    )


def test_ensure_unique_identity_allows_same_institution_label_when_owner_differs() -> None:
    service = HouseholdTrackedAccountService()
    service.list_accounts = lambda _service, **_kwargs: [  # type: ignore[method-assign]
        _tracked_account(
            account_id="acct-1",
            label="FRS Investment Plan",
            asset_group="retirement",
            account_type="retirement",
            source_type="retirement",
            institution_name="Florida Retirement System (FRS)",
            owner_name="Elias B. Leslie",
            account_mask=None,
        )
    ]

    service._ensure_unique_identity(  # type: ignore[attr-defined]
        object(),
        account={
            "label": "FRS Investment Plan",
            "asset_group": "retirement",
            "account_type": "retirement",
            "source_type": "retirement",
            "match_key": None,
            "institution_name": "Florida Retirement System (FRS)",
            "owner_name": "Mariana Leslie",
            "account_mask": None,
            "notes": None,
        },
    )


def test_ensure_unique_identity_rejects_same_institution_label_and_owner() -> None:
    service = HouseholdTrackedAccountService()
    service.list_accounts = lambda _service, **_kwargs: [  # type: ignore[method-assign]
        _tracked_account(
            account_id="acct-1",
            label="FRS Investment Plan",
            asset_group="retirement",
            account_type="retirement",
            source_type="retirement",
            institution_name="Florida Retirement System (FRS)",
            owner_name="Elias B. Leslie",
            account_mask=None,
        )
    ]

    with raises(ValueError, match="already exists"):
        service._ensure_unique_identity(  # type: ignore[attr-defined]
            object(),
            account={
                "label": "FRS Investment Plan",
                "asset_group": "retirement",
                "account_type": "retirement",
                "source_type": "retirement",
                "match_key": None,
                "institution_name": "Florida Retirement System (FRS)",
                "owner_name": "Elias B. Leslie",
                "account_mask": None,
                "notes": None,
            },
        )


def test_ensure_unique_identity_rejects_duplicate_match_key() -> None:
    service = HouseholdTrackedAccountService()
    service.list_accounts = lambda _service, **_kwargs: [  # type: ignore[method-assign]
        _tracked_account(
            account_id="acct-1",
            label="Chase Amazon card",
            asset_group="credit",
            account_type="credit_card",
            source_type="credit_card",
            match_key="evidence|chase amazon card|credit_card",
        )
    ]

    with raises(ValueError, match="already exists"):
        service._ensure_unique_identity(  # type: ignore[attr-defined]
            object(),
            account={
                "label": "Amazon Chase (CC)",
                "asset_group": "credit",
                "account_type": "credit_card",
                "source_type": "credit_card",
                "match_key": "evidence|chase amazon card|credit_card",
                "institution_name": "Chase",
                "owner_name": "Elias and Mariana",
                "account_mask": None,
                "notes": None,
            },
        )


def test_sync_linked_accounts_from_evidence_delegates_to_registry() -> None:
    service = HouseholdTrackedAccountService()
    fake_service = Mock()
    fake_service.account_registry_service.sync_registry.return_value = {"tracked_linked": 1}

    updated = service.sync_linked_accounts_from_evidence(fake_service)

    assert updated == 1
    fake_service.account_registry_service.sync_registry.assert_called_once_with(fake_service, limit=500)


def test_sync_linked_accounts_from_evidence_ignores_unanchored_rows() -> None:
    service = HouseholdTrackedAccountService()
    fake_service = Mock()
    fake_service.account_registry_service.sync_registry.return_value = {"tracked_linked": 0}

    updated = service.sync_linked_accounts_from_evidence(fake_service)

    assert updated == 0
    fake_service.account_registry_service.sync_registry.assert_called_once_with(fake_service, limit=500)


def test_update_account_preserves_identity_fields_for_linked_accounts() -> None:
    service = HouseholdTrackedAccountService()
    existing = _tracked_account(
        account_id="acct-1",
        household_account_id="household-1",
        label="Pinellas County Schools 403(b) Plan",
        asset_group="retirement",
        account_type="retirement",
        source_type="retirement",
        match_key="identity::pinellas|403b",
        institution_name="Pinellas County Schools",
        owner_name="Mariana Leslie",
        account_mask=None,
    )
    updated = _tracked_account(
        account_id="acct-1",
        household_account_id="household-1",
        label="Pinellas 403(b)",
        asset_group="retirement",
        account_type="retirement",
        source_type="retirement",
        match_key="identity::pinellas|403b",
        institution_name="Pinellas County Schools",
        owner_name="Mariana Leslie",
        account_mask=None,
    )
    connection = _FakeConnection()
    fake_service = Mock()
    fake_service.storage = _FakeStorage(connection)
    fake_service.account_registry_service.sync_registry = Mock()
    service.get_account = Mock(side_effect=[existing, updated])  # type: ignore[method-assign]
    service._ensure_unique_identity = Mock()  # type: ignore[method-assign]

    payload = HouseholdTrackedAccountInput(
        label="Pinellas 403(b)",
        asset_group="taxable",
        account_type="brokerage",
        source_type="brokerage",
        match_key="override::bad",
        institution_name="Wrong Bank",
        owner_name="Wrong Owner",
        account_mask="9999",
        notes="Renamed for display",
    )

    result = service.update_account(fake_service, "acct-1", payload)

    assert result == updated
    assert connection.committed is True
    assert len(connection.calls) == 1
    _, params = connection.calls[0]
    assert params is not None
    assert params[0] == "Pinellas 403(b)"
    assert params[1] == "retirement"
    assert params[2] == "retirement"
    assert params[3] == "retirement"
    assert params[4] == "identity::pinellas|403b"
    assert params[5] == "Pinellas County Schools"
    assert params[6] == "Mariana Leslie"
    assert params[7] is None
    assert params[8] == "Renamed for display"
    assert params[10] == "acct-1"
    fake_service.account_registry_service.sync_registry.assert_called_once_with(fake_service, limit=500)
