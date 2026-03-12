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
    service._extract_planning_updates = Mock(
        return_value={"profile_updates": {}, "planning_items": []}
    )

    result = service.chat("I want to retire at 60.")

    service.household_service.answer_question.assert_called_once_with(
        "question-1",
        HouseholdQuestionAnswer(answer_text="60"),
    )
    assert result["session_id"] == "session-1"
    assert result["updated_fields"] == ["target_retirement_age"]
    assert result["resolved_questions"][0]["answer_text"] == "60"


def test_chat_applies_profile_and_planning_updates_from_free_form_message() -> None:
    service = JennyConversationService()
    service.household_service = Mock()
    service.household_service.list_questions.return_value = HouseholdQuestionList(items=[])
    service.household_service.update_profile = Mock()
    service.household_service.merge_planning_items = Mock()
    service._build_context = Mock(return_value={"household": {}, "symbols": {"detected": []}})
    service._complete_conversation = Mock(
        return_value=SimpleNamespace(
            content="I updated the household planning workbook.",
            session_id="session-2",
        )
    )
    service._reconcile_message = Mock(return_value=[])
    service._extract_planning_updates = Mock(
        return_value={
            "profile_updates": {"emergency_fund_target_amount": 30000},
            "planning_items": [
                {
                    "section": "planned_expenses",
                    "label": "Roof replacement",
                    "expense_kind": "major_expense",
                    "category": "home",
                    "target_amount": 18000,
                }
            ],
        }
    )

    result = service.chat("We should plan for a $18k roof and a $30k emergency fund.")

    service.household_service.update_profile.assert_called_once()
    update_payload = service.household_service.update_profile.call_args.args[0]
    assert update_payload.emergency_fund_target_amount == 30000
    service.household_service.merge_planning_items.assert_called_once()
    assert "planned_expenses" in result["updated_fields"]


def test_chat_survives_planning_extract_failure() -> None:
    service = JennyConversationService()
    service.household_service = Mock()
    service.household_service.list_questions.return_value = HouseholdQuestionList(items=[])
    service._build_context = Mock(
        return_value={
            "household": {"jenny_needs": [{"title": "Upload statements"}]},
            "symbols": {"detected": []},
        }
    )
    service._complete_conversation = Mock(
        return_value=SimpleNamespace(
            content="I can still help with the rest of the workspace.",
            session_id="session-3",
        )
    )
    service._reconcile_message = Mock(return_value=[])
    service._extract_planning_updates = Mock(side_effect=RuntimeError("extract failed"))

    result = service.chat("hello")

    assert result["reply"] == "I can still help with the rest of the workspace."
    assert result["session_id"] == "session-3"
    assert result["updated_fields"] == []


def test_chat_returns_fallback_reply_when_completion_fails() -> None:
    service = JennyConversationService()
    service.household_service = Mock()
    service.household_service.list_questions.return_value = HouseholdQuestionList(items=[])
    service._build_context = Mock(
        return_value={
            "household": {
                "jenny_needs": [
                    {"title": "Upload statements"},
                    {"title": "Complete housing planning"},
                ]
            },
            "symbols": {"detected": []},
        }
    )
    service._complete_conversation = Mock(side_effect=RuntimeError("conversation failed"))
    service._reconcile_message = Mock(return_value=[])
    service._extract_planning_updates = Mock(
        return_value={"profile_updates": {}, "planning_items": []}
    )

    result = service.chat("What should I do next?")

    assert "Upload statements" in result["reply"]
    assert "Complete housing planning" in result["reply"]
    assert result["session_id"] == ""
