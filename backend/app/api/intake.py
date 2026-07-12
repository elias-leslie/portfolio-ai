"""Canonical evidence intake API router."""

from __future__ import annotations

import uuid
from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.models.household_finance import HouseholdDocument, HouseholdDocumentList
from app.services.household_document_review_contracts import (
    HouseholdDocumentReviewApplicationError,
    HouseholdDocumentReviewDecisionRequest,
    HouseholdDocumentReviewDecisionResult,
)
from app.services.household_upload_validation import (
    HouseholdUploadValidationError,
    validate_household_upload_metadata,
)

if TYPE_CHECKING:
    from app.services.household_finance_service import HouseholdFinanceService

router = APIRouter(prefix="/api/intake", tags=["intake"])


@lru_cache(maxsize=1)
def _service() -> HouseholdFinanceService:
    return import_module("app.services.household_finance_service").HouseholdFinanceService()


@router.get("/evidence", response_model=HouseholdDocumentList)
async def list_evidence() -> HouseholdDocumentList:
    """Return recent evidence intake items."""
    return await run_in_threadpool(_service().list_documents)


@router.delete("/evidence/{document_id}", status_code=204)
async def delete_evidence(document_id: str) -> None:
    """Remove a household evidence document and its cascading rows."""
    deleted = await run_in_threadpool(_service().delete_document, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Evidence document not found.")


@router.post("/evidence/{document_id}/review", status_code=202)
async def re_review_evidence(
    background_tasks: BackgroundTasks,
    document_id: str,
) -> dict[str, str]:
    """Re-run the Jenny review pipeline on a stuck or failed evidence document."""
    service = _service()
    document = await run_in_threadpool(service.get_document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Evidence document not found.")
    background_tasks.add_task(service.review_document, document_id)
    return {"status": "queued", "document_id": document_id}


@router.post(
    "/evidence/{document_id}/decision",
    response_model=HouseholdDocumentReviewDecisionResult,
)
async def decide_evidence_review(
    document_id: str,
    payload: HouseholdDocumentReviewDecisionRequest,
) -> HouseholdDocumentReviewDecisionResult:
    """Approve or reject the specified held proposal exactly once."""
    service = _service()
    try:
        return await run_in_threadpool(
            service.decide_document_review,
            document_id,
            review_id=payload.review_id,
            proposal_hash=payload.proposal_hash,
            proposal_preview=payload.proposal_preview.model_dump(mode="json"),
            decision=payload.decision,
            reason=payload.reason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HouseholdDocumentReviewApplicationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/evidence", response_model=HouseholdDocument)
async def upload_evidence(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    source_type: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
    account_label: str | None = Form(default=None),
    household_account_id: str | None = Form(default=None),
    review_session_id: str | None = Form(default=None),
) -> HouseholdDocument:
    """Ingest a financial evidence file through the canonical intake path."""
    service = _service()
    try:
        validate_household_upload_metadata(
            file,
            content_length=request.headers.get("content-length"),
        )
        document = await service.ingest_document(
            upload=file,
            source_type=source_type,
            document_type=document_type,
            account_label=account_label,
            household_account_id=household_account_id,
            review_session_id=review_session_id,
        )
    except HouseholdUploadValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if (
        document.metadata.get("duplicate_detected") is not True
        or document.metadata.get("duplicate_rebound") is True
    ):
        background_tasks.add_task(service.review_document, document.id)
    return document


@router.post("/evidence/batch", response_model=list[HouseholdDocument])
async def upload_evidence_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    source_type: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
    account_label: str | None = Form(default=None),
    household_account_id: str | None = Form(default=None),
    review_session_id: str | None = Form(default=None),
) -> list[HouseholdDocument]:
    """Ingest related evidence files and review them in one Agent Hub session."""
    if not files:
        raise HTTPException(status_code=422, detail="At least one evidence file is required.")
    service = _service()
    resolved_review_session_id = (review_session_id or "").strip() or str(uuid.uuid4())
    documents: list[HouseholdDocument] = []
    try:
        for file in files:
            validate_household_upload_metadata(file)
            documents.append(
                await service.ingest_document(
                    upload=file,
                    source_type=source_type,
                    document_type=document_type,
                    account_label=account_label,
                    household_account_id=household_account_id,
                    review_session_id=resolved_review_session_id,
                )
            )
    except HouseholdUploadValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    review_document_ids = [
        document.id
        for document in documents
        if (
            document.metadata.get("duplicate_detected") is not True
            or document.metadata.get("duplicate_rebound") is True
        )
    ]
    if review_document_ids:
        background_tasks.add_task(
            service.review_documents,
            review_document_ids,
            resolved_review_session_id,
        )
    return documents
