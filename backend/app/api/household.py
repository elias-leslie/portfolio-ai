"""Household finance API router."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.middleware.cache import cache_response
from app.models.household_finance import (
    ConfirmFactRequest,
    HouseholdConfirmedFact,
    HouseholdDocument,
    HouseholdDocumentList,
    HouseholdFinanceDashboard,
    HouseholdLedger,
    HouseholdNetWorthTrend,
    HouseholdProfile,
    HouseholdProfileUpdate,
    HouseholdQuestion,
    HouseholdQuestionAnswer,
    HouseholdQuestionList,
    HouseholdSpendingView,
    HouseholdTrackedAccount,
    HouseholdTrackedAccountInput,
    HouseholdTransactionCategoryUpdate,
)
from app.models.household_planning import HouseholdPlanningSnapshot, HouseholdPlanningUpdate
from app.services.household_upload_validation import (
    HouseholdUploadValidationError,
    validate_household_upload_metadata,
)

if TYPE_CHECKING:
    from app.services.household_finance_service import HouseholdFinanceService

router = APIRouter(prefix="/api/household", tags=["household"])


@lru_cache(maxsize=1)
def _service() -> HouseholdFinanceService:
    return import_module("app.services.household_finance_service").HouseholdFinanceService()


@router.get("/dashboard", response_model=HouseholdFinanceDashboard)
@cache_response(ttl=60)
async def get_household_dashboard(request: Request) -> HouseholdFinanceDashboard:
    """Return the household finance dashboard."""
    del request
    return await run_in_threadpool(_service().get_dashboard)


@router.get("/net-worth-trend", response_model=HouseholdNetWorthTrend)
@cache_response(ttl=60)
async def get_household_net_worth_trend(
    request: Request,
    days: int = Query(180, ge=7, le=1825),
) -> HouseholdNetWorthTrend:
    """Return known net-worth trend from current holdings and latest balances."""
    del request
    return await run_in_threadpool(_service().get_net_worth_trend, days=days)


@router.get("/ledger", response_model=HouseholdLedger)
async def get_household_ledger(
    window: str = "all",
    kind: str = "all",
    status: str = "all",
    account: str = "all",
    search: str = "",
    sort: str = "date",
    sort_dir: str = "desc",
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> HouseholdLedger:
    """Return a filtered, sorted, paginated page of household ledger provenance."""
    return await run_in_threadpool(
        _service().get_ledger,
        window=window,
        kind=kind,
        status=status,
        account=account,
        search=search,
        sort=sort,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )


@router.get("/spending", response_model=HouseholdSpendingView)
async def get_household_spending(window: str = "1m") -> HouseholdSpendingView:
    """Return timeframe-aware household spending analytics."""
    return await run_in_threadpool(_service().get_spending, window=window)


@router.get("/profile", response_model=HouseholdProfile)
async def get_household_profile() -> HouseholdProfile:
    """Return the persisted household planning profile."""
    return await run_in_threadpool(_service().get_profile)


@router.post("/profile", response_model=HouseholdProfile)
async def update_household_profile(payload: HouseholdProfileUpdate) -> HouseholdProfile:
    """Update household planning assumptions."""
    return await run_in_threadpool(_service().update_profile, payload)


@router.get("/planning", response_model=HouseholdPlanningSnapshot)
async def get_household_planning() -> HouseholdPlanningSnapshot:
    """Return the typed household planning snapshot."""
    return await run_in_threadpool(_service().get_planning_snapshot)


@router.post("/planning", response_model=HouseholdPlanningSnapshot)
async def update_household_planning(payload: HouseholdPlanningUpdate) -> HouseholdPlanningSnapshot:
    """Replace or update typed planning sections."""
    return await run_in_threadpool(_service().update_planning_snapshot, payload)


@router.get("/documents", response_model=HouseholdDocumentList)
async def list_household_documents() -> HouseholdDocumentList:
    """Return recent household documents."""
    return await run_in_threadpool(_service().list_documents)


@router.get("/questions", response_model=HouseholdQuestionList)
async def list_household_questions() -> HouseholdQuestionList:
    """Return Jenny's open household follow-up questions."""
    return await run_in_threadpool(_service().list_questions)


@router.get("/accounts", response_model=list[HouseholdTrackedAccount])
async def list_household_accounts() -> list[HouseholdTrackedAccount]:
    """Return household account display preferences."""
    return await run_in_threadpool(_service().list_tracked_accounts)


@router.post("/accounts", response_model=HouseholdTrackedAccount)
async def create_household_account(
    payload: HouseholdTrackedAccountInput,
) -> HouseholdTrackedAccount:
    """Create a canonical household account or display preferences."""
    try:
        return await run_in_threadpool(_service().create_tracked_account, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/accounts/{account_id}", response_model=HouseholdTrackedAccount)
async def update_household_account(
    account_id: str,
    payload: HouseholdTrackedAccountInput,
) -> HouseholdTrackedAccount:
    """Update household account display preferences."""
    try:
        account = await run_in_threadpool(
            _service().update_tracked_account,
            account_id,
            payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if account is None:
        raise HTTPException(status_code=404, detail=f"Household account not found: {account_id}")
    return account


@router.delete("/accounts/{account_id}")
async def delete_household_account(account_id: str) -> dict[str, bool]:
    """Delete household account display preferences."""
    deleted = await run_in_threadpool(_service().delete_tracked_account, account_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Household account not found: {account_id}")
    return {"ok": True}


@router.post("/questions/{question_id}/answer", response_model=HouseholdQuestion)
async def answer_household_question(
    question_id: str,
    payload: HouseholdQuestionAnswer,
) -> HouseholdQuestion:
    """Answer a Jenny follow-up question and persist any confirmed value."""
    question = await run_in_threadpool(_service().answer_question, question_id, payload)
    if question is None:
        raise HTTPException(status_code=404, detail=f"Household question not found: {question_id}")
    return question


@router.post("/documents", response_model=HouseholdDocument)
async def upload_household_document(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    source_type: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
    account_label: str | None = Form(default=None),
    household_account_id: str | None = Form(default=None),
) -> HouseholdDocument:
    """Stage a household document for future parsing."""
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


@router.get("/facts", response_model=list[HouseholdConfirmedFact])
async def list_confirmed_facts() -> list[HouseholdConfirmedFact]:
    """Return all confirmed household facts."""
    return await run_in_threadpool(_service().list_confirmed_facts)


@router.post("/facts", response_model=HouseholdConfirmedFact)
async def confirm_fact(payload: ConfirmFactRequest) -> HouseholdConfirmedFact:
    """Upsert a confirmed household fact by key."""
    return await run_in_threadpool(_service().confirm_fact, payload.fact_key, payload.fact_value)


class AskJennyRequest(BaseModel):
    question: str


@router.post("/ask", response_model=HouseholdQuestion)
async def ask_jenny(payload: AskJennyRequest) -> HouseholdQuestion:
    """Create a user-initiated question directed at Jenny."""
    question_text = payload.question.strip()
    if not question_text:
        raise HTTPException(status_code=422, detail="Question text cannot be empty")
    return await run_in_threadpool(_service().ask_jenny, question_text)


@router.post("/transactions/{transaction_id}/categorize")
async def categorize_household_transaction(
    transaction_id: str,
    payload: HouseholdTransactionCategoryUpdate,
) -> dict[str, bool]:
    """Confirm category and essentiality for a household transaction."""
    updated = await run_in_threadpool(_service().update_transaction_category, transaction_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Household transaction not found: {transaction_id}")
    return {"ok": True}
