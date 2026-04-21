"""Evaluation service for matured market prediction calls."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

from app.models.market_prediction import MarketPredictionEvaluation
from app.repositories.market_prediction_repository import MarketPredictionRepository
from app.storage import PortfolioStorage, get_storage


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

    def _lookup_close(self, symbol: str, as_of_date: date) -> float | None:
        rows = self.storage.query(
            "SELECT close FROM day_bars WHERE symbol = ? AND date = ? LIMIT 1",
            [symbol, as_of_date],
        )
        if rows.is_empty():
            return None
        close = rows.row(0, named=True).get("close")
        return float(close) if close is not None else None

    @staticmethod
    def _direction_hit(*, predicted_direction: str, realized_move_pct: float) -> bool:
        if predicted_direction == "bullish":
            return realized_move_pct > 0
        if predicted_direction == "bearish":
            return realized_move_pct < 0
        return realized_move_pct == 0
