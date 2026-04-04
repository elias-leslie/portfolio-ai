"""LLM completion helpers for Jenny conversation service."""

from __future__ import annotations

import json
from typing import Any

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.logging_config import get_logger
from app.models.household_finance import HouseholdProfileUpdate, HouseholdQuestion
from app.utils.json_helpers import json_serializer

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
from ._jenny_response_cleanup import extract_json_object_text

logger = get_logger(__name__)
_EMPTY_PLANNING_UPDATES: dict[str, Any] = {"profile_updates": {}, "planning_items": []}
_PROFILE_UPDATE_FIELDS = frozenset(HouseholdProfileUpdate.model_fields)
_GOAL_BUCKET_SECTION = "goal_buckets"
_PLANNED_EXPENSES_SECTION = "planned_expenses"


def _json_block(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=json_serializer)


def make_client(
    *,
    agent_slug: str = "persona",
    use_memory: bool | None = True,
) -> AgentHubAPIClient:
    return AgentHubAPIClient(agent_slug=agent_slug, use_memory=use_memory)


def complete_conversation(
    *,
    message: str,
    session_id: str | None,
    context: dict[str, Any],
    open_questions: list[HouseholdQuestion],
) -> Any:
    prompt = (
        f"Portfolio-AI context:\n{_json_block(context)}\n\n"
        f"Open household questions:\n{_json_block([question_summary(q) for q in open_questions])}\n\n"
        f"User message:\n{message}"
    )
    client = make_client(agent_slug="chat", use_memory=False)
    try:
        return client.complete_messages(
            messages=[{"role": "user", "content": prompt}],
            purpose=PURPOSE_CHAT,
            session_id=session_id,
            thinking_level="low",
            system_prompt=SYSTEM_CHAT,
            use_memory=False,
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
        f"Open questions:\n{_json_block([question_summary(q) for q in open_questions])}\n\n"
        f"Relevant portfolio-ai context:\n{_json_block(context)}\n\n"
        f"User message:\n{message}"
    )
    client = make_client(agent_slug="chat", use_memory=False)
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
    raw_content = str(getattr(response, "content", "") or "")
    payload_text = extract_json_object_text(raw_content)
    if payload_text is None:
        logger.warning("jenny_chat_reconciliation_parse_failed", content=raw_content)
        return []
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        logger.warning("jenny_chat_reconciliation_parse_failed", content=raw_content)
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
        f"Current context:\n{_json_block(context)}\n\n"
        f"Open questions:\n{_json_block([question_summary(q) for q in open_questions])}\n\n"
        f"User message:\n{message}"
    )
    client = make_client(agent_slug="chat", use_memory=False)
    try:
        request_kwargs = {
            "messages": [{"role": "user", "content": prompt}],
            "purpose": PURPOSE_PLANNING_EXTRACT,
            "thinking_level": "minimal",
            "system_prompt": SYSTEM_PLANNING_EXTRACT,
            "use_memory": False,
        }
        try:
            response = client.complete_messages(
                response_format={"type": "json_object", "schema": PLANNING_UPDATE_SCHEMA},
                **request_kwargs,
            )
        except Exception as exc:
            logger.warning(
                "jenny_chat_planning_schema_retry",
                error=str(exc),
            )
            response = client.complete_messages(
                response_format={"type": "json_object"},
                **request_kwargs,
            )
    finally:
        client.close()
    return _parse_planning_response(response)


def _parse_planning_response(response: Any) -> dict[str, Any]:
    raw_content = str(getattr(response, "content", "") or "")
    payload_text = extract_json_object_text(raw_content)
    if payload_text is None:
        logger.warning("jenny_chat_planning_parse_failed", content=raw_content)
        return dict(_EMPTY_PLANNING_UPDATES)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        logger.warning("jenny_chat_planning_parse_failed", content=raw_content)
        return dict(_EMPTY_PLANNING_UPDATES)
    if not isinstance(payload, dict):
        return dict(_EMPTY_PLANNING_UPDATES)
    normalized = _normalize_planning_payload(payload)
    if normalized == _EMPTY_PLANNING_UPDATES:
        logger.warning("jenny_chat_planning_parse_failed", content=raw_content)
    return normalized


def _normalize_planning_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "profile_updates" in payload or "planning_items" in payload:
        return {
            "profile_updates": _normalize_profile_updates(payload.get("profile_updates")),
            "planning_items": _normalize_planning_items(payload.get("planning_items")),
        }

    if isinstance(payload.get("updates"), dict):
        return _normalize_nested_household_updates(payload["updates"])

    if isinstance(payload.get("changes"), list):
        return _normalize_change_operations(payload["changes"])

    return dict(_EMPTY_PLANNING_UPDATES)


def _normalize_profile_updates(raw_updates: Any) -> dict[str, Any]:
    if not isinstance(raw_updates, dict):
        return {}
    return {
        key: value
        for key, value in raw_updates.items()
        if key in _PROFILE_UPDATE_FIELDS and value is not None
    }


