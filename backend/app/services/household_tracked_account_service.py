"""CRUD helpers for user-facing household account preferences."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdTrackedAccount, HouseholdTrackedAccountInput
from app.services._household_finance_utils import iso
from app.services.household_account_identity import (
    account_identity_candidates,
    clean_text,
    derive_account_mask,
)
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
    """Persist display preferences on the canonical household-account spine."""

    def list_accounts(self, service: Any, *, limit: int = 100) -> list[HouseholdTrackedAccount]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    p.id,
                    p.household_account_id,
                    COALESCE(NULLIF(p.display_label, ''), a.canonical_label) AS label,
                    a.asset_group,
                    a.account_type,
                    a.source_type,
                    a.primary_identity_key AS match_key,
                    a.institution_name,
                    COALESCE(NULLIF(p.display_owner_name, ''), a.owner_name) AS owner_name,
                    a.account_mask,
                    p.notes,
                    p.created_at,
                    p.updated_at
                FROM household_account_preferences p
                JOIN household_accounts a ON a.id = p.household_account_id
                WHERE p.hidden_at IS NULL
                ORDER BY p.updated_at DESC, p.created_at DESC
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
        household_account_id = clean_text(payload.household_account_id)
        if household_account_id:
            existing = self.get_account_by_household_account_id(
                service,
                household_account_id,
            )
            if existing is not None:
                updated = self.update_account(service, existing.id, payload)
                if updated is None:
                    raise RuntimeError("Failed to update linked household account")
                return updated
            canonical = self._get_canonical_account(service, household_account_id)
            if canonical is None:
                raise ValueError(f"Household account not found: {household_account_id}")
            return self._insert_account(
                service,
                account=account,
                household_account_id=household_account_id,
            )

        household_account_id = self._ensure_canonical_account(service, account=account)
        return self._insert_account(
            service,
            account=account,
            household_account_id=household_account_id,
        )

    def _insert_account(
        self,
        service: Any,
        *,
        account: dict[str, str | None],
        household_account_id: str,
    ) -> HouseholdTrackedAccount:
        account_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        with service.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO household_account_preferences (
                    id, household_account_id, display_label, display_owner_name,
                    notes, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (household_account_id) DO UPDATE
                SET display_label = EXCLUDED.display_label,
                    display_owner_name = EXCLUDED.display_owner_name,
                    notes = EXCLUDED.notes,
                    hidden_at = NULL,
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    account_id,
                    household_account_id,
                    account["label"],
                    account["owner_name"],
                    account["notes"],
                    now,
                    now,
                ],
            )
            conn.commit()
        service.account_registry_service.sync_registry(service, limit=500)
        created = self.get_account_by_household_account_id(service, household_account_id)
        if created is None:
            raise RuntimeError("Failed to save household account preferences")
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
            canonical = self._get_canonical_account(service, existing.household_account_id)
            if canonical is not None:
                account = self._lock_account_to_canonical(account, canonical=canonical)
            else:
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
                UPDATE household_account_preferences
                SET display_label = %s,
                    display_owner_name = %s,
                    notes = %s,
                    hidden_at = NULL,
                    updated_at = %s
                WHERE id = %s
                """,
                [
                    account["label"],
                    account["owner_name"],
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
                "DELETE FROM household_account_preferences WHERE id = %s",
                [account_id],
            ).rowcount
            conn.commit()
        if deleted:
            service.account_registry_service.sync_registry(service, limit=500)
        return bool(deleted)

    def get_account(self, service: Any, account_id: str) -> HouseholdTrackedAccount | None:
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    p.id,
                    p.household_account_id,
                    COALESCE(NULLIF(p.display_label, ''), a.canonical_label) AS label,
                    a.asset_group,
                    a.account_type,
                    a.source_type,
                    a.primary_identity_key AS match_key,
                    a.institution_name,
                    COALESCE(NULLIF(p.display_owner_name, ''), a.owner_name) AS owner_name,
                    a.account_mask,
                    p.notes,
                    p.created_at,
                    p.updated_at
                FROM household_account_preferences p
                JOIN household_accounts a ON a.id = p.household_account_id
                WHERE p.id = %s AND p.hidden_at IS NULL
                """,
                [account_id],
            ).fetchone()
        if row is None:
            return None
        return row_to_tracked_account(row, iso=iso)

    def get_account_by_household_account_id(
        self,
        service: Any,
        household_account_id: str,
    ) -> HouseholdTrackedAccount | None:
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    p.id,
                    p.household_account_id,
                    COALESCE(NULLIF(p.display_label, ''), a.canonical_label) AS label,
                    a.asset_group,
                    a.account_type,
                    a.source_type,
                    a.primary_identity_key AS match_key,
                    a.institution_name,
                    COALESCE(NULLIF(p.display_owner_name, ''), a.owner_name) AS owner_name,
                    a.account_mask,
                    p.notes,
                    p.created_at,
                    p.updated_at
                FROM household_account_preferences p
                JOIN household_accounts a ON a.id = p.household_account_id
                WHERE p.household_account_id = %s AND p.hidden_at IS NULL
                ORDER BY p.updated_at DESC, p.created_at DESC
                LIMIT 1
                """,
                [household_account_id],
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

    def _identity_candidates_for_account(self, account: dict[str, str | None]) -> list[str]:
        return account_identity_candidates(
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

    def _ensure_canonical_account(
        self,
        service: Any,
        *,
        account: dict[str, str | None],
    ) -> str:
        candidate_keys = self._identity_candidates_for_account(account)
        if candidate_keys:
            with service.storage.connection() as conn:
                row = conn.execute(
                    """
                    SELECT household_account_id
                    FROM household_account_identities
                    WHERE identity_key = ANY(%s)
                    LIMIT 1
                    """,
                    [candidate_keys],
                ).fetchone()
            if row is not None and row[0] is not None:
                return str(row[0])

        account_id = str(uuid.uuid4())
        primary_identity = candidate_keys[0] if candidate_keys else f"manual::{account_id}"
        now = datetime.now(UTC).isoformat()
        account_mask = derive_account_mask(
            account["account_mask"],
            account["label"],
            account["label"],
        )
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM household_accounts
                WHERE primary_identity_key = %s
                LIMIT 1
                """,
                [primary_identity],
            ).fetchone()
            if row is not None and row[0] is not None:
                return str(row[0])
            conn.execute(
                """
                INSERT INTO household_accounts (
                    id, primary_identity_key, canonical_label, asset_group, account_type,
                    source_type, institution_name, owner_name, account_mask, metadata,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                [
                    account_id,
                    primary_identity,
                    account["label"],
                    account["asset_group"],
                    account["account_type"],
                    account["source_type"],
                    account["institution_name"],
                    account["owner_name"],
                    account_mask,
                    "{}",
                    now,
                    now,
                ],
            )
            for key in candidate_keys:
                conn.execute(
                    """
                    INSERT INTO household_account_identities (
                        id, household_account_id, identity_key, identity_kind,
                        is_primary, confidence, metadata, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (identity_key) DO NOTHING
                    """,
                    [
                        str(uuid.uuid4()),
                        account_id,
                        key,
                        "composite",
                        key == primary_identity,
                        None,
                        "{}",
                        now,
                        now,
                    ],
                )
            conn.commit()
        return account_id

    def _get_canonical_account(
        self,
        service: Any,
        household_account_id: str,
    ) -> dict[str, str | None] | None:
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT id, primary_identity_key, canonical_label, asset_group, account_type,
                       source_type, institution_name, owner_name, account_mask
                FROM household_accounts
                WHERE id = %s
                LIMIT 1
                """,
                [household_account_id],
            ).fetchone()
        if row is None:
            return None
        return {
            "id": str(row[0]),
            "primary_identity_key": str(row[1]) if row[1] is not None else None,
            "canonical_label": str(row[2]) if row[2] is not None else None,
            "asset_group": str(row[3]),
            "account_type": str(row[4]),
            "source_type": str(row[5]),
            "institution_name": str(row[6]) if row[6] is not None else None,
            "owner_name": str(row[7]) if row[7] is not None else None,
            "account_mask": str(row[8]) if row[8] is not None else None,
        }

    def _lock_account_to_canonical(
        self,
        account: dict[str, str | None],
        *,
        canonical: dict[str, str | None],
    ) -> dict[str, str | None]:
        account["asset_group"] = canonical["asset_group"]
        account["account_type"] = canonical["account_type"]
        account["source_type"] = str(canonical["source_type"] or "").lower()
        account["match_key"] = canonical["primary_identity_key"]
        account["institution_name"] = canonical["institution_name"]
        account["account_mask"] = canonical["account_mask"]
        return account

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
                    f"Account already exists for {existing.label}. Rename that row instead of creating a duplicate."
                )
