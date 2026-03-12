"""Unit tests for Jenny conversation service."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

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


def test_chat_returns_document_aware_fallback_for_upload_questions() -> None:
    service = JennyConversationService()
    service.household_service = Mock()
    service.household_service.list_questions.return_value = HouseholdQuestionList(items=[])
    service._build_context = Mock(
        return_value={
            "household": {
                "documents": [
                    {
                        "filename": "image.png",
                        "document_type": "brokerage_statement",
                        "status": "parsed",
                        "review_summary": "529 college savings account snapshot with beneficiary balances.",
                    }
                ],
                "jenny_needs": [],
            },
            "symbols": {"detected": []},
        }
    )
    service._complete_conversation = Mock(side_effect=RuntimeError("conversation failed"))
    service._reconcile_message = Mock(return_value=[])
    service._extract_planning_updates = Mock(
        return_value={"profile_updates": {}, "planning_items": []}
    )

    result = service.chat("Did you get the 529 image I uploaded?")

    assert "I do see your latest upload" in result["reply"]
    assert "529 college savings account snapshot" in result["reply"]
    assert "do not auto-create portfolio accounts" in result["reply"]


@patch("app.services.jenny_conversation_service._get_analytics_payload")
def test_build_context_includes_recent_documents_and_runtime_status(
    get_analytics_payload: Mock,
) -> None:
    service = JennyConversationService()
    service.household_service = Mock()
    service.portfolio_mgr = Mock()
    service.health_service = Mock()
    service.jenny_dashboard_reader = Mock()
    service._load_project_index = Mock(
        return_value={
            "project": "portfolio-ai",
            "generated_at": "2026-03-12 16:00 UTC",
            "pages": ["/money", "/status"],
            "endpoints": ["GET /health/simple"],
            "tasks": ["jenny_daily_operator_wf (cron(15 22 * * 1-5))"],
            "services": {"backend_port": 8000, "frontend_port": 3000},
        }
    )

    def _dumpable(payload: dict[str, object]) -> Mock:
        return Mock(model_dump=Mock(return_value=payload))

    service.household_service.get_dashboard.return_value = SimpleNamespace(
        overview=_dumpable({"visibility_score": 90}),
        profile=_dumpable({"household_name": "Family"}),
        resolved_values=[],
        budget_readiness=_dumpable({"status": "ready"}),
        budget_snapshot=_dumpable({"monthly_income": 8000}),
        retirement_preparedness=_dumpable({"status": "on_track"}),
        import_center=_dumpable({"tracked_documents": 1, "parsed_documents": 1}),
        jenny_needs=[],
        planning=_dumpable({"members": []}),
    )
    service.household_service.list_documents.return_value = SimpleNamespace(
        items=[
            SimpleNamespace(
                id="doc-1",
                filename="image.png",
                source_type="brokerage",
                document_type="brokerage_statement",
                status="parsed",
                review_status="complete",
                review_summary="529 college savings account snapshot with beneficiary balances.",
                uploaded_at="2026-03-12T15:00:00Z",
                parsed_at="2026-03-12T15:01:00Z",
            )
        ]
    )
    service.portfolio_mgr.get_accounts.return_value = []
    service.portfolio_mgr.get_positions.return_value = []
    service.health_service.perform_health_check.return_value = {
        "status": "healthy",
        "services": {"backend": {"status": "healthy"}},
        "workflow_health": SimpleNamespace(model_dump=lambda: {"status": "healthy"}),
    }
    service.jenny_dashboard_reader.get_recent_routines.return_value = [
        SimpleNamespace(
            routine_type="daily_operator",
            status="complete",
            summary="Reviewed live symbols.",
            started_at="2026-03-12T14:15:00Z",
            completed_at="2026-03-12T14:17:00Z",
        )
    ]
    service.jenny_dashboard_reader.get_open_notifications.return_value = [
        SimpleNamespace(
            symbol="AMD",
            category="review",
            severity="warning",
            title="Review AMD thesis",
            status="open",
        )
    ]
    get_analytics_payload.return_value = SimpleNamespace(model_dump=lambda: {"status": "ok"})

    context = service._build_context("Did you get my 529 upload?", [])

    assert context["household"]["documents"][0]["filename"] == "image.png"
    assert context["household"]["documents"][0]["review_summary"].startswith("529 college savings")
    assert context["portfolio_ai"]["current_status"]["system"] == "healthy"
    assert context["portfolio_ai"]["pages"] == ["/money", "/status"]
    assert "do not auto-create portfolio_accounts" in context["portfolio_ai"]["document_pipeline"]["behavior"]
