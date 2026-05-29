"""Database query helpers for household dashboard (require storage access)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdCategorizationCandidate,
    HouseholdRecurringCommitment,
)
from app.services._household_dashboard_builders import (
    build_recurring_commitment,
    suggest_category,
    suggest_essentiality,
)
from app.services._household_dashboard_date_issues import (
    fetch_transaction_date_issues as _fetch_transaction_date_issues_impl,
)
from app.services._household_dashboard_queries_shared import (
    _date_value,
    _days_since,
    _fetch_scalar_float,
)
from app.services._household_dashboard_query_sql import (
    CATEGORIZATION_SQL,
    CONFIRMED_FACTS_SQL,
    DOCUMENT_FUTURE_TRANSACTION_QUALITY_SQL,
    FUTURE_TRANSACTION_QUALITY_SQL,
    LATEST_TRANSACTION_DATE_SQL,
    RECURRING_SQL,
    RETIREMENT_CONTRIBUTION_SQL,
    STATEMENT_FRESHNESS_SQL,
)
from app.services._household_dashboard_unknown_accounts import (
    detect_unknown_accounts as _detect_unknown_accounts_impl,
)
from app.services.household_transaction_service import HouseholdTransactionService


def fetch_transaction_date_issues(storage: Any, limit: int = 12):
    return _fetch_transaction_date_issues_impl(storage, limit=limit)


def detect_unknown_accounts(storage: Any, documents: list[Any]):
    return _detect_unknown_accounts_impl(storage, documents)


def _empty_future_transaction_quality() -> dict[str, Any]:
    return {
        "future_transaction_count": 0,
        "earliest_future_date": None,
        "latest_future_date": None,
    }


def _future_date_candidates(*rows: Any, index: int) -> list[date]:
    return [_date_value(row[index]) for row in rows if row is not None and row[index] is not None]


def _future_transaction_quality_payload(transaction_row: Any, document_row: Any) -> dict[str, Any]:
    earliest_candidates = _future_date_candidates(transaction_row, document_row, index=1)
    latest_candidates = _future_date_candidates(transaction_row, document_row, index=2)
    return {
        "future_transaction_count": int(transaction_row[0] or 0) + int(document_row[0] or 0),
        "earliest_future_date": min(earliest_candidates).isoformat() if earliest_candidates else None,
        "latest_future_date": max(latest_candidates).isoformat() if latest_candidates else None,
    }


def _fetch_future_transaction_quality(storage: Any) -> dict[str, Any]:
    with storage.connection() as conn:
        transaction_row = conn.execute(FUTURE_TRANSACTION_QUALITY_SQL).fetchone()
        document_row = conn.execute(DOCUMENT_FUTURE_TRANSACTION_QUALITY_SQL).fetchone()
    if transaction_row is None and document_row is None:
        return _empty_future_transaction_quality()
    return _future_transaction_quality_payload(transaction_row or (0, None, None), document_row or (0, None, None))


def _gap_months(most_recent_date: date, coverage_months: int, earliest_raw: Any) -> list[str]:
    if earliest_raw is None or coverage_months <= 0:
        return []
    earliest_date = _date_value(earliest_raw)
    total_months = (
        (most_recent_date.year - earliest_date.year) * 12
        + (most_recent_date.month - earliest_date.month)
        + 1
    )
    if total_months <= coverage_months:
        return []
    gap_months_count = total_months - coverage_months
    return [f"{gap_months_count} month{'s' if gap_months_count != 1 else ''} missing in range"]


def check_statement_freshness(storage: Any) -> dict[str, Any]:
    future_quality = _fetch_future_transaction_quality(storage)
    with storage.connection() as conn:
        row = conn.execute(STATEMENT_FRESHNESS_SQL).fetchone()
    if row is None or row[0] is None:
        return {
            "most_recent_date": None,
            "days_since_latest": None,
            "coverage_months": 0,
            "gap_months": [],
            **future_quality,
        }
    most_recent_date = _date_value(row[0])
    coverage_months = int(row[1] or 0)
    return {
        "most_recent_date": most_recent_date.isoformat(),
        "days_since_latest": _days_since(most_recent_date),
        "coverage_months": coverage_months,
        "gap_months": _gap_months(most_recent_date, coverage_months, row[2]),
        **future_quality,
    }


def fetch_confirmed_facts(storage: Any) -> dict[str, str]:
    with storage.connection() as conn:
        rows = conn.execute(CONFIRMED_FACTS_SQL).fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def _categorization_fields(row: Any) -> tuple[str, str, str, str, str, str]:
    return (
        str(row[1]),
        str(row[2]),
        str(row[9] or "").strip(),
        str(row[10] or "").strip(),
        str(row[11] or "").strip(),
        row[4].isoformat(),
    )


def _categorization_candidate(row: Any) -> HouseholdCategorizationCandidate:
    if len(row) < 12:
        raise ValueError(f"fetch_categorization_queue: expected 12 columns, got {len(row)}")
    merchant, description, audit_reason, audit_category, audit_essentiality, transaction_date = _categorization_fields(row)
    return HouseholdCategorizationCandidate(
        id=str(row[0]),
        merchant=merchant,
        description=description,
        amount=float(row[3]),
        transaction_date=transaction_date,
        current_category=str(row[5] or "Household"),
        current_essentiality=str(row[6] or "mixed"),
        suggested_category=audit_category or suggest_category(merchant, description),
        suggested_essentiality=audit_essentiality or suggest_essentiality(merchant, description),
        confidence=float(row[7] or 0.0),
        similar_transaction_count=max(int(row[8] or 0) - 1, 0),
        reason=audit_reason or "Low-confidence classification (below 60%) needs a human pass before Jenny hardens the budget lane.",
    )


def fetch_categorization_queue(storage: Any, limit: int = 10) -> list[HouseholdCategorizationCandidate]:
    with storage.connection() as conn:
        rows = conn.execute(CATEGORIZATION_SQL, [limit]).fetchall()
    return [_categorization_candidate(row) for row in rows]


def fetch_recurring_commitments(
    storage: Any,
    transaction_service: Any,
    limit: int = 6,
) -> list[HouseholdRecurringCommitment]:
    today = datetime.now(UTC).date()
    with storage.connection() as conn:
        rows = conn.execute(RECURRING_SQL, [limit * 2]).fetchall()
    commitments: list[HouseholdRecurringCommitment] = []
    for row in rows:
        cadence_info = transaction_service.infer_merchant_cadence(merchant=str(row[0])) or {}
        cadence = str(cadence_info.get("label") or "irregular")
        commitment = build_recurring_commitment(row, cadence, cadence_info, today)
        if commitment is not None:
            commitments.append(commitment)
    return commitments[:limit]


def fetch_monthly_retirement_contributions(storage: Any) -> float:
    return _fetch_scalar_float(storage, RETIREMENT_CONTRIBUTION_SQL)


def fetch_current_month_spend(storage: Any) -> float:
    transaction_service = HouseholdTransactionService()
    transaction_service.storage = storage
    today = date.today()
    return transaction_service.spend_total_between(
        start_date=today.replace(day=1),
        end_date=today,
    )


def _latest_transaction_dates(storage: Any, column: str) -> dict[str, date]:
    with storage.connection() as conn:
        rows = conn.execute(LATEST_TRANSACTION_DATE_SQL[column]).fetchall()
    latest: dict[str, date] = {}
    for key_raw, latest_raw in rows:
        key = str(key_raw).strip() if key_raw is not None else ""
        if not key or latest_raw is None:
            continue
        latest[key] = _date_value(latest_raw)
    return latest


def fetch_latest_transaction_dates_by_document(storage: Any) -> dict[str, date]:
    return _latest_transaction_dates(storage, "document_id")


def fetch_latest_transaction_dates_by_account_label(storage: Any) -> dict[str, date]:
    return _latest_transaction_dates(storage, "account_label")


def fetch_latest_transaction_dates_by_household_account(storage: Any) -> dict[str, date]:
    return _latest_transaction_dates(storage, "household_account_id")


def fetch_inferred_value_rows(storage: Any) -> dict[str, dict[str, Any]]:
    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT ON (field_name)
                field_name, value_text, confidence, status, rationale,
                source_document_id, metadata->>'source' AS inference_source
            FROM household_inferred_values
            ORDER BY field_name, updated_at DESC
            """
        ).fetchall()
    return {
        str(row[0]): {
            "value": row[1], "confidence": row[2], "status": row[3],
            "rationale": row[4], "source_document_id": row[5],
            "source": row[6] if len(row) > 6 else None,
        }
        for row in rows
    }
