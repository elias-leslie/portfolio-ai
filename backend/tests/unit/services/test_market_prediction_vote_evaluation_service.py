from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.models.market_prediction import MarketPredictionVoteEvaluationCandidate
from app.services.market_prediction_evaluation_service import MarketPredictionEvaluationService


class _FakeRepo:
    def __init__(self, candidates: list[MarketPredictionVoteEvaluationCandidate]) -> None:
        self.candidates = candidates
        self.upserted: list[Any] = []
        self.calls: list[tuple[int, date, int, int]] = []

    def list_vote_evaluation_backfill_candidates(
        self,
        *,
        window_days: int,
        effective_market_date: date,
        run_limit: int = 120,
        max_age_days: int = 180,
    ) -> list[MarketPredictionVoteEvaluationCandidate]:
        self.calls.append((window_days, effective_market_date, run_limit, max_age_days))
        return self.candidates

    def upsert_vote_evaluation(self, evaluation: Any) -> None:
        self.upserted.append(evaluation)



def test_backfill_vote_evaluations_keeps_lowest_valid_duplicate_and_skips_unknown_or_invalid_rows() -> None:
    candidates = [
        MarketPredictionVoteEvaluationCandidate(
            vote_id=9,
            run_id="run-1",
            symbol="SPY",
            window_days=3,
            seat_key="macro",
            direction_label="bullish",
            prob_up=1.4,
            expected_move_pct=1.0,
            base_date=date(2026, 4, 20),
            target_date=date(2026, 4, 23),
        ),
        MarketPredictionVoteEvaluationCandidate(
            vote_id=10,
            run_id="run-1",
            symbol="SPY",
            window_days=3,
            seat_key=" Macro ",
            direction_label="bullish",
            prob_up=0.65,
            expected_move_pct=1.0,
            base_date=date(2026, 4, 20),
            target_date=date(2026, 4, 23),
        ),
        MarketPredictionVoteEvaluationCandidate(
            vote_id=11,
            run_id="run-1",
            symbol="SPY",
            window_days=3,
            seat_key="macro",
            direction_label="bullish",
            prob_up=0.7,
            expected_move_pct=1.5,
            base_date=date(2026, 4, 20),
            target_date=date(2026, 4, 23),
        ),
        MarketPredictionVoteEvaluationCandidate(
            vote_id=12,
            run_id="run-1",
            symbol="SPY",
            window_days=3,
            seat_key="new-seat",
            direction_label="bullish",
            prob_up=0.8,
            expected_move_pct=2.0,
            base_date=date(2026, 4, 20),
            target_date=date(2026, 4, 23),
        ),
        MarketPredictionVoteEvaluationCandidate(
            vote_id=13,
            run_id="run-1",
            symbol="SPY",
            window_days=3,
            seat_key="risk",
            direction_label="bearish",
            prob_up=0.4,
            expected_move_pct=float("nan"),
            base_date=date(2026, 4, 20),
            target_date=date(2026, 4, 23),
        ),
    ]
    repo = _FakeRepo(candidates)
    closes = {
        ("SPY", date(2026, 4, 20)): 500.0,
        ("SPY", date(2026, 4, 23)): 510.0,
    }
    service = MarketPredictionEvaluationService(
        repository=repo,
        price_lookup=lambda symbol, as_of_date: closes.get((symbol, as_of_date)),
        evaluated_at_fn=lambda: datetime(2026, 4, 23, 22, 5, tzinfo=UTC),
    )

    results = service.backfill_vote_evaluations(
        window_days=3,
        as_of_ts=datetime(2026, 4, 23, 22, 5, tzinfo=UTC),
    )

    assert repo.calls == [(3, date(2026, 4, 23), 120, 180)]
    assert len(results) == 1
    evaluation = results[0]
    assert evaluation.vote_id == 10
    assert evaluation.seat_key == "macro"
    assert evaluation.symbol == "SPY"
    assert evaluation.window_days == 3
    assert evaluation.realized_move_pct == pytest.approx(2.0)
    assert evaluation.direction_hit is True
    assert evaluation.move_abs_error_pct == pytest.approx(1.0)
    assert evaluation.brier_score == pytest.approx((1.0 - 0.65) ** 2)
    assert evaluation.metadata == {
        "run_id": "run-1",
        "base_date": "2026-04-20",
        "target_date": "2026-04-23",
    }
    assert repo.upserted[0] == evaluation



