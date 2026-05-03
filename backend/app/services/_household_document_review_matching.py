"""Household document account reconciliation helpers."""

from __future__ import annotations

import re
from typing import Any

from app.services._household_document_review_context import _CONTEXT_STOPWORDS
from app.services.household_account_identity import (
    account_identity_candidates,
    clean_text,
    derive_account_mask,
)

_GENERIC_ACCOUNT_NAME_TERMS = frozenset(
    {
        "account",
        "activity",
        "card",
        "credit",
        "document",
        "export",
        "history",
        "statement",
        "transactions",
        "upload",
    }
)

_STATEMENT_DOCUMENT_TYPES = frozenset({"statement", "brokerage_statement", "retirement_statement"})


def _normalize_match_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _name_tokens(*values: object) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        normalized = _normalize_match_text(value)
        if not normalized:
            continue
        for token in re.split(r"[^a-z0-9]+", normalized):
            if len(token) < 3 or token in _CONTEXT_STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def _owner_matches(left: object, right: object) -> bool:
    left_tokens = [token for token in re.split(r"[^a-z0-9]+", _normalize_match_text(left)) if token]
    right_tokens = [token for token in re.split(r"[^a-z0-9]+", _normalize_match_text(right)) if token]
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    if left_tokens[0] != right_tokens[0]:
        return False
    return len(left_tokens) > 1 and len(right_tokens) > 1 and left_tokens[-1] == right_tokens[-1]


def _looks_generic_account_name(value: object) -> bool:
    tokens = _name_tokens(value)
    return bool(tokens) and tokens <= _GENERIC_ACCOUNT_NAME_TERMS


def _identity_examples(related: dict[str, Any]) -> set[str]:
    return {
        _normalize_match_text(identity)
        for identity in related.get("identity_examples", [])
        if _normalize_match_text(identity)
    }


def _score_related_account(
    *,
    related: dict[str, Any],
    explicit_match_key: str,
    candidate_keys: set[str],
    raw_mask: str,
    filename_mask: str,
    raw_institution: str,
    raw_owner: str,
    raw_account_type: str,
    raw_asset_group: str,
    raw_name_tokens: set[str],
) -> dict[str, Any] | None:
    score = 0
    method = "tokens"
    primary_identity_key = _normalize_match_text(related.get("primary_identity_key"))
    related_mask = _normalize_match_text(related.get("account_mask"))
    related_institution = _normalize_match_text(related.get("institution_name"))
    related_owner = related.get("owner_name")
    related_account_type = _normalize_match_text(related.get("account_type"))
    related_asset_group = _normalize_match_text(related.get("asset_group"))
    related_name_tokens = _name_tokens(related.get("canonical_label"), related.get("institution_name"))

    if explicit_match_key and primary_identity_key and explicit_match_key == primary_identity_key:
        score += 120
        method = "explicit_match_key"
    elif primary_identity_key and primary_identity_key in candidate_keys:
        score += 85
        method = "primary_identity"

    overlap = candidate_keys & _identity_examples(related)
    if overlap:
        score += 50 + (len(overlap) - 1) * 10
        if method == "tokens":
            method = "identity_example"

    if raw_mask and related_mask and _normalize_match_text(raw_mask) == related_mask:
        score += 60
        if method == "tokens":
            method = "mask"
    elif filename_mask and related_mask and _normalize_match_text(filename_mask) == related_mask:
        score += 55
        if method == "tokens":
            method = "filename_mask"

    if raw_institution and related_institution and _normalize_match_text(raw_institution) == related_institution:
        score += 18
    if raw_owner and _owner_matches(raw_owner, related_owner):
        score += 12
    if raw_account_type and related_account_type and _normalize_match_text(raw_account_type) == related_account_type:
        score += 10
    if raw_asset_group and related_asset_group and _normalize_match_text(raw_asset_group) == related_asset_group:
        score += 6

    shared_name_tokens = raw_name_tokens & related_name_tokens
    if shared_name_tokens:
        score += min(len(shared_name_tokens) * 6, 24)

    if score < 40:
        return None
    return {"related_account": related, "score": score, "method": method}


def _select_best_match(scored: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not scored:
        return None
    scored.sort(key=lambda item: item["score"], reverse=True)
    best = scored[0]
    next_score = scored[1]["score"] if len(scored) > 1 else -1
    if int(best["score"]) >= 120:
        return best
    if int(best["score"]) >= 70 and int(best["score"]) >= next_score + 10:
        return best
    return None


def best_related_account_match(
    *,
    raw_account: dict[str, Any],
    related_accounts: list[dict[str, Any]],
    default_source_type: str,
    default_document_type: str,
    filename: str,
) -> dict[str, Any] | None:
    explicit_match_key = _normalize_match_text(raw_account.get("match_key"))
    raw_account_name = clean_text(raw_account.get("account_name")) or clean_text(raw_account.get("account_hint"))
    filename_mask = clean_text(derive_account_mask(None, raw_account_name, filename))
    raw_mask = clean_text(
        derive_account_mask(
            clean_text(raw_account.get("account_mask")),
            raw_account_name,
            filename,
        )
    )
    raw_institution = clean_text(raw_account.get("institution_name"))
    raw_owner = clean_text(raw_account.get("owner_name"))
    raw_account_type = clean_text(raw_account.get("account_type"))
    raw_asset_group = clean_text(raw_account.get("asset_group"))
    candidate_keys = set(
        account_identity_candidates(
            source_type=raw_account.get("source_type") or default_source_type,
            asset_group=raw_asset_group,
            account_type=raw_account_type,
            institution_name=raw_institution,
            account_name=raw_account_name,
            owner_name=raw_owner,
            account_mask=raw_mask,
            fallback_label=raw_account_name,
            explicit_match_key=explicit_match_key or None,
        )
    )
    if not candidate_keys and default_document_type not in _STATEMENT_DOCUMENT_TYPES:
        return None

    raw_tokens = _name_tokens(raw_account_name, raw_account.get("institution_name"), raw_account.get("account_hint"))
    scored = [
        score
        for related in related_accounts
        if isinstance(related, dict)
        for score in [
            _score_related_account(
                related=related,
                explicit_match_key=explicit_match_key,
                candidate_keys=candidate_keys,
                raw_mask=raw_mask,
                filename_mask=filename_mask,
                raw_institution=raw_institution,
                raw_owner=raw_owner,
                raw_account_type=raw_account_type,
                raw_asset_group=raw_asset_group,
                raw_name_tokens=raw_tokens,
            )
        ]
        if score is not None
    ]
    return _select_best_match(scored)
