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
    def connection(self):
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
        service._ensure_unique_identity(
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

    service._ensure_unique_identity(
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

    service._ensure_unique_identity(
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
        service._ensure_unique_identity(
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
        service._ensure_unique_identity(
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


def test_create_account_with_household_account_id_anchors_to_existing_canonical_account() -> None:
    service = HouseholdTrackedAccountService()
    linked = _tracked_account(
        account_id="tracked-457b",
        household_account_id="household-457b",
        label="PCSB 457b",
        asset_group="retirement",
        account_type="401k",
        source_type="retirement",
        match_key="identity::pcsb-457b",
        institution_name="Pinellas County Schools",
        owner_name="Mariana Leslie",
        account_mask=None,
    )
    service.get_account_by_household_account_id = Mock(return_value=None)  # type: ignore[method-assign]
    service._get_canonical_account = Mock(  # type: ignore[method-assign]
        return_value={
            "id": "household-457b",
            "primary_identity_key": "identity::pcsb-457b",
            "canonical_label": "Pinellas County Schools 457(b) Deferred Compensation Plan",
            "asset_group": "retirement",
            "account_type": "401k",
            "source_type": "retirement",
            "institution_name": "Pinellas County Schools",
            "owner_name": None,
            "account_mask": None,
        }
    )
    service._ensure_unique_identity = Mock(side_effect=AssertionError("should not use legacy tracked identity"))  # type: ignore[method-assign]
    service._ensure_canonical_account = Mock(side_effect=AssertionError("canonical account already provided"))  # type: ignore[method-assign]
    service._insert_account = Mock(return_value=linked)  # type: ignore[method-assign]

    result = service.create_account(
        Mock(),
        HouseholdTrackedAccountInput(
            household_account_id="household-457b",
            label="PCSB 457b",
            asset_group="retirement",
            account_type="401k",
            source_type="retirement",
            institution_name="Wrong",
            owner_name="Mariana Leslie",
            account_mask="401k",
        ),
    )

    assert result == linked
    service._insert_account.assert_called_once()
    _, kwargs = service._insert_account.call_args
    assert kwargs["household_account_id"] == "household-457b"
    account = kwargs["account"]
    assert account["label"] == "PCSB 457b"
    assert account["owner_name"] == "Mariana Leslie"


def test_create_account_without_household_account_id_creates_canonical_account_first() -> None:
    service = HouseholdTrackedAccountService()
    created = _tracked_account(
        account_id="pref-1",
        household_account_id="household-new",
        label="New Account",
        asset_group="cash",
        account_type="checking",
        source_type="bank",
    )
    service._ensure_canonical_account = Mock(return_value="household-new")  # type: ignore[method-assign]
    service._insert_account = Mock(return_value=created)  # type: ignore[method-assign]
    service._ensure_unique_identity = Mock(side_effect=AssertionError("should not create account through tracked rows"))  # type: ignore[method-assign]

    result = service.create_account(
        Mock(),
        HouseholdTrackedAccountInput(
            label="New Account",
            asset_group="cash",
            account_type="checking",
            source_type="bank",
            institution_name="Bank",
            account_mask="1234",
        ),
    )

    assert result == created
    service._ensure_canonical_account.assert_called_once()
    _, kwargs = service._insert_account.call_args
    assert kwargs["household_account_id"] == "household-new"


def test_create_account_with_household_account_id_upserts_existing_customization() -> None:
    service = HouseholdTrackedAccountService()
    existing = _tracked_account(
        account_id="tracked-existing",
        household_account_id="household-457b",
        label="Old label",
        asset_group="retirement",
        account_type="401k",
        source_type="retirement",
    )
    updated = existing.model_copy(update={"label": "PCSB 457b"})
    service.get_account_by_household_account_id = Mock(return_value=existing)  # type: ignore[method-assign]
    service.update_account = Mock(return_value=updated)  # type: ignore[method-assign]

    result = service.create_account(
        Mock(),
        HouseholdTrackedAccountInput(
            household_account_id="household-457b",
            label="PCSB 457b",
            asset_group="retirement",
            account_type="401k",
            source_type="retirement",
        ),
    )

    assert result == updated
    service.update_account.assert_called_once()


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


def test_delete_account_syncs_registry_to_prune_orphan_canonical_rows() -> None:
    service = HouseholdTrackedAccountService()
    connection = _FakeConnection()
    fake_service = Mock()
    fake_service.storage = _FakeStorage(connection)
    fake_service.account_registry_service.sync_registry = Mock()

    deleted = service.delete_account(fake_service, "tracked-1")

    assert deleted is True
    assert connection.committed is True
    fake_service.account_registry_service.sync_registry.assert_called_once_with(
        fake_service,
        limit=500,
    )


def test_update_account_preserves_linked_identity_fields_but_allows_owner_change() -> None:
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
        owner_name="Wrong Owner",
        account_mask=None,
    )
    connection = _FakeConnection()
    fake_service = Mock()
    fake_service.storage = _FakeStorage(connection)
    fake_service.account_registry_service.sync_registry = Mock()
    service.get_account = Mock(side_effect=[existing, updated])  # type: ignore[method-assign]
    service._get_canonical_account = Mock(return_value=None)  # type: ignore[method-assign]
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
    assert params[1] == "Wrong Owner"
    assert params[2] == "Renamed for display"
    assert params[4] == "acct-1"
    service._ensure_unique_identity.assert_not_called()
    fake_service.account_registry_service.sync_registry.assert_called_once_with(fake_service, limit=500)


def test_update_account_allows_display_owner_change_for_linked_accounts() -> None:
    service = HouseholdTrackedAccountService()
    existing = _tracked_account(
        account_id="acct-2",
        household_account_id="household-2",
        label="Amazon Chase (CC)",
        asset_group="credit",
        account_type="credit_card",
        source_type="credit_card",
        match_key="identity::chase|5313",
        institution_name="Chase",
        owner_name="Elias B Leslie",
        account_mask="5313",
    )
    updated = _tracked_account(
        account_id="acct-2",
        household_account_id="household-2",
        label="Prime Visa",
        asset_group="credit",
        account_type="credit_card",
        source_type="credit_card",
        match_key="identity::chase|5313",
        institution_name="Chase",
        owner_name="Elias",
        account_mask="5313",
    )
    connection = _FakeConnection()
    fake_service = Mock()
    fake_service.storage = _FakeStorage(connection)
    fake_service.account_registry_service.sync_registry = Mock()
    service.get_account = Mock(side_effect=[existing, updated])  # type: ignore[method-assign]
    service._get_canonical_account = Mock(return_value=None)  # type: ignore[method-assign]
    service._ensure_unique_identity = Mock()  # type: ignore[method-assign]

    payload = HouseholdTrackedAccountInput(
        label="Prime Visa",
        asset_group="credit",
        account_type="credit_card",
        source_type="credit_card",
        match_key=None,
        institution_name="Chase",
        owner_name="Elias",
        account_mask="9728",
        notes="Updated display name only",
    )

    result = service.update_account(fake_service, "acct-2", payload)

    assert result == updated
    _, params = connection.calls[0]
    assert params is not None
    assert params[0] == "Prime Visa"
    assert params[1] == "Elias"
    assert params[2] == "Updated display name only"
    assert params[4] == "acct-2"
    service._ensure_unique_identity.assert_not_called()
