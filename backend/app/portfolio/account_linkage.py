"""Portfolio-to-household account linkage classification."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from app.services._money_workspace_routes import (
    MONEY_ACCOUNT_COVERAGE_ROUTE,
    money_account_focus_route,
)

HouseholdLinkageState = Literal[
    "linked",
    "standalone_by_design",
    "unmapped",
    "duplicate_candidate",
    "stale_evidence",
]

_INVESTMENT_ACCOUNT_GROUPS = {"retirement", "taxable", "education"}
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
    "brokerage",
    "cash",
    "fidelity",
    "fund",
    "investment",
    "ira",
    "joint",
    "management",
    "portfolio",
    "retirement",
    "roth",
    "taxable",
    "traditional",
}


@dataclass(frozen=True)
class AccountLinkage:
    """Household evidence state for one portfolio account."""

    state: HouseholdLinkageState
    label: str
    detail: str | None = None
    action_href: str | None = None
    candidate_count: int = 0
    candidate_ids: list[str] = field(default_factory=list)


def build_account_linkages(
    portfolio_accounts: Iterable[Any],
    household_accounts: Iterable[Any],
) -> dict[str, AccountLinkage]:
    """Classify every portfolio account against Money household account evidence."""
    household_account_list = list(household_accounts)
    return {
        str(account.id): classify_account_linkage(
            account,
            household_account_list,
        )
        for account in portfolio_accounts
    }


def classify_account_linkage(
    portfolio_account: Any,
    household_accounts: Iterable[Any],
) -> AccountLinkage:
    """Return deterministic household linkage state for a portfolio account."""
    account_id = str(getattr(portfolio_account, "id", "") or "")
    account_name = _normalize(getattr(portfolio_account, "name", ""))
    account_type = str(getattr(portfolio_account, "account_type", "") or "")
    household_account_id = str(getattr(portfolio_account, "household_account_id", "") or "")
    asset_group = _PORTFOLIO_ACCOUNT_GROUPS.get(account_type)
    household_account_list = list(household_accounts)

    if account_type == "paper":
        return AccountLinkage(
            state="standalone_by_design",
            label="Standalone by design",
            detail="Paper account excluded from household evidence reconciliation.",
        )

    direct_matches = [
        account
        for account in household_account_list
        if _linked_portfolio_account_id(account) == account_id
        or (household_account_id and _household_account_id(account) == household_account_id)
    ]
    if direct_matches:
        return _direct_linkage(direct_matches[0])

    if household_account_id:
        return AccountLinkage(
            state="stale_evidence",
            label="Linked evidence unavailable",
            detail="This account has a stored Money account link, but the household account was not returned by Money Accounts.",
            action_href=MONEY_ACCOUNT_COVERAGE_ROUTE,
        )

    candidates = _candidate_accounts(
        account_name=account_name,
        asset_group=asset_group,
        household_accounts=household_account_list,
    )
    if candidates:
        candidate_ids = [_household_account_id(account) for account in candidates]
        labels = [_household_label(account) for account in candidates[:2]]
        label_text = "; ".join(label for label in labels if label)
        suffix = f": {label_text}" if label_text else ""
        action_account_id = candidate_ids[0] if candidate_ids else None
        return AccountLinkage(
            state="duplicate_candidate",
            label="Possible household match",
            detail=(
                f"Found {len(candidates)} unlinked Money account candidate"
                f"{'' if len(candidates) == 1 else 's'}{suffix}. Confirm the link in Money Accounts."
            ),
            action_href=(
                money_account_focus_route(action_account_id, intent="review")
                if action_account_id
                else MONEY_ACCOUNT_COVERAGE_ROUTE
            ),
            candidate_count=len(candidates),
            candidate_ids=candidate_ids,
        )

    return AccountLinkage(
        state="unmapped",
        label="Unmapped investment account",
        detail="Included in holdings totals, but Money Accounts has no linked household evidence.",
        action_href=MONEY_ACCOUNT_COVERAGE_ROUTE,
    )


def _direct_linkage(household_account: Any) -> AccountLinkage:
    freshness_status = _household_freshness_status(household_account)
    freshness_label = _household_freshness_label(household_account)
    label = _household_label(household_account)
    account_id = _household_account_id(household_account)
    if freshness_status in {"stale", "needs_evidence"} or not _has_household_evidence(household_account):
        return AccountLinkage(
            state="stale_evidence",
            label="Linked stale evidence",
            detail=(
                f"Money Accounts links this to {label}, but current evidence is "
                f"{freshness_label.lower()}."
            ),
            action_href=money_account_focus_route(account_id, intent="evidence"),
            candidate_count=1,
            candidate_ids=[account_id],
        )
    return AccountLinkage(
        state="linked",
        label="Linked household account",
        detail=f"Money Accounts links this to {label}. Evidence is {freshness_label.lower()}.",
        action_href=money_account_focus_route(account_id, intent="review"),
        candidate_count=1,
        candidate_ids=[account_id],
    )


def _candidate_accounts(
    *,
    account_name: str,
    asset_group: str | None,
    household_accounts: list[Any],
) -> list[Any]:
    scored: list[tuple[int, str, Any]] = []
    for household_account in household_accounts:
        household_asset_group = _normalize(getattr(household_account, "asset_group", ""))
        if household_asset_group not in _INVESTMENT_ACCOUNT_GROUPS:
            continue
        if asset_group and household_asset_group != asset_group:
            continue
        score = _candidate_score(account_name, household_account)
        if score <= 0:
            continue
        scored.append((score, _household_label(household_account), household_account))
    scored.sort(key=lambda item: (-item[0], item[1], _household_account_id(item[2])))
    return [account for _, _, account in scored]


def _candidate_score(account_name: str, household_account: Any) -> int:
    label_candidates = [
        _normalize(_household_label(household_account)),
        _normalize(getattr(household_account, "linked_portfolio_account_name", "")),
        _normalize(getattr(household_account, "institution_name", "")),
    ]
    label_candidates = [label for label in label_candidates if label]
    if account_name and account_name in label_candidates:
        return 100
    if any(_label_contains(left=account_name, right=label) for label in label_candidates):
        return 70
    account_mask = _normalize(getattr(household_account, "account_mask", ""))
    if account_mask and account_mask in account_name:
        return 80
    account_tokens = _match_tokens(account_name)
    household_tokens = set()
    for label in label_candidates:
        household_tokens.update(_match_tokens(label))
    shared_tokens = account_tokens & household_tokens
    if len(shared_tokens) >= 2:
        return 40 + len(shared_tokens)
    return 0


def _household_account_id(account: Any) -> str:
    return str(
        getattr(account, "household_account_id", None)
        or getattr(account, "id", None)
        or ""
    )


def _linked_portfolio_account_id(account: Any) -> str:
    return str(getattr(account, "linked_portfolio_account_id", "") or "")


def _household_label(account: Any) -> str:
    return str(getattr(account, "label", None) or getattr(account, "id", "Money account"))


def _household_freshness_status(account: Any) -> str:
    return _normalize(
        getattr(account, "freshness_status", None)
        or getattr(account, "balance_freshness_status", None)
        or "needs_evidence"
    )


def _household_freshness_label(account: Any) -> str:
    return str(
        getattr(account, "freshness_label", None)
        or getattr(account, "balance_freshness_label", None)
        or "Needs evidence"
    )


def _has_household_evidence(account: Any) -> bool:
    evidence_count = int(getattr(account, "evidence_count", 0) or 0)
    return (
        evidence_count > 0
        or bool(getattr(account, "document_ids", None))
        or bool(getattr(account, "last_evidence_at", None))
        or bool(getattr(account, "last_balance_at", None))
    )


def _normalize(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _label_contains(*, left: str, right: str) -> bool:
    if len(left) < 5 or len(right) < 5:
        return False
    return left in right or right in left


def _match_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", _normalize(value))
        if len(token) >= 3 and token not in _MATCH_TOKEN_STOPWORDS
    }
