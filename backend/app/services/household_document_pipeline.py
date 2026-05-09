"""Document intake, review persistence, and import helpers for household finance."""

from __future__ import annotations

import hashlib
import json
import uuid
from csv import DictReader
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fastapi import UploadFile

from app.logging_config import get_logger
from app.models.household_finance import HouseholdDocument
from app.services._household_document_pipeline_db import (
    archive_prior_document_data,
    dismiss_open_document_questions,
    fetch_document_application_counts,
    fetch_duplicate_document_row,
    insert_document_db,
    insert_inferred_values,
    insert_questions,
    mark_review_failed,
    save_upload_to_disk,
    update_document_and_log_review,
    update_document_application_summary,
    update_import_summary,
    upsert_import_row,
    upsert_signature_record,
)
from app.services._household_document_pipeline_utils import (
    build_import_row_hash,
    classify_document,
    detect_import_dataset,
    normalize_financial_document_classification,
    parse_decimal,
    parse_row_date,
)
from app.services._household_finance_utils import iso, iso_or_none, to_float
from app.services.household_finance_rows import FIELD_LABELS, row_to_document
from app.services.household_review_agent_service import HOUSEHOLD_REVIEW_AGENT_SLUG
from app.services.household_upload_validation import (
    read_household_upload_limited,
    validate_household_upload_metadata,
)

if TYPE_CHECKING:
    from app.services.household_finance_service import HouseholdFinanceService

logger = get_logger(__name__)

# Re-export pure utilities at module level for any direct importers.
__all__ = [
    "HouseholdDocumentPipeline",
    "build_import_row_hash",
    "classify_document",
    "detect_import_dataset",
    "parse_decimal",
    "parse_row_date",
]

_ACCOUNT_EVIDENCE_SOURCE_TYPES = frozenset({"bank", "credit_card", "brokerage", "retirement"})
_ACCOUNT_EVIDENCE_DOCUMENT_TYPES = frozenset(
    {"statement", "brokerage_statement", "retirement_statement"}
)
_MONEY_SIGNATURE_VOLATILE_FIELDS = frozenset(
    {
        "activity_observed_through",
        "as_of_date",
        "statement_period",
        "text_preview",
        "total_amount",
    }
)
_MONEY_SIGNATURE_ACCOUNT_VOLATILE_FIELDS = frozenset(
    {
        "activity_observed_through",
        "as_of_date",
        "balance",
        "cash_balance",
        "confidence",
        "holdings_value",
    }
)


def _structured_data_dict(reviewed: dict[str, object]) -> dict[str, object]:
    structured_data = reviewed.get("structured_data")
    return cast(dict[str, object], structured_data) if isinstance(structured_data, dict) else {}


def _should_merge_planning_items(reviewed: dict[str, object]) -> bool:
    source_type = str(reviewed.get("source_type") or "").strip()
    document_type = str(reviewed.get("document_type") or "").strip()
    structured_data = _structured_data_dict(reviewed)
    financial_accounts = structured_data.get("financial_accounts")
    has_financial_accounts = isinstance(financial_accounts, list) and bool(financial_accounts)
    if has_financial_accounts:
        return False
    return not (
        source_type in _ACCOUNT_EVIDENCE_SOURCE_TYPES
        and document_type in _ACCOUNT_EVIDENCE_DOCUMENT_TYPES
    )


def _review_checks_dict(reviewed: dict[str, object]) -> dict[str, object]:
    review_checks = reviewed.get("review_checks")
    return cast(dict[str, object], review_checks) if isinstance(review_checks, dict) else {}


def _int_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _reviewed_financial_accounts(reviewed: dict[str, object]) -> list[dict[str, object]]:
    structured_data = _structured_data_dict(reviewed)
    accounts = structured_data.get("financial_accounts")
    if not isinstance(accounts, list):
        return []
    return [cast(dict[str, object], account) for account in accounts if isinstance(account, dict)]


