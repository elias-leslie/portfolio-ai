"""Unit tests for Jenny operator service scoring logic."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest

from app.models.jenny import JennyAgentEvaluation, JennyTradeReview
from app.services.jenny_operator_service import JennyOperatorService


def _service() -> JennyOperatorService:
    return object.__new__(JennyOperatorService)


def test_build_scorecard_tracks_win_rate_and_strengths() -> None:
    """Scorecards should summarize wins, returns, and consensus plainly."""
    service = _service()
    evaluations = [
        JennyAgentEvaluation(
            id="eval-1",
            routine_id="routine-1",
            symbol="AAPL",
            agent_name="persona",
            provider="anthropic",
            model="claude-sonnet",
            verdict="buy",
            confidence=0.8,
            rationale="Strong setup",
            recommendation="Watch for breakout",
            strengths=[],
            weaknesses=[],
            thesis_id=None,
            agent_run_id=None,
            created_at="2026-03-07T12:00:00+00:00",
            metadata={},
        ),
        JennyAgentEvaluation(
            id="eval-2",
            routine_id="routine-1",
            symbol="MSFT",
            agent_name="persona",
            provider="anthropic",
            model="claude-sonnet",
            verdict="hold",
            confidence=0.7,
            rationale="Trend intact",
            recommendation="Keep size steady",
            strengths=[],
            weaknesses=[],
            thesis_id=None,
            agent_run_id=None,
            created_at="2026-03-07T12:00:00+00:00",
            metadata={},
        ),
    ]
    reviews_by_symbol = {
        "AAPL": [
            JennyTradeReview(
                id="review-1",
                symbol="AAPL",
                thesis_id=None,
                idea_id="idea-1",
                review_source="paper_trade",
                outcome_label="win",
                return_pct=12.0,
                lesson="Held long enough",
                what_worked=None,
                what_failed=None,
                next_time=None,
                created_at="2026-03-07T12:00:00+00:00",
                updated_at="2026-03-07T12:00:00+00:00",
                agent_consensus={},
                metadata={},
            )
        ],
        "MSFT": [
            JennyTradeReview(
                id="review-2",
                symbol="MSFT",
                thesis_id=None,
                idea_id="idea-2",
                review_source="paper_trade",
                outcome_label="loss",
                return_pct=-3.0,
                lesson="Cut early",
                what_worked=None,
                what_failed=None,
                next_time=None,
                created_at="2026-03-07T12:00:00+00:00",
                updated_at="2026-03-07T12:00:00+00:00",
                agent_consensus={},
                metadata={},
            )
        ],
    }

    scorecard = service._build_scorecard("persona", evaluations, reviews_by_symbol)

    assert scorecard.agent_name == "persona"
    assert scorecard.total_evaluations == 2
    assert scorecard.completed_reviews == 2
    assert scorecard.win_rate == 0.5
    assert scorecard.avg_return_pct == 4.5
    assert scorecard.strengths
    assert scorecard.weaknesses


def test_aggregate_symbol_review_prefers_higher_priority_verdict() -> None:
    """Exit/trim/review should outrank more passive votes when counts tie."""
    service = _service()
    review = service._aggregate_symbol_review(
        "NVDA",
        [
            {
                "agent_name": "analyst",
                "verdict": "hold",
                "confidence": 0.6,
                "rationale": "Trend is fine.",
            },
            {
                "agent_name": "critic",
                "verdict": "review",
                "confidence": 0.7,
                "rationale": "Position is stretched.",
            },
        ],
        thesis=None,
    )

    assert review.final_verdict == "review"
    assert review.average_confidence == pytest.approx(0.65)
    assert review.reasons[0] == "Trend is fine."


def test_create_routine_starts_agent_workflow_and_records_metadata() -> None:
    """Jenny routines should create a real agent workflow for run tracking."""
    service = _service()
    service.storage = MagicMock()
    connection = service.storage.connection.return_value.__enter__.return_value
    service.workflow_orchestrator = Mock()
    service.workflow_orchestrator.start_workflow.return_value = {
        "workflow_id": "workflow-123",
    }

    routine_id, workflow_id = service._create_routine("daily_operator", "manual")

    assert routine_id
    assert workflow_id == "workflow-123"
    service.workflow_orchestrator.start_workflow.assert_called_once()
    inserted_params = connection.execute.call_args.args[1]
    assert inserted_params[-1] == '{"workflow_id": "workflow-123"}'


def test_parse_agent_response_normalizes_qualitative_confidence() -> None:
    """Jenny should accept plain-language confidence labels from finance agents."""
    service = _service()

    parsed = service._parse_agent_response(
        '{"verdict":"buy","confidence":"low","rationale":"Needs more confirmation.","strengths":["Cash flow"],"weaknesses":["Crowded trade"]}',
        "equity-analyst",
    )

    assert parsed["verdict"] == "buy"
    assert parsed["confidence"] == pytest.approx(0.35)
    assert parsed["strengths"] == ["Cash flow"]
    assert parsed["weaknesses"] == ["Crowded trade"]


def test_parse_agent_response_normalizes_percentage_confidence() -> None:
    """Percent-style confidence should be converted into the 0-1 range."""
    service = _service()

    parsed = service._parse_agent_response(
        '{"verdict":"hold","confidence":"70%","rationale":"Trend intact."}',
        "risk-manager",
    )

    assert parsed["confidence"] == pytest.approx(0.7)


def test_parse_agent_response_normalizes_free_form_verdicts() -> None:
    """Free-form finance verdicts should collapse into Jenny's fixed action enum."""
    service = _service()

    buy = service._parse_agent_response(
        '{"verdict":"BUY — small starter position only","confidence":0.7,"rationale":"Constructive but early."}',
        "equity-analyst",
    )
    hold = service._parse_agent_response(
        '{"verdict":"hold — do not add, do not exit","confidence":0.7,"rationale":"Trend intact."}',
        "trade-manager",
    )
    review = service._parse_agent_response(
        '{"verdict":"wait","confidence":0.5,"rationale":"No edge yet."}',
        "investment-committee",
    )
    exit_trade = service._parse_agent_response(
        '{"verdict":"sell now","confidence":0.8,"rationale":"Thesis broken."}',
        "risk-manager",
    )

    assert buy["verdict"] == "buy"
    assert hold["verdict"] == "hold"
    assert review["verdict"] == "review"
    assert exit_trade["verdict"] == "exit"


