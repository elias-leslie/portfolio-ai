from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.models.market_prediction import MarketPredictionSeatReview, MarketPredictionVoteEvaluation
from app.services.market_prediction_seat_weighting_service import (
    MarketPredictionSeatWeightingService,
)


class _FakeRepo:
    def __init__(self, *, latest_rows: list[Any] | None = None, evaluations: list[MarketPredictionVoteEvaluation] | None = None) -> None:
        self.latest_rows = latest_rows or []
        self.evaluations = evaluations or []
        self.persisted: list[MarketPredictionSeatReview] = []
        self.weighting_queries: list[tuple[int, date]] = []

    def list_latest_seat_reviews(self, *, window_days: int, limit: int = 5) -> list[Any]:
        assert window_days in {1, 3, 7, 14}
        return self.latest_rows[:limit]

    def list_vote_evaluations_for_weighting(
        self,
        *,
        window_days: int,
        effective_market_date: date,
    ) -> list[MarketPredictionVoteEvaluation]:
        self.weighting_queries.append((window_days, effective_market_date))
        return self.evaluations

    def upsert_seat_review(self, review: MarketPredictionSeatReview) -> MarketPredictionSeatReview:
        self.persisted.append(review)
        return review



def _vote_evaluation(
    *,
    vote_id: int,
    seat_key: str,
    direction_hit: bool,
    move_abs_error_pct: float,
    brier_score: float,
    target_date: str = "2026-04-23",
) -> MarketPredictionVoteEvaluation:
    return MarketPredictionVoteEvaluation(
        vote_id=vote_id,
        evaluated_at=datetime(2026, 4, 23, 22, 5, tzinfo=UTC),
        seat_key=seat_key,
        symbol="SPY",
        window_days=3,
        base_close=500.0,
        target_close=510.0,
        realized_move_pct=2.0,
        direction_hit=direction_hit,
        move_abs_error_pct=move_abs_error_pct,
        brier_score=brier_score,
        metadata={
            "run_id": f"run-{vote_id}",
            "base_date": "2026-04-20",
            "target_date": target_date,
        },
    )



def test_get_review_returns_synthetic_warmup_before_first_persisted_row() -> None:
    service = MarketPredictionSeatWeightingService(repository=_FakeRepo())
    as_of_ts = datetime(2026, 4, 23, 22, 15, tzinfo=UTC)

    review = service.get_review(window_days=3, as_of_ts=as_of_ts)

    assert review.as_of_ts == as_of_ts
    assert review.window_days == 3
    assert review.review_state == "warmup"
    assert [row.seat_key for row in review.seat_scorecards] == ["cross_asset", "macro", "risk"]
    assert [row.sample_size for row in review.seat_scorecards] == [0, 0, 0]
    assert [row.recommended_action for row in review.seat_scorecards] == ["hold", "hold", "hold"]
    assert all(row.prior_weight == pytest.approx(1 / 3) for row in review.seat_scorecards)
    assert all(row.effective_weight == pytest.approx(1 / 3) for row in review.seat_scorecards)
    assert review.review_summary == {
        "generated_at": "2026-04-23T22:15:00+00:00",
        "review_state": "warmup",
        "drift_callouts": [],
        "top_upweighted": [],
        "top_downweighted": [],
    }



def test_resolve_and_persist_review_computes_live_weights_and_recommended_actions() -> None:
    repo = _FakeRepo(
        evaluations=[
            *[_vote_evaluation(vote_id=100 + idx, seat_key="macro", direction_hit=True, move_abs_error_pct=0.1, brier_score=0.01) for idx in range(6)],
            *[_vote_evaluation(vote_id=200 + idx, seat_key="cross_asset", direction_hit=bool(idx % 2), move_abs_error_pct=1.0, brier_score=0.25) for idx in range(6)],
            *[_vote_evaluation(vote_id=300 + idx, seat_key="risk", direction_hit=False, move_abs_error_pct=4.0, brier_score=1.0) for idx in range(6)],
        ]
    )
    service = MarketPredictionSeatWeightingService(repository=repo)
    as_of_ts = datetime(2026, 4, 23, 22, 15, tzinfo=UTC)

    review = service.resolve_and_persist_review(window_days=3, as_of_ts=as_of_ts)

    assert repo.weighting_queries == [(3, date(2026, 4, 23))]
    assert review.id == "seat-review:3:2026-04-23T22:15:00+00:00"
    assert review.review_state == "live"
    assert [row.seat_key for row in review.seat_scorecards] == ["cross_asset", "macro", "risk"]
    scorecards = {row.seat_key: row for row in review.seat_scorecards}
    assert scorecards["macro"].effective_weight == pytest.approx(0.3895431834)
    assert scorecards["cross_asset"].effective_weight == pytest.approx(0.3435046395)
    assert scorecards["risk"].effective_weight == pytest.approx(0.2669521770)
    assert scorecards["macro"].recommended_action == "upweight"
    assert scorecards["cross_asset"].recommended_action == "hold"
    assert scorecards["risk"].recommended_action == "downweight"
    assert review.metadata == {
        "weighting_half_life_days": 20,
        "trailing_window_trading_days": 60,
        "backfill_run_limit": 120,
        "supported_windows": [1, 3, 7, 14],
    }
    assert repo.persisted[0] == review



