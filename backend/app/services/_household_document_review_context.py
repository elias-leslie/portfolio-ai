"""Household document review context lookup helpers."""

from __future__ import annotations

import re
from typing import Any

_CONTEXT_STOPWORDS = frozenset(
    {
        "account",
        "accounts",
        "activity",
        "amount",
        "balance",
        "cash",
        "date",
        "details",
        "document",
        "history",
        "management",
        "member",
        "plan",
        "positions",
        "recent",
        "statement",
        "summary",
        "total",
        "transaction",
        "transactions",
        "uploaded",
        "view",
    }
)


class HouseholdDocumentContextMixin:
    storage: Any

    def _build_household_context(
        self,
        *,
        baseline_review: dict[str, Any],
        extracted_text: str | None,
    ) -> dict[str, Any] | None:
        structured_data = baseline_review.get("structured_data")
        structured = structured_data if isinstance(structured_data, dict) else {}
        source_type = str(baseline_review.get("source_type") or "").strip()
        institution_hint = str(
            structured.get("provider_name")
            or structured.get("institution_name")
            or structured.get("merchant")
            or ""
        ).strip()
        account_hint = str(structured.get("account_hint") or "").strip()
        owner_hint = str(structured.get("owner_name") or "").strip()
        signal_text = " ".join(
            part
            for part in (
                institution_hint,
                account_hint,
                owner_hint,
                (extracted_text or "")[:4000],
            )
            if part
        )
        hint_tokens = {
            token
            for token in re.findall(r"[a-z0-9]{3,}", signal_text.lower())
            if token not in _CONTEXT_STOPWORDS
        }
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    a.id,
                    a.canonical_label,
                    a.source_type,
                    a.asset_group,
                    a.account_type,
                    a.institution_name,
                    a.owner_name,
                    a.account_mask,
                    a.primary_identity_key,
                    COALESCE(MAX(e.as_of_date)::text, NULL) AS last_as_of_date,
                    COUNT(DISTINCT e.id) AS evidence_count
                FROM household_accounts a
                LEFT JOIN household_evidence_accounts e ON e.household_account_id = a.id
                GROUP BY
                    a.id,
                    a.canonical_label,
                    a.source_type,
                    a.asset_group,
                    a.account_type,
                    a.institution_name,
                    a.owner_name,
                    a.account_mask,
                    a.primary_identity_key,
                    a.updated_at
                ORDER BY MAX(e.as_of_date) DESC NULLS LAST, a.updated_at DESC
                LIMIT 64
                """
            ).fetchall()
        if not rows:
            return None

        ranked: list[tuple[int, Any]] = []
        for row in rows:
            haystack = " ".join(str(value or "") for value in row[1:9]).lower()
            row_tokens = {
                token
                for token in re.findall(r"[a-z0-9]{3,}", haystack)
                if token not in _CONTEXT_STOPWORDS
            }
            score = 0
            if source_type and str(row[2] or "") == source_type:
                score += 5
            if institution_hint and institution_hint.lower() in haystack:
                score += 4
            if account_hint and account_hint.lower() in haystack:
                score += 3
            if owner_hint and owner_hint.lower().split(" ")[0] in haystack:
                score += 2
            score += len(hint_tokens & row_tokens) * 2
            ranked.append((score, row))

        ranked.sort(key=lambda item: item[0], reverse=True)
        selected_rows = [row for score, row in ranked if score > 0][:8]
        if not selected_rows:
            selected_rows = [
                row
                for _, row in ranked
                if not source_type or str(row[2] or "") == source_type
            ][:6] or [row for _, row in ranked[:6]]

        account_ids = [str(row[0]) for row in selected_rows]
        identity_examples: dict[str, list[str]] = {account_id: [] for account_id in account_ids}
        recent_evidence_examples: list[dict[str, Any]] = []
        with self.storage.connection() as conn:
            identity_rows = conn.execute(
                """
                SELECT household_account_id, identity_key
                FROM household_account_identities
                WHERE household_account_id = ANY(%s)
                ORDER BY is_primary DESC, confidence DESC NULLS LAST, updated_at DESC
                """,
                [account_ids],
            ).fetchall()
            evidence_rows = conn.execute(
                """
                SELECT
                    e.household_account_id,
                    d.filename,
                    d.source_type,
                    d.document_type,
                    d.review_summary,
                    e.account_name,
                    e.owner_name,
                    e.account_mask,
                    e.as_of_date
                FROM household_evidence_accounts e
                JOIN household_documents d ON d.id = e.document_id
                WHERE e.household_account_id = ANY(%s)
                ORDER BY e.as_of_date DESC NULLS LAST, d.uploaded_at DESC
                LIMIT 12
                """,
                [account_ids],
            ).fetchall()
        for account_id, identity_key in identity_rows:
            key = str(account_id)
            values = identity_examples.setdefault(key, [])
            text = str(identity_key or "").strip()
            if text and text not in values and len(values) < 3:
                values.append(text)
        for row in evidence_rows:
            recent_evidence_examples.append(
                {
                    "household_account_id": str(row[0]),
                    "filename": str(row[1] or ""),
                    "source_type": str(row[2] or ""),
                    "document_type": str(row[3] or ""),
                    "review_summary": str(row[4] or "") or None,
                    "account_name": str(row[5] or "") or None,
                    "owner_name": str(row[6] or "") or None,
                    "account_mask": str(row[7] or "") or None,
                    "as_of_date": str(row[8] or "") or None,
                }
            )

        related_accounts = [
            {
                "household_account_id": str(row[0]),
                "canonical_label": str(row[1] or ""),
                "source_type": str(row[2] or ""),
                "asset_group": str(row[3] or ""),
                "account_type": str(row[4] or ""),
                "institution_name": str(row[5] or "") or None,
                "owner_name": str(row[6] or "") or None,
                "account_mask": str(row[7] or "") or None,
                "primary_identity_key": str(row[8] or "") or None,
                "last_as_of_date": str(row[9] or "") or None,
                "evidence_count": int(row[10] or 0),
                "identity_examples": identity_examples.get(str(row[0]), []),
            }
            for row in selected_rows
        ]
        return {
            "household_account_count": len(rows),
            "related_accounts": related_accounts,
            "recent_related_evidence": recent_evidence_examples,
        }
