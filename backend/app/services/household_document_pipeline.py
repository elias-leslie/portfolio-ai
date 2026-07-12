"""Document intake, review persistence, and import helpers for household finance."""

from __future__ import annotations

import hashlib
import hmac
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
    archive_prior_inferred_values,
    bind_document_review_proposal,
    claim_document_review_decision,
    complete_document_review_decision,
    dismiss_open_document_questions,
    fail_document_review_application,
    fetch_document_application_counts,
    fetch_document_review_decision_binding,
    insert_document_db,
    insert_inferred_values,
    insert_questions,
    mark_review_failed,
    record_document_review_application_phase,
    release_document_review_executor,
    save_upload_to_disk,
    try_acquire_document_review_executor,
    update_bound_document_review_state,
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
from app.services.household_document_review_contracts import (
    HouseholdDocumentReviewApplicationError,
    HouseholdDocumentReviewDecisionResult,
    HouseholdDocumentReviewPayload,
    HouseholdDocumentReviewProposal,
    HouseholdDocumentReviewProposalPreview,
)
from app.services.household_document_review_proposal import (
    build_document_review_preview,
    canonical_review_json,
    document_review_proposal_hash,
)
from app.services.household_document_storage import (
    household_upload_root,
    resolve_document_upload,
    upload_storage_key,
)
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


def _normalized_preview_accounts(
    service: HouseholdFinanceService | None,
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
) -> list[dict[str, object]] | None:
    """Use the same account normalization/dedupe path as money-data apply."""
    if service is None or not hasattr(service, "evidence_service"):
        return None
    normalized = service.evidence_service._normalize_accounts(
        document=document,
        reviewed=reviewed,
    )
    return service.evidence_service._dedupe_normalized_accounts(normalized)


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
    return cast(
        dict[str, object],
        HouseholdDocumentReviewPayload.model_validate(normalized).model_dump(
            by_alias=True
        ),
    )


