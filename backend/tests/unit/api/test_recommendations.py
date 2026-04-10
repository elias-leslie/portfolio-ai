"""Unit tests for recommendation parsing and risk-level gating."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.api.recommendations._row_parser import parse_row
from app.api.recommendations.router import get_recommendations
from app.api.symbols.recommendations import generate_held_recommendation
from app.portfolio.models import PriceData
from app.portfolio.totals import PortfolioTotals


def _build_row(
    *,
    symbol: str = "AAPL",
    strategy_id: str = "strategy-1",
    strategy_name: str = "Momentum",
    strategy_type: str = "swing",
    signal_type: str = "BUY",
    signal_strength: int = 8,
    reasons: list[str] | None = None,
    market_data: dict[str, object] | None = None,
    signal_date: str = "2026-03-06",
    created_at: str = "2026-03-06T15:30:00Z",
    expected_sharpe: float | None = 1.4,
    thesis_status: str | None = "active",
    cross_validation_score: float | None = 0.82,
    expected_return_pct: float | None = 25.0,
) -> list[object]:
    """Build a recommendation query row matching the parser contract."""
    return [
        symbol,
        strategy_id,
        strategy_name,
        strategy_type,
        signal_type,
        signal_strength,
        reasons or ["trend", "breakout"],
        market_data or {"price": 100.0},
        signal_date,
        created_at,
        expected_sharpe,
        thesis_status,
        cross_validation_score,
        expected_return_pct,
    ]


def test_parse_row_skips_recommendation_without_atr_stop_loss() -> None:
    """Recommendations should be hidden when ATR-backed stop loss is unavailable."""
    row = _build_row()
    mock_storage = MagicMock()

    with patch("app.api.recommendations._row_parser.build_trade_setup", return_value=None):
        recommendation = parse_row(
            row,
            current_prices={
                "AAPL": PriceData(symbol="AAPL", price=102.0, cached_at=datetime.now(UTC)),
            },
            portfolio_size=100_000.0,
            position_pct=0.05,
            validation_filter=None,
            storage=mock_storage,
        )

    assert recommendation is None


def test_parse_row_uses_real_stop_and_thesis_target_instead_of_fixed_percentages() -> None:
    """Recommendations should use ATR stops and thesis-driven targets, not fixed 8/15 heuristics."""
    row = _build_row(expected_return_pct=30.0)
    mock_storage = MagicMock()

    with patch(
        "app.api.recommendations._row_parser.build_trade_setup",
        return_value=MagicMock(
            stop_loss=94.5,
            target_price=130.0,
            sample_dollar_size=5_000.0,
            sample_share_count=49,
            risk_reward_ratio=4.62,
        ),
    ):
        recommendation = parse_row(
            row,
            current_prices={
                "AAPL": PriceData(symbol="AAPL", price=101.0, cached_at=datetime.now(UTC)),
            },
            portfolio_size=100_000.0,
            position_pct=0.05,
            validation_filter=None,
            storage=mock_storage,
        )

    assert recommendation is not None
    assert recommendation.stop_loss == 94.5
    assert recommendation.target_price == 130.0


def test_parse_row_skips_recommendation_when_current_price_is_missing() -> None:
    """Recommendations should be hidden when no live price snapshot is available."""
    row = _build_row()
    mock_storage = MagicMock()

    recommendation = parse_row(
        row,
        current_prices={},
        portfolio_size=100_000.0,
        position_pct=0.05,
        validation_filter=None,
        storage=mock_storage,
    )

    assert recommendation is None


def test_generate_held_recommendation_does_not_fabricate_gain_without_live_price() -> None:
    action, reasoning = generate_held_recommendation(
        {
            "symbol": "VTI",
            "shares": 10,
            "cost_basis": 200,
            "position_type": "long",
            "current_price": None,
        },
        signal="HOLD",
        strength=5,
        fear_greed=50,
    )

    assert action == "HOLD_POSITION"
    assert "Live gain/loss unavailable because current price is missing" in reasoning
    assert all("0.0%" not in reason for reason in reasoning)


def test_parse_row_skips_recommendation_when_current_price_is_stale() -> None:
    """Recommendations should be hidden when the current price snapshot is stale."""
    row = _build_row()
    mock_storage = MagicMock()
    stale_snapshot = PriceData(
        symbol="AAPL",
        price=101.0,
        cached_at=datetime.now(UTC) - timedelta(minutes=30),
    )

    recommendation = parse_row(
        row,
        current_prices={"AAPL": stale_snapshot},
        portfolio_size=100_000.0,
        position_pct=0.05,
        validation_filter=None,
        storage=mock_storage,
    )

    assert recommendation is None


@pytest.mark.asyncio
async def test_get_recommendations_uses_live_portfolio_total_when_no_override() -> None:
    """Route should default sizing to the live cash-inclusive portfolio total."""
    with (
        patch(
            "app.api.recommendations.router.get_live_portfolio_totals",
            return_value=PortfolioTotals(cash_balance_total=2_500.0, invested_total_value=18_000.0),
        ),
        patch("app.api.recommendations.router.fetch_recommendations", return_value=[]),
    ):
        response = await get_recommendations(portfolio_size=None, position_pct=0.05)

    assert response.summary["portfolio_size"] == 20_500.0
    assert response.summary["position_pct"] == 0.05


@pytest.mark.asyncio
async def test_get_recommendations_respects_explicit_portfolio_override() -> None:
    """Explicit sizing override should win over the live portfolio total."""
    with (
        patch(
            "app.api.recommendations.router.get_live_portfolio_totals",
            return_value=PortfolioTotals(cash_balance_total=2_500.0, invested_total_value=18_000.0),
        ),
        patch("app.api.recommendations.router.fetch_recommendations", return_value=[]),
    ):
        response = await get_recommendations(portfolio_size=50_000.0, position_pct=0.05)

    assert response.summary["portfolio_size"] == 50_000.0
