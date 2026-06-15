"""Portfolio response enrichment from SnapTrade broker snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.api import portfolio as portfolio_api


def test_position_response_uses_snaptrade_snapshot_when_quote_missing() -> None:
    synced_at = datetime(2026, 6, 15, 17, 12, tzinfo=UTC)
    position = SimpleNamespace(
        id="snaptrade:source-account:SPAXX",
        account_id="portfolio-account",
        symbol="SPAXX",
        shares=3289.31,
        cost_basis=1.0,
        position_type="long",
        created_at=synced_at,
        updated_at=synced_at,
    )
    source = {
        "account_id": "source-account",
        "position_key": "SPAXX",
        "raw_symbol": "SPAXX",
        "security_kind": "money_market_fund",
        "average_purchase_price": 1.0,
        "cost_basis": 3289.31,
        "market_value": 3289.31,
        "price": 1.0,
        "currency": "USD",
        "last_synced_at": synced_at,
    }

    [response] = portfolio_api._build_position_responses(
        [position],
        {},
        {position.id: source},
    )

    assert response.current_price == 1.0
    assert response.current_value == 3289.31
    assert response.price_source == "snaptrade"
    assert response.price_updated_at == synced_at.isoformat()
    assert response.source == "snaptrade"
    assert response.source_account_id == "source-account"
    assert response.security_kind == "money_market_fund"
    assert response.source_market_value == 3289.31
    assert response.source_cost_basis == 3289.31


def test_position_response_treats_snaptrade_cost_basis_as_per_share() -> None:
    synced_at = datetime(2026, 6, 15, 17, 12, tzinfo=UTC)
    position = SimpleNamespace(
        id="snaptrade:source-account:VTI",
        account_id="portfolio-account",
        symbol="VTI",
        shares=994.409,
        cost_basis=0.2572503869132319,
        position_type="long",
        created_at=synced_at,
        updated_at=synced_at,
    )
    source = {
        "account_id": "source-account",
        "position_key": "VTI",
        "raw_symbol": "VTI",
        "security_kind": "etf",
        "average_purchase_price": None,
        "cost_basis": 255.8121,
        "market_value": 364311.6812,
        "price": 366.36,
        "currency": "USD",
        "last_synced_at": synced_at,
    }

    [response] = portfolio_api._build_position_responses(
        [position],
        {},
        {position.id: source},
    )

    assert response.cost_basis == 255.8121
    assert response.current_price == 366.36
    assert response.gain_pct is not None
    assert 40 < response.gain_pct < 45
