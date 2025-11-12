"""Health check endpoints for portfolio-ai.

This module provides comprehensive health checks for monitoring
system status, dependencies, and service availability including multi-source data fetching.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..middleware.cache import clear_cache
from ..middleware.cache import get_cache_stats as get_response_cache_stats
from ..services.resource_monitor import get_disk_usage
from ..services.service_monitor import get_all_service_statuses
from ..storage import get_storage
from ..utils.health_checks import (
    check_database,
    check_sources,
    get_agent_stats,
    get_api_key_statuses,
    get_api_quotas,
    get_cache_stats,
    get_celery_worker_info,
    get_day_bars_freshness,
    get_watchlist_stats,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# Track application start time for uptime calculation
APP_START_TIME = datetime.now(UTC)


# Pydantic models for API responses (wrap internal classes)
class SourceHealthCheck(BaseModel):
    """Health check for individual data source."""

    status: Literal["ok", "degraded", "down"]
    last_success: datetime | None = None
    success_rate: float | None = None
    avg_latency_ms: int | None = None
    rate_limit_hits: int = 0
    in_cooldown: bool = False
    cooldown_remaining_seconds: int = 0


class CheckResult(BaseModel):
    """Individual health check result."""

    status: Literal["ok", "degraded", "down"]
    latency_ms: int | None = None
    last_success: datetime | None = None
    message: str | None = None


class CacheStats(BaseModel):
    """Price cache statistics."""

    total_cached: int
    cache_age_minutes: float | None = None


class AgentStats(BaseModel):
    """Agent execution statistics."""

    total_runs: int
    completed_runs: int
    failed_runs: int
    avg_duration_s: float | None = None
    avg_cost_usd: float | None = None


class WatchlistStats(BaseModel):
    """Watchlist statistics."""

    total_items: int
    last_refresh: datetime | None = None
    refresh_age_minutes: float | None = None
    items_with_scores: int = 0


class APIQuotaInfo(BaseModel):
    """API quota information for external data sources."""

    source_name: str
    configured: bool
    rate_limit: str | None = None  # e.g., "8 req/min"
    daily_limit: str | None = None  # e.g., "800/day"
    estimated_capacity: int | None = None  # Max tickers for 15-min refresh


class DayBarFreshnessInfo(BaseModel):
    """Data freshness for a ticker's day_bars."""

    ticker: str
    last_updated: datetime | None = None
    age_days: int | None = None


class CeleryWorkerStatus(BaseModel):
    """Celery worker status information."""

    active: bool
    pool_size: int | None = None
    active_tasks: int | None = None
    message: str = ""


class APIKeyStatusInfo(BaseModel):
    """API key configuration status."""

    source: str
    configured: bool
    env_var: str


class DiskUsageInfo(BaseModel):
    """Disk usage statistics."""

    total_gb: float
    used_gb: float
    free_gb: float
    percent_used: float
    status: Literal["ok", "warning", "critical"]


class HealthCheckResponse(BaseModel):
    """Complete health check response."""

    status: Literal["healthy", "degraded", "down"]
    timestamp: datetime = Field(default_factory=datetime.now)
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


class DetailedHealthCheckResponse(HealthCheckResponse):
    """Extended health check response with additional system details."""

    day_bars_freshness: list[DayBarFreshnessInfo] = Field(default_factory=list)
    celery_worker: CeleryWorkerStatus | None = None
    api_keys: list[APIKeyStatusInfo] = Field(default_factory=list)
    disk_usage: DiskUsageInfo | None = None


