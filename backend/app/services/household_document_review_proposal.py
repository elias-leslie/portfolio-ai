"""Build and cryptographically bind user-visible document review proposals."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from app.models.household_finance import HouseholdDocument
from app.services._household_document_pipeline_utils import parse_row_date
from app.services._household_transaction_parsers import extract_transactions
from app.services.household_document_review_contracts import (
    HouseholdDocumentReviewPayload,
    HouseholdDocumentReviewProposalPreview,
)
from app.services.household_finance_rows import FIELD_LABELS

_SENSITIVE_FIELD_PARTS = frozenset(
    {
        "account_number",
        "credential",
        "password",
        "routing_number",
        "secret",
        "security_answer",
        "ssn",
        "tax_id",
        "token",
    }
)
_LONG_DIGIT_RUN = re.compile(r"(?<!\d)(\d{5,})(?!\d)")


def canonical_review_json(value: object) -> str:
    """Return deterministic JSON used for equality checks and SHA-256 binding."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _text(value: object) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).strip().split())
    return normalized or None


def _first_present(*values: object) -> object:
    return next((value for value in values if value not in (None, "")), None)


def _redact_digit_run(match: re.Match[str]) -> str:
    digits = match.group(1)
    return f"••••{digits[-4:]}"


def _redacted_label(value: object, *, fallback: str) -> str:
    label = _text(value) or fallback
    return _LONG_DIGIT_RUN.sub(_redact_digit_run, label)[:160]


def _account_suffix(account: dict[str, object]) -> str | None:
    raw = _text(account.get("account_mask") or account.get("extracted_account_mask"))
    if raw is None:
        return None
    digits = "".join(character for character in raw if character.isdigit())
    return digits[-4:] or None


def _account_label(
    account: dict[str, object],
    *,
    document: HouseholdDocument,
) -> str:
    account_name = _text(account.get("account_name") or account.get("name"))
    institution = _text(
        account.get("institution_name") or account.get("institution")
    )
    base = " · ".join(item for item in (institution, account_name) if item)
    if not base:
        base = _text(document.account_label) or "Account snapshot"
    suffix = _account_suffix(account)
    if suffix and suffix not in base:
        base = f"{base} · ••••{suffix}"
    return _redacted_label(base, fallback="Account snapshot")


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    text = str(value).strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = text.replace("$", "").replace(",", "").strip("() ")
    try:
        parsed = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not parsed.is_finite():
        return None
    return -parsed if negative else parsed


def _date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    parsed = parse_row_date(str(value)) if value not in (None, "") else None
    return date.fromisoformat(parsed[:10]) if parsed else None


def _redacted_json_value(value: object, *, field: str | None = None) -> object:
    normalized_field = (field or "").strip().lower()
    if any(part in normalized_field for part in _SENSITIVE_FIELD_PARTS):
        return "[redacted]"
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Decimal | date):
        return str(value)
    if isinstance(value, list | tuple):
        return [_redacted_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _redacted_json_value(item, field=str(key))
            for key, item in value.items()
        }
    return str(value)


def _transaction_preview(
    transaction: dict[str, object],
    *,
    account_label: str | None,
) -> dict[str, object]:
    merchant = _text(
        transaction.get("merchant")
        or transaction.get("raw_merchant")
        or transaction.get("description")
        or transaction.get("name")
    )
    currency = _text(transaction.get("currency"))
    return {
        "account_label": account_label,
        "transaction_date": _date(
            transaction.get("transaction_date")
            or transaction.get("date")
            or transaction.get("posted_date")
            or transaction.get("trade_date")
        ),
        "merchant": merchant[:300] if merchant else None,
        "amount": _decimal(
            _first_present(
                transaction.get("amount"),
                transaction.get("total_amount"),
                transaction.get("market_value"),
            )
        ),
        "currency": currency[:12] if currency else None,
    }


def _holding_preview(
    holding: dict[str, object],
    *,
    account_label: str | None,
) -> dict[str, object]:
    symbol = _text(
        holding.get("symbol") or holding.get("ticker") or holding.get("security_symbol")
    )
    return {
        "account_label": account_label,
        "symbol": symbol.upper()[:32] if symbol else None,
        "shares": _decimal(
            _first_present(
                holding.get("shares"),
                holding.get("quantity"),
                holding.get("units"),
            )
        ),
        "value": _decimal(
            _first_present(
                holding.get("value"),
                holding.get("market_value"),
                holding.get("current_value"),
                holding.get("holdings_value"),
            )
        ),
    }


def _field_previews(items: object, *, kind: str) -> list[dict[str, object]]:
    if not isinstance(items, list):
        return []
    previews: list[dict[str, object]] = []
    for index, raw_item in enumerate(items):
        if not isinstance(raw_item, dict):
            continue
        item = cast(dict[str, object], raw_item)
        if kind == "inference":
            field = _text(item.get("field_name") or item.get("field"))
            if field not in FIELD_LABELS:
                continue
            value = item.get("value")
        else:
            section = _text(item.get("section"))
            action = _text(item.get("action"))
            field = _text(item.get("field_name") or item.get("field"))
            if field is None:
                field = ".".join(part for part in (section, action) if part)
            value = item.get("value") if "value" in item else item.get("data")
            if value is None:
                value = {
                    key: candidate
                    for key, candidate in item.items()
                    if key not in {"section", "action", "field", "field_name"}
                }
        previews.append(
            {
                "field": (field or f"{kind}_{index + 1}")[:200],
                "value": _redacted_json_value(value, field=field),
            }
        )
    return previews


