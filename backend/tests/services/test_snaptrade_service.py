from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import snaptrade_service
from app.services.snaptrade_service import (
    _READ_ONLY_CONNECTION_TYPE,
    SnapTradeConfigurationError,
    SnapTradeIntegrationError,
    SnapTradeNormalizedAccount,
    SnapTradeNormalizedPosition,
    SnapTradeReadOnlyClient,
    SnapTradeService,
    SnapTradeUser,
    _account_kind,
    _connection_portal_kwargs,
    _redact_account_number,
)


class _FakeSnapTradeClient:
    api_status = object()
    authentication = object()
    connections = object()
    account_information = object()


class _RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object] | None]] = []

    def execute(self, sql: str, params: list[object] | None = None) -> None:
        self.calls.append((sql, params))

    def commit(self) -> None:
        self.calls.append(("COMMIT", None))


class _RecordingStorage:
    def __init__(self, conn: _RecordingConnection) -> None:
        self.conn = conn

    def connection(self) -> _RecordingStorage:
        return self

    def __enter__(self) -> _RecordingConnection:
        return self.conn

    def __exit__(self, *args: object) -> None:
        return None


class _QueuedResult:
    def __init__(self, rows: list[list[object]] | None = None) -> None:
        self.rows = rows or []

    def fetchall(self) -> list[list[object]]:
        return self.rows

    def fetchone(self) -> list[object] | None:
        return self.rows[0] if self.rows else None


class _QueuedConnection:
    def __init__(self, results: list[_QueuedResult]) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, list[object] | None]] = []

    def execute(
        self,
        sql: str,
        params: list[object] | None = None,
    ) -> _QueuedResult:
        self.calls.append((" ".join(sql.split()), params))
        return self.results.pop(0) if self.results else _QueuedResult()

    def commit(self) -> None:
        self.calls.append(("COMMIT", None))


class _QueuedStorage:
    def __init__(self, conn: _QueuedConnection) -> None:
        self.conn = conn

    def connection(self) -> _QueuedStorage:
        return self

    def __enter__(self) -> _QueuedConnection:
        return self.conn

    def __exit__(self, *args: object) -> None:
        return None


class _FakeOrderApi:
    def __init__(self, orders: list[dict[str, object]]) -> None:
        self.orders = orders
        self.kwargs: dict[str, object] = {}

    def get_user_account_orders(self, **kwargs: object) -> list[dict[str, object]]:
        self.kwargs = kwargs
        return self.orders


class _FakeOrderClient:
    def __init__(self, orders: list[dict[str, object]]) -> None:
        self.account_information = _FakeOrderApi(orders)


class _FakePositionsApi:
    def __init__(self, response: object) -> None:
        self.response = response

    def get_all_account_positions(self, **_kwargs: object) -> object:
        return self.response


def _positions_account(account_id: str = "acct-1") -> SnapTradeNormalizedAccount:
    return SnapTradeNormalizedAccount(
        account_id=account_id,
        authorization_id="auth-1",
        name="Individual",
        institution_name="Fidelity",
        account_mask="1234",
        raw_type=None,
        portfolio_account_type="Taxable",
        balance=None,
        cash_balance=None,
        currency="USD",
        household_account_id=f"household-{account_id}",
        portfolio_account_id=f"portfolio-{account_id}",
        metadata={},
    )


def test_connection_portal_is_read_only() -> None:
    kwargs = _connection_portal_kwargs(
        user=SnapTradeUser(user_id="user", user_secret="secret"),
        broker="FIDELITY",
        redirect_uri="https://portfolio-ai.example/money",
    )

    assert kwargs["connection_type"] == _READ_ONLY_CONNECTION_TYPE
    assert kwargs["connection_type"] == "read"
    assert "trade" not in kwargs


def test_read_only_client_blocks_trading_surfaces() -> None:
    client = SnapTradeReadOnlyClient(_FakeSnapTradeClient())

    assert client.account_information is _FakeSnapTradeClient.account_information
    with pytest.raises(AttributeError, match="trading APIs are disabled"):
        _ = client.trading


def test_account_number_is_reduced_to_mask() -> None:
    assert _redact_account_number("Z00000001") == "0001"
    assert _redact_account_number("****1234") == "1234"
    assert _redact_account_number("123") == "123"


def test_fidelity_account_kind_mapping() -> None:
    assert _account_kind("ROTH IRA").portfolio_account_type == "Roth"
    assert _account_kind("Traditional IRA").portfolio_account_type == "IRA"
    assert _account_kind("Individual - TOD").portfolio_account_type == "Taxable"


def test_cash_balance_from_account_preserves_zero() -> None:
    assert SnapTradeService._cash_balance_from_account({"balance": {"cash": "0.00"}}) == Decimal(
        "0.00"
    )


