"""Credit-card management API (plan §9).

Mounted at ``/api/household/cards``. Mirrors household.py: ``@lru_cache`` service
singletons, all DB work pushed to a threadpool. Ranking/rotation outputs carry the
standing disclaimer (CARD_ADVICE_DISCLAIMER) — decision-support modeling of public
reward structures, not personalized financial advice.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.models.credit_cards import (
    CardRanking,
    CreditCardCreate,
    CreditCardProduct,
    CreditCardUpdate,
    HouseholdCreditCard,
    RankingRequest,
    RotationPlanView,
    RotationRequest,
    SoftCharge,
)

if TYPE_CHECKING:
    from app.services.card_management_service import CardManagementService
    from app.services.household_soft_charge_service import HouseholdSoftChargeService

router = APIRouter(prefix="/api/household/cards", tags=["cards"])


@lru_cache(maxsize=1)
def _service() -> CardManagementService:
    return import_module("app.services.card_management_service").CardManagementService()


@lru_cache(maxsize=1)
def _soft_service() -> HouseholdSoftChargeService:
    return import_module("app.services.household_soft_charge_service").HouseholdSoftChargeService()


@lru_cache(maxsize=1)
def _household_service() -> object:
    return import_module("app.services.household_finance_service").HouseholdFinanceService()


# ----------------------------------------------------------------- catalog


@router.get("/catalog", response_model=list[CreditCardProduct])
async def get_catalog() -> list[CreditCardProduct]:
    return await run_in_threadpool(_service().get_catalog)


# -------------------------------------------------------------- owned cards


@router.get("", response_model=list[HouseholdCreditCard])
async def list_cards() -> list[HouseholdCreditCard]:
    return await run_in_threadpool(_service().list_owned_cards)


@router.post("", response_model=HouseholdCreditCard, status_code=201)
async def create_card(body: CreditCardCreate) -> HouseholdCreditCard:
    try:
        return await run_in_threadpool(_service().create_owned_card, body)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{card_id}", response_model=HouseholdCreditCard)
async def update_card(card_id: str, body: CreditCardUpdate) -> HouseholdCreditCard:
    try:
        return await run_in_threadpool(_service().update_owned_card, card_id, body)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{card_id}/activate", response_model=HouseholdCreditCard)
async def activate_card(card_id: str) -> HouseholdCreditCard:
    try:
        return await run_in_threadpool(_service().activate_card, card_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{card_id}", status_code=204)
async def delete_card(card_id: str) -> None:
    try:
        await run_in_threadpool(_service().delete_owned_card, card_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ------------------------------------------------------- ranking / rotation


@router.post("/rankings", response_model=CardRanking)
async def rank_cards(body: RankingRequest) -> CardRanking:
    return await run_in_threadpool(_service().build_ranking, body)


@router.post("/rotation-plan", response_model=RotationPlanView)
async def rotation_plan(body: RotationRequest) -> RotationPlanView:
    return await run_in_threadpool(_service().build_rotation, body)


@router.get("/rotation-plans")
async def list_rotation_plans() -> list[dict]:
    return await run_in_threadpool(_service().list_rotation_plans)


@router.get("/rotation-plan/{plan_id}", response_model=RotationPlanView)
async def get_rotation_plan(plan_id: str) -> RotationPlanView:
    try:
        return await run_in_threadpool(_service().get_rotation_plan, plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ----------------------------------------------------------- offer intake


@router.post("/intake", status_code=201)
async def intake_card_offer(
    file: UploadFile = File(...),
    document_type: str = Form("offer_screenshot"),
) -> object:
    """Upload a card-offer screenshot/agreement; the credit-card-offer-reviewer
    Agent Hub agent extracts terms into the catalog synchronously so the UI can
    show them for confirmation (plan §9)."""
    service = _household_service()
    document = await service.ingest_document(
        upload=file, source_type="credit_card_offer", document_type=document_type
    )
    offer_service = import_module("app.services.card_offer_agent_service").get_card_offer_agent_service()
    try:
        return await run_in_threadpool(offer_service.process_offer_document, service, document)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=f"Card offer extraction failed: {exc}") from exc


# ----------------------------------------------------------- catalog research


@router.post("/research/refresh")
async def refresh_catalog_research() -> dict[str, object]:
    """On-demand catalog refresh via the credit-card-researcher Agent Hub agent
    (also runs monthly from household maintenance). Verifies fees/bonuses/
    valuations against current public sources and applies whitelisted changes."""
    research_service = import_module("app.services.card_research_service").get_card_research_service()
    try:
        return await run_in_threadpool(research_service.refresh_catalog, trigger="on_demand")
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=f"Catalog research failed: {exc}") from exc


# ----------------------------------------------------------- soft charges


@router.post("/soft-charges", response_model=SoftCharge, status_code=201)
async def create_soft_charge(
    amount: float = Form(...),
    description: str = Form(...),
    merchant: str | None = Form(None),
    category: str | None = Form(None),
    essentiality: str | None = Form(None),
    occurred_at: str | None = Form(None),
    household_account_id: str | None = Form(None),
    receipt: UploadFile | None = File(None),
) -> SoftCharge:
    """Phone-entered provisional charge. Counts toward budget immediately via a
    mirror row in the canonical ledger (plan §5). An optional receipt photo is
    ingested through the existing document pipeline and linked."""
    source_document_id: str | None = None
    if receipt is not None and receipt.filename:
        document = await _household_service().ingest_document(
            upload=receipt, source_type="receipt", document_type="receipt"
        )
        source_document_id = document.id
    try:
        soft_charge = await run_in_threadpool(
            _soft_service().create_soft_charge,
            amount=amount,
            description=description,
            merchant=merchant,
            category=category,
            essentiality=essentiality,
            occurred_at=occurred_at,
            household_account_id=household_account_id,
            source_document_id=source_document_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # A phone-entered charge that trips the cap must push immediately (plan §8:
    # the "never surprised" requirement). Alert failures never fail the charge.
    try:
        alert_service = import_module("app.services.spend_alert_service")
        await run_in_threadpool(alert_service.evaluate_and_dispatch, trigger="soft_charge")
    except Exception:
        pass
    return soft_charge


@router.get("/soft-charges", response_model=list[SoftCharge])
async def list_soft_charges(
    status: str | None = Query(None),
) -> list[SoftCharge]:
    return await run_in_threadpool(_soft_service().list_soft_charges, status=status)


@router.post("/soft-charges/{soft_id}/match", response_model=SoftCharge)
async def match_soft_charge(soft_id: str, plaid_transaction_id: str = Form(...)) -> SoftCharge:
    try:
        return await run_in_threadpool(
            _soft_service().match_soft_charge, soft_id, plaid_transaction_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/soft-charges/{soft_id}", status_code=204)
async def delete_soft_charge(soft_id: str) -> None:
    try:
        await run_in_threadpool(_soft_service().delete_soft_charge, soft_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
