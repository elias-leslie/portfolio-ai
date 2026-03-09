"""Household finance API router."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.models.household_finance import (
    HouseholdDocument,
    HouseholdDocumentList,
    HouseholdFinanceDashboard,
    HouseholdProfile,
    HouseholdProfileUpdate,
    HouseholdQuestion,
    HouseholdQuestionAnswer,
    HouseholdQuestionList,
)
from app.services.household_finance_service import HouseholdFinanceService

router = APIRouter(prefix="/api/household", tags=["household"])
service = HouseholdFinanceService()


@router.get("/dashboard", response_model=HouseholdFinanceDashboard)
async def get_household_dashboard() -> HouseholdFinanceDashboard:
    """Return the household finance dashboard."""
    return await run_in_threadpool(service.get_dashboard)


@router.get("/profile", response_model=HouseholdProfile)
async def get_household_profile() -> HouseholdProfile:
    """Return the persisted household planning profile."""
    return await run_in_threadpool(service.get_profile)


@router.post("/profile", response_model=HouseholdProfile)
async def update_household_profile(payload: HouseholdProfileUpdate) -> HouseholdProfile:
    """Update household planning assumptions."""
    return await run_in_threadpool(service.update_profile, payload)


@router.get("/documents", response_model=HouseholdDocumentList)
async def list_household_documents() -> HouseholdDocumentList:
    """Return recent household documents."""
    return await run_in_threadpool(service.list_documents)


@router.get("/questions", response_model=HouseholdQuestionList)
async def list_household_questions() -> HouseholdQuestionList:
    """Return Jenny's open household follow-up questions."""
    return await run_in_threadpool(service.list_questions)


@router.post("/questions/{question_id}/answer", response_model=HouseholdQuestion)
async def answer_household_question(
    question_id: str,
    payload: HouseholdQuestionAnswer,
) -> HouseholdQuestion:
    """Answer a Jenny follow-up question and persist any confirmed value."""
    question = await run_in_threadpool(service.answer_question, question_id, payload)
    if question is None:
        raise HTTPException(status_code=404, detail=f"Household question not found: {question_id}")
    return question


@router.post("/documents", response_model=HouseholdDocument)
async def upload_household_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_type: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
    account_label: str | None = Form(default=None),
) -> HouseholdDocument:
    """Stage a household document for future parsing."""
    document = await service.ingest_document(
        upload=file,
        source_type=source_type,
        document_type=document_type,
        account_label=account_label,
    )
    background_tasks.add_task(service.review_document, document.id)
    return document
