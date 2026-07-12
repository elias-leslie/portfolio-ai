"""Question reconciliation and profile-answer helpers for household finance."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdQuestion
from app.services._household_account_status import (
    account_context_indicates_closed,
    metadata_indicates_closed,
)
from app.services._household_finance_utils import iso, iso_or_none
from app.services.household_finance_rows import FIELD_LABELS, row_to_question
from app.services.household_question_classifier import (
    answer_covers_family,
    clean_source_value,
    parse_answer_value,
    question_family,
    question_sort_key,
    questions_share_source_context,
)

__all__ = [
    "HouseholdQuestionReconciler",
    # Re-exported so existing `from household_question_reconciler import X` callers still work.
    "clean_source_value",
    "parse_answer_value",
    "question_family",
    "question_sort_key",
    "questions_share_source_context",
]

_COLS = (
    "q.id, q.field_name, q.status, q.priority, q.question, q.rationale, "
    "q.answer_text, q.source_document_id, q.metadata, q.question_format, q.options, q.direction, "
    "q.created_at, q.answered_at, d.filename, d.source_type, d.document_type, "
    "d.account_label, d.review_summary, d.metadata"
)
_JOIN = "FROM household_questions q LEFT JOIN household_documents d ON d.id = q.source_document_id"


def _fetch_questions(
    conn: Any, where: str, order: str, params: list[Any] | None = None
) -> list[HouseholdQuestion]:
    rows = conn.execute(f"SELECT {_COLS} {_JOIN} WHERE {where} ORDER BY {order}", params or []).fetchall()
    return [row_to_question(row, iso=iso, iso_or_none=iso_or_none) for row in rows]


def _mark_answered(conn: Any, question_id: str, answer_text: str, answered_at: str, source_id: str) -> None:
    conn.execute(
        "UPDATE household_questions SET status='answered', answer_text=%s, answered_at=%s,"
        " metadata=COALESCE(metadata,'{}'::jsonb)||%s::jsonb WHERE id=%s AND status='open'",
        [
            answer_text,
            answered_at,
            json.dumps(
                {"reconciled_from_question_id": source_id, "reconciliation_reason": "answered_by_existing_context"}
            ),
            question_id,
        ],
    )


def _mark_dismissed(conn: Any, question_id: str, primary_id: str, reason: str) -> None:
    conn.execute(
        "UPDATE household_questions SET status='dismissed', answered_at=%s,"
        " metadata=COALESCE(metadata,'{}'::jsonb)||%s::jsonb WHERE id=%s AND status='open'",
        [
            datetime.now(UTC).isoformat(),
            json.dumps({"duplicate_of_question_id": primary_id, "reconciliation_reason": reason}),
            question_id,
        ],
    )


def _bulk_answer_related(
    conn: Any,
    question: HouseholdQuestion,
    answer_text: str,
    answered_at: str,
    account_label: str | None,
    account_hint: str | None,
    merchant: str | None,
) -> None:
    conn.execute(
        """
        UPDATE household_questions AS q
        SET status = 'answered', answer_text = %s, answered_at = %s
        FROM household_documents AS d
        WHERE q.source_document_id = d.id AND q.status = 'open' AND q.id <> %s
          AND q.question = %s AND COALESCE(q.field_name, '') = COALESCE(%s, '')
          AND (
                q.source_document_id = %s
                OR (%s::text IS NOT NULL AND d.account_label = %s)
                OR (%s::text IS NOT NULL AND d.metadata->'structured_data'->>'account_hint' = %s)
                OR (%s::text IS NOT NULL AND d.metadata->'structured_data'->>'merchant' = %s)
              )
        """,
        [
            answer_text, answered_at, question.id, question.question, question.field_name,
            question.source_document_id,
            account_label or None, account_label or None,
            account_hint or None, account_hint or None,
            merchant or None, merchant or None,
        ],
    )


def _mark_closed_context_dismissed(conn: Any, question_id: str) -> None:
    conn.execute(
        "UPDATE household_questions SET status='dismissed', answered_at=%s,"
        " metadata=COALESCE(metadata,'{}'::jsonb)||%s::jsonb WHERE id=%s AND status='open'",
        [
            datetime.now(UTC).isoformat(),
            json.dumps({"reconciliation_reason": "closed_account_context"}),
            question_id,
        ],
    )


def _question_allows_closed_account_dismissal(question: HouseholdQuestion) -> bool:
    q_family = question_family(question.question, question.field_name)
    if q_family in {"core_spending", "document_role"}:
        return True
    if question.field_name == "account_hint":
        return True
    normalized = question.question.lower()
    return "source account" in normalized and ("csv" in normalized or "export" in normalized)


def _question_label_context_is_closed(question: HouseholdQuestion) -> bool:
    source_document = question.metadata.get("source_document")
    if not isinstance(source_document, dict):
        return False
    return account_context_indicates_closed(
        labels=(
            source_document.get("account_label"),
            source_document.get("account_hint"),
            source_document.get("filename"),
        )
    )


def _source_document_linked_accounts_are_closed(conn: Any, question: HouseholdQuestion) -> bool:
    if question.source_document_id is None:
        return False
    rows = conn.execute(
        """
        SELECT
            ea.household_account_id::text,
            ea.account_name,
            ea.institution_name,
            ea.account_mask,
            ea.metadata,
            ha.canonical_label,
            ha.institution_name,
            ha.account_mask,
            ha.metadata,
            d.account_label,
            d.metadata
        FROM household_evidence_accounts ea
        LEFT JOIN household_accounts ha ON ha.id = ea.household_account_id
        LEFT JOIN household_documents d ON d.id = ea.document_id
        WHERE ea.document_id = %s
        """,
        [question.source_document_id],
    ).fetchall()
    linked_rows = [row for row in rows if row[0] is not None]
    if not linked_rows:
        return False
    for row in linked_rows:
        evidence_closed = account_context_indicates_closed(
            metadata=row[4],
            labels=(row[1], row[2], row[3]),
        )
        canonical_closed = account_context_indicates_closed(
            metadata=row[8],
            labels=(row[5], row[6], row[7]),
        )
        document_closed = metadata_indicates_closed(row[10]) or account_context_indicates_closed(
            labels=(row[9],)
        )
        if not (evidence_closed or canonical_closed or document_closed):
            return False
    return True


# ---------------------------------------------------------------------------
# Main reconciler class
# ---------------------------------------------------------------------------


class HouseholdQuestionReconciler:
    """Keep household questions deduped, contextual, and profile-aware."""

    def parse_answer_value(self, field_name: str, answer_text: str) -> str | float | int | None:
        return parse_answer_value(field_name, answer_text)

    def question_is_answered_by_context(
        self,
        *,
        answered_question: HouseholdQuestion,
        candidate_question: HouseholdQuestion,
        answer_text: str,
        answered_family: str,
    ) -> bool:
        if not questions_share_source_context(answered_question, candidate_question):
            return False
        candidate_family = question_family(candidate_question.question, candidate_question.field_name)
        normalized = answer_text.strip().lower()
        if candidate_family == "unknown" or answered_family == "unknown" or candidate_family != answered_family:
            return False
        if len(normalized) < 3:
            return False
        is_same = (
            candidate_question.question == answered_question.question
            and candidate_question.field_name == answered_question.field_name
        )
        if (is_same and len(normalized) >= 8) or answered_family == "retirement_target":
            return True
        if answered_family == "document_role":
            return len(normalized) >= 8
        return answer_covers_family(normalized, answered_family)

    def questions_are_semantic_duplicates(self, first: HouseholdQuestion, second: HouseholdQuestion) -> bool:
        if not questions_share_source_context(first, second):
            return False
        first_family = question_family(first.question, first.field_name)
        second_family = question_family(second.question, second.field_name)
        if first_family == "unknown" or second_family == "unknown" or first_family != second_family:
            return False
        if first.question == second.question and first.field_name == second.field_name:
            return True
        return first_family in {"core_spending", "shopping_channel", "document_role"}

    def infer_question_resolution_from_existing_context(
        self,
        service: Any,
        *,
        conn: Any,
        question: HouseholdQuestion,
    ) -> dict[str, object] | None:
        if question_family(question.question, question.field_name) != "merchant_cadence":
            return None
        source_document = question.metadata.get("source_document")
        if not isinstance(source_document, dict):
            return None
        merchant = source_document.get("merchant")
        if not isinstance(merchant, str) or not merchant.strip():
            return None
        cadence = service.transaction_service.infer_merchant_cadence(
            merchant=merchant,
            conn=conn,
        )
        if cadence is None:
            return None
        return {
            "inferred_resolution": "merchant_cadence_from_existing_context",
            "inferred_answer": cadence["label"],
            "inferred_confidence": cadence["confidence"],
            "inferred_rationale": cadence["rationale"],
        }

    def reconcile_open_questions(self, service: Any) -> None:
        with service.storage.connection() as conn:
            answered = _fetch_questions(conn, "q.status='answered'", "q.answered_at DESC NULLS LAST, q.created_at DESC")
            open_qs = _fetch_questions(conn, "q.status='open'", "q.created_at ASC")
            updated = self._apply_answered_context(conn, answered, open_qs)
            updated |= self._dismiss_duplicates(conn, open_qs)
            updated |= self._dismiss_inferred(service, conn, open_qs)
            updated |= self._dismiss_closed_account_questions(conn, open_qs)
            if updated:
                conn.commit()

    def resolve_related_open_questions(
        self,
        service: Any,
        *,
        conn: Any,
        question: HouseholdQuestion,
        answer_text: str,
        answered_at: str,
    ) -> None:
        source_document = question.metadata.get("source_document")
        if not isinstance(source_document, dict):
            return
        account_label = clean_source_value(source_document.get("account_label"))
        account_hint = clean_source_value(source_document.get("account_hint"))
        merchant = clean_source_value(source_document.get("merchant"))
        if question.source_document_id is None and not any(
            isinstance(v, str) and v.strip() for v in [account_label, account_hint, merchant]
        ):
            return
        _bulk_answer_related(conn, question, answer_text, answered_at, account_label, account_hint, merchant)
        q_family = question_family(question.question, question.field_name)
        for row in _fetch_questions(conn, "q.status='open' AND q.id<>%s", "q.created_at ASC", [question.id]):
            if self.question_is_answered_by_context(
                answered_question=question, candidate_question=row,
                answer_text=answer_text, answered_family=q_family,
            ):
                _mark_answered(conn, row.id, answer_text, answered_at, question.id)

    def apply_answer_to_profile(self, service: Any, question: HouseholdQuestion, answer_text: str) -> None:
        cleaned = answer_text.strip()
        if not cleaned or question.field_name not in FIELD_LABELS:
            return
        column = question.field_name
        allowed_columns = set(FIELD_LABELS.keys())
        if column not in allowed_columns:
            raise ValueError(f"Column '{column}' is not an allowed profile column.")
        parsed_value = parse_answer_value(column, cleaned)
        if parsed_value is None:
            return
        now = datetime.now(UTC).isoformat()
        profile = service.get_profile()
        with service.storage.connection() as conn:
            conn.execute(
                f"UPDATE household_profiles SET {column} = %s, updated_at = %s WHERE id = %s",
                [parsed_value, now, profile.id],
            )
            if question.field_name:
                conn.execute(
                    """
                    UPDATE household_inferred_values
                    SET value_text=%s, status='confirmed', updated_at=%s,
                        metadata=COALESCE(metadata,'{}'::jsonb)||%s::jsonb
                    WHERE field_name=%s
                    """,
                    [str(parsed_value), now, json.dumps({"confirmed_by_question_id": question.id}), question.field_name],
                )
            conn.commit()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_answered_context(
        self, conn: Any, answered_questions: list[HouseholdQuestion], open_questions: list[HouseholdQuestion]
    ) -> bool:
        """Mark open questions answered when existing context covers them.

        Intentionally mutates candidate objects in-place (status, answer_text,
        answered_at) so that subsequent helpers in the same reconciliation pass
        see the updated state and skip already-resolved candidates. This matches
        the mutation pattern used by _dismiss_duplicates and _dismiss_inferred.
        """
        updated = False
        for answered in answered_questions:
            answer_text = (answered.answer_text or "").strip()
            if not answer_text:
                continue
            answered_family = question_family(answered.question, answered.field_name)
            answered_at = answered.answered_at or datetime.now(UTC).isoformat()
            for candidate in open_questions:
                if candidate.status != "open":
                    continue
                if not self.question_is_answered_by_context(
                    answered_question=answered, candidate_question=candidate,
                    answer_text=answer_text, answered_family=answered_family,
                ):
                    continue
                _mark_answered(conn, candidate.id, answer_text, answered_at, answered.id)
                candidate.status = "answered"
                candidate.answer_text = answer_text
                candidate.answered_at = answered_at
                updated = True
        return updated

    def _dismiss_duplicates(self, conn: Any, open_questions: list[HouseholdQuestion]) -> bool:
        updated = False
        ranked = sorted(open_questions, key=question_sort_key)
        for idx, primary in enumerate(ranked):
            if primary.status != "open":
                continue
            for duplicate in ranked[idx + 1 :]:
                if duplicate.status != "open":
                    continue
                if not self.questions_are_semantic_duplicates(primary, duplicate):
                    continue
                _mark_dismissed(conn, duplicate.id, primary.id, "duplicate_open_question")
                duplicate.status = "dismissed"
                updated = True
        return updated

    def _dismiss_inferred(self, service: Any, conn: Any, open_questions: list[HouseholdQuestion]) -> bool:
        updated = False
        for candidate in open_questions:
            if candidate.status != "open":
                continue
            resolution = self.infer_question_resolution_from_existing_context(service, conn=conn, question=candidate)
            if resolution is None:
                continue
            conn.execute(
                "UPDATE household_questions SET status='dismissed', answered_at=%s,"
                " metadata=COALESCE(metadata,'{}'::jsonb)||%s::jsonb WHERE id=%s AND status='open'",
                [datetime.now(UTC).isoformat(), json.dumps(resolution), candidate.id],
            )
            candidate.status = "dismissed"
            updated = True
        return updated

    def _dismiss_closed_account_questions(
        self,
        conn: Any,
        open_questions: list[HouseholdQuestion],
    ) -> bool:
        updated = False
        for candidate in open_questions:
            if candidate.status != "open":
                continue
            if not _question_allows_closed_account_dismissal(candidate):
                continue
            if not (
                _question_label_context_is_closed(candidate)
                or _source_document_linked_accounts_are_closed(conn, candidate)
            ):
                continue
            _mark_closed_context_dismissed(conn, candidate.id)
            candidate.status = "dismissed"
            updated = True
        return updated
