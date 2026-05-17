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


def test_connection_portal_is_read_only() -> None:
    kwargs = _connection_portal_kwargs(
        user=SnapTradeUser(user_id="user", user_secret="secret"),
        broker="FIDELITY",
        redirect_uri="https://port.summitflow.dev/money",
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
    assert _redact_account_number("Z38367298") == "7298"
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
        redirect_uri="https://port.summitflow.dev/money",
        default_broker="FIDELITY",
    )

    assert result == {"configured": True}
    assert ("client_id", "existing-client", True) not in saved_fields
    assert ("consumer_key", "existing-key", True) not in saved_fields
    assert ("redirect_uri", "https://port.summitflow.dev/money", False) in saved_fields
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