def test_account_cash_balance_prefers_account_currency_then_usd() -> None:
    cash, currency = SnapTradeService._account_cash_balance(
        [
            {"cash": "15.00", "currency": {"code": "CAD"}},
            {"cash": "20.00", "currency": {"code": "USD"}},
        ],
        preferred_currency="CAD",
    )

    assert cash == Decimal("15.00")
    assert currency == "CAD"

    cash, currency = SnapTradeService._account_cash_balance(
        [
            {"cash": "15.00", "currency": {"code": "CAD"}},
            {"cash": "20.00", "currency": {"code": "USD"}},
        ],
    )

    assert cash == Decimal("20.00")
    assert currency == "USD"


def test_source_cash_balance_uses_account_total_when_cash_is_missing() -> None:
    account = SnapTradeNormalizedAccount(
        account_id="acct-1",
        authorization_id="auth-1",
        name="Individual - TOD",
        institution_name="Fidelity",
        account_mask="7544",
        raw_type=None,
        portfolio_account_type="Taxable",
        balance=Decimal("549593.06"),
        cash_balance=None,
        currency="USD",
        household_account_id="household-1",
        portfolio_account_id="portfolio-1",
        metadata={},
    )
    position = SnapTradeNormalizedPosition(
        position_key="vti",
        symbol="VTI",
        raw_symbol=None,
        security_id="vti",
        security_kind=None,
        units=Decimal("1488"),
        price=Decimal("362.74"),
        average_purchase_price=None,
        market_value=Decimal("539757.12"),
        cost_basis=None,
        currency="USD",
        metadata={},
    )

    assert SnapTradeService._source_cash_balance(account, [position]) == Decimal("9835.94")
    assert SnapTradeService._source_cash_balance(account, []) == Decimal("549593.06")


def test_source_cash_balance_prefers_direct_broker_cash() -> None:
    account = SnapTradeNormalizedAccount(
        account_id="acct-1",
        authorization_id="auth-1",
        name="Individual - TOD",
        institution_name="Fidelity",
        account_mask="7544",
        raw_type=None,
        portfolio_account_type="Taxable",
        balance=Decimal("539830.07"),
        cash_balance=Decimal("72.95"),
        currency="USD",
        household_account_id="household-1",
        portfolio_account_id="portfolio-1",
        metadata={},
    )
    position = SnapTradeNormalizedPosition(
        position_key="vti",
        symbol="VTI",
        raw_symbol=None,
        security_id="vti",
        security_kind=None,
        units=Decimal("1488"),
        price=Decimal("362.74"),
        average_purchase_price=None,
        market_value=Decimal("539757.12"),
        cost_basis=None,
        currency="USD",
        metadata={},
    )

    assert SnapTradeService._source_cash_balance(account, [position]) == Decimal("72.95")


def test_position_cost_basis_keeps_snaptrade_per_share_basis() -> None:
    position = SnapTradeNormalizedPosition(
        position_key="vti",
        symbol="VTI",
        raw_symbol=None,
        security_id="vti",
        security_kind="etf",
        units=Decimal("994.409"),
        price=Decimal("366.36"),
        average_purchase_price=None,
        market_value=Decimal("364311.6812"),
        cost_basis=Decimal("255.8121"),
        currency="USD",
        metadata={},
    )

    assert SnapTradeService._position_cost_basis_per_share(position) == Decimal("255.8121")


def test_position_cost_basis_divides_implausible_total_basis() -> None:
    position = SnapTradeNormalizedPosition(
        position_key="vti",
        symbol="VTI",
        raw_symbol=None,
        security_id="vti",
        security_kind="etf",
        units=Decimal("10"),
        price=Decimal("100"),
        average_purchase_price=None,
        market_value=Decimal("1000"),
        cost_basis=Decimal("800"),
        currency="USD",
        metadata={},
    )

    assert SnapTradeService._position_cost_basis_per_share(position) == Decimal("800")

    position.cost_basis = Decimal("8000")
    assert SnapTradeService._position_cost_basis_per_share(position) == Decimal("800")


def test_source_cash_balance_reconciles_incompatible_direct_broker_cash() -> None:
    account = SnapTradeNormalizedAccount(
        account_id="acct-1",
        authorization_id="auth-1",
        name="ROTH IRA",
        institution_name="Fidelity",
        account_mask="7544",
        raw_type=None,
        portfolio_account_type="Roth",
        balance=Decimal("49774.94"),
        cash_balance=Decimal("49541.96"),
        currency="USD",
        household_account_id="household-1",
        portfolio_account_id="portfolio-1",
        metadata={},
    )
    position = SnapTradeNormalizedPosition(
        position_key="vgt",
        symbol="VGT",
        raw_symbol=None,
        security_id="vgt",
        security_kind=None,
        units=Decimal("401.702"),
        price=Decimal("123.91"),
        average_purchase_price=None,
        market_value=Decimal("49774.8948"),
        cost_basis=None,
        currency="USD",
        metadata={},
    )

    assert SnapTradeService._source_cash_balance(account, [position]) == Decimal("0")


