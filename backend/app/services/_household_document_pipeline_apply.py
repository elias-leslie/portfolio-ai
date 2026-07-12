"""Import and sync helpers for apply_review_outputs in the household document pipeline."""

from __future__ import annotations

from csv import DictReader
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from app.logging_config import get_logger
from app.models.household_finance import HouseholdDocument
from app.services._household_document_pipeline_db import (
    fetch_duplicate_document_row,
    update_import_summary,
    upsert_import_row,
    upsert_receipt_line_item_row,
)
from app.services._household_document_pipeline_receipt import receipt_line_item_rows
from app.services._household_document_pipeline_utils import detect_import_dataset
from app.services._household_finance_utils import iso, iso_or_none, to_float
from app.services.household_document_storage import (
    household_upload_root,
    resolve_document_upload,
)
from app.services.household_finance_rows import FIELD_LABELS, row_to_document

if TYPE_CHECKING:
    from app.services.household_finance_service import HouseholdFinanceService

logger = get_logger(__name__)

_ACCOUNT_EVIDENCE_SOURCE_TYPES = frozenset({"bank", "credit_card", "brokerage", "retirement"})
_ACCOUNT_EVIDENCE_DOCUMENT_TYPES = frozenset(
    {"statement", "brokerage_statement", "retirement_statement"}
)
_MONEY_SIGNATURE_VOLATILE_FIELDS = frozenset(
    {
        "activity_observed_through",
        "as_of_date",
        "statement_period",
        "text_preview",
        "total_amount",
    }
)
_MONEY_SIGNATURE_ACCOUNT_VOLATILE_FIELDS = frozenset(
    {
        "activity_observed_through",
        "as_of_date",
        "balance",
        "cash_balance",
        "confidence",
        "holdings_value",
    }
)


# ---------------------------------------------------------------------------
# Scalar helpers
# ---------------------------------------------------------------------------


def _bool_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return None


def _int_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Signature structured data (strips volatile fields)
# ---------------------------------------------------------------------------


def _sanitize_financial_accounts(accounts_raw: list[object]) -> list[dict[str, object]]:
    stable: list[dict[str, object]] = []
    for raw_account in accounts_raw:
        if not isinstance(raw_account, dict):
            continue
        stable_account = {
            k: v
            for k, v in raw_account.items()
            if k not in _MONEY_SIGNATURE_ACCOUNT_VOLATILE_FIELDS
            and v not in (None, "", [], {})
        }
        if stable_account:
            stable.append(stable_account)
    return stable


def signature_structured_data(
    reviewed: dict[str, object], document: HouseholdDocument
) -> dict[str, object]:
    """Return structured data with volatile per-period fields stripped."""
    structured_data = reviewed.get("structured_data")
    structured_data = (
        cast(dict[str, object], structured_data) if isinstance(structured_data, dict) else {}
    )
    if not structured_data:
        return {}
    source_type = str(reviewed.get("source_type") or document.source_type or "")
    if source_type not in _ACCOUNT_EVIDENCE_SOURCE_TYPES:
        return structured_data
    sanitized: dict[str, object] = {}
    for key, value in structured_data.items():
        if key in _MONEY_SIGNATURE_VOLATILE_FIELDS:
            continue
        if key == "financial_accounts" and isinstance(value, list):
            stable = _sanitize_financial_accounts(value)
            if stable:
                sanitized[key] = stable
            continue
        if value not in (None, "", [], {}):
            sanitized[key] = value
    return sanitized


# ---------------------------------------------------------------------------
# Duplicate validation
# ---------------------------------------------------------------------------


def is_duplicate_import_validation(
    *,
    import_summary: dict[str, object],
    transaction_summary: dict[str, object],
    evidence_account_count: int,
    planning_count: int,
    inferred_count: int,
) -> bool:
    """Return True when the import is a full duplicate with no other changes."""
    inserted = int(import_summary.get("inserted") or 0)
    duplicates = int(import_summary.get("duplicates") or 0)
    dataset_type = str(import_summary.get("dataset_type") or "").strip()
    transaction_changes = int(transaction_summary.get("inserted") or 0) + int(
        transaction_summary.get("updated") or 0
    )
    return (
        inserted == 0
        and duplicates > 0
        and bool(dataset_type)
        and transaction_changes == 0
        and evidence_account_count == 0
        and planning_count == 0
        and inferred_count == 0
    )


