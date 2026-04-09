"""Chat orchestration helpers for Jenny conversation service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from app.logging_config import get_logger
from app.models.household_finance import (
    HouseholdProfileUpdate,
    HouseholdQuestionAnswer,
)

from ._jenny_conversation_constants import PROVENANCE_JENNY_CHAT
from ._jenny_response_cleanup import strip_agent_output_tags

if TYPE_CHECKING:
    from app.services.household_finance_service import HouseholdFinanceService

logger = get_logger(__name__)


def apply_reconciled_answers(
    reconciled_answers: list[dict[str, str]],
    household_service: HouseholdFinanceService,
) -> tuple[list[dict[str, Any]], list[str]]:
    resolved_questions: list[dict[str, Any]] = []
    updated_fields: list[str] = []
    for answer in reconciled_answers:
        question_id = str(answer.get("question_id") or "").strip()
        answer_text = str(answer.get("answer_text") or "").strip()
        if not question_id or not answer_text:
            continue
        answered = household_service.answer_question(
            question_id,
            HouseholdQuestionAnswer(answer_text=answer_text),
        )
        if answered is None:
            continue
        resolved_questions.append(
            {
                "id": answered.id,
                "field_name": answered.field_name,
                "question": answered.question,
                "answer_text": answered.answer_text,
            }
        )
        if answered.field_name and answered.field_name not in updated_fields:
            updated_fields.append(answered.field_name)
    return resolved_questions, updated_fields


def apply_profile_updates(
    planning_updates: dict[str, Any],
    updated_fields: list[str],
    household_service: HouseholdFinanceService,
) -> list[str]:
    profile_updates = planning_updates.get("profile_updates") if isinstance(planning_updates, dict) else None
    if not isinstance(profile_updates, dict):
        return updated_fields
    cleaned = {k: v for k, v in profile_updates.items() if v is not None}
    if cleaned:
        try:
            validated = HouseholdProfileUpdate.model_validate(cleaned)
        except ValidationError as exc:
            logger.warning(
                "profile_update_validation_failed",
                error=str(exc),
                keys=list(cleaned.keys()),
            )
            return updated_fields
        household_service.update_profile(validated)
        updated_fields.extend(k for k in cleaned if k not in updated_fields)
    return updated_fields


def apply_planning_items(
    planning_updates: dict[str, Any],
    updated_fields: list[str],
    household_service: HouseholdFinanceService,
) -> list[str]:
    planning_items = planning_updates.get("planning_items") if isinstance(planning_updates, dict) else None
    if not isinstance(planning_items, list) or not planning_items:
        return updated_fields
    dict_items = [item for item in planning_items if isinstance(item, dict)]
    household_service.merge_planning_items(items=dict_items, provenance=PROVENANCE_JENNY_CHAT)
    for section in (str(i.get("section") or "").strip() for i in dict_items):
        if section and section not in updated_fields:
            updated_fields.append(section)
    return updated_fields


def compose_reply(
    completion: Any,
    resolved_questions: list[dict[str, Any]],
    planning_updates: dict[str, Any],
    updated_fields: list[str],
    field_labels: dict[str, str],
) -> str:
    reply = strip_agent_output_tags(str(getattr(completion, "content", "") or ""))
    planning_items = planning_updates.get("planning_items") if isinstance(planning_updates, dict) else None
    if resolved_questions:
        labels = [
            field_labels.get(field_name, field_name.replace("_", " "))
            for field_name in updated_fields
        ]
        if labels:
            reply = (
                f"{reply}\n\n"
                f"I also used your message to update the household plan: {', '.join(labels)}."
            ).strip()
    elif isinstance(planning_items, list) and planning_items:
        reply = f"{reply}\n\nI also added those planning details to your household plan.".strip()
    return reply


def build_fallback_reply(message: str, context: dict[str, Any]) -> str:
    household = context.get("household", {})
    lower_message = message.lower()
    raw_documents = household.get("documents")
    documents = raw_documents if isinstance(raw_documents, list) else []
    if (
        any(token in lower_message for token in ("upload", "uploaded", "image", "document", "screenshot"))
        and documents
    ):
        latest = documents[0]
        if isinstance(latest, dict):
            summary = str(latest.get("review_summary") or latest.get("filename") or "latest upload").strip()
            document_type = str(latest.get("document_type") or "document").replace("_", " ")
            status = str(latest.get("status") or "unknown")
            return (
                "Jenny hit an upstream model issue, but I can still confirm the latest intake state. "
                f"I do see your latest upload: {summary} "
                f"(type: {document_type}, status: {status}). "
                "Jenny treats uploads as shared financial evidence first, then promotes "
                "high-confidence facts into the money and portfolio system after review."
            )
    return _fallback_from_needs(household)


def _fallback_from_needs(household: dict[str, Any]) -> str:
    raw_needs = household.get("jenny_needs")
    needs = raw_needs if isinstance(raw_needs, list) else []
    top_titles = [
        str(need.get("title"))
        for need in needs[:3]
        if isinstance(need, dict) and need.get("title")
    ]
    if top_titles:
        return (
            "Jenny hit an upstream model issue, but your workspace is still available. "
            f"Top priorities right now: {', '.join(top_titles)}."
        )
    return (
        "Jenny hit an upstream model issue, but your household and portfolio "
        "workspace is still available. Try again in a moment."
    )
