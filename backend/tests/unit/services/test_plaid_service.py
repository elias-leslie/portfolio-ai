from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager, contextmanager
from decimal import Decimal
from threading import Event, Lock
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
    _transaction_classification,
    _transaction_flow,
)


def _service() -> PlaidService:
    service = PlaidService.__new__(PlaidService)
    service.storage = _RecordingStorage(_RecordingConnection())
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


def test_card_payment_is_not_income_when_plaid_calls_it_salary() -> None:
    assert _transaction_classification(
        Decimal("-5896.50"),
        {"primary": "INCOME", "detailed": "INCOME_SALARY"},
        account_type="credit",
        description="AUTOMATIC PAYMENT - THANK",
    ) == ("payment", "Transfers", "mixed")
    assert _transaction_classification(
        Decimal("-6189.73"),
        {"primary": "LOAN_DISBURSEMENTS", "detailed": "LOAN_DISBURSEMENTS_OTHER_DISBURSEMENT"},
        account_type="credit",
        description="Payment Thank You-Mobile",
    ) == ("payment", "Transfers", "mixed")


def test_card_payment_rule_preserves_refunds_and_payroll() -> None:
    assert _transaction_classification(
        Decimal("-50"),
        {"primary": "TRAVEL", "detailed": "TRAVEL_LODGING"},
        account_type="credit",
        description="AIRBNB",
    ) == ("refund", "Travel", "discretionary")
    assert _transaction_classification(
        Decimal("-2827.13"),
        {"primary": "INCOME", "detailed": "INCOME_SALARY"},
        account_type="depository",
        description="PAYROLL",
    ) == ("income", "Income", "essential")


@pytest.mark.parametrize(
    ("description", "expected_category", "expected_essentiality"),
    [
        ("Depop", "Retail", "discretionary"),
        ("Anthropic", "Subscriptions", "discretionary"),
        ("Airbnb", "Travel", "discretionary"),
    ],
)
def test_card_merchant_credit_tagged_income_is_a_refund(
    description: str, expected_category: str, expected_essentiality: str
) -> None:
    assert _transaction_classification(
        Decimal("-120.18"),
        {"primary": "INCOME", "detailed": "INCOME_OTHER_INCOME"},
        account_type="credit",
        description=description,
    ) == ("refund", expected_category, expected_essentiality)


@pytest.mark.parametrize("description", ["Unidentified card credit", "Cash back rewards"])
def test_ambiguous_card_credit_is_neither_income_nor_spend_refund(description: str) -> None:
    assert _transaction_classification(
        Decimal("-120.18"),
        {"primary": "INCOME", "detailed": "INCOME_OTHER_INCOME"},
        account_type="credit",
        description=description,
    ) == ("credit", "Unknown", "mixed")


def test_card_credit_uses_plaid_merchant_name_when_transaction_name_is_generic() -> None:
    assert _transaction_classification(
        Decimal("-25.00"),
        {"primary": "INCOME", "detailed": "INCOME_OTHER_INCOME"},
        account_type="credit",
        description="Credit",
        merchant_name="Depop",
    ) == ("refund", "Retail", "discretionary")


def test_plaid_replay_upsert_preserves_reviewed_flow_and_dedup_removal(monkeypatch) -> None:
    service = _service()
    service.transaction_service = SimpleNamespace(
        _resolve_merchant=lambda **_kwargs: (None, "Depop", "Retail", "discretionary", False, None)
    )
    monkeypatch.setattr(plaid_service.SoftChargeReconciler, "try_match", lambda **_kwargs: None)
    queries: list[str] = []

    class FakeResult:
        def fetchone(self):
            return ("household-account", "Card", "credit")

    # Exercise the actual placeholder-rewriting wrapper and psycopg binder,
    # without opening a database or contacting Plaid.
    from psycopg._queries import PostgresQuery
    from psycopg.adapt import Transformer

    from app.storage._connection_wrapper import PostgreSQLConnectionWrapper

    class DriverCursor:
        def execute(self, sql: str, params: list[object]) -> None:
            PostgresQuery(Transformer()).convert(sql, params)
            queries.append(sql)

        def fetchone(self):
            return FakeResult().fetchone()

    class DriverConnection:
        def cursor(self):
            return DriverCursor()

    class FakeConnection:
        def execute(self, sql: str, params: list[object]) -> FakeResult:
            PostgreSQLConnectionWrapper(DriverConnection()).execute(sql, params)
            return FakeResult()

    service._upsert_transaction(
        conn=FakeConnection(),
        item={"item_id": "item-1"},
        document_id="document-1",
        transaction={
            "transaction_id": "txn-1",
            "account_id": "account-1",
            "date": "2026-03-01",
            "amount": -25.00,
            "name": "Depop",
            "personal_finance_category": {"primary": "INCOME", "detailed": "INCOME_OTHER_INCOME"},
        },
        removed=False,
    )

    household_upsert = next(sql for sql in queries if "INSERT INTO household_transactions" in sql)
    assert "transaction_audit_agent" in household_upsert
    assert "THEN household_transactions.flow_type" in household_upsert
    assert "jsonb_exists(household_transactions.metadata, 'dedup')" in household_upsert


