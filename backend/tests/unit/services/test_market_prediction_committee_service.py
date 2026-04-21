"""Unit tests for the market prediction committee service."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import Mock

from app.constants import PREDICTION_TARGET_SYMBOLS
from app.models.market_prediction import (
    CommitteeSeatVote,
    MarketPredictionCall,
    MarketPredictionCommitteeResponse,
)
from app.services.market_prediction_committee_service import MarketPredictionCommitteeService


class _FakeRepo:
    def __init__(self) -> None:
        self.snapshot: MarketPredictionCommitteeResponse | None = None
        self.runs: list[Any] = []
        self.calls: list[MarketPredictionCall] = []
        self.votes: list[CommitteeSeatVote] = []

    def get_latest_committee_snapshot(self, window_days: int) -> MarketPredictionCommitteeResponse | None:
        if self.snapshot and self.snapshot.window_days == window_days:
            return self.snapshot
        return None

    def create_run(self, run: Any) -> None:
        self.runs.append(run)

    def upsert_call(self, run_id: str, call: MarketPredictionCall) -> None:
        self.calls.append(call)

    def replace_votes_for_run(self, run_id: str, votes: list[CommitteeSeatVote]) -> None:
        self.votes = list(votes)

    def get_scorecard(self, window_days: int) -> None:
        return None

    def get_last_evaluated_at(self, window_days: int) -> None:
        return None


class _FakeRoundtableClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.call_kwargs: dict[str, Any] | None = None
        self.closed = False

    def run_committee_roundtable(self, **kwargs: Any) -> dict[str, Any]:
        self.call_kwargs = kwargs
        return self.payload

    def close(self) -> None:
        self.closed = True


def test_get_committee_snapshot_returns_cached_snapshot_without_regenerating() -> None:
    cached_call = MarketPredictionCall(
        symbol="SPY",
        window_days=3,
        direction_label="bullish",
        prob_up=0.61,
        expected_move_pct=1.2,
        confidence_score=74,
    )
    cached_snapshot = MarketPredictionCommitteeResponse(
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        base_date=date(2026, 4, 21),
        target_date=date(2026, 4, 24),
        target_universe=PREDICTION_TARGET_SYMBOLS,
        lead_call=cached_call,
        calls=[cached_call],
        votes=[],
    )
    repo = _FakeRepo()
    repo.snapshot = cached_snapshot
    client_factory = Mock()

    service = MarketPredictionCommitteeService(
        repository=repo,
        roundtable_client_factory=client_factory,
    )

    result = service.get_committee_snapshot(window_days=3)

    assert result == cached_snapshot
    client_factory.assert_not_called()
    assert repo.runs == []


def test_generate_snapshot_persists_full_v1_universe_and_fills_missing_symbols() -> None:
    repo = _FakeRepo()
    raw_payload = {
        "committee_summary": {
            "headline": "Risk appetite is improving but not unanimous.",
            "disagreement_label": "moderate",
        },
        "calls": [
            {
                "symbol": "SPY",
                "prob_up": 0.64,
                "expected_move_pct": 1.8,
                "confidence_score": 78,
                "confidence_band_low_pct": 0.6,
                "confidence_band_high_pct": 2.7,
                "rationale_summary": "Breadth and options positioning both improved.",
                "top_source_clusters": [
                    {"cluster": "market_regime", "weight": 0.35},
                    {"cluster": "options_positioning", "weight": 0.25},
                ],
            },
            {
                "symbol": "XLK",
                "direction_label": "bullish",
                "prob_up": 0.68,
                "expected_move_pct": 2.4,
                "confidence_score": 82,
                "confidence_band_low_pct": 0.8,
                "confidence_band_high_pct": 3.5,
                "rationale_summary": "Semis and software remain the leadership complex.",
                "top_source_clusters": [
                    {"cluster": "sector_rotation", "weight": 0.4},
                ],
            },
        ],
        "votes": [
            {
                "seat_key": "macro",
                "agent_slug": "market-pulse-analyst",
                "model_id": "openai/gpt-5.4",
                "provider": "openai",
                "symbol": "SPY",
                "window_days": 3,
                "direction_label": "bullish",
                "prob_up": 0.66,
                "expected_move_pct": 2.0,
                "confidence_score": 81,
                "rationale_summary": "Rates and breadth are supportive.",
                "source_clusters": [{"cluster": "macro", "weight": 0.4}],
            },
            {
                "seat_key": "macro",
                "agent_slug": "market-pulse-analyst",
                "model_id": "openai/gpt-5.4",
                "provider": "openai",
                "symbol": "XLK",
                "window_days": 3,
                "direction_label": "bullish",
                "prob_up": 0.7,
                "expected_move_pct": 2.7,
                "confidence_score": 83,
                "rationale_summary": "Leadership remains concentrated in tech.",
                "source_clusters": [{"cluster": "sector_rotation", "weight": 0.5}],
            },
        ],
    }
    fake_client = _FakeRoundtableClient(raw_payload)

    service = MarketPredictionCommitteeService(
        repository=repo,
        roundtable_client_factory=lambda **_: fake_client,
    )
    service._build_source_snapshot = Mock(
        return_value={
            "clusters": {
                "market_regime": {"freshness": "fresh"},
                "options_positioning": {"freshness": "fresh"},
            }
        }
    )

    result = service.generate_snapshot(
        window_days=3,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
    )

    assert result.window_days == 3
    assert result.target_universe == PREDICTION_TARGET_SYMBOLS
    assert result.lead_call.symbol == "SPY"
    assert result.lead_call.direction_label == "bullish"
    assert len(result.calls) == len(PREDICTION_TARGET_SYMBOLS)
    assert [call.symbol for call in result.calls] == PREDICTION_TARGET_SYMBOLS
    assert len(repo.calls) == len(PREDICTION_TARGET_SYMBOLS)
    assert repo.runs[0].target_universe == PREDICTION_TARGET_SYMBOLS
    assert fake_client.call_kwargs is not None
    assert fake_client.call_kwargs["window_days"] == 3
    assert "SPY" in fake_client.call_kwargs["source_snapshot_json"]
    assert fake_client.closed is True

    xlu_call = next(call for call in result.calls if call.symbol == "XLU")
    assert xlu_call.direction_label == "neutral"
    assert xlu_call.prob_up == 0.5
    assert xlu_call.expected_move_pct == 0.0
    assert xlu_call.confidence_score == 0.0

    lead_clusters = [cluster.cluster for cluster in result.lead_call.top_source_clusters]
    assert lead_clusters == ["market_regime", "options_positioning"]
