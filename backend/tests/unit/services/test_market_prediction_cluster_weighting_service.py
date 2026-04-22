from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.models.market_prediction import (
    MarketPredictionClusterEvaluationSample,
    MarketPredictionClusterReview,
)
from app.services.market_prediction_cluster_weighting_service import (
    MarketPredictionClusterWeightingService,
)


class _FakeRepo:
    def __init__(
        self,
        *,
        latest_rows: list[Any] | None = None,
        samples: list[MarketPredictionClusterEvaluationSample] | None = None,
    ) -> None:
        self.latest_rows = latest_rows or []
        self.samples = samples or []
        self.persisted: list[MarketPredictionClusterReview] = []
        self.sample_queries: list[tuple[int, date]] = []
        self.raise_on_persist = False

    def list_latest_cluster_reviews(self, *, window_days: int, limit: int = 5) -> list[Any]:
        assert window_days in {1, 3, 7, 14}
        return self.latest_rows[:limit]

    def list_cluster_evaluation_samples(
        self,
        *,
        window_days: int,
        effective_market_date: date,
    ) -> list[MarketPredictionClusterEvaluationSample]:
        self.sample_queries.append((window_days, effective_market_date))
        return self.samples

    def upsert_cluster_review(self, review: MarketPredictionClusterReview) -> MarketPredictionClusterReview:
        if self.raise_on_persist:
            raise RuntimeError("persist failed")
        self.persisted.append(review)
        return review



def _source_snapshot() -> dict[str, Any]:
    return {
        "clusters": {
            "market_regime": {"freshness": "fresh"},
            "sentiment": {"freshness": "fresh"},
            "options_positioning": {"freshness": "fresh"},
            "macro_calendar": {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 1},
        }
    }



def _sample(
    *,
    call_id: str,
    cluster_keys: list[str],
    direction_hit: bool,
    move_abs_error_pct: float,
    brier_score: float,
    target_date: str = "2026-04-23",
) -> MarketPredictionClusterEvaluationSample:
    return MarketPredictionClusterEvaluationSample(
        call_id=call_id,
        window_days=3,
        target_date=date.fromisoformat(target_date),
        active_cluster_keys=cluster_keys,
        direction_hit=direction_hit,
        move_abs_error_pct=move_abs_error_pct,
        brier_score=brier_score,
    )



def test_get_review_returns_synthetic_warmup_before_first_persisted_row() -> None:
    service = MarketPredictionClusterWeightingService(repository=_FakeRepo())
    as_of_ts = datetime(2026, 4, 23, 22, 15, tzinfo=UTC)

    review = service.get_review(window_days=3, as_of_ts=as_of_ts, source_snapshot=_source_snapshot())

    assert review.id == "cluster-review:3:2026-04-23T22:15:00+00:00"
    assert review.review_state == "warmup"
    assert [row.cluster for row in review.cluster_scorecards] == [
        "market_regime",
        "sentiment",
        "options_positioning",
        "macro_calendar",
    ]
    assert [row.sample_size for row in review.cluster_scorecards] == [0, 0, 0, 0]
    assert [row.freshness for row in review.cluster_scorecards] == [
        "fresh",
        "fresh",
        "fresh",
        "fresh",
    ]
    assert all(row.prior_weight == pytest.approx(0.25) for row in review.cluster_scorecards)
    assert all(row.effective_weight == pytest.approx(0.25) for row in review.cluster_scorecards)
    assert review.review_summary == {
        "generated_at": "2026-04-23T22:15:00+00:00",
        "review_state": "warmup",
        "drift_callouts": [],
        "top_upweighted": [],
        "top_downweighted": [],
    }
    assert review.metadata == {
        "weighting_half_life_days": 20,
        "trailing_window_trading_days": 60,
        "freshness_factors": {
            "fresh": 1.0,
            "stale": 0.5,
            "missing": 0.0,
            "unknown": 0.25,
        },
        "supported_windows": [1, 3, 7, 14],
    }



