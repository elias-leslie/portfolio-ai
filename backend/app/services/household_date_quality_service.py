"""Mutations for household transaction date-quality issues."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.household_finance import HouseholdTransactionDateIssueResolution

_RESOLUTION_STATUSES = {
    "date_confirmed_future": "resolved",
    "corrected_evidence_uploaded": "superseded",
    "not_current_transaction": "excluded",
}

_WALMART_ORDER_RE = re.compile(r"walmart\.com/orders/([A-Za-z0-9]+)", re.IGNORECASE)
_ORDER_NUMBER_RE = re.compile(r"\bOrder#\s*([0-9-]+)", re.IGNORECASE)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _document_issue_id(issue_id: str) -> str | None:
    if not issue_id.startswith("future-date-document-"):
        return None
    document_id, separator, index = issue_id.removeprefix("future-date-document-").rpartition("-")
    if not separator or not document_id or not index.isdigit():
        return None
    return document_id


def _transaction_issue_id(issue_id: str) -> str | None:
    if issue_id.startswith("future-date-document-"):
        return None
    if not issue_id.startswith("future-date-"):
        return None
    transaction_id = issue_id.removeprefix("future-date-").strip()
    return transaction_id or None


class HouseholdDateQualityService:
    """Resolve or supersede future-date issues without losing provenance."""

    def resolve_issue(
        self,
        service: Any,
        *,
        issue_id: str,
        payload: HouseholdTransactionDateIssueResolution,
    ) -> bool:
        resolution = payload.resolution.strip()
        status = _RESOLUTION_STATUSES.get(resolution)
        if status is None:
            raise ValueError(f"Unsupported date issue resolution: {resolution}")

        patch = self._resolution_patch(
            status=status,
            resolution=resolution,
            issue_id=issue_id,
            note=payload.note,
        )
        document_id = _document_issue_id(issue_id)
        transaction_id = _transaction_issue_id(issue_id)
        if document_id is None and transaction_id is None:
            return False

        with service.storage.connection() as conn:
            if document_id is not None:
                updated = self._update_document_summary(
                    conn,
                    document_id=document_id,
                    patch=patch,
                )
                if status in {"superseded", "excluded"}:
                    self._update_document_future_transactions(
                        conn,
                        document_id=document_id,
                        patch=patch,
                    )
            else:
                updated = self._update_transaction_resolution(
                    conn,
                    transaction_id=str(transaction_id),
                    patch=patch,
                )
            if updated:
                conn.commit()
            return updated

    def mark_replaced_document(
        self,
        service: Any,
        *,
        replaced_document_id: str,
        replacement_document_id: str,
        issue_id: str | None = None,
        reason: str = "corrected_evidence_uploaded",
    ) -> bool:
        patch = self._resolution_patch(
            status="superseded",
            resolution=reason,
            issue_id=issue_id,
            replacement_document_id=replacement_document_id,
        )
        with service.storage.connection() as conn:
            updated = self._update_document_summary(
                conn,
                document_id=replaced_document_id,
                patch=patch,
            )
            self._update_document_future_transactions(
                conn,
                document_id=replaced_document_id,
                patch=patch,
            )
            if updated:
                conn.commit()
            return updated

    def supersede_matching_document_issues(
        self,
        service: Any,
        *,
        replacement_document_id: str,
        reviewed: dict[str, Any],
    ) -> int:
        replacement = _receipt_fingerprint(
            extracted_text=str(reviewed.get("extracted_text") or ""),
            structured_data=reviewed.get("structured_data"),
        )
        if replacement is None:
            return 0

        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    d.id,
                    d.metadata->'date_quality_summary'->'future_transactions',
                    COALESCE(r.extracted_text, d.metadata->'structured_data'->>'text_preview', ''),
                    COALESCE(r.structured_data, d.metadata->'structured_data', '{}'::jsonb)
                FROM household_documents d
                LEFT JOIN LATERAL (
                    SELECT extracted_text, structured_data
                    FROM household_document_reviews
                    WHERE document_id = d.id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) r ON TRUE
                WHERE d.id <> %s
                  AND d.source_type = 'receipt'
                  AND d.metadata->'date_quality_summary'->>'status' = 'needs_review'
                """,
                [replacement_document_id],
            ).fetchall()

            updated = 0
            for row in rows:
                document_id = str(row[0])
                future_transactions = row[1] if isinstance(row[1], list) else []
                candidate = _receipt_fingerprint(
                    extracted_text=str(row[2] or ""),
                    structured_data=row[3],
                    future_transactions=future_transactions,
                )
                if candidate is None or not _same_receipt(candidate, replacement):
                    continue
                patch = self._resolution_patch(
                    status="superseded",
                    resolution="corrected_evidence_uploaded",
                    issue_id=f"future-date-document-{document_id}-0",
                    replacement_document_id=replacement_document_id,
                )
                if self._update_document_summary(conn, document_id=document_id, patch=patch):
                    self._update_document_future_transactions(
                        conn,
                        document_id=document_id,
                        patch=patch,
                    )
                    updated += 1
            if updated:
                conn.commit()
            return updated

    def _resolution_patch(
        self,
        *,
        status: str,
        resolution: str,
        issue_id: str | None = None,
        note: str | None = None,
        replacement_document_id: str | None = None,
    ) -> dict[str, str]:
        patch = {
            "status": status,
            "resolution": resolution,
            "resolved_at": _utc_now(),
        }
        if issue_id:
            patch["resolved_issue_id"] = issue_id
        if note and note.strip():
            patch["resolution_note"] = note.strip()
        if replacement_document_id:
            patch["replacement_document_id"] = replacement_document_id
        return patch

    def _update_document_summary(self, conn: Any, *, document_id: str, patch: dict[str, str]) -> bool:
        row = conn.execute(
            """
            UPDATE household_documents
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'::jsonb),
                '{date_quality_summary}',
                COALESCE(metadata->'date_quality_summary', '{}'::jsonb) || %s::jsonb,
                true
            )
            WHERE id = %s
            RETURNING id
            """,
            [json.dumps(patch), document_id],
        ).fetchone()
        return row is not None

    def _update_transaction_resolution(
        self,
        conn: Any,
        *,
        transaction_id: str,
        patch: dict[str, str],
    ) -> bool:
        row = conn.execute(
            """
            UPDATE household_transactions
            SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
            WHERE id = %s
            RETURNING id
            """,
            [json.dumps({"date_quality_resolution": patch}), transaction_id],
        ).fetchone()
        return row is not None

    def _update_document_future_transactions(
        self,
        conn: Any,
        *,
        document_id: str,
        patch: dict[str, str],
    ) -> None:
        conn.execute(
            """
            UPDATE household_transactions
            SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
            WHERE document_id = %s
              AND transaction_date > CURRENT_DATE
            """,
            [json.dumps({"date_quality_resolution": patch}), document_id],
        )


