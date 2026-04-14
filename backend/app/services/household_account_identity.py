"""Shared household-account identity helpers."""

from __future__ import annotations

import re
from pathlib import Path


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).strip().split())
    return cleaned or None


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def compact_key(*parts: object) -> str:
    return "|".join(part for raw in parts if (part := normalize_text(raw)))


def derive_account_mask(
    account_mask: str | None,
    account_name: str | None,
    fallback_label: str | None = None,
) -> str | None:
    normalized_mask = clean_text(account_mask)
    if normalized_mask:
        return normalized_mask
    candidates = [clean_text(account_name), clean_text(fallback_label)]
    for normalized_name in candidates:
        if not normalized_name:
            continue
        match = re.search(r"(?:#|acct(?:ount)?\s*)([A-Za-z0-9]{4,})", normalized_name, flags=re.IGNORECASE)
        if match is not None:
            return match.group(1)
        stem = Path(normalized_name).stem
        digit_tokens = [
            token for token in re.findall(r"[A-Za-z0-9]{4,}", stem)
            if any(char.isdigit() for char in token)
        ]
        for token in reversed(digit_tokens):
            if re.fullmatch(r"\d{8}", token):
                continue
            return token
    return None


def legacy_evidence_match_key(
    *,
    source_type: str | None,
    asset_group: str | None,
    account_type: str | None,
    institution_name: str | None,
    account_name: str | None,
    owner_name: str | None,
    account_mask: str | None,
    fallback_label: str | None = None,
) -> str | None:
    institution = normalize_text(institution_name)
    name = normalize_text(account_name) or normalize_text(fallback_label)
    owner = normalize_text(owner_name)
    mask = normalize_text(derive_account_mask(account_mask, account_name, fallback_label))
    account_kind = normalize_text(account_type) or normalize_text(asset_group) or normalize_text(source_type)
    if mask:
        return compact_key("evidence", mask, account_kind)
    if institution and name and owner:
        return compact_key("evidence", institution, name, owner, account_kind)
    if institution and name:
        return compact_key("evidence", institution, name, account_kind)
    if name and owner:
        return compact_key("evidence", name, owner, account_kind)
    if name:
        return compact_key("evidence", name, account_kind)
    return None


def _owner_aliases(owner_name: str | None) -> list[str]:
    normalized = normalize_text(owner_name)
    if not normalized:
        return []
    aliases = [normalized]
    first = normalized.split()[0]
    if first and first not in aliases:
        aliases.append(first)
    return aliases


def _credit_lineage_key(
    *,
    source_type: str | None,
    account_type: str | None,
    institution_name: str | None,
    account_name: str | None,
    owner_name: str | None,
    fallback_label: str | None = None,
) -> str | None:
    source = normalize_text(source_type)
    account_kind = normalize_text(account_type)
    if source != "credit_card" and account_kind != "credit_card":
        return None
    institution = normalize_text(institution_name)
    name = normalize_text(account_name) or normalize_text(fallback_label)
    owner = normalize_text(owner_name)
    if not institution or not name or not owner:
        return None
    return compact_key("credit-lineage", institution, name, owner, account_kind or source or "credit_card")


def account_identity_candidates(
    *,
    source_type: str | None,
    asset_group: str | None,
    account_type: str | None,
    institution_name: str | None,
    account_name: str | None,
    owner_name: str | None,
    account_mask: str | None,
    fallback_label: str | None = None,
    explicit_match_key: str | None = None,
) -> list[str]:
    source = normalize_text(source_type)
    asset = normalize_text(asset_group)
    account_kind = normalize_text(account_type) or asset or source
    institution = normalize_text(institution_name)
    name = normalize_text(account_name) or normalize_text(fallback_label)
    owner = normalize_text(owner_name)
    mask = normalize_text(derive_account_mask(account_mask, account_name, fallback_label))

    candidates: list[str] = []

    def add(value: str | None) -> None:
        normalized = normalize_text(value)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    add(
        _credit_lineage_key(
            source_type=source_type,
            account_type=account_type,
            institution_name=institution_name,
            account_name=account_name,
            owner_name=owner_name,
            fallback_label=fallback_label,
        )
    )
    if institution and mask:
        add(f"institution-mask::{institution}|{mask}")
    if mask:
        add(f"mask::{mask}|{asset}|{account_kind}")
        add(f"mask-asset::{mask}|{asset}")
    for owner_alias in _owner_aliases(owner_name):
        if institution and name:
            add(f"institution-name-owner::{institution}|{name}|{owner_alias}|{asset}|{account_kind}")
        if name:
            add(f"name-owner::{name}|{owner_alias}|{asset}|{account_kind}")
    if institution and name and not owner:
        add(f"institution-name::{institution}|{name}|{asset}|{account_kind}")
    add(
        legacy_evidence_match_key(
            source_type=source_type,
            asset_group=asset_group,
            account_type=account_type,
            institution_name=institution_name,
            account_name=account_name,
            owner_name=owner_name,
            account_mask=account_mask,
            fallback_label=fallback_label,
        )
    )
    add(explicit_match_key)
    add(f"match::{explicit_match_key}" if explicit_match_key else None)
    return candidates
