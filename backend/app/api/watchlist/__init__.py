"""Watchlist API router package.

Aggregates domain-specific routers into a single watchlist router.
"""

from __future__ import annotations

from fastapi import APIRouter

from .crud_router import router as crud_router
from .refresh_router import router as refresh_router
from .reports_router import router as reports_router
from .review_router import router as review_router

# Create main router with prefix and tags
router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

# Include all domain routers
router.include_router(crud_router)
router.include_router(refresh_router)
router.include_router(reports_router)
router.include_router(review_router)

__all__ = ["router"]
