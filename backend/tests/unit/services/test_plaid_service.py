from __future__ import annotations

from contextlib import AbstractContextManager
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import plaid_service
from app.services.plaid_service import (
    PlaidConfigurationError,
    PlaidIntegrationError,
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
        redirect_uri="https://portfolio-ai.example/money",
    )

    assert result == {"configured": True}
    assert ("client_id", "existing-client", True) not in saved_fields
    assert ("secret", "existing-secret", True) not in saved_fields
    assert ("environment", "production", False) in saved_fields
    assert ("redirect_uri", "https://portfolio-ai.example/money", False) in saved_fields


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


class _RecordingResult:
    def fetchall(self) -> list[list[object]]:
        return []

    def fetchone(self) -> list[object] | None:
        return None


class _RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object] | None]] = []

    def execute(
        self,
        sql: str,
        params: list[object] | None = None,
    ) -> _RecordingResult:
        self.calls.append((" ".join(sql.split()), params))
        return _RecordingResult()

    def commit(self) -> None:
        self.calls.append(("COMMIT", None))


class _RecordingStorage(AbstractContextManager[_RecordingConnection]):
    def __init__(self, connection: _RecordingConnection) -> None:
        self._connection = connection

    def connection(self) -> _RecordingStorage:
        return self

    def __enter__(self) -> _RecordingConnection:
        return self._connection

    def __exit__(self, *args: object) -> None:
        return None


def test_authoritative_empty_plaid_snapshot_deactivates_prior_accounts() -> None:
    service = _service()
    connection = _RecordingConnection()
    service.storage = _RecordingStorage(connection)

    count = service._upsert_accounts(
        item={"item_id": "item-1", "institution_name": "Bank"},
        document_id="document-1",
        accounts=[],
    )

    assert count == 0
    lifecycle_calls = [
        (sql, params)
        for sql, params in connection.calls
        if sql.startswith("UPDATE plaid_accounts")
    ]
    assert len(lifecycle_calls) == 1
    assert "SET is_active = FALSE" in lifecycle_calls[0][0]
    assert lifecycle_calls[0][1] is not None
    assert lifecycle_calls[0][1][1] == "item-1"
    assert connection.calls[-1] == ("COMMIT", None)


def test_plaid_account_reappearing_in_snapshot_is_reactivated() -> None:
    service = _service()
    connection = _RecordingConnection()
    service.storage = _RecordingStorage(connection)
    service._upsert_household_account = (  # type: ignore[method-assign]
        lambda **_kwargs: "household-account-1"
    )

    count = service._upsert_accounts(
        item={"item_id": "item-1", "institution_name": "Bank"},
        document_id="document-1",
        accounts=[
            {
                "account_id": "account-1",
                "name": "Checking",
                "mask": "1234",
                "type": "depository",
                "subtype": "checking",
                "balances": {"current": "50.00", "iso_currency_code": "USD"},
            }
        ],
    )

    assert count == 1
    account_sql = next(
        sql for sql, _params in connection.calls if sql.startswith("INSERT INTO plaid_accounts")
    )
    assert "last_synced_at, is_active, removed_at" in account_sql
    assert "is_active = TRUE" in account_sql
    assert "removed_at = NULL" in account_sql


def test_failed_plaid_account_request_cannot_deactivate_accounts() -> None:
    service = _service()
    service.cipher = SimpleNamespace(decrypt=lambda _value: "access-token")
    service.storage = SimpleNamespace(connection=lambda: None)
    upsert_calls: list[list[object]] = []
    service._upsert_accounts = lambda **kwargs: upsert_calls.append(  # type: ignore[method-assign]
        list(kwargs["accounts"])
    ) or 0

    class FailingClient:
        def accounts_balance_get(self, _request: object) -> Any:
            raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        service._sync_single_item(
            client=FailingClient(),
            item={
                "item_id": "item-1",
                "access_token_ciphertext": "ciphertext",
                "transactions_cursor": "",
            },
        )

    assert upsert_calls == []


@pytest.mark.parametrize(
    "accounts_payload",
    [None, {}, "not-a-list", [{"name": "Missing ID"}], [{"account_id": "  "}]],
)
def test_malformed_plaid_snapshot_cannot_reconcile_accounts(
    accounts_payload: object,
) -> None:
    service = _service()
    service.cipher = SimpleNamespace(decrypt=lambda _value: "access-token")
    lifecycle_calls: list[str] = []
    service._ensure_sync_document = lambda **_kwargs: lifecycle_calls.append(  # type: ignore[method-assign]
        "document"
    ) or "document-1"
    service._upsert_accounts = lambda **_kwargs: lifecycle_calls.append(  # type: ignore[method-assign]
        "accounts"
    ) or 0

    class MalformedClient:
        def accounts_balance_get(self, _request: object) -> dict[str, object]:
            return {"accounts": accounts_payload}

    with pytest.raises(PlaidIntegrationError, match="account"):
        service._sync_single_item(
            client=MalformedClient(),
            item={
                "item_id": "item-1",
                "access_token_ciphertext": "ciphertext",
                "transactions_cursor": "",
            },
        )

    assert lifecycle_calls == []


def test_true_empty_plaid_response_reaches_authoritative_reconciliation() -> None:
    service = _service()
    service.cipher = SimpleNamespace(decrypt=lambda _value: "access-token")
    connection = _RecordingConnection()
    service.storage = _RecordingStorage(connection)
    service._ensure_sync_document = lambda **_kwargs: "document-1"  # type: ignore[method-assign]
    account_snapshots: list[list[object]] = []
    service._upsert_accounts = lambda **kwargs: account_snapshots.append(  # type: ignore[method-assign]
        list(kwargs["accounts"])
    ) or 0
    service._sync_transactions = lambda **_kwargs: (  # type: ignore[method-assign]
        {
            "transaction_added_count": 0,
            "transaction_modified_count": 0,
            "transaction_removed_count": 0,
        },
        None,
    )

    class EmptyClient:
        def accounts_balance_get(self, _request: object) -> dict[str, object]:
            return {"accounts": []}

    result = service._sync_single_item(
        client=EmptyClient(),
        item={
            "item_id": "item-1",
            "access_token_ciphertext": "ciphertext",
            "transactions_cursor": "",
        },
    )

    assert account_snapshots == [[]]
    assert result["account_count"] == 0


def test_remove_item_deactivates_accounts_and_current_evidence() -> None:
    service = _service()
    connection = _RecordingConnection()
    service.storage = _RecordingStorage(connection)
    service.cipher = SimpleNamespace(
        available=True,
        decrypt=lambda _value: "access-token",
    )
    service._load_config = SimpleNamespace  # type: ignore[method-assign]
    service._load_items = lambda **_kwargs: [  # type: ignore[method-assign]
        {"item_id": "item-1", "access_token_ciphertext": "ciphertext"}
    ]

    class Client:
        def item_remove(self, _request: object) -> None:
            return None

    service._client = lambda _config: Client()  # type: ignore[method-assign]

    assert service.remove_item(item_id="item-1") == {"ok": True}
    queries = [sql for sql, _params in connection.calls]
    assert any(
        sql.startswith("UPDATE plaid_accounts") and "is_active = FALSE" in sql
        for sql in queries
    )
    assert any(sql.startswith("DELETE FROM household_evidence_accounts") for sql in queries)
