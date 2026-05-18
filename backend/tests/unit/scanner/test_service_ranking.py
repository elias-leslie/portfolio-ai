"""Tests for the universe-relative percentile + composite logic.

The DB-touching parts of ``app.scanner.service`` are exercised in
integration; here we cover the pure ranking helpers that decide what
gets persisted.
"""

from __future__ import annotations

import pytest

from app.scanner import factors, service


def test_percentile_ranks_assign_avg_for_ties() -> None:
    raw = {
        "A": dict.fromkeys(factors.FACTOR_NAMES),
        "B": dict.fromkeys(factors.FACTOR_NAMES),
        "C": dict.fromkeys(factors.FACTOR_NAMES),
    }
    # mom_xover: A=0.10, B=0.10, C=0.20 -> A,B tie at avg rank, C at top
    raw["A"]["mom_xover"] = 0.10
    raw["B"]["mom_xover"] = 0.10
    raw["C"]["mom_xover"] = 0.20

    percentiles = service._percentile_ranks(raw)

    # n=3, sorted asc: [(A,0.10),(B,0.10),(C,0.20)]
    # A,B tie at avg position (0+1)/2 = 0.5 -> 0.5/2*100 = 25.0
    # C at position 2 -> 2/2*100 = 100.0
    assert percentiles["A"]["mom_xover"] == pytest.approx(25.0)
    assert percentiles["B"]["mom_xover"] == pytest.approx(25.0)
    assert percentiles["C"]["mom_xover"] == pytest.approx(100.0)
    # Unfilled factors stay None
    assert percentiles["A"]["vol_surge"] is None


def test_percentile_ranks_single_value_gets_top() -> None:
    raw = {
        "A": dict.fromkeys(factors.FACTOR_NAMES),
        "B": dict.fromkeys(factors.FACTOR_NAMES),
    }
    raw["A"]["mom_xover"] = 0.5
    # B has no mom_xover observation
    percentiles = service._percentile_ranks(raw)
    assert percentiles["A"]["mom_xover"] == pytest.approx(100.0)
    assert percentiles["B"]["mom_xover"] is None


def test_percentile_ranks_all_none_for_factor_stays_none() -> None:
    raw = {sym: dict.fromkeys(factors.FACTOR_NAMES) for sym in ("A", "B")}
    percentiles = service._percentile_ranks(raw)
    for sym in ("A", "B"):
        for name in factors.FACTOR_NAMES:
            assert percentiles[sym][name] is None


def test_composite_drops_missing_factors_and_reports_coverage() -> None:
    percentiles = {
        "A": dict.fromkeys(factors.FACTOR_NAMES),
        "B": dict.fromkeys(factors.FACTOR_NAMES),
    }
    # A has all 5 factors set to 80; B only has 1 factor set to 100.
    for name in factors.FACTOR_NAMES:
        percentiles["A"][name] = 80.0
    percentiles["B"]["mom_xover"] = 100.0

    composites = service._composites(percentiles)

    assert composites["A"][0] == pytest.approx(80.0)
    assert composites["A"][1] == pytest.approx(1.0)
    assert composites["B"][0] == pytest.approx(100.0)
    assert composites["B"][1] == pytest.approx(0.2)


def test_composite_drops_symbols_with_zero_coverage() -> None:
    percentiles = {
        "A": dict.fromkeys(factors.FACTOR_NAMES, 50.0),
        "GHOST": dict.fromkeys(factors.FACTOR_NAMES),
    }
    composites = service._composites(percentiles)
    assert "GHOST" not in composites
    assert composites["A"][0] == pytest.approx(50.0)


def test_rank_orders_desc_by_composite() -> None:
    composites = {"A": (50.0, 1.0), "B": (90.0, 1.0), "C": (70.0, 1.0)}
    ranked = service._rank(composites)
    assert [sym for sym, _ in ranked] == ["B", "C", "A"]


def test_build_score_rows_sets_sequential_ranks() -> None:
    raw_per_symbol = {
        "A": dict.fromkeys(factors.FACTOR_NAMES, 0.1),
        "B": dict.fromkeys(factors.FACTOR_NAMES, 0.2),
    }
    percentiles = {
        "A": dict.fromkeys(factors.FACTOR_NAMES, 25.0),
        "B": dict.fromkeys(factors.FACTOR_NAMES, 100.0),
    }
    composites = {"A": (25.0, 1.0), "B": (100.0, 1.0)}
    ranked = service._rank(composites)
    rows = list(service._build_score_rows(ranked, raw_per_symbol, percentiles, composites))
    assert [r.symbol for r in rows] == ["B", "A"]
    assert [r.rank for r in rows] == [1, 2]
    assert rows[0].composite_pct == pytest.approx(100.0)
    assert rows[0].factor_coverage == pytest.approx(1.0)