def test_get_review_ignores_malformed_latest_row_and_falls_back_to_next_valid_review() -> None:
    latest_rows = [
        {
            "id": "seat-review:3:2026-04-24T22:15:00+00:00",
            "generated_at": datetime(2026, 4, 24, 22, 15, tzinfo=UTC),
            "as_of_ts": datetime(2026, 4, 24, 22, 15, tzinfo=UTC),
            "window_days": 3,
            "review_state": "degraded",
            "seat_scorecards": {"bad": True},
            "review_summary": [],
            "metadata": {},
        },
        MarketPredictionSeatReview(
            id="seat-review:3:2026-04-23T22:15:00+00:00",
            generated_at=datetime(2026, 4, 23, 22, 15, tzinfo=UTC),
            as_of_ts=datetime(2026, 4, 23, 22, 15, tzinfo=UTC),
            window_days=3,
            review_state="live",
            seat_scorecards=[
                {
                    "seat_key": "cross_asset",
                    "prior_weight": 1 / 3,
                    "effective_weight": 0.3,
                    "sample_size": 8,
                    "direction_hit_rate": 0.5,
                    "move_mae_pct": 1.5,
                    "brier_score": 0.2,
                    "skill_score": 0.6,
                    "recommended_action": "hold",
                },
                {
                    "seat_key": "macro",
                    "prior_weight": 1 / 3,
                    "effective_weight": 0.45,
                    "sample_size": 8,
                    "direction_hit_rate": 0.8,
                    "move_mae_pct": 0.4,
                    "brier_score": 0.08,
                    "skill_score": 0.86,
                    "recommended_action": "upweight",
                },
                {
                    "seat_key": "risk",
                    "prior_weight": 1 / 3,
                    "effective_weight": 0.25,
                    "sample_size": 8,
                    "direction_hit_rate": 0.2,
                    "move_mae_pct": 3.0,
                    "brier_score": 0.7,
                    "skill_score": 0.2,
                    "recommended_action": "downweight",
                },
            ],
            review_summary={
                "generated_at": "2026-04-23T22:15:00+00:00",
                "review_state": "live",
                "drift_callouts": ["macro trending stronger than risk"],
                "top_upweighted": [{"kind": "seat", "key": "macro", "prior_weight": 1 / 3, "effective_weight": 0.45}],
                "top_downweighted": [{"kind": "seat", "key": "risk", "prior_weight": 1 / 3, "effective_weight": 0.25}],
            },
            metadata={
                "weighting_half_life_days": 20,
                "trailing_window_trading_days": 60,
                "backfill_run_limit": 120,
                "supported_windows": [1, 3, 7, 14],
            },
        ),
    ]
    service = MarketPredictionSeatWeightingService(repository=_FakeRepo(latest_rows=latest_rows))

    review = service.get_review(window_days=3, as_of_ts=datetime(2026, 4, 24, 22, 15, tzinfo=UTC))

    assert review.as_of_ts == datetime(2026, 4, 23, 22, 15, tzinfo=UTC)
    assert review.review_state == "live"
    assert [row.seat_key for row in review.seat_scorecards] == ["cross_asset", "macro", "risk"]
    assert review.review_summary["top_upweighted"][0] == {
        "kind": "seat",
        "key": "macro",
        "prior_weight": pytest.approx(1 / 3),
        "effective_weight": 0.45,
    }
