"""Inbox item builder for household account summaries."""

from __future__ import annotations

from typing import Any

from app.models.household_finance import (
    HouseholdAccountSummary,
    HouseholdDiscoveredAccount,
    HouseholdInboxItem,
)
from app.services._household_account_summary_gaps import (
    _PRIORITY_ORDER,
    _SEVERITY_PRIORITY,
    _account_blocked_metrics,
    _account_request_detail,
    _top_gap,
)
from app.services._money_workspace_routes import (
    MONEY_ACCOUNTS_ROUTE,
    MONEY_DATE_QUALITY_ROUTE,
    MONEY_DISCOVERED_ACCOUNTS_ROUTE,
    MONEY_EVIDENCE_ROUTE,
    money_account_focus_route,
    money_question_focus_route,
)

_INBOX_CATEGORY_ORDER: dict[str, int] = {"intake": 0, "coverage": 1, "question": 2, "account": 3}


# ---------------------------------------------------------------------------
# Intake / coverage / question items
# ---------------------------------------------------------------------------


def _document_state_items(
    tracked_documents: int,
    parsed_documents: int,
) -> list[HouseholdInboxItem]:
    """Intake items for document upload/processing state."""
    if tracked_documents == 0:
        return [HouseholdInboxItem(
            id="intake-upload-evidence",
            category="intake",
            priority="high",
            title="Upload financial evidence",
            detail="Drop in bank, card, brokerage, retirement, payroll, or bill evidence so Jenny can build the account map and money story.",
            action_label="Open intake",
            action_href=MONEY_EVIDENCE_ROUTE,
        )]
    if parsed_documents == 0:
        return [HouseholdInboxItem(
            id="intake-processing",
            category="intake",
            priority="high",
            title="Finish evidence processing",
            detail="Documents are present, but Jenny still needs at least one parsed financial file before the money system is trustworthy.",
            action_label="Review intake",
            action_href=MONEY_EVIDENCE_ROUTE,
        )]
    return []


def _cashflow_coverage_items(
    tracked_documents: int,
    statement_freshness: dict[str, Any],
) -> list[HouseholdInboxItem]:
    """Coverage and data-quality items derived from statement freshness."""
    items: list[HouseholdInboxItem] = []
    if tracked_documents > 0 and int(statement_freshness.get("coverage_months") or 0) == 0:
        items.append(HouseholdInboxItem(
            id="cashflow-missing-ledger",
            category="coverage",
            priority="high",
            title="Add transaction-bearing account history",
            detail="Jenny still does not have enough bank or card activity to build a usable spending ledger.",
            action_label="Upload statements",
            action_href=MONEY_EVIDENCE_ROUTE,
        ))
    future_count = int(statement_freshness.get("future_transaction_count") or 0)
    if future_count > 0:
        latest_future_date = statement_freshness.get("latest_future_date")
        items.append(HouseholdInboxItem(
            id="cashflow-future-transaction-dates",
            category="intake",
            priority="high",
            title="Review future-dated transactions",
            detail=(
                f"{future_count} transaction{'s' if future_count != 1 else ''}"
                f"{f' through {latest_future_date}' if latest_future_date else ''} "
                "are held out of current spending calculations until the evidence date is corrected."
            ),
            action_label="Review dates",
            action_href=MONEY_DATE_QUALITY_ROUTE,
        ))
    gap_months = statement_freshness.get("gap_months")
    if isinstance(gap_months, list) and gap_months:
        items.append(HouseholdInboxItem(
            id="cashflow-gap-months",
            category="coverage",
            priority="medium",
            title="Close transaction history gaps",
            detail=f"{gap_months[0]}. Upload the missing statement or export month so month-over-month and budget pacing stop drifting.",
            action_label="Review accounts",
            action_href=MONEY_ACCOUNTS_ROUTE,
            affects=["safe_to_spend", "budget_status", "monthly_spend"],
        ))
    return items


def _intake_items(
    tracked_documents: int,
    parsed_documents: int,
    statement_freshness: dict[str, Any],
) -> list[HouseholdInboxItem]:
    return [
        *_document_state_items(tracked_documents, parsed_documents),
        *_cashflow_coverage_items(tracked_documents, statement_freshness),
    ]


