"""Read-only ledger and provenance view for household finance."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.household_finance import HouseholdLedger, HouseholdLedgerEntry
from app.services._household_finance_utils import iso_or_none
from app.services._household_time_windows import resolve_household_time_window


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


def _metadata_decimal(metadata: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = metadata.get(key)
        if value in (None, ""):
            continue
        try:
            return float(Decimal(str(value).replace(",", "").strip()))
        except (InvalidOperation, ValueError):
            continue
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


def _transaction_sql(window_start: str | None, *, limit: int) -> tuple[str, list[Any]]:
    where_clauses: list[str] = ["TRUE"]
    params: list[Any] = []
    if window_start is not None:
        where_clauses.append("COALESCE(t.posted_date, t.transaction_date) >= %s")
        params.append(window_start)

    sql = f"""
        SELECT
            t.id,
            t.flow_type,
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
            t.metadata,
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
        WHERE {" AND ".join(where_clauses)}
        ORDER BY COALESCE(t.posted_date, t.transaction_date) DESC, t.created_at DESC
        LIMIT %s
    """
    params.append(max(limit, 1))
    return sql, params


def _import_sql(window_start: str | None, *, limit: int) -> tuple[str, list[Any]]:
    where_clauses: list[str] = ["TRUE"]
    params: list[Any] = []
    if window_start is not None:
        where_clauses.append("COALESCE(r.row_date, d.uploaded_at) >= %s")
        params.append(window_start)

    sql = f"""
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
        WHERE {" AND ".join(where_clauses)}
        ORDER BY COALESCE(r.row_date, d.statement_end, d.uploaded_at) DESC, r.created_at DESC
        LIMIT %s
    """
    params.append(max(limit, 1))
    return sql, params


class HouseholdLedgerService:
    """Return raw household ledger rows with accounting-style audit fields."""

    def get_ledger(
        self,
        service: Any,
        *,
        window: str = "all",
        kind: str = "all",
        limit: int = 10000,
    ) -> HouseholdLedger:
        timeframe = resolve_household_time_window(window)
        start_date = (
            datetime.combine(timeframe.start_date, datetime.min.time(), tzinfo=UTC).isoformat()
            if timeframe.start_date is not None
            else None
        )
        normalized_kind = (kind or "all").strip().lower()
        if normalized_kind not in {"all", "transactions", "imports"}:
            normalized_kind = "all"

        transaction_rows: list[tuple[Any, ...]] = []
        import_rows: list[tuple[Any, ...]] = []

        with service.storage.connection() as conn:
            if normalized_kind in {"all", "transactions"}:
                tx_sql, tx_params = _transaction_sql(start_date, limit=limit)
                transaction_rows = conn.execute(tx_sql, tx_params).fetchall()
            if normalized_kind in {"all", "imports"}:
                import_sql, import_params = _import_sql(start_date, limit=limit)
                import_rows = conn.execute(import_sql, import_params).fetchall()

        entries: list[tuple[datetime, HouseholdLedgerEntry]] = []
        debit_total = 0.0
        credit_total = 0.0

        for row in transaction_rows:
            metadata = _coerce_metadata(row[13])
            amount = float(row[8]) if row[8] is not None else None
            if amount is not None:
                if amount > 0:
                    debit_total += amount
                elif amount < 0:
                    credit_total += abs(amount)
            entry = HouseholdLedgerEntry(
                id=str(row[0]),
                kind="transaction",
                flow_type=str(row[1]) if row[1] is not None else None,
                household_account_id=str(row[2]) if row[2] is not None else None,
                account_label=str(row[3]) if row[3] is not None else None,
                date=iso_or_none(row[4]),
                posted_date=iso_or_none(row[5]),
                merchant=str(row[6]) if row[6] is not None else None,
                description=str(row[7] or ""),
                amount=amount,
                currency=str(row[9]) if row[9] is not None else None,
                category=str(row[10]) if row[10] is not None else None,
                essentiality=str(row[11]) if row[11] is not None else None,
                row_hash=str(row[12]),
                balance_after=_metadata_decimal(
                    metadata,
                    "balance_after",
                    "cash_balance",
                    "running_balance",
                    "balance",
                ),
                source_document_id=str(row[14]) if row[14] is not None else None,
                source_document_filename=str(row[15]) if row[15] is not None else None,
                source_type=str(row[16]) if row[16] is not None else None,
                document_type=str(row[17]) if row[17] is not None else None,
                uploaded_at=iso_or_none(row[18]),
            )
            entries.append(
                (
                    _effective_date(entry.posted_date, entry.date, entry.uploaded_at),
                    entry,
                )
            )

        for row in import_rows:
            metadata = _coerce_metadata(row[9])
            amount = float(row[6]) if row[6] is not None else None
            if amount is not None:
                if amount > 0:
                    debit_total += amount
                elif amount < 0:
                    credit_total += abs(amount)
            entry = HouseholdLedgerEntry(
                id=str(row[0]),
                kind="import_row",
                account_label=_metadata_account_label(metadata),
                date=iso_or_none(row[3]),
                posted_date=None,
                merchant=str(row[4]) if row[4] is not None else None,
                description=str(row[5] or row[4] or ""),
                amount=amount,
                currency=str(row[7]) if row[7] is not None else None,
                dataset_type=str(row[1]) if row[1] is not None else None,
                external_row_id=str(row[2]) if row[2] is not None else None,
                row_hash=str(row[8]),
                balance_after=_metadata_decimal(
                    metadata,
                    "balance_after",
                    "cash_balance",
                    "running_balance",
                    "balance",
                ),
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
            timeframe_key=timeframe.key,
            timeframe_label=timeframe.label,
            start_date=timeframe.start_date.isoformat() if timeframe.start_date else None,
            end_date=timeframe.end_date.isoformat(),
            transaction_count=len(transaction_rows),
            import_row_count=len(import_rows),
            total_entry_count=len(entries),
            debit_total=round(debit_total, 2),
            credit_total=round(credit_total, 2),
            entries=[entry for _, entry in entries],
        )
