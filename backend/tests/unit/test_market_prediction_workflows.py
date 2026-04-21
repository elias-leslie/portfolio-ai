from __future__ import annotations

from datetime import UTC, datetime

from app.workflows.market_prediction import run_market_prediction_cycle


class _FakeCommitteeService:
    def __init__(self) -> None:
        self.generated: list[int] = []

    def generate_snapshot(self, *, window_days: int, as_of_ts: datetime | None = None):
        self.generated.append(window_days)
        return {"window_days": window_days, "as_of_ts": as_of_ts}


class _FakeEvaluationService:
    def __init__(self) -> None:
        self.calls = 0

    def evaluate_due_predictions(self, *, as_of_date=None, limit: int = 200):
        self.calls += 1
        return ["evaluated"]


def test_run_market_prediction_cycle_evaluates_then_generates_all_supported_windows() -> None:
    committee = _FakeCommitteeService()
    evaluation = _FakeEvaluationService()

    result = run_market_prediction_cycle(
        committee_service=committee,
        evaluation_service=evaluation,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
    )

    assert evaluation.calls == 1
    assert committee.generated == [1, 3, 7, 14]
    assert result["generated_windows"] == [1, 3, 7, 14]
    assert result["evaluations_completed"] == 1
