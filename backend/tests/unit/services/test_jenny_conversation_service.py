"""Unit tests for Jenny conversation service."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from app.models.household_finance import (
    HouseholdQuestion,
    HouseholdQuestionAnswer,
    HouseholdQuestionList,
)
from app.services.jenny_conversation_service import JennyConversationService


def _question(question_id: str, *, field_name: str | None = None) -> HouseholdQuestion:
    return HouseholdQuestion(
        id=question_id,
        field_name=field_name,
        status="open",
        priority="high",
        question="What age do you want to retire?",
        rationale=None,
        recommendation=None,
        answer_text=None,
        source_document_id=None,
        metadata={},
        question_format="integer",
        options=None,
        direction="jenny_to_user",
        created_at="2026-03-11T00:00:00Z",
        answered_at=None,
    )


def test_chat_reconciles_open_questions_from_free_form_message() -> None:
    service = JennyConversationService()
    service.household_service = Mock()
    service.household_service.list_questions.return_value = HouseholdQuestionList(
        items=[_question("question-1", field_name="target_retirement_age")]
    )
    service.household_service.answer_question.return_value = HouseholdQuestion(
        **{
            **_question("question-1", field_name="target_retirement_age").model_dump(),
            "status": "answered",
            "answer_text": "60",
            "answered_at": "2026-03-11T00:05:00Z",
        }
    )
    service._build_context = Mock(
        return_value={
            "household": {"questions": ["What age do you want to retire?"]},
            "symbols": {"detected": []},
        }
    )
    service._complete_conversation = Mock(
        return_value=SimpleNamespace(
            content="Age 60 is now part of the household plan.",
            session_id="session-1",
        )
    )
    service._reconcile_message = Mock(
        return_value=[{"question_id": "question-1", "answer_text": "60"}]
    )

    result = service.chat("I want to retire at 60.")

    service.household_service.answer_question.assert_called_once_with(
        "question-1",
        HouseholdQuestionAnswer(answer_text="60"),
    )
    assert result["session_id"] == "session-1"
    assert result["updated_fields"] == ["target_retirement_age"]
    assert result["resolved_questions"][0]["answer_text"] == "60"
