"""Camera uploads have a narrow member-scoped API, separate from financial intake."""

from __future__ import annotations

import asyncio
import io
from functools import lru_cache
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from starlette.datastructures import Headers
from starlette.responses import FileResponse

from app.api.intake import _service as intake_service
from app.models.household_capture import CaptureReview, CaptureView
from app.models.household_shopping_pilot import (
    ComparisonResult,
    FamilyConfirmation,
    OfferConfirmation,
    PackageConfirmation,
    PilotProduct,
    ShoppingComparison,
)
from app.services.household_capture_service import HouseholdCaptureService
from app.services.household_identity import request_identity, require_adult
from app.services.household_shopping_pilot import HouseholdShoppingPilot
from app.storage import get_storage

router = APIRouter(prefix="/api/captures", tags=["captures"])
_promote_lock = asyncio.Lock()
_MAX_BYTES = 15 * 1024 * 1024


@lru_cache(maxsize=1)
def _service() -> HouseholdCaptureService:
    return HouseholdCaptureService()


@router.get("", response_model=list[CaptureView])
def list_captures(request: Request) -> list[CaptureView]:
    return _service().list_captures(request_identity(request))


class CaptureMember(BaseModel):
    id: str
    name: str


@router.get("/members", response_model=list[CaptureMember])
def review_members(request: Request) -> list[CaptureMember]:
    require_adult(request_identity(request))
    with get_storage().connection() as conn:
        rows = conn.execute(
            "SELECT id, display_name FROM household_members ORDER BY created_at"
        ).fetchall()
    return [CaptureMember(id=str(row[0]), name=row[1]) for row in rows]


@router.post("", response_model=CaptureView)
async def capture(
    request: Request,
    file: UploadFile = File(...),
    client_id: UUID = Form(...),
    member_scope: str = Form(...),
    kind: Literal["receipt", "shelf_tag"] = Form(...),
    store_name: str = Form(default="", max_length=120),
    note: str = Form(default="", max_length=1000),
) -> CaptureView:
    identity = request_identity(request)
    if member_scope != (identity.member_id or "local"):
        raise HTTPException(
            409,
            "This draft belongs to another sign-in. Switch back to its member before uploading.",
        )
    content = await file.read(_MAX_BYTES + 1)
    if len(content) > _MAX_BYTES:
        raise HTTPException(413, "Choose an image or receipt smaller than 15 MB.")
    signatures = [
        (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
        (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
        (b"%PDF-", "application/pdf", ".pdf"),
    ]
    match = next(
        ((mime, suffix) for sig, mime, suffix in signatures if content.startswith(sig)), None
    )
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        match = ("image/webp", ".webp")
    if match is None or (kind == "shelf_tag" and match[0] == "application/pdf"):
        raise HTTPException(415, "Use a JPEG, PNG or WebP photo, or a PDF receipt.")
    mime, suffix = match
    return await run_in_threadpool(
        _service().save,
        identity,
        client_id=str(client_id),
        kind=kind,
        content=content,
        filename=f"{kind}{suffix}",
        content_type=mime,
        store_name=store_name,
        note=note,
    )


@router.get("/{capture_id}/image")
def capture_image(request: Request, capture_id: UUID) -> FileResponse:
    path, content_type = _service().image(request_identity(request), str(capture_id))
    return FileResponse(
        path,
        media_type=content_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )


@router.patch("/{capture_id}", response_model=CaptureView)
def review_capture(request: Request, capture_id: UUID, payload: CaptureReview) -> CaptureView:
    return _service().review(request_identity(request), str(capture_id), payload)


@router.post("/{capture_id}/intake", response_model=CaptureView)
async def send_to_intake(
    request: Request, capture_id: UUID, background_tasks: BackgroundTasks
) -> CaptureView:
    identity = request_identity(request)
    require_adult(identity)
    async with _promote_lock:
        capture = await run_in_threadpool(_service().get, identity, str(capture_id))
        if capture.document_id:
            return capture
        if capture.kind != "receipt":
            raise HTTPException(
                422, "Shelf tags are price evidence; they do not belong in the transaction ledger."
            )
        path, mime = await run_in_threadpool(_service().image, identity, str(capture_id))
        service = intake_service()
        content = await run_in_threadpool(path.read_bytes)
        upload = UploadFile(
            io.BytesIO(content), filename=capture.filename, headers=Headers({"content-type": mime})
        )
        document = await service.ingest_document(
            upload=upload, source_type="receipt", document_type="receipt"
        )
        result = await run_in_threadpool(
            _service().attach_document, identity, str(capture_id), document.id
        )
        background_tasks.add_task(service.review_document, document.id)
        return result


# Keep the small shopping lookup beside capture. The child allow-list permits
# only the product names/stores and an ephemeral comparison, never confirmations.


@router.get("/shopping/products", response_model=list[PilotProduct])
def shopping_products() -> list[PilotProduct]:
    service = HouseholdShoppingPilot()
    with service.storage.connection() as conn:
        return service.products(conn)


@router.get("/shopping/review")
def shopping_review(request: Request):
    return HouseholdShoppingPilot().review(request_identity(request))


@router.post("/shopping/compare", response_model=ComparisonResult)
def compare_shopping(payload: ShoppingComparison) -> ComparisonResult:
    return HouseholdShoppingPilot().compare(payload)


@router.post("/shopping/{product_id}/package")
def confirm_package(request: Request, product_id: UUID, payload: PackageConfirmation):
    HouseholdShoppingPilot().confirm_package(request_identity(request), str(product_id), payload)
    return {"status": "confirmed"}


@router.post("/shopping/offers")
def confirm_shopping_offer(request: Request, payload: OfferConfirmation):
    return {"id": HouseholdShoppingPilot().confirm_offer(request_identity(request), payload)}


@router.post("/shopping/families")
def confirm_shopping_family(request: Request, payload: FamilyConfirmation):
    HouseholdShoppingPilot().confirm_family(request_identity(request), payload)
    return {"status": "confirmed"}


@router.post("/shopping/offers/{offer_id}/withdraw")
def withdraw_shopping_offer(request: Request, offer_id: UUID):
    HouseholdShoppingPilot().withdraw_offer(request_identity(request), str(offer_id))
    return {"status": "withdrawn"}


@router.post("/shopping/{product_id}/ungroup")
def ungroup_shopping_product(request: Request, product_id: UUID):
    HouseholdShoppingPilot().ungroup(request_identity(request), str(product_id))
    return {"status": "ungrouped"}
