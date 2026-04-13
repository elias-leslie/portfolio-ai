"""Unit tests for tracked household account CRUD identity rules."""

from __future__ import annotations

from pytest import raises

from app.models.household_finance import HouseholdTrackedAccount
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
