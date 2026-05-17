"""Plaid API routes for household finance data linking."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, SecretStr

from app.services.credential_crypto import SecretDecryptionError, SecretKeyUnavailableError
from app.services.plaid_service import (
    PlaidConfigurationError,
    PlaidIntegrationError,
    PlaidService,
)

router = APIRouter(prefix="/api/plaid", tags=["plaid"])


class PlaidConfigureRequest(BaseModel):
    client_id: SecretStr | None = None
    secret: SecretStr | None = None
    environment: str = "sandbox"
    products: list[str] = Field(default_factory=lambda: ["transactions"])
    country_codes: list[str] = Field(default_factory=lambda: ["US"])
    redirect_uri: str | None = None


class PlaidPublicTokenExchangeRequest(BaseModel):
    public_token: SecretStr
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlaidSyncRequest(BaseModel):
    item_id: str | None = None


def _service() -> PlaidService:
    return PlaidService()


def _raise_public_error(exc: Exception) -> None:
    if isinstance(exc, PlaidIntegrationError):
        raise HTTPException(status_code=exc.status_code, detail=exc.error_payload) from exc
    if isinstance(exc, PlaidConfigurationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, (SecretDecryptionError, SecretKeyUnavailableError)):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail="Plaid request failed.") from exc


@router.get("/status")
async def get_plaid_status() -> dict[str, object]:
    try:
        return await run_in_threadpool(_service().get_status)
    except Exception as exc:
        _raise_public_error(exc)
        raise


@router.post("/configure")
async def configure_plaid(payload: PlaidConfigureRequest) -> dict[str, object]:
    try:
        return await run_in_threadpool(
            _service().configure,
            client_id=payload.client_id.get_secret_value() if payload.client_id else None,
            secret=payload.secret.get_secret_value() if payload.secret else None,
            environment=payload.environment,
            products=payload.products,
            country_codes=payload.country_codes,
            redirect_uri=payload.redirect_uri,
        )
    except Exception as exc:
        _raise_public_error(exc)
        raise


@router.post("/link-token")
async def create_plaid_link_token() -> dict[str, object]:
    try:
        return await run_in_threadpool(_service().create_link_token)
    except Exception as exc:
        _raise_public_error(exc)
        raise


@router.post("/exchange-public-token")
async def exchange_plaid_public_token(
    payload: PlaidPublicTokenExchangeRequest,
) -> dict[str, object]:
    try:
        return await run_in_threadpool(
            _service().exchange_public_token,
            public_token=payload.public_token.get_secret_value(),
            metadata=payload.metadata,
        )
    except Exception as exc:
        _raise_public_error(exc)
        raise


@router.post("/sync")
async def sync_plaid_items(payload: PlaidSyncRequest | None = None) -> dict[str, object]:
    try:
        return await run_in_threadpool(
            _service().sync_items,
            item_id=payload.item_id if payload else None,
        )
    except Exception as exc:
        _raise_public_error(exc)
        raise


@router.delete("/items/{item_id}")
async def remove_plaid_item(item_id: str) -> dict[str, bool]:
    try:
        result = await run_in_threadpool(_service().remove_item, item_id=item_id)
    except Exception as exc:
        _raise_public_error(exc)
        raise
    if not result["ok"]:
        raise HTTPException(status_code=404, detail="Plaid item not found.")
    return result