def _normalized_review_payload(
    *,
    reviewed: dict[str, object],
    document: HouseholdDocument,
) -> dict[str, object]:
    normalized = dict(reviewed)
    source_type, document_type = normalize_financial_document_classification(
        reviewed=normalized,
        fallback_source_type=document.source_type,
        fallback_document_type=document.document_type,
        filename=document.filename,
        extracted_text=(
            str(normalized.get("extracted_text"))
            if isinstance(normalized.get("extracted_text"), str)
            else None
        ),
    )
    normalized["source_type"] = source_type
    normalized["document_type"] = document_type
    return normalized


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _clean_mask(value: object) -> str:
    return "".join(char for char in str(value or "").lower() if char.isalnum())


def _mask_candidates(value: object) -> set[str]:
    cleaned = _clean_mask(value)
    if not cleaned:
        return set()
    candidates = {cleaned}
    digits = "".join(char for char in cleaned if char.isdigit())
    if len(digits) >= 4:
        candidates.add(digits)
        candidates.add(digits[-4:])
    return candidates


def _account_mask_candidates(account: dict[str, object]) -> set[str]:
    candidates: set[str] = set()
    for key in ("account_mask", "extracted_account_mask"):
        candidates.update(_mask_candidates(account.get(key)))
    return candidates


def _masks_match(left: set[str], right: set[str]) -> bool:
    if not left or not right:
        return False
    if left & right:
        return True
    return any(
        len(left_candidate) >= 4
        and len(right_candidate) >= 4
        and (
            left_candidate.endswith(right_candidate)
            or right_candidate.endswith(left_candidate)
        )
        for left_candidate in left
        for right_candidate in right
    )


def _metadata_household_account_id(document: HouseholdDocument) -> str | None:
    metadata = document.metadata if isinstance(document.metadata, dict) else {}
    raw = metadata.get("upload_household_account_id") or metadata.get("household_account_id")
    text = str(raw).strip() if raw is not None else ""
    return text or None


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


def _account_conflicts_with_target(
    account: dict[str, object],
    target: dict[str, object],
) -> list[str]:
    conflicts: list[str] = []
    account_masks = _account_mask_candidates(account)
    target_masks = _mask_candidates(target.get("account_mask"))
    if account_masks and target_masks and not _masks_match(account_masks, target_masks):
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
    conflicts = _account_conflicts_with_target(account, target)
    if conflicts:
        return False
    account_masks = _account_mask_candidates(account)
    target_masks = _mask_candidates(target.get("account_mask"))
    if _masks_match(account_masks, target_masks):
        return True
    account_name = _clean_text(account.get("account_name") or account.get("account_hint"))
    target_label = _clean_text(target.get("canonical_label"))
    if account_name and target_label and (
        account_name in target_label or target_label in account_name
    ):
        return True
    account_institution = _clean_text(account.get("institution_name") or account.get("institution"))
    target_institution = _clean_text(target.get("institution_name"))
    return bool(account_institution and target_institution and account_institution == target_institution)


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
    review_checks = dict(reviewed.get("review_checks")) if isinstance(reviewed.get("review_checks"), dict) else {}
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
    if not any(isinstance(item, dict) and item.get("question") == question["question"] for item in questions):
        questions.append(question)
    reviewed["questions"] = questions
    review_checks = dict(reviewed.get("review_checks")) if isinstance(reviewed.get("review_checks"), dict) else {}
    review_checks["ambiguity_remaining"] = True
    review_checks["ambiguity_reason"] = reason
    reviewed["review_checks"] = review_checks


def _apply_upload_account_binding(
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
) -> dict[str, object]:
    household_account_id = _metadata_household_account_id(document)
    if household_account_id is None:
        return reviewed
    target = _target_account_for_upload(
        service,
        household_account_id=household_account_id,
    )
    if target is None:
        return reviewed

    reviewed = dict(reviewed)
    structured_data = reviewed.get("structured_data")
    if not isinstance(structured_data, dict):
        structured_data = {}
    else:
        structured_data = dict(structured_data)
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
    account_dicts = [account for account in accounts if isinstance(account, dict)]
    if len(account_dicts) == 1:
        account = account_dicts[0]
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


