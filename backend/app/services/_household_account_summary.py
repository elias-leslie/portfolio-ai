"""Canonical household account summaries and inbox derivation."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.models.household_finance import (
    HouseholdAccountGap,
    HouseholdAccountSummary,
    HouseholdDiscoveredAccount,
    HouseholdDocument,
    HouseholdEvidenceAccount,
    HouseholdInboxItem,
    HouseholdTrackedAccount,
)
from app.services._money_workspace_routes import (
    MONEY_ACCOUNTS_ROUTE,
    MONEY_DATE_QUALITY_ROUTE,
    MONEY_DISCOVERED_ACCOUNTS_ROUTE,
    MONEY_EVIDENCE_ROUTE,
    money_account_focus_route,
    money_question_focus_route,
)

_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_SEVERITY_PRIORITY = {"high": "high", "medium": "medium", "low": "low"}
_INBOX_CATEGORY_ORDER = {"intake": 0, "coverage": 1, "question": 2, "account": 3}
_BALANCE_FRESHNESS_THRESHOLDS = {
    "cash": (3, 7),
    "credit": (3, 7),
    "debt": (7, 14),
    "taxable": (7, 30),
    "retirement": (7, 30),
    "education": (7, 30),
    "other": (14, 30),
}
_TRANSACTION_FRESHNESS_THRESHOLDS = {
    "spend_driver": (3, 7),
    "net_worth_only": (7, 30),
}
_FRESHNESS_SEVERITY = {
    "fresh": 0,
    "aging": 1,
    "stale": 2,
    "needs_evidence": 3,
    "not_applicable": -1,
}
_PORTFOLIO_ACCOUNT_GROUPS = {
    "401k": "retirement",
    "HSA": "retirement",
    "IRA": "retirement",
    "Roth": "retirement",
    "Taxable": "taxable",
}
_MATCH_TOKEN_STOPWORDS = {
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
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


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


def _portfolio_value(account: Any, holdings_by_account: dict[str, float]) -> float:
    return round(float(getattr(account, "cash_balance", 0.0) or 0.0) + holdings_by_account.get(account.id, 0.0), 2)


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


def _tracked_label(account: HouseholdTrackedAccount) -> str:
    return account.label


def _portfolio_summary_key(account: Any) -> str:
    return _compact_key("portfolio", getattr(account, "id", None) or _portfolio_label(account))


def _tracked_summary_key(account: HouseholdTrackedAccount) -> str:
    return _compact_key("tracked", account.id)


def _portfolio_asset_group(account: Any) -> str:
    return _PORTFOLIO_ACCOUNT_GROUPS.get(str(getattr(account, "account_type", "")), "other")


def _portfolio_source_type(account: Any) -> str:
    source_types = {"retirement": "retirement", "taxable": "brokerage"}
    return source_types.get(_portfolio_asset_group(account), "portfolio")


def _freshness_state_from_thresholds(
    thresholds: dict[str, tuple[int, int]],
    threshold_key: str,
    *,
    days_since: int | None,
    empty_label: str = "Needs evidence",
) -> tuple[str, str]:
    if days_since is None:
        return "needs_evidence", empty_label
    fresh_days, aging_days = thresholds.get(
        threshold_key, thresholds["other" if "other" in thresholds else "net_worth_only"]
    )
    if days_since <= fresh_days:
        return "fresh", "Fresh"
    if days_since <= aging_days:
        return "aging", "Refresh soon"
    return "stale", "Stale"


def _money_role(asset_group: str, account_type: str, label: str) -> str:
    normalized = " ".join([_normalize_text(asset_group), _normalize_text(account_type), _normalize_text(label)])
    if asset_group in {"cash", "credit", "debt"}:
        return "spend_driver"
    if asset_group == "taxable" and any(
        token in normalized
        for token in ("checking", "savings", "cash management", "cash_management")
    ):
        return "spend_driver"
    return "net_worth_only"


def _allows_unique_institution_fallback(
    *,
    asset_group: str,
    account_type: str | None,
    label: str,
    account_name: str | None,
    hint_label: str | None,
    institution_name: str | None,
) -> bool:
    combined_label = " ".join(part for part in (label, account_name, hint_label, institution_name) if _normalize_text(part))
    return _money_role(asset_group, account_type or "", combined_label) == "spend_driver"


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
    transaction_dates = [
        latest_transaction_dates_by_document[document_id]
        for document_id in document_ids
        if latest_transaction_dates_by_document.get(document_id) is not None
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


def _match_portfolio_account(
    *,
    household_account_id: str | None,
    label: str,
    account_name: str | None,
    asset_group: str,
    portfolio_accounts: list[Any],
) -> Any | None:
    if household_account_id:
        direct = [
            account
            for account in portfolio_accounts
            if str(getattr(account, "household_account_id", "") or "") == household_account_id
        ]
        if len(direct) == 1:
            return direct[0]
    normalized_label = _normalize_text(label)
    normalized_account_name = _normalize_text(account_name)
    if not normalized_label and not normalized_account_name:
        return None
    matches = [
        account
        for account in portfolio_accounts
        if _portfolio_asset_group(account) == asset_group
        and _normalize_text(_portfolio_label(account)) in {
            normalized_label,
            normalized_account_name,
        }
    ]
    return matches[0] if len(matches) == 1 else None


def _match_tracked_account(
    *,
    group_key: str,
    label: str,
    account_name: str | None,
    hint_label: str | None,
    asset_group: str,
    account_type: str | None,
    institution_name: str | None,
    owner_name: str | None,
    account_mask: str | None,
    tracked_accounts: list[HouseholdTrackedAccount],
) -> HouseholdTrackedAccount | None:
    normalized_asset_group = _normalize_text(asset_group)
    normalized_institution = _normalize_text(institution_name)
    normalized_owner = _normalize_text(owner_name)
    label_candidates = {
        _normalize_text(candidate)
        for candidate in (label, account_name, hint_label)
        if _normalize_text(candidate)
    }
    evidence_tokens = _match_tokens(label, account_name, hint_label, institution_name)
    evidence_signature = (
        _compact_key(institution_name, account_mask)
        if institution_name and account_mask
        else ""
    )
    same_institution_candidates = [
        account
        for account in tracked_accounts
        if _normalize_text(account.asset_group) == normalized_asset_group
        and _normalize_text(account.institution_name) == normalized_institution
    ]
    ranked: list[tuple[int, HouseholdTrackedAccount]] = []
    for account in tracked_accounts:
        if _normalize_text(account.asset_group) != normalized_asset_group:
            continue
        tracked_institution = _normalize_text(account.institution_name)
        tracked_owner = _normalize_text(account.owner_name)
        tracked_tokens = _match_tokens(account.label, account.institution_name)
        identity_locked = bool(account.match_key or account.account_mask)
        score = 0
        if account.match_key and _normalize_text(account.match_key) == _normalize_text(group_key):
            score = 5
        elif (
            evidence_signature
            and account.institution_name
            and account.account_mask
            and _compact_key(account.institution_name, account.account_mask) == evidence_signature
        ):
            score = 4
        elif (
            not identity_locked
            and
            normalized_institution
            and normalized_owner
            and tracked_institution == normalized_institution
            and _owners_match(tracked_owner, normalized_owner)
        ):
            score = 3
        elif (not identity_locked and _normalize_text(account.label) in label_candidates) or (
            not identity_locked
            and
            normalized_institution
            and tracked_institution == normalized_institution
            and account.account_mask is None
            and len(same_institution_candidates) == 1
            and len(tracked_tokens & evidence_tokens) >= 1
            and _allows_unique_institution_fallback(
                asset_group=asset_group,
                account_type=account_type,
                label=label,
                account_name=account_name,
                hint_label=hint_label,
                institution_name=institution_name,
            )
            and (
                not normalized_owner
                or not tracked_owner
                or _owners_match(tracked_owner, normalized_owner)
                or _owner_is_household_scope(account.owner_name)
            )
        ):
            score = 2
        elif (
            not identity_locked
            and
            len(tracked_tokens & evidence_tokens) >= 2
            and not (
                normalized_owner
                and tracked_owner
                and not _owners_match(tracked_owner, normalized_owner)
            )
        ):
            score = 1
        if score > 0:
            ranked.append((score, account))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1].updated_at), reverse=False)
    top_score = ranked[0][0]
    best = [account for score, account in ranked if score == top_score]
    return best[0] if len(best) == 1 else None


def _document_issue_flags(document: HouseholdDocument | None) -> list[HouseholdAccountGap]:
    if document is None:
        return []
    metadata = document.metadata if isinstance(document.metadata, dict) else {}
    gaps: list[HouseholdAccountGap] = []
    if metadata.get("file_available") is False:
        gaps.append(
            HouseholdAccountGap(
                code="source_missing",
                severity="medium",
                title="Source file unavailable",
                detail="The original file is missing, so Jenny is relying on stored review output instead of the source file.",
            )
        )
    application_summary = metadata.get("application_summary")
    application = application_summary if isinstance(application_summary, dict) else {}
    if application.get("status") == "incomplete":
        gaps.append(
            HouseholdAccountGap(
                code="incomplete_application",
                severity="high",
                title="Incomplete ingestion",
                detail="Jenny reviewed this document, but it did not safely produce a full account update yet.",
            )
        )
    return gaps


def _top_gap(gaps: list[HouseholdAccountGap]) -> HouseholdAccountGap | None:
    if not gaps:
        return None
    return sorted(gaps, key=lambda gap: (_PRIORITY_ORDER[_SEVERITY_PRIORITY[gap.severity]], gap.title))[0]


def _format_date_label(value: str | None) -> str | None:
    dt = _parse_datetime(value)
    return dt.date().isoformat() if dt is not None else None


def _join_with_and(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _account_blocked_metrics(account: HouseholdAccountSummary, gap_code: str) -> list[str]:
    blocks: list[str] = []
    if gap_code in {
        "missing_evidence",
        "missing_current_state",
        "refresh_balance_soon",
        "stale_balance",
        "refresh_soon",
        "stale_evidence",
        "incomplete_application",
        "missing_balance",
    }:
        blocks.append("net worth")
    if account.money_role == "spend_driver" and gap_code in {
        "missing_evidence",
        "refresh_transactions_soon",
        "stale_transactions",
        "missing_transaction_history",
        "statement_gap",
        "missing_current_state",
    }:
        blocks.extend(["monthly spend", "budget status", "safe to spend"])
    return blocks


def _account_request_detail(account: HouseholdAccountSummary, gap_code: str) -> str | None:
    today = datetime.now(UTC).date()
    last_balance = _parse_datetime(account.last_balance_at)
    last_transaction = _parse_datetime(account.last_transaction_at)
    blocks = _account_blocked_metrics(account, gap_code)
    block_suffix = f" Blocks {_join_with_and(blocks)}." if blocks else ""
    detail: str | None = None

    if gap_code in {"refresh_transactions_soon", "stale_transactions"}:
        start = (last_transaction.date() + timedelta(days=1)) if last_transaction is not None else today - timedelta(days=30)
        detail = (
            f"Need a bank or card statement/export covering {start.isoformat()} through {today.isoformat()}."
            f"{block_suffix}"
        )
    elif gap_code == "missing_transaction_history":
        start = (today - timedelta(days=30)).isoformat()
        detail = (
            f"Need a statement or export covering at least {start} through {today.isoformat()} so Jenny can trust cash-flow."
            f"{block_suffix}"
        )
    elif gap_code in {"refresh_balance_soon", "stale_balance", "refresh_soon", "stale_evidence"}:
        if last_balance is not None:
            detail = (
                f"Need a newer balance statement, screenshot, or export after {last_balance.date().isoformat()}."
                f"{block_suffix}"
            )
        else:
            detail = f"Need current balance evidence as of {today.isoformat()}.{block_suffix}"
    elif gap_code in {"missing_evidence", "missing_current_state", "incomplete_application", "missing_balance"}:
        if account.money_role == "spend_driver":
            start = (today - timedelta(days=30)).isoformat()
            detail = (
                f"Need the latest statement or export covering {start} through {today.isoformat()}."
                f"{block_suffix}"
            )
        else:
            detail = (
                f"Need a current statement, screenshot, or export as of {today.isoformat()}."
                f"{block_suffix}"
            )
    elif gap_code == "statement_gap":
        detail = f"Need the missing statement month(s) uploaded to close known ledger gaps.{block_suffix}"
    return detail


def _gap(code: str, severity: str, title: str, detail: str) -> HouseholdAccountGap:
    return HouseholdAccountGap(code=code, severity=severity, title=title, detail=detail)


def _freshness_gaps(summary: HouseholdAccountSummary) -> list[HouseholdAccountGap]:
    gaps: list[HouseholdAccountGap] = []
    if summary.current_value is None:
        gaps.append(_gap("missing_balance", "high", "Missing balance", "Jenny could not extract a usable balance, holdings value, or cash balance for this account."))
    balance_gap_map = {
        "aging": ("refresh_balance_soon", "medium", "Refresh balance soon", "The latest balance evidence is getting old. Upload newer evidence before Jenny relies on this as current state."),
        "stale": ("stale_balance", "high", "Stale balance", "The latest balance evidence is too old to trust this account as current state."),
        "needs_evidence": ("missing_evidence", "high", "Needs evidence", "The account exists in the system, but Jenny does not have supporting financial evidence for it yet."),
    }
    balance_gap = balance_gap_map.get(summary.balance_freshness_status)
    if balance_gap is not None:
        gaps.append(_gap(*balance_gap))
    if summary.money_role != "spend_driver":
        return gaps
    transaction_gap_map = {
        "aging": ("refresh_transactions_soon", "medium", "Refresh transaction history soon", "This spending account has not been refreshed recently enough for a confident weekly cash-flow review."),
        "stale": ("stale_transactions", "high", "Stale transaction history", "This spending account is too old to trust for current monthly-spend, budget, or safe-to-spend calculations."),
    }
    transaction_gap = transaction_gap_map.get(summary.transaction_freshness_status)
    if transaction_gap is not None:
        gaps.append(_gap(*transaction_gap))
    needs_transactions = summary.transaction_freshness_status == "needs_evidence" and summary.evidence_count > 0
    missing_linked_transactions = summary.balance_freshness_status == "fresh" and summary.transaction_freshness_status == "not_applicable"
    if needs_transactions or missing_linked_transactions:
        detail = (
            "Jenny has some account evidence here but not enough linked transaction history to trust cash-flow calculations."
            if needs_transactions
            else "Jenny can see this account but cannot yet tie it to recent transaction history."
        )
        gaps.append(_gap("missing_transaction_history", "high", "Missing transaction history", detail))
    return gaps


def _coverage_gaps(summary: HouseholdAccountSummary, existing_gap_codes: set[str]) -> list[HouseholdAccountGap]:
    gaps: list[HouseholdAccountGap] = []
    if summary.freshness_status == "aging" and not ({"refresh_balance_soon", "refresh_transactions_soon"} & existing_gap_codes):
        gaps.append(_gap("refresh_soon", "medium", "Refresh soon", "Part of this account's current state is aging and should be refreshed before weekly review."))
    if summary.freshness_status == "stale" and not ({"stale_balance", "stale_transactions"} & existing_gap_codes):
        gaps.append(_gap("stale_evidence", "high", "Stale evidence", "Part of this account's current state is stale enough that Jenny should not trust it as current."))
    if summary.freshness_status == "needs_evidence" and not ({"missing_evidence", "missing_transaction_history", "missing_balance"} & existing_gap_codes):
        gaps.append(_gap("missing_current_state", "high", "Missing current state", "Jenny cannot confirm enough current evidence to treat this account as covered."))
    return gaps


def _contextual_gaps(
    summary: HouseholdAccountSummary,
    *,
    duplicate: bool,
    statement_freshness: dict[str, Any],
) -> list[HouseholdAccountGap]:
    gaps: list[HouseholdAccountGap] = []
    if summary.match_status == "candidate":
        gaps.append(_gap("unconfirmed_match", "medium", "Needs confirmation", "Jenny found a possible account/entity here, but the match is not strong enough to treat it as fully confirmed."))
    if summary.evidence_count == 1 and summary.last_evidence_at is not None:
        gaps.append(_gap("thin_evidence", "low", "Thin evidence", "This account is backed by a single document so far. More evidence will make the state more trustworthy."))
    if duplicate:
        gaps.append(_gap("possible_duplicate", "medium", "Possible duplicate", "Jenny sees another similar account and is keeping them separate until the identity is clearer."))
    if (
        statement_freshness.get("gap_months")
        and summary.asset_group in {"cash", "credit", "debt"}
        and summary.money_role == "spend_driver"
        and summary.transaction_freshness_status != "fresh"
    ):
        gaps.append(_gap("statement_gap", "medium", "Statement coverage gap", "Jenny detected a gap in transaction-month coverage, so cash-flow conclusions may still be incomplete."))
    return gaps


def _build_account_gaps(
    *,
    summary: HouseholdAccountSummary,
    latest_document: HouseholdDocument | None,
    statement_freshness: dict[str, Any],
    duplicate: bool,
) -> list[HouseholdAccountGap]:
    gaps = [*_document_issue_flags(latest_document), *_freshness_gaps(summary)]
    gaps.extend(_coverage_gaps(summary, {gap.code for gap in gaps}))
    gaps.extend(_contextual_gaps(summary, duplicate=duplicate, statement_freshness=statement_freshness))
    return sorted(gaps, key=lambda gap: (_PRIORITY_ORDER[_SEVERITY_PRIORITY[gap.severity]], gap.title))


def build_account_summaries(
    *,
    evidence_accounts: list[HouseholdEvidenceAccount],
    documents: list[HouseholdDocument],
    portfolio_accounts: list[Any],
    tracked_accounts: list[HouseholdTrackedAccount],
    account_valuations: dict[str, Any] | None = None,
    source_owned_household_account_ids: set[str] | None = None,
    source_owned_account_values: dict[str, dict[str, Any]] | None = None,
    holdings_by_account: dict[str, float],
    statement_freshness: dict[str, Any],
    latest_transaction_dates_by_household_account: dict[str, date] | None = None,
    latest_transaction_dates_by_document: dict[str, date] | None = None,
    latest_transaction_dates_by_account_label: dict[str, date] | None = None,
) -> list[HouseholdAccountSummary]:
    account_valuations = account_valuations or {}
    source_owned_household_account_ids = source_owned_household_account_ids or set()
    source_owned_account_values = source_owned_account_values or {}
    latest_transaction_dates_by_household_account = latest_transaction_dates_by_household_account or {}
    latest_transaction_dates_by_document = latest_transaction_dates_by_document or {}
    latest_transaction_dates_by_account_label = latest_transaction_dates_by_account_label or {}
    documents_by_id = {document.id: document for document in documents}
    grouped: dict[str, list[HouseholdEvidenceAccount]] = defaultdict(list)
    grouped_tracked_matches: dict[str, HouseholdTrackedAccount] = {}
    tracked_by_household_account_id = {
        account.household_account_id: account
        for account in tracked_accounts
        if account.household_account_id
    }
    evidence_household_account_id_by_group_key: dict[str, str] = {}
    evidence_household_account_id_by_match_key: dict[str, str] = {}
    for account in evidence_accounts:
        if not account.household_account_id:
            continue
        evidence_household_account_id_by_group_key.setdefault(
            _evidence_group_key(account),
            account.household_account_id,
        )
        if isinstance(account.metadata, dict):
            match_key = _normalize_text(account.metadata.get("match_key"))
            if match_key:
                evidence_household_account_id_by_match_key.setdefault(
                    match_key,
                    account.household_account_id,
                )
    for account in evidence_accounts:
        document = documents_by_id.get(account.document_id)
        matched_tracked_account = None
        if account.household_account_id:
            group_key = account.household_account_id
            matched_tracked_account = tracked_by_household_account_id.get(account.household_account_id)
        else:
            evidence_group_key = _evidence_group_key(account)
            evidence_match_key = (
                _normalize_text(account.metadata.get("match_key"))
                if isinstance(account.metadata, dict)
                else ""
            )
            linked_household_account_id = (
                evidence_household_account_id_by_match_key.get(evidence_match_key)
                if evidence_match_key
                else None
            ) or evidence_household_account_id_by_group_key.get(evidence_group_key)
            if linked_household_account_id:
                group_key = linked_household_account_id
                matched_tracked_account = tracked_by_household_account_id.get(linked_household_account_id)
            else:
                matched_tracked_account = _match_tracked_account(
                    group_key=evidence_group_key,
                    label=_account_label(account),
                    account_name=account.account_name,
                    hint_label=document.account_label if document is not None else None,
                    asset_group=account.asset_group,
                    account_type=account.account_type,
                    institution_name=account.institution_name,
                    owner_name=account.owner_name,
                    account_mask=account.account_mask,
                    tracked_accounts=tracked_accounts,
                )
                if (
                    matched_tracked_account is not None
                    and matched_tracked_account.household_account_id
                ):
                    group_key = matched_tracked_account.household_account_id
                else:
                    group_key = (
                        _tracked_summary_key(matched_tracked_account)
                        if matched_tracked_account is not None
                        else evidence_group_key
                    )
        grouped[group_key].append(account)
        if matched_tracked_account is not None:
            grouped_tracked_matches[group_key] = matched_tracked_account

    tracked_portfolio_matches = {
        account.id: _match_portfolio_account(
            household_account_id=account.household_account_id,
            label=_tracked_label(account),
            account_name=_tracked_label(account),
            asset_group=account.asset_group,
            portfolio_accounts=portfolio_accounts,
        )
        for account in tracked_accounts
    }
    linked_portfolio_ids: set[str] = {
        match.id for match in tracked_portfolio_matches.values() if match is not None
    }
    linked_tracked_ids: set[str] = set()
    summaries: list[HouseholdAccountSummary] = []
    duplicate_candidates: defaultdict[tuple[str, str, str, str], list[str]] = defaultdict(list)

    for group_key, accounts in grouped.items():
        latest = max(
            accounts,
            key=lambda account: (
                _latest_evidence_timestamp(account, documents_by_id.get(account.document_id)) or datetime.min.replace(tzinfo=UTC),
                float(account.confidence or 0.0),
            ),
        )
        display_account = _best_display_account(accounts, documents_by_id)
        balance_account = _best_balance_account(accounts, documents_by_id)
        latest_document = documents_by_id.get(latest.document_id)
        display_document = documents_by_id.get(display_account.document_id)
        balance_document = documents_by_id.get(balance_account.document_id)
        closed_zero_balance_account = _is_closed_zero_balance_account(
            balance_account,
            balance_document,
            latest_document,
            display_document,
        )
        account_label = _account_label(display_account)
        money_role = _money_role(display_account.asset_group, display_account.account_type, account_label)
        last_balance_dt = _latest_evidence_timestamp(balance_account, balance_document)
        days_since_balance = (
            (datetime.now(UTC).date() - last_balance_dt.date()).days
            if last_balance_dt is not None
            else None
        )
        balance_freshness_status, balance_freshness_label = _freshness_state_from_thresholds(
            _BALANCE_FRESHNESS_THRESHOLDS,
            display_account.asset_group,
            days_since=days_since_balance,
        )
        if closed_zero_balance_account:
            balance_freshness_status, balance_freshness_label = ("fresh", "Closed")
        hint_label = (
            display_document.account_label
            if display_document is not None and display_document.account_label
            else latest_document.account_label if latest_document is not None else None
        )
        transaction_label_candidates: set[str] = set()
        for account in accounts:
            document = documents_by_id.get(account.document_id)
            for candidate in (
                _account_label(account),
                document.account_label if document is not None else None,
                account.account_name,
                account.institution_name,
                account.account_mask,
            ):
                normalized = _normalize_text(candidate)
                if normalized:
                    transaction_label_candidates.add(normalized)
        last_transaction_dt = _latest_transaction_timestamp(
            [str(account.document_id) for account in accounts if account.document_id],
            household_account_id=display_account.household_account_id,
            label_candidates=transaction_label_candidates,
            account_mask=display_account.account_mask,
            latest_transaction_dates_by_household_account=latest_transaction_dates_by_household_account,
            latest_transaction_dates_by_document=latest_transaction_dates_by_document,
            latest_transaction_dates_by_account_label=latest_transaction_dates_by_account_label,
        )
        transaction_coverage_dt = _latest_transaction_coverage_timestamp(
            accounts,
            latest_transaction_dt=last_transaction_dt,
        )
        days_since_transaction = (
            (datetime.now(UTC).date() - transaction_coverage_dt.date()).days
            if transaction_coverage_dt is not None
            else None
        )
        if money_role == "spend_driver":
            transaction_freshness_status, transaction_freshness_label = (
                _freshness_state_from_thresholds(
                    _TRANSACTION_FRESHNESS_THRESHOLDS,
                    money_role,
                    days_since=days_since_transaction,
                    empty_label="Needs transactions",
                )
            )
        else:
            transaction_freshness_status, transaction_freshness_label = (
                "not_applicable",
                "Not required",
            )
        freshness_status, freshness_label = _combine_freshness(
            money_role=money_role,
            balance_status=balance_freshness_status,
            balance_label=balance_freshness_label,
            transaction_status=transaction_freshness_status,
            transaction_label=transaction_freshness_label,
        )
        tracked_account = grouped_tracked_matches.get(group_key)
        if tracked_account is None and display_account.household_account_id:
            tracked_account = tracked_by_household_account_id.get(display_account.household_account_id)
        if tracked_account is None:
            tracked_account = _match_tracked_account(
                group_key=group_key,
                label=account_label,
                account_name=display_account.account_name,
                hint_label=hint_label,
                asset_group=display_account.asset_group,
                account_type=display_account.account_type,
                institution_name=display_account.institution_name,
                owner_name=display_account.owner_name,
                account_mask=display_account.account_mask,
                tracked_accounts=tracked_accounts,
            )
        if tracked_account is not None:
            linked_tracked_ids.add(tracked_account.id)
        portfolio_account = _match_portfolio_account(
            household_account_id=display_account.household_account_id,
            label=_tracked_label(tracked_account) if tracked_account is not None else _account_label(latest),
            account_name=display_account.account_name,
            asset_group=display_account.asset_group,
            portfolio_accounts=portfolio_accounts,
        )
        portfolio_valuation = (
            account_valuations.get(portfolio_account.id)
            if portfolio_account is not None
            else None
        )
        if portfolio_account is not None:
            linked_portfolio_ids.add(portfolio_account.id)
        linked_group_household_account_id = next(
            (
                candidate.household_account_id
                for candidate in accounts
                if candidate.household_account_id
            ),
            None,
        )
        household_account_id = (
            display_account.household_account_id
            or linked_group_household_account_id
            or (tracked_account.household_account_id if tracked_account is not None else None)
        )
        if household_account_id is None and portfolio_account is not None:
            household_account_id = getattr(portfolio_account, "household_account_id", None)
        source_owned = (
            household_account_id is not None
            and household_account_id in source_owned_household_account_ids
        )
        source_account_value = (
            source_owned_account_values.get(household_account_id)
            if household_account_id is not None
            else None
        )
        effective_asset_group = display_account.asset_group
        effective_label = (
            _portfolio_label(portfolio_account)
            if portfolio_account is not None
            else _tracked_label(tracked_account)
            if tracked_account is not None
            else account_label
        )
        effective_account_type = display_account.account_type
        effective_money_role = _money_role(
            effective_asset_group,
            effective_account_type,
            effective_label,
        )
        if closed_zero_balance_account:
            effective_money_role = "net_worth_only"
        if source_owned and portfolio_account is not None:
            source_balance_dt = _parse_datetime((source_account_value or {}).get("last_synced_at")) or _parse_datetime(getattr(portfolio_account, "updated_at", None))
            if source_balance_dt is not None:
                last_balance_dt = source_balance_dt
                days_since_balance = (datetime.now(UTC).date() - source_balance_dt.date()).days
                balance_freshness_status, balance_freshness_label = _freshness_state_from_thresholds(
                    _BALANCE_FRESHNESS_THRESHOLDS,
                    effective_asset_group,
                    days_since=days_since_balance,
                )
        if effective_money_role == "spend_driver":
            transaction_freshness_status, transaction_freshness_label = (
                _freshness_state_from_thresholds(
                    _TRANSACTION_FRESHNESS_THRESHOLDS,
                    effective_money_role,
                    days_since=days_since_transaction,
                    empty_label="Needs transactions",
                )
            )
        else:
            transaction_freshness_status, transaction_freshness_label = (
                "not_applicable",
                "Not required",
            )
        freshness_status, freshness_label = _combine_freshness(
            money_role=effective_money_role,
            balance_status=balance_freshness_status,
            balance_label=balance_freshness_label,
            transaction_status=transaction_freshness_status,
            transaction_label=transaction_freshness_label,
        )
        match_confidence = _confidence_for_summary(
            display_account,
            evidence_count=len(accounts),
            linked=portfolio_account is not None or tracked_account is not None,
        )
        match_status = "tracked" if match_confidence >= 0.8 else "candidate"
        if portfolio_account is not None or tracked_account is not None:
            match_status = "linked"
        has_live_pricing = bool(
            portfolio_valuation is not None
            and getattr(portfolio_valuation, "priced_position_count", 0) > 0
        )
        source_current_value = _source_account_float(source_account_value, "current_value")
        source_cash_value = _source_account_float(source_account_value, "cash_balance")
        source_account_mask = (
            str(source_account_value.get("account_mask"))
            if source_account_value and source_account_value.get("account_mask")
            else None
        )
        has_source_balance = source_owned and source_current_value is not None
        evidence_current_value = _account_value(balance_account)
        if evidence_current_value is None and closed_zero_balance_account:
            evidence_current_value = 0.0
        live_priced_positions_value = (
            float(getattr(portfolio_valuation, "priced_positions_value", 0.0) or 0.0)
            if has_live_pricing
            else None
        )
        portfolio_effective_cash_balance = (
            float(getattr(portfolio_valuation, "effective_cash_balance", 0.0) or 0.0)
            if portfolio_valuation is not None
            else None
        )
        effective_cash_balance = (
            0.0
            if closed_zero_balance_account
            else source_cash_value
            if source_cash_value is not None
            else portfolio_effective_cash_balance
            if has_source_balance
            else float(balance_account.cash_balance)
            if balance_account.cash_balance is not None
            else portfolio_effective_cash_balance
        )
        source_holdings_value = (
            source_current_value - float(effective_cash_balance or 0.0)
            if has_source_balance
            else None
        )
        effective_holdings_value = (
            source_holdings_value
            if source_holdings_value is not None
            else
            live_priced_positions_value
            if live_priced_positions_value is not None
            else float(balance_account.holdings_value)
            if balance_account.holdings_value is not None
            else None
        )
        effective_current_value = (
            source_current_value
            if has_source_balance
            else live_priced_positions_value + float(effective_cash_balance or 0.0)
            if has_live_pricing and live_priced_positions_value is not None
            else evidence_current_value
        )
        valuation_source = (
            "source_balance"
            if has_source_balance
            else "live_quotes"
            if has_live_pricing
            else "evidence"
        )
        if (
            portfolio_account is None
            and tracked_account is None
            and not source_owned
            and effective_current_value is None
        ):
            continue
        summary = HouseholdAccountSummary(
            id=group_key,
            household_account_id=household_account_id,
            label=effective_label,
            asset_group=effective_asset_group,
            account_type=effective_account_type,
            source_type=display_account.source_type,
            match_key=tracked_account.match_key if tracked_account is not None else group_key,
            institution_name=display_account.institution_name,
            owner_name=tracked_account.owner_name if tracked_account is not None and tracked_account.owner_name is not None else display_account.owner_name,
            account_mask=source_account_mask or display_account.account_mask,
            notes=tracked_account.notes if tracked_account is not None else None,
            currency=balance_account.currency or display_account.currency,
            current_value=effective_current_value,
            balance=balance_account.balance,
            holdings_value=effective_holdings_value,
            cash_balance=effective_cash_balance,
            valuation_source=valuation_source,
            evidence_count=len(accounts),
            document_ids=sorted({account.document_id for account in accounts}),
            latest_document_id=balance_account.document_id if _account_value(balance_account) is not None else latest.document_id,
            source_types=sorted({account.source_type for account in accounts}),
            linked_portfolio_account_id=portfolio_account.id if portfolio_account is not None else None,
            linked_portfolio_account_name=_portfolio_label(portfolio_account) if portfolio_account is not None else None,
            tracked_account_id=tracked_account.id if tracked_account is not None else None,
            account_origin="evidence",
            money_role=effective_money_role,
            last_evidence_at=last_balance_dt.isoformat() if last_balance_dt is not None else None,
            days_since_evidence=days_since_balance,
            last_balance_at=last_balance_dt.isoformat() if last_balance_dt is not None else None,
            days_since_balance=days_since_balance,
            balance_freshness_status=balance_freshness_status,
            balance_freshness_label=balance_freshness_label,
            last_transaction_at=last_transaction_dt.isoformat() if last_transaction_dt is not None else None,
            days_since_transaction=days_since_transaction,
            transaction_freshness_status=transaction_freshness_status,
            transaction_freshness_label=transaction_freshness_label,
            quote_updated_at=(
                portfolio_valuation.quote_updated_at.isoformat()
                if has_live_pricing and getattr(portfolio_valuation, "quote_updated_at", None) is not None
                else None
            ),
            quote_freshness_status=(
                str(getattr(portfolio_valuation, "quote_freshness_status", "not_applicable"))
                if has_live_pricing
                else "not_applicable"
            ),
            quote_freshness_label=(
                str(getattr(portfolio_valuation, "quote_freshness_label", "No live quotes"))
                if has_live_pricing
                else "No live quotes"
            ),
            quote_source=(
                str(getattr(portfolio_valuation, "quote_source", None))
                if has_live_pricing and getattr(portfolio_valuation, "quote_source", None)
                else None
            ),
            priced_position_count=(
                int(getattr(portfolio_valuation, "priced_position_count", 0))
                if has_live_pricing
                else 0
            ),
            freshness_status=freshness_status,
            freshness_label=freshness_label,
            match_status=match_status,
            match_confidence=match_confidence,
        )
        summaries.append(summary)
        duplicate_key = (
            _normalize_text(summary.institution_name),
            summary.asset_group,
            _normalize_text(summary.owner_name),
            _duplicate_label_key(summary.label),
        )
        if duplicate_key[0] and duplicate_key[3] and latest.account_mask is None:
            duplicate_candidates[duplicate_key].append(summary.id)

    for account in portfolio_accounts:
        if getattr(account, "account_type", None) == "paper" or account.id in linked_portfolio_ids:
            continue
        portfolio_valuation = account_valuations.get(account.id)
        portfolio_household_account_id = getattr(account, "household_account_id", None)
        source_owned = (
            portfolio_household_account_id is not None
            and str(portfolio_household_account_id) in source_owned_household_account_ids
        )
        source_account_value = (
            source_owned_account_values.get(str(portfolio_household_account_id))
            if portfolio_household_account_id is not None
            else None
        )
        source_balance_dt = (
            _parse_datetime((source_account_value or {}).get("last_synced_at"))
            or _parse_datetime(getattr(account, "updated_at", None))
            if source_owned
            else None
        )
        days_since_source_balance = (
            (datetime.now(UTC).date() - source_balance_dt.date()).days
            if source_balance_dt is not None
            else None
        )
        balance_status, balance_label = (
            _freshness_state_from_thresholds(
                _BALANCE_FRESHNESS_THRESHOLDS,
                _portfolio_asset_group(account),
                days_since=days_since_source_balance,
            )
            if source_owned
            else ("needs_evidence", "Needs evidence")
        )
        source_current_value = _source_account_float(source_account_value, "current_value")
        source_cash_value = _source_account_float(source_account_value, "cash_balance")
        portfolio_current_value = (
            float(getattr(portfolio_valuation, "total_value", 0.0) or 0.0)
            if portfolio_valuation is not None
            else _portfolio_value(account, holdings_by_account)
        )
        portfolio_cash_balance = (
            float(getattr(portfolio_valuation, "effective_cash_balance", 0.0) or 0.0)
            if portfolio_valuation is not None
            else float(getattr(account, "cash_balance", 0.0) or 0.0)
        )
        effective_current_value = source_current_value if source_current_value is not None else portfolio_current_value
        effective_cash_balance = source_cash_value if source_cash_value is not None else portfolio_cash_balance
        summaries.append(
            HouseholdAccountSummary(
                id=_portfolio_summary_key(account),
                household_account_id=getattr(account, "household_account_id", None),
                label=_portfolio_label(account),
                asset_group=_portfolio_asset_group(account),
                account_type=str(account.account_type),
                source_type=_portfolio_source_type(account),
                match_key=None,
                current_value=effective_current_value,
                holdings_value=(
                    effective_current_value - effective_cash_balance
                    if source_current_value is not None
                    else
                    float(getattr(portfolio_valuation, "priced_positions_value", 0.0) or 0.0)
                    if portfolio_valuation is not None
                    else holdings_by_account.get(account.id, 0.0)
                ),
                cash_balance=effective_cash_balance,
                valuation_source=(
                    "live_quotes"
                    if portfolio_valuation is not None
                    and getattr(portfolio_valuation, "priced_position_count", 0) > 0
                    else "source_balance"
                    if source_owned
                    else "portfolio_cash"
                ),
                latest_document_id=None,
                linked_portfolio_account_id=account.id,
                linked_portfolio_account_name=_portfolio_label(account),
                account_origin="portfolio",
                money_role=_money_role(
                    _portfolio_asset_group(account),
                    str(account.account_type),
                    _portfolio_label(account),
                ),
                last_balance_at=source_balance_dt.isoformat() if source_balance_dt is not None else None,
                days_since_balance=days_since_source_balance,
                balance_freshness_status=balance_status,
                balance_freshness_label=balance_label,
                last_transaction_at=None,
                days_since_transaction=None,
                transaction_freshness_status="not_applicable",
                transaction_freshness_label="Not required",
                quote_updated_at=(
                    portfolio_valuation.quote_updated_at.isoformat()
                    if portfolio_valuation is not None
                    and getattr(portfolio_valuation, "quote_updated_at", None) is not None
                    else None
                ),
                quote_freshness_status=(
                    str(getattr(portfolio_valuation, "quote_freshness_status", "not_applicable"))
                    if portfolio_valuation is not None
                    else "not_applicable"
                ),
                quote_freshness_label=(
                    str(getattr(portfolio_valuation, "quote_freshness_label", "No live quotes"))
                    if portfolio_valuation is not None
                    else "No live quotes"
                ),
                quote_source=(
                    str(getattr(portfolio_valuation, "quote_source", None))
                    if portfolio_valuation is not None
                    and getattr(portfolio_valuation, "quote_source", None)
                    else None
                ),
                priced_position_count=(
                    int(getattr(portfolio_valuation, "priced_position_count", 0))
                    if portfolio_valuation is not None
                    else 0
                ),
                freshness_status=balance_status,
                freshness_label=balance_label,
                match_status="tracked",
                match_confidence=None,
            )
        )

    for account in tracked_accounts:
        if account.id in linked_tracked_ids:
            continue
        portfolio_account = tracked_portfolio_matches.get(account.id)
        summaries.append(
            HouseholdAccountSummary(
                id=_tracked_summary_key(account),
                household_account_id=account.household_account_id,
                label=_tracked_label(account),
                asset_group=account.asset_group,
                account_type=account.account_type,
                source_type=account.source_type,
                match_key=account.match_key,
                institution_name=account.institution_name,
                owner_name=account.owner_name,
                account_mask=account.account_mask,
                notes=account.notes,
                latest_document_id=None,
                linked_portfolio_account_id=portfolio_account.id if portfolio_account is not None else None,
                linked_portfolio_account_name=_portfolio_label(portfolio_account) if portfolio_account is not None else None,
                tracked_account_id=account.id,
                account_origin="tracked",
                money_role=_money_role(account.asset_group, account.account_type, account.label),
                last_balance_at=None,
                days_since_balance=None,
                balance_freshness_status="needs_evidence",
                balance_freshness_label="Needs evidence",
                last_transaction_at=None,
                days_since_transaction=None,
                transaction_freshness_status=(
                    "needs_evidence" if _money_role(account.asset_group, account.account_type, account.label) == "spend_driver" else "not_applicable"
                ),
                transaction_freshness_label=(
                    "Needs transactions" if _money_role(account.asset_group, account.account_type, account.label) == "spend_driver" else "Not required"
                ),
                freshness_status="needs_evidence",
                freshness_label="Needs evidence",
                match_status="tracked",
                match_confidence=None,
            )
        )

    duplicate_ids = {
        summary_id
        for ids in duplicate_candidates.values()
        if len(ids) > 1
        for summary_id in ids
    }

    finalized: list[HouseholdAccountSummary] = []
    for summary in summaries:
        latest_document = documents_by_id.get(summary.latest_document_id) if summary.latest_document_id else None
        finalized.append(
            summary.model_copy(
                update={
                    "gap_flags": _build_account_gaps(
                        summary=summary,
                        latest_document=latest_document,
                        statement_freshness=statement_freshness,
                        duplicate=summary.id in duplicate_ids,
                    )
                }
            )
        )

    return sorted(
        finalized,
        key=lambda summary: (
            _PRIORITY_ORDER[
                _SEVERITY_PRIORITY.get(_top_gap(summary.gap_flags).severity, "low")
                if _top_gap(summary.gap_flags) is not None
                else "low"
            ],
            0 if summary.match_status == "candidate" else 1,
            -(summary.current_value or 0.0),
            summary.label.lower(),
        ),
    )


def build_money_inbox(
    *,
    accounts: list[HouseholdAccountSummary],
    discovered_accounts: list[HouseholdDiscoveredAccount] | None = None,
    questions: list[Any],
    tracked_documents: int,
    parsed_documents: int,
    statement_freshness: dict[str, Any],
) -> list[HouseholdInboxItem]:
    discovered_accounts = discovered_accounts or []
    items: list[HouseholdInboxItem] = []
    if tracked_documents == 0:
        items.append(
            HouseholdInboxItem(
                id="intake-upload-evidence",
                category="intake",
                priority="high",
                title="Upload financial evidence",
                detail="Drop in bank, card, brokerage, retirement, payroll, or bill evidence so Jenny can build the account map and money story.",
                action_label="Open intake",
                action_href=MONEY_EVIDENCE_ROUTE,
            )
        )
    elif parsed_documents == 0:
        items.append(
            HouseholdInboxItem(
                id="intake-processing",
                category="intake",
                priority="high",
                title="Finish evidence processing",
                detail="Documents are present, but Jenny still needs at least one parsed financial file before the money system is trustworthy.",
                action_label="Review intake",
                action_href=MONEY_EVIDENCE_ROUTE,
            )
        )

    if tracked_documents > 0 and int(statement_freshness.get("coverage_months") or 0) == 0:
        items.append(
            HouseholdInboxItem(
                id="cashflow-missing-ledger",
                category="coverage",
                priority="high",
                title="Add transaction-bearing account history",
                detail="Jenny still does not have enough bank or card activity to build a usable spending ledger.",
                action_label="Upload statements",
                action_href=MONEY_EVIDENCE_ROUTE,
            )
        )

    future_transaction_count = int(statement_freshness.get("future_transaction_count") or 0)
    if future_transaction_count > 0:
        latest_future_date = statement_freshness.get("latest_future_date")
        items.append(
            HouseholdInboxItem(
                id="cashflow-future-transaction-dates",
                category="intake",
                priority="high",
                title="Review future-dated transactions",
                detail=(
                    f"{future_transaction_count} transaction{'s' if future_transaction_count != 1 else ''}"
                    f"{f' through {latest_future_date}' if latest_future_date else ''} "
                    "are held out of current spending calculations until the evidence date is corrected."
                ),
                action_label="Review dates",
                action_href=MONEY_DATE_QUALITY_ROUTE,
            )
        )

    gap_months = statement_freshness.get("gap_months")
    if isinstance(gap_months, list) and gap_months:
        items.append(
            HouseholdInboxItem(
                id="cashflow-gap-months",
                category="coverage",
                priority="medium",
                title="Close transaction history gaps",
                detail=(
                    f"{gap_months[0]}. Upload the missing statement or export month so month-over-month and budget pacing stop drifting."
                ),
                action_label="Review accounts",
                action_href=MONEY_ACCOUNTS_ROUTE,
            )
        )

    for question in questions:
        if getattr(question, "answered_at", None):
            continue
        items.append(
            HouseholdInboxItem(
                id=f"question-{question.id}",
                category="question",
                priority=str(getattr(question, "priority", "medium") or "medium"),
                title=str(question.question),
                detail=str(getattr(question, "recommendation", None) or getattr(question, "rationale", None) or "Answering this lets Jenny keep the model aligned with reality."),
                action_label="Answer",
                action_href=money_question_focus_route(str(question.id)),
                related_question_id=question.id,
                related_document_ids=[str(question.source_document_id)] if getattr(question, "source_document_id", None) else [],
            )
        )

    for account in accounts:
        top_gap = _top_gap(account.gap_flags)
        if top_gap is None or top_gap.severity == "low":
            continue
        action_href = MONEY_ACCOUNTS_ROUTE
        action_label = "Review account"
        title = f"Review {account.label}"
        if top_gap.code in {
            "missing_evidence",
            "missing_current_state",
            "refresh_balance_soon",
            "stale_balance",
            "refresh_soon",
            "stale_evidence",
            "incomplete_application",
        }:
            action_href = MONEY_EVIDENCE_ROUTE
            action_label = "Add evidence"
            title = (
                f"Refresh {account.label}"
                if top_gap.code in {
                    "refresh_balance_soon",
                    "refresh_soon",
                    "stale_balance",
                    "stale_evidence",
                }
                else f"Add evidence for {account.label}"
            )
            action_href = money_account_focus_route(account.id, intent="evidence")
        elif top_gap.code in {
            "refresh_transactions_soon",
            "stale_transactions",
            "missing_transaction_history",
            "statement_gap",
        }:
            action_href = MONEY_EVIDENCE_ROUTE
            action_label = "Add statements"
            title = (
                f"Refresh transactions for {account.label}"
                if top_gap.code in {"refresh_transactions_soon", "stale_transactions"}
                else f"Add statements for {account.label}"
            )
            action_href = money_account_focus_route(account.id, intent="evidence")
        elif top_gap.code == "unconfirmed_match":
            action_label = "Confirm account"
            title = f"Confirm {account.label}"
            action_href = money_account_focus_route(account.id)
        detail = _account_request_detail(account, top_gap.code) or top_gap.detail
        items.append(
            HouseholdInboxItem(
                id=f"account-{account.id}-{top_gap.code}",
                category="account",
                priority=_SEVERITY_PRIORITY[top_gap.severity],
                title=title,
                detail=detail,
                action_label=action_label,
                action_href=action_href,
                related_account_id=account.id,
                related_document_ids=account.document_ids,
            )
        )

    for discovered in discovered_accounts[:4]:
        items.append(
            HouseholdInboxItem(
                id=f"discovered-{discovered.key}",
                category="account",
                priority="medium",
                title=f"Confirm possible account: {discovered.suggested_label}",
                detail=discovered.detail,
                action_label="Review accounts",
                action_href=MONEY_DISCOVERED_ACCOUNTS_ROUTE,
            )
        )

    deduped: dict[str, HouseholdInboxItem] = {}
    for item in items:
        dedupe_key = "|".join(
            str(part or "")
            for part in (item.category, item.title, item.related_account_id, item.related_question_id)
        )
        current = deduped.get(dedupe_key)
        if current is None or _PRIORITY_ORDER[item.priority] < _PRIORITY_ORDER[current.priority]:
            deduped[dedupe_key] = item

    return sorted(
        deduped.values(),
        key=lambda item: (
            _PRIORITY_ORDER.get(item.priority, _PRIORITY_ORDER["low"]),
            _INBOX_CATEGORY_ORDER.get(item.category, len(_INBOX_CATEGORY_ORDER)),
            item.title.lower(),
        ),
    )[:12]