def test_source_cash_balance_uses_total_when_empty_account_cash_is_incompatible() -> None:
    account = SnapTradeNormalizedAccount(
        account_id="acct-1",
        authorization_id="auth-1",
        name="Cash Management",
        institution_name="Fidelity",
        account_mask="7544",
        raw_type=None,
        portfolio_account_type="Taxable",
        balance=Decimal("37571.48"),
        cash_balance=Decimal("0.00"),
        currency="USD",
        household_account_id="household-1",
        portfolio_account_id="portfolio-1",
        metadata={},
    )

    assert SnapTradeService._source_cash_balance(account, []) == Decimal("37571.48")


def test_normalize_order_extracts_symbol_and_execution_fields() -> None:
    service = object.__new__(SnapTradeService)

    order = service._normalize_order(
        {
            "brokerage_order_id": "937307326",
            "status": "EXECUTED",
            "action": "BUY",
            "universal_symbol": {
                "symbol": "VGT",
                "raw_symbol": "VGT",
                "currency": {"code": "USD"},
            },
            "filled_quantity": "395.000000000000000000",
            "execution_price": "125.0899000000",
            "order_type": "Market",
            "time_in_force": "Day",
            "time_executed": "2026-06-02T04:00:00Z",
        }
    )

    assert order is not None
    assert order.brokerage_order_id == "937307326"
    assert order.symbol == "VGT"
    assert order.raw_symbol == "VGT"
    assert order.filled_quantity == Decimal("395.000000000000000000")
    assert order.execution_price == Decimal("125.0899000000")
    assert order.currency == "USD"
    assert order.time_executed == datetime(2026, 6, 2, 4, 0, tzinfo=UTC)


def test_sync_orders_upserts_recent_brokerage_orders() -> None:
    conn = _RecordingConnection()
    service = object.__new__(SnapTradeService)
    service.storage = _RecordingStorage(conn)
    client = _FakeOrderClient(
        [
            {
                "brokerage_order_id": "order-1",
                "status": "EXECUTED",
                "action": "SELL",
                "universal_symbol": {"symbol": "VTI"},
                "filled_quantity": "2",
                "execution_price": "400.12",
                "time_executed": "2026-06-02T04:00:00Z",
            }
        ]
    )

    count = service._sync_orders(
        client=client,
        user=SnapTradeUser(user_id="user", user_secret="secret"),
        account_id="acct-1",
    )

    assert count == 1
    sql, params = conn.calls[0]
    assert "INSERT INTO snaptrade_orders" in sql
    assert "ON CONFLICT (account_id, brokerage_order_id)" in sql
    assert params is not None
    assert params[1:7] == ["acct-1", "order-1", "EXECUTED", "SELL", "VTI", None]
    assert client.account_information.kwargs["state"] == "all"


