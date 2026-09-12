"""Minimal signed-in identity; email addresses stay server-side."""

from fastapi import APIRouter, Request

from app.services.household_identity import HouseholdIdentity, request_identity

router = APIRouter()


@router.get("/api/identity", response_model=HouseholdIdentity)
def identity(request: Request) -> HouseholdIdentity:
    return request_identity(request)
