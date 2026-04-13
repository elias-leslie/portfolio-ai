"""CRUD helpers for manually tracked household accounts."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdEvidenceAccount,
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


def _identity_key(
    *,
    match_key: str | None,
    label: str,
    asset_group: str,
    account_type: str,
    source_type: str,
    institution_name: str | None,
    owner_name: str | None,
    account_mask: str | None,
) -> str | None:
    normalized_match_key = _clean_text(match_key)
    normalized_institution = _clean_text(institution_name)
    normalized_owner = _clean_text(owner_name)
    normalized_mask = _clean_text(account_mask)
    if normalized_match_key:
        return f"match::{normalized_match_key.lower()}"
    if normalized_institution and normalized_mask:
        return f"institution-mask::{normalized_institution.lower()}|{normalized_mask.lower()}"
    if normalized_mask:
        return f"mask::{normalized_mask.lower()}|{asset_group.lower()}|{account_type.lower()}"
    if normalized_institution:
        return (
            "institution-label::"
            f"{normalized_institution.lower()}|{(normalized_owner or '').lower()}|{asset_group.lower()}|{source_type.lower()}|{label.lower()}"
        )
    return None


class HouseholdTrackedAccountService:
    """Persist manually tracked accounts used by the Money workspace."""

    def list_accounts(self, service: Any, *, limit: int = 100) -> list[HouseholdTrackedAccount]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, label, asset_group, account_type, source_type,
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
        tracked_accounts = self.list_accounts(service, limit=limit)
        evidence_by_match_key = self._latest_evidence_by_match_key(service, limit=limit)
        updates: list[tuple[str, str, str, str, str | None, str | None, str | None]] = []

        for account in tracked_accounts:
            if not account.match_key:
                continue
            evidence = evidence_by_match_key.get(account.match_key)
            if evidence is None:
                continue
            next_asset_group = evidence.asset_group
            next_account_type = evidence.account_type
            next_source_type = evidence.source_type
            next_institution_name = evidence.institution_name
            next_owner_name = evidence.owner_name if evidence.owner_name is not None else account.owner_name
            next_account_mask = evidence.account_mask if evidence.account_mask is not None else account.account_mask
            if (
                account.asset_group == next_asset_group
                and account.account_type == next_account_type
                and account.source_type == next_source_type
                and account.institution_name == next_institution_name
                and account.owner_name == next_owner_name
                and account.account_mask == next_account_mask
            ):
                continue
            updates.append(
                (
                    next_asset_group,
                    next_account_type,
                    next_source_type,
                    next_institution_name,
                    next_owner_name,
                    next_account_mask,
                    account.id,
                )
            )

        if not updates:
            return 0

        now = datetime.now(UTC).isoformat()
        with service.storage.connection() as conn:
            for asset_group, account_type, source_type, institution_name, owner_name, account_mask, account_id in updates:
                conn.execute(
                    """
                    UPDATE household_tracked_accounts
                    SET asset_group = %s,
                        account_type = %s,
                        source_type = %s,
                        institution_name = %s,
                        owner_name = %s,
                        account_mask = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    [
                        asset_group,
                        account_type,
                        source_type,
                        institution_name,
                        owner_name,
                        account_mask,
                        now,
                        account_id,
                    ],
                )
            conn.commit()
        return len(updates)

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
                    id, label, asset_group, account_type, source_type,
                    match_key, institution_name, owner_name, account_mask, notes,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    account_id,
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
        if existing.match_key or existing.account_mask:
            account["asset_group"] = existing.asset_group
            account["account_type"] = existing.account_type
            account["source_type"] = existing.source_type
            account["match_key"] = existing.match_key
            account["institution_name"] = existing.institution_name
            account["owner_name"] = existing.owner_name
            account["account_mask"] = existing.account_mask
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
            "match_key": _clean_text(payload.match_key),
            "institution_name": _clean_text(payload.institution_name),
            "owner_name": _clean_text(payload.owner_name),
            "account_mask": _clean_text(payload.account_mask),
            "notes": _clean_text(payload.notes),
        }

    def _ensure_unique_identity(
        self,
        service: Any,
        *,
        account: dict[str, str | None],
        exclude_account_id: str | None = None,
    ) -> None:
        identity = _identity_key(
            match_key=account["match_key"],
            label=str(account["label"] or ""),
            asset_group=str(account["asset_group"] or ""),
            account_type=str(account["account_type"] or ""),
            source_type=str(account["source_type"] or ""),
            institution_name=account["institution_name"],
            owner_name=account["owner_name"],
            account_mask=account["account_mask"],
        )
        if identity is None:
            return
        for existing in self.list_accounts(service, limit=500):
            if exclude_account_id is not None and existing.id == exclude_account_id:
                continue
            existing_identity = _identity_key(
                match_key=existing.match_key,
                label=existing.label,
                asset_group=existing.asset_group,
                account_type=existing.account_type,
                source_type=existing.source_type,
                institution_name=existing.institution_name,
                owner_name=existing.owner_name,
                account_mask=existing.account_mask,
            )
            if existing_identity == identity:
                raise ValueError(
                    f"Tracked account already exists for {existing.label}. Rename that row instead of creating a duplicate."
                )

    def _latest_evidence_by_match_key(
        self,
        service: Any,
        *,
        limit: int,
    ) -> dict[str, HouseholdEvidenceAccount]:
        grouped: dict[str, list[HouseholdEvidenceAccount]] = defaultdict(list)
        for account in service.list_evidence_accounts(limit=limit):
            match_key = self._evidence_match_key(account)
            if match_key:
                grouped[match_key].append(account)
        latest_by_match_key: dict[str, HouseholdEvidenceAccount] = {}
        for match_key, accounts in grouped.items():
            latest_by_match_key[match_key] = max(
                accounts,
                key=lambda account: (
                    account.as_of_date or "",
                    float(account.confidence or 0.0),
                ),
            )
        return latest_by_match_key

    @staticmethod
    def _evidence_match_key(account: HouseholdEvidenceAccount) -> str | None:
        normalized_institution = _clean_text(account.institution_name)
        normalized_name = _clean_text(account.account_name)
        normalized_owner = _clean_text(account.owner_name)
        normalized_mask = _clean_text(account.account_mask)
        normalized_type = _clean_text(account.account_type)
        normalized_group = _clean_text(account.asset_group)
        if normalized_mask:
            return f"evidence|{normalized_mask.lower()}|{(normalized_group or normalized_type or '').lower()}"
        if normalized_institution and normalized_name:
            if normalized_owner:
                return (
                    "evidence|"
                    f"{normalized_institution.lower()}|{normalized_name.lower()}|{normalized_owner.lower()}|{(normalized_type or normalized_group or '').lower()}"
                )
            return (
                "evidence|"
                f"{normalized_institution.lower()}|{normalized_name.lower()}|{(normalized_type or normalized_group or '').lower()}"
            )
        if normalized_name:
            if normalized_owner:
                return f"evidence|{normalized_name.lower()}|{normalized_owner.lower()}|{(normalized_type or normalized_group or '').lower()}"
            return f"evidence|{normalized_name.lower()}|{(normalized_type or normalized_group or '').lower()}"
        return None
