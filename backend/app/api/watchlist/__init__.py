"""Watchlist API router package.

Aggregates domain-specific routers into a single watchlist router.
"""

from __future__ import annotations

from fastapi import APIRouter

from .crud_router import router as crud_router
from .refresh_router import router as refresh_router

# reports_router removed - daily report feature disabled (never executed, no data)
from .review_router import router as review_router

# Create main router (prefix applied in main.py)
router = APIRouter(tags=["watchlist"])

# Include all domain routers - specific routes first, catch-all {item_id} last
router.include_router(refresh_router)  # /refresh - specific route
router.include_router(review_router)  # /review - specific route
router.include_router(crud_router)  # /{item_id} - catch-all, must be last

__all__ = ["router"]
