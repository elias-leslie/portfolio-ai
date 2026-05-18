"""Monte Carlo weight-sensitivity for the L1 macro gate.

Perturb the six gate weights by ±10% (uniform), renormalise to sum=1, and
recompose the composite from the per-day component scores captured by the
walk-forward replay. Report:

- distribution of zone labels under perturbation,
- share of (sample, day) pairs whose zone label flipped vs the baseline,
- average per-day standard deviation of the composite score.

A robust gate should keep the zone-change rate well below 10% with a
±10% perturbation. Default: 1000 samples.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..scoring import WEIGHTS, classify_zone, compose
from .walk_forward import replay


@dataclass(frozen=True, slots=True)
class SensitivityResult:
    samples: int
    perturbation: float
    baseline_zones: dict[str, int]
    zone_change_rate: float
    score_std_avg: float
    perturbed_zone_counts: dict[str, int]


def _perturb_weights(rng: random.Random, perturbation: float) -> dict[str, float]:
    perturbed = {
        name: weight * (1 + rng.uniform(-perturbation, perturbation))
        for name, weight in WEIGHTS.items()
    }
    total = sum(perturbed.values())
    return {name: weight / total for name, weight in perturbed.items()}


def run_sensitivity(
    start: date,
    end: date,
    samples: int = 1000,
    perturbation: float = 0.10,
    seed: int = 7,
) -> SensitivityResult:
    rng = random.Random(seed)
    baseline = replay(start, end)
    baseline_zone_lookup = {row.snapshot_date: row.zone for row in baseline}
    baseline_zones: dict[str, int] = {}
    for row in baseline:
        baseline_zones[row.zone] = baseline_zones.get(row.zone, 0) + 1

    zone_change_counts = 0
    total_observations = 0
    perturbed_zone_counts: dict[str, int] = {}
    per_day_scores: dict[date, list[float]] = {row.snapshot_date: [] for row in baseline}

    for _ in range(samples):
        weights = _perturb_weights(rng, perturbation)
        for row in baseline:
            score, _coverage = compose(row.scores, weights=weights)
            zone = classify_zone(score)
            perturbed_zone_counts[zone] = perturbed_zone_counts.get(zone, 0) + 1
            per_day_scores[row.snapshot_date].append(score)
            if zone != baseline_zone_lookup[row.snapshot_date]:
                zone_change_counts += 1
            total_observations += 1

    zone_change_rate = zone_change_counts / total_observations if total_observations else 0.0
    score_std_avg = _avg_std(per_day_scores)

    return SensitivityResult(
        samples=samples,
        perturbation=perturbation,
        baseline_zones=baseline_zones,
        zone_change_rate=zone_change_rate,
        score_std_avg=score_std_avg,
        perturbed_zone_counts=perturbed_zone_counts,
    )


def _avg_std(per_day_scores: dict[date, list[float]]) -> float:
    stds: list[float] = []
    for scores in per_day_scores.values():
        if len(scores) < 2:
            continue
        mean = sum(scores) / len(scores)
        var = sum((value - mean) ** 2 for value in scores) / len(scores)
        stds.append(var**0.5)
    return sum(stds) / len(stds) if stds else 0.0


def as_dict(result: SensitivityResult) -> dict[str, Any]:
    return {
        "samples": result.samples,
        "perturbation": result.perturbation,
        "baseline_zone_counts": result.baseline_zones,
        "perturbed_zone_counts": result.perturbed_zone_counts,
        "zone_change_rate": result.zone_change_rate,
        "score_std_avg": result.score_std_avg,
    }


__all__ = ["SensitivityResult", "as_dict", "run_sensitivity"]
