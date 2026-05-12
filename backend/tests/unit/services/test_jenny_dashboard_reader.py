"""Unit tests for Jenny dashboard reader helpers."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock, Mock

from app.models.jenny import JennyAgentEvaluation
from app.services.jenny_dashboard_reader import JennyDashboardReader
from app.services.jenny_operator_service import JennyOperatorService


def _service() -> JennyOperatorService:
    return JennyOperatorService()


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


