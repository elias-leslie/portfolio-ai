"""Read-only ledger and provenance view for household finance."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.household_finance import HouseholdLedger, HouseholdLedgerEntry
from app.services._household_finance_utils import iso_or_none
from app.services._household_report_builder import collapse_report_rows_with_exclusions
from app.services._household_spend_filters import looks_like_cash_movement
from app.services._household_time_windows import resolve_household_time_window
from app.services.household_transaction_service import (
    _effective_transaction_classification,
    _effective_transaction_flow,
)


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


def _row_value(row: Any, index: int, default: Any = None) -> Any:
    try:
        return row[index]
    except IndexError:
        return default


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


def _metadata_text(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


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


def _entry_owner(
    transaction_metadata: dict[str, Any],
    merchant_metadata: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    owner = _metadata_text(transaction_metadata, "owner_name")
    if owner:
        source = _metadata_text(transaction_metadata, "owner_source")
        return owner, source or "manual"
    if isinstance(merchant_metadata, dict):
        rule = merchant_metadata.get("manual_owner_rule")
        if isinstance(rule, dict):
            owner = _metadata_text(rule, "owner_name")
            if owner:
                return owner, "merchant_rule"
    return None, None


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


def _is_credit_flow(flow_type: str | None) -> bool:
    normalized = (flow_type or "").strip().lower()
    return normalized in {"income", "refund", "transfer_in"}


def _is_debit_flow(flow_type: str | None) -> bool:
    normalized = (flow_type or "").strip().lower()
    return normalized in {"expense", "payment", "transfer_out", "investment"}


def _entry_direction(flow_type: str | None, amount: float | None) -> str:
    """Single source of truth for a ledger row's debit/credit direction."""
    if amount is None:
        return "neutral"
    if _is_credit_flow(flow_type) or (not _is_debit_flow(flow_type) and amount < 0):
        return "credit"
    if _is_debit_flow(flow_type) or amount > 0:
        return "debit"
    return "neutral"


# Upper bound on rows scanned per window so dedup/exclusion runs over the whole window
# (a page is sliced out afterwards). Large enough for live data, capped so a runaway
# window cannot fetch unboundedly.
LEDGER_SCAN_CAP = 20000

_LEDGER_SEARCH_FIELDS = (
    "account_label",
    "merchant",
    "description",
    "category",
    "essentiality",
    "owner_name",
    "owner_source",
    "source_document_filename",
    "source_document_id",
    "external_row_id",
    "source_type",
    "document_type",
    "flow_type",
    "exclusion_reason",
    "row_hash",
)


def _entry_is_duplicate(entry: HouseholdLedgerEntry) -> bool:
    return (entry.exclusion_reason or "").startswith("duplicate")


def _entry_matches_filters(
    entry: HouseholdLedgerEntry,
    *,
    status: str,
    account: str,
    search: str,
) -> bool:
    duplicate = _entry_is_duplicate(entry)
    if status == "canonical" and duplicate:
        return False
    if status == "duplicates" and not duplicate:
        return False
    if account != "all":
        label = (entry.account_label or "").strip() or "__unassigned__"
        if label != account:
            return False
    if search:
        haystack = " ".join(
            str(getattr(entry, field))
            for field in _LEDGER_SEARCH_FIELDS
            if getattr(entry, field, None)
        ).lower()
        if search not in haystack:
            return False
    return True


def _entry_sort_value(
    entry: HouseholdLedgerEntry, sort_dt: datetime, sort_key: str
) -> Any:
    if sort_key == "account":
        return (entry.account_label or "").lower()
    if sort_key == "detail":
        return (entry.merchant or entry.description or "").lower()
    if sort_key == "category":
        return (entry.category or "").lower()
    if sort_key == "status":
        return (entry.exclusion_reason or "").lower()
    if sort_key == "amount":
        return abs(entry.amount or 0.0)
    return sort_dt


