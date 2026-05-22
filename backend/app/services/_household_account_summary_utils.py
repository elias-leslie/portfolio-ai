"""Low-level utilities for household account summaries.

Text normalization, timestamp parsing, freshness thresholds, and account
value helpers used throughout the account-summary pipeline.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdDocument,
    HouseholdEvidenceAccount,
)

_BALANCE_FRESHNESS_THRESHOLDS: dict[str, tuple[int, int]] = {
    "cash": (3, 7),
    "credit": (3, 7),
    "debt": (7, 14),
    "taxable": (7, 30),
    "retirement": (7, 30),
    "education": (7, 30),
    "other": (14, 30),
}
_TRANSACTION_FRESHNESS_THRESHOLDS: dict[str, tuple[int, int]] = {
    "spend_driver": (3, 7),
    "net_worth_only": (7, 30),
}
_FRESHNESS_SEVERITY: dict[str, int] = {
    "fresh": 0,
    "aging": 1,
    "stale": 2,
    "needs_evidence": 3,
    "not_applicable": -1,
}
_PORTFOLIO_ACCOUNT_GROUPS: dict[str, str] = {
    "401k": "retirement",
    "HSA": "retirement",
    "IRA": "retirement",
    "Roth": "retirement",
    "Taxable": "taxable",
}
_MATCH_TOKEN_STOPWORDS: set[str] = {
    "account",
    "accounts",
    "bank",
    "bill",
    "card",
    "cash",
    "credit",
    "fund",
    "investment",
    "joint",
    "management",
    "plan",
    "retirement",
    "statement",
    "system",
}


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _compact_key(*parts: object) -> str:
    return "|".join(_normalize_text(part) for part in parts if _normalize_text(part))


def _owner_tokens(value: str | None) -> list[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return []
    return [token for token in re.split(r"[^a-z0-9]+", normalized) if token]


def _match_tokens(*values: str | None) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for token in _owner_tokens(value):
            if len(token) < 3 or token in _MATCH_TOKEN_STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def _owners_match(left: str | None, right: str | None) -> bool:
    left_tokens = _owner_tokens(left)
    right_tokens = _owner_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    if left_tokens[0] != right_tokens[0]:
        return False
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    if left_set <= right_set or right_set <= left_set:
        return True
    return len(left_tokens) > 1 and len(right_tokens) > 1 and left_tokens[-1] == right_tokens[-1]


def _owner_is_household_scope(value: str | None) -> bool:
    tokens = set(_owner_tokens(value))
    if not tokens:
        return False
    return bool(tokens & {"and", "joint", "shared", "household"})


def _duplicate_label_key(value: str | None) -> str:
    normalized = _normalize_text(value)
    if not normalized:
        return ""
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


# ---------------------------------------------------------------------------
# Account identity helpers
# ---------------------------------------------------------------------------


def _derive_account_mask(
    account_mask: str | None,
    account_name: str | None,
) -> str:
    normalized_mask = _normalize_text(account_mask)
    if normalized_mask:
        return normalized_mask
    normalized_name = _normalize_text(account_name)
    if not normalized_name:
        return ""
    match = re.search(r"(?:#|acct(?:ount)?\s*)([a-z0-9]{4,})", normalized_name)
    if match is not None:
        return match.group(1)
    return ""


def _identity_completeness_score(account: HouseholdEvidenceAccount) -> int:
    score = 0
    if account.institution_name:
        score += 3
    if account.account_name:
        score += 3
    if _derive_account_mask(account.account_mask, account.account_name):
        score += 4
    if account.owner_name:
        score += 2
    return score


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            try:
                dt = datetime.fromisoformat(f"{text}T00:00:00+00:00")
            except ValueError:
                return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _latest_document_timestamp(document: HouseholdDocument | None) -> datetime | None:
    if document is None:
        return None
    for candidate in (document.statement_end, document.parsed_at, document.uploaded_at):
        dt = _parse_datetime(candidate)
        if dt is not None:
            return dt
    return None


def _latest_evidence_timestamp(
    account: HouseholdEvidenceAccount,
    document: HouseholdDocument | None,
) -> datetime | None:
    return _parse_datetime(account.as_of_date) or _latest_document_timestamp(document)


def _format_date_label(value: str | None) -> str | None:
    dt = _parse_datetime(value)
    return dt.date().isoformat() if dt is not None else None


# ---------------------------------------------------------------------------
# Account value extraction
# ---------------------------------------------------------------------------


def _account_value(account: HouseholdEvidenceAccount) -> float | None:
    if account.balance is not None:
        return float(account.balance)
    if account.holdings_value is not None or account.cash_balance is not None:
        return float(account.holdings_value or 0.0) + float(account.cash_balance or 0.0)
    return None


def _source_account_float(source_value: dict[str, Any] | None, key: str) -> float | None:
    if not source_value:
        return None
    value = source_value.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _portfolio_value(account: Any, holdings_by_account: dict[str, float]) -> float:
    return round(
        float(getattr(account, "cash_balance", 0.0) or 0.0) + holdings_by_account.get(account.id, 0.0),
        2,
    )


# ---------------------------------------------------------------------------
# Freshness calculations
# ---------------------------------------------------------------------------


def _freshness_state_from_thresholds(
    thresholds: dict[str, tuple[int, int]],
    threshold_key: str,
    *,
    days_since: int | None,
    empty_label: str = "Needs evidence",
) -> tuple[str, str]:
    if days_since is None:
        return "needs_evidence", empty_label
    fallback_key = "other" if "other" in thresholds else "net_worth_only"
    fresh_days, aging_days = thresholds.get(threshold_key, thresholds[fallback_key])
    if days_since <= fresh_days:
        return "fresh", "Fresh"
    if days_since <= aging_days:
        return "aging", "Refresh soon"
    return "stale", "Stale"


def _combine_freshness(
    *,
    money_role: str,
    balance_status: str,
    balance_label: str,
    transaction_status: str,
    transaction_label: str,
) -> tuple[str, str]:
    if money_role != "spend_driver" or transaction_status == "not_applicable":
        return balance_status, balance_label
    if _FRESHNESS_SEVERITY[transaction_status] >= _FRESHNESS_SEVERITY[balance_status]:
        return transaction_status, transaction_label
    return balance_status, balance_label


def _transaction_freshness_pair(
    money_role: str,
    days_since_transaction: int | None,
) -> tuple[str, str]:
    if money_role == "spend_driver":
        return _freshness_state_from_thresholds(
            _TRANSACTION_FRESHNESS_THRESHOLDS,
            money_role,
            days_since=days_since_transaction,
            empty_label="Needs transactions",
        )
    return "not_applicable", "Not required"


# ---------------------------------------------------------------------------
# Money role
# ---------------------------------------------------------------------------


def _money_role(asset_group: str, account_type: str, label: str) -> str:
    normalized = " ".join(
        [_normalize_text(asset_group), _normalize_text(account_type), _normalize_text(label)]
    )
    if asset_group in {"cash", "credit", "debt"}:
        return "spend_driver"
    if asset_group == "taxable" and any(
        token in normalized
        for token in ("checking", "savings", "cash management", "cash_management")
    ):
        return "spend_driver"
    return "net_worth_only"


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------


def _asset_group_label(asset_group: str) -> str:
    labels = {
        "cash": "Cash",
        "credit": "Credit",
        "debt": "Debt",
        "education": "Education",
        "other": "Other",
        "retirement": "Retirement",
        "taxable": "Taxable",
    }
    return labels.get(asset_group, asset_group.replace("_", " ").title())


def _account_label(account: HouseholdEvidenceAccount) -> str:
    owner = _normalize_text(account.owner_name)
    derived_mask = _derive_account_mask(account.account_mask, account.account_name)
    owner_suffix = f" ({account.owner_name})" if owner and not derived_mask else ""
    if account.institution_name and account.account_name:
        return f"{account.institution_name} · {account.account_name}{owner_suffix}"
    if account.account_name:
        return f"{account.account_name}{owner_suffix}"
    if account.institution_name:
        if account.account_mask:
            return f"{account.institution_name} · …{account.account_mask}"
        return f"{account.institution_name}{owner_suffix}"
    return account.account_type.replace("_", " ").title()


def _evidence_group_key(account: HouseholdEvidenceAccount) -> str:
    institution = _normalize_text(account.institution_name)
    name = _normalize_text(account.account_name)
    owner = _normalize_text(account.owner_name)
    mask = _derive_account_mask(account.account_mask, account.account_name)
    account_type = _normalize_text(account.account_type)
    asset_group = _normalize_text(account.asset_group)
    if mask:
        return _compact_key("evidence", mask, asset_group or account_type)
    if institution and name:
        if owner:
            return _compact_key("evidence", institution, name, owner, account_type or asset_group)
        return _compact_key("evidence", institution, name, account_type or asset_group)
    if name:
        if owner:
            return _compact_key("evidence", name, owner, account_type or asset_group)
        return _compact_key("evidence", name, account_type or asset_group)
    return _compact_key("evidence", account.id)


def _portfolio_label(account: Any) -> str:
    return str(getattr(account, "name", None) or getattr(account, "account_type", "Account"))


def _tracked_label(account: Any) -> str:
    return account.label


def _portfolio_summary_key(account: Any) -> str:
    return _compact_key("portfolio", getattr(account, "id", None) or _portfolio_label(account))


def _tracked_summary_key(account: Any) -> str:
    return _compact_key("tracked", account.id)


def _portfolio_asset_group(account: Any) -> str:
    return _PORTFOLIO_ACCOUNT_GROUPS.get(str(getattr(account, "account_type", "")), "other")


def _portfolio_source_type(account: Any) -> str:
    source_types = {"retirement": "retirement", "taxable": "brokerage"}
    return source_types.get(_portfolio_asset_group(account), "portfolio")


# ---------------------------------------------------------------------------
# Transaction timestamps
# ---------------------------------------------------------------------------


def _latest_transaction_timestamp(
    document_ids: list[str],
    *,
    household_account_id: str | None,
    label_candidates: set[str],
    account_mask: str | None,
    latest_transaction_dates_by_household_account: dict[str, date],
    latest_transaction_dates_by_document: dict[str, date],
    latest_transaction_dates_by_account_label: dict[str, date],
) -> datetime | None:
    transaction_dates: list[date] = [
        latest_transaction_dates_by_document[doc_id]
        for doc_id in document_ids
        if latest_transaction_dates_by_document.get(doc_id) is not None
    ]
    if household_account_id and latest_transaction_dates_by_household_account.get(household_account_id) is not None:
        transaction_dates.append(latest_transaction_dates_by_household_account[household_account_id])
    normalized_mask = _normalize_text(account_mask)
    for raw_label, transaction_date in latest_transaction_dates_by_account_label.items():
        normalized_label = _normalize_text(raw_label)
        if not normalized_label:
            continue
        if normalized_label in label_candidates:
            transaction_dates.append(transaction_date)
            continue
        if normalized_mask and normalized_mask in normalized_label:
            transaction_dates.append(transaction_date)
    latest_date = max(transaction_dates, default=None)
    if latest_date is None:
        return None
    return datetime.combine(latest_date, datetime.min.time(), tzinfo=UTC)


def _latest_transaction_coverage_timestamp(
    accounts: list[HouseholdEvidenceAccount],
    *,
    latest_transaction_dt: datetime | None,
) -> datetime | None:
    coverage_dates = [latest_transaction_dt] if latest_transaction_dt is not None else []
    for account in accounts:
        observed_through = _parse_datetime(account.metadata.get("activity_observed_through"))
        if observed_through is not None:
            coverage_dates.append(observed_through)
    return max(coverage_dates, default=None)


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------


def _is_closed_zero_balance_account(
    account: HouseholdEvidenceAccount,
    *documents: HouseholdDocument | None,
) -> bool:
    fields = [
        account.account_name,
        account.institution_name,
        account.account_type,
        account.asset_group,
        account.owner_name,
        *(document.account_label for document in documents if document is not None),
    ]
    normalized = _normalize_text(" ".join(field for field in fields if field))
    if "closed" not in normalized or account.asset_group not in {"cash", "credit", "debt"}:
        return False

    for document in documents:
        metadata = document.metadata if document is not None else {}
        structured = metadata.get("structured_data") if isinstance(metadata, dict) else None
        preview = structured.get("text_preview") if isinstance(structured, dict) else None
        if preview and "payoff debit" in _normalize_text(preview) and "0.00" in str(preview):
            return True
    return False


def _best_display_account(
    accounts: list[HouseholdEvidenceAccount],
    documents_by_id: dict[str, HouseholdDocument],
) -> HouseholdEvidenceAccount:
    return max(
        accounts,
        key=lambda account: (
            1 if _account_value(account) is not None else 0,
            _identity_completeness_score(account),
            _latest_evidence_timestamp(account, documents_by_id.get(account.document_id))
            or datetime.min.replace(tzinfo=UTC),
            float(account.confidence or 0.0),
        ),
    )


def _best_balance_account(
    accounts: list[HouseholdEvidenceAccount],
    documents_by_id: dict[str, HouseholdDocument],
) -> HouseholdEvidenceAccount:
    candidates = [account for account in accounts if _account_value(account) is not None]
    if not candidates:
        return _best_display_account(accounts, documents_by_id)
    return max(
        candidates,
        key=lambda account: (
            _latest_evidence_timestamp(account, documents_by_id.get(account.document_id))
            or datetime.min.replace(tzinfo=UTC),
            float(account.confidence or 0.0),
            _identity_completeness_score(account),
        ),
    )


def _confidence_for_summary(
    latest: HouseholdEvidenceAccount,
    *,
    evidence_count: int,
    linked: bool,
) -> float:
    confidence = float(latest.confidence or 0.65)
    if latest.institution_name:
        confidence += 0.08
    if latest.account_name:
        confidence += 0.08
    if latest.account_mask:
        confidence += 0.12
    if evidence_count > 1:
        confidence += 0.07
    if linked:
        confidence = max(confidence, 0.9)
    return round(min(confidence, 0.99), 2)


def _allows_unique_institution_fallback(
    *,
    asset_group: str,
    account_type: str | None,
    label: str,
    account_name: str | None,
    hint_label: str | None,
    institution_name: str | None,
) -> bool:
    combined_label = " ".join(
        part for part in (label, account_name, hint_label, institution_name) if _normalize_text(part)
    )
    return _money_role(asset_group, account_type or "", combined_label) == "spend_driver"


def _join_with_and(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"
