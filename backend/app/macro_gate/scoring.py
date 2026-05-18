"""Scoring + zone classification for the L1 macro deployment gate.

All scoring is deterministic: identical inputs always produce identical
outputs. Weights and thresholds are constants here, not configured
elsewhere, so the entire macro composite can be replayed exactly off
``signal_macro_snapshots`` history.
"""

from __future__ import annotations

from dataclasses import dataclass

from .signals import factor_crowding, spx_breadth_200d, term_structure

# Weights sum to 1.0; perturbed by ±10% in the Monte Carlo sensitivity test.
WEIGHTS: dict[str, float] = {
    "vix": 0.25,
    "term": 0.20,
    "breadth": 0.20,
    "credit": 0.15,
    "putcall": 0.10,
    "crowding": 0.10,
}

# Zone thresholds (composite score in [0, 100]).
ZONE_FULL_DEPLOY_MIN = 70.0
ZONE_REDUCED_MIN = 40.0

ZONES = ("FULL_DEPLOY", "REDUCED", "DEFENSIVE")


@dataclass(frozen=True, slots=True)
class RawSignals:
    vix_close: float | None
    term_spread_bps: float | None
    breadth_pct: float | None
    hy_spread: float | None
    put_call_ratio: float | None
    factor_crowding_corr: float | None


@dataclass(frozen=True, slots=True)
class ComponentScores:
    vix: float | None
    term: float | None
    breadth: float | None
    credit: float | None
    putcall: float | None
    crowding: float | None


@dataclass(frozen=True, slots=True)
class CompositeResult:
    raw: RawSignals
    scores: ComponentScores
    deployment_score: float
    zone: str
    coverage: float  # share of weighted components that produced a score


def normalize_vix(vix_close: float) -> float:
    """Map VIX level to a 0-100 score (lower VIX => higher score).

    Anchors:
        VIX <= 12  -> 100  (extreme complacency / risk-on regime)
        VIX == 20  -> 50   (historical median)
        VIX >= 40  -> 0    (panic)
    Piecewise linear between anchors.
    """
    if vix_close <= 12:
        return 100.0
    if vix_close >= 40:
        return 0.0
    if vix_close <= 20:
        return 100.0 - (vix_close - 12) * (50.0 / 8.0)
    return 50.0 - (vix_close - 20) * (50.0 / 20.0)


def normalize_credit(hy_spread: float) -> float:
    """Map HY OAS to a 0-100 score (tighter spread => higher score).

    Anchors (OAS in percentage points, i.e. FRED BAMLH0A0HYM2):
        spread <= 2.5  -> 100  (tight credit conditions)
        spread == 5.0  -> 50   (median)
        spread >= 10.0 -> 0    (distressed)
    """
    if hy_spread <= 2.5:
        return 100.0
    if hy_spread >= 10.0:
        return 0.0
    if hy_spread <= 5.0:
        return 100.0 - (hy_spread - 2.5) * (50.0 / 2.5)
    return 50.0 - (hy_spread - 5.0) * (50.0 / 5.0)


def normalize_putcall(put_call_ratio: float) -> float:
    """Map equity put/call ratio to a 0-100 score.

    Put/call > 1 historically signals fear (which precedes rebounds, so we
    treat high P/C as contrarian-bullish), with diminishing returns above
    ~1.4. Very low P/C signals greed.

    Anchors:
        ratio <= 0.6 -> 0    (excessive call buying; greed)
        ratio == 1.0 -> 50
        ratio >= 1.4 -> 100  (capitulation; contrarian buy)
    """
    if put_call_ratio <= 0.6:
        return 0.0
    if put_call_ratio >= 1.4:
        return 100.0
    if put_call_ratio <= 1.0:
        return (put_call_ratio - 0.6) * (50.0 / 0.4)
    return 50.0 + (put_call_ratio - 1.0) * (50.0 / 0.4)


def compute_component_scores(raw: RawSignals) -> ComponentScores:
    return ComponentScores(
        vix=None if raw.vix_close is None else normalize_vix(raw.vix_close),
        term=None
        if raw.term_spread_bps is None
        else term_structure.normalize_to_score(raw.term_spread_bps),
        breadth=None
        if raw.breadth_pct is None
        else spx_breadth_200d.normalize_to_score(raw.breadth_pct),
        credit=None if raw.hy_spread is None else normalize_credit(raw.hy_spread),
        putcall=None
        if raw.put_call_ratio is None
        else normalize_putcall(raw.put_call_ratio),
        crowding=None
        if raw.factor_crowding_corr is None
        else factor_crowding.normalize_to_score(raw.factor_crowding_corr),
    )


def compose(
    scores: ComponentScores,
    weights: dict[str, float] | None = None,
) -> tuple[float, float]:
    """Return ``(deployment_score, coverage_ratio)``.

    Missing components are dropped and the remaining weights are
    renormalised so the composite remains in [0, 100]. Coverage is the
    share of the original weights that produced a real score — useful for
    flagging gates computed from a partial snapshot.
    """
    used_weights = weights or WEIGHTS
    score_lookup: dict[str, float | None] = {
        "vix": scores.vix,
        "term": scores.term,
        "breadth": scores.breadth,
        "credit": scores.credit,
        "putcall": scores.putcall,
        "crowding": scores.crowding,
    }
    weighted_sum = 0.0
    weight_used = 0.0
    for key, weight in used_weights.items():
        value = score_lookup.get(key)
        if value is None:
            continue
        weighted_sum += weight * value
        weight_used += weight
    if weight_used == 0:
        return 0.0, 0.0
    composite = weighted_sum / weight_used
    coverage = weight_used / sum(used_weights.values())
    return composite, coverage


def classify_zone(deployment_score: float) -> str:
    if deployment_score >= ZONE_FULL_DEPLOY_MIN:
        return "FULL_DEPLOY"
    if deployment_score >= ZONE_REDUCED_MIN:
        return "REDUCED"
    return "DEFENSIVE"


def build_composite(raw: RawSignals, weights: dict[str, float] | None = None) -> CompositeResult:
    scores = compute_component_scores(raw)
    deployment_score, coverage = compose(scores, weights=weights)
    return CompositeResult(
        raw=raw,
        scores=scores,
        deployment_score=deployment_score,
        zone=classify_zone(deployment_score),
        coverage=coverage,
    )