def test_resolve_and_persist_review_computes_live_weights_and_summary() -> None:
    repo = _FakeRepo(
        samples=[
            *[
                _sample(
                    call_id=f"macro-{idx}",
                    cluster_keys=["macro_calendar"],
                    direction_hit=True,
                    move_abs_error_pct=0.1,
                    brier_score=0.01,
                )
                for idx in range(24)
            ],
            *[
                _sample(
                    call_id=f"options-{idx}",
                    cluster_keys=["options_positioning"],
                    direction_hit=True,
                    move_abs_error_pct=0.5,
                    brier_score=0.10,
                )
                for idx in range(24)
            ],
            *[
                _sample(
                    call_id=f"regime-{idx}",
                    cluster_keys=["market_regime"],
                    direction_hit=bool(idx % 2),
                    move_abs_error_pct=1.0,
                    brier_score=0.25,
                )
                for idx in range(24)
            ],
            *[
                _sample(
                    call_id=f"sentiment-{idx}",
                    cluster_keys=["sentiment"],
                    direction_hit=False,
                    move_abs_error_pct=4.0,
                    brier_score=1.0,
                )
                for idx in range(24)
            ],
        ]
    )
    service = MarketPredictionClusterWeightingService(repository=repo)
    as_of_ts = datetime(2026, 4, 23, 22, 15, tzinfo=UTC)

    review = service.resolve_and_persist_review(
        window_days=3,
        as_of_ts=as_of_ts,
        source_snapshot=_source_snapshot(),
    )

    assert repo.sample_queries == [(3, date(2026, 4, 23))]
    assert review.id == "cluster-review:3:2026-04-23T22:15:00+00:00"
    assert review.review_state == "live"
    scorecards = {row.cluster: row for row in review.cluster_scorecards}
    assert scorecards["macro_calendar"].effective_weight == pytest.approx(0.3263577312)
    assert scorecards["options_positioning"].effective_weight == pytest.approx(0.3056987879)
    assert scorecards["market_regime"].effective_weight == pytest.approx(0.2486104601)
    assert scorecards["sentiment"].effective_weight == pytest.approx(0.1193330208)
    assert scorecards["macro_calendar"].recommended_action == "upweight"
    assert scorecards["sentiment"].recommended_action == "downweight"
    assert scorecards["market_regime"].recommended_action == "hold"
    assert scorecards["options_positioning"].recommended_action == "upweight"
    assert review.review_summary["top_upweighted"] == [
        {
            "kind": "cluster",
            "key": "options_positioning",
            "prior_weight": pytest.approx(0.25),
            "effective_weight": pytest.approx(0.3056987879),
        },
        {
            "kind": "cluster",
            "key": "macro_calendar",
            "prior_weight": pytest.approx(0.25),
            "effective_weight": pytest.approx(0.3263577312),
        },
    ]
    assert review.review_summary["top_downweighted"] == [
        {
            "kind": "cluster",
            "key": "sentiment",
            "prior_weight": pytest.approx(0.25),
            "effective_weight": pytest.approx(0.1193330208),
        }
    ]
    assert repo.persisted[0] == review



