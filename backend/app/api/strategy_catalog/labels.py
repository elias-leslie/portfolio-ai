"""Plain-language presentation layer for catalog metrics.

Translates raw quantitative fields (Sharpe, p-value, drawdown) into the
HIGH/MED/LOW risk tiers and one-line verdicts the catalog UI surfaces. Kept
separate from the data layer so back-end can refine thresholds without
front-end changes, and front-end can choose to render either layer.
"""

from __future__ import annotations

from typing import Literal

RiskTier = Literal["low", "medium", "high"]


def risk_tier_from_drawdown(max_drawdown_pct: float | None) -> RiskTier:
    """Plain-language risk tier from the max drawdown fraction (0..1)."""
    if max_drawdown_pct is None:
        return "medium"
    if max_drawdown_pct < 0.15:
        return "low"
    if max_drawdown_pct < 0.30:
        return "medium"
    return "high"


def verdict_for_strategy(
    edge_score: float | None,
    pct_folds_beat_bh: float | None,
    statistically_significant: bool,
) -> str:
    """One-line verdict surfaced on each catalog card.

    Honest about uncertainty: only "Beats buy-and-hold" when the data backs it.
    """
    if edge_score is None:
        return "Not enough data"
    if not statistically_significant:
        return "Indistinguishable from random"
    if pct_folds_beat_bh is None:
        return "Insufficient comparison"
    if pct_folds_beat_bh >= 0.7:
        return "Reliably beats buy-and-hold"
    if pct_folds_beat_bh >= 0.5:
        return "Sometimes beats buy-and-hold"
    return "Rarely beats buy-and-hold"


def benchmark_verdict(excess_return_pct: float | None) -> str:
    """Side-by-side comparison verb for the benchmark grid."""
    if excess_return_pct is None:
        return "No comparison"
    if excess_return_pct > 5:
        return "Strongly beats"
    if excess_return_pct > 0:
        return "Beats"
    if excess_return_pct > -5:
        return "Roughly matches"
    if excess_return_pct > -20:
        return "Trails"
    return "Strongly trails"


def beat_count(comparisons: list[dict]) -> tuple[int, int]:
    """How many benchmarks the strategy beats out of how many configured."""
    beats = sum(1 for c in comparisons if c.get("beats_benchmark"))
    return beats, len(comparisons)
