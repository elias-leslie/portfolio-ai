"""LLM completion helpers for Jenny conversation service."""

from __future__ import annotations

import json
from typing import Any

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.logging_config import get_logger
from app.models.household_finance import HouseholdQuestion

from ._jenny_conversation_constants import (
    PLANNING_UPDATE_SCHEMA,
    PURPOSE_CHAT,
    PURPOSE_PLANNING_EXTRACT,
    PURPOSE_RECONCILE,
    RECONCILIATION_RESPONSE_FORMAT,
    SYSTEM_CHAT,
    SYSTEM_PLANNING_EXTRACT,
    SYSTEM_RECONCILE,
)
from ._jenny_conversation_context import question_summary

logger = get_logger(__name__)


def make_client() -> AgentHubAPIClient:
    return AgentHubAPIClient(agent_slug="persona", use_memory=True, timeout=120.0)


def complete_conversation(
    *,
    message: str,
    session_id: str | None,
    context: dict[str, Any],
    open_questions: list[HouseholdQuestion],
) -> Any:
    prompt = (
        f"Portfolio-AI context:\n{json.dumps(context, indent=2)}\n\n"
        f"Open household questions:\n{json.dumps([question_summary(q) for q in open_questions], indent=2)}\n\n"
        f"User message:\n{message}"
    )
    client = make_client()
    try:
        return client.complete_messages(
            messages=[{"role": "user", "content": prompt}],
            purpose=PURPOSE_CHAT,
            session_id=session_id,
            thinking_level="low",
            system_prompt=SYSTEM_CHAT,
        )
    finally:
        client.close()


def reconcile_message(
    *,
    message: str,
    open_questions: list[HouseholdQuestion],
    context: dict[str, Any],
) -> list[dict[str, str]]:
    if not open_questions:
        return []
    prompt = (
        "Decide which open household questions are directly answered by the user's latest message. "
        "Return only answers that are clearly supported.\n\n"
        f"Open questions:\n{json.dumps([question_summary(q) for q in open_questions], indent=2)}\n\n"
        f"Relevant portfolio-ai context:\n{json.dumps(context, indent=2)}\n\n"
        f"User message:\n{message}"
    )
    client = make_client()
    try:
        response = client.complete_messages(
            messages=[{"role": "user", "content": prompt}],
            purpose=PURPOSE_RECONCILE,
            thinking_level="minimal",
            system_prompt=SYSTEM_RECONCILE,
            response_format=RECONCILIATION_RESPONSE_FORMAT,
            use_memory=False,
        )
    finally:
        client.close()
    return _parse_reconciliation_response(response)


def _parse_reconciliation_response(response: Any) -> list[dict[str, str]]:
    try:
        payload = json.loads(str(getattr(response, "content", "") or "{}"))
    except json.JSONDecodeError:
        logger.warning("jenny_chat_reconciliation_parse_failed", content=getattr(response, "content", ""))
        return []
    answers = payload.get("answers")
    if not isinstance(answers, list):
        return []
    return [
        {
            "question_id": str(a.get("question_id") or "").strip(),
            "answer_text": str(a.get("answer_text") or "").strip(),
        }
        for a in answers
        if isinstance(a, dict)
        and str(a.get("question_id") or "").strip()
        and str(a.get("answer_text") or "").strip()
    ]


def extract_planning_updates(
    *,
    message: str,
    context: dict[str, Any],
    open_questions: list[HouseholdQuestion],
) -> dict[str, Any]:
    prompt = (
        "Extract only durable household planning changes that the user directly stated. "
        "Use profile_updates for scalar assumptions and planning_items for typed section rows.\n\n"
        f"Current context:\n{json.dumps(context, indent=2)}\n\n"
        f"Open questions:\n{json.dumps([question_summary(q) for q in open_questions], indent=2)}\n\n"
        f"User message:\n{message}"
    )
    client = make_client()
    try:
        response = client.complete_messages(
            messages=[{"role": "user", "content": prompt}],
            purpose=PURPOSE_PLANNING_EXTRACT,
            thinking_level="minimal",
            system_prompt=SYSTEM_PLANNING_EXTRACT,
            response_format={"type": "json_object", "schema": PLANNING_UPDATE_SCHEMA},
            use_memory=False,
        )
    finally:
        client.close()
    return _parse_planning_response(response)


def _parse_planning_response(response: Any) -> dict[str, Any]:
    empty: dict[str, Any] = {"profile_updates": {}, "planning_items": []}
    try:
        payload = json.loads(str(getattr(response, "content", "") or "{}"))
    except json.JSONDecodeError:
        logger.warning("jenny_chat_planning_parse_failed", content=getattr(response, "content", ""))
        return empty
    if not isinstance(payload, dict):
        return empty
    profile_updates = payload.get("profile_updates")
    planning_items = payload.get("planning_items")
    return {
        "profile_updates": profile_updates if isinstance(profile_updates, dict) else {},
        "planning_items": planning_items if isinstance(planning_items, list) else [],
    }
