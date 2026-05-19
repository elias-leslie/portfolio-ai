from __future__ import annotations

import pytest

from app.agents.committee.signal_sleeve import apply_signal_sleeve, build_signal_sleeve


def test_signal_sleeve_adds_bullish_multifactor_adjustment() -> None:
    sleeve = build_signal_sleeve(
        scanner_factors={"mom_xover_pct": 90, "rs_vs_spy_pct": 80, "vol_surge_pct": 75},
        context_bundle={
            "source_snapshot": {
                "clusters": {
                    "mag7_sector_leadership": {"average_change_pct": 1.0},
                    "overnight_premarket_afterhours_futures_news": {"spy_gap_proxy_pct": 0.5},
                    "holiday_turn_of_month": {"gate_state": "active"},
                }
            }
        },
    )

    assert sleeve.score_adjustment > 0
    assert sleeve.top_factor == "mom_xover"
    assert apply_signal_sleeve(0.8, sleeve) <= 1.0


def test_signal_sleeve_oil_shock_filters_score_lower() -> None:
    sleeve = build_signal_sleeve(
        scanner_factors={"mom_xover_pct": 50, "rs_vs_spy_pct": 50, "vol_surge_pct": 50},
        context_bundle={
            "source_snapshot": {
                "clusters": {
                    "oil_shock_overlay": {"gate_state": "active", "daily_change_pct": 4.0}
                }
            }
        },
    )

    assert sleeve.score_adjustment < 0
    assert sleeve.factors["oil"] < 0
    assert apply_signal_sleeve(0.2, sleeve) == pytest.approx(0.1995)
