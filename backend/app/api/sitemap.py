"""Sitemap API - Dynamic endpoint discovery and health monitoring.

Endpoints:
- GET /api/sitemap/entries - List all entries with filters
- GET /api/sitemap/entries/{id} - Get single entry detail
- POST /api/sitemap/discover - Trigger full discovery scan (OpenAPI + crawler + Next.js)
- POST /api/sitemap/discover/nextjs - Trigger Next.js route discovery only
- POST /api/sitemap/check/{id} - Check single entry health
- POST /api/sitemap/check-all - Check all entries health (manual trigger)
- GET /api/sitemap/health-summary - Aggregate health stats
- POST /api/sitemap/register - Manually register entry
- DELETE /api/sitemap/entries/{id} - Remove entry
- GET /api/sitemap/history-stats - Get history stats for maintenance
- POST /api/sitemap/cleanup-history - Trigger history cleanup
- GET /api/sitemap/ports - Get auto-discovered ports from systemd services
- POST /api/sitemap/ports/refresh - Force refresh port discovery cache
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..services.sitemap import SitemapService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/sitemap", tags=["sitemap"])


# =========================================================================
# Request/Response Models
# =========================================================================


class SitemapEntry(BaseModel):
    """Sitemap entry response model."""

    id: int
    port: int
    path: str
    method: str
    entry_type: str
    source: str | None
    title: str | None
    parent_path: str | None
    health_status: str
    console_errors: int
    console_warnings: int
    http_status: int | None
    response_time_ms: int | None
    last_error_message: str | None
    artifact_id: int | None
    last_checked_at: str | None
    discovered_at: str | None


class SitemapListResponse(BaseModel):
    """Response for listing sitemap entries."""

    total: int
    entries: list[SitemapEntry]


class HealthSummaryResponse(BaseModel):
    """Response for health summary."""

    total: int
    healthy: int
    warning: int
    error: int
    unknown: int
    by_port: dict[str, dict[str, int]]


class RegisterRequest(BaseModel):
    """Request to manually register an entry."""

    port: int = Field(..., description="Port number (3000, 8000, etc.)")
    path: str = Field(..., description="URL path")
    method: str = Field("GET", description="HTTP method")
    entry_type: str = Field("manual", description="Entry type")
    title: str | None = None


class DiscoveryResponse(BaseModel):
    """Response from comprehensive discovery scan."""

    openapi_discovered: int  # All ports with OpenAPI (backend, dev-companion, etc.)
    frontend_discovered: int  # Crawler-discovered pages
    websocket_discovered: int = 0  # WebSocket endpoints
    nextjs_discovered: int = 0  # Next.js app directory routes
    total_saved: int


class NextJsDiscoveryResponse(BaseModel):
    """Response from Next.js route discovery."""

    routes_discovered: int
    routes: list[dict[str, Any]]


class HealthCheckResponse(BaseModel):
    """Response from health check."""

    success: bool
    entry_id: int | None = None
    health_status: str | None = None
    console_errors: int | None = None
    console_warnings: int | None = None
    http_status: int | None = None
    response_time_ms: int | None = None
    error: str | None = None


class HistoryStatsResponse(BaseModel):
    """Response for history statistics."""

    total_rows: int
    oldest_entry: str | None
    storage_size: str


class CleanupResponse(BaseModel):
    """Response from cleanup operation."""

    deleted: int
    retention_days: int


class DiscoveredPortResponse(BaseModel):
    """Response for a discovered port."""

    port: int
    service_name: str
    service_type: str
    source: str
    description: str | None


class DiscoveredPortsResponse(BaseModel):
    """Response for all discovered ports."""

    ports: list[DiscoveredPortResponse]
    frontend_port: int


# =========================================================================
# Endpoints
# =========================================================================


@router.get("/entries", response_model=SitemapListResponse)
def list_entries(
    port: int | None = Query(None, description="Filter by port"),
    health_status: str | None = Query(None, description="Filter by health status"),
    entry_type: str | None = Query(None, description="Filter by entry type"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> SitemapListResponse:
    """List sitemap entries with optional filters."""
    service = SitemapService()
    entries, total = service.get_entries(
        port=port,
        health_status=health_status,
        entry_type=entry_type,
        limit=limit,
        offset=offset,
    )
    return SitemapListResponse(total=total, entries=entries)  # type: ignore


@router.get("/entries/{entry_id}", response_model=SitemapEntry)
def get_entry(entry_id: int) -> SitemapEntry:
    """Get a single sitemap entry by ID."""
    service = SitemapService()
    entry = service.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return SitemapEntry(**entry)


@router.post("/discover", response_model=DiscoveryResponse)
async def trigger_discovery() -> DiscoveryResponse:
    """Trigger discovery scan for new endpoints.

    Runs OpenAPI scan for backend + crawler for frontend + Next.js routes + api_capabilities.
    """
    service = SitemapService()
    result = await service.run_discovery()
    return DiscoveryResponse(**result)


@router.post("/discover/nextjs", response_model=NextJsDiscoveryResponse)
def discover_nextjs_routes() -> NextJsDiscoveryResponse:
    """Discover routes by parsing Next.js app directory.

    Parses frontend/app/**/page.tsx files to find:
    - Static routes (/watchlist, /portfolio)
    - Dynamic routes (/ideas/{id})
    - Tab variations (?tab=workflows, ?tab=database)

    This is also included in the main /discover endpoint.
    """
    service = SitemapService()
    routes = service.discover_nextjs_routes()
    return NextJsDiscoveryResponse(routes_discovered=len(routes), routes=routes)


@router.post("/check/{entry_id}", response_model=HealthCheckResponse)
async def check_entry_health(entry_id: int) -> HealthCheckResponse:
    """Check health of a single sitemap entry."""
    service = SitemapService()
    result = await service.check_entry_health(entry_id)
    return HealthCheckResponse(**result)


@router.post("/check-all")
async def check_all_health() -> dict[str, Any]:
    """Trigger health check of all sitemap entries.

    Queues a Celery task to run in background - does not block.
    The health check spawns Playwright for frontend pages which is resource-intensive.
    """
    from app.tasks.sitemap_tasks import check_sitemap_health  # noqa: PLC0415

    task = check_sitemap_health.delay()
    return {
        "status": "queued",
        "task_id": task.id,
        "message": "Health check queued as background task",
    }


@router.get("/health-summary", response_model=HealthSummaryResponse)
def get_health_summary() -> HealthSummaryResponse:
    """Get aggregate health statistics."""
    service = SitemapService()
    summary = service.get_health_summary()
    return HealthSummaryResponse(**summary)


@router.post("/register", response_model=SitemapEntry)
def register_entry(request: RegisterRequest) -> SitemapEntry:
    """Manually register a new sitemap entry."""
    service = SitemapService()
    try:
        entry = service.register_entry(
            port=request.port,
            path=request.path,
            method=request.method,
            entry_type=request.entry_type,
            title=request.title,
        )
        if entry is None:
            raise HTTPException(status_code=400, detail="Failed to register entry")
        return SitemapEntry(**entry)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int) -> dict[str, Any]:
    """Delete a sitemap entry."""
    service = SitemapService()
    deleted = service.delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"success": True, "deleted_id": entry_id}


# =========================================================================
# Maintenance Endpoints (for Status page)
# =========================================================================


@router.get("/history-stats", response_model=HistoryStatsResponse)
def get_history_stats() -> HistoryStatsResponse:
    """Get health history statistics for maintenance UI."""
    service = SitemapService()
    stats = service.get_history_stats()
    return HistoryStatsResponse(**stats)


@router.post("/cleanup-history", response_model=CleanupResponse)
def cleanup_history(
    days: int = Query(7, ge=1, le=30, description="Days to retain"),
) -> CleanupResponse:
    """Manually trigger cleanup of old health history."""
    service = SitemapService()
    deleted = service.cleanup_old_history(days=days)
    return CleanupResponse(deleted=deleted, retention_days=days)


# =========================================================================
# Port Discovery Endpoints
# =========================================================================


@router.get("/ports", response_model=DiscoveredPortsResponse)
def get_discovered_ports() -> DiscoveredPortsResponse:
    """Get all auto-discovered ports from systemd services.

    Discovers portfolio-* services from systemd user services and extracts
    their port configuration from service files.
    """
    service = SitemapService()
    ports = service.get_discovered_ports()
    return DiscoveredPortsResponse(
        ports=ports,  # type: ignore
        frontend_port=service.frontend_port,
    )


@router.post("/ports/refresh", response_model=DiscoveredPortsResponse)
def refresh_port_discovery() -> DiscoveredPortsResponse:
    """Force refresh of port discovery cache.

    Use this after adding/removing/modifying systemd services.
    """
    service = SitemapService()
    ports = service.refresh_port_discovery()
    return DiscoveredPortsResponse(
        ports=ports,  # type: ignore
        frontend_port=service.frontend_port,
    )
