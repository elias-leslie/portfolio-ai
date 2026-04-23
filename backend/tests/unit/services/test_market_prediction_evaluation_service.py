"""Unit tests for the market prediction evaluation service."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.models.market_prediction import (
    MarketPredictionCall,
    MarketPredictionEvaluationCandidate,
)
from app.services.market_prediction_evaluation_service import MarketPredictionEvaluationService


class _FakeRepo:
    def __init__(self, candidates: list[MarketPredictionEvaluationCandidate]) -> None:
        self.candidates = candidates
        self.upserted: list[Any] = []

    def list_due_evaluation_candidates(
        self,
        as_of_date: date,
        limit: int = 200,
    ) -> list[MarketPredictionEvaluationCandidate]:
        return self.candidates[:limit]

    def upsert_evaluation(self, evaluation: Any) -> None:
        self.upserted.append(evaluation)


def test_evaluate_due_predictions_scores_direction_move_and_brier() -> None:
    candidate = MarketPredictionEvaluationCandidate(
        call=MarketPredictionCall(
            id="call-1",
            symbol="SPY",
            window_days=3,
            direction_label="bullish",
            prob_up=0.7,
            expected_move_pct=2.5,
        ),
        base_date=date(2026, 4, 20),
        target_date=date(2026, 4, 23),
    )
    repo = _FakeRepo([candidate])
    closes = {
        ("SPY", date(2026, 4, 20)): 500.0,
        ("SPY", date(2026, 4, 23)): 510.0,
    }
    service = MarketPredictionEvaluationService(
        repository=repo,
        price_lookup=lambda symbol, as_of_date: closes.get((symbol, as_of_date)),
        evaluated_at_fn=lambda: datetime(2026, 4, 23, 22, 5, tzinfo=UTC),
    )

    results = service.evaluate_due_predictions(as_of_date=date(2026, 4, 23))

    assert len(results) == 1
    evaluation = results[0]
    assert evaluation.call_id == "call-1"
    assert evaluation.realized_move_pct == pytest.approx(2.0)
    assert evaluation.direction_hit is True
    assert evaluation.move_abs_error_pct == pytest.approx(0.5)
    assert evaluation.brier_score == pytest.approx((1.0 - 0.7) ** 2)
    assert repo.upserted[0] == evaluation



def test_evaluate_due_predictions_treats_small_realized_move_as_neutral_hit() -> None:
    candidate = MarketPredictionEvaluationCandidate(
        call=MarketPredictionCall(
            id="call-neutral",
            symbol="XLF",
            window_days=1,
            direction_label="neutral",
            prob_up=0.5,
            expected_move_pct=0.0,
        ),
        base_date=date(2026, 4, 24),
        target_date=date(2026, 4, 25),
    )
    repo = _FakeRepo([candidate])
    closes = {
        ("XLF", date(2026, 4, 24)): 100.0,
        ("XLF", date(2026, 4, 25)): 100.3,
    }
    service = MarketPredictionEvaluationService(
        repository=repo,
        price_lookup=lambda symbol, as_of_date: closes.get((symbol, as_of_date)),
        evaluated_at_fn=lambda: datetime(2026, 4, 25, 22, 5, tzinfo=UTC),
    )

    results = service.evaluate_due_predictions(as_of_date=date(2026, 4, 25))

    assert len(results) == 1
    evaluation = results[0]
    assert evaluation.realized_move_pct == pytest.approx(0.3)
    assert evaluation.direction_hit is True
    assert repo.upserted[0] == evaluation
