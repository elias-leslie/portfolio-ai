"""Integration tests for market prediction API endpoints."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.constants import PREDICTION_TARGET_SYMBOLS
from app.main import app
from app.middleware.cache import clear_cache
from app.models.market_prediction import (
    MarketPredictionCall,
    MarketPredictionCommitteeResponse,
    PredictionSourceCluster,
)


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


class _FakePredictionService:
    def get_committee_snapshot(self, window_days: int) -> MarketPredictionCommitteeResponse:
        calls = [
            MarketPredictionCall(
                symbol=symbol,
                window_days=window_days,
                direction_label="bullish" if symbol in {"SPY", "XLK"} else "neutral",
                prob_up=0.63 if symbol == "SPY" else 0.5,
                expected_move_pct=1.4 if symbol == "SPY" else 0.0,
                confidence_score=76 if symbol == "SPY" else 40,
                rationale_summary=f"Committee read for {symbol}",
                top_source_clusters=[PredictionSourceCluster(cluster="market_regime", weight=0.3)],
            )
            for symbol in PREDICTION_TARGET_SYMBOLS
        ]
        return MarketPredictionCommitteeResponse(
            as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
            generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
            window_days=window_days,
            base_date=date(2026, 4, 21),
            target_date=date(2026, 4, 24),
            target_universe=PREDICTION_TARGET_SYMBOLS,
            lead_call=calls[0],
            calls=calls,
            votes=[],
            committee_summary={"headline": "Constructive risk appetite", "disagreement_label": "moderate"},
            source_snapshot={"clusters": {"market_regime": {"freshness": "fresh"}}},
        )

    def get_history(self, symbol: str, window_days: int, limit: int = 30) -> list[MarketPredictionCall]:
        return [
            MarketPredictionCall(
                id="hist-1",
                symbol=symbol,
                window_days=window_days,
                direction_label="bullish",
                prob_up=0.61,
                expected_move_pct=1.2,
                confidence_score=70,
                rationale_summary="Historical committee call",
            )
        ][:limit]


def test_get_prediction_committee_snapshot(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.market.prediction_router._get_prediction_service",
        lambda: _FakePredictionService(),
    )

    response = client.get("/api/market/prediction/committee?window_days=3")

    assert response.status_code == 200
    data = response.json()
    assert data["window_days"] == 3
    assert data["lead_call"]["symbol"] == "SPY"
    assert len(data["calls"]) == len(PREDICTION_TARGET_SYMBOLS)
    assert data["committee_summary"]["headline"] == "Constructive risk appetite"


def test_get_prediction_committee_history(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.market.prediction_router._get_prediction_service",
        lambda: _FakePredictionService(),
    )

    response = client.get("/api/market/prediction/committee/history?symbol=SPY&window_days=3&limit=5")

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "SPY"
    assert data["window_days"] == 3
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "hist-1"


def test_get_prediction_committee_rejects_unsupported_window(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.market.prediction_router._get_prediction_service",
        lambda: _FakePredictionService(),
    )

    response = client.get("/api/market/prediction/committee?window_days=2")

    assert response.status_code == 400
    assert "supported" in response.json()["detail"].lower()
