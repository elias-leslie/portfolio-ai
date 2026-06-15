from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import snaptrade_service
from app.services.snaptrade_service import (
    _READ_ONLY_CONNECTION_TYPE,
    SnapTradeConfigurationError,
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
