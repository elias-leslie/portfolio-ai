"""Canonical household account summaries and inbox derivation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdAccountSummary,
    HouseholdDocument,
    HouseholdEvidenceAccount,
    HouseholdTrackedAccount,
)
from app.services._household_account_summary_gaps import (
    _PRIORITY_ORDER,
    _SEVERITY_PRIORITY,
    _build_account_gaps,
    _top_gap,
)
from app.services._household_account_summary_inbox import build_money_inbox
from app.services._household_account_summary_matching import (
    _match_portfolio_account,
    _match_tracked_account,
)
from app.services._household_account_summary_utils import (
    _BALANCE_FRESHNESS_THRESHOLDS,
    _account_label,
    _account_value,
    _best_balance_account,
    _best_display_account,
    _combine_freshness,
    _confidence_for_summary,
    _duplicate_label_key,
    _evidence_group_key,
    _freshness_state_from_thresholds,
    _is_closed_zero_balance_account,
    _latest_evidence_timestamp,
    _latest_transaction_coverage_timestamp,
    _latest_transaction_timestamp,
    _money_role,
    _normalize_text,
    _parse_datetime,
    _portfolio_asset_group,
    _portfolio_label,
    _portfolio_source_type,
    _portfolio_summary_key,
    _portfolio_value,
    _source_account_float,
    _tracked_label,
    _tracked_summary_key,
    _transaction_freshness_pair,
)

__all__ = [
    "build_account_summaries",
    "build_money_inbox",
]


# ---------------------------------------------------------------------------
# Grouping helpers
# ---------------------------------------------------------------------------


def _build_evidence_match_indexes(
    evidence_accounts: list[HouseholdEvidenceAccount],
) -> tuple[dict[str, str], dict[str, str]]:
    """Return (group_key→household_id, match_key→household_id) indexes."""
    by_group: dict[str, str] = {}
    by_match: dict[str, str] = {}
    for account in evidence_accounts:
        if not account.household_account_id:
            continue
        by_group.setdefault(_evidence_group_key(account), account.household_account_id)
        if isinstance(account.metadata, dict):
            match_key = _normalize_text(account.metadata.get("match_key"))
            if match_key:
                by_match.setdefault(match_key, account.household_account_id)
    return by_group, by_match


def _group_evidence_accounts(
    evidence_accounts: list[HouseholdEvidenceAccount],
    documents_by_id: dict[str, HouseholdDocument],
    tracked_accounts: list[HouseholdTrackedAccount],
    tracked_by_household_id: dict[str, HouseholdTrackedAccount],
) -> tuple[dict[str, list[HouseholdEvidenceAccount]], dict[str, HouseholdTrackedAccount]]:
    """Group evidence accounts by canonical key; return groups and tracked matches."""
    by_group_key, by_match_key = _build_evidence_match_indexes(evidence_accounts)
    grouped: dict[str, list[HouseholdEvidenceAccount]] = defaultdict(list)
    tracked_matches: dict[str, HouseholdTrackedAccount] = {}

    for account in evidence_accounts:
        document = documents_by_id.get(account.document_id)
        if account.household_account_id:
            group_key = account.household_account_id
            matched = tracked_by_household_id.get(account.household_account_id)
        else:
            matched, group_key = _resolve_unlinked_evidence(
                account=account,
                document=document,
                by_group_key=by_group_key,
                by_match_key=by_match_key,
                tracked_accounts=tracked_accounts,
                tracked_by_household_id=tracked_by_household_id,
            )
        grouped[group_key].append(account)
        if matched is not None:
            tracked_matches[group_key] = matched

    return grouped, tracked_matches


def _resolve_unlinked_evidence(
    *,
    account: HouseholdEvidenceAccount,
    document: HouseholdDocument | None,
    by_group_key: dict[str, str],
    by_match_key: dict[str, str],
    tracked_accounts: list[HouseholdTrackedAccount],
    tracked_by_household_id: dict[str, HouseholdTrackedAccount],
) -> tuple[HouseholdTrackedAccount | None, str]:
    """Resolve the group key and tracked-account match for an unlinked evidence account."""
    evidence_group_key = _evidence_group_key(account)
    evidence_match_key = (
        _normalize_text(account.metadata.get("match_key"))
        if isinstance(account.metadata, dict)
        else ""
    )
    linked_household_id = (
        by_match_key.get(evidence_match_key) if evidence_match_key else None
    ) or by_group_key.get(evidence_group_key)

    if linked_household_id:
        return tracked_by_household_id.get(linked_household_id), linked_household_id

    matched = _match_tracked_account(
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
    if matched is not None and matched.household_account_id:
        group_key = matched.household_account_id
    elif matched is not None:
        group_key = _tracked_summary_key(matched)
    else:
        group_key = evidence_group_key
    return matched, group_key


# ---------------------------------------------------------------------------
# Intermediate data carriers
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _EvidenceSelection:
    """Best account representatives for one evidence group."""
    latest: HouseholdEvidenceAccount
    display: HouseholdEvidenceAccount
    balance: HouseholdEvidenceAccount
    latest_document: HouseholdDocument | None
    display_document: HouseholdDocument | None
    balance_document: HouseholdDocument | None
    closed_zero_balance: bool
    account_label: str
    hint_label: str | None


@dataclass(slots=True)
class _FreshnessState:
    last_balance_dt: datetime | None
    days_since_balance: int | None
    balance_status: str
    balance_label: str
    last_transaction_dt: datetime | None
    days_since_transaction: int | None
    transaction_status: str
    transaction_label: str
    freshness_status: str
    freshness_label: str


@dataclass(slots=True)
class _MatchResolution:
    """Resolved account links and ownership for one evidence group."""
    tracked_account: HouseholdTrackedAccount | None
    portfolio_account: Any
    portfolio_valuation: Any
    household_account_id: str | None
    source_owned: bool
    source_account_value: dict[str, Any] | None
    effective_label: str
    effective_asset_group: str
    effective_account_type: str
    effective_money_role: str
    has_live_pricing: bool


# ---------------------------------------------------------------------------
# Evidence summary sub-steps
# ---------------------------------------------------------------------------


def _select_evidence_accounts(
    accounts: list[HouseholdEvidenceAccount],
    documents_by_id: dict[str, HouseholdDocument],
    closed_household_account_ids: set[str],
) -> _EvidenceSelection:
    """Pick best representative accounts and derive basic metadata."""
    latest = max(
        accounts,
        key=lambda a: (
            _latest_evidence_timestamp(a, documents_by_id.get(a.document_id)) or datetime.min.replace(tzinfo=UTC),
            float(a.confidence or 0.0),
        ),
    )
    display = _best_display_account(accounts, documents_by_id)
    balance = _best_balance_account(accounts, documents_by_id)
    latest_doc = documents_by_id.get(latest.document_id)
    display_doc = documents_by_id.get(display.document_id)
    balance_doc = documents_by_id.get(balance.document_id)
    known_closed = any(
        account.household_account_id is not None
        and str(account.household_account_id) in closed_household_account_ids
        for account in accounts
    )
    closed_zero = _is_closed_zero_balance_account(
        balance,
        balance_doc,
        latest_doc,
        display_doc,
        known_closed=known_closed,
    )
    account_label = _account_label(display)
    hint_label = (
        display_doc.account_label
        if display_doc is not None and display_doc.account_label
        else latest_doc.account_label if latest_doc is not None else None
    )
    return _EvidenceSelection(
        latest=latest,
        display=display,
        balance=balance,
        latest_document=latest_doc,
        display_document=display_doc,
        balance_document=balance_doc,
        closed_zero_balance=closed_zero,
        account_label=account_label,
        hint_label=hint_label,
    )


def _compute_freshness(
    sel: _EvidenceSelection,
    effective_money_role: str,
    effective_asset_group: str,
    *,
    accounts: list[HouseholdEvidenceAccount],
    source_owned: bool,
    portfolio_account: Any,
    source_account_value: dict[str, Any] | None,
    latest_transaction_dates_by_household_account: dict[str, date],
    latest_transaction_dates_by_document: dict[str, date],
    latest_transaction_dates_by_account_label: dict[str, date],
    documents_by_id: dict[str, HouseholdDocument],
) -> _FreshnessState:
    """Compute all freshness state for one evidence group."""
    last_balance_dt = _latest_evidence_timestamp(sel.balance, sel.balance_document)
    days_since_balance = (
        (datetime.now(UTC).date() - last_balance_dt.date()).days if last_balance_dt is not None else None
    )
    balance_status, balance_label = _freshness_state_from_thresholds(
        _BALANCE_FRESHNESS_THRESHOLDS, sel.display.asset_group, days_since=days_since_balance
    )
    if sel.closed_zero_balance:
        balance_status, balance_label = "fresh", "Closed"

    label_candidates = _build_transaction_label_candidates(accounts, documents_by_id)
    last_transaction_dt = _latest_transaction_timestamp(
        [str(a.document_id) for a in accounts if a.document_id],
        household_account_id=sel.display.household_account_id,
        label_candidates=label_candidates,
        account_mask=sel.display.account_mask,
        latest_transaction_dates_by_household_account=latest_transaction_dates_by_household_account,
        latest_transaction_dates_by_document=latest_transaction_dates_by_document,
        latest_transaction_dates_by_account_label=latest_transaction_dates_by_account_label,
    )
    coverage_dt = _latest_transaction_coverage_timestamp(accounts, latest_transaction_dt=last_transaction_dt)
    days_since_transaction = (
        (datetime.now(UTC).date() - coverage_dt.date()).days if coverage_dt is not None else None
    )

    # Override balance freshness from source sync if available.
    if source_owned and portfolio_account is not None:
        source_balance_dt = (
            _parse_datetime((source_account_value or {}).get("last_synced_at"))
            or _parse_datetime(getattr(portfolio_account, "updated_at", None))
        )
        if source_balance_dt is not None:
            last_balance_dt = source_balance_dt
            days_since_balance = (datetime.now(UTC).date() - source_balance_dt.date()).days
            balance_status, balance_label = _freshness_state_from_thresholds(
                _BALANCE_FRESHNESS_THRESHOLDS, effective_asset_group, days_since=days_since_balance
            )
            # A successful brokerage sync also refreshes activity coverage: the
            # sync pulls transactions up through the sync time, so anchor
            # transaction freshness to the sync whenever it is more recent than
            # the latest document-derived transaction. Without this, source-synced
            # spending accounts (e.g. cash management) flag "stale activity" right
            # after a sync, because transaction freshness otherwise reads only from
            # uploaded-statement transactions in household_transactions.
            if days_since_transaction is None or days_since_balance < days_since_transaction:
                days_since_transaction = days_since_balance

    txn_status, txn_label = _transaction_freshness_pair(effective_money_role, days_since_transaction)
    freshness_status, freshness_label = _combine_freshness(
        money_role=effective_money_role,
        balance_status=balance_status,
        balance_label=balance_label,
        transaction_status=txn_status,
        transaction_label=txn_label,
    )
    return _FreshnessState(
        last_balance_dt=last_balance_dt,
        days_since_balance=days_since_balance,
        balance_status=balance_status,
        balance_label=balance_label,
        last_transaction_dt=last_transaction_dt,
        days_since_transaction=days_since_transaction,
        transaction_status=txn_status,
        transaction_label=txn_label,
        freshness_status=freshness_status,
        freshness_label=freshness_label,
    )


def _assemble_evidence_summary(
    group_key: str,
    accounts: list[HouseholdEvidenceAccount],
    sel: _EvidenceSelection,
    fs: _FreshnessState,
    *,
    tracked_account: HouseholdTrackedAccount | None,
    portfolio_account: Any,
    portfolio_valuation: Any,
    household_account_id: str | None,
    effective_label: str,
    effective_asset_group: str,
    effective_account_type: str,
    effective_money_role: str,
    match_status: str,
    match_confidence: float,
    source_account_value: dict[str, Any] | None,
    source_owned: bool,
    has_live_pricing: bool,
) -> HouseholdAccountSummary:
    """Construct the HouseholdAccountSummary from resolved values."""
    source_current_value = _source_account_float(source_account_value, "current_value")
    has_source_balance = source_owned and source_current_value is not None
    source_account_mask = (
        str(source_account_value.get("account_mask"))
        if source_account_value and source_account_value.get("account_mask")
        else None
    )
    effective_current, effective_holdings, effective_cash, valuation_source = _resolve_effective_values(
        balance_account=sel.balance,
        closed_zero_balance=sel.closed_zero_balance,
        source_account_value=source_account_value,
        portfolio_valuation=portfolio_valuation,
        has_source_balance=has_source_balance,
        has_live_pricing=has_live_pricing,
    )
    return HouseholdAccountSummary(
        id=group_key,
        household_account_id=household_account_id,
        label=effective_label,
        asset_group=effective_asset_group,
        account_type=effective_account_type,
        source_type=sel.display.source_type,
        match_key=tracked_account.match_key if tracked_account is not None else group_key,
        institution_name=sel.display.institution_name,
        owner_name=(
            tracked_account.owner_name
            if tracked_account is not None and tracked_account.owner_name is not None
            else sel.display.owner_name
        ),
        account_mask=source_account_mask or sel.display.account_mask,
        notes=tracked_account.notes if tracked_account is not None else None,
        currency=sel.balance.currency or sel.display.currency,
        current_value=effective_current,
        balance=sel.balance.balance,
        holdings_value=effective_holdings,
        cash_balance=effective_cash,
        valuation_source=valuation_source,
        evidence_count=len(accounts),
        document_ids=sorted({account.document_id for account in accounts}),
        latest_document_id=(
            sel.balance.document_id
            if _account_value(sel.balance) is not None
            else sel.latest.document_id
        ),
        source_types=sorted({account.source_type for account in accounts}),
        linked_portfolio_account_id=portfolio_account.id if portfolio_account is not None else None,
        linked_portfolio_account_name=(
            _portfolio_label(portfolio_account) if portfolio_account is not None else None
        ),
        tracked_account_id=tracked_account.id if tracked_account is not None else None,
        account_origin="evidence",
        money_role=effective_money_role,
        last_evidence_at=fs.last_balance_dt.isoformat() if fs.last_balance_dt is not None else None,
        days_since_evidence=fs.days_since_balance,
        last_balance_at=fs.last_balance_dt.isoformat() if fs.last_balance_dt is not None else None,
        days_since_balance=fs.days_since_balance,
        balance_freshness_status=fs.balance_status,
        balance_freshness_label=fs.balance_label,
        last_transaction_at=fs.last_transaction_dt.isoformat() if fs.last_transaction_dt is not None else None,
        days_since_transaction=fs.days_since_transaction,
        transaction_freshness_status=fs.transaction_status,
        transaction_freshness_label=fs.transaction_label,
        freshness_status=fs.freshness_status,
        freshness_label=fs.freshness_label,
        match_status=match_status,
        match_confidence=match_confidence,
        **_quote_fields(portfolio_valuation, has_live_pricing=has_live_pricing),
    )


def _resolve_evidence_matches(
    group_key: str,
    accounts: list[HouseholdEvidenceAccount],
    sel: _EvidenceSelection,
    *,
    portfolio_accounts: list[Any],
    tracked_accounts: list[HouseholdTrackedAccount],
    grouped_tracked_matches: dict[str, HouseholdTrackedAccount],
    tracked_by_household_id: dict[str, HouseholdTrackedAccount],
    account_valuations: dict[str, Any],
    source_owned_household_account_ids: set[str],
    source_owned_account_values: dict[str, dict[str, Any]],
    linked_portfolio_ids: set[str],
    linked_tracked_ids: set[str],
) -> _MatchResolution:
    """Resolve account links, ownership and effective identity for an evidence group."""
    tracked_account = _resolve_tracked_account(
        group_key=group_key,
        display_account=sel.display,
        hint_label=sel.hint_label,
        account_label=sel.account_label,
        grouped_tracked_matches=grouped_tracked_matches,
        tracked_by_household_id=tracked_by_household_id,
        tracked_accounts=tracked_accounts,
    )
    if tracked_account is not None:
        linked_tracked_ids.add(tracked_account.id)

    portfolio_account = _match_portfolio_account(
        household_account_id=sel.display.household_account_id,
        label=_tracked_label(tracked_account) if tracked_account is not None else _account_label(sel.latest),
        account_name=sel.display.account_name,
        asset_group=sel.display.asset_group,
        portfolio_accounts=portfolio_accounts,
    )
    portfolio_valuation = (
        account_valuations.get(portfolio_account.id) if portfolio_account is not None else None
    )
    if portfolio_account is not None:
        linked_portfolio_ids.add(portfolio_account.id)

    household_account_id = _resolve_household_account_id(
        display_account=sel.display,
        accounts=accounts,
        tracked_account=tracked_account,
        portfolio_account=portfolio_account,
    )
    source_owned = (
        household_account_id is not None
        and household_account_id in source_owned_household_account_ids
    )
    source_account_value = (
        source_owned_account_values.get(household_account_id)
        if household_account_id is not None
        else None
    )
    effective_asset_group = sel.display.asset_group
    effective_label = (
        _portfolio_label(portfolio_account) if portfolio_account is not None
        else _tracked_label(tracked_account) if tracked_account is not None
        else sel.account_label
    )
    effective_account_type = (
        tracked_account.account_type if tracked_account is not None else sel.display.account_type
    )
    effective_money_role = _money_role(effective_asset_group, effective_account_type, effective_label)
    if sel.closed_zero_balance:
        effective_money_role = "net_worth_only"
    has_live_pricing = _has_complete_live_pricing(portfolio_valuation)
    return _MatchResolution(
        tracked_account=tracked_account,
        portfolio_account=portfolio_account,
        portfolio_valuation=portfolio_valuation,
        household_account_id=household_account_id,
        source_owned=source_owned,
        source_account_value=source_account_value,
        effective_label=effective_label,
        effective_asset_group=effective_asset_group,
        effective_account_type=effective_account_type,
        effective_money_role=effective_money_role,
        has_live_pricing=has_live_pricing,
    )


def _build_evidence_summary(
    group_key: str,
    accounts: list[HouseholdEvidenceAccount],
    *,
    documents_by_id: dict[str, HouseholdDocument],
    portfolio_accounts: list[Any],
    tracked_accounts: list[HouseholdTrackedAccount],
    grouped_tracked_matches: dict[str, HouseholdTrackedAccount],
    tracked_by_household_id: dict[str, HouseholdTrackedAccount],
    account_valuations: dict[str, Any],
    source_owned_household_account_ids: set[str],
    source_owned_account_values: dict[str, dict[str, Any]],
    latest_transaction_dates_by_household_account: dict[str, date],
    latest_transaction_dates_by_document: dict[str, date],
    latest_transaction_dates_by_account_label: dict[str, date],
    closed_household_account_ids: set[str],
    linked_portfolio_ids: set[str],
    linked_tracked_ids: set[str],
) -> HouseholdAccountSummary | None:
    """Build one evidence-origin HouseholdAccountSummary; return None to skip."""
    sel = _select_evidence_accounts(accounts, documents_by_id, closed_household_account_ids)
    mr = _resolve_evidence_matches(
        group_key, accounts, sel,
        portfolio_accounts=portfolio_accounts,
        tracked_accounts=tracked_accounts,
        grouped_tracked_matches=grouped_tracked_matches,
        tracked_by_household_id=tracked_by_household_id,
        account_valuations=account_valuations,
        source_owned_household_account_ids=source_owned_household_account_ids,
        source_owned_account_values=source_owned_account_values,
        linked_portfolio_ids=linked_portfolio_ids,
        linked_tracked_ids=linked_tracked_ids,
    )
    fs = _compute_freshness(
        sel, mr.effective_money_role, mr.effective_asset_group,
        accounts=accounts,
        source_owned=mr.source_owned,
        portfolio_account=mr.portfolio_account,
        source_account_value=mr.source_account_value,
        latest_transaction_dates_by_household_account=latest_transaction_dates_by_household_account,
        latest_transaction_dates_by_document=latest_transaction_dates_by_document,
        latest_transaction_dates_by_account_label=latest_transaction_dates_by_account_label,
        documents_by_id=documents_by_id,
    )
    match_confidence = _confidence_for_summary(
        sel.display,
        evidence_count=len(accounts),
        linked=mr.portfolio_account is not None or mr.tracked_account is not None,
    )
    match_status = "tracked" if match_confidence >= 0.8 else "candidate"
    if mr.portfolio_account is not None or mr.tracked_account is not None:
        match_status = "linked"

    source_current_value = _source_account_float(mr.source_account_value, "current_value")
    has_source_balance = mr.source_owned and source_current_value is not None
    if (
        mr.portfolio_account is None
        and mr.tracked_account is None
        and not mr.source_owned
        and _resolve_effective_values(
            balance_account=sel.balance,
            closed_zero_balance=sel.closed_zero_balance,
            source_account_value=mr.source_account_value,
            portfolio_valuation=mr.portfolio_valuation,
            has_source_balance=has_source_balance,
            has_live_pricing=mr.has_live_pricing,
        )[0] is None
    ):
        return None

    return _assemble_evidence_summary(
        group_key, accounts, sel, fs,
        tracked_account=mr.tracked_account,
        portfolio_account=mr.portfolio_account,
        portfolio_valuation=mr.portfolio_valuation,
        household_account_id=mr.household_account_id,
        effective_label=mr.effective_label,
        effective_asset_group=mr.effective_asset_group,
        effective_account_type=mr.effective_account_type,
        effective_money_role=mr.effective_money_role,
        match_status=match_status,
        match_confidence=match_confidence,
        source_account_value=mr.source_account_value,
        source_owned=mr.source_owned,
        has_live_pricing=mr.has_live_pricing,
    )


# ---------------------------------------------------------------------------
# Portfolio-origin and tracked-origin summaries
# ---------------------------------------------------------------------------


def _build_portfolio_summary(
    account: Any,
    *,
    account_valuations: dict[str, Any],
    source_owned_household_account_ids: set[str],
    source_owned_account_values: dict[str, dict[str, Any]],
    holdings_by_account: dict[str, float],
) -> HouseholdAccountSummary:
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
    source_balance_dt, days_since_source_balance = _portfolio_source_balance_dt(
        account, source_owned=source_owned, source_account_value=source_account_value
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
    has_live_pricing = _has_complete_live_pricing(portfolio_valuation)
    effective_current = (
        portfolio_current_value
        if has_live_pricing
        else source_current_value
        if source_current_value is not None
        else portfolio_current_value
    )
    effective_cash = source_cash_value if source_cash_value is not None else portfolio_cash_balance
    return HouseholdAccountSummary(
        id=_portfolio_summary_key(account),
        household_account_id=portfolio_household_account_id,
        label=_portfolio_label(account),
        asset_group=_portfolio_asset_group(account),
        account_type=str(account.account_type),
        source_type=_portfolio_source_type(account),
        match_key=None,
        current_value=effective_current,
        holdings_value=_portfolio_holdings_value(
            effective_current, effective_cash, source_current_value, portfolio_valuation, account, holdings_by_account
        ),
        cash_balance=effective_cash,
        valuation_source=(
            "live_quotes" if has_live_pricing
            else "source_balance" if source_owned
            else "portfolio_cash"
        ),
        latest_document_id=None,
        linked_portfolio_account_id=account.id,
        linked_portfolio_account_name=_portfolio_label(account),
        account_origin="portfolio",
        money_role=_money_role(
            _portfolio_asset_group(account), str(account.account_type), _portfolio_label(account)
        ),
        last_balance_at=source_balance_dt.isoformat() if source_balance_dt is not None else None,
        days_since_balance=days_since_source_balance,
        balance_freshness_status=balance_status,
        balance_freshness_label=balance_label,
        last_transaction_at=None,
        days_since_transaction=None,
        transaction_freshness_status="not_applicable",
        transaction_freshness_label="Not required",
        freshness_status=balance_status,
        freshness_label=balance_label,
        match_status="tracked",
        match_confidence=None,
        **_quote_fields(portfolio_valuation, has_live_pricing=has_live_pricing),
    )


def _portfolio_source_balance_dt(
    account: Any,
    *,
    source_owned: bool,
    source_account_value: dict[str, Any] | None,
) -> tuple[datetime | None, int | None]:
    if not source_owned:
        return None, None
    source_balance_dt = (
        _parse_datetime((source_account_value or {}).get("last_synced_at"))
        or _parse_datetime(getattr(account, "updated_at", None))
    )
    days = (
        (datetime.now(UTC).date() - source_balance_dt.date()).days
        if source_balance_dt is not None
        else None
    )
    return source_balance_dt, days


def _portfolio_holdings_value(
    effective_current: float | None,
    effective_cash: float | None,
    source_current_value: float | None,
    portfolio_valuation: Any,
    account: Any,
    holdings_by_account: dict[str, float],
) -> float | None:
    if source_current_value is not None and effective_current is not None:
        return effective_current - float(effective_cash or 0.0)
    if portfolio_valuation is not None:
        return float(getattr(portfolio_valuation, "priced_positions_value", 0.0) or 0.0)
    return holdings_by_account.get(account.id, 0.0)


def _build_tracked_summary(
    account: HouseholdTrackedAccount,
    portfolio_account: Any,
) -> HouseholdAccountSummary:
    role = _money_role(account.asset_group, account.account_type, account.label)
    return HouseholdAccountSummary(
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
        linked_portfolio_account_id=portfolio_account.id,
        linked_portfolio_account_name=_portfolio_label(portfolio_account),
        tracked_account_id=account.id,
        account_origin="tracked",
        money_role=role,
        last_balance_at=None,
        days_since_balance=None,
        balance_freshness_status="needs_evidence",
        balance_freshness_label="Needs evidence",
        last_transaction_at=None,
        days_since_transaction=None,
        transaction_freshness_status="needs_evidence" if role == "spend_driver" else "not_applicable",
        transaction_freshness_label="Needs transactions" if role == "spend_driver" else "Not required",
        freshness_status="needs_evidence",
        freshness_label="Needs evidence",
        match_status="tracked",
        match_confidence=None,
    )


# ---------------------------------------------------------------------------
# Balance / valuation helpers
# ---------------------------------------------------------------------------


def _quote_fields(
    portfolio_valuation: Any,
    *,
    has_live_pricing: bool,
) -> dict[str, Any]:
    return {
        "quote_updated_at": (
            portfolio_valuation.quote_updated_at.isoformat()
            if has_live_pricing and getattr(portfolio_valuation, "quote_updated_at", None) is not None
            else None
        ),
        "quote_freshness_status": (
            str(getattr(portfolio_valuation, "quote_freshness_status", "not_applicable"))
            if has_live_pricing
            else "not_applicable"
        ),
        "quote_freshness_label": (
            str(getattr(portfolio_valuation, "quote_freshness_label", "No live quotes"))
            if has_live_pricing
            else "No live quotes"
        ),
        "quote_source": (
            str(getattr(portfolio_valuation, "quote_source", None))
            if has_live_pricing and getattr(portfolio_valuation, "quote_source", None)
            else None
        ),
        "priced_position_count": (
            int(getattr(portfolio_valuation, "priced_position_count", 0))
            if has_live_pricing
            else 0
        ),
    }


def _has_complete_live_pricing(portfolio_valuation: Any) -> bool:
    if portfolio_valuation is None:
        return False
    priced_position_count = int(getattr(portfolio_valuation, "priced_position_count", 0) or 0)
    total_position_count = int(
        getattr(portfolio_valuation, "total_position_count", 0) or priced_position_count
    )
    return priced_position_count > 0 and priced_position_count >= total_position_count


def _resolve_effective_values(
    *,
    balance_account: HouseholdEvidenceAccount,
    closed_zero_balance: bool,
    source_account_value: dict[str, Any] | None,
    portfolio_valuation: Any,
    has_source_balance: bool,
    has_live_pricing: bool,
) -> tuple[float | None, float | None, float | None, str]:
    """Return (current_value, holdings_value, cash_balance, valuation_source)."""
    source_current_value = _source_account_float(source_account_value, "current_value")
    source_cash_value = _source_account_float(source_account_value, "cash_balance")
    evidence_current_value = _account_value(balance_account)
    if evidence_current_value is None and closed_zero_balance:
        evidence_current_value = 0.0

    live_priced_positions_value = (
        float(getattr(portfolio_valuation, "priced_positions_value", 0.0) or 0.0)
        if has_live_pricing
        else None
    )
    portfolio_effective_cash = (
        float(getattr(portfolio_valuation, "effective_cash_balance", 0.0) or 0.0)
        if portfolio_valuation is not None
        else None
    )

    effective_cash = _pick_effective_cash(
        closed_zero_balance=closed_zero_balance,
        source_cash_value=source_cash_value,
        has_source_balance=has_source_balance,
        portfolio_effective_cash=portfolio_effective_cash,
        balance_account_cash=balance_account.cash_balance,
    )

    source_holdings = (
        source_current_value - float(effective_cash or 0.0)
        if has_source_balance and not has_live_pricing
        else None
    )
    effective_holdings = (
        live_priced_positions_value
        if has_live_pricing and live_priced_positions_value is not None
        else source_holdings
        if source_holdings is not None
        else float(balance_account.holdings_value)
        if balance_account.holdings_value is not None
        else None
    )
    effective_current = (
        live_priced_positions_value + float(effective_cash or 0.0)
        if has_live_pricing and live_priced_positions_value is not None
        else source_current_value
        if has_source_balance
        else evidence_current_value
    )
    valuation_source = (
        "live_quotes" if has_live_pricing
        else "source_balance" if has_source_balance
        else "evidence"
    )
    return effective_current, effective_holdings, effective_cash, valuation_source


def _pick_effective_cash(
    *,
    closed_zero_balance: bool,
    source_cash_value: float | None,
    has_source_balance: bool,
    portfolio_effective_cash: float | None,
    balance_account_cash: float | None,
) -> float | None:
    if closed_zero_balance:
        return 0.0
    if source_cash_value is not None:
        return source_cash_value
    if has_source_balance:
        return portfolio_effective_cash
    if balance_account_cash is not None:
        return float(balance_account_cash)
    return portfolio_effective_cash


# ---------------------------------------------------------------------------
# Small helpers used inside the per-group builder
# ---------------------------------------------------------------------------


def _build_transaction_label_candidates(
    accounts: list[HouseholdEvidenceAccount],
    documents_by_id: dict[str, HouseholdDocument],
) -> set[str]:
    candidates: set[str] = set()
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
                candidates.add(normalized)
    return candidates


def _resolve_tracked_account(
    *,
    group_key: str,
    display_account: HouseholdEvidenceAccount,
    hint_label: str | None,
    account_label: str,
    grouped_tracked_matches: dict[str, HouseholdTrackedAccount],
    tracked_by_household_id: dict[str, HouseholdTrackedAccount],
    tracked_accounts: list[HouseholdTrackedAccount],
) -> HouseholdTrackedAccount | None:
    tracked = grouped_tracked_matches.get(group_key)
    if tracked is None and display_account.household_account_id:
        tracked = tracked_by_household_id.get(display_account.household_account_id)
    if tracked is None:
        tracked = _match_tracked_account(
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
    return tracked


def _resolve_household_account_id(
    *,
    display_account: HouseholdEvidenceAccount,
    accounts: list[HouseholdEvidenceAccount],
    tracked_account: HouseholdTrackedAccount | None,
    portfolio_account: Any,
) -> str | None:
    linked_group_id = next(
        (a.household_account_id for a in accounts if a.household_account_id), None
    )
    household_account_id = (
        display_account.household_account_id
        or linked_group_id
        or (tracked_account.household_account_id if tracked_account is not None else None)
    )
    if household_account_id is None and portfolio_account is not None:
        household_account_id = getattr(portfolio_account, "household_account_id", None)
    return household_account_id


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_account_summaries(
    *,
    evidence_accounts: list[HouseholdEvidenceAccount],
    documents: list[HouseholdDocument],
    portfolio_accounts: list[Any],
    tracked_accounts: list[HouseholdTrackedAccount],
    account_valuations: dict[str, Any] | None = None,
    source_owned_household_account_ids: set[str] | None = None,
    source_owned_account_values: dict[str, dict[str, Any]] | None = None,
    closed_household_account_ids: set[str] | None = None,
    hidden_household_account_ids: set[str] | None = None,
    holdings_by_account: dict[str, float],
    statement_freshness: dict[str, Any],
    latest_transaction_dates_by_household_account: dict[str, date] | None = None,
    latest_transaction_dates_by_document: dict[str, date] | None = None,
    latest_transaction_dates_by_account_label: dict[str, date] | None = None,
) -> list[HouseholdAccountSummary]:
    account_valuations = account_valuations or {}
    source_owned_household_account_ids = source_owned_household_account_ids or set()
    source_owned_account_values = source_owned_account_values or {}
    closed_household_account_ids = closed_household_account_ids or set()
    hidden_household_account_ids = hidden_household_account_ids or set()
    latest_transaction_dates_by_household_account = latest_transaction_dates_by_household_account or {}
    latest_transaction_dates_by_document = latest_transaction_dates_by_document or {}
    latest_transaction_dates_by_account_label = latest_transaction_dates_by_account_label or {}

    evidence_accounts = [
        account
        for account in evidence_accounts
        if not (
            account.household_account_id is not None
            and str(account.household_account_id) in hidden_household_account_ids
        )
    ]
    portfolio_accounts = [
        account
        for account in portfolio_accounts
        if not (
            account.household_account_id is not None
            and str(account.household_account_id) in hidden_household_account_ids
        )
    ]
    source_owned_household_account_ids = (
        source_owned_household_account_ids - hidden_household_account_ids
    )
    source_owned_account_values = {
        account_id: value
        for account_id, value in source_owned_account_values.items()
        if str(account_id) not in hidden_household_account_ids
    }

    documents_by_id = {document.id: document for document in documents}
    tracked_by_household_id = {
        account.household_account_id: account
        for account in tracked_accounts
        if account.household_account_id
    }

    grouped, grouped_tracked_matches = _group_evidence_accounts(
        evidence_accounts, documents_by_id, tracked_accounts, tracked_by_household_id
    )

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
        summary = _build_evidence_summary(
            group_key,
            accounts,
            documents_by_id=documents_by_id,
            portfolio_accounts=portfolio_accounts,
            tracked_accounts=tracked_accounts,
            grouped_tracked_matches=grouped_tracked_matches,
            tracked_by_household_id=tracked_by_household_id,
            account_valuations=account_valuations,
            source_owned_household_account_ids=source_owned_household_account_ids,
            source_owned_account_values=source_owned_account_values,
            latest_transaction_dates_by_household_account=latest_transaction_dates_by_household_account,
            latest_transaction_dates_by_document=latest_transaction_dates_by_document,
            latest_transaction_dates_by_account_label=latest_transaction_dates_by_account_label,
            closed_household_account_ids=closed_household_account_ids,
            linked_portfolio_ids=linked_portfolio_ids,
            linked_tracked_ids=linked_tracked_ids,
        )
        if summary is None:
            continue
        summaries.append(summary)
        _track_duplicate_candidate(summary, accounts, documents_by_id, duplicate_candidates)

    for account in portfolio_accounts:
        if getattr(account, "account_type", None) == "paper" or account.id in linked_portfolio_ids:
            continue
        summaries.append(
            _build_portfolio_summary(
                account,
                account_valuations=account_valuations,
                source_owned_household_account_ids=source_owned_household_account_ids,
                source_owned_account_values=source_owned_account_values,
                holdings_by_account=holdings_by_account,
            )
        )

    for account in tracked_accounts:
        if account.id in linked_tracked_ids:
            continue
        portfolio_account = tracked_portfolio_matches.get(account.id)
        if portfolio_account is None:
            continue
        summaries.append(_build_tracked_summary(account, portfolio_account))

    duplicate_ids = {
        summary_id
        for ids in duplicate_candidates.values()
        if len(ids) > 1
        for summary_id in ids
    }
    return _finalize_summaries(summaries, documents_by_id, statement_freshness, duplicate_ids)


def _track_duplicate_candidate(
    summary: HouseholdAccountSummary,
    accounts: list[HouseholdEvidenceAccount],
    documents_by_id: dict[str, HouseholdDocument],
    duplicate_candidates: defaultdict[tuple[str, str, str, str], list[str]],
) -> None:
    latest = max(
        accounts,
        key=lambda a: (
            _latest_evidence_timestamp(a, documents_by_id.get(a.document_id)) or datetime.min.replace(tzinfo=UTC),
            float(a.confidence or 0.0),
        ),
    )
    duplicate_key = (
        _normalize_text(summary.institution_name),
        summary.asset_group,
        _normalize_text(summary.owner_name),
        _duplicate_label_key(summary.label),
    )
    if duplicate_key[0] and duplicate_key[3] and latest.account_mask is None:
        duplicate_candidates[duplicate_key].append(summary.id)


def _finalize_summaries(
    summaries: list[HouseholdAccountSummary],
    documents_by_id: dict[str, HouseholdDocument],
    statement_freshness: dict[str, Any],
    duplicate_ids: set[str],
) -> list[HouseholdAccountSummary]:
    finalized: list[HouseholdAccountSummary] = []
    for summary in summaries:
        latest_document = (
            documents_by_id.get(summary.latest_document_id) if summary.latest_document_id else None
        )
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
