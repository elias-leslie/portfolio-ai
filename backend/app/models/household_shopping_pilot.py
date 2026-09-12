"""A small evidence-backed shopping workflow, without purchase inference."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PilotProduct(BaseModel):
    id: str
    name: str
    stores: list[str]


class PackageConfirmation(BaseModel):
    fingerprint: str
    package_label: str = Field(min_length=2, max_length=100)
    packages: float = Field(gt=0, le=1000, allow_inf_nan=False)
    evidence: str = Field(min_length=5, max_length=500)


class OfferConfirmation(BaseModel):
    product_id: UUID
    capture_id: UUID | None = None
    store: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=3, max_length=300)
    package_label: str = Field(min_length=2, max_length=100)
    price: float = Field(gt=0, le=10000, allow_inf_nan=False)
    fees: float = Field(ge=0, le=1000, allow_inf_nan=False)
    coupon: float = Field(ge=0, le=10000, allow_inf_nan=False)
    observed_date: date
    valid_until: date
    availability_confirmed: Literal[True]
    equivalence_confirmed: Literal[True]
    membership_confirmed: Literal[True]
    coupon_confirmed: Literal[True]
    fees_confirmed: Literal[True]
    conditions: str = Field(min_length=5, max_length=500)
    costco_item_number: str | None = Field(default=None, pattern=r"^\d{3,8}$")


class FamilyConfirmation(BaseModel):
    product_ids: list[UUID] = Field(min_length=2, max_length=10)
    name: str = Field(min_length=3, max_length=100)
    purpose: str = Field(min_length=10, max_length=500)


class ShoppingComparison(BaseModel):
    product_id: UUID
    package_label: str = Field(min_length=2, max_length=100)
    total_price: float = Field(gt=0, le=10000, allow_inf_nan=False)


class ComparisonResult(BaseModel):
    status: Literal["needs_evidence", "lower_recorded_offer", "no_lower_recorded_offer"]
    explanation: str
    entered_unit_price: float | None = None
    unit: str | None = None
    alternative_store: str | None = None
    alternative_package: str | None = None
    alternative_price: float | None = None
    alternative_date: str | None = None
    equivalent_difference: float | None = None
    conditions: str | None = None