def _signature_structured_data(reviewed: dict[str, object], document: HouseholdDocument) -> dict[str, object]:
    structured_data = _structured_data_dict(reviewed)
    if not structured_data:
        return {}
    source_type = str(reviewed.get("source_type") or document.source_type or "")
    if source_type not in _ACCOUNT_EVIDENCE_SOURCE_TYPES:
        return structured_data
    sanitized: dict[str, object] = {}
    for key, value in structured_data.items():
        if key in _MONEY_SIGNATURE_VOLATILE_FIELDS:
            continue
        if key == "financial_accounts" and isinstance(value, list):
            stable_accounts: list[dict[str, object]] = []
            for raw_account in value:
                if not isinstance(raw_account, dict):
                    continue
                stable_account = {
                    account_key: account_value
                    for account_key, account_value in raw_account.items()
                    if account_key not in _MONEY_SIGNATURE_ACCOUNT_VOLATILE_FIELDS
                    and account_value not in (None, "", [], {})
                }
                if stable_account:
                    stable_accounts.append(stable_account)
            if stable_accounts:
                sanitized[key] = stable_accounts
            continue
        if value not in (None, "", [], {}):
            sanitized[key] = value
    return sanitized


def _bool_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return None


def _is_duplicate_import_validation(
    *,
    import_summary: dict[str, object],
    transaction_summary: dict[str, object],
    evidence_account_count: int,
    planning_count: int,
    inferred_count: int,
) -> bool:
    inserted = int(import_summary.get("inserted") or 0)
    duplicates = int(import_summary.get("duplicates") or 0)
    dataset_type = str(import_summary.get("dataset_type") or "").strip()
    transaction_changes = int(transaction_summary.get("inserted") or 0) + int(
        transaction_summary.get("updated") or 0
    )
    return (
        inserted == 0
        and duplicates > 0
        and bool(dataset_type)
        and transaction_changes == 0
        and evidence_account_count == 0
        and planning_count == 0
        and inferred_count == 0
    )


