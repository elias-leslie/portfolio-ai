"""Unit tests for Jenny learning helpers."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import Mock

from app.models.jenny import JennyAgentEvaluation, JennyTradeReview
from app.services.jenny_learning_service import JennyLearningService
from app.services.jenny_operator_service import JennyOperatorService


def _service() -> JennyOperatorService:
    return JennyOperatorService()


def test_build_trade_lesson_handles_large_loss() -> None:
    helper = JennyLearningService()

    lesson = helper.build_trade_lesson(-12.0, "thesis invalidated")

    assert "Large losses" in lesson


def test_refresh_scorecards_groups_by_agent() -> None:
    helper = JennyLearningService()
    service = _service()
    service._fetch_all_evaluations = Mock(
        return_value=[
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
            )
        ]
    )
    service._get_recent_trade_reviews = Mock(
        return_value=[
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
        ]
    )
    build_scorecard = Mock(return_value=Mock())
    save_scorecard = Mock()
    helper.build_scorecard = cast(Any, build_scorecard)
    helper.save_scorecard = cast(Any, save_scorecard)

    updated = helper.refresh_scorecards(service)

    assert updated == 1
    build_scorecard.assert_called_once()
    save_scorecard.assert_called_once()
