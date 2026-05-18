"""Unit tests for the L2/L3 blender.

Pure-function module; no DB. Covers the conviction-direction mapping,
weight normalisation, blended score math, re-rank ordering, and Δrank
flagging.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.scanner import blender


def test_pm_score_buy_high_confidence_maxes_out() -> None:
    assert blender.pm_score_from_decision("buy", 1.0) == pytest.approx(10.0)
    assert blender.pm_score_from_decision("add", 0.8) == pytest.approx(8.0)


def test_pm_score_hold_is_half_weighted() -> None:
    assert blender.pm_score_from_decision("hold", 1.0) == pytest.approx(5.0)
    assert blender.pm_score_from_decision("hold", 0.4) == pytest.approx(2.0)


def test_pm_score_sell_or_trim_zeros_committee_contribution() -> None:
    assert blender.pm_score_from_decision("sell", 0.9) == 0.0
    assert blender.pm_score_from_decision("trim", 0.9) == 0.0


def test_pm_score_handles_missing_confidence() -> None:
    assert blender.pm_score_from_decision("buy", None) == 0.0


def test_pm_score_clamps_out_of_range_confidence() -> None:
    assert blender.pm_score_from_decision("buy", 1.5) == pytest.approx(10.0)
    assert blender.pm_score_from_decision("buy", -0.5) == 0.0


def test_blend_weights_normalise_to_sum_one() -> None:
    w = blender.BlendWeights(scanner=6.0, committee=4.0).normalised()
    assert w.scanner == pytest.approx(0.6)
    assert w.committee == pytest.approx(0.4)


def test_blend_weights_zero_falls_back_to_defaults() -> None:
    w = blender.BlendWeights(scanner=0.0, committee=0.0).normalised()
    assert w.scanner == pytest.approx(blender.DEFAULT_W_SCANNER)
    assert w.committee == pytest.approx(blender.DEFAULT_W_COMMITTEE)


def test_env_weights_reads_overrides() -> None:
    env = {
        "SCANNER_BLEND_W_SCANNER": "0.4",
        "SCANNER_BLEND_W_COMMITTEE": "0.6",
    }
    with patch.dict(os.environ, env, clear=False):
        w = blender.env_weights()
    assert w.scanner == pytest.approx(0.4)
    assert w.committee == pytest.approx(0.6)


def test_blend_with_no_committee_falls_back_to_scanner_only_ranking() -> None:
    scanner_rows = [
        {"symbol": "AAA", "rank": 1, "composite_pct": 90.0},
        {"symbol": "BBB", "rank": 2, "composite_pct": 80.0},
        {"symbol": "CCC", "rank": 3, "composite_pct": 70.0},
    ]
    rows = blender.blend(scanner_rows, {}, weights=blender.BlendWeights(0.6, 0.4))
    assert [r.symbol for r in rows] == ["AAA", "BBB", "CCC"]
    # blended = 0.6 * composite (committee contribution zero)
    assert rows[0].blended_score == pytest.approx(54.0)
    assert all(r.delta_rank == 0 and not r.flagged for r in rows)


def test_blend_committee_promotes_high_conviction_to_top() -> None:
    scanner_rows = [
        {"symbol": "AAA", "rank": 1, "composite_pct": 90.0},
        {"symbol": "BBB", "rank": 2, "composite_pct": 80.0},
        {"symbol": "CCC", "rank": 3, "composite_pct": 70.0},
        {"symbol": "DDD", "rank": 4, "composite_pct": 60.0},
    ]
    committee = {
        # DDD scanner-rank 4 but committee says "buy at 1.0" -> pm_score=10
        "DDD": blender.CommitteeSignal(
            run_id="r-ddd",
            action="buy",
            confidence=1.0,
            pm_score=10.0,
        ),
    }
    rows = blender.blend(scanner_rows, committee, weights=blender.BlendWeights(0.6, 0.4))
    by_symbol = {r.symbol: r for r in rows}
    # DDD blended = 0.6*60 + 0.4*10*10 = 36 + 40 = 76
    assert by_symbol["DDD"].blended_score == pytest.approx(76.0)
    # AAA blended = 0.6*90 = 54
    assert by_symbol["AAA"].blended_score == pytest.approx(54.0)
    # DDD lands at top, Δrank = 4 - 1 = 3 → flagged
    assert by_symbol["DDD"].blended_rank == 1
    assert by_symbol["DDD"].delta_rank == 3
    assert by_symbol["DDD"].flagged


def test_blend_sell_does_not_pull_symbol_up() -> None:
    scanner_rows = [
        {"symbol": "AAA", "rank": 1, "composite_pct": 90.0},
        {"symbol": "BBB", "rank": 2, "composite_pct": 80.0},
    ]
    committee = {
        "AAA": blender.CommitteeSignal(
            run_id="r-aaa", action="sell", confidence=1.0, pm_score=0.0
        ),
    }
    rows = blender.blend(scanner_rows, committee, weights=blender.BlendWeights(0.6, 0.4))
    # AAA: 0.6*90 + 0 = 54; BBB: 0.6*80 = 48; AAA stays first.
    assert rows[0].symbol == "AAA"
    assert rows[0].blended_score == pytest.approx(54.0)
    assert rows[0].delta_rank == 0


def test_blend_delta_threshold_flag_is_strict() -> None:
    scanner_rows = [
        {"symbol": "AAA", "rank": 1, "composite_pct": 100.0},
        {"symbol": "BBB", "rank": 2, "composite_pct": 99.0},
        {"symbol": "CCC", "rank": 3, "composite_pct": 98.0},
    ]
    # Tiny committee push to AAA cannot move it (already #1) — no flag.
    committee = {
        "AAA": blender.CommitteeSignal(
            run_id="r-aaa", action="buy", confidence=0.1, pm_score=1.0
        ),
    }
    rows = blender.blend(scanner_rows, committee, weights=blender.BlendWeights(0.6, 0.4))
    assert all(not r.flagged for r in rows)


def test_blend_uses_env_weights_by_default() -> None:
    scanner_rows = [{"symbol": "AAA", "rank": 1, "composite_pct": 50.0}]
    with patch.dict(os.environ, {"SCANNER_BLEND_W_SCANNER": "1", "SCANNER_BLEND_W_COMMITTEE": "0"}, clear=False):
        rows = blender.blend(scanner_rows, {})
    assert rows[0].blended_score == pytest.approx(50.0)
