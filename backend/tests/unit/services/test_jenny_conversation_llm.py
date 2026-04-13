"""Regression tests for Jenny conversation LLM helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.models.household_finance import HouseholdQuestion
from app.services._jenny_conversation_constants import PLANNING_UPDATE_SCHEMA
from app.services._jenny_conversation_llm import (
    complete_conversation,
    extract_planning_updates,
    make_client,
    reconcile_message,
)

_PROMPT_LOADER = "app.services._jenny_conversation_llm.require_agent_hub_prompt"


def _question(question_id: str) -> HouseholdQuestion:
    return HouseholdQuestion(
        id=question_id,
        field_name="target_retirement_age",
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


def test_complete_conversation_serializes_datetime_context() -> None:
    client = Mock()
    client.complete_messages.return_value = SimpleNamespace(content="ok", session_id="session-1")

    with (
        patch("app.services._jenny_conversation_llm.make_client", return_value=client),
        patch(_PROMPT_LOADER, return_value="system"),
    ):
        result = complete_conversation(
            message="hello",
            session_id="session-1",
            context={
                "generated_at": datetime(2026, 4, 4, 7, 21, tzinfo=UTC),
                "household": {"next_review_at": datetime(2026, 4, 5, 8, 0, tzinfo=UTC)},
            },
            open_questions=[_question("question-1")],
        )

    prompt = client.complete_messages.call_args.kwargs["messages"][0]["content"]
    assert "2026-04-04T07:21:00+00:00" in prompt
    assert "2026-04-05T08:00:00+00:00" in prompt
    assert result.content == "ok"


def test_reconcile_message_serializes_datetime_context() -> None:
    client = Mock()
    client.complete_messages.return_value = SimpleNamespace(
        content='{"answers":[{"question_id":"question-1","answer_text":"60"}]}'
    )

    with (
        patch("app.services._jenny_conversation_llm.make_client", return_value=client),
        patch(_PROMPT_LOADER, return_value="system"),
    ):
        answers = reconcile_message(
            message="I want to retire at 60.",
            open_questions=[_question("question-1")],
            context={"generated_at": datetime(2026, 4, 4, 7, 21, tzinfo=UTC)},
        )

    prompt = client.complete_messages.call_args.kwargs["messages"][0]["content"]
    assert "2026-04-04T07:21:00+00:00" in prompt
    assert answers == [{"question_id": "question-1", "answer_text": "60"}]


def test_extract_planning_updates_serializes_datetime_context() -> None:
    client = Mock()
    client.complete_messages.return_value = SimpleNamespace(
        content='{"profile_updates":{},"planning_items":[]}'
    )

    with (
        patch("app.services._jenny_conversation_llm.make_client", return_value=client),
        patch(_PROMPT_LOADER, return_value="system"),
    ):
        updates = extract_planning_updates(
            message="Set our emergency fund target to thirty thousand.",
            context={"generated_at": datetime(2026, 4, 4, 7, 21, tzinfo=UTC)},
            open_questions=[_question("question-1")],
        )

    prompt = client.complete_messages.call_args.kwargs["messages"][0]["content"]
    assert "2026-04-04T07:21:00+00:00" in prompt
    assert updates == {"profile_updates": {}, "planning_items": []}


@patch("app.services._jenny_conversation_llm.AgentHubAPIClient")
def test_make_client_uses_persona_with_memory(mock_client_cls: Mock) -> None:
    make_client()

    mock_client_cls.assert_called_once_with(agent_slug="persona", use_memory=True)


@patch(_PROMPT_LOADER, return_value="system")
@patch("app.services._jenny_conversation_llm.make_client")
def test_reconcile_message_uses_chat_agent_without_memory(mock_make_client: Mock, _: Mock) -> None:
    client = Mock()
    client.complete_messages.return_value = SimpleNamespace(
        content='{"answers":[{"question_id":"question-1","answer_text":"60"}]}'
    )
    mock_make_client.return_value = client

    reconcile_message(
        message="I want to retire at 60.",
        open_questions=[_question("question-1")],
        context={"generated_at": datetime(2026, 4, 4, 7, 21, tzinfo=UTC)},
    )

    mock_make_client.assert_called_once_with(agent_slug="chat", use_memory=False)


@patch(_PROMPT_LOADER, return_value="system")
@patch("app.services._jenny_conversation_llm.make_client")
def test_complete_conversation_uses_chat_agent_without_memory(mock_make_client: Mock, _: Mock) -> None:
    client = Mock()
    client.complete_messages.return_value = SimpleNamespace(content="ok", session_id="session-1")
    mock_make_client.return_value = client

    complete_conversation(
        message="hello",
        session_id="session-1",
        context={"generated_at": datetime(2026, 4, 4, 7, 21, tzinfo=UTC)},
        open_questions=[_question("question-1")],
    )

    mock_make_client.assert_called_once_with(agent_slug="chat", use_memory=False)
    assert client.complete_messages.call_args.kwargs["use_memory"] is False


@patch(_PROMPT_LOADER, return_value="system")
@patch("app.services._jenny_conversation_llm.make_client")
def test_extract_planning_updates_uses_chat_agent_without_memory(mock_make_client: Mock, _: Mock) -> None:
    client = Mock()
    client.complete_messages.return_value = SimpleNamespace(
        content='{"profile_updates":{},"planning_items":[]}'
    )
    mock_make_client.return_value = client

    extract_planning_updates(
        message="Set our emergency fund target to thirty thousand.",
        context={"generated_at": datetime(2026, 4, 4, 7, 21, tzinfo=UTC)},
        open_questions=[_question("question-1")],
    )

    mock_make_client.assert_called_once_with(agent_slug="chat", use_memory=False)


@patch(_PROMPT_LOADER, return_value="system")
@patch("app.services._jenny_conversation_llm.make_client")
def test_extract_planning_updates_retries_with_relaxed_json_mode(mock_make_client: Mock, _: Mock) -> None:
    client = Mock()
    client.complete_messages.side_effect = [
        RuntimeError("schema rejected response"),
        SimpleNamespace(content='{"profile_updates":{},"planning_items":[]}'),
    ]
    mock_make_client.return_value = client

    updates = extract_planning_updates(
        message="Set our emergency fund target to thirty thousand.",
        context={"generated_at": datetime(2026, 4, 4, 7, 21, tzinfo=UTC)},
        open_questions=[_question("question-1")],
    )

    first_call = client.complete_messages.call_args_list[0].kwargs
    second_call = client.complete_messages.call_args_list[1].kwargs
    assert first_call["response_format"] == {"type": "json_object", "schema": PLANNING_UPDATE_SCHEMA}
    assert second_call["response_format"] == {"type": "json_object"}
    assert updates == {"profile_updates": {}, "planning_items": []}


@patch(_PROMPT_LOADER, return_value="system")
@patch("app.services._jenny_conversation_llm.make_client")
def test_extract_planning_updates_strips_narration_tags_around_json(mock_make_client: Mock, _: Mock) -> None:
    client = Mock()
    client.complete_messages.return_value = SimpleNamespace(
        content='{"profile_updates":{"emergency_fund_target_amount":30000},"planning_items":[]}\n[[S:completed:Saved planning changes]]'
    )
    mock_make_client.return_value = client

    updates = extract_planning_updates(
        message="Set our emergency fund target to thirty thousand.",
        context={"generated_at": datetime(2026, 4, 4, 7, 21, tzinfo=UTC)},
        open_questions=[_question("question-1")],
    )

    assert updates == {
        "profile_updates": {"emergency_fund_target_amount": 30000},
        "planning_items": [],
    }


@patch(_PROMPT_LOADER, return_value="system")
@patch("app.services._jenny_conversation_llm.make_client")
def test_extract_planning_updates_normalizes_nested_household_updates(mock_make_client: Mock, _: Mock) -> None:
    client = Mock()
    client.complete_messages.return_value = SimpleNamespace(
        content=(
            "[[P:started:extracting]]\n"
            "```json\n"
            "{\n"
            '  "updates": {\n'
            '    "household": {\n'
            '      "profile": {\n'
            '        "emergency_fund_target_amount": 30000\n'
            "      },\n"
            '      "planning": {\n'
            '        "planned_expenses": [\n'
            "          {\n"
            '            "name": "Roof replacement",\n'
            '            "amount": 18000\n'
            "          }\n"
            "        ]\n"
            "      }\n"
            "    }\n"
            "  }\n"
            "}\n"
            "```"
        )
    )
    mock_make_client.return_value = client

    updates = extract_planning_updates(
        message="Set our emergency fund target amount to thirty thousand and add a roof replacement expense.",
        context={"generated_at": datetime(2026, 4, 4, 7, 21, tzinfo=UTC)},
        open_questions=[_question("question-1")],
    )

    assert updates == {
        "profile_updates": {"emergency_fund_target_amount": 30000},
        "planning_items": [
            {
                "section": "planned_expenses",
                "label": "Roof replacement",
                "expense_kind": "major_expense",
                "category": "planned",
                "priority": "medium",
                "target_amount": 18000,
            }
        ],
    }


@patch(_PROMPT_LOADER, return_value="system")
@patch("app.services._jenny_conversation_llm.make_client")
def test_extract_planning_updates_normalizes_planning_items_with_nested_data(mock_make_client: Mock, _: Mock) -> None:
    client = Mock()
    client.complete_messages.return_value = SimpleNamespace(
        content=(
            "```json\n"
            "{\n"
            '  "profile_updates": {\n'
            '    "emergency_fund_target_amount": 30001\n'
            "  },\n"
            '  "planning_items": [\n'
            "    {\n"
            '      "section": "planned_expenses",\n'
            '      "action": "add",\n'
            '      "data": {\n'
            '        "label": "Patio resurfacing",\n'
            '        "amount": 12345\n'
            "      }\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "```"
        )
    )
    mock_make_client.return_value = client

    updates = extract_planning_updates(
        message="Set our emergency fund target amount to 30001 and add a planned patio resurfacing expense of 12345.",
        context={"generated_at": datetime(2026, 4, 4, 7, 21, tzinfo=UTC)},
        open_questions=[_question("question-1")],
    )

    assert updates == {
        "profile_updates": {"emergency_fund_target_amount": 30001},
        "planning_items": [
            {
                "section": "planned_expenses",
                "label": "Patio resurfacing",
                "expense_kind": "major_expense",
                "category": "planned",
                "priority": "medium",
                "target_amount": 12345,
            }
        ],
    }


@patch(_PROMPT_LOADER, return_value="system")
@patch("app.services._jenny_conversation_llm.make_client")
def test_extract_planning_updates_normalizes_change_operations(mock_make_client: Mock, _: Mock) -> None:
    client = Mock()
    client.complete_messages.return_value = SimpleNamespace(
        content=(
            "```json\n"
            "{\n"
            '  "changes": [\n'
            "    {\n"
            '      "path": "household.profile.emergency_fund_target_amount",\n'
            '      "operation": "set",\n'
            '      "value": 30000\n'
            "    },\n"
            "    {\n"
            '      "path": "household.planning.goal_buckets",\n'
            '      "operation": "append",\n'
            '      "value": {\n'
            '        "title": "Travel fund",\n'
            '        "monthly_saving_target": 500\n'
            "      }\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "```"
        )
    )
    mock_make_client.return_value = client

    updates = extract_planning_updates(
        message="Set our emergency fund target amount to thirty thousand and start a travel fund saving $500 monthly.",
        context={"generated_at": datetime(2026, 4, 4, 7, 21, tzinfo=UTC)},
        open_questions=[_question("question-1")],
    )

    assert updates == {
        "profile_updates": {"emergency_fund_target_amount": 30000},
        "planning_items": [
            {
                "section": "planned_expenses",
                "label": "Travel fund",
                "expense_kind": "goal_bucket",
                "category": "goal_bucket",
                "priority": "medium",
                "monthly_saving_target": 500,
            }
        ],
    }
