"""Question answer command helpers for household finance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdQuestion, HouseholdQuestionAnswer
from app.services._household_finance_utils import iso, iso_or_none
from app.services.household_finance_rows import row_to_question

_QUESTION_COLS = (
    "q.id, q.field_name, q.status, q.priority, q.question, q.rationale, "
    "q.answer_text, q.source_document_id, q.metadata, q.question_format, "
    "q.options, q.direction, q.created_at, q.answered_at, "
    "d.filename, d.source_type, d.document_type, d.account_label, d.review_summary, d.metadata"
)
_QUESTION_JOIN = "FROM household_questions q LEFT JOIN household_documents d ON d.id = q.source_document_id"


def _fetch_question_row(service: Any, question_id: str) -> tuple[Any, ...] | None:
    with service.storage.connection() as conn:
        return conn.execute(
            f"SELECT {_QUESTION_COLS} {_QUESTION_JOIN} WHERE q.id = %s",
            [question_id],
        ).fetchone()


class HouseholdQuestionCommandService:
    """Apply question answers and related reconciliation side effects."""

    def answer_question(
        self,
        service: Any,
        question_id: str,
        payload: HouseholdQuestionAnswer,
    ) -> HouseholdQuestion | None:
        question = _fetch_question_row(service, question_id)
        if question is None:
            return None

        row_question = row_to_question(question, iso=iso, iso_or_none=iso_or_none)
        cleaned_answer = payload.answer_text.strip()
        service.question_reconciler.apply_answer_to_profile(service, row_question, cleaned_answer)

        now = datetime.now(UTC).isoformat()
        with service.storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_questions
                SET status = 'answered', answer_text = %s, answered_at = %s
                WHERE id = %s
                """,
                [cleaned_answer, now, question_id],
            )
            if row_question.field_name:
                conn.execute(
                    """
                    UPDATE household_inferred_values
                    SET status = 'confirmed', updated_at = %s
                    WHERE field_name = %s
                    """,
                    [now, row_question.field_name],
                )
            service.question_reconciler.resolve_related_open_questions(
                service,
                conn=conn,
                question=row_question,
                answer_text=cleaned_answer,
                answered_at=now,
            )
            conn.commit()

        answered = _fetch_question_row(service, question_id)
        return (
            row_to_question(answered, iso=iso, iso_or_none=iso_or_none)
            if answered is not None
            else None
        )
