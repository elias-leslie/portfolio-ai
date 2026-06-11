"""Account matching for household account summaries.

Provides `_match_tracked_account` and `_match_portfolio_account` which map
evidence/tracked accounts to their canonical tracked or portfolio counterparts.
"""

from __future__ import annotations

from typing import Any

from app.models.household_finance import HouseholdTrackedAccount
from app.services._household_account_summary_utils import (
    _allows_unique_institution_fallback,
    _compact_key,
    _match_tokens,
    _normalize_text,
    _owner_is_household_scope,
    _owners_match,
    _portfolio_asset_group,
    _portfolio_label,
)


def _unique_institution_match(
    *,
    identity_locked: bool,
    normalized_institution: str,
    tracked_institution: str,
    account: HouseholdTrackedAccount,
    same_institution_candidates: list[HouseholdTrackedAccount],
    tracked_tokens: set[str],
    evidence_tokens: set[str],
    normalized_owner: str,
    tracked_owner: str,
    asset_group: str,
    account_type: str | None,
    label: str,
    account_name: str | None,
    hint_label: str | None,
    institution_name: str | None,
) -> bool:
    """True if the account matches via unique-institution fallback (score 2)."""
    if not (
        not identity_locked
        and normalized_institution
        and tracked_institution == normalized_institution
        and account.account_mask is None
        and len(same_institution_candidates) == 1
        and len(tracked_tokens & evidence_tokens) >= 1
    ):
        return False
    if not _allows_unique_institution_fallback(
        asset_group=asset_group,
        account_type=account_type,
        label=label,
        account_name=account_name,
        hint_label=hint_label,
        institution_name=institution_name,
    ):
        return False
    return (
        not normalized_owner
        or not tracked_owner
        or _owners_match(tracked_owner, normalized_owner)
        or _owner_is_household_scope(account.owner_name)
    )


def _score_tracked_candidate(
    *,
    account: HouseholdTrackedAccount,
    group_key: str,
    normalized_asset_group: str,
    normalized_institution: str,
    normalized_owner: str,
    label_candidates: set[str],
    evidence_tokens: set[str],
    evidence_signature: str,
    same_institution_candidates: list[HouseholdTrackedAccount],
    asset_group: str,
    account_type: str | None,
    label: str,
    account_name: str | None,
    hint_label: str | None,
    institution_name: str | None,
) -> int:
    """Return a match score (0 = no match) for one tracked account candidate."""
    if _normalize_text(account.asset_group) != normalized_asset_group:
        return 0

    tracked_institution = _normalize_text(account.institution_name)
    tracked_owner = _normalize_text(account.owner_name)
    tracked_tokens = _match_tokens(account.label, account.institution_name)
    identity_locked = bool(account.match_key or account.account_mask)

    if account.match_key and _normalize_text(account.match_key) == _normalize_text(group_key):
        return 5
    if (
        evidence_signature
        and account.institution_name
        and account.account_mask
        and _compact_key(account.institution_name, account.account_mask) == evidence_signature
    ):
        return 4
    if (
        not identity_locked
        and normalized_institution
        and normalized_owner
        and tracked_institution == normalized_institution
        and _owners_match(tracked_owner, normalized_owner)
    ):
        return 3
    label_hit = not identity_locked and _normalize_text(account.label) in label_candidates
    institution_hit = _unique_institution_match(
        identity_locked=identity_locked,
        normalized_institution=normalized_institution,
        tracked_institution=tracked_institution,
        account=account,
        same_institution_candidates=same_institution_candidates,
        tracked_tokens=tracked_tokens,
        evidence_tokens=evidence_tokens,
        normalized_owner=normalized_owner,
        tracked_owner=tracked_owner,
        asset_group=asset_group,
        account_type=account_type,
        label=label,
        account_name=account_name,
        hint_label=hint_label,
        institution_name=institution_name,
    )
    if label_hit or institution_hit:
        return 2
    owner_conflict = normalized_owner and tracked_owner and not _owners_match(tracked_owner, normalized_owner)
    token_hit = not identity_locked and len(tracked_tokens & evidence_tokens) >= 2 and not owner_conflict
    return 1 if token_hit else 0


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
        score = _score_tracked_candidate(
            account=account,
            group_key=group_key,
            normalized_asset_group=normalized_asset_group,
            normalized_institution=normalized_institution,
            normalized_owner=normalized_owner,
            label_candidates=label_candidates,
            evidence_tokens=evidence_tokens,
            evidence_signature=evidence_signature,
            same_institution_candidates=same_institution_candidates,
            asset_group=asset_group,
            account_type=account_type,
            label=label,
            account_name=account_name,
            hint_label=hint_label,
            institution_name=institution_name,
        )
        if score > 0:
            ranked.append((score, account))

    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1].updated_at))
    top_score = ranked[0][0]
    best = [account for score, account in ranked if score == top_score]
    return best[0] if len(best) == 1 else None


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
        # An account FK-linked to a household account is claimed; it must not
        # be label-matched to a different household account (two same-label
        # accounts, e.g. his/hers FRS plans, would otherwise collapse onto one
        # valuation).
        if not str(getattr(account, "household_account_id", "") or "")
        and _portfolio_asset_group(account) == asset_group
        and _normalize_text(_portfolio_label(account)) in {normalized_label, normalized_account_name}
    ]
    return matches[0] if len(matches) == 1 else None