class HealthCheckService:
    """Service for performing health checks."""

    def __init__(self) -> None:
        """Initialize health check service."""
        self.storage = get_storage()

    def perform_health_check(self) -> HealthCheckResponse:
        """Perform all health checks including multi-source data fetching.

        Returns:
            HealthCheckResponse with all check results
        """
        checks: dict[str, CheckResult] = {}

        # Critical checks - convert internal to Pydantic models
        db_result = check_database(self.storage)
        checks["database"] = CheckResult(
            status=db_result.status,
            latency_ms=db_result.latency_ms,
            last_success=db_result.last_success,
            message=db_result.message,
        )

        # Data source checks (from source_performance table) - convert to Pydantic
        sources_internal = check_sources(self.storage)
        sources = {
            name: SourceHealthCheck(
                status=src.status,
                last_success=src.last_success,
                success_rate=src.success_rate,
                avg_latency_ms=src.avg_latency_ms,
                rate_limit_hits=src.rate_limit_hits,
                in_cooldown=src.in_cooldown,
                cooldown_remaining_seconds=src.cooldown_remaining_seconds,
            )
            for name, src in sources_internal.items()
        }

        # Service process checks (skip slow Celery inspect for fast health checks)
        service_statuses = get_all_service_statuses(skip_slow_checks=True)
        services_dict = {name: status.model_dump() for name, status in service_statuses.items()}

        # Determine overall status
        if checks["database"].status == "down":
            overall_status: Literal["healthy", "degraded", "down"] = "down"
        elif any(check.status == "degraded" for check in checks.values()):
            overall_status = "degraded"
        elif any(source.status == "down" for source in sources.values()):
            # If all sources are down, we're degraded (not completely down)
            if all(source.status == "down" for source in sources.values()) and sources:
                overall_status = "degraded"
            else:
                overall_status = "healthy"
        else:
            overall_status = "healthy"

        # Get statistics - convert internal to Pydantic
        cache_stats_internal = get_cache_stats(self.storage)
        cache_stats_model = CacheStats(
            total_cached=cache_stats_internal.total_cached,
            cache_age_minutes=cache_stats_internal.cache_age_minutes,
        )

        agent_stats_internal = get_agent_stats(self.storage)
        agent_stats_model = AgentStats(
            total_runs=agent_stats_internal.total_runs,
            completed_runs=agent_stats_internal.completed_runs,
            failed_runs=agent_stats_internal.failed_runs,
            avg_duration_s=agent_stats_internal.avg_duration_s,
            avg_cost_usd=agent_stats_internal.avg_cost_usd,
        )

        watchlist_stats_internal = get_watchlist_stats(self.storage)
        watchlist_stats_model = WatchlistStats(
            total_items=watchlist_stats_internal.total_items,
            last_refresh=watchlist_stats_internal.last_refresh,
            refresh_age_minutes=watchlist_stats_internal.refresh_age_minutes,
            items_with_scores=watchlist_stats_internal.items_with_scores,
        )

        api_quotas_internal = get_api_quotas(self.storage)
        api_quotas_model = [
            APIQuotaInfo(
                source_name=q.source_name,
                configured=q.configured,
                rate_limit=q.rate_limit,
                daily_limit=q.daily_limit,
                estimated_capacity=q.estimated_capacity,
            )
            for q in api_quotas_internal
        ]

        # Calculate uptime
        uptime_seconds = int((datetime.now(UTC) - APP_START_TIME).total_seconds())

        return HealthCheckResponse(
            status=overall_status,
            uptime_seconds=uptime_seconds,
            checks=checks,
            sources=sources,
            services=services_dict,
            cache_stats=cache_stats_model,
            agent_stats=agent_stats_model,
            watchlist_stats=watchlist_stats_model,
            api_quotas=api_quotas_model,
        )

    def perform_detailed_health_check(self) -> DetailedHealthCheckResponse:
        """Perform comprehensive health check with additional system details.

        Returns:
            DetailedHealthCheckResponse with all check results including:
            - All standard health checks
            - Day bars data freshness per ticker
            - Celery worker active status
            - API key configuration status
            - Disk usage information
        """
        # Get base health check data
        base_health = self.perform_health_check()

        # Get additional detailed checks
        day_bars_freshness_internal = get_day_bars_freshness(self.storage)
        day_bars_freshness_model = [
            DayBarFreshnessInfo(
                ticker=item.ticker,
                last_updated=item.last_updated,
                age_days=item.age_days,
            )
            for item in day_bars_freshness_internal
        ]

        celery_worker_internal = get_celery_worker_info()
        celery_worker_model = CeleryWorkerStatus(
            active=celery_worker_internal.active,
            pool_size=celery_worker_internal.pool_size,
            active_tasks=celery_worker_internal.active_tasks,
            message=celery_worker_internal.message,
        )

        api_keys_internal = get_api_key_statuses(self.storage)
        api_keys_model = [
            APIKeyStatusInfo(
                source=item.source,
                configured=item.configured,
                env_var=item.env_var,
            )
            for item in api_keys_internal
        ]

        disk_usage_internal = get_disk_usage()
        disk_usage_model = DiskUsageInfo(**disk_usage_internal)

        logger.info(
            "detailed_health_check_performed",
            status=base_health.status,
            day_bars_tickers=len(day_bars_freshness_model),
            celery_active=celery_worker_model.active,
            api_keys_configured=sum(1 for k in api_keys_model if k.configured),
            disk_percent_used=disk_usage_model.percent_used,
        )

        return DetailedHealthCheckResponse(
            # Base fields
            status=base_health.status,
            timestamp=base_health.timestamp,
            version=base_health.version,
            uptime_seconds=base_health.uptime_seconds,
            checks=base_health.checks,
            sources=base_health.sources,
            services=base_health.services,
            cache_stats=base_health.cache_stats,
            agent_stats=base_health.agent_stats,
            watchlist_stats=base_health.watchlist_stats,
            api_quotas=base_health.api_quotas,
            # Detailed fields
            day_bars_freshness=day_bars_freshness_model,
            celery_worker=celery_worker_model,
            api_keys=api_keys_model,
            disk_usage=disk_usage_model,
        )