def _load_latest_review_payload(
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
) -> tuple[str, dict[str, object]] | None:
    with service.storage.connection() as conn:
        row = conn.execute(
            """
            SELECT id, summary, confidence, extracted_text, structured_data,
                   review_payload
            FROM household_document_reviews
            WHERE document_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [document.id],
        ).fetchone()
    if row is None:
        return None
    persisted_payload = row[5] if isinstance(row[5], dict) else {}
    reviewed = {
        **persisted_payload,
        "source_type": document.source_type,
        "document_type": document.document_type,
        "summary": row[1] if row[1] is not None else None,
        "confidence": to_float(row[2]),
        "extracted_text": row[3] if isinstance(row[3], str) else None,
        "structured_data": row[4] if isinstance(row[4], dict) else {},
    }
    return str(row[0]), _normalized_review_payload(reviewed=reviewed, document=document)


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

    @staticmethod
    def _build_review_proposal(
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
        review_id: str,
        blocker: str,
        stored_path: Path | None = None,
        service: HouseholdFinanceService | None = None,
    ) -> dict[str, object]:
        """Build the typed preview and bind it to this exact normalized review."""
        preview = build_document_review_preview(
            document=document,
            reviewed=reviewed,
            stored_path=stored_path,
            normalized_accounts=_normalized_preview_accounts(
                service,
                document=document,
                reviewed=reviewed,
            ),
        )
        preview_payload = preview.model_dump(mode="json")
        proposed_changes = [
            {
                "kind": "accounts",
                "label": "Account snapshots",
                "count": len(preview.accounts),
            },
            {
                "kind": "transactions",
                "label": "Transactions",
                "count": len(preview.transactions),
            },
            {
                "kind": "holdings",
                "label": "Portfolio positions",
                "count": len(preview.holdings),
            },
            {
                "kind": "planning",
                "label": "Planning facts",
                "count": len(preview.planning),
            },
            {
                "kind": "inferences",
                "label": "Inferred values",
                "count": len(preview.inferences),
            },
        ]
        proposal_hash = document_review_proposal_hash(
            document_id=document.id,
            review_id=review_id,
            reviewed=reviewed,
            preview=preview,
        )
        return cast(
            dict[str, object],
            HouseholdDocumentReviewProposal.model_validate(
                {
                    "review_id": review_id,
                    "document_id": document.id,
                    "summary": reviewed.get("summary"),
                    "confidence": to_float(reviewed.get("confidence")),
                    "source_type": str(
                        reviewed.get("source_type") or document.source_type
                    ),
                    "document_type": str(
                        reviewed.get("document_type") or document.document_type
                    ),
                    "blocker": blocker,
                    "proposal_hash": proposal_hash,
                    "preview": preview_payload,
                    "proposed_changes": [
                        item for item in proposed_changes if item["count"]
                    ],
                }
            ).model_dump(mode="json"),
        )

    @staticmethod
    def _bind_review_proposal(
        service: HouseholdFinanceService,
        *,
        proposal: dict[str, object],
        now: str,
    ) -> None:
        """Persist one proposal binding before exposing its decision controls."""
        preview = HouseholdDocumentReviewProposalPreview.model_validate(
            proposal.get("preview")
        ).model_dump(mode="json")
        with service.storage.connection() as conn:
            bound = bind_document_review_proposal(
                conn,
                document_id=str(proposal["document_id"]),
                review_id=str(proposal["review_id"]),
                proposal_hash=str(proposal["proposal_hash"]),
                proposal_preview=cast(dict[str, object], preview),
                now=now,
            )
            if not bound:
                raise RuntimeError("Document review proposal could not be bound atomically.")
            conn.commit()

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
        storage_key = upload_storage_key(stored_path, upload_root)
        now = datetime.now(UTC).isoformat()
        metadata: dict[str, object] = {
            "original_filename": filename,
            "storage_key": storage_key,
            # Preserve the established response field, but make it portable.
            "stored_path": storage_key,
            "content_sha256": content_sha256,
        }
        if household_account_id:
            metadata["upload_household_account_id"] = household_account_id
        if review_session_id:
            metadata["review_session_id"] = review_session_id
        with service.storage.connection() as conn:
            insert_document_db(
                conn,
                document_id=document_id, filename=filename, stored_path=storage_key,
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
        with service.storage.connection() as review_conn:
            if not try_acquire_document_review_executor(
                review_conn, document_id=document_id
            ):
                logger.info(
                    "household_document_review_already_executing",
                    document_id=document_id,
                )
                return
            try:
                self.process_document_review(
                    service,
                    document,
                    review_session_id=review_session_id,
                )
            except Exception as exc:
                logger.exception(
                    "household_document_review_failed",
                    document_id=document_id,
                    error=str(exc),
                )
                mark_review_failed(
                    review_conn,
                    document_id=document_id,
                    now=datetime.now(UTC).isoformat(),
                )
            finally:
                release_document_review_executor(
                    review_conn, document_id=document_id
                )
                review_conn.commit()

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
        stored_file = resolve_document_upload(
            document.metadata,
            household_upload_root(service),
        )
        if stored_file is None:
            logger.warning(
                "household_document_source_missing_for_review",
                document_id=document.id,
                storage_reference=(
                    document.metadata.get("storage_key")
                    or document.metadata.get("stored_path")
                ),
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
        review_proposal: dict[str, object] = {
            "schema_version": 2,
            "status": "not_required",
        }

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
            reviewed = _normalized_review_payload(reviewed=reviewed, document=document)
            review_id = self._persist_review(
                service, document=document, reviewed=reviewed, now=now
            )
            gated_summaries = self._review_gate_summaries(reviewed)
            if gated_summaries is not None:
                application_summary, reconciliation_summary = gated_summaries
                review_proposal = self._build_review_proposal(
                    document=document,
                    reviewed=reviewed,
                    review_id=review_id,
                    blocker=str(
                        application_summary.get("review_blocker") or "Review required."
                    ),
                    stored_path=stored_file,
                    service=service,
                )
                self._bind_review_proposal(
                    service,
                    proposal=review_proposal,
                    now=now,
                )
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
                review_proposal=review_proposal,
            )
            conn.commit()

    def _recover_review_from_latest_persisted_review(
        self,
        service: HouseholdFinanceService,
        document: HouseholdDocument,
    ) -> bool:
        review_record = _load_latest_review_payload(service, document=document)
        if review_record is None:
            logger.warning(
                "household_document_latest_review_missing_for_recovery",
                document_id=document.id,
            )
            return False
        review_id, reviewed = review_record
        reviewed = _apply_upload_account_binding(service, document=document, reviewed=reviewed)
        gated_summaries = self._review_gate_summaries(reviewed)
        if gated_summaries is not None:
            application_summary, reconciliation_summary = gated_summaries
            review_proposal = self._build_review_proposal(
                document=document,
                reviewed=reviewed,
                review_id=review_id,
                blocker=str(application_summary.get("review_blocker") or "Review required."),
                service=service,
            )
            self._bind_review_proposal(
                service,
                proposal=review_proposal,
                now=datetime.now(UTC).isoformat(),
            )
        else:
            review_proposal = {"schema_version": 2, "status": "not_required"}
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
                review_proposal=review_proposal,
            )
            conn.commit()
        logger.info(
            "household_document_reapplied_latest_review",
            document_id=document.id,
            status=application_summary.get("status"),
            impacts=application_summary.get("impacts"),
        )
        return True

    @staticmethod
    def _reviewed_from_decision_binding(
        *,
        document: HouseholdDocument,
        binding: dict[str, object],
    ) -> dict[str, object]:
        """Reconstruct the exact persisted review without dynamic re-binding."""
        reviewed = binding.get("review_payload")
        reviewed = dict(reviewed) if isinstance(reviewed, dict) else {}
        reviewed.update(
            {
                "source_type": reviewed.get("source_type") or document.source_type,
                "document_type": reviewed.get("document_type")
                or document.document_type,
                "summary": binding.get("summary"),
                "confidence": to_float(binding.get("confidence")),
                "extracted_text": binding.get("extracted_text")
                if isinstance(binding.get("extracted_text"), str)
                else None,
                "structured_data": binding.get("structured_data")
                if isinstance(binding.get("structured_data"), dict)
                else {},
            }
        )
        return _normalized_review_payload(reviewed=reviewed, document=document)

    @staticmethod
    def _validate_decision_binding(
        *,
        document: HouseholdDocument,
        binding: dict[str, object],
        review_id: str,
        proposal_hash: str,
        proposal_preview: dict[str, object],
        decision: str,
        stored_path: Path | None,
        service: HouseholdFinanceService,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        """Validate visible, stored, and recomputed bindings before any write."""
        visible = binding.get("visible_proposal")
        proposal = dict(visible) if isinstance(visible, dict) else {}
        if (
            proposal.get("schema_version") != 2
            or proposal.get("review_id") != review_id
            or proposal.get("document_id") != document.id
        ):
            raise ValueError(
                "This proposal is stale or predates exact previews. Re-run review "
                "before recording a decision."
            )

        status = proposal.get("status")
        existing_decision = binding.get("decision")
        existing_status = binding.get("decision_status")
        if decision == "reject":
            valid_state = status == "pending" and existing_decision is None
        else:
            valid_state = (
                status == "pending" and existing_decision is None
            ) or (
                status in {"applying", "failed"}
                and existing_decision == "approve"
                and existing_status in {"applying", "failed"}
            )
        if not valid_state:
            raise ValueError(
                "This proposal is no longer pending or recoverable. Refresh the "
                "document list before recording a decision."
            )

        request_preview = HouseholdDocumentReviewProposalPreview.model_validate(
            proposal_preview
        )
        request_preview_payload = cast(
            dict[str, object], request_preview.model_dump(mode="json")
        )
        stored_preview = HouseholdDocumentReviewProposalPreview.model_validate(
            binding.get("proposal_preview")
        )
        visible_preview = HouseholdDocumentReviewProposalPreview.model_validate(
            proposal.get("preview")
        )
        reviewed = HouseholdDocumentPipeline._reviewed_from_decision_binding(
            document=document,
            binding=binding,
        )
        recomputed_preview = build_document_review_preview(
            document=document,
            reviewed=reviewed,
            stored_path=stored_path,
            normalized_accounts=_normalized_preview_accounts(
                service,
                document=document,
                reviewed=reviewed,
            ),
        )
        canonical_preview = canonical_review_json(
            recomputed_preview.model_dump(mode="json")
        )
        if any(
            canonical_review_json(candidate.model_dump(mode="json"))
            != canonical_preview
            for candidate in (request_preview, stored_preview, visible_preview)
        ):
            raise ValueError(
                "The proposal preview no longer matches the reviewed values. "
                "Re-run review before approving or rejecting it."
            )

        expected_hash = document_review_proposal_hash(
            document_id=document.id,
            review_id=review_id,
            reviewed=reviewed,
            preview=recomputed_preview,
        )
        hashes = (
            proposal_hash,
            binding.get("proposal_hash"),
            proposal.get("proposal_hash"),
        )
        if any(
            not isinstance(candidate, str)
            or not hmac.compare_digest(candidate, expected_hash)
            for candidate in hashes
        ):
            raise ValueError(
                "The proposal hash no longer matches this document review. "
                "Re-run review before recording a decision."
            )
        return proposal, reviewed, request_preview_payload

    @staticmethod
    def _finalize_inferred_value_summary(
        *,
        application_summary: dict[str, object],
        inferred_value_count: int,
        reconciliation_summary: dict[str, object],
    ) -> dict[str, object]:
        """Return the durable summary after the atomic inference phase."""
        final_application_summary = dict(application_summary)
        final_application_summary["inferred_values"] = inferred_value_count
        raw_impacts = final_application_summary.get("impacts")
        impacts = (
            [
                str(impact)
                for impact in raw_impacts
                if isinstance(impact, str) and impact != "inferences"
            ]
            if isinstance(raw_impacts, list)
            else []
        )
        if inferred_value_count > 0 and "inferences" not in impacts:
            impacts.append("inferences")
        final_application_summary["impacts"] = impacts
        if impacts == ["date_review"]:
            final_status = "needs_date_review"
        elif impacts:
            final_status = "applied"
        else:
            final_status = "incomplete"
        final_application_summary["status"] = final_status
        final_application_summary["needs_follow_up"] = (
            final_status != "applied"
            or reconciliation_summary.get("status") != "clear"
        )
        return final_application_summary

    def decide_document_review(
        self,
        service: HouseholdFinanceService,
        *,
        document_id: str,
        review_id: str,
        proposal_hash: str,
        proposal_preview: dict[str, object],
        decision: str,
        reason: str | None = None,
    ) -> HouseholdDocumentReviewDecisionResult:
        """Record or recover the sole exact decision for one bound proposal."""
        if decision not in {"approve", "reject"}:
            raise ValueError("Review decision must be approve or reject.")
        document = service.get_document(document_id)
        if document is None:
            raise LookupError("Evidence document not found.")

        existing_summary = document.metadata.get("application_summary")
        application_summary = (
            cast(dict[str, object], existing_summary)
            if isinstance(existing_summary, dict)
            else {"status": "needs_review", "impacts": [], "needs_follow_up": True}
        )
        executor_token = str(uuid.uuid4()) if decision == "approve" else None
        claimed_review_id: str | None = None
        proposal: dict[str, object] = {}
        reviewed: dict[str, object] = {}
        reconciliation_summary: dict[str, object] = {}

        with service.storage.connection() as executor_conn:
            if not try_acquire_document_review_executor(
                executor_conn, document_id=document_id
            ):
                raise ValueError(
                    "This document review is already being processed. Refresh to "
                    "see its current state."
                )
            try:
                binding = fetch_document_review_decision_binding(
                    executor_conn,
                    document_id=document_id,
                    review_id=review_id,
                )
                if binding is None:
                    raise ValueError(
                        "This proposal is no longer available. Re-run document review."
                    )
                proposal, reviewed, preview_payload = self._validate_decision_binding(
                    document=document,
                    binding=binding,
                    review_id=review_id,
                    proposal_hash=proposal_hash,
                    proposal_preview=proposal_preview,
                    decision=decision,
                    stored_path=resolve_document_upload(
                        document.metadata,
                        household_upload_root(service),
                    ),
                    service=service,
                )
                proposed_changes = proposal.get("proposed_changes")
                if decision == "approve" and not (
                    isinstance(proposed_changes, list)
                    and proposed_changes
                    and HouseholdDocumentReviewProposalPreview.model_validate(
                        preview_payload
                    ).has_changes()
                ):
                    raise ValueError(
                        "This review has no explicit money-data changes to approve. "
                        "Reject it or re-run review with clearer evidence."
                    )

                now = datetime.now(UTC).isoformat()
                claimed = claim_document_review_decision(
                    executor_conn,
                    document_id=document_id,
                    review_id=review_id,
                    proposal_hash=proposal_hash,
                    proposal_preview=preview_payload,
                    decision=decision,
                    reason=reason,
                    executor_token=executor_token,
                    now=now,
                )
                if claimed is None:
                    raise ValueError(
                        "This proposal changed, is already complete, or has another "
                        "decision. Refresh before trying again."
                    )
                claimed_review_id = str(claimed["id"])
                if claimed_review_id != review_id:
                    raise RuntimeError(
                        "Claimed document review did not match the requested proposal."
                    )

                if decision == "reject":
                    proposal.update(
                        {"status": "rejected", "decided_at": now, "reason": reason}
                    )
                    if not update_bound_document_review_state(
                        executor_conn,
                        document_id=document_id,
                        review_id=review_id,
                        proposal_hash=proposal_hash,
                        expected_statuses=["pending"],
                        application_summary=application_summary,
                        review_proposal=proposal,
                    ):
                        raise RuntimeError(
                            "Visible review proposal changed before rejection completed."
                        )
                    executor_conn.commit()
                    return HouseholdDocumentReviewDecisionResult(
                        document_id=document_id,
                        review_id=claimed_review_id,
                        decision="reject",
                        status="rejected",
                        application_summary=application_summary,
                    )

                if executor_token is None:
                    raise RuntimeError("Approval executor token was not created.")
                proposal.update(
                    {
                        "status": "applying",
                        "application_started_at": now,
                        "reason": reason,
                    }
                )
                if not update_bound_document_review_state(
                    executor_conn,
                    document_id=document_id,
                    review_id=review_id,
                    proposal_hash=proposal_hash,
                    expected_statuses=["pending", "applying", "failed"],
                    application_summary=application_summary,
                    review_proposal=proposal,
                ):
                    raise RuntimeError(
                        "Visible review proposal changed before approval started."
                    )
                executor_conn.commit()

                phase = str(claimed.get("application_phase") or "claimed")
                journal = (
                    dict(claimed["application_journal"])
                    if isinstance(claimed.get("application_journal"), dict)
                    else {}
                )
                if phase == "claimed":
                    application_summary = self.apply_review_outputs(
                        service,
                        document=document,
                        reviewed=reviewed,
                        bind_upload_account=False,
                    )
                    reconciliation_summary = self._build_reconciliation_summary(
                        document=document,
                        reviewed=reviewed,
                        application_summary=application_summary,
                    )
                    if reconciliation_summary["status"] != "clear":
                        application_summary["needs_follow_up"] = True
                    phase_completed_at = datetime.now(UTC).isoformat()
                    journal_patch = {
                        "application_summary": application_summary,
                        "reconciliation_summary": reconciliation_summary,
                        "outputs_applied_at": phase_completed_at,
                    }
                    if not record_document_review_application_phase(
                        executor_conn,
                        review_id=review_id,
                        executor_token=executor_token,
                        expected_phase="claimed",
                        phase="outputs_applied",
                        journal_patch=journal_patch,
                        now=phase_completed_at,
                    ):
                        raise RuntimeError(
                            "Document review approval lost its exclusive outputs phase."
                        )
                    executor_conn.commit()
                    journal.update(journal_patch)
                    phase = "outputs_applied"
                elif phase in {"outputs_applied", "inferences_applied"}:
                    stored_summary = journal.get("application_summary")
                    stored_reconciliation = journal.get("reconciliation_summary")
                    if not isinstance(stored_summary, dict) or not isinstance(
                        stored_reconciliation, dict
                    ):
                        raise RuntimeError(
                            "Approval journal is incomplete; re-review is required."
                        )
                    application_summary = dict(stored_summary)
                    reconciliation_summary = dict(stored_reconciliation)
                else:
                    raise RuntimeError(
                        f"Unsupported approval recovery phase: {phase}."
                    )

                if phase == "outputs_applied":
                    inferred_at = datetime.now(UTC).isoformat()
                    archive_prior_inferred_values(
                        executor_conn, document_id, inferred_at
                    )
                    inferred_value_count = insert_inferred_values(
                        executor_conn,
                        service,
                        document=document,
                        reviewed=reviewed,
                        now=inferred_at,
                    )
                    application_summary = self._finalize_inferred_value_summary(
                        application_summary=application_summary,
                        inferred_value_count=inferred_value_count,
                        reconciliation_summary=reconciliation_summary,
                    )
                    journal_patch = {
                        "application_summary": application_summary,
                        "inferences_applied_at": inferred_at,
                    }
                    if not record_document_review_application_phase(
                        executor_conn,
                        review_id=review_id,
                        executor_token=executor_token,
                        expected_phase="outputs_applied",
                        phase="inferences_applied",
                        journal_patch=journal_patch,
                        now=inferred_at,
                    ):
                        raise RuntimeError(
                            "Document review approval lost its exclusive inference phase."
                        )
                    executor_conn.commit()
                    journal.update(journal_patch)
                    phase = "inferences_applied"

                if phase != "inferences_applied":
                    raise RuntimeError("Approval did not reach its final durable phase.")
                completed_at = datetime.now(UTC).isoformat()
                proposal.update(
                    {
                        "status": "approved",
                        "decided_at": completed_at,
                        "reason": reason,
                    }
                )
                if not complete_document_review_decision(
                    executor_conn,
                    review_id=review_id,
                    executor_token=executor_token,
                    application_summary=application_summary,
                    now=completed_at,
                ):
                    raise RuntimeError(
                        "Document review approval lost its exclusive finalization phase."
                    )
                if not update_bound_document_review_state(
                    executor_conn,
                    document_id=document_id,
                    review_id=review_id,
                    proposal_hash=proposal_hash,
                    expected_statuses=["applying"],
                    application_summary=application_summary,
                    reconciliation_summary=reconciliation_summary,
                    review_proposal=proposal,
                    document_status="parsed",
                    review_status="approved",
                ):
                    raise RuntimeError(
                        "Visible review proposal changed before approval finalized."
                    )
                executor_conn.commit()

                try:
                    self.upsert_document_signatures(
                        service,
                        document=document,
                        reviewed=reviewed,
                        application_summary=application_summary,
                        reconciliation_summary=reconciliation_summary,
                    )
                except Exception as exc:
                    logger.warning(
                        "household_document_signature_update_failed_after_approval",
                        document_id=document_id,
                        review_id=review_id,
                        error=str(exc),
                    )
            except Exception as exc:
                executor_conn.rollback()
                if claimed_review_id is not None and decision == "approve" and executor_token:
                    failed_at = datetime.now(UTC).isoformat()
                    failed_proposal = dict(proposal)
                    failed_proposal.update(
                        {
                            "status": "failed",
                            "failed_at": failed_at,
                            "failure_message": (
                                "Approval stopped before completion. Retry approval to "
                                "resume from the last durable phase."
                            ),
                        }
                    )
                    try:
                        failure_recorded = fail_document_review_application(
                            executor_conn,
                            review_id=claimed_review_id,
                            executor_token=executor_token,
                            error=str(exc),
                            application_summary=application_summary,
                            now=failed_at,
                        )
                        visible_failure_recorded = update_bound_document_review_state(
                            executor_conn,
                            document_id=document_id,
                            review_id=claimed_review_id,
                            proposal_hash=proposal_hash,
                            expected_statuses=["applying"],
                            application_summary=application_summary,
                            reconciliation_summary=(
                                reconciliation_summary or None
                            ),
                            review_proposal=failed_proposal,
                        )
                        if not failure_recorded or not visible_failure_recorded:
                            raise RuntimeError(
                                "Interrupted approval lost its exclusive failure state."
                            )
                        executor_conn.commit()
                    except Exception as recovery_exc:
                        executor_conn.rollback()
                        logger.exception(
                            "household_document_approval_failure_state_not_persisted",
                            document_id=document_id,
                            review_id=claimed_review_id,
                            error=str(recovery_exc),
                        )
                if claimed_review_id is not None and decision == "approve":
                    raise HouseholdDocumentReviewApplicationError(
                        "Approval paused before completion. Retry approval to resume "
                        "from the last durable phase."
                    ) from exc
                raise
            finally:
                try:
                    release_document_review_executor(
                        executor_conn, document_id=document_id
                    )
                    executor_conn.commit()
                except Exception as unlock_exc:
                    executor_conn.rollback()
                    logger.warning(
                        "household_document_review_executor_unlock_failed",
                        document_id=document_id,
                        error=str(unlock_exc),
                    )

        return HouseholdDocumentReviewDecisionResult(
            document_id=document_id,
            review_id=review_id,
            decision="approve",
            status="applied",
            application_summary=application_summary,
        )

    def _persist_review(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
        now: str,
    ) -> str:
        reviewed = _normalized_review_payload(reviewed=reviewed, document=document)
        review_confidence = to_float(reviewed.get("confidence"))
        held_for_approval = self._review_gate_summaries(reviewed) is not None
        review_status = "needs_review" if held_for_approval else "complete"
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
            review_id = update_document_and_log_review(
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
            if not held_for_approval:
                archive_prior_inferred_values(conn, document.id, now)
                insert_inferred_values(
                    conn,
                    service,
                    document=document,
                    reviewed=reviewed,
                    now=now,
                )
            insert_questions(
                conn, service,
                document=document, reviewed=reviewed, now=now,
                resolved_source_type=resolved_source_type,
                resolved_document_type=resolved_document_type,
                structured_data=structured_data,
                account_hint=account_hint,
            )
            conn.commit()
        return review_id

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
        bind_upload_account: bool = True,
    ) -> dict[str, object]:
        reviewed = _normalized_review_payload(reviewed=reviewed, document=document)
        if bind_upload_account:
            reviewed = _apply_upload_account_binding(
                service,
                document=document,
                reviewed=reviewed,
            )
        import_summary = _import_document_rows(service, document=document, reviewed=reviewed)
        transaction_summary = service.transaction_service.import_document_transactions(
            document=document,
            reviewed=reviewed,
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
        proposal = _safe_dict(metadata.get("review_proposal"))
        if str(proposal.get("status") or "") in {
            "pending",
            "rejected",
            "failed",
        }:
            return existing
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
