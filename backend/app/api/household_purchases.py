"""Item-level purchase tracking endpoints."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from app.models.household_finance import (
    HouseholdPriceCheckStatus,
    HouseholdPriceCheckTriggerResponse,
    HouseholdProductDetail,
    HouseholdProductList,
    HouseholdProductMergeRequest,
    HouseholdPurchaseItem,
    HouseholdPurchaseItemCategoryUpdate,
    HouseholdPurchaseItemOwnerUpdate,
    HouseholdPurchaseItemProductAssignment,
    HouseholdPurchaseItemReviewQueue,
    HouseholdShoppingList,
    HouseholdShoppingListImportRequest,
    HouseholdShoppingListImportResponse,
    HouseholdShoppingListRequest,
    HouseholdShoppingListsResponse,
    HouseholdVendorProfileList,
    HouseholdVendorProfileUpdate,
)

if TYPE_CHECKING:
    from app.services.household_finance_service import HouseholdFinanceService
    from app.services.household_price_check_service import HouseholdPriceCheckService
    from app.services.household_product_catalog_service import (
        HouseholdProductCatalogService,
    )
    from app.services.household_shopping_list_service import (
        HouseholdShoppingListService,
    )

router = APIRouter(prefix="/api/household", tags=["household-purchases"])

_ASSIGNMENT_ACTIONS = {"confirm", "reassign", "detach"}


@lru_cache(maxsize=1)
def _service() -> HouseholdFinanceService:
    return import_module("app.services.household_finance_service").HouseholdFinanceService()


@lru_cache(maxsize=1)
def _catalog() -> HouseholdProductCatalogService:
    return import_module(
        "app.services.household_product_catalog_service"
    ).HouseholdProductCatalogService()


@lru_cache(maxsize=1)
def _price_checks() -> HouseholdPriceCheckService:
    return import_module(
        "app.services.household_price_check_service"
    ).HouseholdPriceCheckService()


@lru_cache(maxsize=1)
def _shopping_lists() -> HouseholdShoppingListService:
    return import_module(
        "app.services.household_shopping_list_service"
    ).HouseholdShoppingListService()


@router.post("/purchase-items/backfill")
async def backfill_purchase_items() -> dict[str, int]:
    """Promote eligible import rows to purchase items and link pending groups."""
    return await run_in_threadpool(_service().purchase_item_service.backfill)


@router.post("/purchase-items/link")
async def link_purchase_groups() -> dict[str, int]:
    """Link pending purchase groups to ledger charges and allocate splits."""
    return await run_in_threadpool(_service().purchase_item_service.link_purchase_groups)


@router.get("/products", response_model=HouseholdProductList)
async def list_household_products(
    search: str = "",
    sort: str = "recent",
    sort_dir: str = "desc",
    scope: str = "active",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> HouseholdProductList:
    """Return the paginated product catalog with sparkline price points."""
    return await run_in_threadpool(
        lambda: _catalog().list_products(
            search=search,
            sort=sort,
            sort_dir=sort_dir,
            scope=scope,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/products/{product_id}", response_model=HouseholdProductDetail)
async def get_household_product(product_id: str) -> HouseholdProductDetail:
    """Return one product with identifiers, price history, and recent purchases."""
    detail = await run_in_threadpool(_catalog().get_product_detail, product_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")
    return detail


@router.post("/products/merge")
async def merge_household_products(
    payload: HouseholdProductMergeRequest,
) -> dict[str, bool]:
    """Merge a duplicate product into a canonical target."""
    merged = await run_in_threadpool(
        lambda: _catalog().merge_products(
            source_product_id=payload.source_product_id,
            target_product_id=payload.target_product_id,
        )
    )
    if not merged:
        raise HTTPException(status_code=404, detail="Products not found or identical")
    return {"ok": True}


@router.get(
    "/transactions/{transaction_id}/purchase-items",
    response_model=list[HouseholdPurchaseItem],
)
async def list_transaction_purchase_items(
    transaction_id: str,
) -> list[HouseholdPurchaseItem]:
    """Return the purchase items linked to a ledger transaction."""
    return await run_in_threadpool(_catalog().list_transaction_items, transaction_id)


@router.get("/purchase-items/review", response_model=HouseholdPurchaseItemReviewQueue)
async def list_purchase_item_review_queue() -> HouseholdPurchaseItemReviewQueue:
    """Return purchase items whose product match needs human review."""
    return await run_in_threadpool(_catalog().list_review_queue)


@router.post("/purchase-items/{item_id}/categorize")
async def categorize_purchase_item(
    item_id: str,
    payload: HouseholdPurchaseItemCategoryUpdate,
) -> dict[str, bool]:
    """Set an item's category/essentiality, optionally as a product rule."""
    updated = await run_in_threadpool(
        _service().purchase_item_service.update_item_category, item_id, payload
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Purchase item not found: {item_id}")
    return {"ok": True}


@router.post("/purchase-items/{item_id}/owner")
async def set_purchase_item_owner(
    item_id: str,
    payload: HouseholdPurchaseItemOwnerUpdate,
) -> dict[str, bool]:
    """Set an item's owner, optionally as a product-level owner rule."""
    updated = await run_in_threadpool(
        _service().purchase_item_service.update_item_owner, item_id, payload
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Purchase item not found: {item_id}")
    return {"ok": True}


@router.post("/price-checks/run", response_model=HouseholdPriceCheckTriggerResponse)
async def trigger_price_check(
    product_limit: int | None = Query(None, ge=1, le=12),
    product_id: list[str] | None = Query(None),
    shopping_list_id: str | None = None,
) -> HouseholdPriceCheckTriggerResponse:
    """Queue a cross-vendor price check and hand it to the Hatchet worker."""
    service = _price_checks()
    run_id, already_running = await run_in_threadpool(
        lambda: service.start_run(
            triggered_by="manual",
            product_limit=product_limit,
            product_ids=product_id,
            shopping_list_id=shopping_list_id,
        )
    )
    if already_running:
        return HouseholdPriceCheckTriggerResponse(run_id=run_id, already_running=True)
    try:
        from app.hatchet_app import get_admin_client  # noqa: PLC0415

        await run_in_threadpool(
            lambda: get_admin_client().run_workflow(
                "portfolio-jenny-weekly-price-check",
                json.dumps({"run_id": run_id, "triggered_by": "manual"}),
            )
        )
    except Exception as exc:
        await run_in_threadpool(service.mark_run_failed, run_id, f"trigger failed: {exc}")
        raise HTTPException(
            status_code=502, detail=f"Could not start price check: {exc}"
        ) from exc
    return HouseholdPriceCheckTriggerResponse(run_id=run_id, already_running=False)


@router.get("/price-checks/status", response_model=HouseholdPriceCheckStatus)
async def get_price_check_status() -> HouseholdPriceCheckStatus:
    """Latest run (with per-vendor outcomes) plus the open savings findings."""
    return await run_in_threadpool(_price_checks().get_status)


@router.get("/shopping-lists", response_model=HouseholdShoppingListsResponse)
async def list_shopping_lists() -> HouseholdShoppingListsResponse:
    """Return shopping lists with current items and latest optimization."""
    return await run_in_threadpool(_shopping_lists().list_shopping_lists)


@router.post("/shopping-lists", response_model=HouseholdShoppingList)
async def create_shopping_list(
    payload: HouseholdShoppingListRequest,
) -> HouseholdShoppingList:
    """Create a shopping list."""
    return await run_in_threadpool(_shopping_lists().create_shopping_list, payload)


@router.put("/shopping-lists/{list_id}", response_model=HouseholdShoppingList)
async def update_shopping_list(
    list_id: str,
    payload: HouseholdShoppingListRequest,
) -> HouseholdShoppingList:
    """Replace a shopping list's editable fields and items."""
    updated = await run_in_threadpool(
        _shopping_lists().update_shopping_list,
        list_id,
        payload,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Shopping list not found: {list_id}")
    return updated


@router.delete("/shopping-lists/{list_id}")
async def delete_shopping_list(list_id: str) -> dict[str, bool]:
    """Archive a shopping list."""
    deleted = await run_in_threadpool(_shopping_lists().archive_shopping_list, list_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Shopping list not found: {list_id}")
    return {"ok": True}


@router.post(
    "/shopping-lists/{list_id}/import",
    response_model=HouseholdShoppingListImportResponse,
)
async def import_shopping_list_items(
    list_id: str,
    payload: HouseholdShoppingListImportRequest,
) -> HouseholdShoppingListImportResponse:
    """Parse pasted list text with Agent Hub and append/replace list items."""
    imported = await run_in_threadpool(_shopping_lists().import_items, list_id, payload)
    if imported is None:
        raise HTTPException(status_code=404, detail=f"Shopping list not found: {list_id}")
    return imported


@router.post("/shopping-lists/{list_id}/optimize", response_model=HouseholdShoppingList)
async def optimize_shopping_list(list_id: str) -> HouseholdShoppingList:
    """Optimize a shopping list from fresh stored vendor quotes."""
    optimized = await run_in_threadpool(_shopping_lists().optimize, list_id)
    if optimized is None:
        raise HTTPException(status_code=404, detail=f"Shopping list not found: {list_id}")
    return optimized


@router.get("/vendor-profiles", response_model=HouseholdVendorProfileList)
async def list_vendor_profiles() -> HouseholdVendorProfileList:
    """Return user-configured vendor fee/membership profiles."""
    return await run_in_threadpool(_shopping_lists().list_vendor_profiles)


@router.put("/vendor-profiles", response_model=HouseholdVendorProfileList)
async def update_vendor_profiles(
    payload: HouseholdVendorProfileUpdate,
) -> HouseholdVendorProfileList:
    """Update user-configured vendor fee/membership profiles."""
    return await run_in_threadpool(_shopping_lists().update_vendor_profiles, payload)


@router.post("/purchase-items/{item_id}/product")
async def assign_purchase_item_product(
    item_id: str,
    payload: HouseholdPurchaseItemProductAssignment,
) -> dict[str, bool]:
    """Confirm, reassign, or detach an item's product link."""
    action = payload.action.strip().lower()
    if action not in _ASSIGNMENT_ACTIONS:
        raise HTTPException(status_code=422, detail=f"Unknown action: {payload.action}")
    changed = await run_in_threadpool(
        lambda: _catalog().assign_product(
            item_id=item_id, action=action, product_id=payload.product_id
        )
    )
    if not changed:
        raise HTTPException(
            status_code=404,
            detail=f"Purchase item not found or action not applicable: {item_id}",
        )
    return {"ok": True}
