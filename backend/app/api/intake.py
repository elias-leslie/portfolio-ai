"""Canonical evidence intake API router."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.models.household_finance import HouseholdDocument, HouseholdDocumentList

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
    file: UploadFile = File(...),
    source_type: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
    account_label: str | None = Form(default=None),
    household_account_id: str | None = Form(default=None),
) -> HouseholdDocument:
    """Ingest a financial evidence file through the canonical intake path."""
    service = _service()
    document = await service.ingest_document(
        upload=file,
        source_type=source_type,
        document_type=document_type,
        account_label=account_label,
        household_account_id=household_account_id,
    )
    if (
        document.metadata.get("duplicate_detected") is not True
        or document.metadata.get("duplicate_rebound") is True
    ):
        background_tasks.add_task(service.review_document, document.id)
    return document
