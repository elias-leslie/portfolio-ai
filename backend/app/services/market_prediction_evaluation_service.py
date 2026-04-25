"""Evaluation service for matured market prediction calls and votes."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from app.models.market_prediction import (
    SUPPORTED_ADAPTIVE_SEAT_KEYS,
    MarketPredictionEvaluation,
    MarketPredictionVoteEvaluation,
    MarketPredictionVoteEvaluationCandidate,
    normalize_market_prediction_seat_key,
)
from app.repositories.market_prediction_repository import MarketPredictionRepository
from app.storage import PortfolioStorage, get_storage
from app.utils.market_hours import NY_TZ, get_expected_data_date

_BACKFILL_RUN_LIMIT = 120
_MAX_BACKFILL_AGE_DAYS = 180
_NEUTRAL_MOVE_BAND_PCT = 0.5


class MarketPredictionEvaluationService:
    """Score matured prediction calls against realized day-bar outcomes."""

    def __init__(
        self,
        *,
        repository: MarketPredictionRepository | None = None,
        storage: PortfolioStorage | None = None,
        price_lookup: Callable[[str, date], float | None] | None = None,
        evaluated_at_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.storage = storage or get_storage()
        self.repository = repository or MarketPredictionRepository(self.storage)
        self._price_lookup = price_lookup or self._lookup_close
        self._evaluated_at_fn = evaluated_at_fn or (lambda: datetime.now(UTC))

    def evaluate_due_predictions(
        self,
        *,
        as_of_date: date | None = None,
        limit: int = 200,
    ) -> list[MarketPredictionEvaluation]:
        effective_date = as_of_date or date.today()
        results: list[MarketPredictionEvaluation] = []
        for candidate in self.repository.list_due_evaluation_candidates(effective_date, limit=limit):
            base_close = self._price_lookup(candidate.call.symbol, candidate.base_date)
            target_close = self._price_lookup(candidate.call.symbol, candidate.target_date)
            if base_close in (None, 0) or target_close is None:
                continue

            realized_move_pct = ((target_close / base_close) - 1.0) * 100.0
            actual_up = 1.0 if realized_move_pct > 0 else 0.0
            evaluation = MarketPredictionEvaluation(
                call_id=candidate.call.id or "",
                evaluated_at=self._evaluated_at_fn(),
                base_close=base_close,
                target_close=target_close,
                realized_move_pct=realized_move_pct,
                direction_hit=self._direction_hit(
                    predicted_direction=candidate.call.direction_label,
                    realized_move_pct=realized_move_pct,
                ),
                move_abs_error_pct=abs(realized_move_pct - candidate.call.expected_move_pct),
                brier_score=(actual_up - candidate.call.prob_up) ** 2,
                metadata={
                    "base_date": candidate.base_date.isoformat(),
                    "target_date": candidate.target_date.isoformat(),
                    "symbol": candidate.call.symbol,
                    "window_days": candidate.call.window_days,
                },
            )
            self.repository.upsert_evaluation(evaluation)
            results.append(evaluation)
        return results

    def backfill_vote_evaluations(
        self,
        *,
        window_days: int,
        as_of_ts: datetime,
    ) -> list[MarketPredictionVoteEvaluation]:
        effective_market_date = get_expected_data_date(as_of_ts.astimezone(NY_TZ))
        selected: dict[tuple[str, str, int, str], MarketPredictionVoteEvaluationCandidate] = {}
        for raw_candidate in self.repository.list_vote_evaluation_backfill_candidates(
            window_days=window_days,
            effective_market_date=effective_market_date,
            run_limit=_BACKFILL_RUN_LIMIT,
            max_age_days=_MAX_BACKFILL_AGE_DAYS,
        ):
            candidate = self._normalize_vote_candidate(raw_candidate)
            if candidate is None:
                continue
            seat_key = normalize_market_prediction_seat_key(candidate.seat_key)
            if seat_key not in SUPPORTED_ADAPTIVE_SEAT_KEYS:
                continue
            if not self._finite_probability(candidate.prob_up) or not self._finite_number(candidate.expected_move_pct):
                continue
            symbol = str(candidate.symbol).strip().upper()
            key = (candidate.run_id, symbol, candidate.window_days, seat_key)
            existing = selected.get(key)
            normalized_candidate = candidate.model_copy(update={"seat_key": seat_key, "symbol": symbol})
            if existing is None or normalized_candidate.vote_id < existing.vote_id:
                selected[key] = normalized_candidate

        results: list[MarketPredictionVoteEvaluation] = []
        for candidate in sorted(selected.values(), key=lambda row: row.vote_id):
            base_close = self._price_lookup(candidate.symbol, candidate.base_date)
            target_close = self._price_lookup(candidate.symbol, candidate.target_date)
            if base_close in (None, 0) or target_close is None:
                continue
            realized_move_pct = ((target_close / base_close) - 1.0) * 100.0
            actual_up = 1.0 if realized_move_pct > 0 else 0.0
            metadata: dict[str, Any] = {
                "run_id": candidate.run_id,
                "base_date": candidate.base_date.isoformat(),
                "target_date": candidate.target_date.isoformat(),
            }
            if candidate.confidence_score is not None:
                metadata["confidence_score"] = candidate.confidence_score
            evaluation = MarketPredictionVoteEvaluation(
                vote_id=candidate.vote_id,
                evaluated_at=self._evaluated_at_fn(),
                seat_key=str(candidate.seat_key),
                symbol=candidate.symbol,
                window_days=candidate.window_days,
                base_close=base_close,
                target_close=target_close,
                realized_move_pct=realized_move_pct,
                direction_hit=self._direction_hit(
                    predicted_direction=candidate.direction_label,
                    realized_move_pct=realized_move_pct,
                ),
                move_abs_error_pct=abs(realized_move_pct - candidate.expected_move_pct),
                brier_score=(actual_up - candidate.prob_up) ** 2,
                metadata=metadata,
            )
            self.repository.upsert_vote_evaluation(evaluation)
            results.append(evaluation)
        return results

    def _lookup_close(self, symbol: str, as_of_date: date) -> float | None:
        rows = self.storage.query(
            "SELECT close FROM day_bars WHERE symbol = ? AND date = ? LIMIT 1",
            [symbol, as_of_date],
        )
        if rows.is_empty():
            return None
        close = rows.row(0, named=True).get("close")
        return float(close) if close is not None else None

    def _normalize_vote_candidate(self, raw_candidate: Any) -> MarketPredictionVoteEvaluationCandidate | None:
        if raw_candidate is None:
            return None
        if isinstance(raw_candidate, MarketPredictionVoteEvaluationCandidate):
            return raw_candidate
        if not isinstance(raw_candidate, dict):
            return None
        try:
            return MarketPredictionVoteEvaluationCandidate(
                vote_id=int(raw_candidate["vote_id"]),
                run_id=str(raw_candidate["run_id"]),
                symbol=str(raw_candidate["symbol"]),
                window_days=int(raw_candidate["window_days"]),
                seat_key=raw_candidate.get("seat_key"),
                direction_label=str(raw_candidate["direction_label"]),
                prob_up=float(raw_candidate["prob_up"]),
                expected_move_pct=float(raw_candidate["expected_move_pct"]),
                base_date=self._coerce_date(raw_candidate["base_date"]),
                target_date=self._coerce_date(raw_candidate["target_date"]),
                confidence_score=self._optional_float(raw_candidate.get("confidence_score")),
            )
        except Exception:
            return None

    @staticmethod
    def _coerce_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

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
    def _finite_number(value: Any) -> bool:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return False
        return math.isfinite(numeric)

    @staticmethod
    def _finite_probability(value: Any) -> bool:
        if not MarketPredictionEvaluationService._finite_number(value):
            return False
        numeric = float(value)
        return 0.0 <= numeric <= 1.0

    @staticmethod
    def _direction_hit(*, predicted_direction: str, realized_move_pct: float) -> bool:
        if predicted_direction == "bullish":
            return realized_move_pct > 0
        if predicted_direction == "bearish":
            return realized_move_pct < 0
        return abs(realized_move_pct) <= _NEUTRAL_MOVE_BAND_PCT
