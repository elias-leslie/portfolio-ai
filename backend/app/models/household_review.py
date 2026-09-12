"""A monthly agreement stored in the household's existing confirmed-fact record."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    action: str = Field(min_length=1, max_length=240)
    outcome: Literal["not_reviewed", "kept", "changed", "not_done"] = "not_reviewed"
    note: str = Field(default="", max_length=500)


class MonthlyReviewRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_income: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    planned_asset_draw: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    planned_spending: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    additional_commitments: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    funding_note: str = Field(default="", max_length=1000)
    decisions: list[ReviewDecision] = Field(default_factory=list, max_length=3)


class MonthlyReviewPlan(BaseModel):
    month: str
    record: MonthlyReviewRecord = Field(default_factory=MonthlyReviewRecord)
    confirmed_at: str | None = None
    previous_month: str | None = None
    previous_record: MonthlyReviewRecord | None = None
    expected_income: float | None = None
    income_source: str
    planned_asset_draw: float | None = None
    planned_spending: float | None = None
    additional_commitments: float | None = None
    funding_balance: float | None = None
    unplanned_categories: list[str] = Field(default_factory=list)
    detail: str
