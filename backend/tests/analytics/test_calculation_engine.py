"""Tests for the shared user-facing calculation engine."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.analytics.calculation_engine import (
    build_trade_setup,
    calculate_expected_return_target,
    calculate_position_size_from_risk,
    calculate_risk_reward_ratio,
)


def test_calculate_expected_return_target_returns_none_for_missing_or_invalid_inputs() -> None:
    """Targets should be unavailable when there is no positive expected return."""
    assert calculate_expected_return_target(100.0, None) is None
    assert calculate_expected_return_target(100.0, 0.0) is None
    assert calculate_expected_return_target(100.0, -5.0) is None


def test_calculate_expected_return_target_builds_price_from_positive_return() -> None:
    """Targets should reflect the stated expected return percentage."""
    assert calculate_expected_return_target(100.0, 25.0) == 125.0


def test_calculate_position_size_from_risk_returns_none_for_invalid_setup() -> None:
    """Position size should be unavailable when the stop is not below entry."""
    assert calculate_position_size_from_risk(100.0, 100.0, 500.0) is None
    assert calculate_position_size_from_risk(100.0, 105.0, 500.0) is None


def test_calculate_position_size_from_risk_uses_risk_budget_formula() -> None:
    """Position size should use floor(risk_budget / risk_per_share)."""
    assert calculate_position_size_from_risk(100.0, 95.0, 500.0) == 100


def test_calculate_risk_reward_ratio_returns_none_when_setup_is_invalid() -> None:
    """Risk/reward should be unavailable when the setup has no positive risk and reward."""
    assert calculate_risk_reward_ratio(100.0, 100.0, 120.0) is None
    assert calculate_risk_reward_ratio(100.0, 95.0, 100.0) is None


def test_build_trade_setup_returns_none_without_atr_stop() -> None:
    """Trade setup should be hidden when ATR data is unavailable."""
    mock_storage = MagicMock()

    with patch(
        "app.analytics.calculation_engine.calculate_atr_stop_loss",
        return_value=None,
    ):
        trade_setup = build_trade_setup(
            storage=mock_storage,
            symbol="AAPL",
            entry_price=100.0,
            expected_return_pct=20.0,
            risk_budget=1_500.0,
            portfolio_value=100_000.0,
        )

    assert trade_setup is None


def test_build_trade_setup_caps_risk_size_by_position_limit() -> None:
    """Trade setup should respect both the risk budget and the position-size cap."""
    mock_storage = MagicMock()
    mock_rules = SimpleNamespace(
        paper_trading=SimpleNamespace(default_position_pct=0.05),
        position_sizing=SimpleNamespace(min_position_value=100.0),
    )

    with (
        patch(
            "app.analytics.calculation_engine.calculate_atr_stop_loss",
            return_value=94.0,
        ),
        patch("app.analytics.calculation_engine.get_rules", return_value=mock_rules),
    ):
        trade_setup = build_trade_setup(
            storage=mock_storage,
            symbol="AAPL",
            entry_price=100.0,
            expected_return_pct=25.0,
            risk_budget=1_500.0,
            portfolio_value=100_000.0,
            position_cap_pct=0.05,
        )

    assert trade_setup is not None
    assert trade_setup.stop_loss == 94.0
    assert trade_setup.target_price == 125.0
    assert trade_setup.risk_per_share == 6.0
    assert trade_setup.reward_per_share == 25.0
    assert trade_setup.risk_reward_ratio == 4.17
    assert trade_setup.sample_share_count == 50
    assert trade_setup.sample_dollar_size == 5_000.0
