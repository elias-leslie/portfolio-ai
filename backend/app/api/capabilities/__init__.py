"""System Capabilities API endpoints.

This package provides REST API endpoints to expose system capability data:
- Database table capabilities (db_capabilities)
- Hatchet workflow capabilities (celery_capabilities table)
- API endpoint capabilities (api_capabilities)
- Human annotations (capability_notes)

Note: Feature capabilities (features_router) migrated to SummitFlow.
      Vision goals/content (vision_goals_router, vision_content_router) migrated to SummitFlow.
      See: portfolio-ai-5rz

The package is organized into focused routers:
- capabilities_router: Core capability endpoints (list, detail, health, scan)
- notes_router: Note endpoints (create, list)
"""

from __future__ import annotations

from fastapi import APIRouter

from .capabilities_router import get_capabilities
from .capabilities_router import router as capabilities_router
from .models import CapabilitiesListResponse
from .notes_router import router as notes_router

# Combine all routers into a single router
router = APIRouter(prefix="/api/capabilities", tags=["capabilities"])
router.include_router(notes_router)
router.include_router(capabilities_router)  # Has catch-all /{type}/{id} route

# Root list endpoint at /api/capabilities (no trailing slash) for Next.js proxy compat
router.add_api_route("", get_capabilities, methods=["GET"], response_model=CapabilitiesListResponse)
