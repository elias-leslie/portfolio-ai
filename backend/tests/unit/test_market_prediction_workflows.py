from __future__ import annotations

from datetime import UTC, datetime

from app.workflows.market_prediction import run_market_prediction_cycle


class _FakeCommitteeService:
    def __init__(self) -> None:
        self.generated: list[tuple[int, str, str, str]] = []
        self.built_snapshots: list[str] = []

    def build_source_snapshot(self, as_of_ts: datetime) -> dict[str, object]:
        self.built_snapshots.append(as_of_ts.isoformat())
        return {
            "clusters": {
                "market_regime": {"freshness": "fresh"},
                "sentiment": {"freshness": "fresh"},
                "options_positioning": {"freshness": "fresh"},
                "macro_calendar": {"freshness": "fresh"},
            }
        }

    def generate_snapshot(
        self,
        *,
        window_days: int,
        as_of_ts: datetime | None = None,
        review=None,
        cluster_review=None,
        source_snapshot=None,
    ):
        self.generated.append((window_days, review["id"], cluster_review["id"], source_snapshot["clusters"]["macro_calendar"]["freshness"]))
        return {
            "window_days": window_days,
            "as_of_ts": as_of_ts,
            "review": review,
            "cluster_review": cluster_review,
            "source_snapshot": source_snapshot,
        }


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


class _FakeClusterWeightingService:
    def __init__(self) -> None:
        self.resolved: list[tuple[int, str]] = []

    def resolve_and_persist_review(self, *, window_days: int, as_of_ts: datetime, source_snapshot):
        self.resolved.append((window_days, source_snapshot["clusters"]["macro_calendar"]["freshness"]))
        return {
            "id": f"cluster-review:{window_days}:{as_of_ts.isoformat()}",
            "window_days": window_days,
            "review_state": "warmup",
        }



def test_run_market_prediction_cycle_evaluates_then_backfills_reviews_and_generates_all_supported_windows() -> None:
    committee = _FakeCommitteeService()
    evaluation = _FakeEvaluationService()
    seat_weighting = _FakeSeatWeightingService()
    cluster_weighting = _FakeClusterWeightingService()

    result = run_market_prediction_cycle(
        committee_service=committee,
        evaluation_service=evaluation,
        seat_weighting_service=seat_weighting,
        cluster_weighting_service=cluster_weighting,
        macro_calendar_ingestion_fn=lambda **_: {"status": "success", "events_updated": 2},
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
    )

    assert evaluation.calls == 1
    assert evaluation.backfilled == [1, 3, 7, 14]
    assert seat_weighting.resolved == [1, 3, 7, 14]
    assert cluster_weighting.resolved == [
        (1, "fresh"),
        (3, "fresh"),
        (7, "fresh"),
        (14, "fresh"),
    ]
    assert committee.generated == [
        (1, "seat-review:1:2026-04-21T22:15:00+00:00", "cluster-review:1:2026-04-21T22:15:00+00:00", "fresh"),
        (3, "seat-review:3:2026-04-21T22:15:00+00:00", "cluster-review:3:2026-04-21T22:15:00+00:00", "fresh"),
        (7, "seat-review:7:2026-04-21T22:15:00+00:00", "cluster-review:7:2026-04-21T22:15:00+00:00", "fresh"),
        (14, "seat-review:14:2026-04-21T22:15:00+00:00", "cluster-review:14:2026-04-21T22:15:00+00:00", "fresh"),
    ]
    assert result["generated_windows"] == [1, 3, 7, 14]
    assert result["evaluations_completed"] == 1
    assert result["macro_calendar_ingestion"] == {"status": "success", "events_updated": 2}
