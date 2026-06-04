from __future__ import annotations

from app.macro_gate.scoring import (
    RawSignals,
    build_composite,
    compose,
    compute_component_scores,
)

_RAW = RawSignals(
    vix_close=16.0,
    term_spread_bps=40.0,
    breadth_pct=55.0,
    hy_spread=2.7,
    put_call_ratio=1.3,
    factor_crowding_corr=-0.5,
)


def test_compose_excluding_stale_component_drops_coverage() -> None:
    scores = compute_component_scores(_RAW)
    full_score, full_coverage = compose(scores)
    degraded_score, degraded_coverage = compose(scores, excluded=frozenset({"vix"}))

    assert full_coverage == 1.0
    # vix carries weight 0.25, so excluding it leaves 0.75 of the weight trusted.
    assert degraded_coverage == 0.75
    assert degraded_score != full_score


def test_build_composite_flags_degraded_with_stale_keys() -> None:
    result = build_composite(_RAW, stale_keys=frozenset({"vix"}))

    assert result.metadata["degraded"] is True
    assert result.metadata["stale_components"] == ["vix"]
    assert result.coverage == 0.75


def test_build_composite_is_not_degraded_by_default() -> None:
    result = build_composite(_RAW)

    assert result.metadata["degraded"] is False
    assert result.metadata["stale_components"] == []
    assert result.coverage == 1.0
