"""Question reconciliation and profile-answer helpers for household finance."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdQuestion
from app.services.household_finance_rows import row_to_question


class HouseholdQuestionReconciler:
    """Keep household questions deduped, contextual, and profile-aware."""

    def reconcile_open_questions(self, service: Any) -> None:
        with service.storage.connection() as conn:
            answered_rows = conn.execute(
                """
                SELECT
                    q.id, q.field_name, q.status, q.priority, q.question, q.rationale,
                    q.answer_text, q.source_document_id, q.metadata, q.created_at, q.answered_at,
                    d.filename, d.source_type, d.document_type, d.account_label, d.review_summary, d.metadata
                FROM household_questions q
                LEFT JOIN household_documents d ON d.id = q.source_document_id
                WHERE q.status = 'answered'
                ORDER BY q.answered_at DESC NULLS LAST, q.created_at DESC
                """
            ).fetchall()
            open_rows = conn.execute(
                """
                SELECT
                    q.id, q.field_name, q.status, q.priority, q.question, q.rationale,
                    q.answer_text, q.source_document_id, q.metadata, q.created_at, q.answered_at,
                    d.filename, d.source_type, d.document_type, d.account_label, d.review_summary, d.metadata
                FROM household_questions q
                LEFT JOIN household_documents d ON d.id = q.source_document_id
                WHERE q.status = 'open'
                ORDER BY q.created_at ASC
                """
            ).fetchall()

            answered_questions = [
                row_to_question(row, iso=service._iso, iso_or_none=service._iso_or_none)
                for row in answered_rows
            ]
            open_questions = [
                row_to_question(row, iso=service._iso, iso_or_none=service._iso_or_none)
                for row in open_rows
            ]
            updated = False

            for answered_question in answered_questions:
                answer_text = (answered_question.answer_text or "").strip()
                if not answer_text:
                    continue
                answered_family = self.question_family(
                    answered_question.question,
                    answered_question.field_name,
                )
                answered_at = answered_question.answered_at or datetime.now(UTC).isoformat()

                for candidate_question in open_questions:
                    if candidate_question.status != "open":
                        continue
                    if not self.question_is_answered_by_context(
                        answered_question=answered_question,
                        candidate_question=candidate_question,
                        answer_text=answer_text,
                        answered_family=answered_family,
                    ):
                        continue

                    conn.execute(
                        """
                        UPDATE household_questions
                        SET status = 'answered',
                            answer_text = %s,
                            answered_at = %s,
                            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                        WHERE id = %s
                          AND status = 'open'
                        """,
                        [
                            answer_text,
                            answered_at,
                            json.dumps(
                                {
                                    "reconciled_from_question_id": answered_question.id,
                                    "reconciliation_reason": "answered_by_existing_context",
                                }
                            ),
                            candidate_question.id,
                        ],
                    )
                    candidate_question.status = "answered"
                    candidate_question.answer_text = answer_text
                    candidate_question.answered_at = answered_at
                    updated = True

            ranked_open_questions = sorted(open_questions, key=self.question_sort_key)
            for index, primary_question in enumerate(ranked_open_questions):
                if primary_question.status != "open":
                    continue
                for duplicate_question in ranked_open_questions[index + 1 :]:
                    if duplicate_question.status != "open":
                        continue
                    if not self.questions_are_semantic_duplicates(primary_question, duplicate_question):
                        continue

                    conn.execute(
                        """
                        UPDATE household_questions
                        SET status = 'dismissed',
                            answered_at = %s,
                            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                        WHERE id = %s
                          AND status = 'open'
                        """,
                        [
                            datetime.now(UTC).isoformat(),
                            json.dumps(
                                {
                                    "duplicate_of_question_id": primary_question.id,
                                    "reconciliation_reason": "duplicate_open_question",
                                }
                            ),
                            duplicate_question.id,
                        ],
                    )
                    duplicate_question.status = "dismissed"
                    updated = True

            for candidate_question in open_questions:
                if candidate_question.status != "open":
                    continue
                inferred_resolution = self.infer_question_resolution_from_existing_context(
                    service,
                    conn=conn,
                    question=candidate_question,
                )
                if inferred_resolution is None:
                    continue

                conn.execute(
                    """
                    UPDATE household_questions
                    SET status = 'dismissed',
                        answered_at = %s,
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                    WHERE id = %s
                      AND status = 'open'
                    """,
                    [
                        datetime.now(UTC).isoformat(),
                        json.dumps(inferred_resolution),
                        candidate_question.id,
                    ],
                )
                candidate_question.status = "dismissed"
                updated = True

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

        question_family = self.question_family(question.question, question.field_name)
        source_document_id = question.source_document_id
        account_label = self.clean_source_value(source_document.get("account_label"))
        account_hint = self.clean_source_value(source_document.get("account_hint"))
        merchant = self.clean_source_value(source_document.get("merchant"))

        if source_document_id is None and not any(
            isinstance(value, str) and value.strip()
            for value in [account_label, account_hint, merchant]
        ):
            return

        conn.execute(
            """
            UPDATE household_questions AS q
            SET status = 'answered',
                answer_text = %s,
                answered_at = %s
            FROM household_documents AS d
            WHERE q.source_document_id = d.id
              AND q.status = 'open'
              AND q.id <> %s
              AND q.question = %s
              AND COALESCE(q.field_name, '') = COALESCE(%s, '')
              AND (
                    q.source_document_id = %s
                    OR (
                        %s IS NOT NULL
                        AND d.account_label = %s
                    )
                    OR (
                        %s IS NOT NULL
                        AND d.metadata->'structured_data'->>'account_hint' = %s
                    )
                    OR (
                        %s IS NOT NULL
                        AND d.metadata->'structured_data'->>'merchant' = %s
                    )
                  )
            """,
            [
                answer_text,
                answered_at,
                question.id,
                question.question,
                question.field_name,
                source_document_id,
                account_label if isinstance(account_label, str) and account_label else None,
                account_label if isinstance(account_label, str) and account_label else None,
                account_hint if isinstance(account_hint, str) and account_hint else None,
                account_hint if isinstance(account_hint, str) and account_hint else None,
                merchant if isinstance(merchant, str) and merchant else None,
                merchant if isinstance(merchant, str) and merchant else None,
            ],
        )

        related_rows = conn.execute(
            """
            SELECT
                q.id, q.field_name, q.status, q.priority, q.question, q.rationale,
                q.answer_text, q.source_document_id, q.metadata, q.created_at, q.answered_at,
                d.filename, d.source_type, d.document_type, d.account_label, d.review_summary, d.metadata
            FROM household_questions q
            LEFT JOIN household_documents d ON d.id = q.source_document_id
            WHERE q.status = 'open'
              AND q.id <> %s
            ORDER BY q.created_at ASC
            """,
            [question.id],
        ).fetchall()

        for row in related_rows:
            candidate = row_to_question(row, iso=service._iso, iso_or_none=service._iso_or_none)
            if not self.question_is_answered_by_context(
                answered_question=question,
                candidate_question=candidate,
                answer_text=answer_text,
                answered_family=question_family,
            ):
                continue

            conn.execute(
                """
                UPDATE household_questions
                SET status = 'answered',
                    answer_text = %s,
                    answered_at = %s,
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
                  AND status = 'open'
                """,
                [
                    answer_text,
                    answered_at,
                    json.dumps(
                        {
                            "reconciled_from_question_id": question.id,
                            "reconciliation_reason": "answered_by_existing_context",
                        }
                    ),
                    candidate.id,
                ],
            )

    def question_is_answered_by_context(
        self,
        *,
        answered_question: HouseholdQuestion,
        candidate_question: HouseholdQuestion,
        answer_text: str,
        answered_family: str,
    ) -> bool:
        shares_context = self.questions_share_source_context(answered_question, candidate_question)
        candidate_family = self.question_family(
            candidate_question.question,
            candidate_question.field_name,
        )
        normalized_answer = answer_text.strip().lower()
        is_covered = False
        is_same_question = (
            candidate_question.question == answered_question.question
            and candidate_question.field_name == answered_question.field_name
        )
        family_tokens = {
            "core_spending": [
                "yes",
                "main household",
                "primary account",
                "regular bills",
                "core household",
                "everyday spending",
                "cash flow",
            ],
            "shopping_channel": [
                "yes",
                "recurring",
                "regular household",
                "grocer",
                "consumable",
                "home goods",
                "weekly",
                "monthly",
            ],
        }
        negative_tokens = {
            "core_spending": [
                "no",
                "side account",
                "occasional transfers",
                "occasional transfer",
                "secondary account",
                "not primary",
                "not our main",
            ],
            "shopping_channel": [
                "no",
                "one-off",
                "one off",
                "rarely",
                "occasional",
                "not regular",
            ],
        }
        if (
            shares_context
            and candidate_family != "unknown"
            and answered_family != "unknown"
            and candidate_family == answered_family
            and len(normalized_answer) >= 3
        ):
            if (is_same_question and len(normalized_answer) >= 8) or answered_family == "retirement_target":
                is_covered = True
            elif answered_family == "document_role":
                is_covered = len(normalized_answer) >= 8
            else:
                tokens = family_tokens.get(answered_family, [])
                negatives = negative_tokens.get(answered_family, [])
                has_negative_signal = any(
                    token == normalized_answer
                    or normalized_answer.startswith(f"{token} ")
                    or normalized_answer.startswith(f"{token},")
                    or f" {token} " in normalized_answer
                    or normalized_answer.endswith(f" {token}")
                    for token in negatives
                )
                is_covered = has_negative_signal or any(token in normalized_answer for token in tokens)
        return is_covered

    def questions_are_semantic_duplicates(
        self,
        first: HouseholdQuestion,
        second: HouseholdQuestion,
    ) -> bool:
        if not self.questions_share_source_context(first, second):
            return False

        first_family = self.question_family(first.question, first.field_name)
        second_family = self.question_family(second.question, second.field_name)
        if first_family == "unknown" or second_family == "unknown":
            return False
        if first_family != second_family:
            return False
        if first.question == second.question and first.field_name == second.field_name:
            return True
        return first_family in {"core_spending", "shopping_channel", "document_role"}

    def question_sort_key(self, question: HouseholdQuestion) -> tuple[int, str]:
        priority_rank = {"high": 0, "medium": 1, "low": 2}.get(question.priority, 3)
        return (priority_rank, question.created_at)

    def questions_share_source_context(
        self,
        first: HouseholdQuestion,
        second: HouseholdQuestion,
    ) -> bool:
        if first.source_document_id is not None and first.source_document_id == second.source_document_id:
            return True

        first_source = first.metadata.get("source_document")
        second_source = second.metadata.get("source_document")
        if not isinstance(first_source, dict) or not isinstance(second_source, dict):
            return False

        for key in ["account_label", "account_hint", "merchant"]:
            first_value = self.clean_source_value(first_source.get(key))
            second_value = self.clean_source_value(second_source.get(key))
            if first_value and second_value and first_value == second_value:
                return True
        return False

    def question_family(self, question_text: str, field_name: str | None) -> str:
        normalized = question_text.lower()
        if field_name == "monthly_essential_target" and any(
            phrase in normalized
            for phrase in [
                "primary account",
                "monthly bills",
                "budget tracking",
                "core monthly household spending",
                "core household spending",
                "budget-driving",
            ]
        ):
            return "core_spending"
        if "regular household spending" in normalized or "recurring household shopping channel" in normalized:
            return "shopping_channel"
        if "how often does the household shop" in normalized or "weekly, bi-weekly" in normalized:
            return "merchant_cadence"
        if field_name in {"target_retirement_age", "target_retirement_spend"}:
            return "retirement_target"
        if "what role should this document play" in normalized:
            return "document_role"
        return "unknown"

    def infer_question_resolution_from_existing_context(
        self,
        service: Any,
        *,
        conn: Any,
        question: HouseholdQuestion,
    ) -> dict[str, object] | None:
        del conn
        question_family = self.question_family(question.question, question.field_name)
        if question_family != "merchant_cadence":
            return None

        source_document = question.metadata.get("source_document")
        if not isinstance(source_document, dict):
            return None
        merchant = source_document.get("merchant")
        if not isinstance(merchant, str) or not merchant.strip():
            return None

        cadence = service.transaction_service.infer_merchant_cadence(merchant=merchant)
        if cadence is None:
            return None

        return {
            "inferred_resolution": "merchant_cadence_from_existing_context",
            "inferred_answer": cadence["label"],
            "inferred_confidence": cadence["confidence"],
            "inferred_rationale": cadence["rationale"],
        }

    def clean_source_value(self, value: object) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = value.strip().lower()
        return cleaned or None

    def apply_answer_to_profile(self, service: Any, question: HouseholdQuestion, answer_text: str) -> None:
        cleaned_answer = answer_text.strip()
        if not cleaned_answer:
            return

        parsed_value = None
        updates: dict[str, Any] = {}
        if question.field_name in service.FIELD_LABELS:
            parsed_value = self.parse_answer_value(question.field_name, cleaned_answer)
            if parsed_value is not None:
                updates[question.field_name] = parsed_value

        if not updates:
            return

        now = datetime.now(UTC).isoformat()
        profile = service.get_profile()
        set_clauses = ", ".join(f"{field} = %s" for field in updates)
        params: list[Any] = list(updates.values())
        params.extend([now, profile.id])
        with service.storage.connection() as conn:
            conn.execute(
                f"""
                UPDATE household_profiles
                SET {set_clauses}, updated_at = %s
                WHERE id = %s
                """,
                params,
            )
            if question.field_name:
                conn.execute(
                    """
                    UPDATE household_inferred_values
                    SET value_text = %s,
                        status = 'confirmed',
                        updated_at = %s,
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                    WHERE field_name = %s
                    """,
                    [
                        str(parsed_value),
                        now,
                        json.dumps({"confirmed_by_question_id": question.id}),
                        question.field_name,
                    ],
                )
            conn.commit()

    def parse_answer_value(self, field_name: str, answer_text: str) -> float | int | None:
        normalized = answer_text.replace(",", "").replace("$", "").strip().lower()
        match = re.search(r"-?\d+(?:\.\d+)?", normalized)
        if match is None:
            return None
        number = float(match.group(0))
        if field_name == "target_retirement_age":
            return round(number)
        return round(number, 2)
