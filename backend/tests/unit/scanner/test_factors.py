"""Tests for the pure scanner factor functions."""

from __future__ import annotations

import math

import pytest

from app.scanner import factors

# ---------------------------------------------------------------------------
# mom_xover
# ---------------------------------------------------------------------------


def test_mom_xover_none_when_too_short() -> None:
    assert factors.mom_xover([100.0] * 49) is None


def test_mom_xover_zero_for_flat_series() -> None:
    flat = [100.0] * 60
    result = factors.mom_xover(flat)
    assert result == pytest.approx(0.0)


def test_mom_xover_positive_for_uptrend() -> None:
    # Linear uptrend → EMA10 leads EMA50 → positive ratio
    series = [100.0 + i for i in range(60)]
    result = factors.mom_xover(series)
    assert result is not None and result > 0


def test_mom_xover_negative_for_downtrend() -> None:
    series = [200.0 - i for i in range(60)]
    result = factors.mom_xover(series)
    assert result is not None and result < 0


# ---------------------------------------------------------------------------
# vol_surge
# ---------------------------------------------------------------------------


def test_vol_surge_none_when_too_short() -> None:
    assert factors.vol_surge([1_000_000] * 19) is None


def test_vol_surge_one_when_flat() -> None:
    result = factors.vol_surge([1_000_000.0] * 20)
    assert result == pytest.approx(1.0)


def test_vol_surge_doubling() -> None:
    # 15 days at 1M, then 5 days at 3M → mean5=3M, mean20=(15*1M+5*3M)/20=1.5M
    # ratio = 3M / 1.5M = 2.0
    series = [1_000_000.0] * 15 + [3_000_000.0] * 5
    result = factors.vol_surge(series)
    assert result == pytest.approx(2.0)


def test_vol_surge_zero_mean_returns_none() -> None:
    assert factors.vol_surge([0.0] * 20) is None


# ---------------------------------------------------------------------------
# rs_vs_spy
# ---------------------------------------------------------------------------


def test_rs_vs_spy_none_when_too_short() -> None:
    assert factors.rs_vs_spy([100.0] * 20, [100.0] * 21) is None
    assert factors.rs_vs_spy([100.0] * 21, [100.0] * 20) is None


def test_rs_vs_spy_zero_when_identical() -> None:
    sym = [100.0 + i for i in range(25)]
    spy = list(sym)
    result = factors.rs_vs_spy(sym, spy)
    assert result == pytest.approx(0.0)


def test_rs_vs_spy_outperformance() -> None:
    # Only first and last bars matter: 20-bar return is last/first[-21]-1.
    sym = [100.0] * 20 + [120.0]   # 20% return
    spy = [100.0] * 20 + [110.0]   # 10% return
    result = factors.rs_vs_spy(sym, spy)
    assert result == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# high_52w_proximity
# ---------------------------------------------------------------------------


def test_high_52w_proximity_at_peak() -> None:
    series = [100.0, 110.0, 120.0]
    assert factors.high_52w_proximity(series) == pytest.approx(1.0)


def test_high_52w_proximity_below_peak() -> None:
    series = [100.0, 110.0, 120.0, 90.0]
    assert factors.high_52w_proximity(series) == pytest.approx(0.75)


def test_high_52w_proximity_empty() -> None:
    assert factors.high_52w_proximity([]) is None


def test_high_52w_proximity_clipped_to_252_window() -> None:
    # Old extreme high outside the 252 window should NOT count
    series = [1_000.0] + [50.0] * 252
    assert factors.high_52w_proximity(series) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# short_interest_decline
# ---------------------------------------------------------------------------


def test_short_interest_decline_none_when_missing() -> None:
    assert factors.short_interest_decline(None, 0.05) is None
    assert factors.short_interest_decline(0.05, None) is None


def test_short_interest_decline_positive_when_improving() -> None:
    # Was 10% of float, now 5%; (10-5)/10 = 0.5
    assert factors.short_interest_decline(0.05, 0.10) == pytest.approx(0.5)


def test_short_interest_decline_negative_when_worsening() -> None:
    assert factors.short_interest_decline(0.15, 0.10) == pytest.approx(-0.5)


def test_short_interest_decline_zero_prior_returns_none() -> None:
    assert factors.short_interest_decline(0.05, 0.0) is None


def test_factor_names_match_module_surface() -> None:
    expected = {
        "mom_xover",
        "vol_surge",
        "rs_vs_spy",
        "high_52w_proximity",
        "short_interest_decline",
    }
    assert set(factors.FACTOR_NAMES) == expected
    assert len(factors.FACTOR_NAMES) == 5  # stable ordering matters
    for name in factors.FACTOR_NAMES:
        assert hasattr(factors, name), f"{name} missing as module attribute"


def test_ema_seed_handles_single_value() -> None:
    # Internal helper: short series uses recursive smoothing seeded with first.
    assert factors._ema([10.0], 1) == pytest.approx(10.0)


def test_ema_returns_finite_for_realistic_input() -> None:
    series = [100.0 + math.sin(i / 5) * 5 for i in range(60)]
    assert factors._ema(series, 10) is not None
    assert math.isfinite(factors._ema(series, 50) or float("nan"))
