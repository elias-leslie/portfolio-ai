"""SnapTrade API routes for read-only brokerage data."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, SecretStr

from app.services.credential_crypto import SecretDecryptionError, SecretKeyUnavailableError
from app.services.snaptrade_service import (
    SnapTradeConfigurationError,
    SnapTradeIntegrationError,
    SnapTradeService,
)

router = APIRouter(prefix="/api/snaptrade", tags=["snaptrade"])


class SnapTradeConfigureRequest(BaseModel):
    client_id: SecretStr
    consumer_key: SecretStr
    redirect_uri: str | None = None
    default_broker: str | None = "FIDELITY"


class SnapTradeConnectionPortalRequest(BaseModel):
    broker: str | None = None


def _service() -> SnapTradeService:
    return SnapTradeService()


def _raise_public_error(exc: Exception) -> None:
    if isinstance(exc, SnapTradeIntegrationError):
        raise HTTPException(status_code=exc.status_code, detail=exc.error_payload) from exc
    if isinstance(exc, SnapTradeConfigurationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, (SecretDecryptionError, SecretKeyUnavailableError)):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail="SnapTrade request failed.") from exc


@router.get("/status")
async def get_snaptrade_status() -> dict[str, object]:
    try:
        return await run_in_threadpool(_service().get_status)
    except Exception as exc:
        _raise_public_error(exc)
        raise


@router.post("/configure")
async def configure_snaptrade(payload: SnapTradeConfigureRequest) -> dict[str, object]:
    try:
        return await run_in_threadpool(
            _service().configure,
            client_id=payload.client_id.get_secret_value(),
            consumer_key=payload.consumer_key.get_secret_value(),
            redirect_uri=payload.redirect_uri,
            default_broker=payload.default_broker,
        )
    except Exception as exc:
        _raise_public_error(exc)
        raise


@router.post("/connection-portal")
async def create_snaptrade_connection_portal(
    payload: SnapTradeConnectionPortalRequest | None = None,
) -> dict[str, object]:
    try:
        return await run_in_threadpool(
            _service().create_connection_portal,
            broker=payload.broker if payload else None,
        )
    except Exception as exc:
        _raise_public_error(exc)
        raise


@router.post("/sync")
async def sync_snaptrade() -> dict[str, object]:
    try:
        return await run_in_threadpool(_service().sync)
    except Exception as exc:
        _raise_public_error(exc)
        raise
