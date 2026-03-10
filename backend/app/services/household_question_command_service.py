"""Question answer command helpers for household finance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdQuestion, HouseholdQuestionAnswer
from app.services.household_finance_rows import row_to_question


class HouseholdQuestionCommandService:
    """Apply question answers and related reconciliation side effects."""

    def answer_question(
        self,
        service: Any,
        question_id: str,
        payload: HouseholdQuestionAnswer,
    ) -> HouseholdQuestion | None:
        question = service._get_question_row(question_id)
        if question is None:
            return None

        row_question = row_to_question(question, iso=service._iso, iso_or_none=service._iso_or_none)
        cleaned_answer = payload.answer_text.strip()
        service._apply_answer_to_profile(row_question, cleaned_answer)

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
            service._resolve_related_open_questions(
                conn=conn,
                question=row_question,
                answer_text=cleaned_answer,
                answered_at=now,
            )
            conn.commit()

        answered = service._get_question_row(question_id)
        return (
            row_to_question(answered, iso=service._iso, iso_or_none=service._iso_or_none)
            if answered is not None
            else None
        )
