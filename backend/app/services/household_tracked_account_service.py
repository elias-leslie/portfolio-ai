"""CRUD helpers for manually tracked household accounts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdTrackedAccount,
    HouseholdTrackedAccountInput,
)
from app.services._household_finance_utils import iso
from app.services.household_finance_rows import row_to_tracked_account

_ASSET_GROUPS = {
    "cash",
    "credit",
    "debt",
    "education",
    "other",
    "retirement",
    "taxable",
}


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).strip().split())
    return cleaned or None


def _normalize_asset_group(value: str) -> str:
    normalized = _clean_text(value)
    if normalized is None:
        raise ValueError("Asset group is required")
    lowered = normalized.lower()
    if lowered not in _ASSET_GROUPS:
        raise ValueError(f"Unsupported asset group: {value}")
    return lowered


class HouseholdTrackedAccountService:
    """Persist manually tracked accounts used by the Money workspace."""

    def list_accounts(self, service: Any, *, limit: int = 100) -> list[HouseholdTrackedAccount]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, label, asset_group, account_type, source_type,
                       institution_name, owner_name, account_mask, notes,
                       created_at, updated_at
                FROM household_tracked_accounts
                ORDER BY updated_at DESC, created_at DESC
                LIMIT %s
                """,
                [max(limit, 1)],
            ).fetchall()
        return [row_to_tracked_account(row, iso=iso) for row in rows]

    def create_account(
        self,
        service: Any,
        payload: HouseholdTrackedAccountInput,
    ) -> HouseholdTrackedAccount:
        account = self._normalize_payload(payload)
        account_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        with service.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO household_tracked_accounts (
                    id, label, asset_group, account_type, source_type,
                    institution_name, owner_name, account_mask, notes,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    account_id,
                    account["label"],
                    account["asset_group"],
                    account["account_type"],
                    account["source_type"],
                    account["institution_name"],
                    account["owner_name"],
                    account["account_mask"],
                    account["notes"],
                    now,
                    now,
                ],
            )
            conn.commit()
        created = self.get_account(service, account_id)
        if created is None:
            raise RuntimeError("Failed to create tracked household account")
        return created

    def update_account(
        self,
        service: Any,
        account_id: str,
        payload: HouseholdTrackedAccountInput,
    ) -> HouseholdTrackedAccount | None:
        existing = self.get_account(service, account_id)
        if existing is None:
            return None
        account = self._normalize_payload(payload)
        with service.storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_tracked_accounts
                SET label = %s,
                    asset_group = %s,
                    account_type = %s,
                    source_type = %s,
                    institution_name = %s,
                    owner_name = %s,
                    account_mask = %s,
                    notes = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [
                    account["label"],
                    account["asset_group"],
                    account["account_type"],
                    account["source_type"],
                    account["institution_name"],
                    account["owner_name"],
                    account["account_mask"],
                    account["notes"],
                    datetime.now(UTC).isoformat(),
                    account_id,
                ],
            )
            conn.commit()
        return self.get_account(service, account_id)

    def delete_account(self, service: Any, account_id: str) -> bool:
        with service.storage.connection() as conn:
            deleted = conn.execute(
                "DELETE FROM household_tracked_accounts WHERE id = %s",
                [account_id],
            ).rowcount
            conn.commit()
        return bool(deleted)

    def get_account(self, service: Any, account_id: str) -> HouseholdTrackedAccount | None:
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT id, label, asset_group, account_type, source_type,
                       institution_name, owner_name, account_mask, notes,
                       created_at, updated_at
                FROM household_tracked_accounts
                WHERE id = %s
                """,
                [account_id],
            ).fetchone()
        if row is None:
            return None
        return row_to_tracked_account(row, iso=iso)

    def _normalize_payload(self, payload: HouseholdTrackedAccountInput) -> dict[str, str | None]:
        label = _clean_text(payload.label)
        account_type = _clean_text(payload.account_type)
        source_type = _clean_text(payload.source_type)
        if label is None:
            raise ValueError("Account label is required")
        if account_type is None:
            raise ValueError("Account type is required")
        if source_type is None:
            raise ValueError("Source type is required")
        return {
            "label": label,
            "asset_group": _normalize_asset_group(payload.asset_group),
            "account_type": account_type,
            "source_type": source_type.lower(),
            "institution_name": _clean_text(payload.institution_name),
            "owner_name": _clean_text(payload.owner_name),
            "account_mask": _clean_text(payload.account_mask),
            "notes": _clean_text(payload.notes),
        }
