from __future__ import annotations

from datetime import UTC, datetime

from app.workflows.market_prediction import run_market_prediction_cycle


class _FakeCommitteeService:
    def __init__(self) -> None:
        self.generated: list[tuple[int, str]] = []

    def generate_snapshot(self, *, window_days: int, as_of_ts: datetime | None = None, review=None):
        self.generated.append((window_days, review["id"]))
        return {"window_days": window_days, "as_of_ts": as_of_ts, "review": review}


class _FakeEvaluationService:
    def __init__(self) -> None:
        self.calls = 0
        self.backfilled: list[int] = []

    def evaluate_due_predictions(self, *, as_of_date=None, limit: int = 200):
        self.calls += 1
        return ["evaluated"]

    def backfill_vote_evaluations(self, *, window_days: int, as_of_ts: datetime):
        self.backfilled.append(window_days)
        return [f"vote-eval-{window_days}"]


class _FakeSeatWeightingService:
    def __init__(self) -> None:
        self.resolved: list[int] = []

    def resolve_and_persist_review(self, *, window_days: int, as_of_ts: datetime):
        self.resolved.append(window_days)
        return {
            "id": f"seat-review:{window_days}:{as_of_ts.isoformat()}",
            "window_days": window_days,
            "review_state": "warmup",
        }



def test_run_market_prediction_cycle_evaluates_then_backfills_reviews_and_generates_all_supported_windows() -> None:
    committee = _FakeCommitteeService()
    evaluation = _FakeEvaluationService()
    seat_weighting = _FakeSeatWeightingService()

    result = run_market_prediction_cycle(
        committee_service=committee,
        evaluation_service=evaluation,
        seat_weighting_service=seat_weighting,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
    )

    assert evaluation.calls == 1
    assert evaluation.backfilled == [1, 3, 7, 14]
    assert seat_weighting.resolved == [1, 3, 7, 14]
    assert committee.generated == [
        (1, "seat-review:1:2026-04-21T22:15:00+00:00"),
        (3, "seat-review:3:2026-04-21T22:15:00+00:00"),
        (7, "seat-review:7:2026-04-21T22:15:00+00:00"),
        (14, "seat-review:14:2026-04-21T22:15:00+00:00"),
    ]
    assert result["generated_windows"] == [1, 3, 7, 14]
    assert result["evaluations_completed"] == 1