class HouseholdDocumentPipeline:
    """Persist household uploads and review outcomes."""

    # Expose pure helpers as instance attributes for backward compatibility.
    classify_document = staticmethod(classify_document)
    parse_row_date = staticmethod(parse_row_date)
    parse_decimal = staticmethod(parse_decimal)
    detect_import_dataset = staticmethod(detect_import_dataset)
    build_import_row_hash = staticmethod(build_import_row_hash)

    async def ingest_document(
        self,
        service: HouseholdFinanceService,
        *,
        upload: UploadFile,
        source_type: str | None = None,
        document_type: str | None = None,
        account_label: str | None = None,
        household_account_id: str | None = None,
    ) -> HouseholdDocument:
        document_id = str(uuid.uuid4())
        filename = upload.filename or f"{document_id}.bin"
        validate_household_upload_metadata(upload)
        content = await read_household_upload_limited(upload)
        content_sha256 = hashlib.sha256(content).hexdigest()

        duplicate = self.find_duplicate_document_by_hash(service, content_sha256)
        if duplicate is not None:
            if household_account_id or account_label:
                rebound_metadata = {
                    "duplicate_rebound": True,
                    "duplicate_rebound_at": datetime.now(UTC).isoformat(),
                }
                if household_account_id:
                    rebound_metadata["upload_household_account_id"] = household_account_id
                with service.storage.connection() as conn:
                    conn.execute(
                        """
                        UPDATE household_documents
                        SET account_label = COALESCE(%s, account_label),
                            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                        WHERE id = %s
                        """,
                        [
                            account_label,
                            json.dumps(rebound_metadata),
                            duplicate.id,
                        ],
                    )
                    conn.commit()
                refreshed_duplicate = service.get_document(duplicate.id)
                if refreshed_duplicate is not None:
                    duplicate = refreshed_duplicate
            duplicate.metadata["duplicate_detected"] = True
            duplicate.metadata["duplicate_reason"] = "exact_content_match"
            return duplicate

        inferred_source, inferred_type, confidence = classify_document(
            filename=filename,
            content_type=upload.content_type,
            source_type=source_type,
            document_type=document_type,
        )
        upload_root = service._upload_root()
        stored_path = save_upload_to_disk(
            content, document_id=document_id, filename=filename,
            upload_dir=upload_root,
        )
        now = datetime.now(UTC).isoformat()
        metadata: dict[str, object] = {
            "original_filename": filename,
            "stored_path": str(stored_path),
            "content_sha256": content_sha256,
        }
        if household_account_id:
            metadata["upload_household_account_id"] = household_account_id
        with service.storage.connection() as conn:
            insert_document_db(
                conn,
                document_id=document_id, filename=filename, stored_path=stored_path,
                inferred_source=inferred_source, inferred_type=inferred_type,
                account_label=account_label, content_type=upload.content_type,
                file_size=len(content), confidence=confidence, now=now, metadata=metadata,
            )

        document = service.get_document(document_id)
        if document is None:
            raise RuntimeError("Failed to persist uploaded document")
        return document

    def find_duplicate_document_by_hash(
        self,
        service: HouseholdFinanceService,
        content_sha256: str,
    ) -> HouseholdDocument | None:
        with service.storage.connection() as conn:
            row = fetch_duplicate_document_row(conn, content_sha256)
        if row is None:
            return None
        return row_to_document(
            row,
            to_float=to_float,
            iso=iso,
            iso_or_none=iso_or_none,
        )

    def review_document(self, service: HouseholdFinanceService, document_id: str) -> None:
        document = service.get_document(document_id)
        if document is None:
            logger.warning(
                "household_document_missing_for_review", document_id=document_id
            )
            return
        try:
            self.process_document_review(service, document)
        except Exception as exc:
            logger.exception(
                "household_document_review_failed", document_id=document_id, error=str(exc)
            )
            with service.storage.connection() as conn:
                mark_review_failed(conn, document_id=document_id, now=datetime.now(UTC).isoformat())

    def process_document_review(
        self, service: HouseholdFinanceService, document: HouseholdDocument
    ) -> None:
        stored_path = document.metadata.get("stored_path")
        if not isinstance(stored_path, str) or not stored_path:
            self._recover_review_from_latest_persisted_review(service, document)
            return
        stored_file = Path(stored_path)
        if not stored_file.exists():
            logger.warning(
                "household_document_source_missing_for_review",
                document_id=document.id,
                stored_path=stored_path,
            )
            self._recover_review_from_latest_persisted_review(service, document)
            return

        attempts = 0
        max_attempts = 2
        prior_review: dict[str, object] | None = None
        reconciliation_summary: dict[str, object] | None = None
        while True:
            now = datetime.now(UTC).isoformat()
            reviewed = service.review_service.review(
                document_id=document.id,
                filename=document.filename,
                stored_path=stored_file,
                content_type=document.content_type,
                source_type=document.source_type,
                document_type=document.document_type,
                prior_review=prior_review,
                reconciliation_summary=reconciliation_summary,
            )
            reviewed = _apply_upload_account_binding(
                service,
                document=document,
                reviewed=reviewed,
            )
            self._persist_review(service, document=document, reviewed=reviewed, now=now)
            application_summary = self.apply_review_outputs(
                service, document=document, reviewed=reviewed
            )
            reconciliation_summary = self._build_reconciliation_summary(
                document=document,
                reviewed=reviewed,
                application_summary=application_summary,
            )
            if reconciliation_summary["status"] != "clear":
                application_summary["needs_follow_up"] = True
            if (
                attempts + 1 < max_attempts
                and reconciliation_summary.get("retry_recommended") is True
            ):
                attempts += 1
                prior_review = reviewed
                continue
            self.upsert_document_signatures(
                service,
                document=document,
                reviewed=reviewed,
                application_summary=application_summary,
                reconciliation_summary=reconciliation_summary,
            )
            break
        with service.storage.connection() as conn:
            update_document_application_summary(
                conn,
                document_id=document.id,
                application_summary=application_summary,
                reconciliation_summary=reconciliation_summary,
            )
            conn.commit()

    def _load_latest_review_payload(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
    ) -> dict[str, object] | None:
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT summary, confidence, extracted_text, structured_data
                FROM household_document_reviews
                WHERE document_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [document.id],
            ).fetchone()
        if row is None:
            return None
        structured_data = row[3] if isinstance(row[3], dict) else {}
        extracted_text = row[2] if isinstance(row[2], str) else ""
        reviewed = {
            "source_type": document.source_type,
            "document_type": document.document_type,
            "summary": row[0] if row[0] is not None else None,
            "confidence": to_float(row[1]),
            "extracted_text": extracted_text,
            "structured_data": structured_data,
        }
        return _normalized_review_payload(reviewed=reviewed, document=document)

    def _recover_review_from_latest_persisted_review(
        self,
        service: HouseholdFinanceService,
        document: HouseholdDocument,
    ) -> bool:
        reviewed = self._load_latest_review_payload(service, document=document)
        if reviewed is None:
            logger.warning(
                "household_document_latest_review_missing_for_recovery",
                document_id=document.id,
            )
            return False
        reviewed = _apply_upload_account_binding(
            service,
            document=document,
            reviewed=reviewed,
        )
        application_summary = self.apply_review_outputs(
            service,
            document=document,
            reviewed=reviewed,
        )
        reconciliation_summary = self._build_reconciliation_summary(
            document=document,
            reviewed=reviewed,
            application_summary=application_summary,
        )
        if reconciliation_summary["status"] != "clear":
            application_summary["needs_follow_up"] = True
        with service.storage.connection() as conn:
            update_document_application_summary(
                conn,
                document_id=document.id,
                application_summary=application_summary,
                reconciliation_summary=reconciliation_summary,
            )
            conn.commit()
        logger.info(
            "household_document_reapplied_latest_review",
            document_id=document.id,
            status=application_summary.get("status"),
            impacts=application_summary.get("impacts"),
        )
        return True

    def _persist_review(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
        now: str,
    ) -> None:
        reviewed = _normalized_review_payload(reviewed=reviewed, document=document)
        review_confidence = to_float(reviewed.get("confidence"))
        review_status = "complete" if (review_confidence or 0.0) >= 0.65 else "needs_review"
        document_status = "parsed" if review_status == "complete" else "needs_review"
        structured_data = reviewed.get("structured_data") or {}
        if not isinstance(structured_data, dict):
            structured_data = {}
        extracted_text = reviewed.get("extracted_text")
        resolved_source_type = str(reviewed.get("source_type") or document.source_type)
        resolved_document_type = str(reviewed.get("document_type") or document.document_type)
        account_hint = structured_data.get("account_hint")
        review_strategy = str(reviewed.get("_review_strategy") or "unknown")
        review_metadata = {
            "structured_data": structured_data,
            "review_checks": reviewed.get("review_checks")
            if isinstance(reviewed.get("review_checks"), dict)
            else {},
            "review_strategy": review_strategy,
            "assigned_review_agent_slug": HOUSEHOLD_REVIEW_AGENT_SLUG,
            "review_agent_applied": review_strategy == "agent",
        }

        with service.storage.connection() as conn:
            dismiss_open_document_questions(conn, document_id=document.id, now=now)
            update_document_and_log_review(
                conn,
                document=document,
                resolved_source_type=resolved_source_type,
                resolved_document_type=resolved_document_type,
                document_status=document_status,
                review_status=review_status,
                review_confidence=review_confidence,
                account_hint=account_hint,
                structured_data=structured_data,
                review_metadata=review_metadata,
                reviewed=reviewed,
                extracted_text=extracted_text,
                now=now,
            )
            insert_inferred_values(conn, service, document=document, reviewed=reviewed, now=now)
            insert_questions(
                conn, service,
                document=document, reviewed=reviewed, now=now,
                resolved_source_type=resolved_source_type,
                resolved_document_type=resolved_document_type,
                structured_data=structured_data,
                account_hint=account_hint,
            )
            archive_prior_document_data(conn, document.id, now)
            conn.commit()

    def upsert_document_signatures(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
        application_summary: dict[str, object] | None = None,
        reconciliation_summary: dict[str, object] | None = None,
    ) -> None:
        if (
            isinstance(application_summary, dict)
            and application_summary.get("status") != "applied"
        ):
            return
        if isinstance(reconciliation_summary, dict):
            if str(reconciliation_summary.get("status") or "") != "clear":
                return
            if bool(reconciliation_summary.get("ambiguity_remaining")):
                return
        extracted_text = reviewed.get("extracted_text")
        if not isinstance(extracted_text, str) or not extracted_text:
            return
        signature_candidates = service.review_service.build_signature_candidates(
            filename=document.filename, extracted_text=extracted_text,
        )
        if not signature_candidates:
            return
        structured_data = reviewed.get("structured_data")
        if not isinstance(structured_data, dict):
            structured_data = {}
        signature_structured_data = _signature_structured_data(reviewed, document)
        shared = {
            "source_type": str(reviewed.get("source_type") or document.source_type),
            "document_type": str(reviewed.get("document_type") or document.document_type),
            "structured_data": signature_structured_data,
            "confidence": to_float(reviewed.get("confidence")),
            "document_id": document.id,
            "now": datetime.now(UTC).isoformat(),
        }
        with service.storage.connection() as conn:
            for signature_type, signature_key, metadata in signature_candidates:
                upsert_signature_record(
                    conn, signature_type=signature_type, signature_key=signature_key,
                    metadata=metadata, **shared,
                )
            conn.commit()

    def import_document_rows(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
    ) -> dict[str, object]:
        dataset_type = detect_import_dataset(document=document, reviewed=reviewed)
        if dataset_type is None:
            return {"dataset_type": None, "inserted": 0, "duplicates": 0}
        stored_path = document.metadata.get("stored_path")
        if not isinstance(stored_path, str) or not stored_path:
            return {"dataset_type": dataset_type, "inserted": 0, "duplicates": 0}

        now = datetime.now(UTC).isoformat()
        with Path(stored_path).open("r", encoding="utf-8", errors="ignore", newline="") as fh:
            rows = list(DictReader(fh))
        inserted = duplicates = 0
        with service.storage.connection() as conn:
            for row in rows:
                result = upsert_import_row(
                    conn, row=row, document_id=document.id, dataset_type=dataset_type, now=now,
                )
                inserted += result is True
                duplicates += result is False
            update_import_summary(
                conn, document_id=document.id, dataset_type=dataset_type,
                inserted=inserted, duplicates=duplicates,
            )
            conn.commit()
        enrichment_summary = service.product_enrichment_service.enrich_import_rows(
            service,
            document_id=document.id,
            dataset_type=dataset_type,
        )
        return {
            "dataset_type": dataset_type,
            "inserted": inserted,
            "duplicates": duplicates,
            "enrichment": enrichment_summary,
        }

    def apply_review_outputs(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
    ) -> dict[str, object]:
        reviewed = _normalized_review_payload(reviewed=reviewed, document=document)
        reviewed = _apply_upload_account_binding(
            service,
            document=document,
            reviewed=reviewed,
        )
        import_summary = self.import_document_rows(service, document=document, reviewed=reviewed)
        transaction_summary = service.transaction_service.import_document_transactions(
            document=document,
            reviewed=reviewed,
        )
        transaction_audit_summary: dict[str, object] = {}
        transaction_audit_service = getattr(service, "transaction_audit_service", None)
        if transaction_audit_service is not None:
            transaction_audit_summary = transaction_audit_service.audit_transactions(
                service,
                document_id=document.id,
                limit=120,
            )
        transaction_summary = {
            **transaction_summary,
            "audit_reviewed": int(transaction_audit_summary.get("reviewed") or 0),
            "audit_auto_fixed": int(transaction_audit_summary.get("auto_fixed") or 0),
            "audit_agent_fixed": int(transaction_audit_summary.get("agent_fixed") or 0),
            "audit_flagged": int(transaction_audit_summary.get("flagged") or 0),
        }
        evidence_account_count = service.evidence_service.replace_document_accounts(
            service,
            document=document,
            reviewed=reviewed,
        )
        registry_summary: dict[str, int] = {}
        registry_service = getattr(service, "account_registry_service", None)
        if registry_service is not None:
            registry_summary = registry_service.sync_registry(service, limit=1000)
        portfolio_position_summary: dict[str, int] = {}
        portfolio_position_sync_service = getattr(
            service,
            "portfolio_position_sync_service",
            None,
        )
        if portfolio_position_sync_service is not None:
            portfolio_position_summary = (
                portfolio_position_sync_service.sync_from_reviewed_accounts(
                    service,
                    document=document,
                    reviewed=reviewed,
                )
            )
        planning_items = reviewed.get("planning_items")
        planning_count = 0
        planning_skipped = 0
        planning_error: str | None = None
        if isinstance(planning_items, list):
            dict_items = [item for item in planning_items if isinstance(item, dict)]
            if dict_items and _should_merge_planning_items(reviewed):
                try:
                    service.merge_planning_items(
                        items=dict_items,
                        provenance="document_review",
                        source_document_id=document.id,
                    )
                    planning_count = len(dict_items)
                except Exception as exc:
                    planning_skipped = len(dict_items)
                    planning_error = str(exc)
                    logger.warning(
                        "household_document_planning_merge_skipped",
                        document_id=document.id,
                        error=str(exc),
                    )
            else:
                planning_skipped = len(dict_items)
        inferred_count = 0
        raw_inferred_values = reviewed.get("inferred_values")
        if not isinstance(raw_inferred_values, list):
            raw_inferred_values = []
        for inferred in raw_inferred_values:
            if not isinstance(inferred, dict):
                continue
            if str(inferred.get("field_name") or "").strip() in FIELD_LABELS:
                inferred_count += 1

        impacts: list[str] = []
        if (import_summary.get("inserted") or 0) > 0:
            impacts.append("imports")
        if (transaction_summary.get("inserted") or 0) > 0 or (transaction_summary.get("updated") or 0) > 0:
            impacts.append("transactions")
        if evidence_account_count > 0:
            impacts.append("accounts")
        if (
            portfolio_position_summary.get("positions_inserted", 0) > 0
            or portfolio_position_summary.get("positions_updated", 0) > 0
            or portfolio_position_summary.get("positions_deleted", 0) > 0
            or portfolio_position_summary.get("cash_updated", 0) > 0
        ):
            impacts.append("portfolio_positions")
        if planning_count > 0:
            impacts.append("planning")
        if inferred_count > 0:
            impacts.append("inferences")
        duplicate_import_validation = _is_duplicate_import_validation(
            import_summary=import_summary,
            transaction_summary=cast(dict[str, object], transaction_summary),
            evidence_account_count=evidence_account_count,
            planning_count=planning_count,
            inferred_count=inferred_count,
        )
        if duplicate_import_validation:
            impacts.append("imports")
        status = "applied" if impacts else "incomplete"

        return {
            "status": status,
            "impacts": impacts,
            "imports": import_summary,
            "transactions": transaction_summary,
            "evidence_accounts": evidence_account_count,
            "account_registry": registry_summary,
            "portfolio_positions": portfolio_position_summary,
            "planning_items": planning_count,
            "planning_items_skipped": planning_skipped,
            "planning_error": planning_error,
            "inferred_values": inferred_count,
            "needs_follow_up": not impacts,
            "no_change": duplicate_import_validation,
        }

    def _build_reconciliation_summary(
        self,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
        application_summary: dict[str, object],
    ) -> dict[str, object]:
        review_checks = _review_checks_dict(reviewed)
        expected_account_count = int(
            review_checks.get("expected_account_count")
            or len(_reviewed_financial_accounts(reviewed))
            or 0
        )
        transaction_summary = cast(
            dict[str, object],
            application_summary.get("transactions")
            if isinstance(application_summary.get("transactions"), dict)
            else {},
        )
        import_summary = cast(
            dict[str, object],
            application_summary.get("imports")
            if isinstance(application_summary.get("imports"), dict)
            else {},
        )
        evidence_account_count = int(application_summary.get("evidence_accounts") or 0)
        transaction_changes = (
            int(transaction_summary.get("inserted") or 0)
            + int(transaction_summary.get("updated") or 0)
            + int(transaction_summary.get("held_for_date_review") or 0)
        )
        import_changes = int(import_summary.get("inserted") or 0)
        expects_transaction_activity = _bool_value(
            review_checks.get("expects_transaction_activity")
        )
        if expects_transaction_activity is None:
            is_image_snapshot = str(document.content_type or "").lower().startswith("image/")
            expects_transaction_activity = (
                not is_image_snapshot
                and str(reviewed.get("source_type") or "") in {"bank", "credit_card"}
                and str(reviewed.get("document_type") or "") == "statement"
            )
        ambiguity_remaining = _bool_value(review_checks.get("ambiguity_remaining")) or False
        issues: list[dict[str, object]] = []
        if expected_account_count > evidence_account_count:
            issues.append(
                {
                    "code": "missing_accounts",
                    "detail": (
                        f"Review identified {expected_account_count} account(s) but "
                        f"only {evidence_account_count} evidence account row(s) applied."
                    ),
                }
            )
        if expects_transaction_activity and transaction_changes == 0:
            issues.append(
                {
                    "code": "missing_transactions",
                    "detail": "Review expected transaction activity but no transaction rows applied.",
                }
            )
        if (
            str(reviewed.get("source_type") or "") in _ACCOUNT_EVIDENCE_SOURCE_TYPES
            and import_changes == 0
            and transaction_changes == 0
            and evidence_account_count == 0
        ):
            issues.append(
                {
                    "code": "no_applied_outputs",
                    "detail": "Financial evidence review produced no applied imports, transactions, or accounts.",
                }
            )
        status = "clear" if not issues else "needs_retry"
        retry_recommended = bool(issues) and not ambiguity_remaining
        return {
            "status": status,
            "retry_recommended": retry_recommended,
            "review_strategy": str(reviewed.get("_review_strategy") or "unknown"),
            "expected_account_count": expected_account_count,
            "evidence_account_count": evidence_account_count,
            "transaction_changes": transaction_changes,
            "import_changes": import_changes,
            "ambiguity_remaining": ambiguity_remaining,
            "issues": issues,
        }

    def describe_application_state(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
    ) -> dict[str, object]:
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        existing_summary = metadata.get("application_summary")
        existing = existing_summary if isinstance(existing_summary, dict) else {}
        existing_imports = existing.get("imports")
        existing_imports_dict = existing_imports if isinstance(existing_imports, dict) else {}
        existing_transactions = existing.get("transactions")
        existing_transactions_dict = (
            existing_transactions if isinstance(existing_transactions, dict) else {}
        )
        existing_portfolio_positions = existing.get("portfolio_positions")
        existing_portfolio_positions_dict = (
            existing_portfolio_positions
            if isinstance(existing_portfolio_positions, dict)
            else {}
        )
        existing_account_registry = existing.get("account_registry")
        existing_account_registry_dict = (
            existing_account_registry if isinstance(existing_account_registry, dict) else {}
        )

        with service.storage.connection() as conn:
            counts = fetch_document_application_counts(conn, document_id=document.id)

        import_count = int(counts["import_count"])
        transaction_count = int(counts["transaction_count"])
        evidence_account_count = int(counts["evidence_account_count"])
        inferred_count = int(counts["inferred_count"])
        planning_count = int(existing.get("planning_items") or 0)

        impacts: list[str] = []
        if import_count > 0:
            impacts.append("imports")
        if transaction_count > 0:
            impacts.append("transactions")
        if evidence_account_count > 0:
            impacts.append("accounts")
        portfolio_position_events = sum(
            _int_value(existing_portfolio_positions_dict.get(key)) or 0
            for key in (
                "accounts_linked",
                "cash_updated",
                "positions_seen",
                "positions_inserted",
                "positions_updated",
                "positions_unchanged",
                "positions_deleted",
            )
        )
        if portfolio_position_events > 0:
            impacts.append("portfolio_positions")
        if planning_count > 0:
            impacts.append("planning")
        if inferred_count > 0:
            impacts.append("inferences")
        duplicate_import_validation = _is_duplicate_import_validation(
            import_summary=cast(dict[str, object], existing_imports_dict),
            transaction_summary=cast(dict[str, object], existing_transactions_dict),
            evidence_account_count=evidence_account_count,
            planning_count=planning_count,
            inferred_count=inferred_count,
        )
        if duplicate_import_validation:
            impacts.append("imports")

        summary: dict[str, object] = {
            "status": "applied" if impacts else "incomplete",
            "impacts": impacts,
            "imports": {
                "dataset_type": counts["dataset_type"] or existing_imports_dict.get("dataset_type"),
                "inserted": import_count,
                "duplicates": int(existing_imports_dict.get("duplicates") or 0),
            },
            "transactions": {
                "inserted": transaction_count,
                "updated": int(existing_transactions_dict.get("updated") or 0),
            },
            "evidence_accounts": evidence_account_count,
            "planning_items": planning_count,
            "inferred_values": inferred_count,
            "needs_follow_up": not impacts,
            "no_change": duplicate_import_validation,
        }
        if existing_account_registry_dict:
            summary["account_registry"] = existing_account_registry_dict
        if existing_portfolio_positions_dict:
            summary["portfolio_positions"] = existing_portfolio_positions_dict
        return summary
