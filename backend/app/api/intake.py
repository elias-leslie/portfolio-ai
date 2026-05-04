"""Canonical evidence intake API router."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.models.household_finance import HouseholdDocument, HouseholdDocumentList
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


@router.post("/evidence", response_model=HouseholdDocument)
async def upload_evidence(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    source_type: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
    account_label: str | None = Form(default=None),
    household_account_id: str | None = Form(default=None),
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
        )
    except HouseholdUploadValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if (
        document.metadata.get("duplicate_detected") is not True
        or document.metadata.get("duplicate_rebound") is True
    ):
        background_tasks.add_task(service.review_document, document.id)
    return document
