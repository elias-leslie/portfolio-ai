"""Tests for canonical current portfolio fact calculations."""

from __future__ import annotations

import pytest

from app.portfolio.current_facts import calculate_current_position_fact


def test_calculate_current_position_fact_for_long_position() -> None:
    fact = calculate_current_position_fact(
        symbol="vti",
        shares=10,
        cost_basis=200,
        position_type="long",
        current_price=250,
        invested_total_value=10_000,
    )

    assert fact.symbol == "VTI"
    assert fact.current_value == pytest.approx(2_500)
    assert fact.cost_total == pytest.approx(2_000)
    assert fact.gain == pytest.approx(500)
    assert fact.gain_pct == pytest.approx(25)
    assert fact.weight_pct == pytest.approx(25)


def test_calculate_current_position_fact_for_short_position() -> None:
    fact = calculate_current_position_fact(
        symbol="TSLA",
        shares=10,
        cost_basis=300,
        position_type="short",
        current_price=250,
        invested_total_value=10_000,
    )

    assert fact.current_value == pytest.approx(-2_500)
    assert fact.cost_total == pytest.approx(-3_000)
    assert fact.gain == pytest.approx(500)
    assert fact.gain_pct == pytest.approx(16.666667)
    assert fact.weight_pct == pytest.approx(-25)


def test_calculate_current_position_fact_keeps_missing_price_unknown() -> None:
    fact = calculate_current_position_fact(
        symbol="VTI",
        shares=10,
        cost_basis=200,
        position_type="long",
        current_price=None,
        invested_total_value=10_000,
    )

    assert fact.current_value is None
    assert fact.gain is None
    assert fact.gain_pct is None
    assert fact.weight_pct is None
