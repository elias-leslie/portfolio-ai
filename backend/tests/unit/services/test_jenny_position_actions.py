"""Unit tests for Jenny position action helpers."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.portfolio.fund_lookthrough import FundHolding, FundLookthroughProfile
from app.portfolio.models import Position, PriceData
from app.services._jenny_position_actions import (
    build_position_action_map,
    get_position_action,
)


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


def test_get_position_action_keeps_small_profitable_review_vote_as_hold() -> None:
    action = get_position_action(
        symbol="AMZN",
        gain_pct=18.5,
        weight_pct=0.1,
        thesis=Mock(),
        invalidation_triggers=[],
        aggregated_review=Mock(final_verdict="review", reasons=["Mixed conviction."]),
    )

    assert action["action"] == "hold"
    assert action["severity"] == "info"


def test_build_position_action_map_does_not_trim_broad_etf_on_wrapper_weight_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = Mock()
    service.storage = Mock()
    service.portfolio_mgr.get_positions.return_value = [
        Position(
            id="pos-vti",
            account_id="acct-1",
            symbol="VTI",
            shares=9.0,
            cost_basis=100.0,
            position_type="long",
        ),
        Position(
            id="pos-tsla",
            account_id="acct-1",
            symbol="TSLA",
            shares=1.0,
            cost_basis=100.0,
            position_type="long",
        ),
    ]
    service.price_fetcher.fetch_price_data.return_value = {
        "VTI": PriceData(symbol="VTI", price=130.0),
        "TSLA": PriceData(symbol="TSLA", price=100.0),
    }
    service.thesis_service.get_thesis.return_value = None
    service.thesis_service.check_invalidation_triggers.return_value = []

    monkeypatch.setattr(
        "app.services._jenny_position_actions.get_fund_lookthroughs",
        lambda _symbols, _storage: {
            "VTI": FundLookthroughProfile(
                symbol="VTI",
                quote_type="ETF",
                family="Vanguard",
                category="Large Blend",
                legal_type="Exchange Traded Fund",
                description="Broad U.S. market ETF",
                top_holdings=[
                    FundHolding(symbol="NVDA", name="NVIDIA", weight=0.0617),
                    FundHolding(symbol="AAPL", name="Apple", weight=0.0589),
                ],
                sector_weightings={"technology": 0.311, "financial_services": 0.124},
                as_of_date="2026-04-16",
            )
        },
    )

    action_map = build_position_action_map(
        service,
        {"VTI": Mock(final_verdict="hold", reasons=[])},
    )

    assert action_map["VTI"]["action"] == "hold"
    assert action_map["VTI"]["weight_pct"] == pytest.approx(92.125984, rel=1e-4)