def find_duplicate_document_by_hash(
    service: HouseholdFinanceService,
    content_sha256: str,
) -> HouseholdDocument | None:
    with service.storage.connection() as conn:
        row = fetch_duplicate_document_row(conn, content_sha256)
    if row is None:
        return None
    return row_to_document(row, to_float=to_float, iso=iso, iso_or_none=iso_or_none)


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------


def _enriched_import_summary(
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
    dataset_type: str,
    inserted: int,
    duplicates: int,
) -> dict[str, object]:
    enrichment_summary = service.product_enrichment_service.enrich_import_rows(
        service,
        document_id=document.id,
        dataset_type=dataset_type,
    )
    return {
        "dataset_type": dataset_type,
        "inserted": inserted,
        "duplicates": duplicates,
        "enrichment": enrichment_summary,
    }


def import_receipt_line_item_rows(
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
    rows: list[dict[str, str | None]],
) -> dict[str, object]:
    dataset_type = "receipt_line_items"
    inserted = duplicates = 0
    now = datetime.now(UTC).isoformat()
    with service.storage.connection() as conn:
        for row in rows:
            result = upsert_receipt_line_item_row(
                conn, row=row, document_id=document.id, now=now
            )
            inserted += result is True
            duplicates += result is False
        update_import_summary(
            conn,
            document_id=document.id,
            dataset_type=dataset_type,
            inserted=inserted,
            duplicates=duplicates,
        )
        conn.commit()
    return _enriched_import_summary(
        service, document=document, dataset_type=dataset_type,
        inserted=inserted, duplicates=duplicates,
    )


def import_csv_rows(
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
    dataset_type: str,
    stored_path: Path,
) -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    with stored_path.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
        rows = list(DictReader(fh))
    inserted = duplicates = 0
    with service.storage.connection() as conn:
        for row in rows:
            result = upsert_import_row(
                conn, row=row, document_id=document.id,
                dataset_type=dataset_type, now=now,
            )
            inserted += result is True
            duplicates += result is False
        update_import_summary(
            conn, document_id=document.id, dataset_type=dataset_type,
            inserted=inserted, duplicates=duplicates,
        )
        conn.commit()
    return _enriched_import_summary(
        service, document=document, dataset_type=dataset_type,
        inserted=inserted, duplicates=duplicates,
    )


def import_document_rows(
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
) -> dict[str, object]:
    dataset_type = detect_import_dataset(document=document, reviewed=reviewed)
    if dataset_type is None:
        rows = receipt_line_item_rows(document=document, reviewed=reviewed)
        if not rows:
            return {"dataset_type": None, "inserted": 0, "duplicates": 0}
        return import_receipt_line_item_rows(service, document=document, rows=rows)
    stored_path = resolve_document_upload(
        document.metadata,
        household_upload_root(service),
    )
    if stored_path is None:
        return {"dataset_type": dataset_type, "inserted": 0, "duplicates": 0}
    return import_csv_rows(
        service, document=document, dataset_type=dataset_type, stored_path=stored_path
    )


# ---------------------------------------------------------------------------
# Service delegation helpers
# ---------------------------------------------------------------------------


def audit_transactions(
    service: HouseholdFinanceService,
    *,
    document_id: str,
) -> dict[str, object]:
    transaction_audit_service = getattr(service, "transaction_audit_service", None)
    if transaction_audit_service is None:
        return {}
    return transaction_audit_service.audit_transactions(
        service, document_id=document_id, limit=1000
    )


