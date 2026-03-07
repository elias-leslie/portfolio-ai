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
