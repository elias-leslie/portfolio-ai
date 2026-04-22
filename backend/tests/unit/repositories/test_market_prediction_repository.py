"""Unit tests for market prediction repository raw read behavior."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.models.market_prediction import (
    CommitteeSeatVote,
    MarketPredictionCall,
    MarketPredictionRun,
)
from app.repositories.market_prediction_repository import MarketPredictionRepository


class _Result:
    def __init__(self, *, one: Any = None, many: list[Any] | None = None) -> None:
        self._one = one
        self._many = many or []

    def fetchone(self) -> Any:
        return self._one

    def fetchall(self) -> list[Any]:
        return list(self._many)


class _Conn:
    def __init__(self, responses: list[_Result]) -> None:
        self._responses = responses

    def execute(self, query: str, params: Any) -> _Result:
        return self._responses.pop(0)


class _Storage:
    def __init__(self, responses: list[_Result]) -> None:
        self._responses = responses

    @contextmanager
    def connection(self):
        yield _Conn(self._responses)


class _WriteConn:
    def __init__(self, *, fail_on_execute: int | None = None) -> None:
        self.fail_on_execute = fail_on_execute
        self.execute_calls = 0
        self.commit_calls = 0

    def execute(self, query: str, params: Any) -> _Result:
        self.execute_calls += 1
        if self.fail_on_execute is not None and self.execute_calls == self.fail_on_execute:
            raise RuntimeError("write failed")
        return _Result()

    def commit(self) -> None:
        self.commit_calls += 1


class _WriteStorage:
    def __init__(self, conn: _WriteConn) -> None:
        self.conn = conn

    @contextmanager
    def connection(self):
        yield self.conn


def test_row_to_call_and_vote_keep_raw_attribution_payloads() -> None:
    repo = MarketPredictionRepository(storage=object())

    call = repo._row_to_call(
        (
            "call-1",
            "SPY",
            3,
            "neutral",
            0.5,
            0.0,
            None,
            None,
            40.0,
            0.0,
            None,
            ["bad-row", {"cluster": "macro_calendar", "weight": 0.4}],
            {"meta": True},
        )
    )
    vote = repo._row_to_vote(
        (
            "macro",
            "market-pulse-analyst",
            "gpt-5.4",
            "codex",
            "SPY",
            3,
            "neutral",
            0.5,
            0.0,
            40.0,
            None,
            [42, {"cluster": "market_regime"}],
            {"meta": True},
        )
    )

    assert call.top_source_clusters == ["bad-row", {"cluster": "macro_calendar", "weight": 0.4}]
    assert vote.source_clusters == [42, {"cluster": "market_regime"}]


def test_get_latest_committee_snapshot_preserves_raw_metadata_for_service_normalization() -> None:
    responses = [
        _Result(
            one=(
                "run-1",
                datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
                datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
                3,
                date(2026, 4, 21),
                date(2026, 4, 24),
                ["SPY"],
                "SPY",
                "neutral",
                0.5,
                0.0,
                {"clusters": {"macro_calendar": []}},
                {},
                "[1, 2, 3]",
            )
        ),
        _Result(many=[]),
        _Result(many=[]),
        _Result(one=(None, None, None, 0)),
        _Result(one=(None,)),
    ]
    repo = MarketPredictionRepository(storage=_Storage(responses))

    result = repo.get_latest_committee_snapshot(3)

    assert result is not None
    assert result._storage_metadata == [1, 2, 3]
    assert result.source_snapshot == {"clusters": {"macro_calendar": []}}


def _run() -> MarketPredictionRun:
    return MarketPredictionRun(
        id="run-1",
        generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        base_date=date(2026, 4, 21),
        target_date=date(2026, 4, 24),
        target_universe=["SPY"],
        lead_symbol="SPY",
        lead_direction="neutral",
        lead_prob_up=0.5,
        lead_expected_move_pct=0.0,
        source_snapshot={"clusters": {}},
        committee_summary={},
        metadata={"committee_execution_path": "committee_endpoint"},
    )


def _call_model() -> MarketPredictionCall:
    return MarketPredictionCall(
        symbol="SPY",
        window_days=3,
        direction_label="neutral",
        prob_up=0.5,
        expected_move_pct=0.0,
        confidence_score=40.0,
        top_source_clusters=[],
        metadata={},
    )


def _vote_model() -> CommitteeSeatVote:
    return CommitteeSeatVote(
        seat_key="macro",
        agent_slug="market-pulse-analyst",
        model_id="gpt-5.4",
        provider="codex",
        symbol="SPY",
        window_days=3,
        direction_label="neutral",
        prob_up=0.5,
        expected_move_pct=0.0,
        confidence_score=40.0,
        source_clusters=[],
        metadata={},
    )


def test_persist_snapshot_commits_once_after_all_writes() -> None:
    conn = _WriteConn()
    repo = MarketPredictionRepository(storage=_WriteStorage(conn))

    repo.persist_snapshot(run=_run(), calls=[_call_model()], votes=[_vote_model()])

    assert conn.execute_calls == 4
    assert conn.commit_calls == 1


def test_persist_snapshot_does_not_commit_when_a_write_fails_midway() -> None:
    conn = _WriteConn(fail_on_execute=3)
    repo = MarketPredictionRepository(storage=_WriteStorage(conn))

    with pytest.raises(RuntimeError, match="write failed"):
        repo.persist_snapshot(run=_run(), calls=[_call_model()], votes=[_vote_model()])

    assert conn.commit_calls == 0