def test_configure_keeps_saved_credentials_when_secret_inputs_are_blank(monkeypatch) -> None:
    service = object.__new__(SnapTradeService)
    service.storage = object()
    service.cipher = SimpleNamespace(available=True)
    saved_fields: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(service, "_ensure_source_registry", lambda: None)
    monkeypatch.setattr(service, "get_status", lambda: {"configured": True})
    monkeypatch.setattr(
        snaptrade_service,
        "get_source_credentials",
        lambda _storage, _source_id: {
            "client_id": "existing-client",
            "consumer_key": "existing-key",
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

    monkeypatch.setattr(snaptrade_service, "set_source_credential", fake_set_source_credential)

    result = service.configure(
        client_id="",
        consumer_key=None,
        redirect_uri="https://portfolio-ai.example/money",
        default_broker="FIDELITY",
    )

    assert result == {"configured": True}
    assert ("client_id", "existing-client", True) not in saved_fields
    assert ("consumer_key", "existing-key", True) not in saved_fields
    assert ("redirect_uri", "https://portfolio-ai.example/money", False) in saved_fields
    assert ("default_broker", "FIDELITY", False) in saved_fields


def test_configure_still_requires_credentials_for_first_setup(monkeypatch) -> None:
    service = object.__new__(SnapTradeService)
    service.storage = object()
    service.cipher = SimpleNamespace(available=True)
    monkeypatch.setattr(
        snaptrade_service,
        "get_source_credentials",
        lambda _storage, _source_id: {},
    )

    with pytest.raises(SnapTradeConfigurationError) as exc_info:
        service.configure(
            client_id=None,
            consumer_key=None,
            redirect_uri=None,
            default_broker="FIDELITY",
        )

    assert str(exc_info.value) == "SnapTrade client_id and consumer_key are required."


def test_replace_portfolio_positions_removes_unmanaged_rows_for_source_owned_account() -> None:
    account = SnapTradeNormalizedAccount(
        account_id="acct-1",
        authorization_id="auth-1",
        name="Traditional IRA",
        institution_name="Fidelity",
        account_mask="4181",
        raw_type=None,
        portfolio_account_type="IRA",
        balance=Decimal("376672.30"),
        cash_balance=None,
        currency="USD",
        household_account_id="household-1",
        portfolio_account_id="portfolio-1",
        metadata={},
    )
    position = SnapTradeNormalizedPosition(
        position_key="vti",
        symbol="VTI",
        raw_symbol=None,
        security_id="vti",
        security_kind=None,
        units=Decimal("994.409"),
        price=Decimal("362.74"),
        average_purchase_price=None,
        market_value=Decimal("360711.9207"),
        cost_basis=None,
        currency="USD",
        metadata={},
    )
    conn = _RecordingConnection()
    service = object.__new__(SnapTradeService)

    service._replace_portfolio_positions(
        conn=conn,
        account=account,
        positions=[position],
        existing_portfolio_ids={},
        synced_at=datetime(2026, 5, 16, 18, 0, tzinfo=UTC),
    )

    delete_sql, delete_params = conn.calls[0]
    assert "strategy_id IS NULL" in delete_sql
    assert "id <> ALL" in delete_sql
    assert delete_params == ["portfolio-1", ["snaptrade:acct-1:vti"]]


def test_portfolio_positions_skip_snaptrade_other_instruments() -> None:
    etf = SnapTradeNormalizedPosition(
        position_key="vti",
        symbol="VTI",
        raw_symbol="VTI",
        security_id="vti",
        security_kind="etf",
        units=Decimal("1"),
        price=Decimal("100"),
        average_purchase_price=None,
        market_value=Decimal("100"),
        cost_basis=None,
        currency="USD",
        metadata={},
    )
    plan_fund = SnapTradeNormalizedPosition(
        position_key="plan-fund",
        symbol="NHFSMKX98",
        raw_symbol="NHFSMKX98",
        security_id="plan-fund",
        security_kind="other",
        units=Decimal("1"),
        price=Decimal("75.82"),
        average_purchase_price=None,
        market_value=Decimal("75.82"),
        cost_basis=None,
        currency="USD",
        metadata={},
    )

    assert SnapTradeService._portfolio_positions([etf, plan_fund]) == [etf]


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        {},
        {"results": None},
        {"results": {}},
        {"results": ["not-a-position"]},
        {"results": [{"instrument": {"symbol": "VTI"}}]},
    ],
)
def test_malformed_position_snapshot_preserves_current_mirror(response: object) -> None:
    conn = _QueuedConnection([])
    service = object.__new__(SnapTradeService)
    service.storage = _QueuedStorage(conn)
    client = SimpleNamespace(account_information=_FakePositionsApi(response))

    with pytest.raises(SnapTradeIntegrationError, match="malformed|valid symbol"):
        service._sync_positions(
            client=client,
            user=SnapTradeUser(user_id="user-1", user_secret="secret"),
            account=_positions_account(),
        )

    assert conn.calls == []


def test_malformed_position_snapshot_does_not_advance_existing_account_freshness() -> None:
    conn = _RecordingConnection()
    service = object.__new__(SnapTradeService)
    service.storage = _RecordingStorage(conn)
    service._resolve_household_account = lambda **_kwargs: "household-1"
    service._resolve_portfolio_account = lambda **_kwargs: "portfolio-1"
    account = service._sync_account(
        user=SnapTradeUser(user_id="user-1", user_secret="secret"),
        raw_account={"id": "acct-1", "name": "Individual"},
        authorization_id="auth-1",
    )
    assert account is not None
    account_upsert_sql, _account_params = conn.calls[0]
    assert "last_synced_at = snaptrade_accounts.last_synced_at" in account_upsert_sql
    calls_before_position_validation = list(conn.calls)
    client = SimpleNamespace(
        account_information=_FakePositionsApi(
            {"results": [{"instrument": {"symbol": "VTI"}}]}
        )
    )

    with pytest.raises(SnapTradeIntegrationError, match="valid symbol"):
        service._sync_positions(
            client=client,
            user=SnapTradeUser(user_id="user-1", user_secret="secret"),
            account=account,
        )

    assert conn.calls == calls_before_position_validation


def test_true_empty_position_snapshot_is_authoritative() -> None:
    conn = _QueuedConnection([_QueuedResult([])])
    service = object.__new__(SnapTradeService)
    service.storage = _QueuedStorage(conn)
    client = SimpleNamespace(
        account_information=_FakePositionsApi({"results": []})
    )

    result = service._sync_positions(
        client=client,
        user=SnapTradeUser(user_id="user-1", user_secret="secret"),
        account=_positions_account(),
    )

    assert result == (0, 0, set())
    assert any(sql.startswith("DELETE FROM snaptrade_positions") for sql, _ in conn.calls)
    assert any(sql.startswith("DELETE FROM portfolio_positions") for sql, _ in conn.calls)


