"""Shared household-account lifecycle helpers."""

from __future__ import annotations

import re
from typing import Any

_CLOSED_STATUS_VALUES = frozenset({"closed", "inactive_closed", "closed_by_user"})
_CLOSED_TEXT_RE = re.compile(r"\bclosed\b", re.IGNORECASE)


def metadata_indicates_closed(metadata: object) -> bool:
    if not isinstance(metadata, dict):
        return False
    for flag in ("closed", "is_closed"):
        if metadata.get(flag) is True:
            return True
    for key in ("account_status", "lifecycle_status", "status"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip().lower() in _CLOSED_STATUS_VALUES:
            return True
    return False


def text_indicates_closed(*values: object) -> bool:
    return any(
        isinstance(value, str) and bool(_CLOSED_TEXT_RE.search(value))
        for value in values
    )


def account_context_indicates_closed(
    *,
    metadata: object = None,
    labels: tuple[object, ...] = (),
) -> bool:
    return metadata_indicates_closed(metadata) or text_indicates_closed(*labels)


def fetch_closed_household_account_ids(storage: Any) -> set[str]:
    with storage.connection() as conn:
        rows = conn.execute("SELECT id::text, metadata FROM household_accounts").fetchall()
    return {
        str(row[0])
        for row in rows
        if metadata_indicates_closed(row[1])
    }


def fetch_hidden_household_account_ids(storage: Any) -> set[str]:
    """Return canonical accounts the user removed from active Money views."""
    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT household_account_id::text
            FROM household_account_preferences
            WHERE hidden_at IS NOT NULL
            """
        ).fetchall()
    return {str(row[0]) for row in rows if row[0] is not None}
