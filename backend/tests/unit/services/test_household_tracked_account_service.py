"""Unit tests for tracked household account CRUD identity rules."""

from __future__ import annotations

from unittest.mock import Mock

from pytest import raises

from app.models.household_finance import HouseholdEvidenceAccount, HouseholdTrackedAccount
from app.services.household_tracked_account_service import HouseholdTrackedAccountService


def _tracked_account(
    *,
    account_id: str,
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


def test_sync_linked_accounts_from_evidence_repairs_drifted_identity() -> None:
    service = HouseholdTrackedAccountService()
    tracked = _tracked_account(
        account_id="acct-1",
        label="Pinellas County Schools 403(b) Plan",
        asset_group="retirement",
        account_type="roth",
        source_type="retirement",
        match_key="evidence|pinellas county schools|pinellas county schools 403(b) plan|retirement",
        institution_name="Pinellas County Schools",
        owner_name="Mariana",
        account_mask=None,
    )
    service.list_accounts = lambda _service, **_kwargs: [tracked]  # type: ignore[method-assign]

    fake_conn = Mock()
    fake_ctx = Mock()
    fake_ctx.__enter__ = Mock(return_value=fake_conn)
    fake_ctx.__exit__ = Mock(return_value=False)
    fake_service = Mock()
    fake_service.storage.connection.return_value = fake_ctx
    fake_service.list_evidence_accounts.return_value = [
        HouseholdEvidenceAccount(
            id="evidence-1",
            document_id="doc-1",
            source_type="retirement",
            asset_group="retirement",
            account_type="retirement",
            institution_name="Pinellas County Schools",
            account_name="Pinellas County Schools 403(b) Plan",
            account_mask=None,
            owner_name=None,
            currency="USD",
            balance=130087.17,
            holdings_value=130087.17,
            cash_balance=None,
            as_of_date="2026-04-10T00:00:00+00:00",
            confidence=0.98,
            metadata={},
        )
    ]

    updated = service.sync_linked_accounts_from_evidence(fake_service)

    assert updated == 1
    fake_conn.execute.assert_called_once()
    sql, params = fake_conn.execute.call_args.args
    assert "UPDATE household_tracked_accounts" in sql
    assert params[0] == "retirement"
    assert params[1] == "retirement"
    assert params[2] == "retirement"
    assert params[3] == "Pinellas County Schools"
    assert params[4] == "Mariana"
    assert params[5] is None
    assert params[-1] == "acct-1"


def test_sync_linked_accounts_from_evidence_ignores_unanchored_rows() -> None:
    service = HouseholdTrackedAccountService()
    service.list_accounts = lambda _service, **_kwargs: [  # type: ignore[method-assign]
        _tracked_account(
            account_id="acct-1",
            label="Amazon Chase (CC)",
            asset_group="credit",
            account_type="credit_card",
            source_type="credit_card",
            match_key=None,
            institution_name="Chase",
            owner_name="Elias and Mariana",
            account_mask=None,
        )
    ]

    fake_conn = Mock()
    fake_ctx = Mock()
    fake_ctx.__enter__ = Mock(return_value=fake_conn)
    fake_ctx.__exit__ = Mock(return_value=False)
    fake_service = Mock()
    fake_service.storage.connection.return_value = fake_ctx
    fake_service.list_evidence_accounts.return_value = []

    updated = service.sync_linked_accounts_from_evidence(fake_service)

    assert updated == 0
    fake_conn.execute.assert_not_called()