def transaction_summary_with_audit(
    transaction_summary: dict[str, object],
    audit_summary: dict[str, object],
) -> dict[str, object]:
    return {
        **transaction_summary,
        "audit_reviewed": int(audit_summary.get("reviewed") or 0),
        "audit_auto_fixed": int(audit_summary.get("auto_fixed") or 0),
        "audit_agent_fixed": int(audit_summary.get("agent_fixed") or 0),
        "audit_flagged": int(audit_summary.get("flagged") or 0),
    }


def sync_account_registry(service: HouseholdFinanceService) -> dict[str, int]:
    registry_service = getattr(service, "account_registry_service", None)
    if registry_service is None:
        return {}
    return registry_service.sync_registry(service, limit=1000)


def sync_portfolio_positions(
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
) -> dict[str, int]:
    sync_service = getattr(service, "portfolio_position_sync_service", None)
    if sync_service is None:
        return {}
    return sync_service.sync_from_reviewed_accounts(service, document=document, reviewed=reviewed)


def sync_portfolio_transactions(
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
) -> dict[str, int]:
    sync_service = getattr(service, "portfolio_transaction_sync_service", None)
    if sync_service is None:
        return {}
    return sync_service.sync_from_reviewed_accounts(service, document=document, reviewed=reviewed)


def _should_merge_planning_items(reviewed: dict[str, object]) -> bool:
    source_type = str(reviewed.get("source_type") or "").strip()
    document_type = str(reviewed.get("document_type") or "").strip()
    structured_data = reviewed.get("structured_data")
    structured_data = (
        cast(dict[str, object], structured_data) if isinstance(structured_data, dict) else {}
    )
    financial_accounts = structured_data.get("financial_accounts")
    has_financial_accounts = isinstance(financial_accounts, list) and bool(financial_accounts)
    if has_financial_accounts:
        return False
    return not (
        source_type in _ACCOUNT_EVIDENCE_SOURCE_TYPES
        and document_type in _ACCOUNT_EVIDENCE_DOCUMENT_TYPES
    )


def merge_review_planning_items(
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
) -> tuple[int, int, str | None]:
    planning_items = reviewed.get("planning_items")
    if not isinstance(planning_items, list):
        return 0, 0, None
    dict_items = [item for item in planning_items if isinstance(item, dict)]
    if not dict_items or not _should_merge_planning_items(reviewed):
        return 0, len(dict_items), None
    try:
        service.merge_planning_items(
            items=dict_items,
            provenance="document_review",
            source_document_id=document.id,
        )
    except Exception as exc:
        logger.warning(
            "household_document_planning_merge_skipped",
            document_id=document.id,
            error=str(exc),
        )
        return 0, len(dict_items), str(exc)
    return len(dict_items), 0, None


def inferred_value_count(reviewed: dict[str, object]) -> int:
    raw_inferred_values = reviewed.get("inferred_values")
    if not isinstance(raw_inferred_values, list):
        return 0
    return sum(
        1
        for inferred in raw_inferred_values
        if isinstance(inferred, dict)
        and str(inferred.get("field_name") or "").strip() in FIELD_LABELS
    )


def append_review_impacts(
    impacts: list[str],
    *,
    import_summary: dict[str, object],
    transaction_summary: dict[str, object],
    evidence_account_count: int,
    portfolio_position_summary: dict[str, int],
    planning_count: int,
    inferred_count: int,
) -> None:
    if (import_summary.get("inserted") or 0) > 0:
        impacts.append("imports")
    if (transaction_summary.get("inserted") or 0) > 0 or (
        transaction_summary.get("updated") or 0
    ) > 0:
        impacts.append("transactions")
    if (transaction_summary.get("held_for_date_review") or 0) > 0:
        impacts.append("date_review")
    if evidence_account_count > 0:
        impacts.append("accounts")
    if (
        portfolio_position_summary.get("positions_inserted", 0) > 0
        or portfolio_position_summary.get("positions_updated", 0) > 0
        or portfolio_position_summary.get("positions_deleted", 0) > 0
        or portfolio_position_summary.get("cash_updated", 0) > 0
    ):
        impacts.append("portfolio_positions")
    if planning_count > 0:
        impacts.append("planning")
    if inferred_count > 0:
        impacts.append("inferences")
