"""TLH (tax-loss-harvesting) routes — thin serializer over TLHAnalyzer.

This module owns *no* analytics. Every endpoint instantiates a single
``TLHAnalyzer`` (via ``lru_cache`` helpers) and returns its Pydantic
contracts. Token-efficient defaults are enforced here by excluding
detail-only fields when ``detail=False``.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from importlib import import_module
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.logging_config import get_logger
from app.portfolio.contracts.tlh import TLHCandidate, WashSaleVerdict

logger = get_logger(__name__)

router = APIRouter(prefix="/tlh", tags=["portfolio-tlh"])


# Fields excluded from the TLHCandidate payload when ``detail=False``.
# Keeps default responses to {symbol, account_id, account_type, shares,
# cost_basis, current_price, current_value, unrealized_loss,
# unrealized_loss_pct, schema_version} — the four most-actionable fields
# the plan calls out plus the contextual identity columns.
_DETAIL_ONLY_FIELDS = {
    "holding_period_days",
    "realized_loss_long_term",
    "realized_loss_short_term",
    "replacement",
    "wash_sale_blocked",
    "wash_sale_reason",
}


@lru_cache(maxsize=1)
def _storage():
    return import_module("app.storage").get_storage()


@lru_cache(maxsize=1)
def _ledger():
    return import_module("app.portfolio.transactions").TransactionLedger(_storage())


@lru_cache(maxsize=1)
def _price_fetcher():
    return import_module("app.portfolio.price_fetcher").PriceDataFetcher(_storage())


@lru_cache(maxsize=1)
def _tlh_analyzer():
    tlh_module = import_module("app.portfolio.tlh")
    return tlh_module.TLHAnalyzer(_storage(), _ledger(), _price_fetcher())


class WashSaleCheckRequest(BaseModel):
    """Body for POST /tlh/wash-sale-check."""

    symbol: str = Field(..., min_length=1, max_length=32)
    sell_date: date
    household_id: str | None = None


def _serialize_candidate(candidate: TLHCandidate, *, detail: bool) -> dict[str, Any]:
    if detail:
        return candidate.model_dump(mode="json")
    return candidate.model_dump(mode="json", exclude=_DETAIL_ONLY_FIELDS)


def _candidates_payload(
    *,
    limit: int,
    min_loss: float,
    min_loss_pct: float,
    detail: bool,
) -> list[dict[str, Any]]:
    candidates = _tlh_analyzer().find_loss_candidates(
        min_loss_pct=min_loss_pct,
        min_loss_amount=min_loss,
        limit=limit,
        detail=detail,
    )
    return [_serialize_candidate(c, detail=detail) for c in candidates]


@router.get("/candidates")
async def get_tlh_candidates(
    limit: int = Query(20, ge=1, le=100),
    min_loss: float = Query(500.0, ge=0.0),
    min_loss_pct: float = Query(0.05, ge=0.0, le=1.0),
    detail: bool = Query(False),
) -> list[dict[str, Any]]:
    """Return up to ``limit`` taxable positions trading below cost.

    Default fields stay compact: ``symbol``, ``account_id``,
    ``unrealized_loss``, ``unrealized_loss_pct`` (plus contextual
    identity columns). ``detail=true`` adds replacement, holding
    period, ST/LT loss split, and wash-sale annotations.
    """
    return await run_in_threadpool(
        _candidates_payload,
        limit=limit,
        min_loss=min_loss,
        min_loss_pct=min_loss_pct,
        detail=detail,
    )


def _wash_sale_payload(payload: WashSaleCheckRequest) -> WashSaleVerdict:
    return _tlh_analyzer().wash_sale_check(
        symbol=payload.symbol,
        sell_date=payload.sell_date,
        household_id=payload.household_id,
    )


@router.post("/wash-sale-check", response_model=WashSaleVerdict)
async def post_wash_sale_check(payload: WashSaleCheckRequest) -> WashSaleVerdict:
    """Scan the household's 61-day window for substantially-identical buys.

    Per IRS Pub 550 and Rev. Rul. 2008-5, the scan covers spouse
    accounts and tax-advantaged accounts (Roth, IRA, 401k, HSA).
    """
    return await run_in_threadpool(_wash_sale_payload, payload)
