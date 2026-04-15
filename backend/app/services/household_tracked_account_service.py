"""CRUD helpers for household account customizations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdTrackedAccount, HouseholdTrackedAccountInput
from app.services._household_finance_utils import iso
from app.services.household_account_identity import account_identity_candidates, clean_text
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


def _normalize_asset_group(value: str) -> str:
    normalized = clean_text(value)
    if normalized is None:
        raise ValueError("Asset group is required")
    lowered = normalized.lower()
    if lowered not in _ASSET_GROUPS:
        raise ValueError(f"Unsupported asset group: {value}")
    return lowered


class HouseholdTrackedAccountService:
    """Persist user-facing account labels and notes, anchored to canonical accounts."""

    def list_accounts(self, service: Any, *, limit: int = 100) -> list[HouseholdTrackedAccount]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, household_account_id, label, asset_group, account_type, source_type,
                       match_key, institution_name, owner_name, account_mask, notes,
                       created_at, updated_at
                FROM household_tracked_accounts
                ORDER BY updated_at DESC, created_at DESC
                LIMIT %s
                """,
                [max(limit, 1)],
            ).fetchall()
        return [row_to_tracked_account(row, iso=iso) for row in rows]

    def sync_linked_accounts_from_evidence(self, service: Any, *, limit: int = 500) -> int:
        summary = service.account_registry_service.sync_registry(service, limit=limit)
        tracked_linked = summary.get("tracked_linked", 0) if isinstance(summary, dict) else 0
        return int(tracked_linked) if isinstance(tracked_linked, int | float | str) and str(tracked_linked).strip() else 0

    def create_account(
        self,
        service: Any,
        payload: HouseholdTrackedAccountInput,
    ) -> HouseholdTrackedAccount:
        account = self._normalize_payload(payload)
        self._ensure_unique_identity(service, account=account)
        account_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        with service.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO household_tracked_accounts (
                    id, household_account_id, label, asset_group, account_type, source_type,
                    match_key, institution_name, owner_name, account_mask, notes,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    account_id,
                    None,
                    account["label"],
                    account["asset_group"],
                    account["account_type"],
                    account["source_type"],
                    account["match_key"],
                    account["institution_name"],
                    account["owner_name"],
                    account["account_mask"],
                    account["notes"],
                    now,
                    now,
                ],
            )
            conn.commit()
        service.account_registry_service.sync_registry(service, limit=500)
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
        if existing.household_account_id:
            account["asset_group"] = existing.asset_group
            account["account_type"] = existing.account_type
            account["source_type"] = existing.source_type
            account["match_key"] = existing.match_key
            account["institution_name"] = existing.institution_name
            account["account_mask"] = existing.account_mask
        elif existing.match_key or existing.account_mask:
            account["asset_group"] = existing.asset_group
            account["account_type"] = existing.account_type
            account["source_type"] = existing.source_type
            account["match_key"] = existing.match_key
            account["institution_name"] = existing.institution_name
            account["owner_name"] = existing.owner_name
            account["account_mask"] = existing.account_mask
        if not existing.household_account_id:
            self._ensure_unique_identity(service, account=account, exclude_account_id=account_id)
        with service.storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_tracked_accounts
                SET label = %s,
                    asset_group = %s,
                    account_type = %s,
                    source_type = %s,
                    match_key = %s,
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
                    account["match_key"],
                    account["institution_name"],
                    account["owner_name"],
                    account["account_mask"],
                    account["notes"],
                    datetime.now(UTC).isoformat(),
                    account_id,
                ],
            )
            conn.commit()
        service.account_registry_service.sync_registry(service, limit=500)
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
                SELECT id, household_account_id, label, asset_group, account_type, source_type,
                       match_key, institution_name, owner_name, account_mask, notes,
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
        label = clean_text(payload.label)
        account_type = clean_text(payload.account_type)
        source_type = clean_text(payload.source_type)
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
            "match_key": clean_text(payload.match_key),
            "institution_name": clean_text(payload.institution_name),
            "owner_name": clean_text(payload.owner_name),
            "account_mask": clean_text(payload.account_mask),
            "notes": clean_text(payload.notes),
        }

    def _ensure_unique_identity(
        self,
        service: Any,
        *,
        account: dict[str, str | None],
        exclude_account_id: str | None = None,
    ) -> None:
        candidate_keys = account_identity_candidates(
            source_type=account["source_type"],
            asset_group=account["asset_group"],
            account_type=account["account_type"],
            institution_name=account["institution_name"],
            account_name=account["label"],
            owner_name=account["owner_name"],
            account_mask=account["account_mask"],
            fallback_label=account["label"],
            explicit_match_key=account["match_key"],
        )
        if not candidate_keys:
            return
        for existing in self.list_accounts(service, limit=500):
            if exclude_account_id is not None and existing.id == exclude_account_id:
                continue
            existing_keys = account_identity_candidates(
                source_type=existing.source_type,
                asset_group=existing.asset_group,
                account_type=existing.account_type,
                institution_name=existing.institution_name,
                account_name=existing.label,
                owner_name=existing.owner_name,
                account_mask=existing.account_mask,
                fallback_label=existing.label,
                explicit_match_key=existing.match_key,
            )
            if set(candidate_keys) & set(existing_keys):
                raise ValueError(
                    f"Tracked account already exists for {existing.label}. Rename that row instead of creating a duplicate."
                )
