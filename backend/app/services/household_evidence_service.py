"""Evidence-account persistence and normalization for household finance."""

from __future__ import annotations

import json
import re
import uuid
from types import SimpleNamespace
from typing import Any

from app.models.household_finance import HouseholdEvidenceAccount
from app.services._household_document_pipeline_utils import parse_decimal, parse_row_date
from app.services._household_finance_utils import iso_or_none, to_float
from app.services.household_finance_rows import row_to_evidence_account

_EVIDENCE_COLS = (
    "id, document_id, household_account_id, source_type, asset_group, account_type, "
    "institution_name, account_name, account_mask, owner_name, currency, "
    "balance, holdings_value, cash_balance, as_of_date, metadata, confidence"
)
_EVIDENCE_SQL = f"SELECT {_EVIDENCE_COLS} FROM household_evidence_accounts"

_ALLOWED_ASSET_GROUPS = {"cash", "retirement", "taxable", "education", "debt", "credit", "other"}


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal_or_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    parsed = parse_decimal(str(value))
    return float(parsed) if parsed is not None else None


def _statement_period_end_date(value: object) -> str | None:
    text = _string_or_none(value)
    if not text:
        return None
    matches = re.findall(
        r"(?:19|20)\d{2}[-/](?:1[0-2]|0?\d)[-/](?:[12]\d|3[01]|0?\d)",
        text,
    )
    if not matches:
        compact_matches = re.findall(r"(?<!\d)((?:19|20)\d{2}(?:1[0-2]|0[1-9])(?:3[01]|[12]\d|0[1-9]))(?!\d)", text)
        if not compact_matches:
            return None
        compact = compact_matches[-1]
        return parse_row_date(f"{compact[0:4]}-{compact[4:6]}-{compact[6:8]}")
    return parse_row_date(matches[-1])


