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
_MIN_CLUSTER_SAMPLE_SIZE = 8
_LIVE_CLUSTER_SAMPLE_SIZE = 8
_FRESHNESS_FACTORS = {
    "fresh": 1.0,
    "stale": 0.5,
    "missing": 0.0,
    "unknown": 0.25,
}
_CLUSTER_PRIORS_1D_3D = {
    "price_structure_market_regime_breadth": 24.0,
    "overnight_premarket_afterhours_futures_news": 18.0,
    "mag7_sector_leadership": 15.0,
    "options_positioning": 14.0,
    "macro_calendar": 12.0,
    "news_filings_earnings_analyst": 10.0,
    "sentiment_fear_greed": 4.0,
    "oil_shock_overlay": 2.0,
    "holiday_turn_of_month": 1.0,
    "day_of_week": 0.0,
    "freight_transport_event": 0.0,
}
_CLUSTER_PRIORS_7D_14D = {
    "price_structure_market_regime_breadth": 26.0,
    "overnight_premarket_afterhours_futures_news": 10.0,
    "mag7_sector_leadership": 16.0,
    "options_positioning": 10.0,
    "macro_calendar": 16.0,
    "news_filings_earnings_analyst": 14.0,
    "sentiment_fear_greed": 5.0,
    "oil_shock_overlay": 2.0,
    "holiday_turn_of_month": 1.0,
    "day_of_week": 0.0,
    "freight_transport_event": 0.0,
}
_OVERLAP_GROUPS = (
    (
        "price_structure_market_regime_breadth",
        "overnight_premarket_afterhours_futures_news",
        "mag7_sector_leadership",
    ),
    ("macro_calendar", "news_filings_earnings_analyst", "sentiment_fear_greed"),
    ("oil_shock_overlay", "freight_transport_event"),
)
_TRACKED_ONLY_CLUSTERS = {"day_of_week"}
_CLUSTER_AGENT_ROUTES = {
    "price_structure_market_regime_breadth": "investment-committee",
    "overnight_premarket_afterhours_futures_news": "equity-analyst",
    "mag7_sector_leadership": "equity-analyst",
    "options_positioning": "risk-manager",
    "macro_calendar": "risk-manager",
    "news_filings_earnings_analyst": "equity-analyst",
    "sentiment_fear_greed": "investment-committee",
    "oil_shock_overlay": "risk-manager",
    "holiday_turn_of_month": "investment-committee",
    "day_of_week": "investment-committee",
    "freight_transport_event": "risk-manager",
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
        gate_map = self._gate_map(source_snapshot)
        scorecards = [
            self._resolve_scorecard(
                window_days=window_days,
                cluster=cluster,
                weighted_rows=grouped[cluster],
                freshness=freshness_map[cluster],
                gate_state=gate_map[cluster],
            )
            for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS
        ]
        has_live_signal = any(row.sample_size >= _LIVE_CLUSTER_SAMPLE_SIZE for row in scorecards)
        has_active_freshness = any(
            self._freshness_factor(cluster=row.cluster, freshness=row.freshness) > _WEIGHT_EPSILON
            for row in scorecards
        )
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
        window_days: int,
        cluster: str,
        weighted_rows: list[tuple[MarketPredictionClusterEvaluationSample, float]],
        freshness: str,
        gate_state: str,
    ) -> MarketPredictionClusterScorecardRow:
        prior_weight = self._prior_weight(window_days=window_days, cluster=cluster)
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
                gate_state=self._normalize_gate_state(gate_state),
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
            gate_state=self._normalize_gate_state(gate_state),
            recommended_action="hold",
        )

    def _apply_prior_only_weights(
        self,
        scorecards: list[MarketPredictionClusterScorecardRow],
    ) -> list[MarketPredictionClusterScorecardRow]:
        raw_weights = {
            row.cluster: row.prior_weight
            * self._freshness_factor(cluster=row.cluster, freshness=row.freshness)
            * self._gate_factor(row)
            for row in scorecards
        }
        total = sum(weight for weight in raw_weights.values() if weight > _WEIGHT_EPSILON)
        if total <= _WEIGHT_EPSILON:
            return [
                row.model_copy(
                    update={
                        "effective_weight": 0.0,
                        "gate_state": self._gate_state(row=row, effective_weight=0.0),
                        "recommended_action": self._recommended_action(
                            prior_weight=row.prior_weight,
                            effective_weight=0.0,
                            gate_state=self._gate_state(row=row, effective_weight=0.0),
                        ),
                    }
                )
                for row in scorecards
            ]
        return [
            self._with_effective_weight(row, effective_weight=(raw_weights[row.cluster] / total) * 100.0)
            for row in scorecards
        ]

    def _apply_effective_weights(
        self,
        scorecards: list[MarketPredictionClusterScorecardRow],
    ) -> list[MarketPredictionClusterScorecardRow]:
        raw_weights: dict[str, float] = {}
        indexed = {row.cluster: row for row in scorecards}
        for row in scorecards:
            freshness_factor = self._freshness_factor(cluster=row.cluster, freshness=row.freshness)
            gate_factor = self._gate_factor(row)
            if row.sample_size < _MIN_CLUSTER_SAMPLE_SIZE or row.skill_score is None:
                learned_multiplier = 1.0
            else:
                shrink = min(1.0, row.sample_size / 30.0)
                learned_multiplier = self._clamp(0.5 + shrink * row.skill_score, low=0.5, high=1.5)
            raw_weights[row.cluster] = row.prior_weight * freshness_factor * gate_factor * learned_multiplier
        raw_weights = self._apply_overlap_penalty(raw_weights=raw_weights, scorecards=scorecards)
        total = sum(weight for weight in raw_weights.values() if weight > _WEIGHT_EPSILON)
        if total <= _WEIGHT_EPSILON:
            return [
                row.model_copy(
                    update={
                        "effective_weight": 0.0,
                        "gate_state": self._gate_state(row=row, effective_weight=0.0),
                        "recommended_action": self._recommended_action(
                            prior_weight=row.prior_weight,
                            effective_weight=0.0,
                            gate_state=self._gate_state(row=row, effective_weight=0.0),
                        ),
                    }
                )
                for row in scorecards
            ]
        updated: list[MarketPredictionClusterScorecardRow] = []
        for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS:
            row = indexed[cluster]
            effective_weight = (raw_weights[cluster] / total) * 100.0
            updated.append(self._with_effective_weight(row, effective_weight=effective_weight))
        return updated

    def _build_prior_review(
        self,
        *,
        window_days: int,
        as_of_ts: datetime,
        review_state: str,
        source_snapshot: dict[str, Any],
    ) -> MarketPredictionClusterReview:
        scorecards = self._prior_scorecards(window_days=window_days, source_snapshot=source_snapshot)
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

    def _prior_scorecards(
        self,
        *,
        window_days: int,
        source_snapshot: dict[str, Any],
    ) -> list[MarketPredictionClusterScorecardRow]:
        freshness_map = self._freshness_map(source_snapshot)
        gate_map = self._gate_map(source_snapshot)
        base_rows = [
            MarketPredictionClusterScorecardRow(
                cluster=cluster,
                prior_weight=self._prior_weight(window_days=window_days, cluster=cluster),
                effective_weight=self._prior_weight(window_days=window_days, cluster=cluster),
                sample_size=0,
                direction_hit_rate=None,
                move_mae_pct=None,
                brier_score=None,
                skill_score=None,
                freshness=freshness_map[cluster],
                gate_state=gate_map[cluster],
                recommended_action="hold",
            )
            for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS
        ]
        return self._apply_prior_only_weights(base_rows)

    def _freshness_map(self, source_snapshot: dict[str, Any]) -> dict[str, str]:
        clusters = source_snapshot.get("clusters") if isinstance(source_snapshot, dict) else {}
        clusters = clusters if isinstance(clusters, dict) else {}
        market_regime = self._cluster_payload(clusters, "price_structure_market_regime_breadth", "market_regime")
        overnight = self._cluster_payload(clusters, "overnight_premarket_afterhours_futures_news")
        mag7 = self._cluster_payload(clusters, "mag7_sector_leadership")
        options_positioning = self._cluster_payload(clusters, "options_positioning")
        macro_calendar = self._cluster_payload(clusters, "macro_calendar")
        news = self._cluster_payload(clusters, "news_filings_earnings_analyst")
        sentiment = self._cluster_payload(clusters, "sentiment_fear_greed", "sentiment")
        oil = self._cluster_payload(clusters, "oil_shock_overlay")
        return {
            "price_structure_market_regime_breadth": self._normalize_freshness(
                market_regime.get("freshness"),
                fallback="fresh" if market_regime.get("latest_closes") else "missing",
            ),
            "overnight_premarket_afterhours_futures_news": self._normalize_freshness(
                overnight.get("freshness"),
                fallback="missing",
            ),
            "mag7_sector_leadership": self._normalize_freshness(
                mag7.get("freshness"),
                fallback="missing",
            ),
            "options_positioning": self._normalize_freshness(
                options_positioning.get("freshness"),
                fallback="missing",
            ),
            "macro_calendar": self._normalize_freshness(macro_calendar.get("freshness"), fallback="unknown"),
            "news_filings_earnings_analyst": self._normalize_freshness(news.get("freshness"), fallback="missing"),
            "sentiment_fear_greed": self._normalize_freshness(
                sentiment.get("freshness"),
                fallback="fresh" if sentiment.get("fear_greed") is not None else "missing",
            ),
            "oil_shock_overlay": self._normalize_freshness(oil.get("freshness"), fallback="missing"),
            "holiday_turn_of_month": "fresh",
            "day_of_week": "fresh",
            "freight_transport_event": self._normalize_freshness(
                self._cluster_payload(clusters, "freight_transport_event").get("freshness"),
                fallback="fresh",
            ),
        }

    def _gate_map(self, source_snapshot: dict[str, Any]) -> dict[str, str]:
        clusters = source_snapshot.get("clusters") if isinstance(source_snapshot, dict) else {}
        clusters = clusters if isinstance(clusters, dict) else {}
        oil = self._cluster_payload(clusters, "oil_shock_overlay")
        freight = self._cluster_payload(clusters, "freight_transport_event")
        holiday = self._cluster_payload(clusters, "holiday_turn_of_month")
        return {
            "price_structure_market_regime_breadth": "active",
            "overnight_premarket_afterhours_futures_news": "active",
            "mag7_sector_leadership": "active",
            "options_positioning": "active",
            "macro_calendar": "active",
            "news_filings_earnings_analyst": "active",
            "sentiment_fear_greed": "active",
            "oil_shock_overlay": "active"
            if self._normalize_gate_state(oil.get("gate_state")) == "active"
            or "energy_supply_shock" in self._event_tags(oil)
            else "downweighted",
            "holiday_turn_of_month": "active"
            if self._normalize_gate_state(holiday.get("gate_state")) == "active"
            else "off",
            "day_of_week": "tracked_only",
            "freight_transport_event": "active"
            if "freight_disruption" in self._event_tags(freight)
            else "tracked_only",
        }

    @staticmethod
    def _cluster_payload(clusters: dict[str, Any], *keys: str) -> dict[str, Any]:
        for key in keys:
            payload = clusters.get(key)
            if isinstance(payload, dict):
                return payload
        return {}

    @staticmethod
    def _event_tags(payload: dict[str, Any]) -> set[str]:
        raw_tags = payload.get("event_tags")
        if not isinstance(raw_tags, list):
            return set()
        return {str(tag).strip().lower() for tag in raw_tags if str(tag).strip()}

    def _normalize_persisted_review(self, raw_row: Any) -> MarketPredictionClusterReview | None:
        if raw_row is None:
            return None
        if isinstance(raw_row, MarketPredictionClusterReview):
            raw_row = raw_row.model_dump()
        if not isinstance(raw_row, dict):
            return None
        cluster_scorecards = self._normalize_persisted_scorecards(
            raw_row.get("cluster_scorecards"),
            window_days=self._int_or_default(raw_row.get("window_days"), 3),
        )
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

    def _normalize_persisted_scorecards(
        self,
        raw_rows: Any,
        *,
        window_days: int,
    ) -> list[MarketPredictionClusterScorecardRow] | None:
        if not isinstance(raw_rows, list):
            return None
        if self._has_legacy_cluster_weight_scale(raw_rows, window_days=window_days):
            return None
        normalized_by_key: dict[str, MarketPredictionClusterScorecardRow] = {}
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue
            cluster = normalize_market_prediction_cluster_key(raw_row.get("cluster"))
            if cluster not in SUPPORTED_ADAPTIVE_CLUSTER_KEYS or cluster in normalized_by_key:
                continue
            prior = self._prior_weight(window_days=window_days, cluster=cluster)
            normalized_by_key[cluster] = MarketPredictionClusterScorecardRow(
                cluster=cluster,
                prior_weight=self._float_or_default(raw_row.get("prior_weight"), prior),
                effective_weight=self._float_or_default(raw_row.get("effective_weight"), prior),
                sample_size=int(raw_row.get("sample_size") or 0),
                direction_hit_rate=self._optional_float(raw_row.get("direction_hit_rate")),
                move_mae_pct=self._optional_float(raw_row.get("move_mae_pct")),
                brier_score=self._optional_float(raw_row.get("brier_score")),
                skill_score=self._optional_float(raw_row.get("skill_score")),
                freshness=self._normalize_freshness(raw_row.get("freshness"), fallback="unknown"),
                gate_state=self._normalize_gate_state(raw_row.get("gate_state")),
                recommended_action=self._normalize_recommended_action(raw_row.get("recommended_action")),
            )
        if not normalized_by_key:
            return None
        ordered: list[MarketPredictionClusterScorecardRow] = []
        for cluster in SUPPORTED_ADAPTIVE_CLUSTER_KEYS:
            row = normalized_by_key.get(cluster)
            if row is None:
                prior = self._prior_weight(window_days=window_days, cluster=cluster)
                row = MarketPredictionClusterScorecardRow(
                    cluster=cluster,
                    prior_weight=prior,
                    effective_weight=prior,
                    sample_size=0,
                    direction_hit_rate=None,
                    move_mae_pct=None,
                    brier_score=None,
                    skill_score=None,
                    freshness="unknown",
                    gate_state="off",
                    recommended_action="hold",
                )
            ordered.append(row)
        return ordered

    def _has_legacy_cluster_weight_scale(self, raw_rows: list[Any], *, window_days: int) -> bool:
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue
            cluster = normalize_market_prediction_cluster_key(raw_row.get("cluster"))
            if cluster not in SUPPORTED_ADAPTIVE_CLUSTER_KEYS:
                continue
            expected_prior = self._prior_weight(window_days=window_days, cluster=cluster)
            raw_prior = self._optional_float(raw_row.get("prior_weight"))
            if expected_prior > 1.0 and raw_prior is not None and 0.0 < raw_prior <= 1.0:
                return True
        return False

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
            "gap_callouts": [str(item) for item in raw_summary.get("gap_callouts", []) if str(item).strip()],
            "agent_actions": [str(item) for item in raw_summary.get("agent_actions", []) if str(item).strip()],
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
        gap_callouts = []
        agent_actions = []
        for row in scorecards:
            delta = row.effective_weight - row.prior_weight
            if row.sample_size < _MIN_CLUSTER_SAMPLE_SIZE:
                gap_callouts.append(
                    f"{row.cluster} has {row.sample_size} matured samples; keep shrinkage until 8+."
                )
                agent_actions.append(
                    self._agent_action_for_gap(
                        cluster=row.cluster,
                        gap="collect more matured outcomes before promoting this signal",
                    )
                )
            if row.freshness in {"stale", "missing", "unknown"}:
                gap_callouts.append(f"{row.cluster} data freshness is {row.freshness}.")
                agent_actions.append(
                    self._agent_action_for_gap(
                        cluster=row.cluster,
                        gap=f"repair {row.freshness} input data before treating it as edge",
                    )
                )
            if row.gate_state in {"off", "tracked_only"}:
                gap_callouts.append(f"{row.cluster} is {row.gate_state}; review-only until a real catalyst appears.")
                agent_actions.append(
                    self._agent_action_for_gap(
                        cluster=row.cluster,
                        gap=f"keep {row.gate_state} gate review-only until a real catalyst appears",
                    )
                )
            if delta >= 2.0:
                upweighted.append(
                    {
                        "kind": "cluster",
                        "key": row.cluster,
                        "prior_weight": row.prior_weight,
                        "effective_weight": row.effective_weight,
                    }
                )
                drift_callouts.append(
                    f"{row.cluster} upweighted from {row.prior_weight:.2f} to {row.effective_weight:.2f}"
                )
            elif delta <= -2.0:
                downweighted.append(
                    {
                        "kind": "cluster",
                        "key": row.cluster,
                        "prior_weight": row.prior_weight,
                        "effective_weight": row.effective_weight,
                    }
                )
                drift_callouts.append(
                    f"{row.cluster} downweighted from {row.prior_weight:.2f} to {row.effective_weight:.2f}"
                )
        return {
            "generated_at": generated_at.isoformat(),
            "review_state": review_state,
            "drift_callouts": drift_callouts,
            "gap_callouts": list(dict.fromkeys(gap_callouts)),
            "agent_actions": list(dict.fromkeys(agent_actions)),
            "top_upweighted": upweighted,
            "top_downweighted": downweighted,
        }

    def _agent_action_for_gap(self, *, cluster: str, gap: str) -> str:
        agent = _CLUSTER_AGENT_ROUTES.get(cluster, "investment-committee")
        return f"Jenny/{agent}: {cluster} gap - {gap}."

    def _normalize_change_item(self, raw_item: Any) -> dict[str, Any] | None:
        if not isinstance(raw_item, dict):
            return None
        cluster = normalize_market_prediction_cluster_key(raw_item.get("key"))
        if str(raw_item.get("kind") or "") != "cluster" or cluster not in SUPPORTED_ADAPTIVE_CLUSTER_KEYS:
            return None
        prior = self._prior_weight(window_days=3, cluster=cluster)
        return {
            "kind": "cluster",
            "key": cluster,
            "prior_weight": self._float_or_default(raw_item.get("prior_weight"), prior),
            "effective_weight": self._float_or_default(raw_item.get("effective_weight"), prior),
        }

    def _review_metadata(self) -> dict[str, Any]:
        return {
            "weighting_half_life_days": _WEIGHTING_HALF_LIFE_DAYS,
            "trailing_window_trading_days": _TRAILING_WINDOW_TRADING_DAYS,
            "min_cluster_sample_size": _MIN_CLUSTER_SAMPLE_SIZE,
            "freshness_factors": dict(_FRESHNESS_FACTORS),
            "cluster_priors_1d_3d": dict(_CLUSTER_PRIORS_1D_3D),
            "cluster_priors_7d_14d": dict(_CLUSTER_PRIORS_7D_14D),
            "overlap_groups": [list(group) for group in _OVERLAP_GROUPS],
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

    def _prior_weight(self, *, window_days: int, cluster: str) -> float:
        priors = _CLUSTER_PRIORS_7D_14D if window_days in {7, 14} else _CLUSTER_PRIORS_1D_3D
        return priors.get(cluster, 0.0)

    def _with_effective_weight(
        self,
        row: MarketPredictionClusterScorecardRow,
        *,
        effective_weight: float,
    ) -> MarketPredictionClusterScorecardRow:
        gate_state = self._gate_state(row=row, effective_weight=effective_weight)
        return row.model_copy(
            update={
                "effective_weight": max(0.0, effective_weight),
                "gate_state": gate_state,
                "recommended_action": self._recommended_action(
                    prior_weight=row.prior_weight,
                    effective_weight=effective_weight,
                    gate_state=gate_state,
                ),
            }
        )

    def _gate_factor(self, row: MarketPredictionClusterScorecardRow) -> float:
        if row.cluster in _TRACKED_ONLY_CLUSTERS:
            return 0.0
        if row.cluster == "holiday_turn_of_month":
            return 1.0 if row.gate_state == "active" else 0.0
        if row.cluster == "oil_shock_overlay":
            return 1.0 if row.gate_state == "active" else 0.25
        if row.cluster == "freight_transport_event":
            return 1.0 if row.gate_state == "active" else 0.0
        return 1.0

    def _gate_state(self, *, row: MarketPredictionClusterScorecardRow, effective_weight: float) -> str:
        if row.cluster in _TRACKED_ONLY_CLUSTERS:
            return "tracked_only"
        if row.cluster == "freight_transport_event" and row.prior_weight == 0.0 and effective_weight <= _WEIGHT_EPSILON:
            return "tracked_only"
        if row.prior_weight == 0.0 and effective_weight <= _WEIGHT_EPSILON:
            return "tracked_only"
        if effective_weight <= _WEIGHT_EPSILON:
            return "off"
        if effective_weight + _WEIGHT_EPSILON < row.prior_weight:
            return "downweighted"
        return "active"

    def _apply_overlap_penalty(
        self,
        *,
        raw_weights: dict[str, float],
        scorecards: list[MarketPredictionClusterScorecardRow],
    ) -> dict[str, float]:
        adjusted = dict(raw_weights)
        indexed = {row.cluster: row for row in scorecards}
        for group in _OVERLAP_GROUPS:
            active = [cluster for cluster in group if adjusted.get(cluster, 0.0) > _WEIGHT_EPSILON]
            if len(active) <= 1:
                continue
            keep = sorted(
                active,
                key=lambda cluster: (
                    -(indexed[cluster].skill_score if indexed[cluster].skill_score is not None else 0.0),
                    -indexed[cluster].prior_weight,
                    cluster,
                ),
            )[0]
            for cluster in active:
                if cluster != keep:
                    adjusted[cluster] *= 0.75
        return adjusted

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
        if normalized in {"upweight", "downweight", "hold", "track_only"}:
            return normalized
        return "hold"

    @staticmethod
    def _normalize_gate_state(value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"active", "downweighted", "off", "tracked_only"}:
            return normalized
        return "off"

    @staticmethod
    def _float_or_default(value: Any, default: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        return numeric if math.isfinite(numeric) else default

    @staticmethod
    def _int_or_default(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

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
    def _freshness_factor(*, cluster: str, freshness: str) -> float:
        normalized_cluster = normalize_market_prediction_cluster_key(cluster)
        normalized_freshness = MarketPredictionClusterWeightingService._normalize_freshness(
            freshness,
            fallback="unknown",
        )
        if normalized_cluster == "macro_calendar" and normalized_freshness in {"stale", "missing"}:
            return 0.0
        return _FRESHNESS_FACTORS[normalized_freshness]

    @staticmethod
    def _recommended_action(*, prior_weight: float, effective_weight: float, gate_state: str) -> str:
        if gate_state == "tracked_only" or (prior_weight == 0.0 and effective_weight <= _WEIGHT_EPSILON):
            return "track_only"
        if effective_weight - prior_weight >= 2.0:
            return "upweight"
        if prior_weight - effective_weight >= 2.0:
            return "downweight"
        return "hold"

    @staticmethod
    def _review_id(*, window_days: int, as_of_ts: datetime) -> str:
        return f"cluster-review:{window_days}:{as_of_ts.isoformat()}"

    @staticmethod
    def _validate_window_days(window_days: int) -> None:
        if window_days not in {1, 3, 7, 14}:
            raise ValueError("Unsupported window_days")
