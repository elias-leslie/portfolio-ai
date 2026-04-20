from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any


def _fetch_scalar_float(storage: Any, sql: str) -> float:
    with storage.connection() as conn:
        row = conn.execute(sql).fetchone()
    return round(float(row[0] or 0.0), 2) if row is not None else 0.0


def _date_value(value: Any) -> Any:
    return value.date() if hasattr(value, "date") else value


def _date_iso(value: Any) -> str | None:
    date_value = _date_value(value)
    return date_value.isoformat() if date_value is not None else None


def _future_transaction_quality_payload(transaction_row: Any, document_row: Any) -> dict[str, Any]:
    if transaction_row is None and document_row is None:
        return {
            "future_transaction_count": 0,
            "earliest_future_date": None,
            "latest_future_date": None,
        }
    transaction_count = int(transaction_row[0] or 0) if transaction_row is not None else 0
    document_count = int(document_row[0] or 0) if document_row is not None else 0
    earliest_candidates = [
        _date_value(row[1])
        for row in (transaction_row, document_row)
        if row is not None and row[1] is not None
    ]
    latest_candidates = [
        _date_value(row[2])
        for row in (transaction_row, document_row)
        if row is not None and row[2] is not None
    ]
    return {
        "future_transaction_count": transaction_count + document_count,
        "earliest_future_date": min(earliest_candidates).isoformat() if earliest_candidates else None,
        "latest_future_date": max(latest_candidates).isoformat() if latest_candidates else None,
    }


def _days_since(date_value: date) -> int:
    return (datetime.now(UTC).date() - date_value).days


def _short_excerpt(value: Any, *, max_length: int = 220) -> str | None:
    if not isinstance(value, str):
        return None
    compact = " ".join(value.split())
    if not compact:
        return None
    return compact[: max_length - 1] + "…" if len(compact) > max_length else compact


def _float_or_zero(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
