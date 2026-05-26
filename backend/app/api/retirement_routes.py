"""Retirement Monte Carlo router (F5).

Thin serializer over :class:`RetirementPlanningService`. Three
endpoints per the plan:

- ``POST /api/retirement/scenarios`` — build inputs, run + persist
- ``GET /api/retirement/scenarios?household_id=…`` — list summaries
- ``GET /api/retirement/scenarios/{id}?detail=…`` — show one (compact
  by default, ``?detail=true`` adds percentile paths + CMA snapshot)

No Hatchet workflow; runs are user-initiated, capped at 50k trials.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from importlib import import_module
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.logging_config import get_logger
from app.portfolio.contracts.retirement import (
    RetirementInputs,
    RetirementPreview,
    ScenarioResults,
    ScenarioSummary,
)
from app.services.retirement_planning_service import (
    DEFAULT_LIST_LIMIT,
    DEFAULT_TRIALS,
    MAX_LIST_LIMIT,
    MAX_TRIALS,
    RetirementPlanningService,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/retirement", tags=["retirement"])


@lru_cache(maxsize=1)
def _storage() -> Any:
    return import_module("app.storage").get_storage()


@lru_cache(maxsize=1)
def _service() -> RetirementPlanningService:
    return RetirementPlanningService(_storage())


class RunScenarioRequest(BaseModel):
    household_id: str = Field(..., min_length=1, max_length=64)
    name: str | None = Field(None, max_length=128)
    trials: int = Field(DEFAULT_TRIALS, ge=1, le=MAX_TRIALS)
    seed: int | None = Field(None)
    annual_expenses: float | None = Field(None, ge=0.0)
    annual_contribution: float | None = Field(None, ge=0.0)
    retirement_age: int | None = Field(None, ge=18, le=120)
    horizon_years: int | None = Field(None, ge=1, le=70)
    inflation_rate: float | None = Field(None, ge=0.0, le=0.2)
    social_security_payable_ratio: float | None = Field(None, ge=0.0, le=1.0)
    primary_age: int | None = Field(None, ge=18, le=120)
    spouse_age: int | None = Field(None, ge=18, le=120)
    as_of_date: date | None = None


class PreviewRequest(RunScenarioRequest):
    monthly_spend: float | None = Field(None, ge=0.0)
    primary_social_security_monthly: float | None = Field(None, ge=0.0)
    spouse_social_security_monthly: float | None = Field(None, ge=0.0)
    primary_social_security_annual_earnings: float | None = Field(None, ge=0.0)
    spouse_social_security_annual_earnings: float | None = Field(None, ge=0.0)
    primary_social_security_start_age: int | None = Field(None, ge=62, le=70)
    spouse_social_security_start_age: int | None = Field(None, ge=62, le=70)


@router.post("/scenarios")
async def run_scenario(payload: RunScenarioRequest) -> dict[str, Any]:
    """Build inputs from household + portfolio, run the simulation, persist."""
    service = _service()

    def _execute() -> ScenarioResults:
        inputs: RetirementInputs = service.build_inputs(
            payload.household_id,
            annual_expenses=payload.annual_expenses,
            annual_contribution=payload.annual_contribution,
            retirement_age=payload.retirement_age,
            horizon_years=payload.horizon_years,
            inflation_rate=payload.inflation_rate,
            social_security_payable_ratio=payload.social_security_payable_ratio,
            primary_age=payload.primary_age,
            spouse_age=payload.spouse_age,
            as_of_date=payload.as_of_date,
        )
        sim = service.run_simulation(inputs, trials=payload.trials, seed=payload.seed)
        name = payload.name or _default_scenario_name(inputs)
        return service.save_scenario(
            name=name, inputs=inputs, sim=sim, trials=payload.trials
        )

    results = await run_in_threadpool(_execute)
    return results.model_dump(mode="json")


@router.post("/preview")
async def preview(payload: PreviewRequest) -> dict[str, Any]:
    """Return a non-persisted account-type-aware retirement preview."""
    service = _service()

    def _execute() -> RetirementPreview:
        return service.preview(
            payload.household_id,
            annual_expenses=payload.annual_expenses,
            monthly_spend=payload.monthly_spend,
            retirement_age=payload.retirement_age,
            horizon_years=payload.horizon_years,
            annual_contribution=payload.annual_contribution,
            inflation_rate=payload.inflation_rate,
            social_security_payable_ratio=payload.social_security_payable_ratio,
            primary_age=payload.primary_age,
            spouse_age=payload.spouse_age,
            primary_social_security_monthly=payload.primary_social_security_monthly,
            spouse_social_security_monthly=payload.spouse_social_security_monthly,
            primary_social_security_annual_earnings=payload.primary_social_security_annual_earnings,
            spouse_social_security_annual_earnings=payload.spouse_social_security_annual_earnings,
            primary_social_security_start_age=payload.primary_social_security_start_age,
            spouse_social_security_start_age=payload.spouse_social_security_start_age,
            trials=payload.trials,
            seed=payload.seed,
            as_of_date=payload.as_of_date,
        )

    preview_result = await run_in_threadpool(_execute)
    return preview_result.model_dump(mode="json")


@router.get("/scenarios")
async def list_scenarios(
    household_id: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
) -> list[dict[str, Any]]:
    service = _service()
    rows: list[ScenarioSummary] = await run_in_threadpool(
        service.list_scenarios, household_id, limit=limit
    )
    return [row.model_dump(mode="json") for row in rows]


@router.get("/scenarios/{scenario_id}")
async def show_scenario(
    scenario_id: str,
    detail: bool = Query(False),
) -> dict[str, Any]:
    service = _service()
    results: ScenarioResults | None = await run_in_threadpool(
        service.show_scenario, scenario_id, detail=detail
    )
    if results is None:
        raise HTTPException(status_code=404, detail="scenario_not_found")
    return results.model_dump(mode="json")


def _default_scenario_name(inputs: RetirementInputs) -> str:
    return (
        f"Retire at {inputs.retirement_age}, "
        f"{inputs.horizon_years}y horizon, "
        f"${inputs.annual_expenses:,.0f}/yr"
    )
