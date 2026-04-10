"""Unit tests for Jenny position action helpers."""

from __future__ import annotations

from unittest.mock import Mock

from app.portfolio.models import Position, PriceData
from app.services._jenny_position_actions import build_position_action_map


def test_build_position_action_map_uses_full_live_portfolio_for_weights() -> None:
    service = Mock()
    service.portfolio_mgr.get_positions.return_value = [
        Position(
            id="pos-tsla",
            account_id="acct-1",
            symbol="TSLA",
            shares=1.0,
            cost_basis=100.0,
            position_type="long",
        ),
        Position(
            id="pos-vti",
            account_id="acct-1",
            symbol="VTI",
            shares=9.0,
            cost_basis=100.0,
            position_type="long",
        ),
    ]
    service.price_fetcher.fetch_price_data.return_value = {
        "TSLA": PriceData(symbol="TSLA", price=100.0),
        "VTI": PriceData(symbol="VTI", price=100.0),
    }
    service.thesis_service.get_thesis.return_value = None

    action_map = build_position_action_map(
        service,
        {"TSLA": Mock(final_verdict="hold", reasons=[])},
    )

    assert action_map["TSLA"]["action"] == "hold"
    assert action_map["TSLA"]["weight_pct"] == 10.0
    service.price_fetcher.fetch_price_data.assert_called_once_with(["TSLA", "VTI"])