def test_valid_position_snapshot_advances_freshness_even_without_cash_value() -> None:
    conn = _RecordingConnection()
    service = object.__new__(SnapTradeService)
    synced_at = datetime(2026, 7, 14, 15, 0, tzinfo=UTC)

    service._update_portfolio_account_cash_balance(
        conn=conn,
        account=_positions_account(),
        positions=[],
        synced_at=synced_at,
    )

    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert "UPDATE snaptrade_accounts" in sql
    assert "cash_balance = COALESCE(%s, cash_balance)" in sql
    assert "last_synced_at = %s" in sql
    assert params == [None, synced_at, "acct-1"]


def test_cash_balance_update_persists_to_source_and_portfolio_accounts() -> None:
    account = SnapTradeNormalizedAccount(
        account_id="acct-1",
        authorization_id="auth-1",
        name="Individual - TOD",
        institution_name="Fidelity",
        account_mask="7544",
        raw_type=None,
        portfolio_account_type="Taxable",
        balance=Decimal("72.95"),
        cash_balance=Decimal("72.95"),
        currency="USD",
        household_account_id="household-1",
        portfolio_account_id="portfolio-1",
        metadata={},
    )
    conn = _RecordingConnection()
    service = object.__new__(SnapTradeService)
    synced_at = datetime(2026, 6, 3, 22, 0, tzinfo=UTC)

    service._update_portfolio_account_cash_balance(
        conn=conn,
        account=account,
        positions=[],
        synced_at=synced_at,
    )

    assert len(conn.calls) == 2
    portfolio_sql, portfolio_params = conn.calls[0]
    source_sql, source_params = conn.calls[1]
    assert "UPDATE portfolio_accounts" in portfolio_sql
    assert portfolio_params == [72.95, synced_at, "portfolio-1"]
    assert "UPDATE snaptrade_accounts" in source_sql
    assert source_params == [72.95, synced_at, "acct-1"]


def test_cash_balance_update_persists_reconciled_cash_when_direct_cash_is_incompatible() -> None:
    account = SnapTradeNormalizedAccount(
        account_id="acct-1",
        authorization_id="auth-1",
        name="Traditional IRA",
        institution_name="Fidelity",
        account_mask="4181",
        raw_type=None,
        portfolio_account_type="IRA",
        balance=Decimal("386059.06"),
        cash_balance=Decimal("16441.73"),
        currency="USD",
        household_account_id="household-1",
        portfolio_account_id="portfolio-1",
        metadata={},
    )
    vgt_position = SnapTradeNormalizedPosition(
        position_key="vgt",
        symbol="VGT",
        raw_symbol=None,
        security_id="vgt",
        security_kind=None,
        units=Decimal("133.056"),
        price=Decimal("123.91"),
        average_purchase_price=None,
        market_value=Decimal("16486.96896"),
        cost_basis=None,
        currency="USD",
        metadata={},
    )
    vti_position = SnapTradeNormalizedPosition(
        position_key="vti",
        symbol="VTI",
        raw_symbol=None,
        security_id="vti",
        security_kind=None,
        units=Decimal("994.409"),
        price=Decimal("371.65"),
        average_purchase_price=None,
        market_value=Decimal("369572.1049"),
        cost_basis=None,
        currency="USD",
        metadata={},
    )
    conn = _RecordingConnection()
    service = object.__new__(SnapTradeService)
    synced_at = datetime(2026, 6, 4, 12, 39, tzinfo=UTC)

    service._update_portfolio_account_cash_balance(
        conn=conn,
        account=account,
        positions=[vgt_position, vti_position],
        synced_at=synced_at,
    )

    assert len(conn.calls) == 2
    portfolio_sql, portfolio_params = conn.calls[0]
    source_sql, source_params = conn.calls[1]
    assert "UPDATE portfolio_accounts" in portfolio_sql
    assert portfolio_params == [0.0, synced_at, "portfolio-1"]
    assert "UPDATE snaptrade_accounts" in source_sql
    assert source_params == [0.0, synced_at, "acct-1"]


def test_account_snapshot_reconciliation_clears_inactive_current_mirror() -> None:
    conn = _QueuedConnection(
        [
            _QueuedResult([["portfolio-1"]]),
            _QueuedResult(),
        ]
    )
    service = object.__new__(SnapTradeService)
    service.storage = _QueuedStorage(conn)

    removed = service._reconcile_snaptrade_accounts_for_connection(
        authorization_id="auth-1",
        authoritative_account_ids={"account-current"},
    )

    assert removed == 1
    update_sql, update_params = conn.calls[0]
    assert update_sql.startswith("UPDATE snaptrade_accounts")
    assert "is_active = FALSE" in update_sql
    assert "account_id <> ALL" in update_sql
    assert update_params is not None
    assert update_params[1:] == ["auth-1", ["account-current"]]
    assert any(sql.startswith("DELETE FROM portfolio_positions") for sql, _ in conn.calls)
    assert any(
        sql.startswith("UPDATE portfolio_accounts") and params is not None and params[-1] == "portfolio-1"
        for sql, params in conn.calls
    )


