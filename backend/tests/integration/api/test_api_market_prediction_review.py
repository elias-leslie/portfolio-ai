"""Integration tests for the market prediction review API endpoint."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.cache import clear_cache
from app.models.market_prediction import MarketPredictionSeatReviewResponse


@pytest.fixture(autouse=True)
def clear_response_cache() -> None:
    clear_cache()


@pytest.fixture
def client() -> Generator[TestClient]:
    import importlib

    prediction_mod = importlib.import_module("app.api.market.prediction_router")
    prediction_mod._state.clear()

    yield TestClient(app)

    prediction_mod._state.clear()


class _FakeReviewService:
    def get_review(self, *, window_days: int, as_of_ts=None) -> MarketPredictionSeatReviewResponse:
        return MarketPredictionSeatReviewResponse(
            as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
            window_days=window_days,
            review_state="warmup",
            seat_scorecards=[
                {
                    "seat_key": "cross_asset",
                    "prior_weight": 1 / 3,
                    "effective_weight": 1 / 3,
                    "sample_size": 0,
                    "direction_hit_rate": None,
                    "move_mae_pct": None,
                    "brier_score": None,
                    "skill_score": None,
                    "recommended_action": "hold",
                },
                {
                    "seat_key": "macro",
                    "prior_weight": 1 / 3,
                    "effective_weight": 1 / 3,
                    "sample_size": 0,
                    "direction_hit_rate": None,
                    "move_mae_pct": None,
                    "brier_score": None,
                    "skill_score": None,
                    "recommended_action": "hold",
                },
                {
                    "seat_key": "risk",
                    "prior_weight": 1 / 3,
                    "effective_weight": 1 / 3,
                    "sample_size": 0,
                    "direction_hit_rate": None,
                    "move_mae_pct": None,
                    "brier_score": None,
                    "skill_score": None,
                    "recommended_action": "hold",
                },
            ],
            review_summary={
                "generated_at": "2026-04-21T22:15:00+00:00",
                "review_state": "warmup",
                "drift_callouts": [],
                "top_upweighted": [],
                "top_downweighted": [],
            },
        )



def _fake_review_service() -> _FakeReviewService:
    return _FakeReviewService()



def test_get_prediction_review_returns_supported_horizon_payload(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.market.prediction_router._get_review_service",
        _fake_review_service,
    )

    response = client.get("/api/market/prediction/review?window_days=3")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "as_of_ts": "2026-04-21T22:15:00Z",
        "window_days": 3,
        "review_state": "warmup",
        "seat_scorecards": [
            {
                "seat_key": "cross_asset",
                "prior_weight": pytest.approx(1 / 3),
                "effective_weight": pytest.approx(1 / 3),
                "sample_size": 0,
                "direction_hit_rate": None,
                "move_mae_pct": None,
                "brier_score": None,
                "skill_score": None,
                "recommended_action": "hold",
            },
            {
                "seat_key": "macro",
                "prior_weight": pytest.approx(1 / 3),
                "effective_weight": pytest.approx(1 / 3),
                "sample_size": 0,
                "direction_hit_rate": None,
                "move_mae_pct": None,
                "brier_score": None,
                "skill_score": None,
                "recommended_action": "hold",
            },
            {
                "seat_key": "risk",
                "prior_weight": pytest.approx(1 / 3),
                "effective_weight": pytest.approx(1 / 3),
                "sample_size": 0,
                "direction_hit_rate": None,
                "move_mae_pct": None,
                "brier_score": None,
                "skill_score": None,
                "recommended_action": "hold",
            },
        ],
        "review_summary": {
            "generated_at": "2026-04-21T22:15:00+00:00",
            "review_state": "warmup",
            "drift_callouts": [],
            "top_upweighted": [],
            "top_downweighted": [],
        },
    }



def test_get_prediction_review_rejects_unsupported_window(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.market.prediction_router._get_review_service",
        _fake_review_service,
    )

    response = client.get("/api/market/prediction/review?window_days=2")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported window_days=2. Supported values: 1, 3, 7, 14"