def test_confirmed_property_zelle_receipt_is_income_even_with_transfer_pfc() -> None:
    assert _transaction_classification(
        Decimal("-506.31"),
        {"primary": "TRANSFER_IN", "detailed": "TRANSFER_IN_ACCOUNT_TRANSFER"},
        account_type="depository",
        description="Zelle From Michael Wiley Mortgage Payment On The Property At 8",
    ) == ("income", "Income", "essential")


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
    def __init__(self, row: list[object] | None = None) -> None:
        self.row = row

    def fetchall(self) -> list[list[object]]:
        return []

    def fetchone(self) -> list[object] | None:
        return self.row


class _RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object] | None]] = []

    def execute(
        self,
        sql: str,
        params: list[object] | None = None,
    ) -> _RecordingResult:
        self.calls.append((" ".join(sql.split()), params))
        if "pg_try_advisory_lock" in sql:
            return _RecordingResult([True])
        if "SELECT transactions_cursor" in sql:
            return _RecordingResult([""])
        return _RecordingResult()

    def commit(self) -> None:
        self.calls.append(("COMMIT", None))

    def rollback(self) -> None:
        self.calls.append(("ROLLBACK", None))


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


def test_empty_transaction_sync_is_valid_and_keeps_its_cursor():
    service = _service()
    conn = _RecordingConnection()
    service.storage = _RecordingStorage(conn)
    client = SimpleNamespace(transactions_sync=lambda _: {'added': [], 'modified': [], 'removed': [], 'has_more': False, 'next_cursor': 'unchanged'})
    counts, cursor = service._sync_transactions(client=client, item={'item_id': 'item-1', 'transactions_cursor': 'unchanged'}, document_id='doc', access_token='test')
    assert counts['transaction_added_count'] == 0
    assert cursor == 'unchanged'
    assert 'UPDATE plaid_items' in conn.calls[0][0]
    cursor_params = conn.calls[0][1]
    assert cursor_params is not None
    assert cursor_params[0] == 'unchanged'
    assert conn.calls[-1] == ('COMMIT', None)


@pytest.mark.parametrize('response', [
    {},
    {'added': [], 'modified': [], 'removed': [], 'has_more': True, 'next_cursor': 'unchanged'},
    {'added': 'invalid', 'modified': [], 'removed': [], 'has_more': False, 'next_cursor': 'next'},
    {'added': [{}], 'modified': [], 'removed': [], 'has_more': False, 'next_cursor': 'next'},
])
def test_incomplete_transaction_sync_never_writes_a_successful_batch(response):
    service = _service()
    conn = _RecordingConnection()
    service.storage = _RecordingStorage(conn)
    client = SimpleNamespace(transactions_sync=lambda _: response)
    with pytest.raises(PlaidIntegrationError, match='coverage is unverified'):
        service._sync_transactions(client=client, item={'transactions_cursor': 'unchanged'}, document_id='doc', access_token='test')
    assert conn.calls == [('ROLLBACK', None)]


def _transaction(**overrides):
    return {"transaction_id": "txn-1", "account_id": "account-1", "date": "2026-10-01", "amount": 5, **overrides}


def _page(*, added=None, modified=None, cursor="next", has_more=False):
    return {"added": added or [], "modified": modified or [], "removed": [], "next_cursor": cursor, "has_more": has_more}


def _mutation_error():
    error = plaid_service.plaid.ApiException(status=400)
    error.body = json.dumps({"error_code": "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"})
    return error


