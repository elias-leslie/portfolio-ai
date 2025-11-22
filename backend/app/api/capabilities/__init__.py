"""System Capabilities API endpoints.

This package provides REST API endpoints to expose system capability data:
- Database table capabilities (db_capabilities)
- Celery task capabilities (celery_capabilities)
- API endpoint capabilities (api_capabilities)
- AI-generated insights (capability_insights)
- Human annotations (capability_notes)

The package is organized into focused routers:
- capabilities_router: Core capability endpoints (list, detail, health, scan)
- insights_router: Insight endpoints (list, review)
- notes_router: Note endpoints (create, list)
"""

from __future__ import annotations

from fastapi import APIRouter

from .capabilities_router import router as capabilities_router
from .insights_router import router as insights_router
from .notes_router import router as notes_router

# Combine all routers into a single router
router = APIRouter(prefix="/api/capabilities", tags=["capabilities"])
router.include_router(capabilities_router)
router.include_router(insights_router)
router.include_router(notes_router)
