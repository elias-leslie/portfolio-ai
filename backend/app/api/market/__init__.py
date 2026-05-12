"""Market API package - aggregates all market routers."""

from fastapi import APIRouter

from app.api.market.core_router import router as core_router
from app.api.market.corporate_router import router as corporate_router
from app.api.market.events_router import router as events_router
from app.api.market.historical_router import router as historical_router

# Create main router with /api/market prefix
router = APIRouter(prefix="/api/market", tags=["market"])

# Include all domain routers
router.include_router(core_router)
router.include_router(historical_router)
router.include_router(events_router)
router.include_router(corporate_router)

__all__ = ["router"]
