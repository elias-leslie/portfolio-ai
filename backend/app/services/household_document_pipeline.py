"""Document intake, review persistence, and import helpers for household finance."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fastapi import UploadFile

from app.logging_config import get_logger
from app.models.household_finance import HouseholdDocument
from app.services._household_document_pipeline_accounts import (
    apply_upload_account_binding as _apply_upload_account_binding,
)
from app.services._household_document_pipeline_apply import (
    append_review_impacts as _append_review_impacts,
)
from app.services._household_document_pipeline_apply import (
    audit_transactions as _audit_transactions,
)
from app.services._household_document_pipeline_apply import (
    find_duplicate_document_by_hash as _find_duplicate_document_by_hash,
)
from app.services._household_document_pipeline_apply import (
    import_document_rows as _import_document_rows,
)
from app.services._household_document_pipeline_apply import (
    inferred_value_count as _inferred_value_count,
)
from app.services._household_document_pipeline_apply import (
    is_duplicate_import_validation as _is_duplicate_import_validation,
)
from app.services._household_document_pipeline_apply import (
    merge_review_planning_items as _merge_review_planning_items,
)
from app.services._household_document_pipeline_apply import (
    signature_structured_data as _signature_structured_data,
)
from app.services._household_document_pipeline_apply import (
    sync_account_registry as _sync_account_registry,
)
from app.services._household_document_pipeline_apply import (
    sync_portfolio_positions as _sync_portfolio_positions,
)
from app.services._household_document_pipeline_apply import (
    sync_portfolio_transactions as _sync_portfolio_transactions,
)
from app.services._household_document_pipeline_apply import (
    transaction_summary_with_audit as _transaction_summary_with_audit,
)
from app.services._household_document_pipeline_db import (
    archive_prior_document_data,
    dismiss_open_document_questions,
    fetch_document_application_counts,
    insert_document_db,
    insert_inferred_values,
    insert_questions,
    mark_review_failed,
    save_upload_to_disk,
    update_document_and_log_review,
    update_document_application_summary,
    upsert_signature_record,
)
from app.services._household_document_pipeline_receipt import (  # noqa: F401
    receipt_line_item_rows as _receipt_line_item_rows,
)
from app.services._household_document_pipeline_utils import (
    build_import_row_hash,
    classify_document,
    detect_import_dataset,
    normalize_financial_document_classification,
    parse_decimal,
    parse_row_date,
)
from app.services._household_finance_utils import to_float
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


def _int_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _review_checks_dict(reviewed: dict[str, object]) -> dict[str, object]:
    review_checks = reviewed.get("review_checks")
    return cast(dict[str, object], review_checks) if isinstance(review_checks, dict) else {}


def _reviewed_financial_accounts(reviewed: dict[str, object]) -> list[dict[str, object]]:
    structured_data = reviewed.get("structured_data")
    structured_data = cast(dict[str, object], structured_data) if isinstance(structured_data, dict) else {}
    accounts = structured_data.get("financial_accounts")
    if not isinstance(accounts, list):
        return []
    return [cast(dict[str, object], a) for a in accounts if isinstance(a, dict)]


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


def _load_latest_review_payload(
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
    reviewed = {
        "source_type": document.source_type,
        "document_type": document.document_type,
        "summary": row[0] if row[0] is not None else None,
        "confidence": to_float(row[1]),
        "extracted_text": row[2] if isinstance(row[2], str) else "",
        "structured_data": row[3] if isinstance(row[3], dict) else {},
    }
    return _normalized_review_payload(reviewed=reviewed, document=document)


# ---------------------------------------------------------------------------
# Main pipeline class
# ---------------------------------------------------------------------------


class HouseholdDocumentPipeline:
    """Persist household uploads and review outcomes."""

    # Expose pure helpers as instance attributes for backward compatibility.
    classify_document = staticmethod(classify_document)
    parse_row_date = staticmethod(parse_row_date)
    parse_decimal = staticmethod(parse_decimal)
    detect_import_dataset = staticmethod(detect_import_dataset)
    build_import_row_hash = staticmethod(build_import_row_hash)

    @staticmethod
    def _review_gate_summaries(
        reviewed: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, object]] | None:
        """Return non-applying summaries when review evidence is not trustworthy."""
        confidence = to_float(reviewed.get("confidence"))
        review_checks = _review_checks_dict(reviewed)
        ambiguity_remaining = _bool_value(review_checks.get("ambiguity_remaining")) or False
        if confidence is not None and confidence >= 0.65 and not ambiguity_remaining:
            return None

        if ambiguity_remaining:
            reason = "The review still has unresolved account or evidence ambiguity."
        elif confidence is None:
            reason = "The review did not provide a confidence score."
        else:
            reason = f"Review confidence {confidence:.0%} is below the 65% auto-apply threshold."
        application_summary: dict[str, object] = {
            "status": "needs_review",
            "impacts": [],
            "imports": {"inserted": 0, "duplicates": 0},
            "transactions": {"inserted": 0, "updated": 0, "held_for_date_review": 0},
            "evidence_accounts": 0,
            "portfolio_positions": {},
            "portfolio_transactions": {},
            "planning_items": 0,
            "planning_items_skipped": 0,
            "planning_error": None,
            "inferred_values": 0,
            "needs_follow_up": True,
            "review_blocker": reason,
        }
        reconciliation_summary: dict[str, object] = {
            "status": "needs_review",
            "retry_recommended": False,
            "review_strategy": str(reviewed.get("_review_strategy") or "unknown"),
            "ambiguity_remaining": ambiguity_remaining,
            "issues": [reason],
        }
        return application_summary, reconciliation_summary

    async def ingest_document(
        self,
        service: HouseholdFinanceService,
        *,
        upload: UploadFile,
        source_type: str | None = None,
        document_type: str | None = None,
        account_label: str | None = None,
        household_account_id: str | None = None,
        review_session_id: str | None = None,
    ) -> HouseholdDocument:
        document_id = str(uuid.uuid4())
        filename = upload.filename or f"{document_id}.bin"
        validate_household_upload_metadata(upload)
        content = await read_household_upload_limited(upload)
        content_sha256 = hashlib.sha256(content).hexdigest()

        find_duplicate = getattr(self, "find_duplicate_document_by_hash", _find_duplicate_document_by_hash)
        duplicate = find_duplicate(service, content_sha256)
        if duplicate is not None:
            return self._handle_duplicate_upload(
                service,
                duplicate=duplicate,
                account_label=account_label,
                household_account_id=household_account_id,
                review_session_id=review_session_id,
            )

        inferred_source, inferred_type, confidence = classify_document(
            filename=filename,
            content_type=upload.content_type,
            source_type=source_type,
            document_type=document_type,
        )
        upload_root = service._upload_root()
        stored_path = save_upload_to_disk(
            content, document_id=document_id, filename=filename, upload_dir=upload_root,
        )
        now = datetime.now(UTC).isoformat()
        metadata: dict[str, object] = {
            "original_filename": filename,
            "stored_path": str(stored_path),
            "content_sha256": content_sha256,
        }
        if household_account_id:
            metadata["upload_household_account_id"] = household_account_id
        if review_session_id:
            metadata["review_session_id"] = review_session_id
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

    def _handle_duplicate_upload(
        self,
        service: HouseholdFinanceService,
        *,
        duplicate: HouseholdDocument,
        account_label: str | None,
        household_account_id: str | None,
        review_session_id: str | None,
    ) -> HouseholdDocument:
        if household_account_id or account_label:
            rebound_metadata: dict[str, object] = {
                "duplicate_rebound": True,
                "duplicate_rebound_at": datetime.now(UTC).isoformat(),
            }
            if household_account_id:
                rebound_metadata["upload_household_account_id"] = household_account_id
            if review_session_id:
                rebound_metadata["review_session_id"] = review_session_id
            with service.storage.connection() as conn:
                conn.execute(
                    """
                    UPDATE household_documents
                    SET account_label = COALESCE(%s, account_label),
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                    WHERE id = %s
                    """,
                    [account_label, json.dumps(rebound_metadata), duplicate.id],
                )
                conn.commit()
            refreshed = service.get_document(duplicate.id)
            if refreshed is not None:
                duplicate = refreshed
        duplicate.metadata["duplicate_detected"] = True
        duplicate.metadata["duplicate_reason"] = "exact_content_match"
        return duplicate

    def review_document(
        self,
        service: HouseholdFinanceService,
        document_id: str,
        review_session_id: str | None = None,
    ) -> None:
        document = service.get_document(document_id)
        if document is None:
            logger.warning("household_document_missing_for_review", document_id=document_id)
            return
        try:
            self.process_document_review(service, document, review_session_id=review_session_id)
        except Exception as exc:
            logger.exception(
                "household_document_review_failed", document_id=document_id, error=str(exc)
            )
            with service.storage.connection() as conn:
                mark_review_failed(conn, document_id=document_id, now=datetime.now(UTC).isoformat())

    def process_document_review(
        self,
        service: HouseholdFinanceService,
        document: HouseholdDocument,
        review_session_id: str | None = None,
    ) -> None:
        if document.source_type == "credit_card_offer":
            # Card offers feed the credit-card catalog, not the finance ledger
            # review loop (plan §9).
            from app.services.card_offer_agent_service import (  # noqa: PLC0415 — avoids importing the agent stack at pipeline load
                get_card_offer_agent_service,
            )

            get_card_offer_agent_service().process_offer_document(service, document)
            return
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
        self._run_review_loop(service, document=document, stored_file=stored_file, review_session_id=review_session_id)

    def _resolve_review_session_id(
        self,
        document: HouseholdDocument,
        review_session_id: str | None,
    ) -> str | None:
        if isinstance(review_session_id, str) and review_session_id.strip():
            return review_session_id
        metadata_session_id = document.metadata.get("review_session_id")
        if isinstance(metadata_session_id, str) and metadata_session_id.strip():
            return metadata_session_id
        return None

    def _run_review_loop(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
        stored_file: Path,
        review_session_id: str | None,
    ) -> None:
        resolved_session_id = self._resolve_review_session_id(document, review_session_id)
        attempts = 0
        max_attempts = 2
        prior_review: dict[str, object] | None = None
        reconciliation_summary: dict[str, object] | None = None
        application_summary: dict[str, object] = {}

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
                review_session_id=resolved_session_id,
            )
            reviewed = _apply_upload_account_binding(service, document=document, reviewed=reviewed)
            self._persist_review(service, document=document, reviewed=reviewed, now=now)
            gated_summaries = self._review_gate_summaries(reviewed)
            if gated_summaries is not None:
                application_summary, reconciliation_summary = gated_summaries
                break
            application_summary = self.apply_review_outputs(service, document=document, reviewed=reviewed)
            reconciliation_summary = self._build_reconciliation_summary(
                document=document, reviewed=reviewed, application_summary=application_summary,
            )
            if reconciliation_summary["status"] != "clear":
                application_summary["needs_follow_up"] = True
            should_retry = (
                attempts + 1 < max_attempts
                and reconciliation_summary.get("retry_recommended") is True
                and str(reviewed.get("_review_strategy") or "") != "agent_vision"
            )
            if not should_retry:
                break
            attempts += 1
            prior_review = reviewed

        self.upsert_document_signatures(
            service,
            document=document,
            reviewed=reviewed,
            application_summary=application_summary,
            reconciliation_summary=reconciliation_summary,
        )
        with service.storage.connection() as conn:
            update_document_application_summary(
                conn,
                document_id=document.id,
                application_summary=application_summary,
                reconciliation_summary=reconciliation_summary,
            )
            conn.commit()

    def _recover_review_from_latest_persisted_review(
        self,
        service: HouseholdFinanceService,
        document: HouseholdDocument,
    ) -> bool:
        reviewed = _load_latest_review_payload(service, document=document)
        if reviewed is None:
            logger.warning(
                "household_document_latest_review_missing_for_recovery",
                document_id=document.id,
            )
            return False
        reviewed = _apply_upload_account_binding(service, document=document, reviewed=reviewed)
        gated_summaries = self._review_gate_summaries(reviewed)
        if gated_summaries is not None:
            application_summary, reconciliation_summary = gated_summaries
        else:
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
            archive_prior_document_data(conn, document.id, now)
            insert_inferred_values(conn, service, document=document, reviewed=reviewed, now=now)
            insert_questions(
                conn, service,
                document=document, reviewed=reviewed, now=now,
                resolved_source_type=resolved_source_type,
                resolved_document_type=resolved_document_type,
                structured_data=structured_data,
                account_hint=account_hint,
            )
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
        if isinstance(application_summary, dict) and application_summary.get("status") != "applied":
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

    def apply_review_outputs(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
    ) -> dict[str, object]:
        reviewed = _normalized_review_payload(reviewed=reviewed, document=document)
        reviewed = _apply_upload_account_binding(service, document=document, reviewed=reviewed)
        import_summary = _import_document_rows(service, document=document, reviewed=reviewed)
        transaction_summary = service.transaction_service.import_document_transactions(
            document=document, reviewed=reviewed,
        )
        transaction_summary = _transaction_summary_with_audit(
            transaction_summary, _audit_transactions(service, document_id=document.id)
        )
        # Purchase items ride the same apply pass (after transactions exist to
        # link against) but never block document application.
        try:
            purchase_item_summary: dict[str, object] = dict(
                service.purchase_item_service.sync_document(document_id=document.id)
            )
        except Exception as exc:
            logger.warning(
                "household_document_purchase_item_sync_failed",
                document_id=document.id,
                error=str(exc),
            )
            purchase_item_summary = {"error": str(exc)}
        evidence_account_count = service.evidence_service.replace_document_accounts(
            service, document=document, reviewed=reviewed,
        )
        registry_summary = _sync_account_registry(service)
        portfolio_position_summary = _sync_portfolio_positions(service, document=document, reviewed=reviewed)
        portfolio_transaction_summary = _sync_portfolio_transactions(service, document=document, reviewed=reviewed)
        planning_count, planning_skipped, planning_error = _merge_review_planning_items(
            service, document=document, reviewed=reviewed,
        )
        inferred_count = _inferred_value_count(reviewed)
        impacts: list[str] = []
        _append_review_impacts(
            impacts,
            import_summary=import_summary,
            transaction_summary=transaction_summary,
            evidence_account_count=evidence_account_count,
            portfolio_position_summary=portfolio_position_summary,
            planning_count=planning_count,
            inferred_count=inferred_count,
        )
        duplicate_import_validation = _is_duplicate_import_validation(
            import_summary=import_summary,
            transaction_summary=transaction_summary,
            evidence_account_count=evidence_account_count,
            planning_count=planning_count,
            inferred_count=inferred_count,
        )
        if duplicate_import_validation:
            impacts.append("imports")
        status = "applied" if impacts else "incomplete"
        if impacts == ["date_review"]:
            status = "needs_date_review"
        summary = {
            "status": status,
            "impacts": impacts,
            "imports": import_summary,
            "transactions": transaction_summary,
            "purchase_items": purchase_item_summary,
            "evidence_accounts": evidence_account_count,
            "account_registry": registry_summary,
            "portfolio_positions": portfolio_position_summary,
            "portfolio_transactions": portfolio_transaction_summary,
            "planning_items": planning_count,
            "planning_items_skipped": planning_skipped,
            "planning_error": planning_error,
            "inferred_values": inferred_count,
            "needs_follow_up": not impacts or "date_review" in impacts,
            "no_change": duplicate_import_validation,
        }
        return self._refresh_application_summary_counts(
            service,
            document=document,
            application_summary=summary,
        )

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
        expects_transaction_activity = _build_expects_transaction_activity(
            document=document,
            reviewed=reviewed,
            review_checks=review_checks,
        )
        ambiguity_remaining = _bool_value(review_checks.get("ambiguity_remaining")) or False
        issues = _collect_reconciliation_issues(
            expected_account_count=expected_account_count,
            evidence_account_count=evidence_account_count,
            expects_transaction_activity=expects_transaction_activity,
            transaction_changes=transaction_changes,
            import_changes=import_changes,
            reviewed=reviewed,
        )
        status = "clear" if not issues else "needs_retry"
        return {
            "status": status,
            "retry_recommended": bool(issues) and not ambiguity_remaining,
            "review_strategy": str(reviewed.get("_review_strategy") or "unknown"),
            "expected_account_count": expected_account_count,
            "evidence_account_count": evidence_account_count,
            "transaction_changes": transaction_changes,
            "import_changes": import_changes,
            "ambiguity_remaining": ambiguity_remaining,
            "issues": issues,
        }

    def _refresh_application_summary_counts(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
        application_summary: dict[str, object],
    ) -> dict[str, object]:
        if not hasattr(service, "storage"):
            return application_summary
        with service.storage.connection() as conn:
            counts = fetch_document_application_counts(conn, document_id=document.id)

        imports = _safe_dict(application_summary.get("imports"))
        transactions = _safe_dict(application_summary.get("transactions"))
        import_count = int(counts["import_count"])
        transaction_count = int(counts["transaction_count"])
        evidence_account_count = int(counts["evidence_account_count"])
        inferred_count = int(counts["inferred_count"])
        held_count = int(transactions.get("held_for_date_review") or 0)

        impacts: list[str] = []
        if import_count > 0:
            impacts.append("imports")
        if transaction_count > 0:
            impacts.append("transactions")
        if evidence_account_count > 0:
            impacts.append("accounts")
        for key in ("portfolio_positions", "portfolio_transactions"):
            value = application_summary.get(key)
            if isinstance(value, dict) and any(
                int(item or 0) > 0
                for item in value.values()
                if isinstance(item, (int, float))
            ):
                impacts.append(key)
        if int(application_summary.get("planning_items") or 0) > 0:
            impacts.append("planning")
        if inferred_count > 0:
            impacts.append("inferences")
        if held_count > 0 and "date_review" not in impacts:
            impacts.append("date_review")

        status = "applied" if impacts else "incomplete"
        if impacts == ["date_review"]:
            status = "needs_date_review"

        return {
            **application_summary,
            "status": status,
            "impacts": impacts,
            "imports": {
                **imports,
                "dataset_type": counts["dataset_type"] or imports.get("dataset_type"),
                "inserted": import_count,
            },
            "transactions": {
                **transactions,
                "inserted": transaction_count,
                "held_for_date_review": held_count,
            },
            "evidence_accounts": evidence_account_count,
            "inferred_values": inferred_count,
            "needs_follow_up": status != "applied" or "date_review" in impacts,
        }

    def describe_application_state(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
    ) -> dict[str, object]:
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        existing = _safe_dict(metadata.get("application_summary"))
        existing_imports = _safe_dict(existing.get("imports"))
        existing_transactions = _safe_dict(existing.get("transactions"))
        existing_portfolio_positions = _safe_dict(existing.get("portfolio_positions"))
        existing_account_registry = _safe_dict(existing.get("account_registry"))

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
            _int_value(existing_portfolio_positions.get(key)) or 0
            for key in (
                "accounts_linked", "cash_updated", "positions_seen",
                "positions_inserted", "positions_updated",
                "positions_unchanged", "positions_deleted",
            )
        )
        if portfolio_position_events > 0:
            impacts.append("portfolio_positions")
        if planning_count > 0:
            impacts.append("planning")
        if inferred_count > 0:
            impacts.append("inferences")
        duplicate_import_validation = _is_duplicate_import_validation(
            import_summary=existing_imports,
            transaction_summary=existing_transactions,
            evidence_account_count=evidence_account_count,
            planning_count=planning_count,
            inferred_count=inferred_count,
        )
        if duplicate_import_validation:
            impacts.append("imports")
        held_count = int(existing_transactions.get("held_for_date_review") or 0)
        if held_count > 0:
            impacts.append("date_review")
        status = "applied" if impacts else "incomplete"
        if impacts == ["date_review"]:
            status = "needs_date_review"

        summary: dict[str, object] = {
            "status": status,
            "impacts": impacts,
            "imports": {
                "dataset_type": counts["dataset_type"] or existing_imports.get("dataset_type"),
                "inserted": import_count,
                "duplicates": int(existing_imports.get("duplicates") or 0),
            },
            "transactions": {
                "inserted": transaction_count,
                "updated": int(existing_transactions.get("updated") or 0),
                "held_for_date_review": held_count,
            },
            "evidence_accounts": evidence_account_count,
            "planning_items": planning_count,
            "inferred_values": inferred_count,
            "needs_follow_up": status != "applied" or "date_review" in impacts,
            "no_change": duplicate_import_validation,
        }
        if existing_account_registry:
            summary["account_registry"] = existing_account_registry
        if existing_portfolio_positions:
            summary["portfolio_positions"] = existing_portfolio_positions
        return summary


# ---------------------------------------------------------------------------
# Private module-level helpers
# ---------------------------------------------------------------------------


def _safe_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _build_expects_transaction_activity(
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
    review_checks: dict[str, object],
) -> bool:
    result = _bool_value(review_checks.get("expects_transaction_activity"))
    if result is not None:
        return result
    is_image_snapshot = str(document.content_type or "").lower().startswith("image/")
    return (
        not is_image_snapshot
        and str(reviewed.get("source_type") or "") in {"bank", "credit_card"}
        and str(reviewed.get("document_type") or "") == "statement"
    )


def _collect_reconciliation_issues(
    *,
    expected_account_count: int,
    evidence_account_count: int,
    expects_transaction_activity: bool,
    transaction_changes: int,
    import_changes: int,
    reviewed: dict[str, object],
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    if expected_account_count > evidence_account_count:
        issues.append({
            "code": "missing_accounts",
            "detail": (
                f"Review identified {expected_account_count} account(s) but "
                f"only {evidence_account_count} evidence account row(s) applied."
            ),
        })
    if expects_transaction_activity and transaction_changes == 0:
        issues.append({
            "code": "missing_transactions",
            "detail": "Review expected transaction activity but no transaction rows applied.",
        })
    if (
        str(reviewed.get("source_type") or "") in _ACCOUNT_EVIDENCE_SOURCE_TYPES
        and import_changes == 0
        and transaction_changes == 0
        and evidence_account_count == 0
    ):
        issues.append({
            "code": "no_applied_outputs",
            "detail": "Financial evidence review produced no applied imports, transactions, or accounts.",
        })
    return issues
