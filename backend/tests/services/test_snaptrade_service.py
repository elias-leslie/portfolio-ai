from __future__ import annotations

import pytest

from app.services.snaptrade_service import (
    _READ_ONLY_CONNECTION_TYPE,
    SnapTradeReadOnlyClient,
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