def test_get_review_ignores_malformed_latest_row_and_falls_back_to_next_valid_review() -> None:
    latest_rows = [
        {
            "id": "cluster-review:3:2026-04-24T22:15:00+00:00",
            "generated_at": datetime(2026, 4, 24, 22, 15, tzinfo=UTC),
            "as_of_ts": datetime(2026, 4, 24, 22, 15, tzinfo=UTC),
            "window_days": 3,
            "review_state": "degraded",
            "cluster_scorecards": {"bad": True},
            "review_summary": [],
            "metadata": {},
        },
        MarketPredictionClusterReview(
            id="cluster-review:3:2026-04-23T22:15:00+00:00",
            generated_at=datetime(2026, 4, 23, 22, 15, tzinfo=UTC),
            as_of_ts=datetime(2026, 4, 23, 22, 15, tzinfo=UTC),
            window_days=3,
            review_state="live",
            cluster_scorecards=[
                {
                    "cluster": "market_regime",
                    "prior_weight": 0.25,
                    "effective_weight": 0.24,
                    "sample_size": 24,
                    "direction_hit_rate": 0.5,
                    "move_mae_pct": 1.0,
                    "brier_score": 0.25,
                    "skill_score": 0.625,
                    "freshness": "fresh",
                    "recommended_action": "hold",
                },
                {
                    "cluster": "sentiment",
                    "prior_weight": 0.25,
                    "effective_weight": 0.12,
                    "sample_size": 24,
                    "direction_hit_rate": 0.0,
                    "move_mae_pct": 4.0,
                    "brier_score": 1.0,
                    "skill_score": 0.04,
                    "freshness": "fresh",
                    "recommended_action": "downweight",
                },
                {
                    "cluster": "options_positioning",
                    "prior_weight": 0.25,
                    "effective_weight": 0.31,
                    "sample_size": 24,
                    "direction_hit_rate": 1.0,
                    "move_mae_pct": 0.5,
                    "brier_score": 0.1,
                    "skill_score": 0.8833333333,
                    "freshness": "fresh",
                    "recommended_action": "upweight",
                },
                {
                    "cluster": "macro_calendar",
                    "prior_weight": 0.25,
                    "effective_weight": 0.33,
                    "sample_size": 24,
                    "direction_hit_rate": 1.0,
                    "move_mae_pct": 0.1,
                    "brier_score": 0.01,
                    "skill_score": 0.9768181818,
                    "freshness": "fresh",
                    "recommended_action": "upweight",
                },
            ],
            review_summary={
                "generated_at": "2026-04-23T22:15:00+00:00",
                "review_state": "live",
                "drift_callouts": ["sentiment downweighted from 0.2500 to 0.1200"],
                "top_upweighted": [
                    {
                        "kind": "cluster",
                        "key": "macro_calendar",
                        "prior_weight": 0.25,
                        "effective_weight": 0.33,
                    }
                ],
                "top_downweighted": [
                    {
                        "kind": "cluster",
                        "key": "sentiment",
                        "prior_weight": 0.25,
                        "effective_weight": 0.12,
                    }
                ],
            },
            metadata={
                "weighting_half_life_days": 20,
                "trailing_window_trading_days": 60,
                "freshness_factors": {
                    "fresh": 1.0,
                    "stale": 0.5,
                    "missing": 0.0,
                    "unknown": 0.25,
                },
                "supported_windows": [1, 3, 7, 14],
            },
        ),
    ]
    service = MarketPredictionClusterWeightingService(repository=_FakeRepo(latest_rows=latest_rows))

    review = service.get_review(
        window_days=3,
        as_of_ts=datetime(2026, 4, 24, 22, 15, tzinfo=UTC),
        source_snapshot=_source_snapshot(),
    )

    assert review.as_of_ts == datetime(2026, 4, 23, 22, 15, tzinfo=UTC)
    assert review.review_state == "live"
    assert [row.cluster for row in review.cluster_scorecards] == [
        "market_regime",
        "sentiment",
        "options_positioning",
        "macro_calendar",
    ]
    assert review.review_summary["top_downweighted"][0] == {
        "kind": "cluster",
        "key": "sentiment",
        "prior_weight": 0.25,
        "effective_weight": 0.12,
    }



def test_resolve_and_persist_review_returns_priors_only_degraded_when_persist_fails() -> None:
    repo = _FakeRepo(samples=[])
    repo.raise_on_persist = True
    service = MarketPredictionClusterWeightingService(repository=repo)

    review = service.resolve_and_persist_review(
        window_days=3,
        as_of_ts=datetime(2026, 4, 23, 22, 15, tzinfo=UTC),
        source_snapshot=_source_snapshot(),
    )

    assert review.review_state == "degraded"
    assert all(row.effective_weight == pytest.approx(0.25) for row in review.cluster_scorecards)
    assert review.metadata["_persisted"] is False
