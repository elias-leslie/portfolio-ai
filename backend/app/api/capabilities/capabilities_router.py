"""Capabilities router - main capabilities endpoints.

This module provides REST API endpoints for core system capability data:
- GET / - List all capabilities (with filtering/pagination)
- GET /health/summary - Health status summary across all capability types
- GET /{type}/{id} - Get detailed capability view with insights/notes
- POST /scan - Trigger manual capabilities scan
- GET /cleanup-candidates - Orphaned/legacy capabilities for review
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager
from ...tasks.capability_tasks import scan_system_capabilities
from ..types import DependenciesDict, HealthSummaryDict
from ._queries import (
    SYSTEM_TABLES,
    build_health_summary,
    extract_dependencies,
    fetch_api_cleanup_candidates,
    fetch_capability_record,
    fetch_db_cleanup_candidates,
    fetch_hatchet_cleanup_candidates,
    fetch_insights,
    fetch_notes,
    query_all_capabilities,
    query_single_type_capabilities,
)
from .models import CapabilitiesListResponse, CapabilityDetailResponse, ScanTriggerResponse

logger = get_logger(__name__)

router = APIRouter(prefix="")

__all__ = [
    "SYSTEM_TABLES",
    "get_capabilities",
    "get_capability_detail",
    "get_cleanup_candidates",
    "get_health_summary",
    "router",
    "trigger_scan",
]


@router.get("/", response_model=CapabilitiesListResponse)
async def get_capabilities(
    type: str = Query("all", description="Filter by type: db, hatchet, api, or all"),
    category: str | None = Query(None, description="Filter by category"),
    status: str | None = Query(None, description="Filter by status (db only)"),
    health_status: str | None = Query(
        None, description="Filter by health: active, orphaned, legacy, suspect"
    ),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results offset"),
) -> CapabilitiesListResponse:
    """Get paginated list of system capabilities."""
    if type not in ("all", "db", "hatchet", "api"):
        raise HTTPException(status_code=400, detail=f"Invalid type: {type}")

    conn_mgr = get_connection_manager()
    try:
        with conn_mgr.connection() as conn:
            if type == "all":
                capabilities, total = query_all_capabilities(
                    conn,
                    category=category,
                    health_status=health_status,
                    limit=limit,
                    offset=offset,
                )
            else:
                capabilities, total = query_single_type_capabilities(
                    conn, type,
                    category=category,
                    status=status,
                    health_status=health_status,
                    limit=limit,
                    offset=offset,
                )

        logger.info(
            "capabilities_list_retrieved",
            type=type, category=category, status=status,
            health_status=health_status, total=total,
            returned=len(capabilities), limit=limit, offset=offset,
        )
        return CapabilitiesListResponse(total=total, capabilities=capabilities)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("capabilities_list_error", error=str(e), type=type)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve capabilities: {e}"
        ) from e


@router.get("/health/summary")
async def get_health_summary() -> HealthSummaryDict:
    """Get health status summary across all capability types."""
    conn_mgr = get_connection_manager()
    try:
        with conn_mgr.connection() as conn:
            summary: HealthSummaryDict = build_health_summary(conn)  # type: ignore[assignment]

        logger.info(
            "health_summary_retrieved",
            total=summary["total"],
            active=summary["by_status"]["active"],
            orphaned=summary["by_status"]["orphaned"],
            legacy=summary["by_status"]["legacy"],
            suspect=summary["by_status"]["suspect"],
        )
        return summary

    except Exception as e:
        logger.error("health_summary_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve health summary: {e}"
        ) from e


@router.get("/{capability_type}/{capability_id}", response_model=CapabilityDetailResponse)
async def get_capability_detail(
    capability_type: Literal["db", "hatchet", "api"],
    capability_id: int,
) -> CapabilityDetailResponse:
    """Get detailed view of a single capability with related insights, notes, and dependencies."""
    conn_mgr = get_connection_manager()
    try:
        with conn_mgr.connection() as conn:
            cap = fetch_capability_record(conn, capability_type, capability_id)
            if cap is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Capability not found: {capability_type}/{capability_id}",
                )
            insights = fetch_insights(conn, capability_type, capability_id)
            notes = fetch_notes(conn, capability_type, capability_id)
            dependencies: DependenciesDict = extract_dependencies(cap, capability_type)

        logger.info(
            "capability_detail_retrieved",
            capability_type=capability_type,
            capability_id=capability_id,
            insights_count=len(insights),
            notes_count=len(notes),
        )
        return CapabilityDetailResponse(
            capability=cap,
            insights=insights,
            notes=notes,
            dependencies=dependencies,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "capability_detail_error",
            error=str(e),
            capability_type=capability_type,
            capability_id=capability_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve capability: {e}"
        ) from e


@router.post("/scan", response_model=ScanTriggerResponse)
async def trigger_scan() -> ScanTriggerResponse:
    """Trigger a manual system capabilities scan."""
    try:
        task = scan_system_capabilities()
        logger.info("capabilities_scan_triggered", task_id=task.get("status"))
        return ScanTriggerResponse(
            task_id=task.get("status", "completed"),
            status="completed",
            message="Capabilities scan completed",
        )
    except Exception as e:
        logger.error("scan_trigger_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger scan: {e}") from e


@router.get("/cleanup-candidates")
async def get_cleanup_candidates() -> dict[str, Any]:
    """Get all orphaned and legacy capabilities for cleanup review.

    Used by /scrub_it command to identify items that may be safe to remove.
    IMPORTANT: Items returned here still require verification before removal.
    """
    conn_mgr = get_connection_manager()
    try:
        with conn_mgr.connection() as conn:
            db_items = fetch_db_cleanup_candidates(conn)
            hatchet_items = fetch_hatchet_cleanup_candidates(conn)
            api_items = fetch_api_cleanup_candidates(conn)

        total = len(db_items) + len(hatchet_items) + len(api_items)
        by_status: dict[str, int] = {"orphaned": 0, "legacy": 0}
        for item in [*db_items, *hatchet_items, *api_items]:
            h = item.get("health_status")
            if isinstance(h, str) and h in by_status:
                by_status[h] += 1

        logger.info(
            "cleanup_candidates_retrieved",
            total=total,
            database=len(db_items),
            hatchet=len(hatchet_items),
            api=len(api_items),
        )
        return {
            "database": db_items,
            "hatchet": hatchet_items,
            "api": api_items,
            "summary": {"total_candidates": total, "by_status": by_status},
        }

    except Exception as e:
        logger.error("cleanup_candidates_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve cleanup candidates: {e}"
        ) from e
