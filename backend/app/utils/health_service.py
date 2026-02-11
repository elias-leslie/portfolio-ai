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
    AgentStats,
    APIKeyStatus,
    APIQuotaInfo,
    CacheStats,
    CheckResult,
    DayBarFreshness,
    SourceHealthCheck,
    WatchlistStats,
    WorkerInfo,
    check_database,
    check_sources,
    get_agent_stats,
    get_api_key_statuses,
    get_api_quotas,
    get_cache_stats,
    get_day_bars_freshness,
    get_watchlist_stats,
    get_worker_info,
)
from .health_workflows import get_workflow_health, get_workflow_metrics

logger = get_logger(__name__)

# Track application start time for uptime calculation
APP_START_TIME = datetime.now(UTC)

# Backward compatibility aliases for renamed models
APIKeyStatusInfo = APIKeyStatus  # Old name -> new name
DayBarFreshnessInfo = DayBarFreshness  # Old name -> new name
CeleryWorkerStatus = WorkerInfo  # Old name -> new name (backward compat)

# Re-export models for backward compatibility with any external imports
__all__ = [
    "APIKeyStatus",
    "APIKeyStatusInfo",  # Alias
    "APIQuotaInfo",
    "AgentStats",
    "CacheStats",
    "CeleryWorkerStatus",  # Alias
    "CheckResult",
    "DayBarFreshness",
    "DayBarFreshnessInfo",  # Alias
    "DiskUsageInfo",
    "HealthCheckService",
    "SourceHealthCheck",
    "WatchlistStats",
    "WorkerInfo",
]


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

        # Critical checks - now returns Pydantic model directly
        checks["database"] = check_database(self.storage)

        # Data source checks - now returns Pydantic models directly
        sources = check_sources(self.storage)

        # Service process checks (skip slow service inspect for fast health checks)
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

        # Get statistics - now returns Pydantic models directly
        cache_stats = get_cache_stats(self.storage)
        agent_stats = get_agent_stats(self.storage)
        workflow_health = get_workflow_health(self.storage)
        watchlist_stats = get_watchlist_stats(self.storage)
        api_quotas = get_api_quotas(self.storage)

        # Calculate uptime
        uptime_seconds = int((datetime.now(UTC) - APP_START_TIME).total_seconds())

        return {
            "status": overall_status,
            "uptime_seconds": uptime_seconds,
            "checks": checks,
            "sources": sources,
            "services": services_dict,
            "cache_stats": cache_stats,
            "agent_stats": agent_stats,
            "watchlist_stats": watchlist_stats,
            "api_quotas": api_quotas,
            "workflow_health": workflow_health,
        }

    def perform_detailed_health_check(self) -> dict[str, Any]:
        """Perform comprehensive health check with additional system details.

        Returns:
            Dictionary with all check results including additional system details
        """
        # Get base health check data
        base_health = self.perform_health_check()

        # Get additional detailed checks - now returns Pydantic models directly
        day_bars_freshness = get_day_bars_freshness(self.storage)
        worker = get_worker_info()
        api_keys = get_api_key_statuses(self.storage)

        disk_usage_internal = get_disk_usage()
        disk_usage = DiskUsageInfo(
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
            day_bars_symbols=len(day_bars_freshness),
            worker_active=worker.active,
            api_keys_configured=sum(1 for k in api_keys if k.configured),
            disk_percent_used=disk_usage.percent_used,
        )

        return {
            # Base fields
            **base_health,
            # Detailed fields
            "day_bars_freshness": day_bars_freshness,
            "celery_worker": worker,
            "api_keys": api_keys,
            "disk_usage": disk_usage,
            "workflow_metrics": workflow_metrics,
        }
