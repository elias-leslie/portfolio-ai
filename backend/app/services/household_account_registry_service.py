"""Canonical household-account registry and self-healing linkage."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdEvidenceAccount, HouseholdTrackedAccount
from app.portfolio.models import Account
from app.services._household_finance_utils import iso, iso_or_none, to_float
from app.services.household_account_identity import (
    account_identity_candidates,
    clean_text,
    derive_account_mask,
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
        return {
            str(key): nested
            for key, nested in value.items()
        }
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


class HouseholdAccountRegistryService:
    """Own canonical household-account identities across evidence, settings, and ledger."""

    @staticmethod
    def _evidence_fallback_label(evidence: HouseholdEvidenceAccount) -> str | None:
        if not isinstance(evidence.metadata, dict):
            return None
        raw = evidence.metadata.get("document_filename") or evidence.metadata.get("document_account_label")
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None

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

            accounts_merged += self._merge_shadow_accounts(
                conn,
                canonical_accounts=canonical_accounts,
                identity_map=identity_map,
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
        return [row_to_evidence_account(row, to_float=to_float, iso_or_none=iso_or_none) for row in rows]

    def _fetch_tracked_accounts(self, conn: Any, *, limit: int) -> list[HouseholdTrackedAccount]:
        rows = conn.execute(
            f"""
            SELECT {_TRACKED_COLS}
            FROM household_tracked_accounts
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
        candidates = account_identity_candidates(
            source_type=evidence.source_type,
            asset_group=evidence.asset_group,
            account_type=evidence.account_type,
            institution_name=evidence.institution_name,
            account_name=evidence.account_name,
            owner_name=evidence.owner_name,
            account_mask=evidence.account_mask,
            fallback_label=self._evidence_fallback_label(evidence),
            explicit_match_key=str(evidence.metadata.get("match_key")) if isinstance(evidence.metadata, dict) and evidence.metadata.get("match_key") else None,
        )
        matched_ids = {
            identity_map[key]
            for key in candidates
            if key in identity_map
        }
        if evidence.household_account_id:
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
            account_id = str(uuid.uuid4())
            created = 1
            primary_identity = candidates[0] if candidates else f"manual::{account_id}"
            canonical_accounts[account_id] = HouseholdCanonicalAccount(
                id=account_id,
                primary_identity_key=primary_identity,
                canonical_label=_canonical_label(
                    institution_name=evidence.institution_name,
                    account_name=evidence.account_name,
                    account_mask=evidence.account_mask,
                    account_type=evidence.account_type,
                ),
                asset_group=evidence.asset_group,
                account_type=evidence.account_type,
                source_type=evidence.source_type,
                institution_name=evidence.institution_name,
                owner_name=evidence.owner_name,
                account_mask=derive_account_mask(
                    evidence.account_mask,
                    evidence.account_name,
                    self._evidence_fallback_label(evidence),
                ),
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
                    canonical_accounts[account_id].primary_identity_key,
                    canonical_accounts[account_id].canonical_label,
                    evidence.asset_group,
                    evidence.account_type,
                    evidence.source_type,
                    evidence.institution_name,
                    evidence.owner_name,
                    derive_account_mask(
                        evidence.account_mask,
                        evidence.account_name,
                        self._evidence_fallback_label(evidence),
                    ),
                    "{}",
                    _now_iso(),
                    _now_iso(),
                ],
            )
        self._refresh_account_from_evidence(conn, account_id=account_id, evidence=evidence, canonical_accounts=canonical_accounts)
        self._upsert_identity_candidates(
            conn,
            account_id=account_id,
            candidate_keys=candidates,
            source_document_id=evidence.document_id,
            confidence=evidence.confidence,
            identity_map=identity_map,
            canonical_accounts=canonical_accounts,
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
        if tracked.household_account_id and tracked.household_account_id in canonical_accounts:
            return tracked.household_account_id, 0
        fuzzy = self._fuzzy_match_account(
            canonical_accounts=canonical_accounts,
            asset_group=None,
            source_type=None,
            institution_name=tracked.institution_name,
            owner_name=tracked.owner_name,
            account_mask=None,
            labels=[tracked.label],
        )
        if fuzzy is not None:
            candidates = account_identity_candidates(
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
            self._upsert_identity_candidates(
                conn,
                account_id=fuzzy,
                candidate_keys=candidates,
                source_document_id=None,
                confidence=None,
                identity_map=identity_map,
                canonical_accounts=canonical_accounts,
            )
            return fuzzy, 0
        candidates = account_identity_candidates(
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
        matched = [identity_map[key] for key in candidates if key in identity_map and identity_map[key] in canonical_accounts]
        if matched:
            account_id = matched[0]
        else:
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
            evidence.account_mask,
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
    ) -> None:
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
            if existing_account_id is not None and existing_account_id != account_id:
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
        unique_ids = [account_id for account_id in dict.fromkeys(account_ids) if account_id in canonical_accounts]
        if len(unique_ids) <= 1:
            return unique_ids[0]
        counts = self._account_link_counts(conn, account_ids=unique_ids)
        winner_id = max(unique_ids, key=lambda account_id: (counts.get(account_id, 0), canonical_accounts[account_id].primary_identity_key is not None, account_id))
        losers = [account_id for account_id in unique_ids if account_id != winner_id]
        for loser_id in losers:
            self._merge_account(conn, winner_id=winner_id, loser_id=loser_id, identity_map=identity_map, canonical_accounts=canonical_accounts)
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
        winner_rows = [tracked for tracked in tracked_accounts if tracked.household_account_id == winner_id]
        loser_rows = [tracked for tracked in tracked_accounts if tracked.household_account_id == loser_id]
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
        conn.execute("DELETE FROM household_account_identities WHERE household_account_id = %s", [loser_id])
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
            for right_id in account_ids[left_index + 1:]:
                if right_id not in canonical_accounts:
                    continue
                left = canonical_accounts[left_id]
                right = canonical_accounts[right_id]
                if not self._should_merge_accounts(left, right, metrics=metrics):
                    continue
                winner_id, loser_id = self._choose_merge_winner(left_id, right_id, metrics=metrics)
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
    ) -> tuple[str, str]:
        left = metrics.get(left_id, {})
        right = metrics.get(right_id, {})
        left_score = (
            left.get("evidence", 0) * 100
            + left.get("transactions", 0) * 10
            + left.get("portfolio", 0) * 10
            + left.get("tracked", 0)
        )
        right_score = (
            right.get("evidence", 0) * 100
            + right.get("transactions", 0) * 10
            + right.get("portfolio", 0) * 10
            + right.get("tracked", 0)
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
        if left.asset_group != right.asset_group:
            return False
        if left.account_mask and right.account_mask and clean_text(left.account_mask) == clean_text(right.account_mask):
            return True

        left_metrics = metrics.get(left.id, {})
        right_metrics = metrics.get(right.id, {})
        left_evidence = left_metrics.get("evidence", 0)
        right_evidence = right_metrics.get("evidence", 0)
        left_tokens = _name_tokens(left.canonical_label, left.institution_name)
        right_tokens = _name_tokens(right.canonical_label, right.institution_name)
        same_institution = (
            bool(left.institution_name)
            and bool(right.institution_name)
            and clean_text(left.institution_name) == clean_text(right.institution_name)
        )
        owner_compatible = _owner_matches(left.owner_name, right.owner_name) or not left.owner_name or not right.owner_name
        tokens_compatible = bool(left_tokens) and bool(right_tokens) and (left_tokens <= right_tokens or right_tokens <= left_tokens)

        if left_evidence > 0 and right_evidence > 0:
            return False

        evidence_backed = left_evidence > 0 or right_evidence > 0
        if not evidence_backed:
            return False
        return (
            same_institution
            and owner_compatible
            and tokens_compatible
            and (left_evidence == 0 or right_evidence == 0)
        )

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
        next_owner_name = canonical_account.owner_name
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
        conn.execute(
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
        return 1

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
                matched = {identity_map[key] for key in candidates if key in identity_map}
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
            LEFT JOIN household_tracked_accounts ta ON ta.household_account_id = a.id
            LEFT JOIN household_transactions tx ON tx.household_account_id = a.id
            LEFT JOIN portfolio_accounts pa ON pa.household_account_id = a.id
            GROUP BY a.id
            HAVING COUNT(ea.id) = 0 AND COUNT(ta.id) = 0 AND COUNT(tx.id) = 0 AND COUNT(pa.id) = 0
            """
        ).fetchall()
        orphan_ids = [str(row[0]) for row in rows if row[0] is not None]
        for account_id in orphan_ids:
            conn.execute("DELETE FROM household_account_identities WHERE household_account_id = %s", [account_id])
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
        normalized_mask = derive_account_mask(account_mask, None)
        input_tokens = _name_tokens(*labels, institution_name)

        scored: list[tuple[int, str]] = []
        for account_id, account in canonical_accounts.items():
            score = 0
            if normalized_mask and account.account_mask and clean_text(account.account_mask) == normalized_mask:
                score += 60
            if normalized_asset and clean_text(account.asset_group) == normalized_asset:
                score += 8
            if normalized_source and clean_text(account.source_type) == normalized_source:
                score += 3
            if normalized_institution and account.institution_name and clean_text(account.institution_name) == normalized_institution:
                score += 20
            if owner_name and _owner_matches(owner_name, account.owner_name):
                score += 15
            shared_tokens = input_tokens & _name_tokens(account.canonical_label, account.institution_name)
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
