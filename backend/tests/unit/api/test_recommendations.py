"""Unit tests for recommendation parsing and risk-level gating."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.api.recommendations._row_parser import parse_row


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
            current_prices={"AAPL": 102.0},
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
            current_prices={"AAPL": 101.0},
            portfolio_size=100_000.0,
            position_pct=0.05,
            validation_filter=None,
            storage=mock_storage,
        )

    assert recommendation is not None
    assert recommendation.stop_loss == 94.5
    assert recommendation.target_price == 130.0
