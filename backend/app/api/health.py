"""Health check endpoints for portfolio-ai.

This module provides comprehensive health checks for monitoring
system status, dependencies, and service availability including multi-source data fetching.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..middleware.cache import clear_cache
from ..middleware.cache import get_cache_stats as get_response_cache_stats
from ..storage import get_storage
from ..utils.health_service import (
    AgentStats,
    APIKeyStatusInfo,
    APIQuotaInfo,
    CacheStats,
    CeleryWorkerStatus,
    CheckResult,
    DayBarFreshnessInfo,
    DiskUsageInfo,
    HealthCheckService,
    SourceHealthCheck,
    WatchlistStats,
    WorkflowHealthInfo,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


# API Response Models
class HealthCheckResponse(BaseModel):
    """Complete health check response."""

    status: Literal["healthy", "degraded", "down"]
    timestamp: str = Field(default_factory=lambda: str(__import__("datetime").datetime.now()))
    version: str = "1.0.0"
    uptime_seconds: int
    checks: dict[str, CheckResult]
    sources: dict[str, SourceHealthCheck] = Field(default_factory=dict)
    services: dict[str, Any] = Field(
        default_factory=dict,
        description="Service process status (backend, celery, frontend, redis)",
    )
    cache_stats: CacheStats | None = None
    agent_stats: AgentStats | None = None
    watchlist_stats: WatchlistStats | None = None
    api_quotas: list[APIQuotaInfo] = Field(default_factory=list)
    workflow_health: WorkflowHealthInfo | None = None


class DetailedHealthCheckResponse(HealthCheckResponse):
    """Extended health check response with additional system details."""

    day_bars_freshness: list[DayBarFreshnessInfo] = Field(default_factory=list)
    celery_worker: CeleryWorkerStatus | None = None
    api_keys: list[APIKeyStatusInfo] = Field(default_factory=list)
    disk_usage: DiskUsageInfo | None = None
    workflow_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow metrics for last 7 days",
    )


class DeletionRate(BaseModel):
    """Deletion rate monitoring response."""

    status: Literal["ok", "warning", "critical"]
    time_window_hours: int
    deletions_by_table: dict[str, int]
    total_deletions: int
    alert_threshold_warning: int = 10
    alert_threshold_critical: int = 100
    message: str


class ResponseCacheStats(BaseModel):
    """Response cache statistics."""

    enabled: bool
    size: int
    max_size: int
    ttl_default: int
    hits: int
    misses: int
    hit_rate: float
    invalidations: int


class CacheClearResponse(BaseModel):
    """Response for cache clear operation."""

    status: str
    cleared_entries: int
    message: str


# Create singleton health check service instance
health_service = HealthCheckService()


@router.get("", response_model=HealthCheckResponse)
async def health_check(response: Response) -> HealthCheckResponse:
    """Comprehensive health check endpoint.

    Returns health status, uptime, and metrics for all system components including
    multi-source data fetching health (yfinance, polygon, etc).
    Returns HTTP 503 if database is down, HTTP 200 otherwise.
    """
    result = health_service.perform_health_check()

    # Set appropriate HTTP status code
    if result["status"] == "down":
        response.status_code = 503

    # Build source status summary for logging
    source_status_summary = {name: src.status for name, src in result["sources"].items()}

    logger.info(
        "health_check_performed",
        status=result["status"],
        uptime_seconds=result["uptime_seconds"],
        database_status=result["checks"]["database"].status,
        sources=source_status_summary,
        num_sources=len(result["sources"]),
    )

    return HealthCheckResponse(**result)


@router.get("/detailed", response_model=DetailedHealthCheckResponse)
async def detailed_health_check(response: Response) -> DetailedHealthCheckResponse:
    """Comprehensive health check endpoint with additional system details.

    Returns detailed health status including:
    - All standard health checks (database, sources, services, etc.)
    - Day bars data freshness per ticker
    - Celery worker active status and pool information
    - API key configuration status
    - Disk usage statistics

    Returns HTTP 503 if database is down, HTTP 200 otherwise.
    """
    result = health_service.perform_detailed_health_check()

    # Set appropriate HTTP status code
    if result["status"] == "down":
        response.status_code = 503

    logger.info(
        "detailed_health_check_endpoint",
        status=result["status"],
        day_bars_tickers=len(result["day_bars_freshness"]),
        celery_active=result["celery_worker"].active if result["celery_worker"] else False,
        api_keys_configured=sum(1 for k in result["api_keys"] if k.configured),
    )

    return DetailedHealthCheckResponse(**result)


@router.get("/simple")
async def simple_health_check() -> dict[str, str]:
    """Simple health check endpoint (legacy compatibility).

    Returns:
        Simple status dict
    """
    return {"status": "healthy"}


@router.get("/deletion-rate", response_model=DeletionRate)
async def get_deletion_rate(hours: int = 1) -> DeletionRate:
    """Monitor deletion rate for incident detection.

    Created: 2025-11-10 (Response to Nov 9 deletion incident)

    Tracks deletions from critical tables to detect mass deletion events
    that may indicate data loss incidents, migration issues, or bugs.

    Alert thresholds:
    - Warning: >10 deletions in time window
    - Critical: >100 deletions in time window

    Args:
        hours: Time window in hours (default: 1)

    Returns:
        Deletion rate summary with alert status
    """
    storage = get_storage()

    try:
        # Query deletion_audit table (requires migration 024)
        query = """
        SELECT
            table_name,
            COUNT(*) as deletion_count
        FROM deletion_audit
        WHERE deleted_at > NOW() - INTERVAL '1 hour' * ?
        GROUP BY table_name
        ORDER BY deletion_count DESC
        """

        with storage.connection() as conn:
            result = conn.execute(query, [hours]).pl()

        # Build deletion summary
        deletions_by_table = {}
        if not result.is_empty():
            for row in result.iter_rows(named=True):
                deletions_by_table[row["table_name"]] = row["deletion_count"]

        total_deletions = sum(deletions_by_table.values())

        # Determine alert status
        status: Literal["ok", "warning", "critical"]
        if total_deletions >= 100:
            status = "critical"
            message = f"🔴 CRITICAL: {total_deletions} deletions in last {hours}h (threshold: 100)"
        elif total_deletions >= 10:
            status = "warning"
            message = f"⚠️  WARNING: {total_deletions} deletions in last {hours}h (threshold: 10)"
        else:
            status = "ok"
            message = f"✅ OK: {total_deletions} deletions in last {hours}h"

        logger.info(
            "deletion_rate_check",
            status=status,
            total_deletions=total_deletions,
            time_window_hours=hours,
            deletions_by_table=deletions_by_table,
        )

        return DeletionRate(
            status=status,
            time_window_hours=hours,
            deletions_by_table=deletions_by_table,
            total_deletions=total_deletions,
            message=message,
        )

    except Exception as e:
        # If deletion_audit table doesn't exist (migration 024 not applied),
        # return OK status with explanation
        logger.warning("deletion_audit_check_failed", error=str(e))

        return DeletionRate(
            status="ok",
            time_window_hours=hours,
            deletions_by_table={},
            total_deletions=0,
            message=f"⚠️  Deletion auditing not enabled (migration 024 required): {e}",
        )


@router.get("/cache/stats", response_model=ResponseCacheStats)
async def get_cache_statistics() -> ResponseCacheStats:
    """Get response cache statistics.

    Returns cache size, hit rate, and other metrics for the response caching middleware.
    """
    stats = get_response_cache_stats()

    logger.info(
        "cache_stats_retrieved",
        cache_size=stats["size"],
        hit_rate=stats["hit_rate"],
        total_hits=stats["hits"],
        total_misses=stats["misses"],
    )

    return ResponseCacheStats(**stats)


@router.post("/cache/clear", response_model=CacheClearResponse)
async def clear_response_cache() -> CacheClearResponse:
    """Clear all response cache entries.

    Clears the entire response cache, forcing fresh data fetches for all cached endpoints.
    Use this when you need to ensure all data is up-to-date.
    """
    cleared_count = clear_cache()

    logger.info(
        "cache_cleared",
        cleared_entries=cleared_count,
    )

    return CacheClearResponse(
        status="success",
        cleared_entries=cleared_count,
        message=f"Cleared {cleared_count} cache entries",
    )
