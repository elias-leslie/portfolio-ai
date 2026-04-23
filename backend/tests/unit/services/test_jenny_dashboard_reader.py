"""Unit tests for Jenny dashboard reader helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, Mock

from pytest_mock import MockerFixture

from app.models.jenny import JennyAgentEvaluation
from app.models.market_prediction import (
    MarketPredictionSeatReview,
)
from app.services.jenny_dashboard_reader import JennyDashboardReader
from app.services.jenny_operator_service import JennyOperatorService


def _service() -> JennyOperatorService:
    return JennyOperatorService()


def _seat_review(
    *,
    review_id: str,
    window_days: int,
    as_of_ts: datetime,
    generated_at: datetime,
    review_state: str,
) -> MarketPredictionSeatReview:
    return MarketPredictionSeatReview.model_construct(
        id=review_id,
        generated_at=generated_at,
        as_of_ts=as_of_ts,
        window_days=window_days,
        review_state=review_state,
        seat_scorecards=[
            {
                "seat_key": "macro",
                "prior_weight": 1 / 3,
                "effective_weight": 0.39,
                "sample_size": 8,
                "direction_hit_rate": 0.7,
                "move_mae_pct": 0.6,
                "brier_score": 0.18,
                "skill_score": 0.74,
                "recommended_action": "upweight",
            }
        ],
        review_summary={
            "generated_at": generated_at.isoformat(),
            "review_state": review_state,
            "drift_callouts": ["macro upweighted from 0.3333 to 0.3900"],
            "top_upweighted": [
                {
                    "kind": "seat",
                    "key": "macro",
                    "prior_weight": 1 / 3,
                    "effective_weight": 0.39,
                }
            ],
            "top_downweighted": [],
        },
        metadata={},
    )


def test_get_latest_symbol_reviews_uses_newest_routine_per_symbol() -> None:
    reader = JennyDashboardReader()
    service = _service()
    service.storage = MagicMock()
    service.thesis_service = Mock()
    service.thesis_service.get_thesis.return_value = None

    rows = [
        (
            "eval-new-1",
            "routine-new",
            "AAPL",
            "equity-analyst",
            None,
            None,
            "review",
            0.6,
            "fresh thesis",
            None,
            [],
            [],
            {},
            None,
            None,
            "2026-03-07T12:00:00+00:00",
        ),
        (
            "eval-new-2",
            "routine-new",
            "AAPL",
            "risk-manager",
            None,
            None,
            "review",
            0.5,
            "fresh risk",
            None,
            [],
            [],
            {},
            None,
            None,
            "2026-03-07T12:00:01+00:00",
        ),
        (
            "eval-old-1",
            "routine-old",
            "AAPL",
            "equity-analyst",
            None,
            None,
            "hold",
            0.9,
            "stale thesis",
            None,
            [],
            [],
            {},
            None,
            None,
            "2026-03-07T11:00:00+00:00",
        ),
        (
            "eval-msft-1",
            "routine-msft",
            "MSFT",
            "equity-analyst",
            None,
            None,
            "buy",
            0.7,
            "msft setup",
            None,
            [],
            [],
            {},
            None,
            None,
            "2026-03-07T12:00:02+00:00",
        ),
    ]
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = rows

    aggregated_inputs: list[tuple[str, list[JennyAgentEvaluation]]] = []

    def capture(
        symbol: str,
        evaluations: list[JennyAgentEvaluation],
        thesis,
    ) -> Mock:
        del thesis
        aggregated_inputs.append((symbol, evaluations))
        return Mock(symbol=symbol)

    cast(Any, service)._aggregate_symbol_review = Mock(side_effect=capture)
    cast(Any, service)._build_position_action_map = Mock(return_value={})
    reviews = reader.get_latest_symbol_reviews(service, limit=8)

    assert len(reviews) == 2
    aapl_evaluations = next(
        evaluations for symbol, evaluations in aggregated_inputs if symbol == "AAPL"
    )
    assert {evaluation.id for evaluation in aapl_evaluations} == {
        "eval-new-1",
        "eval-new-2",
    }
    assert all(evaluation.routine_id == "routine-new" for evaluation in aapl_evaluations)


def test_get_open_notifications_limits_results_to_recent_window() -> None:
    reader = JennyDashboardReader()
    service = _service()
    service.storage = MagicMock()

    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = []

    reader.get_open_notifications(service, limit=12)

    query = connection.execute.call_args.args[0]
    assert "created_at >= NOW() - INTERVAL '7 days'" in query


def test_get_open_notifications_for_symbol_filters_to_symbol() -> None:
    reader = JennyDashboardReader()
    service = _service()
    service.storage = MagicMock()

    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = []

    reader.get_open_notifications_for_symbol(service, "NVDA", limit=3)

    query = connection.execute.call_args.args[0]
    params = connection.execute.call_args.args[1]
    assert "symbol = %s" in query
    assert params == ["NVDA", 3]


def test_get_latest_symbol_review_uses_newest_routine_for_symbol() -> None:
    reader = JennyDashboardReader()
    service = _service()
    service.storage = MagicMock()
    service.thesis_service = Mock()
    service.thesis_service.get_thesis.return_value = None

    rows = [
        (
            "eval-new-1",
            "routine-new",
            "NVDA",
            "equity-analyst",
            None,
            None,
            "review",
            0.6,
            "fresh thesis",
            None,
            [],
            [],
            {},
            None,
            None,
            "2026-03-07T12:00:00+00:00",
        ),
        (
            "eval-new-2",
            "routine-new",
            "NVDA",
            "risk-manager",
            None,
            None,
            "review",
            0.5,
            "fresh risk",
            None,
            [],
            [],
            {},
            None,
            None,
            "2026-03-07T12:00:01+00:00",
        ),
    ]
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = rows

    review = Mock(symbol="NVDA", management_action=None, management_detail=None)
    cast(Any, service)._aggregate_symbol_review = Mock(return_value=review)
    cast(Any, service)._build_position_action_map = Mock(
        return_value={"NVDA": {"action": "trim", "detail": "Cut back size."}}
    )

    result = reader.get_latest_symbol_review(service, "NVDA")

    assert result is review
    cast(Any, service)._aggregate_symbol_review.assert_called_once()
    assert result.management_action == "trim"
    assert result.management_detail == "Cut back size."


def test_get_latest_prediction_review_summary_prefers_newest_persisted_review(
    mocker: MockerFixture,
) -> None:
    older = _seat_review(
        review_id="seat-review:1",
        window_days=1,
        as_of_ts=datetime(2026, 4, 22, 21, 0, tzinfo=UTC),
        generated_at=datetime(2026, 4, 22, 21, 0, tzinfo=UTC),
        review_state="live",
    )
    newer = _seat_review(
        review_id="seat-review:7",
        window_days=7,
        as_of_ts=datetime(2026, 4, 23, 15, 40, tzinfo=UTC),
        generated_at=datetime(2026, 4, 23, 15, 41, tzinfo=UTC),
        review_state="warmup",
    )

    repository = mocker.Mock()
    repository.list_latest_seat_reviews.side_effect = [[older], [], [newer], []]
    mocker.patch(
        "app.services.jenny_dashboard_reader.MarketPredictionRepository",
        return_value=repository,
    )

    reader = JennyDashboardReader()
    summary = reader.get_latest_prediction_review_summary(
        SimpleNamespace(storage=object())
    )

    assert summary is not None
    assert summary.window_days == 7
    assert summary.review_state == "warmup"
    assert summary.generated_at == newer.generated_at.isoformat()
    assert summary.seat_weights[0].seat_key == "macro"
    assert summary.top_upweighted[0].key == "macro"