def build_document_review_preview(
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
    stored_path: Path | None = None,
    normalized_accounts: list[dict[str, object]] | None = None,
) -> HouseholdDocumentReviewProposalPreview:
    """Build the exact typed preview shown to the user before approval."""
    structured = reviewed.get("structured_data")
    structured = cast(dict[str, object], structured) if isinstance(structured, dict) else {}
    raw_accounts = structured.get("financial_accounts")
    account_rows = raw_accounts if isinstance(raw_accounts, list) else []

    accounts: list[dict[str, object]] = []
    transactions: list[dict[str, object]] = []
    holdings: list[dict[str, object]] = []
    for raw_account in account_rows:
        if not isinstance(raw_account, dict):
            continue
        account = cast(dict[str, object], raw_account)
        label = _account_label(account, document=document)
        if normalized_accounts is None:
            accounts.append(
                {
                    "label": label,
                    "account_suffix": _account_suffix(account),
                    "balance": _decimal(
                        _first_present(
                            account.get("balance"), account.get("account_balance")
                        )
                    ),
                    "holdings_value": _decimal(account.get("holdings_value")),
                    "cash_balance": _decimal(account.get("cash_balance")),
                    "currency": _text(
                        account.get("currency") or structured.get("currency")
                    ),
                    "as_of_date": _date(
                        account.get("as_of_date") or structured.get("as_of_date")
                    ),
                }
            )
        raw_transactions = account.get("transactions")
        if isinstance(raw_transactions, list):
            transactions.extend(
                _transaction_preview(item, account_label=label)
                for item in raw_transactions
                if isinstance(item, dict)
            )
        raw_holdings = account.get("holdings")
        if isinstance(raw_holdings, list):
            holdings.extend(
                _holding_preview(item, account_label=label)
                for item in raw_holdings
                if isinstance(item, dict)
            )

    if normalized_accounts is not None:
        accounts.extend(
            {
                "label": _account_label(account, document=document),
                "account_suffix": _account_suffix(account),
                "balance": _decimal(account.get("balance")),
                "holdings_value": _decimal(account.get("holdings_value")),
                "cash_balance": _decimal(account.get("cash_balance")),
                "currency": _text(account.get("currency")),
                "as_of_date": _date(account.get("as_of_date")),
            }
            for account in normalized_accounts
        )

    top_level_transactions = structured.get("transactions")
    if isinstance(top_level_transactions, list):
        top_level_label = _redacted_label(
            structured.get("account_hint") or document.account_label,
            fallback="Document transactions",
        )
        transactions.extend(
            _transaction_preview(item, account_label=top_level_label)
            for item in top_level_transactions
            if isinstance(item, dict)
        )

    extracted_text = reviewed.get("extracted_text")
    parsed_transactions = extract_transactions(
        filename=document.filename,
        source_type=str(reviewed.get("source_type") or document.source_type or ""),
        document_type=str(
            reviewed.get("document_type") or document.document_type or ""
        ),
        extracted_text=extracted_text if isinstance(extracted_text, str) else "",
        structured_data=structured,
        account_label=(
            document.account_label
            or _text(structured.get("account_hint"))
            or _text(structured.get("account_mask"))
        ),
        review_summary=str(reviewed.get("summary") or ""),
        stored_path=stored_path,
    )
    transactions.extend(
        {
            "account_label": _redacted_label(
                transaction.account_label,
                fallback="Document transactions",
            ),
            "transaction_date": transaction.transaction_date,
            "merchant": _text(
                transaction.raw_merchant or transaction.description
            ),
            "amount": transaction.amount,
            "currency": transaction.currency,
        }
        for transaction in parsed_transactions
    )

    unique_transactions: list[dict[str, object]] = []
    seen_transactions: set[str] = set()
    for transaction in transactions:
        transaction_key = canonical_review_json(
            {
                key: str(value) if isinstance(value, Decimal | date) else value
                for key, value in transaction.items()
            }
        )
        if transaction_key in seen_transactions:
            continue
        seen_transactions.add(transaction_key)
        unique_transactions.append(transaction)

    return HouseholdDocumentReviewProposalPreview.model_validate(
        {
            "accounts": accounts,
            "transactions": unique_transactions,
            "holdings": holdings,
            "planning": _field_previews(
                reviewed.get("planning_items"), kind="planning"
            ),
            "inferences": _field_previews(
                reviewed.get("inferred_values"), kind="inference"
            ),
        }
    )


def document_review_proposal_hash(
    *,
    document_id: str,
    review_id: str,
    reviewed: dict[str, object],
    preview: HouseholdDocumentReviewProposalPreview,
) -> str:
    """Bind one preview to one document, review row, and normalized review payload."""
    review_payload = HouseholdDocumentReviewPayload.model_validate(reviewed).model_dump(
        by_alias=True,
        mode="json",
    )
    binding = {
        "schema_version": 2,
        "document_id": document_id,
        "review_id": review_id,
        "review_payload": review_payload,
        "proposal_preview": preview.model_dump(mode="json"),
    }
    return hashlib.sha256(canonical_review_json(binding).encode("utf-8")).hexdigest()