def _question_items(questions: list[Any]) -> list[HouseholdInboxItem]:
    items: list[HouseholdInboxItem] = []
    for question in questions:
        if getattr(question, "answered_at", None):
            continue
        items.append(
            HouseholdInboxItem(
                id=f"question-{question.id}",
                category="question",
                priority=str(getattr(question, "priority", "medium") or "medium"),
                title=str(question.question),
                detail=str(
                    getattr(question, "recommendation", None)
                    or getattr(question, "rationale", None)
                    or "Answering this lets Jenny keep the model aligned with reality."
                ),
                action_label="Answer",
                action_href=money_question_focus_route(str(question.id)),
                related_question_id=question.id,
                related_document_ids=[str(question.source_document_id)] if getattr(question, "source_document_id", None) else [],
            )
        )
    return items


# ---------------------------------------------------------------------------
# Account-level inbox items
# ---------------------------------------------------------------------------


_EVIDENCE_CODES = {
    "missing_evidence",
    "missing_current_state",
    "refresh_balance_soon",
    "stale_balance",
    "refresh_soon",
    "stale_evidence",
    "incomplete_application",
}
_REFRESH_CODES = {"refresh_balance_soon", "refresh_soon", "stale_balance", "stale_evidence"}
_TRANSACTION_CODES = {
    "refresh_transactions_soon",
    "stale_transactions",
    "missing_transaction_history",
    "statement_gap",
}


def _account_gap_action(
    account: HouseholdAccountSummary,
    gap_code: str,
) -> tuple[str, str, str]:
    """Return (title, action_label, action_href) for a gap code."""
    if gap_code in _EVIDENCE_CODES:
        title = (
            f"Refresh {account.label}"
            if gap_code in _REFRESH_CODES
            else f"Add evidence for {account.label}"
        )
        return title, "Add evidence", money_account_focus_route(account.id, intent="evidence")
    if gap_code in _TRANSACTION_CODES:
        title = (
            f"Refresh transactions for {account.label}"
            if gap_code in {"refresh_transactions_soon", "stale_transactions"}
            else f"Add statements for {account.label}"
        )
        return title, "Add statements", money_account_focus_route(account.id, intent="evidence")
    if gap_code == "unconfirmed_match":
        return f"Confirm {account.label}", "Confirm account", money_account_focus_route(account.id)
    return f"Review {account.label}", "Review account", MONEY_ACCOUNTS_ROUTE


def _account_item_for_gap(
    account: HouseholdAccountSummary,
    top_gap_code: str,
    top_gap_severity: str,
    top_gap_detail: str,
) -> HouseholdInboxItem:
    title, action_label, action_href = _account_gap_action(account, top_gap_code)
    detail = _account_request_detail(account, top_gap_code) or top_gap_detail
    affects = [
        block.replace(" ", "_")
        for block in _account_blocked_metrics(account, top_gap_code)
    ]
    return HouseholdInboxItem(
        id=f"account-{account.id}-{top_gap_code}",
        category="account",
        priority=_SEVERITY_PRIORITY[top_gap_severity],
        title=title,
        detail=detail,
        action_label=action_label,
        action_href=action_href,
        related_account_id=account.id,
        related_document_ids=account.document_ids,
        affects=affects,
    )


def _account_items(accounts: list[HouseholdAccountSummary]) -> list[HouseholdInboxItem]:
    items: list[HouseholdInboxItem] = []
    for account in accounts:
        top_gap = _top_gap(account.gap_flags)
        if top_gap is None or top_gap.severity == "low":
            continue
        items.append(
            _account_item_for_gap(account, top_gap.code, top_gap.severity, top_gap.detail)
        )
    return items


def _discovered_items(discovered_accounts: list[HouseholdDiscoveredAccount]) -> list[HouseholdInboxItem]:
    return [
        HouseholdInboxItem(
            id=f"discovered-{discovered.key}",
            category="account",
            priority="medium",
            title=f"Confirm possible account: {discovered.suggested_label}",
            detail=discovered.detail,
            action_label="Review accounts",
            action_href=MONEY_DISCOVERED_ACCOUNTS_ROUTE,
        )
        for discovered in discovered_accounts[:4]
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_money_inbox(
    *,
    accounts: list[HouseholdAccountSummary],
    discovered_accounts: list[HouseholdDiscoveredAccount] | None = None,
    questions: list[Any],
    tracked_documents: int,
    parsed_documents: int,
    statement_freshness: dict[str, Any],
) -> list[HouseholdInboxItem]:
    all_items = [
        *_intake_items(tracked_documents, parsed_documents, statement_freshness),
        *_question_items(questions),
        *_account_items(accounts),
        *_discovered_items(discovered_accounts or []),
    ]

    deduped: dict[str, HouseholdInboxItem] = {}
    for item in all_items:
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
