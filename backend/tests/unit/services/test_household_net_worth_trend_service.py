"""Unit tests for household net-worth trend construction."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import polars as pl

from app.portfolio.models import Account, Position, PriceData
from app.services.household_net_worth_trend_service import build_net_worth_trend


def test_build_net_worth_trend_reprices_current_symbol_holdings() -> None:
    dashboard = Mock()
    dashboard.generated_at = "2026-05-06T10:00:00+00:00"
    dashboard.overview = Mock(
        total_tracked_assets=1100.0,
        liabilities_total=100.0,
        net_worth=1000.0,
        net_worth_status="estimated",
        net_worth_detail="Known net worth from current data.",
        gap_count=2,
        needs_refresh_count=1,
    )
    dashboard.accounts = [
        Mock(current_value=600.0, balance_freshness_status="fresh"),
        Mock(current_value=None, balance_freshness_status="needs_evidence"),
        Mock(current_value=500.0, balance_freshness_status="stale"),
    ]

    service = Mock()
    service.get_dashboard.return_value = dashboard
    service.portfolio_mgr.get_accounts.return_value = [
        Account(id="acct-1", name="Taxable", account_type="Taxable", cash_balance=100.0)
    ]
    service.portfolio_mgr.get_positions.return_value = [
        Position(
            id="pos-1",
            account_id="acct-1",
            symbol="ABC",
            shares=10.0,
            cost_basis=20.0,
            position_type="long",
        )
    ]
    service.price_fetcher.fetch_price_data.return_value = {
        "ABC": PriceData(
            symbol="ABC",
            price=50.0,
            cached_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
        )
    }
    service.storage.query.return_value = pl.DataFrame(
        [
            {"symbol": "ABC", "date": "2026-05-01", "close": 40.0},
            {"symbol": "ABC", "date": "2026-05-05", "close": 45.0},
        ]
    )

    trend = build_net_worth_trend(service, days=30)

    assert trend.as_of_date == "2026-05-06"
    assert trend.holdings_symbol_count == 1
    assert trend.holdings_position_count == 1
    assert trend.points[0].net_worth == 900.0
    assert trend.points[1].net_worth == 950.0
    assert trend.points[-1].net_worth == 1000.0
    assert trend.points[-1].priced_holdings_value == 500.0
    assert trend.missing_balance_account_count == 1
    assert trend.stale_account_count == 1
    assert "Current shares are repriced" in trend.methodology
