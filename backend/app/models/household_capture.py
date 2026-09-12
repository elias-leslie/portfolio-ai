"""Capturing evidence and describing a purchase are separate facts."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CaptureView(BaseModel):
    id: str
    captured_by: str | None = None
    captured_by_name: str
    kind: Literal["receipt", "shelf_tag"]
    filename: str
    store_name: str
    note: str
    status: str
    outcome: Literal["unknown", "purchased", "not_purchased"]
    purchased_by: str | None = None
    purchased_for: str | None = None
    document_id: str | None = None
    review_note: str
    created_at: str


class CaptureReview(BaseModel):
    status: Literal["pending_review", "verified", "needs_correction"]
    outcome: Literal["unknown", "purchased", "not_purchased"] = "unknown"
    purchased_by: UUID | None = None
    purchased_for: UUID | None = None
    review_note: str = Field(min_length=1, max_length=1000)