# Create singleton instance
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
    if result.status == "down":
        response.status_code = 503

    # Build source status summary for logging
    source_status_summary = {name: src.status for name, src in result.sources.items()}

    logger.info(
        "health_check_performed",
        status=result.status,
        uptime_seconds=result.uptime_seconds,
        database_status=result.checks["database"].status,
        sources=source_status_summary,
        num_sources=len(result.sources),
    )

    return result


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
    if result.status == "down":
        response.status_code = 503

    logger.info(
        "detailed_health_check_endpoint",
        status=result.status,
        day_bars_tickers=len(result.day_bars_freshness),
        celery_active=result.celery_worker.active if result.celery_worker else False,
        api_keys_configured=sum(1 for k in result.api_keys if k.configured),
    )

    return result


@router.get("/simple")
async def simple_health_check() -> dict[str, str]:
    """Simple health check endpoint (legacy compatibility).

    Returns:
        Simple status dict
    """
    return {"status": "healthy"}


class DeletionRate(BaseModel):
    """Deletion rate monitoring response."""

    status: Literal["ok", "warning", "critical"]
    time_window_hours: int
    deletions_by_table: dict[str, int]
    total_deletions: int
    alert_threshold_warning: int = 10
    alert_threshold_critical: int = 100
    message: str


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

    Example:
        GET /api/health/deletion-rate?hours=1
        {
            "status": "warning",
            "time_window_hours": 1,
            "deletions_by_table": {
                "watchlist_items": 12,
                "watchlist_snapshots": 245
            },
            "total_deletions": 257,
            "message": "⚠️  High deletion rate detected"
        }
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


@router.get("/cache/stats", response_model=ResponseCacheStats)
async def get_cache_statistics() -> ResponseCacheStats:
    """Get response cache statistics.

    Returns cache size, hit rate, and other metrics for the response caching middleware.

    Returns:
        Response cache statistics including hit rate and size

    Example:
        GET /health/cache/stats
        {
            "enabled": true,
            "size": 42,
            "max_size": 1000,
            "ttl_default": 300,
            "hits": 1234,
            "misses": 567,
            "hit_rate": 68.5,
            "invalidations": 89
        }
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


class CacheClearResponse(BaseModel):
    """Response for cache clear operation."""

    status: str
    cleared_entries: int
    message: str


@router.post("/cache/clear", response_model=CacheClearResponse)
async def clear_response_cache() -> CacheClearResponse:
    """Clear all response cache entries.

    Clears the entire response cache, forcing fresh data fetches for all cached endpoints.
    Use this when you need to ensure all data is up-to-date.

    Returns:
        Cache clear status with number of entries cleared

    Example:
        POST /health/cache/clear
        {
            "status": "success",
            "cleared_entries": 42,
            "message": "Cleared 42 cache entries"
        }
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
