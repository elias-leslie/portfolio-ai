"""Adaptive seat-weighting review service for market prediction committees."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from typing import Any

from app.logging_config import get_logger
from app.models.market_prediction import (
    SUPPORTED_ADAPTIVE_SEAT_KEYS,
    MarketPredictionSeatReview,
    MarketPredictionSeatReviewResponse,
    MarketPredictionSeatScorecardRow,
    MarketPredictionVoteEvaluation,
    normalize_market_prediction_seat_key,
)
from app.repositories.market_prediction_repository import MarketPredictionRepository
from app.services.market_prediction_committee_service import SUPPORTED_PREDICTION_WINDOWS
from app.storage import PortfolioStorage, get_storage
from app.utils.market_hours import NY_TZ, get_expected_data_date, get_next_trading_day

logger = get_logger(__name__)

_BACKFILL_RUN_LIMIT = 120
_MAX_BACKFILL_AGE_DAYS = 180
_TRAILING_WINDOW_TRADING_DAYS = 60
_WEIGHTING_HALF_LIFE_DAYS = 20
_WEIGHT_EPSILON = 1e-9


class MarketPredictionSeatWeightingService:
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
    ) -> MarketPredictionSeatReviewResponse:
        self._validate_window_days(window_days)
        effective_ts = self._coerce_datetime(as_of_ts or datetime.now(UTC))
        for raw_row in self.repository.list_latest_seat_reviews(window_days=window_days, limit=5):
            normalized = self._normalize_persisted_review(raw_row)
            if normalized is not None:
                return normalized
        return self._build_synthetic_warmup_response(window_days=window_days, as_of_ts=effective_ts)

    def resolve_and_persist_review(
        self,
        *,
        window_days: int,
        as_of_ts: datetime,
    ) -> MarketPredictionSeatReview:
        self._validate_window_days(window_days)
        effective_ts = self._coerce_datetime(as_of_ts)
        try:
            review = self._resolve_review(window_days=window_days, as_of_ts=effective_ts)
        except Exception:
            logger.warning("market_prediction_review_resolution_failed", window_days=window_days, exc_info=True)
            review = self._build_prior_review(window_days=window_days, as_of_ts=effective_ts, review_state="degraded")
        try:
            persisted = self.repository.upsert_seat_review(review)
            if isinstance(persisted, MarketPredictionSeatReview):
                return persisted
            normalized = self._normalize_review_model(persisted)
            return normalized or review
        except Exception:
            logger.warning("market_prediction_review_persist_failed", window_days=window_days, exc_info=True)
            degraded = self._build_prior_review(window_days=window_days, as_of_ts=effective_ts, review_state="degraded")
            degraded.metadata["_persisted"] = False
            return degraded

    def _resolve_review(self, *, window_days: int, as_of_ts: datetime) -> MarketPredictionSeatReview:
        effective_market_date = get_expected_data_date(as_of_ts.astimezone(NY_TZ))
        evaluations = [
            self._normalize_vote_evaluation(row)
            for row in self.repository.list_vote_evaluations_for_weighting(
                window_days=window_days,
                effective_market_date=effective_market_date,
            )
        ]
        filtered = [evaluation for evaluation in evaluations if evaluation is not None]
        grouped: dict[str, list[tuple[MarketPredictionVoteEvaluation, float]]] = {
            seat_key: [] for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS
        }
        for evaluation in filtered:
            seat_key = normalize_market_prediction_seat_key(evaluation.seat_key)
            if seat_key not in grouped:
                continue
            age = self._trading_day_age(
                target_date=self._parse_date(evaluation.metadata.get("target_date")),
                effective_market_date=effective_market_date,
            )
            if age is None or age < 0 or age > _TRAILING_WINDOW_TRADING_DAYS:
                continue
            grouped[seat_key].append((evaluation, 0.5 ** (age / _WEIGHTING_HALF_LIFE_DAYS)))

        scorecards = [
            self._resolve_scorecard(seat_key=seat_key, weighted_rows=grouped[seat_key])
            for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS
        ]
        review_state = "live" if any(row.sample_size >= 6 for row in scorecards) else "warmup"
        if review_state == "warmup":
            scorecards = self._apply_prior_only_weights(scorecards)
        else:
            scorecards = self._apply_effective_weights(scorecards)
        review = MarketPredictionSeatReview(
            id=self._review_id(window_days=window_days, as_of_ts=as_of_ts),
            generated_at=as_of_ts,
            as_of_ts=as_of_ts,
            window_days=window_days,
            review_state=review_state,
            seat_scorecards=scorecards,
            review_summary=self._build_review_summary(scorecards=scorecards, review_state=review_state, generated_at=as_of_ts),
            metadata=self._review_metadata(),
        )
        return review

    def _resolve_scorecard(
        self,
        *,
        seat_key: str,
        weighted_rows: list[tuple[MarketPredictionVoteEvaluation, float]],
    ) -> MarketPredictionSeatScorecardRow:
        prior_weight = 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS)
        if not weighted_rows:
            return MarketPredictionSeatScorecardRow(
                seat_key=seat_key,
                prior_weight=prior_weight,
                effective_weight=prior_weight,
                sample_size=0,
                direction_hit_rate=None,
                move_mae_pct=None,
                brier_score=None,
                skill_score=None,
                recommended_action="hold",
            )
        sample_size = len(weighted_rows)
        weights = [weight for _, weight in weighted_rows]
        direction_hit_rate = self._weighted_mean([1.0 if row.direction_hit else 0.0 for row, _ in weighted_rows], weights)
        move_mae_pct = self._weighted_mean([row.move_abs_error_pct for row, _ in weighted_rows], weights)
        brier_score = self._weighted_mean([row.brier_score for row, _ in weighted_rows], weights)
        skill_score = self._skill_score(
            direction_hit_rate=direction_hit_rate,
            move_mae_pct=move_mae_pct,
            brier_score=brier_score,
        )
        return MarketPredictionSeatScorecardRow(
            seat_key=seat_key,
            prior_weight=prior_weight,
            effective_weight=prior_weight,
            sample_size=sample_size,
            direction_hit_rate=direction_hit_rate,
            move_mae_pct=move_mae_pct,
            brier_score=brier_score,
            skill_score=skill_score,
            recommended_action="hold",
        )

    def _apply_prior_only_weights(
        self,
        scorecards: list[MarketPredictionSeatScorecardRow],
    ) -> list[MarketPredictionSeatScorecardRow]:
        return [
            row.model_copy(update={"effective_weight": row.prior_weight, "recommended_action": "hold"})
            for row in scorecards
        ]

    def _apply_effective_weights(
        self,
        scorecards: list[MarketPredictionSeatScorecardRow],
    ) -> list[MarketPredictionSeatScorecardRow]:
        raw_weights: dict[str, float] = {}
        indexed: dict[str, MarketPredictionSeatScorecardRow] = {row.seat_key: row for row in scorecards}
        for row in scorecards:
            if row.sample_size < 6 or row.skill_score is None:
                raw_weights[row.seat_key] = row.prior_weight
                continue
            shrink = min(1.0, row.sample_size / 24.0)
            raw_weights[row.seat_key] = row.prior_weight * (0.5 + shrink * row.skill_score)
        effective_weights = self._normalize_and_cap(raw_weights)
        updated: list[MarketPredictionSeatScorecardRow] = []
        for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS:
            row = indexed[seat_key]
            effective_weight = effective_weights[seat_key]
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

    def _normalize_and_cap(self, raw_weights: dict[str, float]) -> dict[str, float]:
        total = sum(max(0.0, raw_weights.get(seat_key, 0.0)) for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS)
        if total <= 0:
            return {seat_key: 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS) for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS}
        current = {
            seat_key: max(0.0, raw_weights.get(seat_key, 0.0)) / total
            for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS
        }
        capped: dict[str, float] = {}
        while True:
            over = [seat_key for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS if seat_key not in capped and current[seat_key] > 0.5 + _WEIGHT_EPSILON]
            if not over:
                break
            for seat_key in sorted(over):
                capped[seat_key] = 0.5
                current[seat_key] = 0.5
            remaining_mass = 1.0 - sum(capped.values())
            uncapped = [seat_key for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS if seat_key not in capped]
            if not uncapped:
                break
            uncapped_total = sum(current[seat_key] for seat_key in uncapped)
            if uncapped_total <= 0:
                equal_weight = remaining_mass / len(uncapped)
                for seat_key in uncapped:
                    current[seat_key] = equal_weight
            else:
                for seat_key in uncapped:
                    current[seat_key] = remaining_mass * (current[seat_key] / uncapped_total)
        normalized = {seat_key: capped.get(seat_key, current[seat_key]) for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS}
        total = sum(normalized.values())
        if total > 0:
            normalized = {seat_key: normalized[seat_key] / total for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS}
        return normalized

    def _recommended_action(self, *, prior_weight: float, effective_weight: float) -> str:
        if effective_weight - prior_weight >= 0.05:
            return "upweight"
        if prior_weight - effective_weight >= 0.05:
            return "downweight"
        return "hold"

    def _build_synthetic_warmup_response(
        self,
        *,
        window_days: int,
        as_of_ts: datetime,
    ) -> MarketPredictionSeatReviewResponse:
        return MarketPredictionSeatReviewResponse(
            as_of_ts=as_of_ts,
            window_days=window_days,
            review_state="warmup",
            seat_scorecards=self._prior_scorecards(),
            review_summary={
                "generated_at": as_of_ts.isoformat(),
                "review_state": "warmup",
                "drift_callouts": [],
                "top_upweighted": [],
                "top_downweighted": [],
            },
        )

    def _build_prior_review(
        self,
        *,
        window_days: int,
        as_of_ts: datetime,
        review_state: str,
    ) -> MarketPredictionSeatReview:
        scorecards = self._prior_scorecards()
        return MarketPredictionSeatReview(
            id=self._review_id(window_days=window_days, as_of_ts=as_of_ts),
            generated_at=as_of_ts,
            as_of_ts=as_of_ts,
            window_days=window_days,
            review_state=review_state,
            seat_scorecards=scorecards,
            review_summary=self._build_review_summary(scorecards=scorecards, review_state=review_state, generated_at=as_of_ts),
            metadata=self._review_metadata(),
        )

    def _prior_scorecards(self) -> list[MarketPredictionSeatScorecardRow]:
        prior = 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS)
        return [
            MarketPredictionSeatScorecardRow(
                seat_key=seat_key,
                prior_weight=prior,
                effective_weight=prior,
                sample_size=0,
                direction_hit_rate=None,
                move_mae_pct=None,
                brier_score=None,
                skill_score=None,
                recommended_action="hold",
            )
            for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS
        ]

    def _normalize_persisted_review(self, raw_row: Any) -> MarketPredictionSeatReviewResponse | None:
        review = self._normalize_review_model(raw_row)
        if review is None or not isinstance(review.review_summary, dict):
            return None
        rows = self._normalize_persisted_scorecards(review.seat_scorecards)
        if rows is None:
            return None
        summary = self._normalize_review_summary(review.review_summary, generated_at=review.generated_at, review_state=review.review_state)
        return MarketPredictionSeatReviewResponse(
            as_of_ts=review.as_of_ts,
            window_days=review.window_days,
            review_state=review.review_state,
            seat_scorecards=rows,
            review_summary=summary,
        )

    def _normalize_review_model(self, raw_row: Any) -> MarketPredictionSeatReview | None:
        if raw_row is None:
            return None
        if isinstance(raw_row, MarketPredictionSeatReview):
            return raw_row
        if not isinstance(raw_row, dict):
            return None
        try:
            return MarketPredictionSeatReview(
                id=str(raw_row["id"]),
                generated_at=self._coerce_datetime(raw_row["generated_at"]),
                as_of_ts=self._coerce_datetime(raw_row["as_of_ts"]),
                window_days=int(raw_row["window_days"]),
                review_state=str(raw_row["review_state"]),
                seat_scorecards=raw_row.get("seat_scorecards", []),
                review_summary=raw_row.get("review_summary", {}),
                metadata=raw_row.get("metadata", {}),
            )
        except Exception:
            return None

    def _normalize_persisted_scorecards(self, raw_rows: Any) -> list[MarketPredictionSeatScorecardRow] | None:
        if not isinstance(raw_rows, list):
            return None
        seen: set[str] = set()
        normalized_by_key: dict[str, MarketPredictionSeatScorecardRow] = {}
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict):
                continue
            seat_key = normalize_market_prediction_seat_key(raw_row.get("seat_key"))
            if seat_key not in SUPPORTED_ADAPTIVE_SEAT_KEYS or seat_key in seen:
                continue
            seen.add(seat_key)
            normalized_by_key[seat_key] = MarketPredictionSeatScorecardRow(
                seat_key=seat_key,
                prior_weight=self._float_or_default(raw_row.get("prior_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS)),
                effective_weight=self._float_or_default(raw_row.get("effective_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS)),
                sample_size=int(raw_row.get("sample_size") or 0),
                direction_hit_rate=self._optional_float(raw_row.get("direction_hit_rate")),
                move_mae_pct=self._optional_float(raw_row.get("move_mae_pct")),
                brier_score=self._optional_float(raw_row.get("brier_score")),
                skill_score=self._optional_float(raw_row.get("skill_score")),
                recommended_action=self._normalize_recommended_action(raw_row.get("recommended_action")),
            )
        ordered: list[MarketPredictionSeatScorecardRow] = []
        for seat_key in SUPPORTED_ADAPTIVE_SEAT_KEYS:
            row = normalized_by_key.get(seat_key)
            if row is None:
                prior = 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS)
                row = MarketPredictionSeatScorecardRow(
                    seat_key=seat_key,
                    prior_weight=prior,
                    effective_weight=prior,
                    sample_size=0,
                    direction_hit_rate=None,
                    move_mae_pct=None,
                    brier_score=None,
                    skill_score=None,
                    recommended_action="hold",
                )
            ordered.append(row)
        return ordered

    def _normalize_review_summary(
        self,
        raw_summary: dict[str, Any],
        *,
        generated_at: datetime,
        review_state: str,
    ) -> dict[str, Any]:
        return {
            "generated_at": str(raw_summary.get("generated_at") or generated_at.isoformat()),
            "review_state": str(raw_summary.get("review_state") or review_state),
            "drift_callouts": [str(item) for item in raw_summary.get("drift_callouts", []) if str(item).strip()],
            "top_upweighted": [self._normalize_change_item(item) for item in raw_summary.get("top_upweighted", []) if self._normalize_change_item(item) is not None],
            "top_downweighted": [self._normalize_change_item(item) for item in raw_summary.get("top_downweighted", []) if self._normalize_change_item(item) is not None],
        }

    def _build_review_summary(
        self,
        *,
        scorecards: list[MarketPredictionSeatScorecardRow],
        review_state: str,
        generated_at: datetime,
    ) -> dict[str, Any]:
        upweighted = []
        downweighted = []
        drift_callouts = []
        for row in scorecards:
            delta = row.effective_weight - row.prior_weight
            if delta >= 0.05:
                item = {
                    "kind": "seat",
                    "key": row.seat_key,
                    "prior_weight": row.prior_weight,
                    "effective_weight": row.effective_weight,
                }
                upweighted.append(item)
                drift_callouts.append(
                    f"{row.seat_key} upweighted from {row.prior_weight:.4f} to {row.effective_weight:.4f}"
                )
            elif delta <= -0.05:
                item = {
                    "kind": "seat",
                    "key": row.seat_key,
                    "prior_weight": row.prior_weight,
                    "effective_weight": row.effective_weight,
                }
                downweighted.append(item)
                drift_callouts.append(
                    f"{row.seat_key} downweighted from {row.prior_weight:.4f} to {row.effective_weight:.4f}"
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
        kind = str(raw_item.get("kind") or "")
        key = normalize_market_prediction_seat_key(raw_item.get("key"))
        if kind != "seat" or key not in SUPPORTED_ADAPTIVE_SEAT_KEYS:
            return None
        return {
            "kind": "seat",
            "key": key,
            "prior_weight": self._float_or_default(raw_item.get("prior_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS)),
            "effective_weight": self._float_or_default(raw_item.get("effective_weight"), 1.0 / len(SUPPORTED_ADAPTIVE_SEAT_KEYS)),
        }

    def _review_metadata(self) -> dict[str, Any]:
        return {
            "weighting_half_life_days": _WEIGHTING_HALF_LIFE_DAYS,
            "trailing_window_trading_days": _TRAILING_WINDOW_TRADING_DAYS,
            "backfill_run_limit": _BACKFILL_RUN_LIMIT,
            "supported_windows": list(SUPPORTED_PREDICTION_WINDOWS),
        }

    def _skill_score(self, *, direction_hit_rate: float, move_mae_pct: float, brier_score: float) -> float:
        return (
            0.5 * (1.0 - max(0.0, min(1.0, brier_score)))
            + 0.3 * direction_hit_rate
            + 0.2 * (1.0 / (1.0 + move_mae_pct))
        )

    def _weighted_mean(self, values: list[float], weights: list[float]) -> float:
        total_weight = sum(weights)
        if total_weight <= 0:
            return 0.0
        return sum(value * weight for value, weight in zip(values, weights, strict=False)) / total_weight

    def _normalize_vote_evaluation(self, raw_row: Any) -> MarketPredictionVoteEvaluation | None:
        if raw_row is None:
            return None
        if isinstance(raw_row, MarketPredictionVoteEvaluation):
            return raw_row
        if not isinstance(raw_row, dict):
            return None
        try:
            return MarketPredictionVoteEvaluation(
                vote_id=int(raw_row["vote_id"]),
                evaluated_at=self._coerce_datetime(raw_row["evaluated_at"]),
                seat_key=str(raw_row["seat_key"]),
                symbol=str(raw_row["symbol"]),
                window_days=int(raw_row["window_days"]),
                base_close=float(raw_row["base_close"]),
                target_close=float(raw_row["target_close"]),
                realized_move_pct=float(raw_row["realized_move_pct"]),
                direction_hit=bool(raw_row["direction_hit"]),
                move_abs_error_pct=float(raw_row["move_abs_error_pct"]),
                brier_score=float(raw_row["brier_score"]),
                metadata=dict(raw_row.get("metadata") or {}),
            )
        except Exception:
            return None

    def _review_id(self, *, window_days: int, as_of_ts: datetime) -> str:
        return f"seat-review:{window_days}:{as_of_ts.isoformat()}"

    def _validate_window_days(self, window_days: int) -> None:
        if window_days not in SUPPORTED_PREDICTION_WINDOWS:
            raise ValueError(
                f"Unsupported window_days={window_days}. Supported values: {', '.join(str(v) for v in SUPPORTED_PREDICTION_WINDOWS)}"
            )

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

    def _parse_date(self, value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return None

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
        return value