def test_create_notifications_adds_invalidation_alerts() -> None:
    """Active invalidation triggers should surface as explicit Jenny alerts."""
    service = _service()
    service.thesis_service = Mock()
    service.thesis_service.get_thesis.return_value = Mock()
    service.thesis_service.check_invalidation_triggers.return_value = [
        "Signal flipped from BUY to AVOID",
    ]
    service._aggregate_symbol_review = Mock(
        return_value=Mock(
            final_verdict="hold",
            average_confidence=0.6,
            reasons=["Trend intact."],
            evaluations=[],
        )
    )
    service._upsert_notification = Mock()

    created = service._create_notifications(
        routine_id="routine-1",
        live_symbols={"AAPL"},
        evaluations_by_symbol={"AAPL": [{"verdict": "hold"}]},
    )

    assert created == 1
    service._upsert_notification.assert_called_once_with(
        "routine-1",
        "AAPL",
        category="thesis_invalidation",
        severity="critical",
        title="AAPL: thesis invalidation triggered",
        detail="Signal flipped from BUY to AVOID",
        recommendation="Review the thesis and current price action before holding or adding.",
    )


def test_get_latest_symbol_reviews_uses_newest_routine_per_symbol() -> None:
    """Dashboard reviews should ignore stale evaluations from older routines."""
    service = _service()
    service.storage = MagicMock()
    service.thesis_service = Mock()
    service.thesis_service.get_thesis.return_value = None

    rows = [
        ("eval-new-1", "routine-new", "AAPL", "equity-analyst", None, None, "review", 0.6, "fresh thesis", None, [], [], {}, None, None, "2026-03-07T12:00:00+00:00"),
        ("eval-new-2", "routine-new", "AAPL", "risk-manager", None, None, "review", 0.5, "fresh risk", None, [], [], {}, None, None, "2026-03-07T12:00:01+00:00"),
        ("eval-old-1", "routine-old", "AAPL", "equity-analyst", None, None, "hold", 0.9, "stale thesis", None, [], [], {}, None, None, "2026-03-07T11:00:00+00:00"),
        ("eval-msft-1", "routine-msft", "MSFT", "equity-analyst", None, None, "buy", 0.7, "msft setup", None, [], [], {}, None, None, "2026-03-07T12:00:02+00:00"),
    ]
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = rows

    aggregated_inputs: list[tuple[str, list[JennyAgentEvaluation]]] = []

    def capture(symbol: str, evaluations: list[JennyAgentEvaluation], thesis) -> Mock:
        aggregated_inputs.append((symbol, evaluations))
        return Mock(symbol=symbol)

    service._aggregate_symbol_review = Mock(side_effect=capture)

    reviews = service._get_latest_symbol_reviews(limit=8)

    assert len(reviews) == 2
    aapl_evaluations = next(evaluations for symbol, evaluations in aggregated_inputs if symbol == "AAPL")
    assert {evaluation.id for evaluation in aapl_evaluations} == {"eval-new-1", "eval-new-2"}
    assert all(evaluation.routine_id == "routine-new" for evaluation in aapl_evaluations)
