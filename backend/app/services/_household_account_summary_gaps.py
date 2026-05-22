"""Gap and request-detail builders for household account summaries."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.models.household_finance import (
    HouseholdAccountGap,
    HouseholdAccountSummary,
    HouseholdDocument,
)
from app.services._household_account_summary_utils import (
    _join_with_and,
    _parse_datetime,
)

_PRIORITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_SEVERITY_PRIORITY: dict[str, str] = {"high": "high", "medium": "medium", "low": "low"}


# ---------------------------------------------------------------------------
# Gap primitives
# ---------------------------------------------------------------------------


def _gap(code: str, severity: str, title: str, detail: str) -> HouseholdAccountGap:
    return HouseholdAccountGap(code=code, severity=severity, title=title, detail=detail)


def _top_gap(gaps: list[HouseholdAccountGap]) -> HouseholdAccountGap | None:
    if not gaps:
        return None
    return sorted(gaps, key=lambda gap: (_PRIORITY_ORDER[_SEVERITY_PRIORITY[gap.severity]], gap.title))[0]


# ---------------------------------------------------------------------------
# Document-level flags
# ---------------------------------------------------------------------------


def _document_issue_flags(document: HouseholdDocument | None) -> list[HouseholdAccountGap]:
    if document is None:
        return []
    metadata = document.metadata if isinstance(document.metadata, dict) else {}
    gaps: list[HouseholdAccountGap] = []
    if metadata.get("file_available") is False:
        gaps.append(
            _gap(
                "source_missing",
                "medium",
                "Source file unavailable",
                "The original file is missing, so Jenny is relying on stored review output instead of the source file.",
            )
        )
    application_summary = metadata.get("application_summary")
    application = application_summary if isinstance(application_summary, dict) else {}
    if application.get("status") == "incomplete":
        gaps.append(
            _gap(
                "incomplete_application",
                "high",
                "Incomplete ingestion",
                "Jenny reviewed this document, but it did not safely produce a full account update yet.",
            )
        )
    return gaps


# ---------------------------------------------------------------------------
# Freshness and coverage gaps
# ---------------------------------------------------------------------------


def _freshness_gaps(summary: HouseholdAccountSummary) -> list[HouseholdAccountGap]:
    gaps: list[HouseholdAccountGap] = []
    if summary.current_value is None:
        gaps.append(
            _gap(
                "missing_balance",
                "high",
                "Missing balance",
                "Jenny could not extract a usable balance, holdings value, or cash balance for this account.",
            )
        )
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
    missing_linked_transactions = (
        summary.balance_freshness_status == "fresh"
        and summary.transaction_freshness_status == "not_applicable"
    )
    if needs_transactions or missing_linked_transactions:
        detail = (
            "Jenny has some account evidence here but not enough linked transaction history to trust cash-flow calculations."
            if needs_transactions
            else "Jenny can see this account but cannot yet tie it to recent transaction history."
        )
        gaps.append(_gap("missing_transaction_history", "high", "Missing transaction history", detail))
    return gaps


def _coverage_gaps(
    summary: HouseholdAccountSummary,
    existing_gap_codes: set[str],
) -> list[HouseholdAccountGap]:
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


# ---------------------------------------------------------------------------
# Request detail text
# ---------------------------------------------------------------------------


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


def _transaction_request_detail(
    gap_code: str,
    today: date,
    last_transaction: datetime | None,
    block_suffix: str,
) -> str | None:
    """Detail text for transaction-related gap codes."""
    if gap_code not in {"refresh_transactions_soon", "stale_transactions", "missing_transaction_history"}:
        return None
    if gap_code == "missing_transaction_history":
        start = (today - timedelta(days=30)).isoformat()
        return (
            f"Need a statement or export covering at least {start} through {today.isoformat()} so Jenny can trust cash-flow."
            f"{block_suffix}"
        )
    prior_date = last_transaction.date() if last_transaction is not None else None
    start = (prior_date + timedelta(days=1)) if prior_date is not None else today - timedelta(days=30)
    return (
        f"Need a bank or card statement/export covering {start.isoformat()} through {today.isoformat()}."
        f"{block_suffix}"
    )


def _balance_request_detail(
    gap_code: str,
    today: date,
    last_balance: datetime | None,
    money_role: str,
    block_suffix: str,
) -> str | None:
    """Detail text for balance-related gap codes."""
    refresh_codes = {"refresh_balance_soon", "stale_balance", "refresh_soon", "stale_evidence"}
    missing_codes = {"missing_evidence", "missing_current_state", "incomplete_application", "missing_balance"}
    if gap_code not in refresh_codes and gap_code not in missing_codes and gap_code != "statement_gap":
        return None
    if gap_code == "statement_gap":
        return f"Need the missing statement month(s) uploaded to close known ledger gaps.{block_suffix}"
    if gap_code in refresh_codes:
        if last_balance is not None:
            return (
                f"Need a newer balance statement, screenshot, or export after {last_balance.date().isoformat()}."
                f"{block_suffix}"
            )
        return f"Need current balance evidence as of {today.isoformat()}.{block_suffix}"
    if money_role == "spend_driver":
        start = (today - timedelta(days=30)).isoformat()
        return (
            f"Need the latest statement or export covering {start} through {today.isoformat()}."
            f"{block_suffix}"
        )
    return f"Need a current statement, screenshot, or export as of {today.isoformat()}.{block_suffix}"


def _account_request_detail(account: HouseholdAccountSummary, gap_code: str) -> str | None:
    today = datetime.now(UTC).date()
    last_balance = _parse_datetime(account.last_balance_at)
    last_transaction = _parse_datetime(account.last_transaction_at)
    blocks = _account_blocked_metrics(account, gap_code)
    block_suffix = f" Blocks {_join_with_and(blocks)}." if blocks else ""
    return (
        _transaction_request_detail(gap_code, today, last_transaction, block_suffix)
        or _balance_request_detail(gap_code, today, last_balance, account.money_role, block_suffix)
    )