def test_backfill_vote_evaluations_treats_exact_zero_move_as_neutral_hit() -> None:
    repo = _FakeRepo(
        [
            MarketPredictionVoteEvaluationCandidate(
                vote_id=21,
                run_id="run-2",
                symbol="XLF",
                window_days=1,
                seat_key="risk",
                direction_label="neutral",
                prob_up=0.4,
                expected_move_pct=0.0,
                base_date=date(2026, 4, 24),
                target_date=date(2026, 4, 25),
            )
        ]
    )
    closes = {
        ("XLF", date(2026, 4, 24)): 42.0,
        ("XLF", date(2026, 4, 25)): 42.0,
    }
    service = MarketPredictionEvaluationService(
        repository=repo,
        price_lookup=lambda symbol, as_of_date: closes.get((symbol, as_of_date)),
        evaluated_at_fn=lambda: datetime(2026, 4, 25, 22, 5, tzinfo=UTC),
    )

    results = service.backfill_vote_evaluations(
        window_days=1,
        as_of_ts=datetime(2026, 4, 25, 22, 5, tzinfo=UTC),
    )

    assert len(results) == 1
    evaluation = results[0]
    assert evaluation.vote_id == 21
    assert evaluation.realized_move_pct == pytest.approx(0.0)
    assert evaluation.direction_hit is True
    assert evaluation.brier_score == pytest.approx(0.16)



def test_backfill_vote_evaluations_treats_small_realized_move_as_neutral_hit() -> None:
    repo = _FakeRepo(
        [
            MarketPredictionVoteEvaluationCandidate(
                vote_id=22,
                run_id="run-3",
                symbol="XLF",
                window_days=1,
                seat_key="risk",
                direction_label="neutral",
                prob_up=0.4,
                expected_move_pct=0.0,
                base_date=date(2026, 4, 24),
                target_date=date(2026, 4, 25),
            )
        ]
    )
    closes = {
        ("XLF", date(2026, 4, 24)): 100.0,
        ("XLF", date(2026, 4, 25)): 100.3,
    }
    service = MarketPredictionEvaluationService(
        repository=repo,
        price_lookup=lambda symbol, as_of_date: closes.get((symbol, as_of_date)),
        evaluated_at_fn=lambda: datetime(2026, 4, 25, 22, 5, tzinfo=UTC),
    )

    results = service.backfill_vote_evaluations(
        window_days=1,
        as_of_ts=datetime(2026, 4, 25, 22, 5, tzinfo=UTC),
    )

    assert len(results) == 1
    evaluation = results[0]
    assert evaluation.vote_id == 22
    assert evaluation.realized_move_pct == pytest.approx(0.3)
    assert evaluation.direction_hit is True


def test_backfill_vote_evaluations_scores_statistical_baseline_seat() -> None:
    repo = _FakeRepo(
        [
            MarketPredictionVoteEvaluationCandidate(
                vote_id=31,
                run_id="run-baseline",
                symbol="SPY",
                window_days=3,
                seat_key="baseline",
                direction_label="bullish",
                prob_up=0.58,
                expected_move_pct=0.6,
                base_date=date(2026, 4, 20),
                target_date=date(2026, 4, 23),
            )
        ]
    )
    closes = {
        ("SPY", date(2026, 4, 20)): 500.0,
        ("SPY", date(2026, 4, 23)): 505.0,
    }
    service = MarketPredictionEvaluationService(
        repository=repo,
        price_lookup=lambda symbol, as_of_date: closes.get((symbol, as_of_date)),
        evaluated_at_fn=lambda: datetime(2026, 4, 23, 22, 5, tzinfo=UTC),
    )

    results = service.backfill_vote_evaluations(
        window_days=3,
        as_of_ts=datetime(2026, 4, 23, 22, 5, tzinfo=UTC),
    )

    assert len(results) == 1
    assert results[0].seat_key == "baseline"
    assert results[0].direction_hit is True
    assert results[0].brier_score == pytest.approx((1.0 - 0.58) ** 2)
