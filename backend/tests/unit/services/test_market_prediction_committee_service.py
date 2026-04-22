"""Unit tests for the market prediction committee service."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.constants import PREDICTION_TARGET_SYMBOLS
from app.models.market_prediction import (
    CommitteeSeatVote,
    MarketPredictionCall,
    MarketPredictionCommitteeResponse,
    MarketPredictionSeatReview,
)
from app.services.market_prediction_committee_service import MarketPredictionCommitteeService


class _FakeRepo:
    def __init__(self) -> None:
        self.snapshot: MarketPredictionCommitteeResponse | None = None
        self.raise_on_get = False
        self.raise_on_persist = False
        self.runs: list[Any] = []
        self.calls: list[MarketPredictionCall] = []
        self.votes: list[CommitteeSeatVote] = []
        self.history: list[MarketPredictionCall] = []
        self.scorecard: Any = None
        self.last_evaluated_at: datetime | None = None

    def get_latest_committee_snapshot(self, window_days: int) -> MarketPredictionCommitteeResponse | None:
        if self.raise_on_get:
            raise RuntimeError("boom")
        if self.snapshot and self.snapshot.window_days == window_days:
            return self.snapshot
        return None

    def persist_snapshot(
        self,
        *,
        run: Any,
        calls: list[MarketPredictionCall],
        votes: list[CommitteeSeatVote],
    ) -> None:
        if self.raise_on_persist:
            raise RuntimeError("persist failed")
        self.runs.append(run)
        self.calls = list(calls)
        self.votes = list(votes)

    def create_run(self, run: Any) -> None:
        self.runs.append(run)

    def upsert_call(self, run_id: str, call: MarketPredictionCall) -> None:
        self.calls.append(call)

    def replace_votes_for_run(self, run_id: str, votes: list[CommitteeSeatVote]) -> None:
        self.votes = list(votes)

    def list_history(self, symbol: str, window_days: int, limit: int = 30) -> list[MarketPredictionCall]:
        return self.history[:limit]

    def get_scorecard(self, window_days: int) -> Any:
        return self.scorecard

    def get_last_evaluated_at(self, window_days: int) -> datetime | None:
        return self.last_evaluated_at


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


def _call(
    *,
    symbol: str = "SPY",
    window_days: int = 3,
    clusters: Any | None = None,
) -> MarketPredictionCall:
    return MarketPredictionCall.model_construct(
        symbol=symbol,
        window_days=window_days,
        direction_label="neutral",
        prob_up=0.5,
        expected_move_pct=0.0,
        confidence_score=40.0,
        top_source_clusters=[] if clusters is None else clusters,
        metadata={},
    )


def _response(
    *,
    lead_call: Any,
    calls: list[Any],
    source_snapshot: Any = None,
    scorecard: Any = None,
    committee_summary: Any = None,
) -> MarketPredictionCommitteeResponse:
    response = MarketPredictionCommitteeResponse.model_construct(
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        base_date=date(2026, 4, 21),
        target_date=date(2026, 4, 24),
        target_universe=PREDICTION_TARGET_SYMBOLS,
        lead_call=lead_call,
        calls=calls,
        votes=[],
        scorecard=scorecard,
        committee_summary={} if committee_summary is None else committee_summary,
        source_snapshot={} if source_snapshot is None else source_snapshot,
        last_evaluated_at=None,
    )
    response._storage_metadata = {}
    return response


def test_get_committee_snapshot_freezes_truth_contract_baseline(monkeypatch) -> None:
    repo = _FakeRepo()
    repo.snapshot = _response(
        lead_call=_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4}]),
        calls=[_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4}])],
        source_snapshot={"clusters": {" Macro_Calendar ": {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 2, "next_event_date": "2026-04-22"}}},
        committee_summary={"headline": "Constructive risk appetite"},
    )
    service = MarketPredictionCommitteeService(repository=repo)

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 2,
            "next_event_date": "2026-04-22",
        },
    )

    result = service.get_committee_snapshot(window_days=3)

    assert result is not None
    assert result.source_snapshot["clusters"]["Macro_Calendar"] == {
        "freshness": "fresh",
        "reason": "ok",
        "upcoming_event_count": 2,
        "next_event_date": "2026-04-22",
    }
    assert result.committee_summary["truth_state"] == "pending_target"
    assert [cluster.cluster for cluster in result.lead_call.top_source_clusters] == ["market_regime"]



def test_get_committee_snapshot_defaults_additive_review_fields_for_legacy_rows(monkeypatch) -> None:
    repo = _FakeRepo()
    snapshot = _response(
        lead_call=_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4}]),
        calls=[_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4}])],
        source_snapshot={"clusters": {"macro_calendar": {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 1, "next_event_date": "2026-04-22"}}},
        committee_summary={"headline": "Legacy snapshot"},
    )
    snapshot._storage_metadata = {"committee_execution_path": "committee_endpoint", "executed_seats": []}
    repo.snapshot = snapshot
    service = MarketPredictionCommitteeService(repository=repo)

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 1,
            "next_event_date": "2026-04-22",
        },
    )

    result = service.get_committee_snapshot(window_days=3)

    assert result is not None
    assert result.committee_summary["resolved_seat_weights"] == []
    assert result.committee_summary["review_state"] is None
    assert result.committee_summary["review_as_of_ts"] is None
    assert result.committee_summary["review_row_id"] is None



def test_generate_snapshot_uses_weighted_committee_synthesis_and_additive_review_metadata(monkeypatch) -> None:
    repo = _FakeRepo()
    raw_payload = {
        "_portfolio_execution_path": "committee_endpoint",
        "calls": [],
        "votes": [
            {
                "seat_key": "macro",
                "agent_slug": "macro-analyst",
                "symbol": "SPY",
                "prob_up": 0.8,
                "expected_move_pct": 2.0,
                "confidence_score": 80,
                "source_clusters": [{"cluster": "macro_calendar", "weight": 0.6}],
            },
            {
                "seat_key": "risk",
                "agent_slug": "risk-manager",
                "symbol": "SPY",
                "prob_up": 0.4,
                "expected_move_pct": -1.0,
                "confidence_score": None,
                "source_clusters": [{"cluster": "market_regime", "weight": 0.4}],
            },
            {
                "seat_key": "new-seat",
                "agent_slug": "ignored-seat",
                "symbol": "SPY",
                "prob_up": 0.95,
                "expected_move_pct": 4.0,
                "confidence_score": 99,
                "source_clusters": [{"cluster": "market_regime", "weight": 0.9}],
            },
        ],
    }
    fake_client = _FakeRoundtableClient(raw_payload)
    review = MarketPredictionSeatReview(
        id="seat-review:3:2026-04-21T22:15:00+00:00",
        generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        review_state="live",
        seat_scorecards=[
            {
                "seat_key": "cross_asset",
                "prior_weight": 1 / 3,
                "effective_weight": 0.2,
                "sample_size": 6,
                "direction_hit_rate": 0.5,
                "move_mae_pct": 1.0,
                "brier_score": 0.2,
                "skill_score": 0.6,
                "recommended_action": "downweight",
            },
            {
                "seat_key": "macro",
                "prior_weight": 1 / 3,
                "effective_weight": 0.5,
                "sample_size": 12,
                "direction_hit_rate": 0.7,
                "move_mae_pct": 0.6,
                "brier_score": 0.12,
                "skill_score": 0.82,
                "recommended_action": "upweight",
            },
            {
                "seat_key": "risk",
                "prior_weight": 1 / 3,
                "effective_weight": 0.3,
                "sample_size": 10,
                "direction_hit_rate": 0.4,
                "move_mae_pct": 2.1,
                "brier_score": 0.35,
                "skill_score": 0.41,
                "recommended_action": "hold",
            },
        ],
        review_summary={
            "generated_at": "2026-04-21T22:15:00+00:00",
            "review_state": "live",
            "drift_callouts": ["macro gained weight versus prior"],
            "top_upweighted": [{"kind": "seat", "key": "macro", "prior_weight": 1 / 3, "effective_weight": 0.5}],
            "top_downweighted": [{"kind": "seat", "key": "cross_asset", "prior_weight": 1 / 3, "effective_weight": 0.2}],
        },
        metadata={
            "weighting_half_life_days": 20,
            "trailing_window_trading_days": 60,
            "backfill_run_limit": 120,
            "supported_windows": [1, 3, 7, 14],
        },
    )
    service = MarketPredictionCommitteeService(
        repository=repo,
        roundtable_client_factory=lambda **_: fake_client,
    )

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        service,
        "_build_source_snapshot",
        lambda _: {
            "clusters": {
                "market_regime": {"freshness": "fresh"},
                "macro_calendar": {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 1, "next_event_date": "2026-04-22"},
            }
        },
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 1,
            "next_event_date": "2026-04-22",
        },
    )

    result = service.generate_snapshot(
        window_days=3,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        review=review,
    )

    assert repo.calls[0].prob_up == pytest.approx(0.6713692625)
    assert repo.calls[0].expected_move_pct == pytest.approx(0.875)
    assert repo.calls[0].confidence_score == pytest.approx(68.75)
    assert repo.calls[0].confidence_band_low_pct == pytest.approx(-1.0)
    assert repo.calls[0].confidence_band_high_pct == pytest.approx(2.0)
    assert repo.calls[0].committee_disagreement_score == pytest.approx(0.4)
    assert repo.calls[0].metadata["aggregation_mode"] == "weighted_committee"
    assert repo.calls[0].metadata["active_seat_keys"] == ["macro", "risk"]
    assert result.committee_summary["resolved_seat_weights"] == [
        {"seat_key": "cross_asset", "prior_weight": pytest.approx(1 / 3), "effective_weight": 0.2, "sample_size": 6, "skill_score": 0.6},
        {"seat_key": "macro", "prior_weight": pytest.approx(1 / 3), "effective_weight": 0.5, "sample_size": 12, "skill_score": 0.82},
        {"seat_key": "risk", "prior_weight": pytest.approx(1 / 3), "effective_weight": 0.3, "sample_size": 10, "skill_score": 0.41},
    ]
    assert result.committee_summary["review_state"] == "live"
    assert result.committee_summary["review_as_of_ts"] == "2026-04-21T22:15:00+00:00"
    assert result.committee_summary["review_row_id"] == "seat-review:3:2026-04-21T22:15:00+00:00"
    assert repo.runs[0].metadata["adaptive_weighting_version"] == "seat-v1"
    assert repo.runs[0].metadata["review_state"] == "live"
    assert repo.runs[0].metadata["review_row_id"] == "seat-review:3:2026-04-21T22:15:00+00:00"



def test_generate_snapshot_persists_root_provenance_and_generation_time_fallbacks(monkeypatch) -> None:
    repo = _FakeRepo()
    raw_payload = {
        "_portfolio_execution_path": "committee_endpoint",
        "calls": [
            {
                "symbol": "SPY",
                "prob_up": 0.62,
                "expected_move_pct": 1.4,
                "confidence_score": 78,
                "top_source_clusters": [],
            }
        ],
        "votes": [
            {
                "seat_key": " Macro ",
                "agent_slug": "market-pulse-analyst",
                "model_id": "gpt-5.4",
                "provider": "codex",
                "symbol": "SPY",
                "prob_up": 0.64,
                "expected_move_pct": 1.6,
                "confidence_score": 81,
                "source_clusters": [],
            }
        ],
    }
    fake_client = _FakeRoundtableClient(raw_payload)
    service = MarketPredictionCommitteeService(
        repository=repo,
        roundtable_client_factory=lambda **_: fake_client,
    )

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        service,
        "_build_source_snapshot",
        lambda _: {
            "clusters": {
                "market_regime": {"freshness": "fresh"},
                "sentiment": {"freshness": "fresh"},
                "macro_calendar": {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 2, "next_event_date": "2026-04-22"},
            }
        },
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 2,
            "next_event_date": "2026-04-22",
        },
    )

    result = service.generate_snapshot(
        window_days=3,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
    )

    assert fake_client.closed is True
    assert repo.runs[0].metadata["committee_execution_path"] == "committee_endpoint"
    assert repo.runs[0].metadata["committee_roster_mode"] == "custom_roster"
    assert repo.runs[0].metadata["executed_seats"] == [
        {
            "seat_key": "macro",
            "agent_slug": "market-pulse-analyst",
            "model_id": "gpt-5.4",
            "provider": "codex",
        }
    ]
    assert len(repo.runs[0].metadata["committee_fingerprint"]) == 64
    assert repo.votes[0].source_clusters[0].cluster == "macro_calendar"
    assert repo.calls[0].top_source_clusters[0].cluster == "macro_calendar"
    assert result.committee_summary["committee_execution_path"] == "committee_endpoint"
    assert result.committee_summary["executed_seat_keys"] == ["macro"]
    assert result.committee_summary["truth_state"] == "pending_target"
    assert result.committee_summary["scorecard_status_note"]
    assert "_portfolio_execution_path" not in result.committee_summary


def test_macro_helper_failure_defaults_macro_contract_without_fetch_error(monkeypatch) -> None:
    repo = _FakeRepo()
    repo.snapshot = _response(
        lead_call=_call(clusters=[{"cluster": "market_regime", "weight": 0.4}]),
        calls=[_call(clusters=[{"cluster": "market_regime", "weight": 0.4}])],
        source_snapshot={"clusters": {"macro_calendar": {"legacy_flag": True}}},
    )
    service = MarketPredictionCommitteeService(repository=repo)

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: (_ for _ in ()).throw(RuntimeError("macro helper failed")),
    )

    result = service.get_committee_snapshot(window_days=3)

    assert result is not None
    assert result.committee_summary["truth_state"] == "pending_target"
    assert result.source_snapshot["clusters"]["macro_calendar"] == {
        "legacy_flag": True,
        "freshness": "missing",
        "reason": "no_future_rows",
        "upcoming_event_count": 0,
        "next_event_date": None,
    }


def test_get_committee_snapshot_returns_degraded_fetch_error_when_repository_read_fails(monkeypatch) -> None:
    repo = _FakeRepo()
    repo.raise_on_get = True
    service = MarketPredictionCommitteeService(repository=repo)

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "missing",
            "reason": "no_future_rows",
            "upcoming_event_count": 0,
            "next_event_date": None,
        },
    )

    result = service.get_committee_snapshot(window_days=3, generate_if_missing=False)

    assert result is not None
    assert result.lead_call.symbol == "SPY"
    assert result.lead_call.direction_label == "neutral"
    assert result.votes == []
    assert result.calls[0].top_source_clusters == []
    assert result.committee_summary == {
        "committee_roster_mode": None,
        "committee_execution_path": "fallback_completion",
        "executed_seat_keys": [],
        "truth_state": "fetch_error",
        "scorecard_status_note": "Committee snapshot unavailable; serving degraded fallback.",
    }
    assert result.source_snapshot["clusters"]["macro_calendar"]["reason"] == "no_future_rows"
    assert repo.runs == []


def test_normalizer_uses_spy_call_when_top_level_lead_call_lacks_valid_clusters(monkeypatch) -> None:
    repo = _FakeRepo()
    repo.snapshot = _response(
        lead_call=_call(symbol="XLK", clusters=[]),
        calls=[
            _call(symbol="SPY", clusters=[{"cluster": "macro_calendar", "weight": 0.4}]),
            _call(symbol="XLK", clusters=[]),
        ],
    )
    service = MarketPredictionCommitteeService(repository=repo)

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 1,
            "next_event_date": "2026-04-22",
        },
    )

    result = service.get_committee_snapshot(window_days=3)

    assert result is not None
    assert result.lead_call.symbol == "SPY"
    assert result.committee_summary["truth_state"] == "pending_target"


def test_normalizer_marks_legacy_sparse_and_nulls_invalid_scorecard(monkeypatch) -> None:
    repo = _FakeRepo()
    snapshot = _response(
        lead_call=_call(clusters=[]),
        calls=[_call(clusters=[]), _call(symbol="XLK", clusters=[])],
        scorecard={"sample_size": "bad"},
        source_snapshot={"clusters": {"macro_calendar": []}},
    )
    snapshot._storage_metadata = {"committee_execution_path": "committee_endpoint", "executed_seats": []}
    repo.snapshot = snapshot
    service = MarketPredictionCommitteeService(repository=repo)

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 1,
            "next_event_date": "2026-04-22",
        },
    )

    result = service.get_committee_snapshot(window_days=3)

    assert result is not None
    assert result.scorecard is None
    assert result.committee_summary["committee_execution_path"] == "committee_endpoint"
    assert result.committee_summary["truth_state"] == "legacy_sparse"
    assert result.committee_summary["scorecard_status_note"] == "Legacy sparse data: selected lead attribution unavailable."


def test_generate_snapshot_returns_degraded_fetch_error_without_persisting_rows_when_atomic_persist_fails(monkeypatch) -> None:
    repo = _FakeRepo()
    repo.raise_on_persist = True
    raw_payload = {
        "_portfolio_execution_path": "committee_endpoint",
        "calls": [
            {
                "symbol": "SPY",
                "prob_up": 0.6,
                "expected_move_pct": 1.0,
                "top_source_clusters": [{"cluster": "market_regime", "weight": 0.4}],
            }
        ],
        "votes": [],
    }
    fake_client = _FakeRoundtableClient(raw_payload)
    service = MarketPredictionCommitteeService(
        repository=repo,
        roundtable_client_factory=lambda **_: fake_client,
    )

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        service,
        "_build_source_snapshot",
        lambda _: {"clusters": {"macro_calendar": {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 1, "next_event_date": "2026-04-22"}}},
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "missing",
            "reason": "no_future_rows",
            "upcoming_event_count": 0,
            "next_event_date": None,
        },
    )

    result = service.generate_snapshot(
        window_days=3,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
    )

    assert result.committee_summary["truth_state"] == "fetch_error"
    assert repo.runs == []
    assert repo.calls == []
    assert repo.votes == []


def test_generate_snapshot_falls_back_to_committee_config_seats_when_votes_all_drop(monkeypatch) -> None:
    repo = _FakeRepo()
    raw_payload = {
        "_portfolio_execution_path": "fallback_completion",
        "calls": [
            {
                "symbol": "SPY",
                "prob_up": 0.51,
                "expected_move_pct": 0.2,
                "top_source_clusters": [{"cluster": "market_regime", "weight": 0.3}],
            }
        ],
        "votes": [{"seat_key": " ", "symbol": "SPY"}],
        "committee_config": {
            "seats": [
                {"seat_key": " Macro ", "agent_slug": "market-pulse-analyst", "model_id": "gpt-5.4", "provider": "codex"},
                {"seat_key": "macro", "agent_slug": "ignored", "model_id": "ignored", "provider": "ignored"},
                {"seat_key": "risk", "agent_slug": "risk-manager", "model_id": "claude-opus-4-7", "provider": "anthropic"},
                {"seat_key": "", "agent_slug": "drop-me"},
                "bad-row",
            ]
        },
    }
    fake_client = _FakeRoundtableClient(raw_payload)
    service = MarketPredictionCommitteeService(
        repository=repo,
        roundtable_client_factory=lambda **_: fake_client,
    )

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        service,
        "_build_source_snapshot",
        lambda _: {"clusters": {"market_regime": {"freshness": "fresh"}, "macro_calendar": {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 1, "next_event_date": "2026-04-22"}}},
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 1,
            "next_event_date": "2026-04-22",
        },
    )

    result = service.generate_snapshot(
        window_days=3,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
    )

    assert repo.runs[0].metadata["executed_seats"] == [
        {
            "seat_key": "macro",
            "agent_slug": "market-pulse-analyst",
            "model_id": "gpt-5.4",
            "provider": "codex",
        },
        {
            "seat_key": "risk",
            "agent_slug": "risk-manager",
            "model_id": "claude-opus-4-7",
            "provider": "anthropic",
        },
    ]
    assert result.committee_summary["committee_execution_path"] == "fallback_completion"
    assert result.committee_summary["executed_seat_keys"] == ["macro", "risk"]


def test_generate_snapshot_keeps_macro_contract_invariant_across_window_days(monkeypatch) -> None:
    payload = {
        "_portfolio_execution_path": "committee_endpoint",
        "calls": [
            {
                "symbol": "SPY",
                "prob_up": 0.55,
                "expected_move_pct": 0.4,
                "top_source_clusters": [{"cluster": "market_regime", "weight": 0.3}],
            }
        ],
        "votes": [],
    }
    service = MarketPredictionCommitteeService(
        repository=_FakeRepo(),
        roundtable_client_factory=lambda **_: _FakeRoundtableClient(payload),
    )

    monkeypatch.setattr(
        service,
        "_build_source_snapshot",
        lambda _: {
            "clusters": {
                "macro_calendar": {
                    "freshness": "stale",
                    "reason": "stale_table",
                    "upcoming_event_count": 0,
                    "next_event_date": None,
                }
            }
        },
    )

    one_day = service.generate_snapshot(
        window_days=1,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
    )
    fourteen_day = service.generate_snapshot(
        window_days=14,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
    )

    assert one_day.source_snapshot["clusters"]["macro_calendar"] == fourteen_day.source_snapshot["clusters"]["macro_calendar"]