@pytest.mark.parametrize("field,value", [("date", "bad-date"), ("date", None), ("amount", "NaN"), ("amount", "Infinity"), ("amount", None), ("account_id", "  "), ("account_id", None)])
@pytest.mark.parametrize("kind", ["added", "modified"])
def test_invalid_transaction_prevents_all_writes_and_cursor_advance(field, value, kind, monkeypatch):
    service = _service()
    conn = _RecordingConnection()
    service.storage = _RecordingStorage(conn)
    writes = []
    monkeypatch.setattr(service, "_upsert_transaction", lambda **kwargs: writes.append(kwargs))
    response = _page(**{kind: [_transaction(), _transaction(**{field: value})]})
    with pytest.raises(PlaidIntegrationError, match="coverage is unverified"):
        service._sync_transactions(client=SimpleNamespace(transactions_sync=lambda _: response), item={"item_id": "item-1", "transactions_cursor": "original"}, document_id="doc", access_token="test")
    assert writes == []
    assert not any("UPDATE plaid_items" in sql or sql == "COMMIT" for sql, _ in conn.calls)


def test_sync_commits_transaction_rows_and_cursor_once_in_same_connection(monkeypatch):
    service = _service()
    conn = _RecordingConnection()
    service.storage = _RecordingStorage(conn)
    monkeypatch.setattr(service, "_upsert_transaction", lambda **kwargs: kwargs["conn"].execute("TRANSACTION ROW", []))
    service._sync_transactions(client=SimpleNamespace(transactions_sync=lambda _: _page(added=[_transaction()])), item={"item_id": "item-1", "transactions_cursor": "original"}, document_id="doc", access_token="test")
    queries = [sql for sql, _ in conn.calls]
    assert queries[-1] == "COMMIT"
    assert queries.count("COMMIT") == 1
    assert queries.index("TRANSACTION ROW") < next(i for i, sql in enumerate(queries) if "UPDATE plaid_items" in sql)


def test_cursor_write_failure_never_commits_transaction_rows(monkeypatch):
    service = _service()
    class FailingConnection(_RecordingConnection):
        def execute(self, sql, params=None):
            if "UPDATE plaid_items" in sql:
                raise RuntimeError("cursor write failed")
            return super().execute(sql, params)
    conn = FailingConnection()
    service.storage = _RecordingStorage(conn)
    monkeypatch.setattr(service, "_upsert_transaction", lambda **kwargs: kwargs["conn"].execute("TRANSACTION ROW", []))
    with pytest.raises(RuntimeError, match="cursor write failed"):
        service._sync_transactions(client=SimpleNamespace(transactions_sync=lambda _: _page(added=[_transaction()])), item={"item_id": "item-1", "transactions_cursor": "original"}, document_id="doc", access_token="test")
    assert ("COMMIT", None) not in conn.calls


def test_sync_restarts_mutated_pagination_at_original_cursor_and_discards_old_pages(monkeypatch):
    service = _service()
    conn = _RecordingConnection()
    service.storage = _RecordingStorage(conn)
    requests, writes = [], []
    responses = iter([_page(added=[_transaction(transaction_id="discard")], cursor="page-1", has_more=True), _mutation_error(), _page(added=[_transaction(transaction_id="keep")], cursor="final")])
    def sync(request):
        requests.append(request.cursor)
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr(service, "_upsert_transaction", lambda **kwargs: writes.append(kwargs["transaction"]["transaction_id"]))
    counts, cursor = service._sync_transactions(client=SimpleNamespace(transactions_sync=sync), item={"item_id": "item-1", "transactions_cursor": "original"}, document_id="doc", access_token="test")
    assert requests == ["original", "page-1", "original"]
    assert writes == ["keep"]
    assert counts["transaction_added_count"] == 1
    assert cursor == "final"


def test_repeated_pagination_mutations_are_bounded_and_never_committed():
    service = _service()
    conn = _RecordingConnection()
    service.storage = _RecordingStorage(conn)
    requests = []
    def sync(request):
        requests.append(request.cursor)
        raise _mutation_error()
    with pytest.raises(plaid_service.plaid.ApiException):
        service._sync_transactions(client=SimpleNamespace(transactions_sync=sync), item={"item_id": "item-1", "transactions_cursor": "original"}, document_id="doc", access_token="test")
    assert requests == ["original"] * 3
    assert ("COMMIT", None) not in conn.calls


