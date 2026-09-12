"""Small read-only coverage summary for a named household review period."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services._household_account_status import metadata_indicates_closed
from app.services._household_account_summary_utils import _money_role


def review_coverage(storage: Any, *, end_date: date) -> dict[str, Any]:
    """Surface known missing activity; never call transaction recency a full audit.

    Use the same canonical account spine as Money. A seven-day reporting grace
    accommodates weekends and ordinary posting delays. Display the actual
    observed date as well so this is not mistaken for statement certification.
    """
    with storage.connection() as conn:
        rows = conn.execute(
            """SELECT a.canonical_label, a.asset_group, a.account_type, a.metadata,
                      a.feed_status, GREATEST(a.coverage_through, (SELECT MAX(t.transaction_date)::date FROM household_transactions t WHERE t.household_account_id=a.id AND NOT t.removed))
               FROM household_accounts a
               WHERE a.archived_at IS NULL AND a.merged_into_account_id IS NULL
                 AND NOT EXISTS (SELECT 1 FROM household_account_preferences p
                                 WHERE p.household_account_id=a.id AND p.hidden_at IS NOT NULL)
               ORDER BY a.canonical_label"""
        ).fetchall()
    drivers = [
        row for row in rows
        if row[4] != "closed" and not metadata_indicates_closed(row[3])
        and _money_role(str(row[1]), str(row[2]), str(row[0])) == "spend_driver"
    ]
    if not drivers:
        return {"coverage_status": "unknown", "coverage_detail": "No spending feeds have established coverage.", "coverage_through": None}
    missing = [row for row in drivers if row[5] is None or row[5] < end_date - timedelta(days=7)]
    dates = [min(row[5], end_date) for row in drivers if isinstance(row[5], date)]
    through = min(dates).isoformat() if dates else None
    detail = (
        f"Confirm transaction coverage for {', '.join(str(row[0]) for row in missing)}. A gap in posted activity does not prove that transactions are missing."
        if missing else "No known late spending feeds. Transaction recency does not certify a complete statement."
    )
    return {"coverage_status": "incomplete" if missing else "current", "coverage_detail": detail, "coverage_through": through}
