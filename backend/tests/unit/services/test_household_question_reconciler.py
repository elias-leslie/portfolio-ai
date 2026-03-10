"""Unit tests for household question reconciliation helpers."""

from __future__ import annotations

from app.models.household_finance import HouseholdQuestion
from app.services.household_question_reconciler import HouseholdQuestionReconciler


def _question(
    *,
    question_id: str,
    text: str,
    field_name: str | None = None,
    source_document_id: str | None = "doc-1",
    metadata: dict | None = None,
) -> HouseholdQuestion:
    return HouseholdQuestion(
        id=question_id,
        field_name=field_name,
        status="open",
        priority="high",
        question=text,
        rationale=None,
        recommendation=None,
        answer_text=None,
        source_document_id=source_document_id,
        metadata=metadata or {},
        created_at="2026-03-10T00:00:00Z",
        answered_at=None,
    )


def test_questions_are_semantic_duplicates_for_shopping_channel() -> None:
    reconciler = HouseholdQuestionReconciler()
    first = _question(
        question_id="q1",
        text="Should Jenny treat Walmart orders like this as part of regular household spending?",
    )
    second = _question(
        question_id="q2",
        text="Is Walmart a recurring household shopping channel for Jenny (weekly or monthly)?",
    )

    assert reconciler.questions_are_semantic_duplicates(first, second) is True


def test_parse_answer_value_rounds_retirement_age_to_int() -> None:
    reconciler = HouseholdQuestionReconciler()

    parsed = reconciler.parse_answer_value("target_retirement_age", "around 59.6 years old")

    assert parsed == 60


def test_question_is_answered_by_context_for_document_role() -> None:
    reconciler = HouseholdQuestionReconciler()
    answered = _question(
        question_id="q1",
        text="What role should this document play in the household plan?",
    )
    candidate = _question(
        question_id="q2",
        text="What role should this document play in the household plan?",
    )

    assert reconciler.question_is_answered_by_context(
        answered_question=answered,
        candidate_question=candidate,
        answer_text="Use it as the main monthly checking baseline.",
        answered_family="document_role",
    )