def test_update_link_request_enables_account_selection_and_omits_products(monkeypatch):
    service = _service()
    service.cipher = SimpleNamespace(decrypt=lambda _: "access-token")
    monkeypatch.setattr(service, "_load_config", lambda: SimpleNamespace(country_codes=["US"], products=["transactions"], redirect_uri=None))
    monkeypatch.setattr(service, "_load_items", lambda **_: [{"access_token_ciphertext": "encrypted"}])
    requests = []
    monkeypatch.setattr(service, "_client", lambda _: SimpleNamespace(link_token_create=lambda request: requests.append(request.to_dict()) or {"link_token": "test"}))
    service.create_link_token(item_id="item-1")
    assert requests[0]["update"] == {"account_selection_enabled": True}
    assert "products" not in requests[0]


def test_single_item_sync_reloads_cursor_under_session_lock_and_releases_on_failure(monkeypatch):
    service = _service()
    class LockConnection(_RecordingConnection):
        def execute(self, sql, params=None):
            super().execute(sql, params)
            if "pg_try_advisory_lock" in sql:
                return _RecordingResult([True])
            if "SELECT transactions_cursor" in sql:
                return _RecordingResult(["persisted"])
            return _RecordingResult()
        def rollback(self):
            self.calls.append(("ROLLBACK", None))
    conn = LockConnection()
    service.storage = _RecordingStorage(conn)
    service.cipher = SimpleNamespace(decrypt=lambda _: "test")
    monkeypatch.setattr(service, "_ensure_sync_document", lambda **_: "doc")
    monkeypatch.setattr(service, "_upsert_accounts", lambda **_: 0)
    cursors = []
    def sync(request):
        cursors.append(request.cursor)
        raise RuntimeError("provider unavailable")
    client = SimpleNamespace(accounts_balance_get=lambda _: {"accounts": []}, transactions_sync=sync)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        service._sync_single_item(client=client, item={"item_id": "item-1", "access_token_ciphertext": "encrypted", "transactions_cursor": "stale"})
    assert cursors == ["persisted"]
    queries = [sql for sql, _ in conn.calls]
    assert "pg_try_advisory_lock" in queries[0]
    assert "pg_advisory_unlock" in queries[-1]
    assert queries.index("ROLLBACK") < len(queries) - 1


def test_overlapping_item_syncs_are_excluded_and_later_sync_reloads_committed_cursor(monkeypatch):
    service = _service()
    mutex = Lock()
    started, finish = Event(), Event()
    state = {"locked": False, "cursor": "original"}
    requests = []

    class Session(_RecordingConnection):
        def execute(self, sql, params=None):
            self.calls.append((sql, params))
            if "pg_try_advisory_lock" in sql:
                with mutex:
                    acquired = not state["locked"]
                    if acquired:
                        state["locked"] = True
                return _RecordingResult([acquired])
            if "pg_advisory_unlock" in sql:
                with mutex:
                    state["locked"] = False
            if "SELECT transactions_cursor" in sql:
                return _RecordingResult([state["cursor"]])
            if "UPDATE plaid_items" in sql:
                assert params is not None
                cursor = params[0]
                assert isinstance(cursor, str)
                self.pending_cursor = cursor
            return _RecordingResult()

        def commit(self):
            if hasattr(self, "pending_cursor"):
                state["cursor"] = self.pending_cursor
            super().commit()

    class Storage:
        @contextmanager
        def connection(self):
            yield Session()

    service.storage = Storage()
    service.cipher = SimpleNamespace(decrypt=lambda _: "test")
    monkeypatch.setattr(service, "_ensure_sync_document", lambda **_: "doc")
    monkeypatch.setattr(service, "_upsert_accounts", lambda **_: 0)
    item = {"item_id": "item-1", "access_token_ciphertext": "encrypted", "transactions_cursor": "stale"}
    def sync(request):
        requests.append(request.cursor)
        if len(requests) == 1:
            started.set()
            assert finish.wait(timeout=5)
        return _page(cursor="committed")
    client = SimpleNamespace(accounts_balance_get=lambda _: {"accounts": []}, transactions_sync=sync)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(service._sync_single_item, client=client, item=item)
        try:
            assert started.wait(timeout=5)
            with pytest.raises(PlaidIntegrationError, match="already running"):
                service._sync_single_item(client=client, item=item)
            assert requests == ["original"]
        finally:
            finish.set()
        assert future.result(timeout=5)["transaction_added_count"] == 0
    service._sync_single_item(client=client, item=item)
    assert requests == ["original", "committed"]
    assert state["locked"] is False
