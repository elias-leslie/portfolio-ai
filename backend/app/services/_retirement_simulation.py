"""Monte Carlo simulation shared internals (F5).

Private helper to ``RetirementPlanningService`` — mirrors the
``_jenny_*`` convention. Self-contained: no DB, no app config, only
numpy + the long-term return estimates loaded from
``retirement_cma.yaml`` by the caller.

The simulation itself lives in
``retirement_planning_service._run_tax_aware_monte_carlo`` (tax-aware
buckets + the floor-and-upside withdrawal engine). This module keeps
the allocation/covariance sampling helpers and the
``SimulationOutputs`` result shape.

The deterministic seed pathway is the contract: same seed + same
inputs ⇒ same numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

PERCENTILE_KEYS: tuple[tuple[str, float], ...] = (
    ("p10", 10.0),
    ("p25", 25.0),
    ("p50", 50.0),
    ("p75", 75.0),
    ("p90", 90.0),
)
SEQUENCE_OF_RETURNS_HORIZON = 5


@dataclass(slots=True)
class SimulationOutputs:
    success_probability: float
    median_ending_balance: float
    sequence_of_returns_risk: float
    percentiles: dict[str, float]
    failure_year_distribution: dict[str, int]
    ending_balance_paths: dict[str, list[float]]
    # Median real discretionary spending funded per year (floor-and-upside
    # engine); empty before retirement-aware runs populate it.
    median_discretionary_path: list[float] = field(default_factory=list)
    # Beyond-success-% framing (failure depth, warning window, penalty
    # backstop, upside tail) — keys mirror RetirementOutcomeFraming.
    outcome_framing: dict[str, Any] = field(default_factory=dict)


def _normalize_allocation(
    allocation: dict[str, float], cma: dict[str, Any]
) -> tuple[list[str], NDArray[np.float64]]:
    classes_meta = cma["asset_classes"]
    pairs = [(k, float(v)) for k, v in allocation.items() if k in classes_meta and v > 0]
    if not pairs:
        return [], np.array([])
    classes = [k for k, _ in pairs]
    raw = np.array([v for _, v in pairs])
    total = raw.sum()
    if total <= 0:
        return [], np.array([])
    return classes, raw / total


def _covariance_matrix(
    classes: list[str], cma: dict[str, Any]
) -> NDArray[np.float64]:
    n = len(classes)
    sigmas = np.array(
        [float(cma["asset_classes"][c]["volatility"]) for c in classes]
    )
    cov = np.zeros((n, n), dtype=np.float64)
    correlations = cma.get("correlations", {})
    for i, ci in enumerate(classes):
        for j, cj in enumerate(classes):
            if i == j:
                cov[i, j] = sigmas[i] ** 2
                continue
            corr = _lookup_correlation(correlations, ci, cj)
            cov[i, j] = corr * sigmas[i] * sigmas[j]
    return cov


def _lookup_correlation(table: dict[str, Any], a: str, b: str) -> float:
    if a == b:
        return 1.0
    forward = table.get(a, {})
    if isinstance(forward, dict) and b in forward:
        return float(forward[b])
    backward = table.get(b, {})
    if isinstance(backward, dict) and a in backward:
        return float(backward[a])
    # Default to mild positive correlation between unspecified risk
    # assets, zero against cash.
    if a == "cash" or b == "cash":
        return 0.0
    return 0.2