def _normalize_planning_items(raw_items: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    normalized = [
        item
        for raw_item in raw_items
        if isinstance(raw_item, dict)
        for item in [_normalize_planning_item(raw_item)]
        if item is not None
    ]
    return normalized


def _normalize_nested_household_updates(updates: dict[str, Any]) -> dict[str, Any]:
    household = updates.get("household")
    if not isinstance(household, dict):
        return dict(_EMPTY_PLANNING_UPDATES)

    profile_updates = _normalize_profile_updates(household.get("profile"))
    planning_items: list[dict[str, Any]] = []
    planning = household.get("planning")
    if isinstance(planning, dict):
        for raw_section, raw_items in planning.items():
            planning_items.extend(_collect_section_items(raw_section, raw_items))

    return {
        "profile_updates": profile_updates,
        "planning_items": planning_items,
    }


def _normalize_change_operations(changes: list[Any]) -> dict[str, Any]:
    profile_updates: dict[str, Any] = {}
    planning_items: list[dict[str, Any]] = []

    for raw_change in changes:
        if not isinstance(raw_change, dict):
            continue
        path = str(raw_change.get("path") or "").strip()
        if path.startswith("household.profile."):
            field_name = path.removeprefix("household.profile.")
            if field_name in _PROFILE_UPDATE_FIELDS and raw_change.get("value") is not None:
                profile_updates[field_name] = raw_change["value"]
            continue
        if path.startswith("household.planning."):
            raw_section = path.removeprefix("household.planning.")
            planning_items.extend(_collect_section_items(raw_section, raw_change.get("value")))

    return {
        "profile_updates": profile_updates,
        "planning_items": planning_items,
    }


def _collect_section_items(raw_section: str, raw_items: Any) -> list[dict[str, Any]]:
    section = _normalize_section_name(raw_section)
    if not section:
        return []
    if isinstance(raw_items, dict):
        items = [raw_items]
    elif isinstance(raw_items, list):
        items = [item for item in raw_items if isinstance(item, dict)]
    else:
        return []
    return [
        item
        for raw_item in items
        for item in [_normalize_planning_item({"section": section, "__raw_section__": raw_section, **raw_item})]
        if item is not None
    ]


def _normalize_section_name(section: Any) -> str:
    normalized = str(section or "").strip()
    if normalized == _GOAL_BUCKET_SECTION:
        return _PLANNED_EXPENSES_SECTION
    return normalized


def _normalize_planning_item(raw_item: dict[str, Any]) -> dict[str, Any] | None:
    section = _normalize_section_name(raw_item.get("section"))
    raw_section = str(raw_item.get("__raw_section__") or raw_item.get("section") or "").strip()
    if not section:
        return None
    payload = {
        key: value
        for key, value in raw_item.items()
        if key not in {"section", "__raw_section__"} and value is not None
    }
    nested_data = payload.pop("data", None)
    if isinstance(nested_data, dict):
        payload = {**nested_data, **payload}
    payload.pop("action", None)

    if section == "members":
        display_name = _consume_first_string(payload, "display_name", "name", "label", "title")
        if not display_name:
            return None
        item: dict[str, Any] = {
            "section": section,
            "display_name": display_name,
            "role": _consume_first_string(payload, "role") or "adult",
        }
        for key in (
            "relationship",
            "birth_year",
            "is_dependent",
            "lives_in_household",
            "notes",
            "rationale",
        ):
            if key in payload:
                item[key] = payload[key]
        return item

    label = _consume_first_string(payload, "label", "name", "title")
    if not label:
        return None

    if section == "income_sources":
        _remap_key(payload, "type", "source_type")
        payload.setdefault("source_type", "other")
    elif section == "debt_obligations":
        _remap_key(payload, "type", "debt_type")
        payload.setdefault("debt_type", "other")
    elif section == "housing_costs":
        _remap_key(payload, "type", "housing_type")
        payload.setdefault("housing_type", "other")
        payload.setdefault("occupancy_role", "primary")
    elif section == "insurance_policies":
        _remap_key(payload, "type", "coverage_type")
        payload.setdefault("coverage_type", "other")
    elif section == "retirement_income_sources":
        _remap_key(payload, "type", "source_type")
        payload.setdefault("source_type", "other")
    elif section == _PLANNED_EXPENSES_SECTION:
        _remap_key(payload, "amount", "target_amount")
        expense_kind = str(payload.get("expense_kind") or "").strip()
        if not expense_kind:
            payload["expense_kind"] = "goal_bucket" if raw_section == _GOAL_BUCKET_SECTION else "major_expense"
        payload.setdefault(
            "category",
            "goal_bucket" if payload["expense_kind"] == "goal_bucket" else "planned",
        )
        payload.setdefault("priority", "medium")

    return {
        "section": section,
        "label": label,
        **payload,
    }


def _consume_first_string(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.pop(key, None)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _remap_key(payload: dict[str, Any], source: str, target: str) -> None:
    if target not in payload and source in payload:
        payload[target] = payload.pop(source)