def _asset_group(value: object, *, source_type: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _ALLOWED_ASSET_GROUPS:
        return normalized
    return {
        "bank": "cash",
        "credit_card": "credit",
        "brokerage": "taxable",
        "retirement": "retirement",
    }.get(source_type, "other")


def _identity_text(value: object) -> str:
    return str(value or "").strip().lower()


def _account_identity(account: HouseholdEvidenceAccount) -> tuple[str, ...]:
    if account.household_account_id:
        return ("household_account_id", _identity_text(account.household_account_id))
    return (
        _identity_text(account.source_type),
        _identity_text(account.asset_group),
        _identity_text(account.account_type),
        _identity_text(account.institution_name),
        _identity_text(account.account_name),
        _identity_text(account.account_mask),
        _identity_text(account.owner_name),
    )


class HouseholdEvidenceService:
    """Persist evidence-derived account snapshots for the money system."""

    def list_accounts(
        self,
        service: Any,
        limit: int = 20,
        *,
        dedupe: bool = True,
    ) -> list[HouseholdEvidenceAccount]:
        fetch_limit = max(limit * 4, limit)
        with service.storage.connection() as conn:
            rows = conn.execute(
                f"{_EVIDENCE_SQL} ORDER BY COALESCE(as_of_date, updated_at) DESC, updated_at DESC LIMIT %s",
                [fetch_limit],
            ).fetchall()
        accounts = [
            row_to_evidence_account(
                row,
                to_float=to_float,
                iso_or_none=iso_or_none,
            )
            for row in rows
        ]
        if dedupe:
            return self._dedupe_accounts(accounts)[:limit]
        return accounts[:limit]

    def replace_document_accounts(
        self,
        service: Any,
        *,
        document: Any,
        reviewed: dict[str, object],
    ) -> int:
        normalized_accounts = self._normalize_accounts(document=document, reviewed=reviewed)
        now = document.parsed_at or reviewed.get("parsed_at")
        now_text = str(now) if isinstance(now, str) and now else None
        if now_text is None:
            from datetime import UTC, datetime  # noqa: PLC0415

            now_text = datetime.now(UTC).isoformat()

        with service.storage.connection() as conn:
            candidate_account_ids = [
                str(account["household_account_id"])
                for account in normalized_accounts
                if account.get("household_account_id")
            ]
            valid_account_ids: set[str] = set()
            if candidate_account_ids:
                valid_rows = conn.execute(
                    "SELECT id FROM household_accounts WHERE id = ANY(%s)",
                    [candidate_account_ids],
                ).fetchall()
                valid_account_ids = {str(row[0]) for row in valid_rows}
            for account in normalized_accounts:
                household_account_id = _string_or_none(account.get("household_account_id"))
                if household_account_id and household_account_id not in valid_account_ids:
                    account["household_account_id"] = None
                    metadata = account.get("metadata")
                    if not isinstance(metadata, dict):
                        metadata = {}
                        account["metadata"] = metadata
                    metadata_dict = dict(metadata)
                    metadata_dict["stale_household_account_id"] = household_account_id
                    account["metadata"] = metadata_dict
            conn.execute("DELETE FROM household_evidence_accounts WHERE document_id = %s", [document.id])
            for account in normalized_accounts:
                conn.execute(
                    """
                    INSERT INTO household_evidence_accounts (
                        id, document_id, household_account_id, source_type, asset_group, account_type,
                        institution_name, account_name, account_mask, owner_name, currency,
                        balance, holdings_value, cash_balance, as_of_date, confidence,
                        metadata, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s::jsonb, %s, %s
                    )
                    """,
                    [
                        str(uuid.uuid4()),
                        document.id,
                        account["household_account_id"],
                        account["source_type"],
                        account["asset_group"],
                        account["account_type"],
                        account["institution_name"],
                        account["account_name"],
                        account["account_mask"],
                        account["owner_name"],
                        account["currency"],
                        account["balance"],
                        account["holdings_value"],
                        account["cash_balance"],
                        account["as_of_date"],
                        account["confidence"],
                        json.dumps(account["metadata"]),
                        now_text,
                        now_text,
                    ],
                )
            conn.commit()
        return len(normalized_accounts)

    def totals_by_group(self, accounts: list[HouseholdEvidenceAccount]) -> dict[str, float]:
        totals = dict.fromkeys(_ALLOWED_ASSET_GROUPS, 0.0)
        for account in self._dedupe_accounts(accounts):
            total = account.balance
            if total is None:
                subtotal = (account.holdings_value or 0.0) + (account.cash_balance or 0.0)
                total = subtotal if subtotal > 0 else None
            if total is None:
                continue
            totals[account.asset_group] = totals.get(account.asset_group, 0.0) + total
        return totals

    def investment_like_count(self, accounts: list[HouseholdEvidenceAccount]) -> int:
        return sum(
            1
            for account in self._dedupe_accounts(accounts)
            if account.asset_group in {"taxable", "retirement", "education"}
            and ((account.balance or 0.0) > 0 or (account.holdings_value or 0.0) > 0)
        )

    def backfill_from_latest_reviews(self, service: Any, *, limit: int = 24) -> int:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    d.id,
                    d.filename,
                    d.source_type,
                    d.document_type,
                    d.account_label,
                    d.parsed_at,
                    r.summary,
                    r.confidence,
                    r.structured_data
                FROM household_documents d
                JOIN LATERAL (
                    SELECT summary, confidence, structured_data
                    FROM household_document_reviews
                    WHERE document_id = d.id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) r ON TRUE
                WHERE d.source_type IN ('brokerage', 'retirement', 'bank', 'credit_card')
                ORDER BY d.uploaded_at DESC
                LIMIT %s
                """,
                [limit],
            ).fetchall()

        inserted = 0
        for row in rows:
            inserted += self.replace_document_accounts(
                service,
                document=SimpleNamespace(
                    id=str(row[0]),
                    filename=str(row[1]),
                    source_type=str(row[2]),
                    document_type=str(row[3]),
                    account_label=str(row[4]) if row[4] is not None else None,
                    parsed_at=iso_or_none(row[5]),
                ),
                reviewed={
                    "summary": row[6],
                    "confidence": row[7],
                    "structured_data": row[8] if isinstance(row[8], dict) else {},
                    "source_type": row[2],
                    "document_type": row[3],
                },
            )
        return inserted

    def _normalize_accounts(
        self,
        *,
        document: Any,
        reviewed: dict[str, object],
    ) -> list[dict[str, object]]:
        structured_data = reviewed.get("structured_data")
        if not isinstance(structured_data, dict):
            return []
        raw_accounts = structured_data.get("financial_accounts")
        if not isinstance(raw_accounts, list):
            raw_accounts = self._legacy_financial_accounts(
                document=document,
                reviewed=reviewed,
                structured_data=structured_data,
            )
        if not isinstance(raw_accounts, list):
            return []

        source_type = str(reviewed.get("source_type") or document.source_type or "other")
        root_total_amount = _decimal_or_none(structured_data.get("total_amount"))
        fallback_as_of_date = (
            parse_row_date(_string_or_none(structured_data.get("as_of_date")))
            or _statement_period_end_date(structured_data.get("statement_period"))
            or parse_row_date(_string_or_none(getattr(document, "statement_end", None)))
            or _statement_period_end_date(_string_or_none(getattr(document, "filename", None)))
        )
        account_dicts = [account for account in raw_accounts if isinstance(account, dict)]
        single_account_document = len(account_dicts) == 1
        normalized_accounts: list[dict[str, object]] = []
        for raw_account in raw_accounts:
            if not isinstance(raw_account, dict):
                continue
            account_source_type = _string_or_none(raw_account.get("source_type")) or source_type
            account_type = _string_or_none(raw_account.get("account_type")) or account_source_type
            institution_name = (
                _string_or_none(raw_account.get("institution_name"))
                or _string_or_none(raw_account.get("institution"))
                or _string_or_none(structured_data.get("provider_name"))
            )
            account_name = (
                _string_or_none(raw_account.get("account_name"))
                or _string_or_none(raw_account.get("account_label"))
                or _string_or_none(raw_account.get("account_hint"))
                or document.account_label
            )
            account_mask = _string_or_none(raw_account.get("account_mask"))
            owner_name = (
                _string_or_none(raw_account.get("owner_name"))
                or _string_or_none(structured_data.get("owner_name"))
            )
            currency = _string_or_none(raw_account.get("currency")) or _string_or_none(structured_data.get("currency")) or "USD"
            balance = _decimal_or_none(raw_account.get("balance"))
            holdings_value = _decimal_or_none(raw_account.get("holdings_value"))
            cash_balance = _decimal_or_none(raw_account.get("cash_balance")) or _decimal_or_none(raw_account.get("available_cash"))
            if single_account_document and root_total_amount is not None and balance is None:
                if account_source_type == "credit_card":
                    balance = root_total_amount
                elif account_source_type in {"brokerage", "retirement"} and holdings_value is None and cash_balance is None:
                    balance = root_total_amount
                    holdings_value = root_total_amount
                elif account_source_type == "bank" and cash_balance is None:
                    balance = root_total_amount
                    cash_balance = root_total_amount
            if balance is None and (holdings_value is not None or cash_balance is not None):
                balance = round((holdings_value or 0.0) + (cash_balance or 0.0), 4)
            if holdings_value is None and balance is not None and account_source_type in {"brokerage", "retirement"}:
                holdings_value = balance
            if cash_balance is None and balance is not None and account_source_type == "bank":
                cash_balance = balance
            as_of_date = parse_row_date(_string_or_none(raw_account.get("as_of_date"))) or fallback_as_of_date
            confidence = _decimal_or_none(raw_account.get("confidence")) or _decimal_or_none(reviewed.get("confidence"))
            household_account_id = _string_or_none(raw_account.get("household_account_id"))
            if not any(
                item is not None
                for item in (institution_name, account_name, account_mask, balance, holdings_value, cash_balance, household_account_id)
            ):
                continue
            metadata = {
                key: value
                for key, value in raw_account.items()
                if key
                not in {
                    "account_type",
                    "asset_group",
                    "institution_name",
                    "institution",
                    "account_name",
                    "account_label",
                    "account_hint",
                    "account_mask",
                    "owner_name",
                    "currency",
                    "balance",
                    "holdings_value",
                    "cash_balance",
                    "available_cash",
                    "as_of_date",
                    "confidence",
                    "household_account_id",
                }
                and value is not None
            }
            normalized_accounts.append(
                {
                    "household_account_id": household_account_id,
                    "source_type": account_source_type,
                    "asset_group": _asset_group(raw_account.get("asset_group"), source_type=account_source_type),
                    "account_type": account_type,
                    "institution_name": institution_name,
                    "account_name": account_name,
                    "account_mask": account_mask,
                    "owner_name": owner_name,
                    "currency": currency,
                    "balance": balance,
                    "holdings_value": holdings_value,
                    "cash_balance": cash_balance,
                    "as_of_date": as_of_date,
                    "confidence": confidence,
                    "metadata": metadata,
                }
            )
        return normalized_accounts

    def _legacy_financial_accounts(
        self,
        *,
        document: Any,
        reviewed: dict[str, object],
        structured_data: dict[str, object],
    ) -> list[dict[str, object]] | None:
        source_type = str(reviewed.get("source_type") or getattr(document, "source_type", "") or "other")
        total_amount = _decimal_or_none(structured_data.get("total_amount"))
        account_hint = (
            _string_or_none(structured_data.get("account_hint"))
            or _string_or_none(getattr(document, "account_label", None))
        )
        if source_type in {"brokerage", "retirement"} and total_amount is not None and account_hint:
            statement_period = _string_or_none(structured_data.get("statement_period"))
            if statement_period and statement_period.lower().startswith("as of "):
                statement_period = statement_period[6:].strip()
            lowered_hint = account_hint.lower()
            asset_group = _asset_group(None, source_type=source_type)
            account_type = source_type
            if "529" in lowered_hint or "college" in lowered_hint:
                asset_group = "education"
                account_type = "529"
            return [
                {
                    "asset_group": asset_group,
                    "account_type": account_type,
                    "account_name": account_hint,
                    "balance": total_amount,
                    "holdings_value": total_amount,
                    "currency": _string_or_none(structured_data.get("currency")) or "USD",
                    "as_of_date": statement_period,
                    "confidence": reviewed.get("confidence"),
                }
            ]
        if source_type == "credit_card" and total_amount is not None and account_hint:
            return [
                {
                    "asset_group": "credit",
                    "account_type": "credit_card",
                    "account_name": account_hint,
                    "balance": total_amount,
                    "currency": _string_or_none(structured_data.get("currency")) or "USD",
                    "confidence": reviewed.get("confidence"),
                }
            ]
        return None

    def _dedupe_accounts(
        self,
        accounts: list[HouseholdEvidenceAccount],
    ) -> list[HouseholdEvidenceAccount]:
        deduped: list[HouseholdEvidenceAccount] = []
        seen: set[tuple[str, ...]] = set()
        for account in accounts:
            identity = _account_identity(account)
            if identity in seen:
                continue
            seen.add(identity)
            deduped.append(account)
        return deduped
