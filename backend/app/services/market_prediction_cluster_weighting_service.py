"""Adaptive cluster-weighting review service for market prediction committees."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from typing import Any

from app.logging_config import get_logger
from app.models.market_prediction import (
    SUPPORTED_ADAPTIVE_CLUSTER_KEYS,
    MarketPredictionClusterEvaluationSample,
    MarketPredictionClusterReview,
    MarketPredictionClusterScorecardRow,
    normalize_market_prediction_cluster_key,
)
from app.repositories.market_prediction_repository import MarketPredictionRepository
from app.storage import PortfolioStorage, get_storage
from app.utils.market_hours import NY_TZ, get_expected_data_date, get_next_trading_day

logger = get_logger(__name__)

_TRAILING_WINDOW_TRADING_DAYS = 60
_WEIGHTING_HALF_LIFE_DAYS = 20
_WEIGHT_EPSILON = 1e-9
_FRESHNESS_FACTORS = {
    "fresh": 1.0,
    "stale": 0.5,
    "missing": 0.0,
    "unknown": 0.25,
}


class MarketPredictionClusterWeightingService:
    def __init__(
        self,
        *,
        repository: MarketPredictionRepository | Any | None = None,
        storage: PortfolioStorage | None = None,
    ) -> None:
        self.storage = storage or get_storage()
        self.repository = repository or MarketPredictionRepository(self.storage)

    def get_review(
        self,
        *,
        window_days: int,
        as_of_ts: datetime | None = None,
        source_snapshot: dict[str, Any] | None = None,
    ) -> MarketPredictionClusterReview:
        self._validate_window_days(window_days)
        effective_ts = self._coerce_datetime(as_of_ts or datetime.now(UTC))
        for raw_row in self.repository.list_latest_cluster_reviews(window_days=window_days, limit=5):
            normalized = self._normalize_persisted_review(raw_row)
            if normalized is not None:
                return normalized
        return self._build_prior_review(
            window_days=window_days,
            as_of_ts=effective_ts,
            review_state="warmup",
            source_snapshot=source_snapshot or {},
        )

    def resolve_and_persist_review(
        self,
        *,
        window_days: int,
        as_of_ts: datetime,
        source_snapshot: dict[str, Any],
    ) -> MarketPredictionClusterReview:
        self._validate_window_days(window_days)
        effective_ts = self._coerce_datetime(as_of_ts)
        try:
            review = self._resolve_review(
                window_days=window_days,
                as_of_ts=effective_ts,
                source_snapshot=source_snapshot,
            )
        except Exception:
            logger.warning("market_prediction_cluster_review_resolution_failed", window_days=window_days, exc_info=True)
            review = self._build_prior_review(
                window_days=window_days,
                as_of_ts=effective_ts,
                review_state="degraded",
                source_snapshot=source_snapshot,
            )
        try:
            persisted = self.repository.upsert_cluster_review(review)
            return self._normalize_persisted_review(persisted) or review
        except Exception:
            logger.warning("market_prediction_cluster_review_persist_failed", window_days=window_days, exc_info=True)
            degraded = self._build_prior_review(
                window_days=window_days,
                as_of_ts=effective_ts,
                review_state="degraded",
                source_snapshot=source_snapshot,
            )
            degraded.metadata["_persisted"] = False
            return degraded

    def _resolve_review(
        self,
        *,
        window_days: int,
        as_of_ts: datetime,
        source_snapshot: dict[str, Any],
    ) -> MarketPredictionClusterReview:
        effective_market_date = get_expected_data_date(as_of_ts.astimezone(NY_TZ))
        grouped: dict[str, list[tuple[MarketPredictionClusterEvaluationSample, float]]] = {
            cluster: [] for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS
        }
        for raw_sample in self.repository.list_cluster_evaluation_samples(
            window_days=window_days,
            effective_market_date=effective_market_date,
        ):
            sample = self._normalize_sample(raw_sample)
            if sample is None:
                continue
            age = self._trading_day_age(
                target_date=sample.target_date,
                effective_market_date=effective_market_date,
            )
            if age is None or age < 0 or age > _TRAILING_WINDOW_TRADING_DAYS:
                continue
            weight = 0.5 ** (age / _WEIGHTING_HALF_LIFE_DAYS)
            for cluster in self._normalize_cluster_keys(sample.active_cluster_keys):
                grouped[cluster].append((sample, weight))

        freshness_map = self._freshness_map(source_snapshot)
        scorecards = [
            self._resolve_scorecard(
                cluster=cluster,
                weighted_rows=grouped[cluster],
                freshness=freshness_map[cluster],
            )
            for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS
        ]
        has_live_signal = any(row.sample_size >= 6 for row in scorecards)
        has_active_freshness = any(_FRESHNESS_FACTORS[row.freshness] > _WEIGHT_EPSILON for row in scorecards)
        review_state = "live" if has_live_signal and has_active_freshness else "warmup"
        if review_state == "live":
            scorecards = self._apply_effective_weights(scorecards)
        else:
            scorecards = self._apply_prior_only_weights(scorecards)
        review = MarketPredictionClusterReview(
            id=self._review_id(window_days=window_days, as_of_ts=as_of_ts),
            generated_at=as_of_ts,
            as_of_ts=as_of_ts,
            window_days=window_days,
            review_state=review_state,
            cluster_scorecards=scorecards,
            review_summary=self._build_review_summary(
                scorecards=scorecards,
                review_state=review_state,
                generated_at=as_of_ts,
            ),
            metadata=self._review_metadata(),
        )
        return review

    def _resolve_scorecard(
        self,
        *,
        cluster: str,
        weighted_rows: list[tuple[MarketPredictionClusterEvaluationSample, float]],
        freshness: str,
    ) -> MarketPredictionClusterScorecardRow:
        prior_weight = 1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS)
        if not weighted_rows:
            return MarketPredictionClusterScorecardRow(
                cluster=cluster,
                prior_weight=prior_weight,
                effective_weight=prior_weight,
                sample_size=0,
                direction_hit_rate=None,
                move_mae_pct=None,
                brier_score=None,
                skill_score=None,
                freshness=freshness,
                recommended_action="hold",
            )
        sample_size = len(weighted_rows)
        weights = [weight for _, weight in weighted_rows]
        direction_hit_rate = self._weighted_mean(
            [1.0 if row.direction_hit else 0.0 for row, _ in weighted_rows],
            weights,
        )
        move_mae_pct = self._weighted_mean([row.move_abs_error_pct for row, _ in weighted_rows], weights)
        brier_score = self._weighted_mean([row.brier_score for row, _ in weighted_rows], weights)
        skill_score = self._skill_score(
            direction_hit_rate=direction_hit_rate,
            move_mae_pct=move_mae_pct,
            brier_score=brier_score,
        )
        return MarketPredictionClusterScorecardRow(
            cluster=cluster,
            prior_weight=prior_weight,
            effective_weight=prior_weight,
            sample_size=sample_size,
            direction_hit_rate=direction_hit_rate,
            move_mae_pct=move_mae_pct,
            brier_score=brier_score,
            skill_score=skill_score,
            freshness=freshness,
            recommended_action="hold",
        )

    def _apply_prior_only_weights(
        self,
        scorecards: list[MarketPredictionClusterScorecardRow],
    ) -> list[MarketPredictionClusterScorecardRow]:
        return [
            row.model_copy(update={"effective_weight": row.prior_weight, "recommended_action": "hold"})
            for row in scorecards
        ]

    def _apply_effective_weights(
        self,
        scorecards: list[MarketPredictionClusterScorecardRow],
    ) -> list[MarketPredictionClusterScorecardRow]:
        raw_weights: dict[str, float] = {}
        indexed = {row.cluster: row for row in scorecards}
        for row in scorecards:
            freshness_factor = _FRESHNESS_FACTORS[row.freshness]
            if row.sample_size < 6 or row.skill_score is None:
                learned_multiplier = 1.0
            else:
                shrink = min(1.0, row.sample_size / 24.0)
                learned_multiplier = self._clamp(0.5 + shrink * row.skill_score, low=0.5, high=1.5)
            raw_weights[row.cluster] = row.prior_weight * freshness_factor * learned_multiplier
        total = sum(weight for weight in raw_weights.values() if weight > _WEIGHT_EPSILON)
        if total <= _WEIGHT_EPSILON:
            return self._apply_prior_only_weights(scorecards)
        updated: list[MarketPredictionClusterScorecardRow] = []
        for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS:
            row = indexed[cluster]
            effective_weight = raw_weights[cluster] / total
            updated.append(
                row.model_copy(
                    update={
                        "effective_weight": effective_weight,
                        "recommended_action": self._recommended_action(
                            prior_weight=row.prior_weight,
                            effective_weight=effective_weight,
                        ),
                    }
                )
            )
        return updated

    def _build_prior_review(
        self,
        *,
        window_days: int,
        as_of_ts: datetime,
        review_state: str,
        source_snapshot: dict[str, Any],
    ) -> MarketPredictionClusterReview:
        scorecards = self._prior_scorecards(source_snapshot)
        return MarketPredictionClusterReview(
            id=self._review_id(window_days=window_days, as_of_ts=as_of_ts),
            generated_at=as_of_ts,
            as_of_ts=as_of_ts,
            window_days=window_days,
            review_state=review_state,
            cluster_scorecards=scorecards,
            review_summary=self._build_review_summary(
                scorecards=scorecards,
                review_state=review_state,
                generated_at=as_of_ts,
            ),
            metadata=self._review_metadata(),
        )

    def _prior_scorecards(self, source_snapshot: dict[str, Any]) -> list[MarketPredictionClusterScorecardRow]:
        prior = 1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS)
        freshness_map = self._freshness_map(source_snapshot)
        return [
            MarketPredictionClusterScorecardRow(
                cluster=cluster,
                prior_weight=prior,
                effective_weight=prior,
                sample_size=0,
                direction_hit_rate=None,
                move_mae_pct=None,
                brier_score=None,
                skill_score=None,
                freshness=freshness_map[cluster],
                recommended_action="hold",
            )
            for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS
        ]

    def _freshness_map(self, source_snapshot: dict[str, Any]) -> dict[str, str]:
        clusters = source_snapshot.get("clusters") if isinstance(source_snapshot, dict) else {}
        clusters = clusters if isinstance(clusters, dict) else {}
        market_regime = clusters.get("market_regime") if isinstance(clusters.get("market_regime"), dict) else {}
        sentiment = clusters.get("sentiment") if isinstance(clusters.get("sentiment"), dict) else {}
        options_positioning = clusters.get("options_positioning") if isinstance(clusters.get("options_positioning"), dict) else {}
        macro_calendar = clusters.get("macro_calendar") if isinstance(clusters.get("macro_calendar"), dict) else {}
        return {
            "market_regime": self._normalize_freshness(
                market_regime.get("freshness"),
                fallback="fresh" if market_regime.get("latest_closes") else "missing",
            ),
            "sentiment": self._normalize_freshness(
                sentiment.get("freshness"),
                fallback="fresh" if sentiment.get("fear_greed") is not None else "missing",
            ),
            "options_positioning": self._normalize_freshness(
                options_positioning.get("freshness"),
                fallback="missing",
            ),
            "macro_calendar": self._normalize_freshness(macro_calendar.get("freshness"), fallback="unknown"),
        }

    def _normalize_persisted_review(self, raw_row: Any) -> MarketPredictionClusterReview | None:
        if raw_row is None:
            return None
        if isinstance(raw_row, MarketPredictionClusterReview):
            return raw_row
        if not isinstance(raw_row, dict):
            return None
        cluster_scorecards = self._normalize_persisted_scorecards(raw_row.get("cluster_scorecards"))
        review_summary = self._normalize_review_summary(raw_row.get("review_summary"), raw_row.get("generated_at"), raw_row.get("review_state"))
        if cluster_scorecards is None or review_summary is None:
            return None
        try:
            return MarketPredictionClusterReview(
                id=str(raw_row["id"]),
                generated_at=self._coerce_datetime(raw_row["generated_at"]),
                as_of_ts=self._coerce_datetime(raw_row["as_of_ts"]),
                window_days=int(raw_row["window_days"]),
                review_state=str(raw_row["review_state"]),
                cluster_scorecards=cluster_scorecards,
                review_summary=review_summary,
                metadata=dict(raw_row.get("metadata") or {}),
            )
        except Exception:
            return None

    def _normalize_persisted_scorecards(self, raw_rows: Any) -> list[MarketPredictionClusterScorecardRow] | None:
        if not isinstance(raw_rows, list):
            return None
        normalized_by_key: dict[str, MarketPredictionClusterScorecardRow] = {}
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue
            cluster = normalize_market_prediction_cluster_key(raw_row.get("cluster"))
            if cluster not in SUPPORTED_ADAPTIVE_CLUSTER_KEYS or cluster in normalized_by_key:
                continue
            normalized_by_key[cluster] = MarketPredictionClusterScorecardRow(
                cluster=cluster,
                prior_weight=self._float_or_default(raw_row.get("prior_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS)),
                effective_weight=self._float_or_default(raw_row.get("effective_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS)),
                sample_size=int(raw_row.get("sample_size") or 0),
                direction_hit_rate=self._optional_float(raw_row.get("direction_hit_rate")),
                move_mae_pct=self._optional_float(raw_row.get("move_mae_pct")),
                brier_score=self._optional_float(raw_row.get("brier_score")),
                skill_score=self._optional_float(raw_row.get("skill_score")),
                freshness=self._normalize_freshness(raw_row.get("freshness"), fallback="unknown"),
                recommended_action=self._normalize_recommended_action(raw_row.get("recommended_action")),
            )
        if not normalized_by_key:
            return None
        ordered: list[MarketPredictionClusterScorecardRow] = []
        for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS:
            row = normalized_by_key.get(cluster)
            if row is None:
                row = MarketPredictionClusterScorecardRow(
                    cluster=cluster,
                    prior_weight=1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS),
                    effective_weight=1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS),
                    sample_size=0,
                    direction_hit_rate=None,
                    move_mae_pct=None,
                    brier_score=None,
                    skill_score=None,
                    freshness="unknown",
                    recommended_action="hold",
                )
            ordered.append(row)
        return ordered

    def _normalize_review_summary(self, raw_summary: Any, generated_at: Any, review_state: Any) -> dict[str, Any] | None:
        if not isinstance(raw_summary, dict):
            return None
        try:
            generated = self._coerce_datetime(generated_at).isoformat()
        except Exception:
            return None
        normalized_state = str(review_state or raw_summary.get("review_state") or "warmup")
        return {
            "generated_at": str(raw_summary.get("generated_at") or generated),
            "review_state": str(raw_summary.get("review_state") or normalized_state),
            "drift_callouts": [str(item) for item in raw_summary.get("drift_callouts", []) if str(item).strip()],
            "top_upweighted": [
                self._normalize_change_item(item)
                for item in raw_summary.get("top_upweighted", [])
                if self._normalize_change_item(item) is not None
            ],
            "top_downweighted": [
                self._normalize_change_item(item)
                for item in raw_summary.get("top_downweighted", [])
                if self._normalize_change_item(item) is not None
            ],
        }

    def _build_review_summary(
        self,
        *,
        scorecards: list[MarketPredictionClusterScorecardRow],
        review_state: str,
        generated_at: datetime,
    ) -> dict[str, Any]:
        upweighted = []
        downweighted = []
        drift_callouts = []
        for row in scorecards:
            delta = row.effective_weight - row.prior_weight
            if delta >= 0.05:
                upweighted.append(
                    {
                        "kind": "cluster",
                        "key": row.cluster,
                        "prior_weight": row.prior_weight,
                        "effective_weight": row.effective_weight,
                    }
                )
                drift_callouts.append(
                    f"{row.cluster} upweighted from {row.prior_weight:.4f} to {row.effective_weight:.4f}"
                )
            elif delta <= -0.05:
                downweighted.append(
                    {
                        "kind": "cluster",
                        "key": row.cluster,
                        "prior_weight": row.prior_weight,
                        "effective_weight": row.effective_weight,
                    }
                )
                drift_callouts.append(
                    f"{row.cluster} downweighted from {row.prior_weight:.4f} to {row.effective_weight:.4f}"
                )
        return {
            "generated_at": generated_at.isoformat(),
            "review_state": review_state,
            "drift_callouts": drift_callouts,
            "top_upweighted": upweighted,
            "top_downweighted": downweighted,
        }

    def _normalize_change_item(self, raw_item: Any) -> dict[str, Any] | None:
        if not isinstance(raw_item, dict):
            return None
        cluster = normalize_market_prediction_cluster_key(raw_item.get("key"))
        if str(raw_item.get("kind") or "") != "cluster" or cluster not in SUPPORTED_ADAPTIVE_CLUSTER_KEYS:
            return None
        return {
            "kind": "cluster",
            "key": cluster,
            "prior_weight": self._float_or_default(raw_item.get("prior_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS)),
            "effective_weight": self._float_or_default(raw_item.get("effective_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_CLUSTER_KEYS)),
        }

    def _review_metadata(self) -> dict[str, Any]:
        return {
            "weighting_half_life_days": _WEIGHTING_HALF_LIFE_DAYS,
            "trailing_window_trading_days": _TRAILING_WINDOW_TRADING_DAYS,
            "freshness_factors": dict(_FRESHNESS_FACTORS),
            "supported_windows": [1, 3, 7, 14],
        }

    def _normalize_sample(self, raw_sample: Any) -> MarketPredictionClusterEvaluationSample | None:
        if raw_sample is None:
            return None
        if isinstance(raw_sample, MarketPredictionClusterEvaluationSample):
            return raw_sample
        if not isinstance(raw_sample, dict):
            return None
        try:
            return MarketPredictionClusterEvaluationSample(
                call_id=str(raw_sample["call_id"]),
                window_days=int(raw_sample["window_days"]),
                target_date=self._coerce_date(raw_sample["target_date"]),
                active_cluster_keys=list(raw_sample.get("active_cluster_keys") or []),
                direction_hit=bool(raw_sample["direction_hit"]),
                move_abs_error_pct=float(raw_sample["move_abs_error_pct"]),
                brier_score=float(raw_sample["brier_score"]),
            )
        except Exception:
            return None

    def _normalize_cluster_keys(self, raw_keys: Any) -> list[str]:
        if not isinstance(raw_keys, list):
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_key in raw_keys:
            cluster = normalize_market_prediction_cluster_key(raw_key)
            if cluster not in SUPPORTED_ADAPTIVE_CLUSTER_KEYS or cluster in seen:
                continue
            seen.add(cluster)
            normalized.append(cluster)
        return normalized

    def _trading_day_age(self, *, target_date: date | None, effective_market_date: date) -> int | None:
        if target_date is None:
            return None
        if target_date > effective_market_date:
            return -1
        age = 0
        cursor = target_date
        while cursor < effective_market_date:
            cursor = get_next_trading_day(cursor)
            age += 1
            if age > _TRAILING_WINDOW_TRADING_DAYS:
                break
        return age

    @staticmethod
    def _skill_score(*, direction_hit_rate: float, move_mae_pct: float, brier_score: float) -> float:
        return (
            0.5 * (1.0 - max(0.0, min(1.0, brier_score)))
            + 0.3 * direction_hit_rate
            + 0.2 * (1.0 / (1.0 + move_mae_pct))
        )

    @staticmethod
    def _weighted_mean(values: list[float], weights: list[float]) -> float:
        total_weight = sum(weights)
        if total_weight <= 0:
            return 0.0
        return sum(value * weight for value, weight in zip(values, weights, strict=False)) / total_weight

    @staticmethod
    def _normalize_recommended_action(value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"upweight", "downweight", "hold"}:
            return normalized
        return "hold"

    @staticmethod
    def _float_or_default(value: Any, default: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        return numeric if math.isfinite(numeric) else default

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        try:
            numeric = None if value is None else float(value)
        except (TypeError, ValueError):
            return None
        if numeric is None or not math.isfinite(numeric):
            return None
        return numeric

    @staticmethod
    def _coerce_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _coerce_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _clamp(value: float, *, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _normalize_freshness(value: Any, *, fallback: str) -> str:
        normalized = normalize_market_prediction_cluster_key(value)
        if normalized in _FRESHNESS_FACTORS:
            return normalized
        return fallback if fallback in _FRESHNESS_FACTORS else "unknown"

    @staticmethod
    def _recommended_action(*, prior_weight: float, effective_weight: float) -> str:
        if effective_weight - prior_weight >= 0.05:
            return "upweight"
        if prior_weight - effective_weight >= 0.05:
            return "downweight"
        return "hold"

    @staticmethod
    def _review_id(*, window_days: int, as_of_ts: datetime) -> str:
        return f"cluster-review:{window_days}:{as_of_ts.isoformat()}"

    @staticmethod
    def _validate_window_days(window_days: int) -> None:
        if window_days not in {1, 3, 7, 14}:
            raise ValueError("Unsupported window_days")