def _receipt_fingerprint(
    *,
    extracted_text: str,
    structured_data: Any,
    future_transactions: list[dict[str, Any]] | None = None,
) -> dict[str, object] | None:
    data = structured_data if isinstance(structured_data, dict) else {}
    preview = data.get("text_preview")
    haystack = "\n".join(
        value
        for value in (
            extracted_text,
            str(preview) if isinstance(preview, str) else "",
        )
        if value
    )
    order_key = _extract_receipt_order_key(haystack)
    if not order_key:
        return None

    amount = _parse_amount(data.get("total_amount"))
    if amount is None and future_transactions:
        for transaction in future_transactions:
            amount = _parse_amount(transaction.get("amount"))
            if amount is not None:
                break
    if amount is None:
        return None
    return {"order_key": order_key, "amount": amount}


def _extract_receipt_order_key(text: str) -> str | None:
    walmart_match = _WALMART_ORDER_RE.search(text)
    if walmart_match:
        return f"walmart:{walmart_match.group(1)}"
    order_match = _ORDER_NUMBER_RE.search(text)
    if order_match:
        return f"order:{order_match.group(1).replace('-', '')}"
    return None


def _parse_amount(value: object) -> Decimal | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if not cleaned:
        return None
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _same_receipt(candidate: dict[str, object], replacement: dict[str, object]) -> bool:
    return (
        candidate.get("order_key") == replacement.get("order_key")
        and candidate.get("amount") == replacement.get("amount")
    )