def test_account_snapshot_reconciliation_preserves_mirror_with_active_alias() -> None:
    conn = _QueuedConnection(
        [
            _QueuedResult([["portfolio-1"]]),
            _QueuedResult([[1]]),
        ]
    )
    service = object.__new__(SnapTradeService)
    service.storage = _QueuedStorage(conn)

    removed = service._reconcile_snaptrade_accounts_for_connection(
        authorization_id="auth-1",
        authoritative_account_ids=set(),
    )

    assert removed == 1
    assert not any(sql.startswith("DELETE FROM portfolio_positions") for sql, _ in conn.calls)
    assert not any(sql.startswith("UPDATE portfolio_accounts") for sql, _ in conn.calls)


def test_connection_snapshot_reconciliation_deactivates_absent_accounts() -> None:
    conn = _QueuedConnection(
        [
            _QueuedResult([["auth-old"]]),
            _QueuedResult([["portfolio-old"]]),
            _QueuedResult(),
        ]
    )
    service = object.__new__(SnapTradeService)
    service.storage = _QueuedStorage(conn)

    removed_connections, removed_accounts = service._reconcile_snaptrade_connections(
        user_id="user-1",
        authoritative_connection_ids={"auth-current"},
    )

    assert (removed_connections, removed_accounts) == (1, 1)
    connection_sql, connection_params = conn.calls[0]
    assert connection_sql.startswith("UPDATE snaptrade_connections")
    assert "authorization_id <> ALL" in connection_sql
    assert connection_params is not None
    assert connection_params[1:] == ["user-1", ["auth-current"]]
    assert any(sql.startswith("DELETE FROM portfolio_positions") for sql, _ in conn.calls)


class _SyncConnectionsApi:
    def __init__(
        self,
        *,
        connections: object,
        accounts: object = None,
        account_error: Exception | None = None,
        connection_error: Exception | None = None,
    ) -> None:
        self.connections = connections
        self.accounts = [] if accounts is None else accounts
        self.account_error = account_error
        self.connection_error = connection_error

    def list_brokerage_authorizations(self, **_kwargs: object) -> object:
        if self.connection_error is not None:
            raise self.connection_error
        return self.connections

    def list_brokerage_authorization_accounts(self, **_kwargs: object) -> object:
        if self.account_error is not None:
            raise self.account_error
        return self.accounts


def _sync_test_service(client: object) -> SnapTradeService:
    service = object.__new__(SnapTradeService)
    service.storage = object()
    service._load_config = SimpleNamespace
    service._client = lambda _config: client
    service._load_user = lambda: SnapTradeUser(
        user_id="user-1", user_secret="secret"
    )
    service._upsert_connection = lambda **_kwargs: None
    service._reconcile_account_ownership = lambda: None
    service._record_user_sync = lambda *_args, **_kwargs: None
    service._record_user_error = lambda *_args, **_kwargs: None
    return service


def _stub_sync_tail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(snaptrade_service, "bridge_cash_activities", lambda _storage: {})
    monkeypatch.setattr(
        snaptrade_service,
        "ensure_symbols_in_watchlist",
        lambda *_args, **_kwargs: None,
    )


def test_account_provider_error_does_not_deactivate_prior_snapshot(monkeypatch) -> None:
    _stub_sync_tail(monkeypatch)
    client = SimpleNamespace(
        connections=_SyncConnectionsApi(
            connections=[{"id": "auth-1", "disabled": False}],
            account_error=snaptrade_service.ApiException(status=502, reason="unavailable"),
        ),
        account_information=SimpleNamespace(),
    )
    service = _sync_test_service(client)
    account_reconciliations: list[tuple[str, set[str]]] = []
    service._reconcile_snaptrade_accounts_for_connection = (  # type: ignore[method-assign]
        lambda *, authorization_id, authoritative_account_ids: account_reconciliations.append(
            (authorization_id, authoritative_account_ids)
        )
        or 0
    )
    service._reconcile_snaptrade_connections = (  # type: ignore[method-assign]
        lambda **_kwargs: (0, 0)
    )

    result = service.sync()

    assert account_reconciliations == []
    assert len(result["errors"]) == 1


def test_successful_empty_account_snapshot_is_authoritative(monkeypatch) -> None:
    _stub_sync_tail(monkeypatch)
    client = SimpleNamespace(
        connections=_SyncConnectionsApi(
            connections=[{"id": "auth-1", "disabled": False}],
            accounts=[],
        ),
        account_information=SimpleNamespace(),
    )
    service = _sync_test_service(client)
    account_reconciliations: list[tuple[str, set[str]]] = []
    service._reconcile_snaptrade_accounts_for_connection = (  # type: ignore[method-assign]
        lambda *, authorization_id, authoritative_account_ids: account_reconciliations.append(
            (authorization_id, authoritative_account_ids)
        )
        or 0
    )
    service._reconcile_snaptrade_connections = (  # type: ignore[method-assign]
        lambda **_kwargs: (0, 0)
    )

    result = service.sync()

    assert account_reconciliations == [("auth-1", set())]
    assert result["errors"] == []


