"""Upload account binding and account-matching helpers for the household document pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.household_finance import HouseholdDocument
from app.services.household_account_identity import (
    account_masks_match,
    normalize_account_mask,
)

if TYPE_CHECKING:
    from app.services.household_finance_service import HouseholdFinanceService


# ---------------------------------------------------------------------------
# Scalar helpers
# ---------------------------------------------------------------------------


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _string_value(value: object) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


# ---------------------------------------------------------------------------
# Account mask helpers
# ---------------------------------------------------------------------------


def _account_mask_values(account: dict[str, object]) -> list[object]:
    return [
        value
        for key in ("account_mask", "extracted_account_mask")
        if normalize_account_mask(value := account.get(key))
    ]


def _account_matches_mask(account: dict[str, object], target_mask: object) -> bool:
    return any(account_masks_match(mask, target_mask) for mask in _account_mask_values(account))


# ---------------------------------------------------------------------------
# Document metadata helper
# ---------------------------------------------------------------------------


def _metadata_household_account_id(document: HouseholdDocument) -> str | None:
    metadata = document.metadata if isinstance(document.metadata, dict) else {}
    raw = metadata.get("upload_household_account_id") or metadata.get("household_account_id")
    text = str(raw).strip() if raw is not None else ""
    return text or None


# ---------------------------------------------------------------------------
# DB fetch
# ---------------------------------------------------------------------------


def _target_account_for_upload(
    service: HouseholdFinanceService,
    *,
    household_account_id: str,
) -> dict[str, object] | None:
    with service.storage.connection() as conn:
        row = conn.execute(
            """
            SELECT
                id,
                canonical_label,
                source_type,
                asset_group,
                account_type,
                institution_name,
                owner_name,
                account_mask,
                primary_identity_key
            FROM household_accounts
            WHERE id = %s
            LIMIT 1
            """,
            [household_account_id],
        ).fetchone()
    if row is None:
        return None
    return {
        "household_account_id": str(row[0]),
        "canonical_label": str(row[1] or ""),
        "source_type": str(row[2] or ""),
        "asset_group": str(row[3] or ""),
        "account_type": str(row[4] or ""),
        "institution_name": str(row[5] or "") or None,
        "owner_name": str(row[6] or "") or None,
        "account_mask": str(row[7] or "") or None,
        "primary_identity_key": str(row[8] or "") or None,
    }


# ---------------------------------------------------------------------------
# Conflict / matching logic
# ---------------------------------------------------------------------------


def _account_conflicts_with_target(
    account: dict[str, object],
    target: dict[str, object],
) -> list[str]:
    conflicts: list[str] = []
    target_mask = target.get("account_mask")
    if (
        _account_mask_values(account)
        and normalize_account_mask(target_mask)
        and not _account_matches_mask(account, target_mask)
    ):
        conflicts.append("account_mask")

    account_source = _clean_text(account.get("source_type"))
    target_source = _clean_text(target.get("source_type"))
    if account_source and target_source and account_source != target_source:
        conflicts.append("source_type")

    account_type = _clean_text(account.get("account_type"))
    target_type = _clean_text(target.get("account_type"))
    if account_type and target_type and account_type != target_type:
        conflicts.append("account_type")

    return conflicts


def _account_matches_target(
    account: dict[str, object],
    target: dict[str, object],
) -> bool:
    if _account_conflicts_with_target(account, target):
        return False
    if _account_matches_mask(account, target.get("account_mask")):
        return True
    account_name = _clean_text(account.get("account_name") or account.get("account_hint"))
    target_label = _clean_text(target.get("canonical_label"))
    if account_name and target_label and (
        account_name in target_label or target_label in account_name
    ):
        return True
    account_institution = _clean_text(
        account.get("institution_name") or account.get("institution")
    )
    target_institution = _clean_text(target.get("institution_name"))
    return bool(
        account_institution and target_institution and account_institution == target_institution
    )


# ---------------------------------------------------------------------------
# Binding mutations
# ---------------------------------------------------------------------------


def _bind_account_to_upload_target(
    account: dict[str, object],
    target: dict[str, object],
) -> None:
    account["household_account_id"] = target["household_account_id"]
    if target.get("primary_identity_key") and not account.get("match_key"):
        account["match_key"] = target["primary_identity_key"]
    for account_key, target_key in (
        ("source_type", "source_type"),
        ("asset_group", "asset_group"),
        ("account_type", "account_type"),
        ("institution_name", "institution_name"),
        ("owner_name", "owner_name"),
        ("account_mask", "account_mask"),
    ):
        if not account.get(account_key) and target.get(target_key):
            account[account_key] = target[target_key]
    if not account.get("account_name") and target.get("canonical_label"):
        account["account_name"] = target["canonical_label"]


def _clear_upload_binding_ambiguity(reviewed: dict[str, object]) -> None:
    reviewed["questions"] = []
    review_checks = (
        dict(reviewed.get("review_checks"))
        if isinstance(reviewed.get("review_checks"), dict)
        else {}
    )
    review_checks["ambiguity_remaining"] = False
    review_checks.pop("ambiguity_reason", None)
    reviewed["review_checks"] = review_checks


def _upload_target_question(
    *,
    target: dict[str, object],
    reason: str,
) -> dict[str, object]:
    target_label = str(target.get("canonical_label") or "the selected account")
    return {
        "field_name": None,
        "question": (
            f"This upload was sent to {target_label}, but Jenny could not safely "
            f"attach it there because {reason}. Which account should this evidence update?"
        ),
        "priority": "high",
        "question_format": "long_text",
        "recommendation": "Confirm the correct account or upload the matching account evidence.",
        "rationale": "Account-scoped uploads must not silently update the wrong account.",
    }


def _append_upload_binding_question(
    reviewed: dict[str, object],
    *,
    target: dict[str, object],
    reason: str,
) -> None:
    questions = reviewed.get("questions")
    if not isinstance(questions, list):
        questions = []
    question = _upload_target_question(target=target, reason=reason)
    if not any(
        isinstance(item, dict) and item.get("question") == question["question"]
        for item in questions
    ):
        questions.append(question)
    reviewed["questions"] = questions
    review_checks = (
        dict(reviewed.get("review_checks"))
        if isinstance(reviewed.get("review_checks"), dict)
        else {}
    )
    review_checks["ambiguity_remaining"] = True
    review_checks["ambiguity_reason"] = reason
    reviewed["review_checks"] = review_checks


# ---------------------------------------------------------------------------
# Single-account binding path
# ---------------------------------------------------------------------------


def _bind_single_account(
    reviewed: dict[str, object],
    account: dict[str, object],
    target: dict[str, object],
) -> dict[str, object]:
    conflicts = _account_conflicts_with_target(account, target)
    if conflicts:
        _append_upload_binding_question(
            reviewed,
            target=target,
            reason=f"document {', '.join(conflicts)} did not match the selected account",
        )
        return reviewed
    _bind_account_to_upload_target(account, target)
    _clear_upload_binding_ambiguity(reviewed)
    return reviewed


# ---------------------------------------------------------------------------
# Multi-account binding path
# ---------------------------------------------------------------------------


def _bind_multiple_accounts(
    reviewed: dict[str, object],
    account_dicts: list[dict[str, object]],
    target: dict[str, object],
) -> dict[str, object]:
    bound_count = 0
    for account in account_dicts:
        if _account_matches_target(account, target):
            _bind_account_to_upload_target(account, target)
            bound_count += 1
    if bound_count == 0:
        _append_upload_binding_question(
            reviewed,
            target=target,
            reason="none of the parsed accounts matched the selected account",
        )
    else:
        _clear_upload_binding_ambiguity(reviewed)
    return reviewed


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def apply_upload_account_binding(
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
) -> dict[str, object]:
    """Resolve upload target account and bind reviewed accounts to it."""
    household_account_id = _metadata_household_account_id(document)
    if household_account_id is None:
        return reviewed
    target = _target_account_for_upload(service, household_account_id=household_account_id)
    if target is None:
        return reviewed

    reviewed = dict(reviewed)
    structured_data = reviewed.get("structured_data")
    structured_data = dict(structured_data) if isinstance(structured_data, dict) else {}
    reviewed["structured_data"] = structured_data
    structured_data["upload_household_account_id"] = household_account_id
    structured_data["upload_account_label"] = target.get("canonical_label")

    raw_accounts = structured_data.get("financial_accounts")
    if not isinstance(raw_accounts, list) or not raw_accounts:
        _append_upload_binding_question(
            reviewed,
            target=target,
            reason="the document did not expose an account identity or balance row",
        )
        return reviewed

    accounts = [
        dict(account) if isinstance(account, dict) else account
        for account in raw_accounts
    ]
    structured_data["financial_accounts"] = accounts
    account_dicts = [a for a in accounts if isinstance(a, dict)]

    if len(account_dicts) == 1:
        return _bind_single_account(reviewed, account_dicts[0], target)
    return _bind_multiple_accounts(reviewed, account_dicts, target)
