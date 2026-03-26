"""Facts and question methods mixed into HouseholdFinanceService."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdConfirmedFact,
    HouseholdQuestion,
    HouseholdQuestionAnswer,
    HouseholdQuestionList,
)
from app.services._household_finance_utils import iso, iso_or_none
from app.services.household_finance_rows import row_to_question

_Q_COLS = (
    "q.id, q.field_name, q.status, q.priority, q.question, q.rationale, "
    "q.answer_text, q.source_document_id, q.metadata, q.question_format, "
    "q.options, q.direction, q.created_at, q.answered_at, "
    "d.filename, d.source_type, d.document_type, d.account_label, d.review_summary, d.metadata"
)
_Q_JOIN = "FROM household_questions q LEFT JOIN household_documents d ON d.id = q.source_document_id"


class _HFIntakeMethods:
    """Confirmed facts and question intake methods."""

    storage: Any
    question_reconciler: Any
    question_command_service: Any

    def list_confirmed_facts(self) -> list[HouseholdConfirmedFact]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT fact_key, fact_value, confirmed_at FROM household_confirmed_facts ORDER BY confirmed_at"
            ).fetchall()
        return [
            HouseholdConfirmedFact(fact_key=str(r[0]), fact_value=str(r[1]), confirmed_at=iso(r[2]))
            for r in rows
        ]

    def confirm_fact(self, fact_key: str, fact_value: str) -> HouseholdConfirmedFact:
        now = datetime.now(UTC)
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO household_confirmed_facts (fact_key, fact_value, confirmed_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (fact_key) DO UPDATE
                SET fact_value = EXCLUDED.fact_value, confirmed_at = EXCLUDED.confirmed_at
                """,
                [fact_key, fact_value, now],
            )
            conn.commit()
        return HouseholdConfirmedFact(fact_key=fact_key, fact_value=fact_value, confirmed_at=now.isoformat())

    def list_questions(self, limit: int = 20) -> HouseholdQuestionList:
        self._reconcile_open_questions()
        with self.storage.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT {_Q_COLS} {_Q_JOIN}
                WHERE q.status = 'open'
                ORDER BY
                    CASE q.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                    q.created_at ASC
                LIMIT %s
                """,
                [limit],
            ).fetchall()
        return HouseholdQuestionList(
            items=[row_to_question(row, iso=iso, iso_or_none=iso_or_none) for row in rows]
        )

    def _reconcile_open_questions(self) -> None:
        self.question_reconciler.reconcile_open_questions(self)

    def answer_question(self, question_id: str, payload: HouseholdQuestionAnswer) -> HouseholdQuestion | None:
        return self.question_command_service.answer_question(self, question_id, payload)

    def ask_jenny(self, question_text: str) -> HouseholdQuestion:
        """Create a user-initiated question directed at Jenny."""
        question_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO household_questions
                    (id, field_name, status, priority, question, rationale,
                     question_format, options, direction, metadata, created_at)
                VALUES (%s, NULL, 'open', 'medium', %s, NULL,
                        'short_text', NULL, 'user_to_jenny', '{}', %s)
                """,
                [question_id, question_text.strip(), now],
            )
            conn.commit()
        return HouseholdQuestion(
            id=question_id, field_name=None, status="open", priority="medium",
            question=question_text.strip(), rationale=None, recommendation=None,
            answer_text=None, source_document_id=None, metadata={},
            question_format="short_text", options=None, direction="user_to_jenny",
            created_at=now, answered_at=None,
        )
