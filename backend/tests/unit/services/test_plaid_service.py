from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import plaid_service
from app.services.plaid_service import (
    PlaidConfigurationError,
    PlaidService,
    _account_kind,
    _transaction_category,
    _transaction_flow,
)


def _service() -> PlaidService:
    service = PlaidService.__new__(PlaidService)
    service.storage = object()
    service.cipher = SimpleNamespace(available=True)
    return service


def test_configure_keeps_saved_credentials_when_secret_inputs_are_blank(monkeypatch) -> None:
    service = _service()
    saved_fields: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(service, "_ensure_source_registry", lambda: None)
    monkeypatch.setattr(service, "get_status", lambda: {"configured": True})
    monkeypatch.setattr(
        plaid_service,
        "get_source_credentials",
        lambda _storage, _source_id: {
            "client_id": "existing-client",
            "secret": "existing-secret",
        },
    )

    def fake_set_source_credential(
        storage: object,
        source_id: str,
        field: str,
        value: str,
        *,
        encrypt: bool = True,
    ) -> None:
        saved_fields.append((field, value, encrypt))

    monkeypatch.setattr(plaid_service, "set_source_credential", fake_set_source_credential)

    result = service.configure(
        client_id="",
        secret=None,
        environment="production",
        products=["transactions"],
        country_codes=["US"],
        redirect_uri="https://port.summitflow.dev/money",
    )

    assert result == {"configured": True}
    assert ("client_id", "existing-client", True) not in saved_fields
    assert ("secret", "existing-secret", True) not in saved_fields
    assert ("environment", "production", False) in saved_fields
    assert ("redirect_uri", "https://port.summitflow.dev/money", False) in saved_fields


def test_configure_still_requires_credentials_for_first_setup(monkeypatch) -> None:
    service = _service()
    monkeypatch.setattr(
        plaid_service,
        "get_source_credentials",
        lambda _storage, _source_id: {},
    )

    with pytest.raises(PlaidConfigurationError) as exc_info:
        service.configure(
            client_id=None,
            secret=None,
            environment="production",
            products=["transactions"],
            country_codes=["US"],
            redirect_uri=None,
        )

    assert str(exc_info.value) == "Plaid client_id and secret are required."


def test_upsert_household_account_targets_partial_identity_key_index() -> None:
    service = _service()
    executed_queries: list[str] = []

    class FakeResult:
        def fetchall(self) -> list[list[str]]:
            return []

        def fetchone(self) -> list[str]:
            return ["household-account-id"]

    class FakeConnection:
        def execute(self, query: str, params: list[object]) -> FakeResult:
            executed_queries.append(" ".join(query.split()))
            return FakeResult()

    result = service._upsert_household_account(
        conn=FakeConnection(),
        account_id="plaid-account-id",
        label="Chase Checking *1234",
        asset_group="cash",
        source_type="bank",
        account_type="checking",
        institution_name="Chase",
        mask="1234",
    )

    assert result == "household-account-id"
    assert any(
        "ON CONFLICT (primary_identity_key) WHERE primary_identity_key IS NOT NULL DO UPDATE SET"
        in query
        for query in executed_queries
    )


def test_account_kind_uses_household_credit_card_taxonomy() -> None:
    assert _account_kind("credit", "credit card") == (
        "credit",
        "credit_card",
        "credit_card",
    )


def test_transaction_category_maps_plaid_taxonomy_to_household_taxonomy() -> None:
    assert _transaction_category(
        {"primary": "FOOD_AND_DRINK", "detailed": "FOOD_AND_DRINK_RESTAURANT"}
    ) == ("Dining", "discretionary")
    assert _transaction_category(
        {
            "primary": "GENERAL_MERCHANDISE",
            "detailed": "GENERAL_MERCHANDISE_CLOTHING_AND_ACCESSORIES",
        }
    ) == ("Retail", "discretionary")
    assert _transaction_category(
        {"primary": "TRANSPORTATION", "detailed": "TRANSPORTATION_GAS"}
    ) == ("Gas", "essential")


def test_transaction_flow_keeps_investment_transfers_out_of_spend() -> None:
    assert (
        _transaction_flow(
            Decimal("5.00"),
            {
                "primary": "TRANSFER_OUT",
                "detailed": "TRANSFER_OUT_INVESTMENT_AND_RETIREMENT_FUNDS",
            },
        )
        == "investment"
    )


def test_upsert_household_account_reuses_existing_mask_identity() -> None:
    service = _service()
    executed_params: list[list[object]] = []

    class FakeResult:
        def __init__(self, rows: list[list[str]] | None = None) -> None:
            self.rows = rows or []

        def fetchall(self) -> list[list[str]]:
            return self.rows

        def fetchone(self) -> list[str]:
            return ["new-household-account-id"]

    class FakeConnection:
        def execute(self, query: str, params: list[object]) -> FakeResult:
            executed_params.append(params)
            if "FROM household_account_identities" in query:
                identity_keys = params[0]
                if "institution-mask::chase|9728" in identity_keys:
                    return FakeResult(
                        [["institution-mask::chase|9728", "existing-household-account-id"]]
                    )
                return FakeResult([])
            return FakeResult()

    result = service._upsert_household_account(
        conn=FakeConnection(),
        account_id="plaid-account-id",
        label="Chase - Prime Visa *9728",
        asset_group="credit",
        source_type="credit_card",
        account_type="credit_card",
        institution_name="Chase",
        mask="9728",
    )

    assert result == "existing-household-account-id"
    assert any("plaid_account:plaid-account-id" in params for params in executed_params)
