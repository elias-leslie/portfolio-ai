"""Read-only ledger and provenance view for household finance."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdLedger, HouseholdLedgerEntry
from app.services._household_finance_utils import iso_or_none


def _coerce_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _metadata_account_label(metadata: dict[str, Any]) -> str | None:
    for key in (
        "account_label",
        "account_name",
        "account",
        "source_account",
        "source_account_label",
    ):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _effective_date(*values: Any) -> datetime:
    for value in values:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        if value:
            text = str(value).strip()
            if not text:
                continue
            if text.endswith("Z"):
                text = f"{text[:-1]}+00:00"
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                continue
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
    return datetime.min.replace(tzinfo=UTC)


class HouseholdLedgerService:
    """Return a compact, provenance-rich ledger for audit and duplicate review."""

    def get_ledger(self, service: Any, *, limit: int = 200) -> HouseholdLedger:
        with service.storage.connection() as conn:
            transaction_rows = conn.execute(
                """
                SELECT
                    t.id,
                    t.household_account_id,
                    COALESCE(ta.label, a.canonical_label, t.account_label) AS account_label,
                    t.transaction_date,
                    t.posted_date,
                    COALESCE(NULLIF(t.raw_merchant, ''), NULLIF(t.description, '')) AS merchant,
                    t.description,
                    t.amount,
                    t.currency,
                    t.category,
                    t.essentiality,
                    t.row_hash,
                    d.id AS source_document_id,
                    d.filename AS source_document_filename,
                    d.source_type,
                    d.document_type,
                    d.uploaded_at
                FROM household_transactions t
                LEFT JOIN household_accounts a
                  ON a.id = t.household_account_id
                LEFT JOIN LATERAL (
                    SELECT label
                    FROM household_tracked_accounts ta
                    WHERE ta.household_account_id = t.household_account_id
                    ORDER BY ta.updated_at DESC
                    LIMIT 1
                ) ta ON TRUE
                LEFT JOIN household_documents d
                  ON d.id = t.document_id
                ORDER BY COALESCE(t.posted_date, t.transaction_date) DESC, t.created_at DESC
                LIMIT %s
                """,
                [max(limit, 1)],
            ).fetchall()
            import_rows = conn.execute(
                """
                SELECT
                    r.id,
                    r.dataset_type,
                    r.external_row_id,
                    r.row_date,
                    r.merchant,
                    r.description,
                    r.amount,
                    r.currency,
                    r.row_hash,
                    r.row_metadata,
                    d.id AS source_document_id,
                    d.filename AS source_document_filename,
                    d.source_type,
                    d.document_type,
                    d.uploaded_at
                FROM household_import_rows r
                JOIN household_documents d
                  ON d.id = r.document_id
                ORDER BY COALESCE(r.row_date, d.statement_end, d.uploaded_at) DESC, r.created_at DESC
                LIMIT %s
                """,
                [max(limit, 1)],
            ).fetchall()

        entries: list[tuple[datetime, HouseholdLedgerEntry]] = []

        for row in transaction_rows:
            entry = HouseholdLedgerEntry(
                id=str(row[0]),
                kind="transaction",
                household_account_id=str(row[1]) if row[1] is not None else None,
                account_label=str(row[2]) if row[2] is not None else None,
                date=iso_or_none(row[3]),
                posted_date=iso_or_none(row[4]),
                merchant=str(row[5]) if row[5] is not None else None,
                description=str(row[6] or ""),
                amount=float(row[7]) if row[7] is not None else None,
                currency=str(row[8]) if row[8] is not None else None,
                category=str(row[9]) if row[9] is not None else None,
                essentiality=str(row[10]) if row[10] is not None else None,
                row_hash=str(row[11]),
                source_document_id=str(row[12]) if row[12] is not None else None,
                source_document_filename=str(row[13]) if row[13] is not None else None,
                source_type=str(row[14]) if row[14] is not None else None,
                document_type=str(row[15]) if row[15] is not None else None,
                uploaded_at=iso_or_none(row[16]),
            )
            entries.append(
                (
                    _effective_date(entry.posted_date, entry.date, entry.uploaded_at),
                    entry,
                )
            )

        for row in import_rows:
            metadata = _coerce_metadata(row[9])
            entry = HouseholdLedgerEntry(
                id=str(row[0]),
                kind="import_row",
                account_label=_metadata_account_label(metadata),
                date=iso_or_none(row[3]),
                posted_date=None,
                merchant=str(row[4]) if row[4] is not None else None,
                description=str(row[5] or row[4] or ""),
                amount=float(row[6]) if row[6] is not None else None,
                currency=str(row[7]) if row[7] is not None else None,
                dataset_type=str(row[1]) if row[1] is not None else None,
                external_row_id=str(row[2]) if row[2] is not None else None,
                row_hash=str(row[8]),
                source_document_id=str(row[10]) if row[10] is not None else None,
                source_document_filename=str(row[11]) if row[11] is not None else None,
                source_type=str(row[12]) if row[12] is not None else None,
                document_type=str(row[13]) if row[13] is not None else None,
                uploaded_at=iso_or_none(row[14]),
            )
            entries.append(
                (
                    _effective_date(entry.date, entry.uploaded_at),
                    entry,
                )
            )

        entries.sort(key=lambda item: item[0], reverse=True)

        return HouseholdLedger(
            generated_at=datetime.now(UTC).isoformat(),
            transaction_count=len(transaction_rows),
            import_row_count=len(import_rows),
            entries=[entry for _, entry in entries[: max(limit * 2, limit)]],
        )
