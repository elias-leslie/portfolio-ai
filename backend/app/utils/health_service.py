"""Health check service for performing system health checks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, cast

from pydantic import BaseModel

from ..logging_config import get_logger
from ..services.resource_monitor import get_disk_usage
from ..services.service_monitor import get_all_service_statuses
from ..storage import get_storage
from .health_checks import (
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
from .health_workflows import get_workflow_health, get_workflow_metrics

logger = get_logger(__name__)

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
    rate_limit: str | None = None
    daily_limit: str | None = None
    estimated_capacity: int | None = None


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


class HealthCheckService:
    """Service for performing health checks."""

    def __init__(self) -> None:
        """Initialize health check service."""
        self.storage = get_storage()

    def perform_health_check(self) -> dict[str, Any]:
        """Perform all health checks including multi-source data fetching.

        Returns:
            Dictionary with all check results (to be wrapped in HealthCheckResponse)
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

        # Get workflow health (already returns Pydantic model)
        workflow_health_model = get_workflow_health(self.storage)

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

        return {
            "status": overall_status,
            "uptime_seconds": uptime_seconds,
            "checks": checks,
            "sources": sources,
            "services": services_dict,
            "cache_stats": cache_stats_model,
            "agent_stats": agent_stats_model,
            "watchlist_stats": watchlist_stats_model,
            "api_quotas": api_quotas_model,
            "workflow_health": workflow_health_model,
        }

    def perform_detailed_health_check(self) -> dict[str, Any]:
        """Perform comprehensive health check with additional system details.

        Returns:
            Dictionary with all check results including additional system details
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
        disk_usage_model = DiskUsageInfo(
            total_gb=disk_usage_internal["total_gb"],
            used_gb=disk_usage_internal["used_gb"],
            free_gb=disk_usage_internal["free_gb"],
            percent_used=disk_usage_internal["percent_used"],
            status=cast(Literal["ok", "warning", "critical"], disk_usage_internal["status"]),
        )

        workflow_metrics = get_workflow_metrics(self.storage)

        logger.info(
            "detailed_health_check_performed",
            status=base_health["status"],
            day_bars_tickers=len(day_bars_freshness_model),
            celery_active=celery_worker_model.active,
            api_keys_configured=sum(1 for k in api_keys_model if k.configured),
            disk_percent_used=disk_usage_model.percent_used,
        )

        return {
            # Base fields
            **base_health,
            # Detailed fields
            "day_bars_freshness": day_bars_freshness_model,
            "celery_worker": celery_worker_model,
            "api_keys": api_keys_model,
            "disk_usage": disk_usage_model,
            "workflow_metrics": workflow_metrics,
        }