def _purchase_items_by_transaction(conn: Any) -> dict[str, tuple[int, list[str]]]:
    """Item count + distinct categories per linked transaction.

    Counts linked items regardless of allocation reconciliation — the ledger
    badge is a provenance affordance (row expansion), not spend math.
    """
    rows = conn.execute(
        """
        SELECT i.transaction_id::text,
               COUNT(*),
               ARRAY_AGG(DISTINCT i.category)
        FROM household_purchase_items i
        WHERE i.transaction_id IS NOT NULL
          AND i.removed IS NOT TRUE
        GROUP BY i.transaction_id
        """
    ).fetchall()
    return {
        str(row[0]): (
            int(row[1] or 0),
            [str(category) for category in (row[2] or []) if category],
        )
        for row in rows
    }


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
            COALESCE(ap.display_label, a.canonical_label, t.account_label) AS account_label,
            t.transaction_date,
            t.posted_date,
            COALESCE(m.canonical_name, NULLIF(t.raw_merchant, ''), NULLIF(t.description, '')) AS merchant,
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
            d.uploaded_at,
            m.metadata,
            t.original_category,
            t.categorization_source,
            t.categorization_version,
            t.category_updated_at,
            t.category_updated_by,
            t.source_system,
            t.external_transaction_id,
            t.pending,
            t.removed,
            t.transaction_rule_id,
            t.balance_after
        FROM household_transactions t
        LEFT JOIN household_merchants m
          ON m.id = t.merchant_id
        LEFT JOIN household_accounts a
          ON a.id = t.household_account_id
        LEFT JOIN LATERAL (
            SELECT display_label
            FROM household_account_preferences ap
            WHERE ap.household_account_id = t.household_account_id
              AND ap.hidden_at IS NULL
            ORDER BY ap.updated_at DESC
            LIMIT 1
        ) ap ON TRUE
        LEFT JOIN household_documents d
          ON d.id = t.document_id
        WHERE {" AND ".join(where_clauses)}
          AND t.removed IS NOT TRUE
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
        status: str = "all",
        account: str = "all",
        search: str = "",
        sort: str = "date",
        sort_dir: str = "desc",
        limit: int = 100,
        offset: int = 0,
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
        normalized_status = (status or "all").strip().lower()
        if normalized_status not in {"all", "canonical", "duplicates"}:
            normalized_status = "all"
        normalized_account = (account or "all").strip() or "all"
        normalized_search = (search or "").strip().lower()
        valid_sorts = {"date", "account", "detail", "category", "status", "amount"}
        normalized_sort = (sort or "date").strip().lower()
        if normalized_sort not in valid_sorts:
            normalized_sort = "date"
        descending = (sort_dir or "desc").strip().lower() != "asc"
        page_limit = max(1, min(int(limit), 500))
        page_offset = max(0, int(offset))

        transaction_rows: list[tuple[Any, ...]] = []
        import_rows: list[tuple[Any, ...]] = []
        items_by_transaction: dict[str, tuple[int, list[str]]] = {}

        with service.storage.connection() as conn:
            if normalized_kind in {"all", "transactions"}:
                tx_sql, tx_params = _transaction_sql(start_date, limit=LEDGER_SCAN_CAP)
                transaction_rows = conn.execute(tx_sql, tx_params).fetchall()
                items_by_transaction = _purchase_items_by_transaction(conn)
            if normalized_kind in {"all", "imports"}:
                import_sql, import_params = _import_sql(start_date, limit=LEDGER_SCAN_CAP)
                import_rows = conn.execute(import_sql, import_params).fetchall()

        entries: list[tuple[datetime, HouseholdLedgerEntry]] = []
        report_candidates: list[dict[str, Any]] = []

        for row in transaction_rows:
            metadata = _coerce_metadata(row[13])
            balance_after = (
                float(_row_value(row, 30))
                if _row_value(row, 30) is not None
                else _metadata_decimal(
                    metadata,
                    "balance_after",
                    "cash_balance",
                    "running_balance",
                    "balance",
                )
            )
            amount = float(row[8]) if row[8] is not None else None
            effective_flow = _effective_transaction_flow(
                flow_type=str(row[1] or ""),
                raw_merchant=str(row[6] or row[7] or ""),
                description=str(row[7] or row[6] or ""),
                source_type=str(row[16] or ""),
            )
            effective_category, effective_essentiality = _effective_transaction_classification(
                flow_type=effective_flow,
                raw_merchant=str(row[6] or row[7] or ""),
                description=str(row[7] or row[6] or ""),
                amount=amount,
                stored_category=str(row[10] or ""),
                stored_essentiality=str(row[11] or ""),
                merchant_metadata=row[19] if isinstance(row[19], dict) else None,
                categorization_source=(
                    str(_row_value(row, 21)) if _row_value(row, 21) is not None else None
                ),
            )
            if amount is not None and amount > 0:
                report_candidates.append(
                    {
                        "id": str(row[0]),
                        "row_hash": str(row[12]),
                        "household_account_id": str(row[2]) if row[2] is not None else None,
                        "date": (
                            row[5].date() if isinstance(row[5], datetime)
                            else row[4].date() if isinstance(row[4], datetime)
                            else None
                        ),
                        "merchant": str(row[6] or row[7] or ""),
                        "description": str(row[7] or ""),
                        "amount": amount,
                        "signed_amount": -amount if effective_flow == "refund" else amount,
                        "category": effective_category,
                        "essentiality": effective_essentiality,
                        "document_id": str(row[14]) if row[14] is not None else None,
                        "document_type": str(row[17] or ""),
                        "source_type": str(row[16] or ""),
                        "source_document_filename": str(row[15] or ""),
                        "source_kind": "transaction",
                        # _effective_document_type needs this to class
                        # receipt-sourced rows as receipts, matching Reports.
                        "source_system": (
                            str(_row_value(row, 25))
                            if _row_value(row, 25) is not None
                            else None
                        ),
                    }
                )

        for row in import_rows:
            metadata = _coerce_metadata(row[9])
            amount = float(row[6]) if row[6] is not None else None
            if amount is not None and amount > 0:
                report_candidates.append(
                    {
                        "id": str(row[0]),
                        "row_hash": str(row[8]),
                        "household_account_id": None,
                        "date": row[3].date() if isinstance(row[3], datetime) else None,
                        "merchant": str(row[4] or ""),
                        "description": str(row[5] or row[4] or ""),
                        "amount": amount,
                        "category": "Household shopping",
                        "essentiality": "mixed",
                        "document_id": str(row[10]) if row[10] is not None else None,
                        "document_type": "import",
                        "source_type": str(row[1] or "import"),
                        "source_document_filename": str(row[11] or ""),
                        "source_kind": "import",
                    }
                )

        _, excluded_row_hashes = collapse_report_rows_with_exclusions(
            [row for row in report_candidates if row.get("date") is not None]
        )

        for row in transaction_rows:
            metadata = _coerce_metadata(row[13])
            amount = float(row[8]) if row[8] is not None else None
            effective_flow = _effective_transaction_flow(
                flow_type=str(row[1] or ""),
                raw_merchant=str(row[6] or row[7] or ""),
                description=str(row[7] or row[6] or ""),
                source_type=str(row[16] or ""),
            )
            effective_category, effective_essentiality = _effective_transaction_classification(
                flow_type=effective_flow,
                raw_merchant=str(row[6] or row[7] or ""),
                description=str(row[7] or row[6] or ""),
                amount=amount,
                stored_category=str(row[10] or ""),
                stored_essentiality=str(row[11] or ""),
                merchant_metadata=row[19] if isinstance(row[19], dict) else None,
                categorization_source=(
                    str(_row_value(row, 21)) if _row_value(row, 21) is not None else None
                ),
            )
            exclusion_reason: str | None = None
            included_in_spend = False
            if effective_flow not in {"expense", "refund"}:
                exclusion_reason = "non_expense_flow"
            elif amount is None or amount <= 0:
                exclusion_reason = "non_positive_amount"
            elif looks_like_cash_movement(
                category=effective_category,
                description=str(row[7] or ""),
                merchant=str(row[6] or row[7] or ""),
            ):
                exclusion_reason = "cash_movement"
            else:
                exclusion_reason = excluded_row_hashes.get(str(row[12]))
                included_in_spend = exclusion_reason is None
            item_count, item_categories = items_by_transaction.get(str(row[0]), (0, []))
            owner_name, owner_source = _entry_owner(
                metadata,
                row[19] if isinstance(row[19], dict) else None,
            )
            entry = HouseholdLedgerEntry(
                id=str(row[0]),
                kind="transaction",
                item_count=item_count,
                item_categories=item_categories,
                flow_type=effective_flow,
                direction=_entry_direction(effective_flow, amount),
                household_account_id=str(row[2]) if row[2] is not None else None,
                account_label=str(row[3]) if row[3] is not None else None,
                date=iso_or_none(row[4]),
                posted_date=iso_or_none(row[5]),
                merchant=str(row[6]) if row[6] is not None else None,
                description=str(row[7] or ""),
                amount=amount,
                currency=str(row[9]) if row[9] is not None else None,
                category=effective_category,
                essentiality=effective_essentiality,
                owner_name=owner_name,
                owner_source=owner_source,
                original_category=str(_row_value(row, 20)) if _row_value(row, 20) is not None else None,
                categorization_source=str(_row_value(row, 21)) if _row_value(row, 21) is not None else None,
                categorization_version=str(_row_value(row, 22)) if _row_value(row, 22) is not None else None,
                category_updated_at=iso_or_none(_row_value(row, 23)),
                category_updated_by=str(_row_value(row, 24)) if _row_value(row, 24) is not None else None,
                source_system=str(_row_value(row, 25)) if _row_value(row, 25) is not None else None,
                external_transaction_id=(
                    str(_row_value(row, 26)) if _row_value(row, 26) is not None else None
                ),
                pending=bool(_row_value(row, 27, False)),
                removed=bool(_row_value(row, 28, False)),
                transaction_rule_id=(
                    str(_row_value(row, 29)) if _row_value(row, 29) is not None else None
                ),
                row_hash=str(row[12]),
                balance_after=balance_after,
                source_document_id=str(row[14]) if row[14] is not None else None,
                source_document_filename=str(row[15]) if row[15] is not None else None,
                source_type=str(row[16]) if row[16] is not None else None,
                document_type=str(row[17]) if row[17] is not None else None,
                uploaded_at=iso_or_none(row[18]),
                included_in_spend=included_in_spend,
                exclusion_reason=exclusion_reason,
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
            entry = HouseholdLedgerEntry(
                id=str(row[0]),
                kind="import_row",
                direction=_entry_direction(None, amount),
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
                included_in_spend=False,
                exclusion_reason=excluded_row_hashes.get(str(row[8])) or "raw_import_only",
            )
            entries.append(
                (
                    _effective_date(entry.date, entry.uploaded_at),
                    entry,
                )
            )

        account_options = sorted(
            {
                (entry.account_label or "").strip()
                for _, entry in entries
                if (entry.account_label or "").strip()
            },
            key=str.lower,
        )

        category_options = sorted(
            {
                (entry.category or "").strip()
                for _, entry in entries
                if entry.kind == "transaction" and (entry.category or "").strip()
            },
            key=str.lower,
        )

        filtered = [
            (sort_dt, entry)
            for sort_dt, entry in entries
            if _entry_matches_filters(
                entry,
                status=normalized_status,
                account=normalized_account,
                search=normalized_search,
            )
        ]

        debit_total = 0.0
        credit_total = 0.0
        included_count = 0
        for _, entry in filtered:
            if entry.included_in_spend:
                included_count += 1
            amount = entry.amount
            if amount is None:
                continue
            if entry.direction == "credit":
                credit_total += abs(amount)
            elif entry.direction == "debit":
                debit_total += abs(amount)

        if normalized_sort == "date":
            filtered.sort(key=lambda item: item[0], reverse=descending)
        else:
            # Stable sort: lay down the chronological tie-break first (newest first),
            # then sort by the primary key so equal keys stay date-ordered.
            filtered.sort(key=lambda item: item[0], reverse=True)
            filtered.sort(
                key=lambda item: _entry_sort_value(item[1], item[0], normalized_sort),
                reverse=descending,
            )

        page = filtered[page_offset : page_offset + page_limit]

        return HouseholdLedger(
            generated_at=datetime.now(UTC).isoformat(),
            timeframe_key=timeframe.key,
            timeframe_label=timeframe.label,
            start_date=timeframe.start_date.isoformat() if timeframe.start_date else None,
            end_date=timeframe.end_date.isoformat(),
            transaction_count=len(transaction_rows),
            import_row_count=len(import_rows),
            total_entry_count=len(entries),
            filtered_count=len(filtered),
            included_count=included_count,
            excluded_count=len(filtered) - included_count,
            offset=page_offset,
            limit=page_limit,
            returned_count=len(page),
            account_options=account_options,
            category_options=category_options,
            debit_total=round(debit_total, 2),
            credit_total=round(credit_total, 2),
            entries=[entry for _, entry in page],
        )
