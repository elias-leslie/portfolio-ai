"""Canonical household-account registry and self-healing linkage."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg

from app.models.household_finance import HouseholdEvidenceAccount, HouseholdTrackedAccount
from app.portfolio.models import Account
from app.services._household_finance_utils import iso, iso_or_none, to_float
from app.services.household_account_identity import (
    account_identity_candidates,
    account_masks_conflict,
    account_masks_match,
    clean_text,
    derive_account_mask,
    looks_generic_account_mask,
    normalize_account_mask,
    normalize_text,
)
from app.services.household_finance_rows import row_to_evidence_account, row_to_tracked_account

_EVIDENCE_COLS = (
    "id, document_id, household_account_id, source_type, asset_group, account_type, "
    "institution_name, account_name, account_mask, owner_name, currency, "
    "balance, holdings_value, cash_balance, as_of_date, metadata, confidence"
)
_TRACKED_COLS = (
    "id, household_account_id, label, asset_group, account_type, source_type, "
    "match_key, institution_name, owner_name, account_mask, notes, created_at, updated_at"
)
_MATCH_STOPWORDS = {
    "account",
    "card",
    "plan",
    "investment",
    "deferred",
    "compensation",
    "retirement",
    "ira",
}
_PORTFOLIO_ACCOUNT_GROUPS = {
    "401k": "retirement",
    "HSA": "retirement",
    "IRA": "retirement",
    "Roth": "retirement",
    "Taxable": "taxable",
}
_MASK_IDENTITY_PREFIXES = ("institution-mask::", "mask::", "mask-asset::")


@dataclass(slots=True)
class HouseholdCanonicalAccount:
    id: str
    primary_identity_key: str | None
    canonical_label: str | None
    asset_group: str
    account_type: str
    source_type: str
    institution_name: str | None
    owner_name: str | None
    account_mask: str | None
    metadata: dict[str, object]


def _load_json_object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): nested for key, nested in value.items()}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_label(
    *,
    institution_name: str | None,
    account_name: str | None,
    account_mask: str | None,
    account_type: str | None,
) -> str:
    if clean_text(account_name):
        return str(clean_text(account_name))
    if clean_text(institution_name) and clean_text(account_mask):
        return f"{clean_text(institution_name)} · …{clean_text(account_mask)}"
    if clean_text(institution_name):
        return str(clean_text(institution_name))
    return str(clean_text(account_type) or "Account")


def _looks_generic_account_name(value: str | None) -> bool:
    text = clean_text(value)
    if not text:
        return True
    normalized = text.lower()
    return normalized in {
        "account",
        "accounts",
        "bank account",
        "brokerage account",
        "cash management account",
        "cash management (joint wros)",
        "cash management account (cma)",
        "chase credit card activity export",
        "credit card",
        "credit card activity export",
        "credit card statement",
        "retirement account",
        "529 college savings account",
    }


def _parse_iso_timestamp(value: object) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _evidence_recency_timestamp(row: dict[str, object]) -> datetime:
    for candidate in (
        row.get("as_of_date"),
        row.get("document_statement_end"),
        row.get("document_uploaded_at"),
        row.get("updated_at"),
        row.get("created_at"),
    ):
        parsed = _parse_iso_timestamp(candidate)
        if parsed is not None:
            return parsed
    return datetime.fromtimestamp(0, UTC)


def _evidence_mask_rank(row: dict[str, object]) -> tuple[int, datetime, str]:
    metadata = _load_json_object(row.get("metadata"))
    extracted_mask = clean_text(metadata.get("extracted_account_mask"))
    mask = extracted_mask or clean_text(row.get("account_mask"))
    if not mask or looks_generic_account_mask(mask):
        return (-1, _evidence_recency_timestamp(row), "")
    filename = clean_text(metadata.get("document_filename"))
    filename_mask = derive_account_mask(None, clean_text(row.get("account_name")), filename)
    score = 0
    if extracted_mask:
        score += 100
    if filename_mask and clean_text(filename_mask) == mask:
        score += 90
    if metadata.get("plaid_account_id"):
        score += 80
    if metadata.get("extracted_account_mask"):
        score += 30
    if (
        row.get("balance") is not None
        or row.get("holdings_value") is not None
        or row.get("cash_balance") is not None
    ):
        score += 40
    filename_text = (filename or "").lower()
    if any(token in filename_text for token in ("activity", "history", "transactions", "export")):
        score -= 35
    if any(char.isdigit() for char in mask):
        score += 10
    if row.get("source_type") in {"bank", "brokerage", "retirement", "credit_card"}:
        score += 8
    confidence = row.get("confidence")
    if isinstance(confidence, (int, float)):
        score += int(float(confidence) * 5)
    return (score, _evidence_recency_timestamp(row), mask)


def _evidence_name_rank(row: dict[str, object]) -> tuple[int, datetime, str]:
    name = clean_text(row.get("account_name"))
    if not name:
        return (-1, _evidence_recency_timestamp(row), "")
    score = 0
    if not _looks_generic_account_name(name):
        score += 40
    metadata = _load_json_object(row.get("metadata"))
    if metadata.get("beneficiary_name"):
        score += 25
    if row.get("account_mask") and not looks_generic_account_mask(row.get("account_mask")):
        score += 15
    if row.get("owner_name"):
        score += 10
    confidence = row.get("confidence")
    if isinstance(confidence, (int, float)):
        score += int(float(confidence) * 5)
    return (score, _evidence_recency_timestamp(row), name)


def _canonical_identity_strength(account: HouseholdCanonicalAccount) -> int:
    score = 0
    if clean_text(account.institution_name):
        score += 30
    if clean_text(account.owner_name):
        score += 25
    if clean_text(account.account_mask) and not looks_generic_account_mask(account.account_mask):
        score += 20
    if clean_text(account.primary_identity_key):
        score += 10
    if clean_text(account.canonical_label) and not _looks_generic_account_name(
        account.canonical_label
    ):
        score += 10
    return score


def _name_tokens(*values: str | None) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        normalized = clean_text(value)
        if not normalized:
            continue
        for token in re.split(r"[^a-z0-9]+", normalized.lower()):
            if len(token) < 3 or token in _MATCH_STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def _owner_matches(left: str | None, right: str | None) -> bool:
    left_text = clean_text(left)
    right_text = clean_text(right)
    if not left_text or not right_text:
        return False
    left_tokens = left_text.lower().split()
    right_tokens = right_text.lower().split()
    return left_tokens[0] == right_tokens[0] or left_text.lower() == right_text.lower()


def _identity_key_has_mask_evidence(identity_key: str) -> bool:
    if identity_key.startswith("match::"):
        return _identity_key_has_mask_evidence(identity_key.removeprefix("match::"))
    if identity_key.startswith(_MASK_IDENTITY_PREFIXES):
        return True
    if not identity_key.startswith("evidence|"):
        return False
    parts = identity_key.split("|")
    return len(parts) > 1 and any(char.isdigit() for char in parts[1])


def _mask_identity_candidates(candidate_keys: list[str]) -> list[str]:
    return [key for key in candidate_keys if _identity_key_has_mask_evidence(key)]


def _registry_identity_candidates(
    candidate_keys: list[str],
    *,
    explicit_match_key: str | None = None,
) -> list[str]:
    explicit = normalize_text(explicit_match_key)
    explicit_candidates = {explicit, f"match::{explicit}"} if explicit else set()
    return [
        key
        for key in candidate_keys
        if _identity_key_has_mask_evidence(key) or key in explicit_candidates
    ]


def _trusted_evidence_account_mask(evidence: HouseholdEvidenceAccount) -> str | None:
    if isinstance(evidence.metadata, dict):
        extracted_mask = clean_text(evidence.metadata.get("extracted_account_mask"))
        if extracted_mask and not looks_generic_account_mask(extracted_mask):
            return extracted_mask
    return evidence.account_mask


class HouseholdAccountRegistryService:
    """Own canonical household-account identities across evidence, settings, and ledger."""

    @staticmethod
    def _evidence_fallback_label(evidence: HouseholdEvidenceAccount) -> str | None:
        if not isinstance(evidence.metadata, dict):
            return None
        raw = evidence.metadata.get("document_filename") or evidence.metadata.get(
            "document_account_label"
        )
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None

    def _evidence_matches_canonical_account(
        self,
        *,
        evidence: HouseholdEvidenceAccount,
        canonical_account: HouseholdCanonicalAccount,
        allow_mask_conflict: bool = False,
        require_mask: bool = True,
    ) -> bool:
        evidence_source_type = clean_text(evidence.source_type)
        canonical_source_type = clean_text(canonical_account.source_type)
        evidence_asset_group = clean_text(evidence.asset_group)
        canonical_asset_group = clean_text(canonical_account.asset_group)
        evidence_account_type = clean_text(evidence.account_type)
        canonical_account_type = clean_text(canonical_account.account_type)
        evidence_institution = clean_text(evidence.institution_name)
        canonical_institution = clean_text(canonical_account.institution_name)
        evidence_owner = clean_text(evidence.owner_name)
        canonical_owner = clean_text(canonical_account.owner_name)

        has_mismatch = any(
            (
                evidence_source_type
                and canonical_source_type
                and evidence_source_type != canonical_source_type,
                evidence_asset_group
                and canonical_asset_group
                and evidence_asset_group != canonical_asset_group,
                evidence_account_type
                and canonical_account_type
                and evidence_account_type != canonical_account_type,
                evidence_institution
                and canonical_institution
                and evidence_institution != canonical_institution,
                evidence_owner
                and canonical_owner
                and not _owner_matches(evidence_owner, canonical_owner),
            )
        )
        if has_mismatch:
            return False

        evidence_mask = derive_account_mask(
            _trusted_evidence_account_mask(evidence),
            evidence.account_name,
            self._evidence_fallback_label(evidence),
        )
        if not evidence_mask:
            return not require_mask
        if allow_mask_conflict:
            return True
        canonical_mask = clean_text(canonical_account.account_mask)
        return not account_masks_conflict(evidence_mask, canonical_mask)

    def sync_registry(self, service: Any, *, limit: int = 500) -> dict[str, int]:
        with service.storage.connection() as conn:
            canonical_accounts = self._fetch_accounts(conn)
            identity_map = self._fetch_identity_map(conn)
            evidence_accounts = self._fetch_evidence_accounts(conn, limit=limit)
            tracked_accounts = self._fetch_tracked_accounts(conn, limit=limit)
            portfolio_accounts = self._fetch_portfolio_accounts(conn)

            accounts_created = 0
            accounts_merged = 0
            accounts_pruned = 0
            evidence_linked = 0
            tracked_linked = 0
            portfolio_linked = 0
            transaction_linked = 0

            for evidence in evidence_accounts:
                account_id, created, merged = self._resolve_from_evidence(
                    conn,
                    evidence=evidence,
                    canonical_accounts=canonical_accounts,
                    identity_map=identity_map,
                )
                accounts_created += created
                accounts_merged += merged
                if evidence.household_account_id != account_id:
                    conn.execute(
                        """
                        UPDATE household_evidence_accounts
                        SET household_account_id = %s
                        WHERE id = %s
                        """,
                        [account_id, evidence.id],
                    )
                    evidence_linked += 1
                    evidence.household_account_id = account_id

            accounts_merged += self._merge_shadow_accounts(
                conn,
                canonical_accounts=canonical_accounts,
                identity_map=identity_map,
            )
            self._refresh_accounts_from_linked_evidence(
                conn,
                canonical_accounts=canonical_accounts,
            )

            for tracked in tracked_accounts:
                account_id, created = self._resolve_from_tracked(
                    conn,
                    tracked=tracked,
                    canonical_accounts=canonical_accounts,
                    identity_map=identity_map,
                )
                if created:
                    accounts_created += 1
                if tracked.household_account_id != account_id:
                    linked, deleted = self._link_tracked_account(
                        conn,
                        tracked=tracked,
                        account_id=account_id,
                        canonical_account=canonical_accounts[account_id],
                    )
                    tracked_linked += linked
                    if deleted:
                        continue
                tracked_linked += self._sync_tracked_identity_snapshot(
                    conn,
                    tracked=tracked,
                    canonical_account=canonical_accounts[account_id],
                )
            portfolio_linked = self._sync_portfolio_accounts(
                conn,
                canonical_accounts=canonical_accounts,
                tracked_accounts=tracked_accounts,
                portfolio_accounts=portfolio_accounts,
            )
            transaction_linked = self._sync_transactions(conn, identity_map=identity_map)
            accounts_pruned = self._prune_orphan_accounts(
                conn,
                canonical_accounts=canonical_accounts,
                identity_map=identity_map,
            )
            conn.commit()

        return {
            "accounts_created": accounts_created,
            "accounts_merged": accounts_merged,
            "accounts_pruned": accounts_pruned,
            "evidence_linked": evidence_linked,
            "tracked_linked": tracked_linked,
            "portfolio_linked": portfolio_linked,
            "transaction_linked": transaction_linked,
        }

    def rebuild_registry(self, service: Any, *, limit: int = 5000) -> dict[str, int]:
        with service.storage.connection() as conn:
            conn.execute("UPDATE portfolio_accounts SET household_account_id = NULL")
            conn.execute("UPDATE household_transactions SET household_account_id = NULL")
            conn.execute("UPDATE household_tracked_accounts SET household_account_id = NULL")
            conn.execute("UPDATE household_evidence_accounts SET household_account_id = NULL")
            conn.execute("DELETE FROM household_account_identities")
            conn.execute("DELETE FROM household_accounts")
            conn.commit()
        return self.sync_registry(service, limit=limit)

    def _fetch_accounts(self, conn: Any) -> dict[str, HouseholdCanonicalAccount]:
        rows = conn.execute(
            """
            SELECT id, primary_identity_key, canonical_label, asset_group, account_type, source_type,
                   institution_name, owner_name, account_mask, metadata
            FROM household_accounts
            """
        ).fetchall()
        return {
            str(row[0]): HouseholdCanonicalAccount(
                id=str(row[0]),
                primary_identity_key=str(row[1]) if row[1] is not None else None,
                canonical_label=str(row[2]) if row[2] is not None else None,
                asset_group=str(row[3]),
                account_type=str(row[4]),
                source_type=str(row[5]),
                institution_name=str(row[6]) if row[6] is not None else None,
                owner_name=str(row[7]) if row[7] is not None else None,
                account_mask=str(row[8]) if row[8] is not None else None,
                metadata=_load_json_object(row[9]),
            )
            for row in rows
        }

    def _fetch_identity_map(self, conn: Any) -> dict[str, str]:
        rows = conn.execute(
            """
            SELECT identity_key, household_account_id
            FROM household_account_identities
            """
        ).fetchall()
        return {str(row[0]): str(row[1]) for row in rows}

    def _fetch_evidence_accounts(self, conn: Any, *, limit: int) -> list[HouseholdEvidenceAccount]:
        rows = conn.execute(
            """
            SELECT
                ea.id,
                ea.document_id,
                ea.household_account_id,
                ea.source_type,
                ea.asset_group,
                ea.account_type,
                ea.institution_name,
                ea.account_name,
                ea.account_mask,
                ea.owner_name,
                ea.currency,
                ea.balance,
                ea.holdings_value,
                ea.cash_balance,
                ea.as_of_date,
                COALESCE(ea.metadata, '{}'::jsonb)
                    || jsonb_build_object(
                        'document_filename', d.filename,
                        'document_account_label', d.account_label
                    ) AS metadata,
                ea.confidence
            FROM household_evidence_accounts ea
            LEFT JOIN household_documents d ON d.id = ea.document_id
            ORDER BY updated_at DESC, created_at DESC
            LIMIT %s
            """,
            [max(limit, 1)],
        ).fetchall()
        return [
            row_to_evidence_account(row, to_float=to_float, iso_or_none=iso_or_none) for row in rows
        ]

    def _fetch_tracked_accounts(self, conn: Any, *, limit: int) -> list[HouseholdTrackedAccount]:
        rows = conn.execute(
            """
            SELECT id, household_account_id, label, asset_group, account_type, source_type,
                   match_key, institution_name, owner_name, account_mask, notes, created_at, updated_at
            FROM (
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

                UNION ALL

                SELECT id, household_account_id, label, asset_group, account_type, source_type,
                       match_key, institution_name, owner_name, account_mask, notes, created_at, updated_at
                FROM household_tracked_accounts
                WHERE household_account_id IS NULL
            ) tracked
            ORDER BY updated_at DESC, created_at DESC
            LIMIT %s
            """,
            [max(limit, 1)],
        ).fetchall()
        return [row_to_tracked_account(row, iso=iso) for row in rows]

    def _fetch_portfolio_accounts(self, conn: Any) -> list[Account]:
        rows = conn.execute(
            """
            SELECT id, name, account_type, household_account_id, cash_balance, initial_cash, created_at, updated_at
            FROM portfolio_accounts
            ORDER BY created_at
            """
        ).fetchall()
        return [
            Account(
                id=str(row[0]),
                name=str(row[1]),
                account_type=str(row[2]),
                household_account_id=str(row[3]) if row[3] is not None else None,
                cash_balance=float(row[4] or 0.0),
                initial_cash=float(row[5] or 0.0),
                created_at=row[6],
                updated_at=row[7],
            )
            for row in rows
        ]

    def _resolve_from_evidence(
        self,
        conn: Any,
        *,
        evidence: HouseholdEvidenceAccount,
        canonical_accounts: dict[str, HouseholdCanonicalAccount],
        identity_map: dict[str, str],
    ) -> tuple[str, int, int]:
        stale_candidate_keys: set[str] = set()
        explicit_match_key = (
            str(evidence.metadata.get("match_key"))
            if isinstance(evidence.metadata, dict) and evidence.metadata.get("match_key")
            else None
        )
        candidates = _registry_identity_candidates(
            account_identity_candidates(
                source_type=evidence.source_type,
                asset_group=evidence.asset_group,
                account_type=evidence.account_type,
                institution_name=evidence.institution_name,
                account_name=evidence.account_name,
                owner_name=evidence.owner_name,
                account_mask=_trusted_evidence_account_mask(evidence),
                fallback_label=self._evidence_fallback_label(evidence),
                explicit_match_key=explicit_match_key,
            ),
            explicit_match_key=explicit_match_key,
        )
        matched_ids: set[str] = set()
        preserved_account_id = (
            str(evidence.metadata.get("preserved_household_account_id"))
            if isinstance(evidence.metadata, dict)
            and evidence.metadata.get("preserved_household_account_id")
            else None
        )
        if (
            preserved_account_id
            and preserved_account_id in canonical_accounts
            and self._evidence_matches_canonical_account(
                evidence=evidence,
                canonical_account=canonical_accounts[preserved_account_id],
                allow_mask_conflict=True,
                require_mask=False,
            )
        ):
            matched_ids.add(preserved_account_id)
        for key in candidates:
            mapped_account_id = identity_map.get(key)
            if mapped_account_id is None or mapped_account_id not in canonical_accounts:
                continue
            if self._evidence_matches_canonical_account(
                evidence=evidence,
                canonical_account=canonical_accounts[mapped_account_id],
                allow_mask_conflict=_identity_key_has_mask_evidence(key),
                require_mask=_identity_key_has_mask_evidence(key),
            ):
                matched_ids.add(mapped_account_id)
            else:
                stale_candidate_keys.add(key)
        if (
            evidence.household_account_id
            and evidence.household_account_id in canonical_accounts
            and self._evidence_matches_canonical_account(
                evidence=evidence,
                canonical_account=canonical_accounts[evidence.household_account_id],
            )
        ):
            matched_ids.add(evidence.household_account_id)
        matched = [account_id for account_id in matched_ids if account_id in canonical_accounts]
        merged = 0
        if matched:
            account_id = self._merge_accounts_if_needed(
                conn,
                account_ids=matched,
                canonical_accounts=canonical_accounts,
                identity_map=identity_map,
            )
            merged = max(len(set(matched)) - 1, 0)
            created = 0
        else:
            proposed_id = str(uuid.uuid4())
            primary_identity = candidates[0] if candidates else f"manual::{proposed_id}"
            canonical_label = _canonical_label(
                institution_name=evidence.institution_name,
                account_name=evidence.account_name,
                account_mask=evidence.account_mask,
                account_type=evidence.account_type,
            )
            derived_mask = derive_account_mask(
                _trusted_evidence_account_mask(evidence),
                evidence.account_name,
                self._evidence_fallback_label(evidence),
            )
            now = _now_iso()
            try:
                conn.execute(
                    """
                    INSERT INTO household_accounts (
                        id, primary_identity_key, canonical_label, asset_group, account_type, source_type,
                        institution_name, owner_name, account_mask, metadata, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    """,
                    [
                        proposed_id,
                        primary_identity,
                        canonical_label,
                        evidence.asset_group,
                        evidence.account_type,
                        evidence.source_type,
                        evidence.institution_name,
                        evidence.owner_name,
                        derived_mask,
                        "{}",
                        now,
                        now,
                    ],
                )
                account_id = proposed_id
                created = 1
                canonical_accounts[account_id] = HouseholdCanonicalAccount(
                    id=account_id,
                    primary_identity_key=primary_identity,
                    canonical_label=canonical_label,
                    asset_group=evidence.asset_group,
                    account_type=evidence.account_type,
                    source_type=evidence.source_type,
                    institution_name=evidence.institution_name,
                    owner_name=evidence.owner_name,
                    account_mask=derived_mask,
                    metadata={},
                )
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                row = conn.execute(
                    """
                    SELECT
                        id,
                        primary_identity_key,
                        canonical_label,
                        asset_group,
                        account_type,
                        source_type,
                        institution_name,
                        owner_name,
                        account_mask,
                        metadata
                    FROM household_accounts
                    WHERE primary_identity_key = %s
                    """,
                    [primary_identity],
                ).fetchone()
                if row is None:
                    raise
                account_id = str(row[0])
                created = 0
                canonical_accounts[account_id] = HouseholdCanonicalAccount(
                    id=account_id,
                    primary_identity_key=str(row[1]) if row[1] is not None else None,
                    canonical_label=str(row[2]) if row[2] is not None else None,
                    asset_group=str(row[3]),
                    account_type=str(row[4]),
                    source_type=str(row[5]),
                    institution_name=str(row[6]) if row[6] is not None else None,
                    owner_name=str(row[7]) if row[7] is not None else None,
                    account_mask=str(row[8]) if row[8] is not None else None,
                    metadata=_load_json_object(row[9]),
                )
        self._refresh_account_from_evidence(
            conn, account_id=account_id, evidence=evidence, canonical_accounts=canonical_accounts
        )
        self._upsert_identity_candidates(
            conn,
            account_id=account_id,
            candidate_keys=candidates,
            source_document_id=evidence.document_id,
            confidence=evidence.confidence,
            identity_map=identity_map,
            canonical_accounts=canonical_accounts,
            force_reassign_keys=stale_candidate_keys,
        )
        return account_id, created, merged

    def _resolve_from_tracked(
        self,
        conn: Any,
        *,
        tracked: HouseholdTrackedAccount,
        canonical_accounts: dict[str, HouseholdCanonicalAccount],
        identity_map: dict[str, str],
    ) -> tuple[str, int]:
        linked_account_id = (
            tracked.household_account_id
            if tracked.household_account_id in canonical_accounts
            else None
        )
        tracked_mask = derive_account_mask(tracked.account_mask, tracked.label)
        base_candidates = _mask_identity_candidates(
            account_identity_candidates(
                source_type=tracked.source_type,
                asset_group=tracked.asset_group,
                account_type=tracked.account_type,
                institution_name=tracked.institution_name,
                account_name=tracked.label,
                owner_name=tracked.owner_name,
                account_mask=tracked.account_mask,
                fallback_label=tracked.label,
                explicit_match_key=None,
            )
        )
        base_matches = {
            identity_map[key]
            for key in base_candidates
            if key in identity_map
            and identity_map[key] in canonical_accounts
            and not account_masks_conflict(
                tracked_mask, canonical_accounts[identity_map[key]].account_mask
            )
        }
        matched_ids: set[str] = set()
        if (
            linked_account_id is not None
            and tracked_mask
            and not account_masks_conflict(
                tracked_mask, canonical_accounts[linked_account_id].account_mask
            )
        ):
            matched_ids.add(linked_account_id)
        if base_matches:
            matched_ids.update(base_matches)
        else:
            fuzzy = self._fuzzy_match_account(
                canonical_accounts=canonical_accounts,
                asset_group=None,
                source_type=None,
                institution_name=tracked.institution_name,
                owner_name=tracked.owner_name,
                account_mask=tracked_mask,
                labels=[tracked.label],
            )
            if fuzzy is not None:
                matched_ids.add(fuzzy)
        if not base_matches and tracked.match_key and linked_account_id is not None:
            explicit_candidates = _mask_identity_candidates(
                account_identity_candidates(
                    source_type=tracked.source_type,
                    asset_group=tracked.asset_group,
                    account_type=tracked.account_type,
                    institution_name=tracked.institution_name,
                    account_name=tracked.label,
                    owner_name=tracked.owner_name,
                    account_mask=tracked.account_mask,
                    fallback_label=tracked.label,
                    explicit_match_key=tracked.match_key,
                )
            )
            matched_ids = {
                identity_map[key]
                for key in explicit_candidates
                if key in identity_map
                and identity_map[key] in canonical_accounts
                and not account_masks_conflict(
                    tracked_mask, canonical_accounts[identity_map[key]].account_mask
                )
            }
            if (
                linked_account_id is not None
                and tracked_mask
                and not account_masks_conflict(
                    tracked_mask, canonical_accounts[linked_account_id].account_mask
                )
            ):
                matched_ids.add(linked_account_id)
        candidates = _mask_identity_candidates(
            account_identity_candidates(
                source_type=tracked.source_type,
                asset_group=tracked.asset_group,
                account_type=tracked.account_type,
                institution_name=tracked.institution_name,
                account_name=tracked.label,
                owner_name=tracked.owner_name,
                account_mask=tracked.account_mask,
                fallback_label=tracked.label,
                explicit_match_key=tracked.match_key,
            )
        )
        matched = [account_id for account_id in matched_ids if account_id in canonical_accounts]
        if matched:
            account_id = (
                self._merge_accounts_if_needed(
                    conn,
                    account_ids=matched,
                    canonical_accounts=canonical_accounts,
                    identity_map=identity_map,
                )
                if len(set(matched)) > 1
                else matched[0]
            )
            self._upsert_identity_candidates(
                conn,
                account_id=account_id,
                candidate_keys=candidates,
                source_document_id=None,
                confidence=None,
                identity_map=identity_map,
                canonical_accounts=canonical_accounts,
            )
            return account_id, 0
        account_id = str(uuid.uuid4())
        primary_identity = candidates[0] if candidates else f"manual::{tracked.id}"
        canonical_accounts[account_id] = HouseholdCanonicalAccount(
            id=account_id,
            primary_identity_key=primary_identity,
            canonical_label=tracked.label,
            asset_group=tracked.asset_group,
            account_type=tracked.account_type,
            source_type=tracked.source_type,
            institution_name=tracked.institution_name,
            owner_name=tracked.owner_name,
            account_mask=derive_account_mask(tracked.account_mask, tracked.label),
            metadata={},
        )
        conn.execute(
            """
            INSERT INTO household_accounts (
                id, primary_identity_key, canonical_label, asset_group, account_type, source_type,
                institution_name, owner_name, account_mask, metadata, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            [
                account_id,
                primary_identity,
                tracked.label,
                tracked.asset_group,
                tracked.account_type,
                tracked.source_type,
                tracked.institution_name,
                tracked.owner_name,
                derive_account_mask(tracked.account_mask, tracked.label),
                "{}",
                _now_iso(),
                _now_iso(),
            ],
        )
        self._upsert_identity_candidates(
            conn,
            account_id=account_id,
            candidate_keys=candidates,
            source_document_id=None,
            confidence=None,
            identity_map=identity_map,
            canonical_accounts=canonical_accounts,
        )
        return account_id, 1

    def _refresh_account_from_evidence(
        self,
        conn: Any,
        *,
        account_id: str,
        evidence: HouseholdEvidenceAccount,
        canonical_accounts: dict[str, HouseholdCanonicalAccount],
    ) -> None:
        current = canonical_accounts[account_id]
        next_mask = derive_account_mask(
            _trusted_evidence_account_mask(evidence),
            evidence.account_name,
            self._evidence_fallback_label(evidence),
        )
        next_label = _canonical_label(
            institution_name=evidence.institution_name,
            account_name=evidence.account_name,
            account_mask=evidence.account_mask,
            account_type=evidence.account_type,
        )
        updated = HouseholdCanonicalAccount(
            id=current.id,
            primary_identity_key=current.primary_identity_key,
            canonical_label=next_label or current.canonical_label,
            asset_group=evidence.asset_group or current.asset_group,
            account_type=evidence.account_type or current.account_type,
            source_type=evidence.source_type or current.source_type,
            institution_name=evidence.institution_name or current.institution_name,
            owner_name=evidence.owner_name or current.owner_name,
            account_mask=next_mask or current.account_mask,
            metadata=current.metadata,
        )
        canonical_accounts[account_id] = updated
        conn.execute(
            """
            UPDATE household_accounts
            SET canonical_label = %s,
                asset_group = %s,
                account_type = %s,
                source_type = %s,
                institution_name = %s,
                owner_name = %s,
                account_mask = %s,
                updated_at = %s
            WHERE id = %s
            """,
            [
                updated.canonical_label,
                updated.asset_group,
                updated.account_type,
                updated.source_type,
                updated.institution_name,
                updated.owner_name,
                updated.account_mask,
                _now_iso(),
                account_id,
            ],
        )

    def _refresh_accounts_from_linked_evidence(
        self,
        conn: Any,
        *,
        canonical_accounts: dict[str, HouseholdCanonicalAccount],
    ) -> None:
        account_ids = list(canonical_accounts)
        if not account_ids:
            return
        rows = conn.execute(
            """
            SELECT
                ea.household_account_id,
                ea.source_type,
                ea.asset_group,
                ea.account_type,
                ea.institution_name,
                ea.account_name,
                ea.account_mask,
                ea.owner_name,
                ea.balance,
                ea.holdings_value,
                ea.cash_balance,
                ea.as_of_date,
                ea.confidence,
                ea.created_at,
                ea.updated_at,
                d.filename,
                d.statement_end,
                d.uploaded_at,
                COALESCE(ea.metadata, '{}'::jsonb) AS metadata
            FROM household_evidence_accounts ea
            LEFT JOIN household_documents d ON d.id = ea.document_id
            WHERE ea.household_account_id = ANY(%s)
            ORDER BY ea.household_account_id, COALESCE(ea.as_of_date, d.uploaded_at, ea.updated_at, ea.created_at) DESC, ea.updated_at DESC, ea.created_at DESC
            """,
            [account_ids],
        ).fetchall()
        grouped: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            account_id = str(row[0]) if row[0] is not None else None
            if not account_id or account_id not in canonical_accounts:
                continue
            evidence_row = {
                "household_account_id": account_id,
                "source_type": str(row[1]) if row[1] is not None else None,
                "asset_group": str(row[2]) if row[2] is not None else None,
                "account_type": str(row[3]) if row[3] is not None else None,
                "institution_name": str(row[4]) if row[4] is not None else None,
                "account_name": str(row[5]) if row[5] is not None else None,
                "account_mask": str(row[6]) if row[6] is not None else None,
                "owner_name": str(row[7]) if row[7] is not None else None,
                "balance": row[8],
                "holdings_value": row[9],
                "cash_balance": row[10],
                "as_of_date": iso_or_none(row[11]),
                "confidence": float(row[12]) if row[12] is not None else None,
                "created_at": iso_or_none(row[13]),
                "updated_at": iso_or_none(row[14]),
                "document_statement_end": iso_or_none(row[16]),
                "document_uploaded_at": iso_or_none(row[17]),
                "metadata": _load_json_object(row[18])
                | {"document_filename": str(row[15]) if row[15] is not None else None},
            }
            grouped.setdefault(account_id, []).append(evidence_row)

        for account_id, evidence_rows in grouped.items():
            current = canonical_accounts[account_id]
            institution_name = next(
                (
                    clean_text(row.get("institution_name"))
                    for row in evidence_rows
                    if clean_text(row.get("institution_name"))
                ),
                current.institution_name,
            )
            owner_name = next(
                (
                    clean_text(row.get("owner_name"))
                    for row in evidence_rows
                    if clean_text(row.get("owner_name"))
                ),
                current.owner_name,
            )
            best_mask = max(evidence_rows, key=_evidence_mask_rank)
            best_mask_rank = _evidence_mask_rank(best_mask)
            next_mask = best_mask_rank[2] if best_mask_rank[0] >= 0 else None
            best_name = max(evidence_rows, key=_evidence_name_rank)
            next_name = (
                clean_text(best_name.get("account_name"))
                if _evidence_name_rank(best_name)[0] >= 0
                else None
            )
            next_label = _canonical_label(
                institution_name=institution_name or current.institution_name,
                account_name=next_name or current.canonical_label,
                account_mask=next_mask or current.account_mask,
                account_type=next(
                    (
                        clean_text(row.get("account_type"))
                        for row in evidence_rows
                        if clean_text(row.get("account_type"))
                    ),
                    current.account_type,
                ),
            )
            updated = HouseholdCanonicalAccount(
                id=current.id,
                primary_identity_key=current.primary_identity_key,
                canonical_label=next_label or current.canonical_label,
                asset_group=next(
                    (
                        clean_text(row.get("asset_group"))
                        for row in evidence_rows
                        if clean_text(row.get("asset_group"))
                    ),
                    current.asset_group,
                )
                or current.asset_group,
                account_type=next(
                    (
                        clean_text(row.get("account_type"))
                        for row in evidence_rows
                        if clean_text(row.get("account_type"))
                    ),
                    current.account_type,
                )
                or current.account_type,
                source_type=next(
                    (
                        clean_text(row.get("source_type"))
                        for row in evidence_rows
                        if clean_text(row.get("source_type"))
                    ),
                    current.source_type,
                )
                or current.source_type,
                institution_name=institution_name or current.institution_name,
                owner_name=owner_name or current.owner_name,
                account_mask=next_mask or current.account_mask,
                metadata=current.metadata,
            )
            canonical_accounts[account_id] = updated
            conn.execute(
                """
                UPDATE household_accounts
                SET canonical_label = %s,
                    asset_group = %s,
                    account_type = %s,
                    source_type = %s,
                    institution_name = %s,
                    owner_name = %s,
                    account_mask = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [
                    updated.canonical_label,
                    updated.asset_group,
                    updated.account_type,
                    updated.source_type,
                    updated.institution_name,
                    updated.owner_name,
                    updated.account_mask,
                    _now_iso(),
                    account_id,
                ],
            )

    def _upsert_identity_candidates(
        self,
        conn: Any,
        *,
        account_id: str,
        candidate_keys: list[str],
        source_document_id: str | None,
        confidence: float | None,
        identity_map: dict[str, str],
        canonical_accounts: dict[str, HouseholdCanonicalAccount],
        force_reassign_keys: set[str] | None = None,
    ) -> None:
        force_reassign_keys = force_reassign_keys or set()
        current = canonical_accounts[account_id]
        if current.primary_identity_key is None and candidate_keys:
            canonical_accounts[account_id] = HouseholdCanonicalAccount(
                id=current.id,
                primary_identity_key=candidate_keys[0],
                canonical_label=current.canonical_label,
                asset_group=current.asset_group,
                account_type=current.account_type,
                source_type=current.source_type,
                institution_name=current.institution_name,
                owner_name=current.owner_name,
                account_mask=current.account_mask,
                metadata=current.metadata,
            )
            conn.execute(
                """
                UPDATE household_accounts
                SET primary_identity_key = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [candidate_keys[0], _now_iso(), account_id],
            )
        for index, key in enumerate(candidate_keys):
            existing_account_id = identity_map.get(key)
            if existing_account_id == account_id:
                conn.execute(
                    """
                    UPDATE household_account_identities
                    SET is_primary = %s,
                        source_document_id = COALESCE(%s, source_document_id),
                        confidence = COALESCE(%s, confidence),
                        updated_at = %s
                    WHERE identity_key = %s
                    """,
                    [index == 0, source_document_id, confidence, _now_iso(), key],
                )
                continue
            if (
                existing_account_id is not None
                and existing_account_id != account_id
                and key not in force_reassign_keys
            ):
                continue
            conn.execute(
                """
                INSERT INTO household_account_identities (
                    id, household_account_id, identity_key, identity_kind, is_primary,
                    source_document_id, confidence, metadata, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (identity_key) DO UPDATE SET
                    household_account_id = EXCLUDED.household_account_id,
                    is_primary = EXCLUDED.is_primary,
                    source_document_id = COALESCE(EXCLUDED.source_document_id, household_account_identities.source_document_id),
                    confidence = COALESCE(EXCLUDED.confidence, household_account_identities.confidence),
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    str(uuid.uuid4()),
                    account_id,
                    key,
                    "composite",
                    index == 0,
                    source_document_id,
                    confidence,
                    "{}",
                    _now_iso(),
                    _now_iso(),
                ],
            )
            identity_map[key] = account_id

    def _tracked_row_rank(
        self,
        tracked: HouseholdTrackedAccount,
        *,
        canonical_account: HouseholdCanonicalAccount,
    ) -> tuple[int, int, str, str]:
        custom_label = int(
            bool(tracked.label)
            and bool(canonical_account.canonical_label)
            and clean_text(tracked.label) != clean_text(canonical_account.canonical_label)
        )
        note_rank = int(bool(clean_text(tracked.notes)))
        updated_at = tracked.updated_at or tracked.created_at or ""
        return (custom_label, note_rank, updated_at, tracked.id)

    def _link_tracked_account(
        self,
        conn: Any,
        *,
        tracked: HouseholdTrackedAccount,
        account_id: str,
        canonical_account: HouseholdCanonicalAccount,
    ) -> tuple[int, bool]:
        existing_row = conn.execute(
            """
            SELECT id, household_account_id, label, asset_group, account_type, source_type,
                   match_key, institution_name, owner_name, account_mask, notes, created_at, updated_at
            FROM household_tracked_accounts
            WHERE household_account_id = %s
              AND id <> %s
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """,
            [account_id, tracked.id],
        ).fetchone()
        if existing_row is None:
            conn.execute(
                """
                UPDATE household_tracked_accounts
                SET household_account_id = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [account_id, _now_iso(), tracked.id],
            )
            tracked.household_account_id = account_id
            return 1, False

        existing = row_to_tracked_account(existing_row, iso=iso)
        keep_current = self._tracked_row_rank(
            tracked, canonical_account=canonical_account
        ) > self._tracked_row_rank(existing, canonical_account=canonical_account)
        keeper = tracked if keep_current else existing
        loser = existing if keep_current else tracked

        if not keeper.notes and loser.notes:
            conn.execute(
                """
                UPDATE household_tracked_accounts
                SET notes = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [loser.notes, _now_iso(), keeper.id],
            )
            keeper.notes = loser.notes

        if keep_current:
            conn.execute("DELETE FROM household_tracked_accounts WHERE id = %s", [existing.id])
            conn.execute(
                """
                UPDATE household_tracked_accounts
                SET household_account_id = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [account_id, _now_iso(), tracked.id],
            )
            tracked.household_account_id = account_id
            return 1, False

        conn.execute("DELETE FROM household_tracked_accounts WHERE id = %s", [tracked.id])
        return 0, True

    def _merge_accounts_if_needed(
        self,
        conn: Any,
        *,
        account_ids: list[str],
        canonical_accounts: dict[str, HouseholdCanonicalAccount],
        identity_map: dict[str, str],
    ) -> str:
        unique_ids = [
            account_id
            for account_id in dict.fromkeys(account_ids)
            if account_id in canonical_accounts
        ]
        if len(unique_ids) <= 1:
            return unique_ids[0]
        counts = self._account_link_counts(conn, account_ids=unique_ids)
        winner_id = max(
            unique_ids,
            key=lambda account_id: (
                counts.get(account_id, 0),
                canonical_accounts[account_id].primary_identity_key is not None,
                account_id,
            ),
        )
        losers = [account_id for account_id in unique_ids if account_id != winner_id]
        for loser_id in losers:
            self._merge_account(
                conn,
                winner_id=winner_id,
                loser_id=loser_id,
                identity_map=identity_map,
                canonical_accounts=canonical_accounts,
            )
        return winner_id

    def _account_link_counts(self, conn: Any, *, account_ids: list[str]) -> dict[str, int]:
        if not account_ids:
            return {}
        rows = conn.execute(
            """
            SELECT household_account_id, COUNT(*)
            FROM (
                SELECT household_account_id FROM household_evidence_accounts WHERE household_account_id = ANY(%s)
                UNION ALL
                SELECT household_account_id FROM household_transactions WHERE household_account_id = ANY(%s)
                UNION ALL
                SELECT household_account_id FROM household_tracked_accounts WHERE household_account_id = ANY(%s)
                UNION ALL
                SELECT household_account_id FROM portfolio_accounts WHERE household_account_id = ANY(%s)
            ) linked
            GROUP BY household_account_id
            """,
            [account_ids, account_ids, account_ids, account_ids],
        ).fetchall()
        return {str(row[0]): int(row[1]) for row in rows if row[0] is not None}

    def _account_metrics(self, conn: Any, *, account_ids: list[str]) -> dict[str, dict[str, int]]:
        metrics = {
            account_id: {"evidence": 0, "tracked": 0, "transactions": 0, "portfolio": 0}
            for account_id in account_ids
        }
        if not account_ids:
            return metrics
        queries = {
            "evidence": "SELECT household_account_id, COUNT(*) FROM household_evidence_accounts WHERE household_account_id = ANY(%s) GROUP BY household_account_id",
            "tracked": "SELECT household_account_id, COUNT(*) FROM household_tracked_accounts WHERE household_account_id = ANY(%s) GROUP BY household_account_id",
            "transactions": "SELECT household_account_id, COUNT(*) FROM household_transactions WHERE household_account_id = ANY(%s) GROUP BY household_account_id",
            "portfolio": "SELECT household_account_id, COUNT(*) FROM portfolio_accounts WHERE household_account_id = ANY(%s) GROUP BY household_account_id",
        }
        for key, sql in queries.items():
            for row in conn.execute(sql, [account_ids]).fetchall():
                if row[0] is None:
                    continue
                metrics[str(row[0])][key] = int(row[1])
        return metrics

    def _merge_account(
        self,
        conn: Any,
        *,
        winner_id: str,
        loser_id: str,
        identity_map: dict[str, str],
        canonical_accounts: dict[str, HouseholdCanonicalAccount],
    ) -> None:
        tracked_rows = conn.execute(
            """
            SELECT id, household_account_id, label, asset_group, account_type, source_type,
                   match_key, institution_name, owner_name, account_mask, notes, created_at, updated_at
            FROM household_tracked_accounts
            WHERE household_account_id = ANY(%s)
            ORDER BY updated_at DESC, created_at DESC
            """,
            [[winner_id, loser_id]],
        ).fetchall()
        tracked_accounts = [row_to_tracked_account(row, iso=iso) for row in tracked_rows]
        winner_rows = [
            tracked for tracked in tracked_accounts if tracked.household_account_id == winner_id
        ]
        loser_rows = [
            tracked for tracked in tracked_accounts if tracked.household_account_id == loser_id
        ]
        keeper = winner_rows[0] if winner_rows else (loser_rows[0] if loser_rows else None)
        if keeper is not None and winner_rows and not keeper.notes:
            note_candidates = [tracked.notes for tracked in loser_rows if tracked.notes]
            if note_candidates:
                conn.execute(
                    """
                    UPDATE household_tracked_accounts
                    SET notes = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    [note_candidates[0], _now_iso(), keeper.id],
                )
        for tracked in tracked_accounts:
            if keeper is None:
                break
            if tracked.id == keeper.id:
                if tracked.household_account_id != winner_id:
                    conn.execute(
                        """
                        UPDATE household_tracked_accounts
                        SET household_account_id = %s,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        [winner_id, _now_iso(), tracked.id],
                    )
                continue
            conn.execute("DELETE FROM household_tracked_accounts WHERE id = %s", [tracked.id])

        conn.execute(
            """
            INSERT INTO household_account_preferences (
                household_account_id, display_label, display_owner_name, notes,
                hidden_at, metadata, created_at, updated_at
            )
            SELECT
                %s,
                display_label,
                display_owner_name,
                notes,
                hidden_at,
                metadata,
                created_at,
                updated_at
            FROM household_account_preferences
            WHERE household_account_id = %s
            ON CONFLICT (household_account_id) DO UPDATE
            SET display_label = COALESCE(household_account_preferences.display_label, EXCLUDED.display_label),
                display_owner_name = COALESCE(household_account_preferences.display_owner_name, EXCLUDED.display_owner_name),
                notes = COALESCE(household_account_preferences.notes, EXCLUDED.notes),
                updated_at = GREATEST(household_account_preferences.updated_at, EXCLUDED.updated_at)
            """,
            [winner_id, loser_id],
        )
        conn.execute(
            "DELETE FROM household_account_preferences WHERE household_account_id = %s",
            [loser_id],
        )
        conn.execute(
            "UPDATE household_evidence_accounts SET household_account_id = %s WHERE household_account_id = %s",
            [winner_id, loser_id],
        )
        conn.execute(
            "UPDATE household_transactions SET household_account_id = %s WHERE household_account_id = %s",
            [winner_id, loser_id],
        )
        conn.execute(
            "UPDATE portfolio_accounts SET household_account_id = %s WHERE household_account_id = %s",
            [winner_id, loser_id],
        )
        conn.execute(
            "UPDATE plaid_accounts SET household_account_id = %s WHERE household_account_id = %s",
            [winner_id, loser_id],
        )
        conn.execute(
            "UPDATE snaptrade_accounts SET household_account_id = %s WHERE household_account_id = %s",
            [winner_id, loser_id],
        )
        conn.execute(
            """
            UPDATE household_account_identities
            SET household_account_id = %s,
                updated_at = %s
            WHERE household_account_id = %s
              AND identity_key NOT IN (
                  SELECT identity_key FROM household_account_identities WHERE household_account_id = %s
              )
            """,
            [winner_id, _now_iso(), loser_id, winner_id],
        )
        duplicate_identity_rows = conn.execute(
            """
            SELECT identity_key
            FROM household_account_identities
            WHERE household_account_id = %s
            INTERSECT
            SELECT identity_key
            FROM household_account_identities
            WHERE household_account_id = %s
            """,
            [winner_id, loser_id],
        ).fetchall()
        for row in duplicate_identity_rows:
            identity_map[str(row[0])] = winner_id
        conn.execute(
            "DELETE FROM household_account_identities WHERE household_account_id = %s", [loser_id]
        )
        conn.execute("DELETE FROM household_accounts WHERE id = %s", [loser_id])
        for key, account_id in list(identity_map.items()):
            if account_id == loser_id:
                identity_map[key] = winner_id
        canonical_accounts.pop(loser_id, None)

    def _merge_shadow_accounts(
        self,
        conn: Any,
        *,
        canonical_accounts: dict[str, HouseholdCanonicalAccount],
        identity_map: dict[str, str],
    ) -> int:
        account_ids = list(canonical_accounts)
        metrics = self._account_metrics(conn, account_ids=account_ids)
        merged = 0
        for left_index, left_id in enumerate(account_ids):
            if left_id not in canonical_accounts:
                continue
            for right_id in account_ids[left_index + 1 :]:
                if left_id not in canonical_accounts:
                    break
                if right_id not in canonical_accounts:
                    continue
                left = canonical_accounts[left_id]
                right = canonical_accounts[right_id]
                if not self._should_merge_accounts(left, right, metrics=metrics):
                    continue
                winner_id, loser_id = self._choose_merge_winner(
                    left_id,
                    right_id,
                    metrics=metrics,
                    canonical_accounts=canonical_accounts,
                )
                self._merge_account(
                    conn,
                    winner_id=winner_id,
                    loser_id=loser_id,
                    identity_map=identity_map,
                    canonical_accounts=canonical_accounts,
                )
                merged += 1
                metrics = self._account_metrics(conn, account_ids=list(canonical_accounts))
        return merged

    def _choose_merge_winner(
        self,
        left_id: str,
        right_id: str,
        *,
        metrics: dict[str, dict[str, int]],
        canonical_accounts: dict[str, HouseholdCanonicalAccount],
    ) -> tuple[str, str]:
        left = metrics.get(left_id, {})
        right = metrics.get(right_id, {})
        left_score = (
            left.get("evidence", 0) * 100
            + left.get("transactions", 0) * 10
            + left.get("portfolio", 0) * 10
            + left.get("tracked", 0)
            + _canonical_identity_strength(canonical_accounts[left_id]) * 25
        )
        right_score = (
            right.get("evidence", 0) * 100
            + right.get("transactions", 0) * 10
            + right.get("portfolio", 0) * 10
            + right.get("tracked", 0)
            + _canonical_identity_strength(canonical_accounts[right_id]) * 25
        )
        if right_score > left_score:
            return right_id, left_id
        return left_id, right_id

    def _should_merge_accounts(
        self,
        left: HouseholdCanonicalAccount,
        right: HouseholdCanonicalAccount,
        *,
        metrics: dict[str, dict[str, int]],
    ) -> bool:
        return account_masks_match(left.account_mask, right.account_mask)

    def _sync_tracked_identity_snapshot(
        self,
        conn: Any,
        *,
        tracked: HouseholdTrackedAccount,
        canonical_account: HouseholdCanonicalAccount,
    ) -> int:
        next_asset_group = canonical_account.asset_group
        next_account_type = canonical_account.account_type
        next_source_type = canonical_account.source_type
        next_institution_name = canonical_account.institution_name
        next_owner_name = tracked.owner_name or canonical_account.owner_name
        next_account_mask = canonical_account.account_mask
        next_match_key = canonical_account.primary_identity_key or tracked.match_key
        if (
            tracked.asset_group == next_asset_group
            and tracked.account_type == next_account_type
            and tracked.source_type == next_source_type
            and tracked.institution_name == next_institution_name
            and tracked.owner_name == next_owner_name
            and tracked.account_mask == next_account_mask
            and tracked.match_key == next_match_key
        ):
            return 0
        result = conn.execute(
            """
            UPDATE household_tracked_accounts
            SET match_key = %s,
                asset_group = %s,
                account_type = %s,
                source_type = %s,
                institution_name = %s,
                owner_name = %s,
                account_mask = %s,
                updated_at = %s
            WHERE id = %s
            """,
            [
                next_match_key,
                next_asset_group,
                next_account_type,
                next_source_type,
                next_institution_name,
                next_owner_name,
                next_account_mask,
                _now_iso(),
                tracked.id,
            ],
        )
        return int(getattr(result, "rowcount", 0) or 0)

    def _sync_transactions(self, conn: Any, *, identity_map: dict[str, str]) -> int:
        rows = conn.execute(
            """
            SELECT
                t.id,
                t.document_id,
                t.account_label,
                d.account_label,
                array_remove(array_agg(DISTINCT e.household_account_id), NULL)
            FROM household_transactions t
            LEFT JOIN household_documents d ON d.id = t.document_id
            LEFT JOIN household_evidence_accounts e ON e.document_id = t.document_id
            WHERE t.household_account_id IS NULL
            GROUP BY t.id, d.account_label
            """
        ).fetchall()
        updated = 0
        for row in rows:
            transaction_id = str(row[0])
            transaction_label = clean_text(row[2]) or clean_text(row[3])
            account_ids = list(row[4] or [])
            next_account_id: str | None = None
            if len(account_ids) == 1:
                next_account_id = str(account_ids[0])
            elif transaction_label:
                candidates = account_identity_candidates(
                    source_type=None,
                    asset_group=None,
                    account_type=None,
                    institution_name=None,
                    account_name=transaction_label,
                    owner_name=None,
                    account_mask=transaction_label,
                    fallback_label=transaction_label,
                    explicit_match_key=None,
                )
                matched = {
                    identity_map[key]
                    for key in _mask_identity_candidates(candidates)
                    if key in identity_map
                }
                if len(matched) == 1:
                    next_account_id = next(iter(matched))
            if not next_account_id:
                continue
            conn.execute(
                """
                UPDATE household_transactions
                SET household_account_id = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [next_account_id, _now_iso(), transaction_id],
            )
            updated += 1
        return updated

    def _sync_portfolio_accounts(
        self,
        conn: Any,
        *,
        canonical_accounts: dict[str, HouseholdCanonicalAccount],
        tracked_accounts: list[HouseholdTrackedAccount],
        portfolio_accounts: list[Account],
    ) -> int:
        linked_portfolio_by_household_account_id = {
            portfolio_account.household_account_id: portfolio_account.id
            for portfolio_account in portfolio_accounts
            if portfolio_account.household_account_id
            and portfolio_account.household_account_id in canonical_accounts
        }
        tracked_by_label: dict[tuple[str, str], str] = {}
        for tracked in tracked_accounts:
            if not tracked.household_account_id:
                continue
            key = (
                clean_text(tracked.label) or "",
                clean_text(tracked.asset_group) or "",
            )
            if key[0] and key[1] and key not in tracked_by_label:
                tracked_by_label[key] = tracked.household_account_id

        canonical_by_label: dict[tuple[str, str], str] = {}
        for account_id, canonical in canonical_accounts.items():
            key = (
                clean_text(canonical.canonical_label) or "",
                clean_text(canonical.asset_group) or "",
            )
            if key[0] and key[1] and key not in canonical_by_label:
                canonical_by_label[key] = account_id

        updated = 0
        for portfolio_account in portfolio_accounts:
            asset_group = _PORTFOLIO_ACCOUNT_GROUPS.get(portfolio_account.account_type)
            if not asset_group:
                continue
            if (
                portfolio_account.household_account_id
                and portfolio_account.household_account_id in canonical_accounts
            ):
                continue
            key = (clean_text(portfolio_account.name) or "", asset_group)
            next_account_id = tracked_by_label.get(key) or canonical_by_label.get(key)
            if not next_account_id:
                continue
            existing_portfolio_id = linked_portfolio_by_household_account_id.get(next_account_id)
            if existing_portfolio_id and existing_portfolio_id != portfolio_account.id:
                continue
            conn.execute(
                """
                UPDATE portfolio_accounts
                SET household_account_id = %s
                WHERE id = %s
                """,
                [next_account_id, portfolio_account.id],
            )
            linked_portfolio_by_household_account_id[next_account_id] = portfolio_account.id
            updated += 1
        return updated

    def _prune_orphan_accounts(
        self,
        conn: Any,
        *,
        canonical_accounts: dict[str, HouseholdCanonicalAccount],
        identity_map: dict[str, str],
    ) -> int:
        rows = conn.execute(
            """
            SELECT a.id
            FROM household_accounts a
            LEFT JOIN household_evidence_accounts ea ON ea.household_account_id = a.id
            LEFT JOIN household_account_preferences ap ON ap.household_account_id = a.id
            LEFT JOIN household_transactions tx ON tx.household_account_id = a.id
            LEFT JOIN portfolio_accounts pa ON pa.household_account_id = a.id
            GROUP BY a.id
            HAVING COUNT(ea.id) = 0 AND COUNT(ap.id) = 0 AND COUNT(tx.id) = 0 AND COUNT(pa.id) = 0
            """
        ).fetchall()
        orphan_ids = [str(row[0]) for row in rows if row[0] is not None]
        for account_id in orphan_ids:
            conn.execute(
                "DELETE FROM household_account_identities WHERE household_account_id = %s",
                [account_id],
            )
            conn.execute("DELETE FROM household_accounts WHERE id = %s", [account_id])
            canonical_accounts.pop(account_id, None)
        if orphan_ids:
            for key, mapped_id in list(identity_map.items()):
                if mapped_id in orphan_ids:
                    identity_map.pop(key, None)
        return len(orphan_ids)

    def _fuzzy_match_account(
        self,
        *,
        canonical_accounts: dict[str, HouseholdCanonicalAccount],
        asset_group: str | None,
        source_type: str | None,
        institution_name: str | None,
        owner_name: str | None,
        account_mask: str | None,
        labels: list[str | None],
    ) -> str | None:
        normalized_asset = clean_text(asset_group)
        normalized_source = clean_text(source_type)
        normalized_institution = clean_text(institution_name)
        normalized_mask = normalize_account_mask(account_mask)
        if not normalized_mask:
            return None
        input_tokens = _name_tokens(*labels, institution_name)

        scored: list[tuple[int, str]] = []
        for account_id, account in canonical_accounts.items():
            score = 0
            if normalized_mask:
                if not account_masks_match(account.account_mask, normalized_mask):
                    continue
                score += 100
            if normalized_asset and clean_text(account.asset_group) == normalized_asset:
                score += 8
            if normalized_source and clean_text(account.source_type) == normalized_source:
                score += 3
            if (
                normalized_institution
                and account.institution_name
                and clean_text(account.institution_name) == normalized_institution
            ):
                score += 20
            if owner_name and _owner_matches(owner_name, account.owner_name):
                score += 15
            shared_tokens = input_tokens & _name_tokens(
                account.canonical_label, account.institution_name
            )
            score += len(shared_tokens) * 5
            if score >= 20:
                scored.append((score, account_id))
        if not scored:
            return None
        scored.sort(reverse=True)
        if len(scored) == 1:
            return scored[0][1]
        top_score, top_id = scored[0]
        next_score = scored[1][0]
        return top_id if top_score >= 20 and top_score > next_score else None
