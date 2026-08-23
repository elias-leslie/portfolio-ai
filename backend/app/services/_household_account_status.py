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


def fetch_registry_account_overrides(storage: Any) -> dict[str, dict[str, str]]:
    """Return what an operator corrected about an account the provider gets wrong.

    Two overrides live on the registry row, and both exist because the provider
    is not wrong once but wrong on every sync: Fidelity reports a 529 as
    ``Taxable``, and Chase reports two different cards under one name,
    ``Ultimate Rewards``. Correcting either at the source would be undone by the
    next refresh, so the correction lives on the registry and is reapplied.

    Both were read back only inside the registry. Every surface built from
    account summaries -- the dashboard, the money inbox, the account list -- kept
    showing the provider's version, so an override could be set, be visible in
    the registry, and change nothing the household actually looks at.

    Only overridden rows appear here. A registry value that merely agrees with
    the provider has nothing to correct, and preferring the registry everywhere
    would move totals and rename accounts nobody asked to change.
    """
    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT id::text,
                   metadata -> 'classification_override' IS NOT NULL AS has_classification,
                   asset_group, account_type,
                   metadata -> 'identity_override' IS NOT NULL AS has_identity,
                   canonical_label, account_mask, owner_name
            FROM household_accounts
            WHERE (
                    jsonb_exists(COALESCE(metadata, '{}'::jsonb), 'classification_override')
                 OR jsonb_exists(COALESCE(metadata, '{}'::jsonb), 'identity_override')
            )
              AND archived_at IS NULL
            """
        ).fetchall()
    overrides: dict[str, dict[str, str]] = {}
    for row in rows:
        entry: dict[str, str] = {}
        if bool(row[1]):
            if row[2]:
                entry["asset_group"] = str(row[2])
            if row[3]:
                entry["account_type"] = str(row[3])
        if bool(row[4]):
            if row[5]:
                entry["label"] = str(row[5])
            if row[6]:
                entry["account_mask"] = str(row[6])
            if row[7]:
                entry["owner_name"] = str(row[7])
        if entry:
            overrides[str(row[0])] = entry
    return overrides


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
