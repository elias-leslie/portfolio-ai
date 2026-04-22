"""Integration tests for market prediction API endpoints."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime

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
            committee_summary={
                "headline": "Constructive risk appetite",
                "disagreement_label": "moderate",
                "committee_roster_mode": "default_roster",
                "committee_execution_path": "committee_endpoint",
                "executed_seat_keys": ["cross_asset", "macro", "risk"],
                "truth_state": "live",
                "scorecard_status_note": None,
            },
            source_snapshot={
                "clusters": {
                    "market_regime": {"freshness": "fresh"},
                    "macro_calendar": {
                        "freshness": "fresh",
                        "reason": "ok",
                        "upcoming_event_count": 2,
                        "next_event_date": "2026-04-22",
                    },
                }
            },
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


class _DegradedPredictionService:
    def get_committee_snapshot(self, window_days: int) -> MarketPredictionCommitteeResponse:
        lead_call = MarketPredictionCall(
            symbol="SPY",
            window_days=window_days,
            direction_label="neutral",
            prob_up=0.5,
            expected_move_pct=0.0,
            confidence_score=0.0,
            top_source_clusters=[],
        )
        return MarketPredictionCommitteeResponse(
            as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
            generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
            window_days=window_days,
            base_date=date(2026, 4, 21),
            target_date=date(2026, 4, 24),
            target_universe=PREDICTION_TARGET_SYMBOLS,
            lead_call=lead_call,
            calls=[lead_call],
            votes=[],
            committee_summary={
                "committee_roster_mode": None,
                "committee_execution_path": "fallback_completion",
                "executed_seat_keys": [],
                "truth_state": "fetch_error",
                "scorecard_status_note": "Committee snapshot unavailable; serving degraded fallback.",
            },
            source_snapshot={
                "clusters": {
                    "macro_calendar": {
                        "freshness": "missing",
                        "reason": "no_future_rows",
                        "upcoming_event_count": 0,
                        "next_event_date": None,
                    }
                }
            },
            scorecard=None,
        )

    def get_history(self, symbol: str, window_days: int, limit: int = 30) -> list[MarketPredictionCall]:
        return []


def _fake_prediction_service() -> _FakePredictionService:
    return _FakePredictionService()


def _degraded_prediction_service() -> _DegradedPredictionService:
    return _DegradedPredictionService()


def test_get_prediction_committee_snapshot_serializes_additive_summary_and_macro_contract(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.market.prediction_router._get_prediction_service",
        _fake_prediction_service,
    )

    response = client.get("/api/market/prediction/committee?window_days=3")

    assert response.status_code == 200
    data = response.json()
    assert data["window_days"] == 3
    assert data["lead_call"]["symbol"] == "SPY"
    assert len(data["calls"]) == len(PREDICTION_TARGET_SYMBOLS)
    assert data["committee_summary"]["headline"] == "Constructive risk appetite"
    assert data["committee_summary"]["committee_roster_mode"] == "default_roster"
    assert data["committee_summary"]["committee_execution_path"] == "committee_endpoint"
    assert data["committee_summary"]["executed_seat_keys"] == ["cross_asset", "macro", "risk"]
    assert data["committee_summary"]["truth_state"] == "live"
    assert data["committee_summary"]["scorecard_status_note"] is None
    assert data["source_snapshot"]["clusters"]["macro_calendar"] == {
        "freshness": "fresh",
        "reason": "ok",
        "upcoming_event_count": 2,
        "next_event_date": "2026-04-22",
    }


def test_get_prediction_committee_allows_degraded_fetch_error_200_shape(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.market.prediction_router._get_prediction_service",
        _degraded_prediction_service,
    )

    response = client.get("/api/market/prediction/committee?window_days=3")

    assert response.status_code == 200
    data = response.json()
    assert data["lead_call"]["symbol"] == "SPY"
    assert data["votes"] == []
    assert data["scorecard"] is None
    assert data["committee_summary"]["committee_execution_path"] == "fallback_completion"
    assert data["committee_summary"]["truth_state"] == "fetch_error"
    assert data["source_snapshot"]["clusters"]["macro_calendar"]["reason"] == "no_future_rows"


def test_get_prediction_committee_history(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.market.prediction_router._get_prediction_service",
        _fake_prediction_service,
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
        _fake_prediction_service,
    )

    response = client.get("/api/market/prediction/committee?window_days=2")

    assert response.status_code == 400
    assert "supported" in response.json()["detail"].lower()