def test_connection_provider_error_never_reconciles_lifecycle(monkeypatch) -> None:
    _stub_sync_tail(monkeypatch)
    client = SimpleNamespace(
        connections=_SyncConnectionsApi(
            connections=[],
            connection_error=snaptrade_service.ApiException(
                status=502,
                reason="unavailable",
            ),
        ),
        account_information=SimpleNamespace(),
    )
    service = _sync_test_service(client)
    lifecycle_calls: list[str] = []
    service._reconcile_snaptrade_accounts_for_connection = (  # type: ignore[method-assign]
        lambda **_kwargs: lifecycle_calls.append("accounts") or 0
    )
    service._reconcile_snaptrade_connections = (  # type: ignore[method-assign]
        lambda **_kwargs: lifecycle_calls.append("connections") or (0, 0)
    )

    with pytest.raises(SnapTradeIntegrationError, match="unavailable"):
        service.sync()

    assert lifecycle_calls == []


def test_account_validation_failure_is_partial_and_does_not_abort_later_accounts(
    monkeypatch,
) -> None:
    _stub_sync_tail(monkeypatch)
    client = SimpleNamespace(
        connections=_SyncConnectionsApi(
            connections=[{"id": "auth-1", "disabled": False}],
            accounts=[{"id": "acct-bad"}, {"id": "acct-good"}],
        ),
        account_information=SimpleNamespace(
            get_user_account_balance=lambda **_kwargs: []
        ),
    )
    service = _sync_test_service(client)
    position_calls: list[str] = []
    activity_calls: list[str] = []
    order_calls: list[str] = []
    recorded_syncs: list[tuple[str, list[dict[str, object]]]] = []
    account_reconciliations: list[tuple[str, set[str]]] = []

    service._sync_account = (  # type: ignore[method-assign]
        lambda **kwargs: _positions_account(str(kwargs["raw_account"]["id"]))
    )

    def sync_positions(**kwargs: object) -> tuple[int, int, set[str]]:
        account = kwargs["account"]
        assert isinstance(account, SnapTradeNormalizedAccount)
        position_calls.append(account.account_id)
        if account.account_id == "acct-bad":
            raise SnapTradeIntegrationError(
                "SnapTrade returned a position without a valid symbol and quantity.",
                error_payload={
                    "surface": "positions",
                    "error_code": "INVALID_POSITION",
                    "error_message": (
                        "SnapTrade returned a position without a valid symbol and quantity."
                    ),
                },
            )
        return 1, 1, {"VTI"}

    service._sync_positions = sync_positions  # type: ignore[method-assign]
    service._sync_activities = (  # type: ignore[method-assign]
        lambda **kwargs: activity_calls.append(str(kwargs["account_id"])) or 2
    )
    service._sync_orders = (  # type: ignore[method-assign]
        lambda **kwargs: order_calls.append(str(kwargs["account_id"])) or 3
    )
    service._reconcile_snaptrade_accounts_for_connection = (  # type: ignore[method-assign]
        lambda *, authorization_id, authoritative_account_ids: account_reconciliations.append(
            (authorization_id, authoritative_account_ids)
        )
        or 0
    )
    service._reconcile_snaptrade_connections = (  # type: ignore[method-assign]
        lambda **_kwargs: (0, 0)
    )
    service._record_user_sync = (  # type: ignore[method-assign]
        lambda user_id, *, errors: recorded_syncs.append(
            (user_id, [dict(error) for error in errors])
        )
    )

    result = service.sync()

    assert result["status"] == "partial"
    assert result["error_count"] == 1
    assert result["position_count"] == 1
    assert result["activity_count"] == 4
    assert result["order_count"] == 6
    assert position_calls == ["acct-bad", "acct-good"]
    assert activity_calls == ["acct-bad", "acct-good"]
    assert order_calls == ["acct-bad", "acct-good"]
    assert account_reconciliations == [
        ("auth-1", {"acct-bad", "acct-good"})
    ]
    assert recorded_syncs[0][0] == "user-1"
    errors = recorded_syncs[0][1]
    assert errors == result["errors"]
    assert errors[0]["authorization_id"] == "auth-1"
    assert errors[0]["account_id"] == "acct-bad"
    assert errors[0]["surface"] == "positions"
    assert errors[0]["error_code"] == "INVALID_POSITION"


