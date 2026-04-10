"""Canonical household account summaries and inbox derivation."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdAccountGap,
    HouseholdAccountSummary,
    HouseholdDocument,
    HouseholdEvidenceAccount,
    HouseholdInboxItem,
    HouseholdTrackedAccount,
)
from app.services._money_workspace_routes import (
    MONEY_ACCOUNTS_ROUTE,
    MONEY_CLARIFICATIONS_ROUTE,
    MONEY_DATE_QUALITY_ROUTE,
    MONEY_EVIDENCE_ROUTE,
)

_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_SEVERITY_PRIORITY = {"high": "high", "medium": "medium", "low": "low"}
_INBOX_CATEGORY_ORDER = {"intake": 0, "coverage": 1, "question": 2, "account": 3}
_FRESHNESS_THRESHOLDS = {
    "cash": (45, 90),
    "credit": (45, 90),
    "debt": (45, 90),
    "taxable": (60, 120),
    "retirement": (60, 120),
    "education": (60, 120),
    "other": (90, 180),
}
_PORTFOLIO_ACCOUNT_GROUPS = {
    "401k": "retirement",
    "HSA": "retirement",
    "IRA": "retirement",
    "Roth": "retirement",
    "Taxable": "taxable",
}


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _compact_key(*parts: object) -> str:
    return "|".join(_normalize_text(part) for part in parts if _normalize_text(part))


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
    if account.institution_name and account.account_name:
        return f"{account.institution_name} · {account.account_name}"
    if account.account_name:
        return account.account_name
    if account.institution_name:
        if account.account_mask:
            return f"{account.institution_name} · …{account.account_mask}"
        return account.institution_name
    return account.account_type.replace("_", " ").title()


def _evidence_group_key(account: HouseholdEvidenceAccount) -> str:
    institution = _normalize_text(account.institution_name)
    name = _normalize_text(account.account_name)
    mask = _normalize_text(account.account_mask)
    account_type = _normalize_text(account.account_type)
    asset_group = _normalize_text(account.asset_group)
    source_type = _normalize_text(account.source_type)
    if institution and mask:
        return _compact_key("evidence", institution, mask, source_type or asset_group)
    if institution and name:
        return _compact_key("evidence", institution, name, account_type or asset_group)
    if name and mask:
        return _compact_key("evidence", name, mask, account_type or asset_group)
    if name:
        return _compact_key("evidence", name, account_type or asset_group, source_type)
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
    asset_group = _portfolio_asset_group(account)
    if asset_group == "retirement":
        return "retirement"
    if asset_group == "taxable":
        return "brokerage"
    return "portfolio"


def _freshness_state(asset_group: str, *, days_since: int | None) -> tuple[str, str]:
    if days_since is None:
        return "needs_evidence", "Needs evidence"
    fresh_days, aging_days = _FRESHNESS_THRESHOLDS.get(asset_group, _FRESHNESS_THRESHOLDS["other"])
    if days_since <= fresh_days:
        return "fresh", "Fresh"
    if days_since <= aging_days:
        return "aging", "Refresh soon"
    return "stale", "Stale"


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
    label: str,
    asset_group: str,
    portfolio_accounts: list[Any],
) -> Any | None:
    normalized_label = _normalize_text(label)
    if not normalized_label:
        return None
    matches = [
        account
        for account in portfolio_accounts
        if _portfolio_asset_group(account) == asset_group
        and _normalize_text(_portfolio_label(account)) == normalized_label
    ]
    return matches[0] if len(matches) == 1 else None


def _match_tracked_account(
    *,
    label: str,
    hint_label: str | None,
    asset_group: str,
    institution_name: str | None,
    account_mask: str | None,
    tracked_accounts: list[HouseholdTrackedAccount],
) -> HouseholdTrackedAccount | None:
    normalized_asset_group = _normalize_text(asset_group)
    label_candidates = {
        _normalize_text(candidate)
        for candidate in (label, hint_label)
        if _normalize_text(candidate)
    }
    evidence_signature = (
        _compact_key(institution_name, account_mask)
        if institution_name and account_mask
        else ""
    )
    ranked: list[tuple[int, HouseholdTrackedAccount]] = []
    for account in tracked_accounts:
        if _normalize_text(account.asset_group) != normalized_asset_group:
            continue
        score = 0
        if _normalize_text(account.label) in label_candidates:
            score = 3
        elif (
            evidence_signature
            and account.institution_name
            and account.account_mask
            and _compact_key(account.institution_name, account.account_mask)
            == evidence_signature
        ):
            score = 2
        elif (
            hint_label
            and account.institution_name
            and _normalize_text(account.institution_name)
            == _normalize_text(institution_name)
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


def _build_account_gaps(
    *,
    summary: HouseholdAccountSummary,
    latest_document: HouseholdDocument | None,
    statement_freshness: dict[str, Any],
    duplicate: bool,
) -> list[HouseholdAccountGap]:
    gaps = list(_document_issue_flags(latest_document))
    if summary.current_value is None:
        gaps.append(
            HouseholdAccountGap(
                code="missing_balance",
                severity="high",
                title="Missing balance",
                detail="Jenny could not extract a usable balance, holdings value, or cash balance for this account.",
            )
        )
    if summary.freshness_status == "aging":
        gaps.append(
            HouseholdAccountGap(
                code="refresh_soon",
                severity="medium",
                title="Refresh soon",
                detail="This account is getting stale. Upload newer evidence before Jenny relies on it for recommendations.",
            )
        )
    if summary.freshness_status == "stale":
        gaps.append(
            HouseholdAccountGap(
                code="stale_evidence",
                severity="high",
                title="Stale evidence",
                detail="This account has not been refreshed recently enough to trust it as current state.",
            )
        )
    if summary.freshness_status == "needs_evidence":
        gaps.append(
            HouseholdAccountGap(
                code="missing_evidence",
                severity="high",
                title="Needs evidence",
                detail="The account exists in the system, but Jenny does not have supporting financial evidence for it yet.",
            )
        )
    if summary.match_status == "candidate":
        gaps.append(
            HouseholdAccountGap(
                code="unconfirmed_match",
                severity="medium",
                title="Needs confirmation",
                detail="Jenny found a possible account/entity here, but the match is not strong enough to treat it as fully confirmed.",
            )
        )
    if summary.evidence_count == 1 and summary.last_evidence_at is not None:
        gaps.append(
            HouseholdAccountGap(
                code="thin_evidence",
                severity="low",
                title="Thin evidence",
                detail="This account is backed by a single document so far. More evidence will make the state more trustworthy.",
            )
        )
    if duplicate:
        gaps.append(
            HouseholdAccountGap(
                code="possible_duplicate",
                severity="medium",
                title="Possible duplicate",
                detail="Jenny sees another similar account and is keeping them separate until the identity is clearer.",
            )
        )
    if (
        statement_freshness.get("gap_months")
        and summary.asset_group in {"cash", "credit", "debt"}
    ):
        gaps.append(
            HouseholdAccountGap(
                code="statement_gap",
                severity="medium",
                title="Statement coverage gap",
                detail="Jenny detected a gap in transaction-month coverage, so cash-flow conclusions may still be incomplete.",
            )
        )
    return sorted(gaps, key=lambda gap: (_PRIORITY_ORDER[_SEVERITY_PRIORITY[gap.severity]], gap.title))


def build_account_summaries(
    *,
    evidence_accounts: list[HouseholdEvidenceAccount],
    documents: list[HouseholdDocument],
    portfolio_accounts: list[Any],
    tracked_accounts: list[HouseholdTrackedAccount],
    holdings_by_account: dict[str, float],
    statement_freshness: dict[str, Any],
) -> list[HouseholdAccountSummary]:
    documents_by_id = {document.id: document for document in documents}
    grouped: dict[str, list[HouseholdEvidenceAccount]] = defaultdict(list)
    for account in evidence_accounts:
        grouped[_evidence_group_key(account)].append(account)

    tracked_portfolio_matches = {
        account.id: _match_portfolio_account(
            label=_tracked_label(account),
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
    duplicate_candidates: defaultdict[tuple[str, str], list[str]] = defaultdict(list)

    for group_key, accounts in grouped.items():
        latest = max(
            accounts,
            key=lambda account: (
                _latest_evidence_timestamp(account, documents_by_id.get(account.document_id)) or datetime.min.replace(tzinfo=UTC),
                float(account.confidence or 0.0),
            ),
        )
        latest_document = documents_by_id.get(latest.document_id)
        last_dt = _latest_evidence_timestamp(latest, latest_document)
        days_since = (datetime.now(UTC).date() - last_dt.date()).days if last_dt is not None else None
        tracked_account = _match_tracked_account(
            label=_account_label(latest),
            hint_label=latest_document.account_label if latest_document is not None else None,
            asset_group=latest.asset_group,
            institution_name=latest.institution_name,
            account_mask=latest.account_mask,
            tracked_accounts=tracked_accounts,
        )
        if tracked_account is not None:
            linked_tracked_ids.add(tracked_account.id)
        portfolio_account = _match_portfolio_account(
            label=_tracked_label(tracked_account) if tracked_account is not None else _account_label(latest),
            asset_group=latest.asset_group,
            portfolio_accounts=portfolio_accounts,
        )
        if portfolio_account is not None:
            linked_portfolio_ids.add(portfolio_account.id)
        effective_asset_group = (
            tracked_account.asset_group if tracked_account is not None else latest.asset_group
        )
        match_confidence = _confidence_for_summary(
            latest,
            evidence_count=len(accounts),
            linked=portfolio_account is not None or tracked_account is not None,
        )
        match_status = "tracked" if match_confidence >= 0.8 else "candidate"
        if portfolio_account is not None or tracked_account is not None:
            match_status = "linked"
        summary = HouseholdAccountSummary(
            id=group_key,
            label=_tracked_label(tracked_account) if tracked_account is not None else _account_label(latest),
            asset_group=effective_asset_group,
            account_type=tracked_account.account_type if tracked_account is not None else latest.account_type,
            source_type=tracked_account.source_type if tracked_account is not None else latest.source_type,
            institution_name=tracked_account.institution_name if tracked_account is not None and tracked_account.institution_name is not None else latest.institution_name,
            owner_name=tracked_account.owner_name if tracked_account is not None and tracked_account.owner_name is not None else latest.owner_name,
            account_mask=tracked_account.account_mask if tracked_account is not None and tracked_account.account_mask is not None else latest.account_mask,
            notes=tracked_account.notes if tracked_account is not None else None,
            currency=latest.currency,
            current_value=_account_value(latest),
            balance=latest.balance,
            holdings_value=latest.holdings_value,
            cash_balance=latest.cash_balance,
            evidence_count=len(accounts),
            document_ids=sorted({account.document_id for account in accounts}),
            latest_document_id=latest.document_id,
            source_types=sorted({account.source_type for account in accounts}),
            linked_portfolio_account_id=portfolio_account.id if portfolio_account is not None else None,
            linked_portfolio_account_name=_portfolio_label(portfolio_account) if portfolio_account is not None else None,
            tracked_account_id=tracked_account.id if tracked_account is not None else None,
            account_origin="tracked" if tracked_account is not None else "evidence",
            last_evidence_at=last_dt.isoformat() if last_dt is not None else None,
            days_since_evidence=days_since,
            freshness_status=_freshness_state(effective_asset_group, days_since=days_since)[0],
            freshness_label=_freshness_state(effective_asset_group, days_since=days_since)[1],
            match_status=match_status,
            match_confidence=match_confidence,
        )
        summaries.append(summary)
        duplicate_key = (_normalize_text(summary.institution_name), summary.asset_group)
        if duplicate_key[0] and latest.account_mask is None:
            duplicate_candidates[duplicate_key].append(summary.id)

    for account in portfolio_accounts:
        if getattr(account, "account_type", None) == "paper" or account.id in linked_portfolio_ids:
            continue
        summaries.append(
            HouseholdAccountSummary(
                id=_portfolio_summary_key(account),
                label=_portfolio_label(account),
                asset_group=_portfolio_asset_group(account),
                account_type=str(account.account_type),
                source_type=_portfolio_source_type(account),
                current_value=_portfolio_value(account, holdings_by_account),
                cash_balance=float(getattr(account, "cash_balance", 0.0) or 0.0),
                latest_document_id=None,
                linked_portfolio_account_id=account.id,
                linked_portfolio_account_name=_portfolio_label(account),
                account_origin="portfolio",
                freshness_status="needs_evidence",
                freshness_label="Needs evidence",
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
                label=_tracked_label(account),
                asset_group=account.asset_group,
                account_type=account.account_type,
                source_type=account.source_type,
                institution_name=account.institution_name,
                owner_name=account.owner_name,
                account_mask=account.account_mask,
                notes=account.notes,
                latest_document_id=None,
                linked_portfolio_account_id=portfolio_account.id if portfolio_account is not None else None,
                linked_portfolio_account_name=_portfolio_label(portfolio_account) if portfolio_account is not None else None,
                tracked_account_id=account.id,
                account_origin="tracked",
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
    questions: list[Any],
    tracked_documents: int,
    parsed_documents: int,
    statement_freshness: dict[str, Any],
) -> list[HouseholdInboxItem]:
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
                detail=str(gap_months[0]),
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
                action_href=MONEY_CLARIFICATIONS_ROUTE,
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
        if top_gap.code in {"missing_evidence", "refresh_soon", "stale_evidence", "incomplete_application"}:
            action_label = "Add evidence"
        elif top_gap.code == "unconfirmed_match":
            action_label = "Confirm account"
        items.append(
            HouseholdInboxItem(
                id=f"account-{account.id}-{top_gap.code}",
                category="account",
                priority=_SEVERITY_PRIORITY[top_gap.severity],
                title=(
                    f"Refresh {account.label}"
                    if top_gap.code in {"refresh_soon", "stale_evidence"}
                    else f"Add evidence for {account.label}"
                    if top_gap.code in {"missing_evidence", "incomplete_application"}
                    else f"Confirm {account.label}"
                    if top_gap.code == "unconfirmed_match"
                    else f"Review {account.label}"
                ),
                detail=top_gap.detail,
                action_label=action_label,
                action_href=action_href,
                related_account_id=account.id,
                related_document_ids=account.document_ids,
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
