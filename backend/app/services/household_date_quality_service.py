"""Mutations for household transaction date-quality issues."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdTransactionDateIssueResolution

_RESOLUTION_STATUSES = {
    "date_confirmed_future": "resolved",
    "corrected_evidence_uploaded": "superseded",
    "not_current_transaction": "excluded",
}


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
