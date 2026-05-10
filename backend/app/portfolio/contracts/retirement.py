"""Pydantic contracts for the retirement Monte Carlo simulator (F5).

The canonical service is ``app/services/retirement_planning_service.py``;
it builds these contracts from household + portfolio sources and
returns them. Field names stay technical
(``success_probability``, ``sequence_of_returns_risk``); the
plain-English translations from the plan's UX language table happen at
the render boundary, never in the contract.

Token-saving: ``ScenarioSummary`` is the compact list view; the full
``ScenarioResults`` (with percentile paths and the CMA snapshot) is
opt-in via ``GET /api/retirement/scenarios/{id}?detail=true``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RetirementIncomeSource(BaseModel):
    """One household_retirement_income_sources row, normalised for sim."""

    model_config = ConfigDict(frozen=True)

    label: str
    source_type: str | None = None
    owner_name: str | None = None
    start_age: int = Field(..., ge=0, le=120)
    monthly_amount: float = Field(0.0, ge=0.0)
    inflation_adjusted: bool = False
    survivor_benefit: float | None = Field(None, ge=0.0)


class RetirementInputs(BaseModel):
    """Snapshot of the household + portfolio data driving a scenario.

    The service builds this once via ``build_inputs(household_id)``;
    the JSON shape is persisted in ``retirement_scenarios.inputs`` so
    that comparison runs against later household state remain
    reproducible.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    household_id: str
    primary_age: int = Field(..., ge=0, le=120)
    spouse_age: int | None = Field(None, ge=0, le=120)
    retirement_age: int = Field(..., ge=18, le=120)
    horizon_years: int = Field(30, ge=1, le=70)
    annual_expenses: float = Field(..., ge=0.0)
    portfolio_value: float = Field(..., ge=0.0)
    asset_allocation: dict[str, float] = Field(default_factory=dict)
    income_sources: tuple[RetirementIncomeSource, ...] = ()
    inflation_rate: float = Field(0.025, ge=0.0, le=0.2)
    as_of_date: date


class ScenarioSummary(BaseModel):
    """Compact list-view row.

    Stored in ``retirement_scenarios`` as the cheap aggregate result —
    the simulation engine writes ``ScenarioResults`` to ``results`` and
    a ``ScenarioSummary`` is what list endpoints return.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    id: str
    household_id: str
    name: str
    success_probability: float = Field(..., ge=0.0, le=1.0)
    median_ending_balance: float
    sequence_of_returns_risk: float = Field(..., ge=0.0, le=1.0)
    trial_count: int = Field(..., ge=1, le=50_000)
    cma_source: str
    created_at: datetime


class ScenarioResults(BaseModel):
    """Full result body for one Monte Carlo run.

    ``percentiles`` is a {label: value} map (e.g.
    ``{"p10": 120000.0, "p50": 480000.0, "p90": 1200000.0}``).
    ``ending_balance_paths`` is opt-in detail (one float per percentile
    track per year) and can be null in the compact response.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    summary: ScenarioSummary
    inputs: RetirementInputs
    percentiles: dict[str, float]
    failure_year_distribution: dict[str, int] = Field(default_factory=dict)
    ending_balance_paths: dict[str, list[float]] | None = None
    cma_snapshot: dict[str, Any] | None = None