def test_activity_failure_keeps_position_counts_and_still_attempts_orders(
    monkeypatch,
) -> None:
    _stub_sync_tail(monkeypatch)
    client = SimpleNamespace(
        connections=_SyncConnectionsApi(
            connections=[{"id": "auth-1", "disabled": False}],
            accounts=[{"id": "acct-1"}],
        ),
        account_information=SimpleNamespace(
            get_user_account_balance=lambda **_kwargs: []
        ),
    )
    service = _sync_test_service(client)
    activity_calls: list[str] = []
    order_calls: list[str] = []
    service._sync_account = (  # type: ignore[method-assign]
        lambda **_kwargs: _positions_account()
    )
    service._sync_positions = (  # type: ignore[method-assign]
        lambda **_kwargs: (2, 1, {"VTI"})
    )

    def fail_activities(**kwargs: object) -> int:
        activity_calls.append(str(kwargs["account_id"]))
        raise snaptrade_service.ApiException(status=503, reason="activities unavailable")

    service._sync_activities = fail_activities  # type: ignore[method-assign]
    service._sync_orders = (  # type: ignore[method-assign]
        lambda **kwargs: order_calls.append(str(kwargs["account_id"])) or 4
    )
    service._reconcile_snaptrade_accounts_for_connection = (  # type: ignore[method-assign]
        lambda **_kwargs: 0
    )
    service._reconcile_snaptrade_connections = (  # type: ignore[method-assign]
        lambda **_kwargs: (0, 0)
    )

    result = service.sync()

    assert result["status"] == "partial"
    assert result["error_count"] == 1
    assert result["position_count"] == 2
    assert result["portfolio_position_count"] == 1
    assert result["activity_count"] == 0
    assert result["order_count"] == 4
    assert activity_calls == ["acct-1"]
    assert order_calls == ["acct-1"]
    errors = result["errors"]
    assert isinstance(errors, list)
    error = errors[0]
    assert isinstance(error, dict)
    assert error["surface"] == "activities"
    assert error["error_code"] == "503"


def test_record_user_sync_persists_partial_state_without_advancing_success() -> None:
    partial_conn = _RecordingConnection()
    service = object.__new__(SnapTradeService)
    service.storage = _RecordingStorage(partial_conn)
    errors = [
        {
            "account_id": "acct-bad",
            "surface": "positions",
            "error_code": "INVALID_POSITION",
            "error_message": "Invalid position snapshot.",
        }
    ]

    service._record_user_sync("user-1", errors=errors)

    partial_sql, partial_params = partial_conn.calls[0]
    assert "WHEN %s THEN last_successful_sync_at" in partial_sql
    assert partial_params is not None
    assert partial_params[0] is True
    assert partial_params[2] == "SnapTrade sync partially completed with 1 error(s)."
    partial_state = json.loads(str(partial_params[3]))["last_sync"]
    assert partial_state["status"] == "partial"
    assert partial_state["error_count"] == 1
    assert partial_state["errors"] == errors

    success_conn = _RecordingConnection()
    service.storage = _RecordingStorage(success_conn)
    service._record_user_sync("user-1", errors=[])

    _success_sql, success_params = success_conn.calls[0]
    assert success_params is not None
    assert success_params[0] is False
    assert isinstance(success_params[1], datetime)
    assert success_params[2] is None
    success_state = json.loads(str(success_params[3]))["last_sync"]
    assert success_state == {
        "status": "success",
        "attempted_at": success_params[1].isoformat(),
        "error_count": 0,
        "errors": [],
    }


def test_status_exposes_structured_partial_sync_state() -> None:
    attempted_at = datetime(2026, 7, 14, 14, 30, tzinfo=UTC)
    prior_success = datetime(2026, 7, 12, 10, 0, tzinfo=UTC)
    last_error = "SnapTrade sync partially completed with 1 error(s)."
    sync_error = {
        "account_id": "acct-bad",
        "surface": "positions",
        "error_code": "INVALID_POSITION",
        "error_message": "Invalid position snapshot.",
    }
    conn = _QueuedConnection(
        [
            _QueuedResult([]),
            _QueuedResult([[1]]),
            _QueuedResult([[0]]),
            _QueuedResult([[0]]),
            _QueuedResult([[0]]),
            _QueuedResult([[0]]),
            _QueuedResult([[0]]),
            _QueuedResult([[0]]),
            _QueuedResult([[prior_success]]),
            _QueuedResult([]),
            _QueuedResult([]),
            _QueuedResult([]),
            _QueuedResult(
                [
                    [
                        last_error,
                        {
                            "last_sync": {
                                "status": "partial",
                                "attempted_at": attempted_at.isoformat(),
                                "error_count": 1,
                                "errors": [sync_error],
                            }
                        },
                        attempted_at,
                    ]
                ]
            ),
        ]
    )
    service = object.__new__(SnapTradeService)
    service.storage = _QueuedStorage(conn)
    service.cipher = SimpleNamespace(available=True)

    result = service.get_status()

    assert result["last_successful_sync_at"] == prior_success.isoformat()
    assert result["last_error"] == last_error
    assert result["last_sync_status"] == "partial"
    assert result["last_sync_attempt_at"] == attempted_at.isoformat()
    assert result["last_sync_error_count"] == 1
    assert result["last_sync_errors"] == [sync_error]
