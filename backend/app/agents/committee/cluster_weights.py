"""Dynamic source-cluster weights for committee scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)

SUPPORTED_CLUSTER_KEYS: tuple[str, ...] = (
    "market_regime",
    "sentiment",
    "options_positioning",
    "macro_calendar",
)
PRIOR_WEIGHT = 1.0 / len(SUPPORTED_CLUSTER_KEYS)
FRESHNESS_FACTORS: dict[str, float] = {
    "fresh": 1.0,
    "stale": 0.5,
    "missing": 0.0,
    "unknown": 0.25,
}


@dataclass(frozen=True, slots=True)
class ClusterWeight:
    cluster: str
    prior_weight: float
    effective_weight: float
    sample_size: int
    direction_hit_rate: float | None
    move_mae_pct: float | None
    brier_score: float | None
    skill_score: float | None
    freshness: str
    recommended_action: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "cluster": self.cluster,
            "prior_weight": self.prior_weight,
            "effective_weight": self.effective_weight,
            "sample_size": self.sample_size,
            "direction_hit_rate": self.direction_hit_rate,
            "move_mae_pct": self.move_mae_pct,
            "brier_score": self.brier_score,
            "skill_score": self.skill_score,
            "freshness": self.freshness,
            "recommended_action": self.recommended_action,
        }


def compute_cluster_weights(scorecards: list[dict[str, Any]]) -> dict[str, ClusterWeight]:
    """Compute normalized dynamic weights from persisted cluster scorecards."""
    by_cluster = {
        str(row.get("cluster")): row
        for row in scorecards
        if isinstance(row, dict) and str(row.get("cluster")) in SUPPORTED_CLUSTER_KEYS
    }
    raw_weights: dict[str, float] = {}
    weights: dict[str, ClusterWeight] = {}
    for cluster in SUPPORTED_CLUSTER_KEYS:
        row = by_cluster.get(cluster, {})
        freshness = str(row.get("freshness") or "unknown").lower()
        freshness_factor = FRESHNESS_FACTORS.get(freshness, FRESHNESS_FACTORS["unknown"])
        sample_size = max(0, _int(row.get("sample_size"), default=0))
        brier_score = _optional_float(row.get("brier_score"))
        direction_hit_rate = _optional_float(row.get("direction_hit_rate"))
        move_mae_pct = _optional_float(row.get("move_mae_pct"))
        skill_score = _skill_score(brier_score, direction_hit_rate, move_mae_pct)
        learned_multiplier = _learned_multiplier(sample_size, skill_score)
        raw_weights[cluster] = PRIOR_WEIGHT * freshness_factor * learned_multiplier
        weights[cluster] = ClusterWeight(
            cluster=cluster,
            prior_weight=PRIOR_WEIGHT,
            effective_weight=0.0,
            sample_size=sample_size,
            direction_hit_rate=direction_hit_rate,
            move_mae_pct=move_mae_pct,
            brier_score=brier_score,
            skill_score=skill_score,
            freshness=freshness if freshness in FRESHNESS_FACTORS else "unknown",
            recommended_action="hold",
        )
    total = sum(value for value in raw_weights.values() if value > 0.0)
    if total <= 0.0:
        normalized = dict.fromkeys(SUPPORTED_CLUSTER_KEYS, PRIOR_WEIGHT)
    else:
        normalized = {cluster: max(0.0, raw_weights[cluster]) / total for cluster in SUPPORTED_CLUSTER_KEYS}
    return {
        cluster: ClusterWeight(
            cluster=w.cluster,
            prior_weight=w.prior_weight,
            effective_weight=normalized[cluster],
            sample_size=w.sample_size,
            direction_hit_rate=w.direction_hit_rate,
            move_mae_pct=w.move_mae_pct,
            brier_score=w.brier_score,
            skill_score=w.skill_score,
            freshness=w.freshness,
            recommended_action=_recommended_action(normalized[cluster]),
        )
        for cluster, w in weights.items()
    }


def latest_cluster_weight_payload(*, window_days: int = 3) -> dict[str, Any]:
    """Read latest persisted cluster review and return compact payload for agent context."""
    try:
        cm = get_connection_manager()
        with cm.connection() as conn:
            row = conn.execute(
                """
                SELECT id, generated_at, review_state, cluster_scorecards
                FROM market_prediction_cluster_reviews
                WHERE window_days = %s
                ORDER BY as_of_ts DESC,
                  CASE review_state WHEN 'live' THEN 0 WHEN 'warmup' THEN 1 ELSE 2 END,
                  generated_at DESC
                LIMIT 1
                """,
                (window_days,),
            ).fetchone()
    except Exception as exc:
        logger.warning("committee_cluster_weights_unavailable", error=str(exc))
        return _fallback_payload(review_state="degraded")
    if row is None:
        return _fallback_payload(review_state="warmup")
    scorecards = row[3] if isinstance(row[3], list) else []
    weights = compute_cluster_weights(scorecards)
    generated_at = row[1]
    generated_at_value = generated_at.isoformat() if isinstance(generated_at, datetime) else generated_at
    return {
        "version": "cluster-v1",
        "review_id": str(row[0]),
        "review_state": str(row[2]),
        "generated_at": generated_at_value,
        "weights": {k: v.to_payload() for k, v in weights.items()},
    }


def _fallback_payload(*, review_state: str) -> dict[str, Any]:
    weights = compute_cluster_weights([
        {"cluster": cluster, "freshness": "fresh", "sample_size": 0}
        for cluster in SUPPORTED_CLUSTER_KEYS
    ])
    return {
        "version": "cluster-v1",
        "review_id": None,
        "review_state": review_state,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "weights": {k: v.to_payload() for k, v in weights.items()},
    }


def _skill_score(
    brier_score: float | None,
    direction_hit_rate: float | None,
    move_mae_pct: float | None,
) -> float:
    brier = _clamp(brier_score if brier_score is not None else 0.5, 0.0, 1.0)
    hit_rate = _clamp(direction_hit_rate if direction_hit_rate is not None else 0.5, 0.0, 1.0)
    mae = max(0.0, move_mae_pct if move_mae_pct is not None else 1.0)
    return 0.5 * (1.0 - brier) + 0.3 * hit_rate + 0.2 * (1.0 / (1.0 + mae))


def _learned_multiplier(sample_size: int, skill_score: float) -> float:
    if sample_size < 6:
        return 1.0
    shrink = min(1.0, sample_size / 24.0)
    return _clamp(0.5 + shrink * skill_score, 0.5, 1.5)


def _recommended_action(effective_weight: float) -> str:
    if effective_weight - PRIOR_WEIGHT >= 0.05:
        return "upweight"
    if PRIOR_WEIGHT - effective_weight >= 0.05:
        return "downweight"
    return "hold"


def _optional_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
