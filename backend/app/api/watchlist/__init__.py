"""Watchlist API router package.

Aggregates domain-specific routers into a single watchlist router.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.watchlist.response_builders import WatchlistItemResponse, WatchlistListResponse

from .crud_router import create_watchlist_item, get_score_history, list_watchlist_items
from .crud_router import router as crud_router
from .refresh_router import router as refresh_router

# reports_router removed - daily report feature disabled (never executed, no data)
from .review_router import router as review_router

# Create main router (prefix applied in main.py as /api/watchlist)
router = APIRouter(tags=["watchlist"])

# Register root endpoints without trailing slash for Next.js proxy compatibility
# (Next.js rewrites strip trailing slashes; redirect_slashes=False avoids loops)
router.add_api_route("", list_watchlist_items, methods=["GET"], response_model=WatchlistListResponse)
router.add_api_route("", create_watchlist_item, methods=["POST"], response_model=WatchlistItemResponse, status_code=201)

# Include all domain routers - specific routes first, catch-all {item_id} last
router.include_router(refresh_router)  # /refresh - specific route
router.include_router(review_router)  # /review - specific route
router.include_router(crud_router)  # / and /{item_id} - catch-all, must be last

__all__ = ["get_score_history", "router"]
